from authlib.integrations.requests_client.oauth2_session import OAuth2Session
from authlib.common.urls import add_params_to_uri
from cryptography.fernet import Fernet
import flask
from flask import Flask
import json
from urllib.parse import urlparse
from cdislogging import get_logger
from cdiserrors import APIError

from .blueprints import oauth2, tokens, external_oidc, aggregate
from .models import db, Base, RefreshToken
from .utils import get_config_var as get_var
from .version_data import VERSION, COMMIT


app = Flask(__name__)
app.logger = get_logger(__name__, log_level="info")


def load_settings(app):
    """
    load setttings from environment variables
    SECRET_KEY: app secret key to encrypt session cookies
    ENCRYPTION_KEY: encryption key to encrypt credentials in database
    POSTGRES_CREDS_FILE: JSON file with "db_username", "db_password",
        "db_host" and "db_database" keys
    SQLALCHEMY_DATABASE_URI: database connection uri. Overriden by
        POSTGRES_CREDS_FILE
    FENCE_BASE_URL: fence base url, eg: https://gen3_commons/user
    WTS_BASE_URL: base url for this workspace token service
    OIDC_CLIENT_ID: client id for the oidc client for this app
    OIDC_CLIENT_SECRET: client secret for the oidc client for this app
    AUTH_PLUGINS: a list of comma separate plugins, eg: k8s
    EXTERNAL_OIDC: config for additional oidc handshakes
    """
    app.secret_key = get_var("SECRET_KEY")
    app.encrytion_key = Fernet(get_var("ENCRYPTION_KEY"))
    postgres_creds = get_var("POSTGRES_CREDS_FILE", "")
    if postgres_creds:
        with open(postgres_creds, "r") as f:
            creds = json.load(f)
            app.config[
                "SQLALCHEMY_DATABASE_URI"
            ] = "postgresql://{db_username}:{db_password}@{db_host}:5432/{db_database}".format(
                **creds
            )
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = get_var("SQLALCHEMY_DATABASE_URI")
    url = get_var("FENCE_BASE_URL")
    fence_base_url = url if url.endswith("/") else (url + "/")

    wts_base_url = get_var("WTS_BASE_URL")
    if not wts_base_url.endswith("/"):
        wts_base_url = wts_base_url + "/"
    wts_hostname = urlparse(wts_base_url).netloc.split(".")[0]
    oauth_config = {
        "client_id": get_var("OIDC_CLIENT_ID"),
        "client_secret": get_var("OIDC_CLIENT_SECRET"),
        "api_base_url": fence_base_url,
        "authorize_url": fence_base_url + "oauth2/authorize",
        "access_token_url": fence_base_url + "oauth2/token",
        "redirect_uri": wts_base_url + "oauth2/authorize",
        "scope": "openid data user",
        "state_prefix": "",
    }
    app.config["OIDC"] = {"default": oauth_config}

    for conf in get_var("EXTERNAL_OIDC", []):
        url = get_var("BASE_URL", secret_config=conf)
        fence_base_url = (url if url.endswith("/") else (url + "/")) + "user/"
        # can redirect authorize callbacks to a shared central authorizer
        redirect_uri = get_var("REDIRECT_URI", default="", secret_config=conf)
        state_prefix = wts_hostname or ""
        if not redirect_uri:
            redirect_uri = wts_base_url + "oauth2/authorize"
            state_prefix = ""

        for idp, idp_conf in conf.get("login_options", {}).items():
            authorization_url = fence_base_url + "oauth2/authorize"
            authorization_url = add_params_to_uri(
                authorization_url, idp_conf.get("params", {})
            )
            app.config["OIDC"][idp] = {
                "client_id": get_var("OIDC_CLIENT_ID", secret_config=conf),
                "client_secret": get_var("OIDC_CLIENT_SECRET", secret_config=conf),
                "api_base_url": fence_base_url,
                "authorize_url": authorization_url,
                "access_token_url": fence_base_url + "oauth2/token",
                "redirect_uri": redirect_uri,
                "scope": "openid data user",
                "state_prefix": state_prefix,
            }

    app.config["SESSION_COOKIE_NAME"] = "wts"
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


def _log_and_jsonify_exception(e):
    """
    Log an exception and return the jsonified version along with the code.
    This is the error handling mechanism for ``APIErrors`` and
    ``AuthError``.
    """
    app.logger.exception(e)
    if hasattr(e, "json") and e.json:
        return flask.jsonify(**e.json), e.code
    else:
        return flask.jsonify(message=e.message), e.code


app.register_error_handler(APIError, _log_and_jsonify_exception)


@app.before_first_request
def setup():
    _setup(app)


def _setup(app):
    load_settings(app)
    app.oauth2_clients = {
        idp: OAuth2Session(**conf) for idp, conf in app.config["OIDC"].items()
    }
    app.logger.info("Set up OIDC clients: {}".format(list(app.oauth2_clients.keys())))
    db.init_app(app)
    app.register_blueprint(oauth2.blueprint, url_prefix="/oauth2")
    app.register_blueprint(tokens.blueprint, url_prefix="/token")
    app.register_blueprint(external_oidc.blueprint, url_prefix="/external_oidc")
    app.register_blueprint(aggregate.blueprint, url_prefix="/aggregate")


@app.route("/_status", methods=["GET"])
def health_check():
    """
    Health check endpoint
    """
    try:
        db.session.query(RefreshToken).first()
        return "Healthy", 200
    except Exception as e:
        app.logger.exception("Unable to query DB: {}".format(e))
        return "Unhealthy", 500


@app.route("/_version", methods=["GET"])
def version():
    """
    Return the version of this service.
    """

    base = {"version": VERSION, "commit": COMMIT}

    return flask.jsonify(base), 200


@app.route("/")
def root():
    return flask.jsonify(
        {
            "/token": "get temporary token",
            "/oauth2": "oauth2 resources",
            "/external_oidc": "list available identity providers",
        }
    )
