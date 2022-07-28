import flask
import time
import httpx

from cdiserrors import AuthError, InternalError, UserError

from .models import db, RefreshToken
from .utils import get_oauth_client


def get_data_for_fence_request(refresh_token):
    token = refresh_token.token
    if hasattr(flask.current_app, "encryption_key"):
        try:
            token = str(
                flask.current_app.encryption_key.decrypt(bytes(token, encoding="utf8")),
                encoding="utf8",
            )
        except:
            pass
    client = get_oauth_client(idp=refresh_token.idp)
    flask.current_app.logger.info(f"oidc client metadata -- {client.metadata} ")
    url = client.metadata.get("access_token_url")
    data = {"grant_type": "refresh_token", "refresh_token": token}
    auth = (client.client_id, client.client_secret)
    flask.current_app.logger.info(
        f"The values of the request are url - {url}, data-{data}, auth-{auth} "
    )
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
        r = httpx.post(url, data=data, auth=auth)
    except Exception:
        raise InternalError("Fail to reach fence")
    if r.status_code != 200:
        raise InternalError("Fail to get a access token from fence: {}".format(r.text))
    return r.json()["access_token"]


# TODO: Need to handle the expired refresh token scenario
async def async_get_access_token(refresh_token):
    commons_hostname = flask.current_app.config["OIDC"][refresh_token.idp][
        "commons_hostname"
    ]
    try:
        url, data, auth = get_data_for_fence_request(refresh_token)
        async with httpx.AsyncClient() as http_client:
            res = await http_client.post(url, data=data, auth=auth)
            res.raise_for_status()
    except httpx.RequestError as e:
        flask.current_app.logger.error(
            "Failed to POST %s to obtain access token", e.request.url
        )
        return commons_hostname, ""
    except httpx.HTTPStatusError as e:
        flask.current_app.logger.error(
            "Failed to POST %s to obtain access token. Status code: %s",
            e.request.url,
            e.response.status_code,
        )
        return commons_hostname, ""
    except:
        return commons_hostname, ""
    return commons_hostname, res.json()["access_token"]
