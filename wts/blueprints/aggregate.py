import asyncio
import flask
import httpx
import time
from cdiserrors import NotFoundError, UserError

from ..auth import authenticate
from ..models import db, RefreshToken
from ..tokens import async_get_access_token


blueprint = flask.Blueprint("aggregate", __name__)


@blueprint.route("/<path:endpoint>", methods=["GET"])
async def get_aggregate_response(endpoint):
    """
    Proxy GET requests to `endpoint` on each linked commons and return
    an aggregated response.

    For an authenticated request, each proxied request incudes an access token
    fetched using the current user's refresh token.

    The size of the aggregated response body can be reduced by supplying a
    `filters` parameter. If provided, only return JSON key-value pairs whose
    key is in `filters`. Multiple filters can be specified:

    `GET /aggregate/user/user?filters=authz&filters=username`
    """
    # for `GET /aggregate/user/user`, flask sets endpoint to 'user/user'
    endpoint = f"/{endpoint}"
    if endpoint not in flask.current_app.config["AGGREGATE_ENDPOINT_ALLOWLIST"]:
        raise NotFoundError(
            "supplied endpoint is not configured in the Workspace Token Service aggregate endpoint allowlist"
        )

    filters = flask.request.args.getlist("filters")
    parameters = flask.request.args.to_dict()
    parameters.pop("filters", None)

    if flask.request.headers.get("Authorization"):
        authenticate(allow_access_token=True)
        refresh_tokens = (
            db.session.query(RefreshToken)
            .filter_by(username=flask.g.user.username)
            .filter(RefreshToken.expires > int(time.time()))
            .order_by(RefreshToken.expires.asc())
        )
        #  if a user has multiple refresh tokens for the same commons, we want
        #  the latest one to be used. see
        #  https://stackoverflow.com/questions/39678672/is-a-python-dict-comprehension-always-last-wins-if-there-are-duplicate-keys
        refresh_tokens = {
            flask.current_app.config["OIDC"][rt.idp]["commons_hostname"]: rt
            for rt in refresh_tokens
        }
        access_tokens = await asyncio.gather(
            *[async_get_access_token(rt) for rt in refresh_tokens.values()]
        )
        request_info = [
            (commons, endpoint, {"Authorization": f"Bearer {access_token}"})
            if access_token
            else (commons, None, None)
            for commons, access_token in access_tokens
        ]
    else:
        request_info = [
            (commons, endpoint, {})
            for commons in flask.current_app.config["COMMONS_HOSTNAMES"]
        ]

    commons_user_info = await asyncio.gather(
        *[
            make_request(commons, endpoint, headers, parameters, filters)
            for commons, endpoint, headers in request_info
        ]
    )

    return flask.jsonify({c: i for c, i in commons_user_info})


async def make_request(commons_hostname, endpoint, headers, parameters, filters):
    """
    Make an asychronous request to `endpoint` on `commons_hostname`.
    """

    # represent failure to get data with `null` JSON value (Python `None` will
    # be serialized as JSON `null`)
    failure_indicator = (commons_hostname, None)
    if endpoint is None:
        return failure_indicator
    endpoint_url = f"https://{commons_hostname}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            endpoint_response = await client.get(
                endpoint_url, headers=headers, params=parameters
            )
            endpoint_response.raise_for_status()
    except httpx.RequestError as e:
        flask.current_app.logger.error("Failed to get response from %s.", e.request.url)
        return failure_indicator
    except httpx.HTTPStatusError as e:
        flask.current_app.logger.error(
            "Status code %s returned from %s",
            e.response.status_code,
            e.request.url,
        )
        return failure_indicator

    data = endpoint_response.json()
    for filter_parameter in filters:
        if filter_parameter not in data:
            raise UserError(
                f"at least one of the provided filters is not a key in the response returned from {endpoint_url}"
            )

    if filters:
        data = {k: data[k] for k in filters}
    return (commons_hostname, data)
