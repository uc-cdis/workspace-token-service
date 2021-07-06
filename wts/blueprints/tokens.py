import flask

from cdiserrors import AuthError
from ..auth_plugins import find_user
from ..tokens import get_access_token


blueprint = flask.Blueprint("token", __name__)

blueprint.route("")


@blueprint.route("/")
def get_token():
    requested_idp = flask.request.args.get("idp", "default")
    flask.g.user = find_user(allow_access_token=(requested_idp != "default"))
    if not flask.g.user:
        raise AuthError("You need to be authenticated to use this resource")

    expires = flask.request.args.get("expires")
    if expires:
        try:
            expires = int(expires)
        except ValueError:
            return flask.jsonify({"error": "expires has to be an integer"}), 400

    return flask.jsonify({"token": get_access_token(requested_idp, expires=expires)})
