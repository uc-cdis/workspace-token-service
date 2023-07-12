import flask
import time
import httpx

from cdiserrors import AuthError, InternalError, UserError

from .models import db, RefreshToken
from .utils import get_oauth_client


def get_data_for_fence_request(refresh_token):
    """
    Given `refresh_token`, prepare data for request to IdP's token endpoint.

    Args:
        refresh_token (wts.models.RefreshToken): refresh token reference

    Return:
        tuple: (url(str), data(dict), auth(tuple))
    """
    token = refresh_token.token
    token_bytes = bytes(token, encoding="utf-8")
    token = flask.current_app.encryption_key.decrypt(token_bytes).decode("utf-8")
    client = get_oauth_client(idp=refresh_token.idp)
    url = client.metadata.get("access_token_url")
    data = {"grant_type": "refresh_token", "refresh_token": token}
    auth = (client.client_id, client.client_secret)
    return (url, data, auth)


def get_access_token(requested_idp, expires=None):
    if requested_idp not in flask.current_app.oauth2_clients:
        raise UserError('Requested IdP "{}" is not configured'.format(requested_idp))
    username = flask.g.user.username
    flask.current_app.logger.info(
        "Getting refresh token for user '{}', IdP '{}'".format(username, requested_idp)
    )
    refresh_token = (
        db.session.query(RefreshToken)
        .filter_by(username=username)
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


async def async_get_access_token(refresh_token, commons_hostname=None):
    """
    Make an asynchronous request to obtain an access token given 'refresh_token'.

    Args:
        refresh_token (wts.models.RefreshToken): refresh token reference
        commons_hostname (str): optional. name of the data commons, extracted from refresh token if absent.

    Return:
        tuple: (commons_hostname(str), access_token(str or None))
    """
    if not refresh_token:
        return commons_hostname, None

    if not commons_hostname:
        commons_hostname = flask.current_app.config["OIDC"][refresh_token.idp][
            "commons_hostname"
        ]
    access_token = None
    try:
        url, data, auth = get_data_for_fence_request(refresh_token)
        async with httpx.AsyncClient() as http_client:
            res = await http_client.post(url, data=data, auth=auth)
            res.raise_for_status()
            access_token = res.json()["access_token"]
    except httpx.RequestError as e:
        flask.current_app.logger.error(
            "Failed to POST {} to obtain access token".format(e.request.url)
        )
    except httpx.HTTPStatusError as e:
        flask.current_app.logger.error(
            "Failed to POST {} to obtain access token. Status code: {}".format(
                e.request.url, e.response.status_code
            )
        )
    except Exception as e:
        flask.current_app.logger.error(
            "Failed to get access token for {}. Exception - {}".format(
                commons_hostname, e
            )
        )
    return commons_hostname, access_token
