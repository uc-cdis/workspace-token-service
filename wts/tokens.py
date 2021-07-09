import flask
import requests
import time
import httpx

from cdiserrors import AuthError, InternalError, UserError

from .models import db, RefreshToken
from .utils import get_oauth_client


def get_data_for_fence_request(refresh_token):
    token = refresh_token.token
    if hasattr(flask.current_app, "encryption_key"):
        token = flask.current_app.encryption_key.decrypt(token)
    client = get_oauth_client(idp=refresh_token.idp)
    url = client.metadata.get("access_token_url")
    data = {"grant_type": "refresh_token", "refresh_token": token}
    auth = (client.client_id, client.client_secret)
    return url, data, auth


def get_access_token(requested_idp, expires=None):
    if requested_idp not in flask.current_app.oauth2_clients:
        raise UserError('Requested IDP "{}" is not configured'.format(requested_idp))
    refresh_token = (
        db.session.query(RefreshToken)
        .filter_by(username=flask.g.user.username)
        .filter_by(idp=requested_idp)
        .order_by(RefreshToken.expires.desc())
        .first()
    )
    now = int(time.time())
    if not refresh_token:
        raise AuthError("User doesn't have a refresh token")
    if refresh_token.expires <= now:
        raise AuthError("your refresh token is expired, please login again")
    url, data, auth = get_data_for_fence_request(refresh_token)
    try:
        r = requests.post(url, data=data, auth=auth)
    except Exception:
        raise InternalError("Fail to reach fence")
    if r.status_code != 200:
        raise InternalError("Fail to get a access token from fence: {}".format(r.text))
    return r.json()["access_token"]


async def async_get_access_token(refresh_token):
    try:
        url, data, auth = get_data_for_fence_request(refresh_token)
        async with httpx.AsyncClient() as http_client:
            r = await http_client.post(url, data=data, auth=auth)
    except httpx.RequestError as e:
        flask.current_app.logger.error(
            "Failed to POST %s to obtain access token", e.request.url
        )
        return ""
    except httpx.HTTPStatusError as e:
        flask.current_app.logger.error(
            "Failed to POST %s to obtain access token. Status code: %s",
            e.request.url,
            e.response.status_code,
        )
        return ""
    except:
        return ""
    return r.json()["access_token"]
