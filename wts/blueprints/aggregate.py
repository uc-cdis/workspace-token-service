import flask
import requests

from urllib.parse import urljoin, urlparse

from ..auth import login_required
from ..models import db, RefreshToken
from ..tokens import get_access_token2


blueprint = flask.Blueprint("aggregate", __name__)


@blueprint.route("/authz", methods=["GET"])
@login_required
def get_aggregate_authz():
    auth_header = {"Authorization": flask.request.headers.get("Authorization")}
    authz_endpoint = "https://john.planx-pla.net/user/user"

    aggregate_tokens = db.session.query(RefreshToken).filter_by(
        username=flask.g.user.username
    )

    aggregate_authz_mappings = {}
    for refresh_token in aggregate_tokens:
        fence_url = flask.current_app.config["OIDC"][refresh_token.idp]["api_base_url"]
        fence_user_info_url = urljoin(fence_url, "user")
        access_token = get_access_token2(refresh_token)
        auth_header = {"Authorization": access_token}
        user_info_response = requests.get(fence_user_info_url, headers=auth_header)

        commons_hostname = urlparse(fence_url).netloc
        aggregate_authz_mappings[commons_hostname] = user_info_response.json()["authz"]

    # response = requests.get(authz_endpoint, headers=auth_header)
    # import pdb; pdb.set_trace()
    if response.status_code == 200:
        return flask.jsonify(aggregate_authz_mappings)
        # return flask.jsonify(response.json()["authz"])
    else:
        return "Error!"
