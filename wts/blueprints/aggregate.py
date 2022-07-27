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
    Send GET requests to the specified endpoint on all of the current user's linked commons and return an aggregated response.
    Authentication is performed using an access token supplied in the Authorization header. All url query parameters other than
    filters are passed along to the specified endpoint. `GET /aggregate/user/user?filters=authz&filters=username`

    To reduce the size of the aggregated response body, only return JSON key-value pairs whose key is in filters. Multiple filters
    can be specified by repeating the filters in the URL
    """
    authenticate(allow_access_token=True)
    # for `GET /aggregate/user/user`, flask sets endpoint to 'user/user'
    endpoint = f"/{endpoint}"
    if endpoint not in flask.current_app.config["AGGREGATE_ENDPOINT_ALLOWLIST"]:
        raise NotFoundError(
            "supplied endpoint is not configured in the Workspace Token Service aggregate endpoint allowlist"
        )
    flask.current_app.logger.info(f"Sending an agg request to - {endpoint}")
    filters = flask.request.args.getlist("filters")
    parameters = flask.request.args.to_dict()
    parameters.pop("filters", None)

    refresh_tokens = (
        db.session.query(RefreshToken)
        .filter_by(username=flask.g.user.username)
        .filter(RefreshToken.expires > int(time.time()))
        .order_by(RefreshToken.expires.asc())
    )

    #  if a user has multiple refresh tokens for the same commons, we want the
    #  latest one to be used. see https://stackoverflow.com/questions/39678672/is-a-python-dict-comprehension-always-last-wins-if-there-are-duplicate-keys
    aggregate_tokens = {
        flask.current_app.config["OIDC"][rt.idp]["commons_hostname"]: rt
        for rt in refresh_tokens
    }
    flask.current_app.logger.info(
        f"The agg tokens for all the commons are - {aggregate_tokens}"
    )

    async def get_endpoint(commons_hostname, refresh_token):
        endpoint_url = f"https://{commons_hostname}{endpoint}"

        authz_info = {}
        access_token = await async_get_access_token(refresh_token)
        if not access_token:
            flask.current_app.logger.info(
                f"Access token missing for commons - {commons_hostname}"
            )
            return [commons_hostname, authz_info]
        auth_header = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient() as client:
                endpoint_response = await client.get(
                    endpoint_url, headers=auth_header, params=parameters
                )
                endpoint_response.raise_for_status()
        except httpx.RequestError as e:
            flask.current_app.logger.error(
                "Failed to get response from %s.", e.request.url
            )
            return [commons_hostname, authz_info]
        except httpx.HTTPStatusError as e:
            flask.current_app.logger.error(
                "Status code %s returned from %s",
                e.response.status_code,
                e.request.url,
            )
            return [commons_hostname, authz_info]

        data = endpoint_response.json()
        for filter_parameter in filters:
            if filter_parameter not in data:
                raise UserError(
                    f"at least one of the provided filters is not a key in the response returned from {endpoint_url}"
                )

        if filters:
            data = {k: data[k] for k in filters}
        return (commons_hostname, data)

    commons_user_info = await asyncio.gather(
        *[get_endpoint(u, rt) for u, rt in aggregate_tokens.items()]
    )

    return flask.jsonify({c: i for c, i in commons_user_info})
