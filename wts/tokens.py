import flask
import requests
import time

from cdiserrors import AuthError, InternalError

from .models import db, RefreshToken
from .utils import get_oauth_client


def get_access_token(requested_idp, expires=None):
    client = get_oauth_client(idp=requested_idp)
    now = int(time.time())
    refresh_token = (
        db.session.query(RefreshToken)
        .filter_by(username=flask.g.user.username)
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
        token = flask.current_app.encryption_key.decrypt(token)
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


# XXX put logic in get_access_token
def get_access_token2(refresh_token):
    client = get_oauth_client(idp=refresh_token.idp)
    now = int(time.time())
    if not refresh_token:
        raise AuthError("User doesn't have a refresh token")
    if refresh_token.expires <= now:
        raise AuthError("your refresh token is expired, please login again")
    token = refresh_token.token
    if hasattr(flask.current_app, "encryption_key"):
        token = flask.current_app.encryption_key.decrypt(token)
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
