import asyncio
import flask
import httpx
import requests
import time

from urllib.parse import urljoin, urlparse

from ..auth import async_login_required
from ..models import db, RefreshToken
from ..tokens import async_get_access_token


blueprint = flask.Blueprint("aggregate", __name__)


@blueprint.route("/authz", methods=["GET"])
@async_login_required
async def get_aggregate_authz():
    auth_header = {"Authorization": flask.request.headers.get("Authorization")}

    # XXX consider multiple idps per commons and multiple tokens per idp
    # XXX maybe filter by unexpired
    # XXX should we return {} for commons that haven't been linked yet (i.e. no refresh token)
    refresh_tokens = (
        db.session.query(RefreshToken)
        .filter_by(username=flask.g.user.username)
        .filter(RefreshToken.expires > int(time.time()))
        .order_by(RefreshToken.expires.asc())
    )

    #  XXX better comment
    #  we want the latest refresh tokens to win
    aggregate_tokens = {
        flask.current_app.config["OIDC"][rt.idp]["api_base_url"]: rt
        for rt in refresh_tokens
    }

    async def get_user_info(fence_url, refresh_token):
        #  fence_url = flask.current_app.config["OIDC"][refresh_token.idp]["api_base_url"]
        fence_user_info_url = urljoin(fence_url, "user")

        commons_hostname = urlparse(fence_url).netloc
        authz_info = {}
        access_token = await async_get_access_token(refresh_token)
        if not access_token:
            return [commons_hostname, authz_info]
        auth_header = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient() as client:
                user_info_response = await client.get(
                    fence_user_info_url, headers=auth_header
                )
        except httpx.RequestError as e:
            flask.current_app.logger.error(
                "Failed to get response for user authz info from %s.", e.request.url
            )
            return [commons_hostname, authz_info]
        except httpx.HTTPStatusError as e:
            flask.current_app.logger.error(
                "Failed to get user authz info from %s. Status code: %s",
                e.request.url,
                e.response.status_code,
            )

        authz_info = user_info_response.json()["authz"]
        return [commons_hostname, authz_info]

    commons_user_info = await asyncio.gather(
        *[get_user_info(u, t) for u, t in aggregate_tokens.items()]
    )

    return flask.jsonify({c: i for c, i in commons_user_info})
