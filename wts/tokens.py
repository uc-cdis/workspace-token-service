import flask
import requests
import time

from cdiserrors import AuthError, InternalError

from .models import db, RefreshToken
from .utils import get_oauth_client


def get_access_token(requested_idp, expires=None):
    client = get_oauth_client(idp=requested_idp)
    now = int(time.time())
    username = flask.g.user.username
    flask.current_app.logger.info(
        "Getting refresh token for user '{}', IDP '{}'".format(username, requested_idp)
    )
    refresh_token = (
        db.session.query(RefreshToken)
        .filter_by(username=username)
        .filter_by(idp=requested_idp)
        .order_by(RefreshToken.expires.desc())
        .first()
    )
    if not refresh_token:
        raise AuthError("User doesn't have a refresh token")
    if refresh_token.expires <= now:
        raise AuthError("your refresh token is expired, please login again")
    token = refresh_token.token
    if hasattr(flask.current_app, "encryption_key"):
        try:
            token_bytes = bytes(token, encoding="utf-8")
            token = flask.current_app.encryption_key.decrypt(token_bytes).decode(
                "utf-8"
            )
        except Exception as e:
            flask.current_app.logger.error(f"Unable to decrypt refresh token: {e}")
            raise
    data = {"grant_type": "refresh_token", "refresh_token": token}
    auth = (client.client_id, client.client_secret)
    try:
        url = client.metadata.get("access_token_url")
        r = requests.post(url, data=data, auth=auth)
    except Exception:
        raise InternalError("Fail to reach fence")
    if r.status_code != 200:
        raise InternalError("Fail to get a access token from fence: {}".format(r.text))
    return r.json()["access_token"]
