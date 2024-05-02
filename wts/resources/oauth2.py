from authlib.common.errors import AuthlibBaseError
from datetime import datetime
import flask
from jose import jwt

from authutils.user import current_user
from cdiserrors import AuthError

from ..models import RefreshToken, db
from ..utils import get_oauth_client


def client_do_authorize():
    requested_idp = flask.session.get("idp", "default")
    client = get_oauth_client(idp=requested_idp)
    token_url = client.metadata["access_token_url"]
    username_field = client.metadata["username_field"]
    mismatched_state = (
        "state" not in flask.request.args
        or "state" not in flask.session
        or flask.request.args["state"] != flask.session.pop("state")
    )

    print("DEBUG ===================== oauth client  metadata: ", client.metadata)

    if mismatched_state:
        raise AuthError("could not authorize; state did not match across auth requests")
    try:
        tokens = client.fetch_token(token_url, **flask.request.args.to_dict())
        refresh_refresh_token(tokens, requested_idp, username_field)
    except KeyError as e:
        raise AuthError("error in token response: {}".format(tokens))
    except AuthlibBaseError as e:
        raise AuthError(str(e))


def find_valid_refresh_token(username, idp):
    has_valid = False
    for token in (
        db.session.query(RefreshToken).filter_by(username=username).filter_by(idp=idp)
    ):
        flask.current_app.logger.info("find token with exp {}".format(token.expires))
        if datetime.fromtimestamp(token.expires) < datetime.now():
            flask.current_app.logger.info("Purging expired token {}".format(token.jti))
        else:
            has_valid = True
    return has_valid


def refresh_refresh_token(tokens, idp, username_field):
    """
    store new refresh token in db and purge all old tokens for the user
    """
    options = {
        "verify_signature": False,
        "verify_aud": False,
        "verify_iat": False,
        "verify_exp": False,
        "verify_nbf": False,
        "verify_iss": False,
        "verify_sub": False,
        "verify_jti": False,
        "verify_at_hash": False,
        "leeway": 0,
    }

    refresh_token = tokens["refresh_token"]
    id_token = tokens["id_token"]
    # TODO: verify signature with authutils
    id_token = jwt.decode(id_token, key=None, options=options)
    content = jwt.decode(refresh_token, key=None, options=options)
    userid = content["sub"]
    for old_token in (
        db.session.query(RefreshToken).filter_by(userid=userid).filter_by(idp=idp)
    ):
        flask.current_app.logger.info(
            "Refreshing token, purging {}".format(old_token.jti)
        )
        db.session.delete(old_token)
    refresh_token = flask.current_app.encryption_key.encrypt(
        bytes(refresh_token, encoding="utf8")
    ).decode("utf8")

    # get the username of the current logged in user.
    # `current_user` validates the token and relies on `OIDC_ISSUER`
    # to know the issuer
    client = get_oauth_client(idp="default")
    flask.current_app.config["OIDC_ISSUER"] = client.metadata["api_base_url"].strip("/")
    user = current_user
    username = user.username

    idp_username = id_token
    # username field is written like "context.user.name" so we split it and loop through the segments
    for field in username_field.split("."):
        idp_username = idp_username.get(field)

    flask.current_app.logger.info(
        'Linking username "{}" for IdP "{}" to current user "{}"'.format(
            idp_username, idp, username
        )
    )
    new_token = RefreshToken(
        token=refresh_token,
        userid=userid,
        username=username,
        jti=content["jti"],
        expires=content["exp"],
        idp=idp,
    )
    db.session.add(new_token)
    db.session.commit()
