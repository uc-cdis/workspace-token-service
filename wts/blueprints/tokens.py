import flask
import traceback

from ..auth import authenticate
from ..tokens import get_access_token


blueprint = flask.Blueprint("token", __name__)

blueprint.route("")


@blueprint.route("/")
def get_token():
    requested_idp = flask.request.args.get("idp", "default")
    authenticate(allow_access_token=(requested_idp != "default"))

    expires = flask.request.args.get("expires")
    if expires:
        try:
            expires = int(expires)
        except ValueError:
            return flask.jsonify({"error": "expires has to be an integer"}), 400

    try:
        access_token = get_access_token(requested_idp, expires=expires)
    except Exception:
        traceback.print_exc()
        raise
    return flask.jsonify({"token": access_token})
