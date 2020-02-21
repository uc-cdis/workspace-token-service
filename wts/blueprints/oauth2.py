import flask
from urllib.parse import urljoin

from authutils.user import current_user
from cdiserrors import APIError, UserError, AuthNError, AuthZError

from ..auth import login_required
from ..resources import oauth2
from ..utils import get_oauth_client


blueprint = flask.Blueprint("oauth2", __name__)


@blueprint.route("/connected", methods=["GET"])
def connected():
    """
    Check if user is connected and has a valid token
    """

    # `current_user` valides the token and needs to know the issuer
    client, requested_idp = get_oauth_client()
    flask.current_app.config["OIDC_ISSUER"] = client.api_base_url.strip("/")

    try:
        user = current_user
        flask.current_app.logger.info(user)
        username = user.username
    except:
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

    # This will be the value that was put in the ``client_kwargs`` in config.
    client, requested_idp = get_oauth_client()
    redirect_uri = client.session.redirect_uri
    # Get the authorization URL and the random state; save the state to check
    # later, and return the URL.
    (authorization_url, state) = client.generate_authorize_redirect(redirect_uri)
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
    """
    url = urljoin(flask.current_app.config.get("USER_API"), "/oauth2/revoke")
    token = flask.request.form.get("token")
    client, _ = get_oauth_client()

    try:
        client.session.revoke_token(url, token)
    except APIError as e:
        msg = "could not log out, failed to revoke token: {}".format(e.message)
        return msg, 400
    return "", 204
