import flask

from authlib.common.security import generate_token
from urllib.parse import urljoin

from authutils.user import current_user
from cdiserrors import APIError, UserError, AuthNError, AuthZError

from ..resources import oauth2
from ..utils import get_oauth_client


blueprint = flask.Blueprint("oauth2", __name__)


@blueprint.route("/connected", methods=["GET"])
def connected():
    """
    Check if user is connected and has a valid token
    """
    requested_idp = flask.request.args.get("idp", "default")
    # `current_user` validates the token and relies on `OIDC_ISSUER`
    # to know the issuer
    client = get_oauth_client(idp=requested_idp)
    flask.current_app.config["OIDC_ISSUER"] = client.metadata["api_base_url"].strip("/")

    try:
        user = current_user
        flask.current_app.logger.info(user)
        username = user.username
    except Exception:
        flask.current_app.logger.exception("fail to get username")
        raise AuthNError("user is not logged in")
    if oauth2.find_valid_refresh_token(username, requested_idp):
        return "", 200
    else:
        raise AuthZError("user is not connected with token service or expired")


@blueprint.route("/authorization_url", methods=["GET"])
def get_authorization_url():
    """
    Provide a redirect to the authorization endpoint from the OP.
    """
    redirect = flask.request.args.get("redirect")
    if redirect and not redirect.startswith("/"):
        raise UserError("only support relative redirect")
    if redirect:
        flask.session["redirect"] = redirect

    requested_idp = flask.request.args.get("idp", "default")
    client = get_oauth_client(idp=requested_idp)
    # This will be the value that was put in the ``metadata`` in config.
    state_prefix = client.metadata.get("state_prefix")
    authorize_url = client.metadata.get("authorize_url")
    print("This is the authorize_url: ", authorize_url)
    state = generate_token()
    if state_prefix:
        state = state_prefix + "-" + state
    # Get the authorization URL and the random state; save the state to check
    # later, and return the URL.
    (authorization_url, state) = client.create_authorization_url(
        authorize_url, state=state
    )
    flask.session["state"] = state
    flask.session["idp"] = requested_idp
    return flask.redirect(authorization_url)


@blueprint.route("/authorize", methods=["GET"])
def do_authorize():
    """
    Send a token request to the OP.
    """
    oauth2.client_do_authorize()
    try:
        redirect = flask.session.pop("redirect")
        return flask.redirect(redirect)
    except KeyError:
        return flask.jsonify({"success": "connected with fence"})


@blueprint.route("/logout", methods=["GET"])
def logout_oauth():
    """
    Log out the user.
    To accomplish this, just revoke the refresh token if provided.

    NOTE: this endpoint doesn't handle the "idp" parameter for now. If we want
    to allow logging out, we'll have to revoke the token associated with the
    specified IdP.
    """
    url = urljoin(flask.current_app.config.get("USER_API"), "/oauth2/revoke")
    token = flask.request.form.get("token")
    client = get_oauth_client(idp="default")

    try:
        client.session.revoke_token(url, token)
    except APIError as e:
        msg = "could not log out, failed to revoke token: {}".format(e.message)
        return msg, 400
    return "", 204
