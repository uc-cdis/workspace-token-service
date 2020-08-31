import flask

from ..auth import login_required
from ..tokens import get_access_token
from ..utils import get_oauth_client


blueprint = flask.Blueprint("token", __name__)

blueprint.route("")


@blueprint.route("/")
@login_required
def get_token():
    expires = flask.request.args.get("expires")
    if expires:
        try:
            expires = int(expires)
        except ValueError:
            return flask.jsonify({"error": "expires has to be an integer"}), 400

    requested_idp = flask.request.args.get("idp", "default")
    try:
        client = get_oauth_client(idp=requested_idp)
    except KeyError:
        return flask.jsonify({"error": "requested idp not configured"}), 400
    return flask.jsonify(
        {"token": get_access_token(requested_idp, client, expires=expires)}
    )
