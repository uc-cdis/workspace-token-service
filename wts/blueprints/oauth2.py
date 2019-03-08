from cdiserrors import APIError
import flask
from urllib.parse import urljoin
from ..resources import oauth2
from ..auth import login_required


blueprint = flask.Blueprint("oauth2", __name__)


@blueprint.route("/authorization_url", methods=["GET"])
def get_authorization_url():
    """
    Provide a redirect to the authorization endpoint from the OP.
    """
    redirect = flask.request.args.get('redirect')
    if not redirect.startswith("/"):
        raise UserError("only support relative redirect")
    if redirect:
        flask.session["redirect"] = redirect

    # This will be the value that was put in the ``client_kwargs`` in config.
    redirect_uri = flask.current_app.oauth2_client.session.redirect_uri
    # Get the authorization URL and the random state; save the state to check
    # later, and return the URL.
    authorization_url, state = flask.current_app.oauth2_client.generate_authorize_redirect(
        redirect_uri
    )
    flask.session["state"] = state
    return flask.redirect(authorization_url)


@blueprint.route("/authorize", methods=["GET"])
def do_authorize():
    """
    Send a token request to the OP.
    """
    redirect = flask.session.pop("redirect")
    oauth2.client_do_authorize()
    if redirect:
        return flask.redirect(redirect)
    return flask.jsonify({"success": "connected with fence"})


@blueprint.route("/logout", methods=["GET"])
def logout_oauth():
    """
    Log out the user.
    To accomplish this, just revoke the refresh token if provided.
    """
    url = urljoin(flask.current_app.config.get("USER_API"), "/oauth2/revoke")
    token = flask.request.form.get("token")
    try:
        flask.current_app.oauth2_client.session.revoke_token(url, token)
    except APIError as e:
        msg = "could not log out, failed to revoke token: {}".format(e.message)
        return msg, 400
    return "", 204
