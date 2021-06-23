import flask
import requests
import asyncio
import httpx

from urllib.parse import urljoin, urlparse

from ..auth import async_login_required
from ..models import db, RefreshToken
from ..tokens import get_access_token2


blueprint = flask.Blueprint("aggregate", __name__)


@blueprint.route("/authz", methods=["GET"])
@async_login_required
async def get_aggregate_authz():
    auth_header = {"Authorization": flask.request.headers.get("Authorization")}
    authz_endpoint = "https://john.planx-pla.net/user/user"

    # XXX consider multiple tokens per idp and multiple idps per commons
    aggregate_tokens = db.session.query(RefreshToken).filter_by(
        username=flask.g.user.username
    )

    async def get_user_info(refresh_token):
        fence_url = flask.current_app.config["OIDC"][refresh_token.idp]["api_base_url"]
        fence_user_info_url = urljoin(fence_url, "user")
        access_token = get_access_token2(refresh_token)
        auth_header = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(
                fence_user_info_url, headers=auth_header
            )

        commons_hostname = urlparse(fence_url).netloc
        # XXX need error handling here, can't just call json()
        return [commons_hostname, user_info_response.json()["authz"]]

    commons_user_info = await asyncio.gather(
        *[get_user_info(t) for t in aggregate_tokens]
    )

    return flask.jsonify({c: i for c, i in commons_user_info})
