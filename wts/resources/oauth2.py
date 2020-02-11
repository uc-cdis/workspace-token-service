from authlib.client.errors import OAuthError
from authlib.specs.rfc6749.errors import OAuth2Error
from cdiserrors import AuthError
from datetime import datetime
import flask
from jose import jwt

from ..models import RefreshToken, db


def client_do_authorize():
    redirect_uri = flask.current_app.oauth2_client.session.redirect_uri
    mismatched_state = (
        "state" not in flask.request.args
        or "state" not in flask.session
        or flask.request.args["state"] != flask.session.pop("state")
    )
    if mismatched_state:
        raise AuthError("could not authorize; state did not match across auth requests")
    try:
        tokens = flask.current_app.oauth2_client.fetch_access_token(
            redirect_uri, **flask.request.args.to_dict()
        )
        return refresh_refresh_token(tokens)
    except KeyError as e:
        raise AuthError("error in token response: {}".format(tokens))
    except (OAuth2Error, OAuthError) as e:
        raise AuthError(str(e))


def find_valid_refresh_token(username):
    has_valid = False
    for token in db.session.query(RefreshToken).filter_by(username=username):
        flask.current_app.logger.info("find token with exp {}".format(token.expires))
        if datetime.fromtimestamp(token.expires) < datetime.now():
            flask.current_app.logger.info(
                "Purging expired token {}".format(token.jti)
            )
        else:
            has_valid = True
    return has_valid


def refresh_refresh_token(tokens):
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
    for old_token in db.session.query(RefreshToken).filter_by(userid=userid):
        flask.current_app.logger.info(
            "Refreshing token, purging {}".format(old_token.jti)
        )
        db.session.delete(old_token)
    if hasattr(flask.current_app, "encryption_key"):
        refresh_token = flask.current_app.encryption_key.encrypt(
            bytes(refresh_token, encoding="utf8")
        )

    new_token = RefreshToken(
        token=refresh_token,
        userid=userid,
        username=id_token["context"]["user"]["name"],
        jti=content["jti"],
        expires=content["exp"],
    )
    db.session.add(new_token)
    db.session.commit()
    return refresh_token
