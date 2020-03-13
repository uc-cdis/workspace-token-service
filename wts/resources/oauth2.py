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
    client, _ = get_oauth_client(idp=requested_idp)
    redirect_uri = client.client_kwargs.get("redirect_uri")
    mismatched_state = (
        "state" not in flask.request.args
        or "state" not in flask.session
        or flask.request.args["state"] != flask.session.pop("state")
    )
    if mismatched_state:
        raise AuthError("could not authorize; state did not match across auth requests")
    try:
        tokens = client.fetch_access_token(redirect_uri, **flask.request.args.to_dict())
        return refresh_refresh_token(tokens, requested_idp)
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


def refresh_refresh_token(tokens, idp):
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
    if hasattr(flask.current_app, "encryption_key"):
        refresh_token = flask.current_app.encryption_key.encrypt(
            bytes(refresh_token, encoding="utf8")
        )

    # get the username of the current logged in user.
    # `current_user` validates the token and relies on `OIDC_ISSUER`
    # to know the issuer
    client, _ = get_oauth_client(idp="default")
    flask.current_app.config["OIDC_ISSUER"] = client.api_base_url.strip("/")
    user = current_user
    username = user.username

    flask.current_app.logger.info(
        'Linking username "{}" for IDP "{}" to current user "{}"'.format(
            id_token["context"]["user"]["name"], idp, username
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
    return refresh_token
