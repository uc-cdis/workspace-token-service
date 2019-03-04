# app.py

import json
import os

from authlib.client import OAuthClient
import flask
from flask import Flask
from cryptography.fernet import Fernet

from cdislogging import get_logger
from cdiserrors import APIError

from .auth_plugins import setup_plugins
from .blueprints import oauth2, tokens
from .models import db, Base, RefreshToken

app = Flask(__name__)
app.logger = get_logger(__name__)


def get_var(variable, default=None):
    '''
    get a secret from env var or mounted secret dir,
    raise exception if it doesn't exist
    '''
    secret_dir = os.environ.get('SECRET_DIR')
    value = os.environ.get(variable, default)
    if secret_dir:
        secret_file = os.path.join(secret_dir, variable)
        if os.path.isfile(secret_file):
            with open(secret_file, 'r') as f:
                value = f.read()
    if not value:
        raise Exception(
            '{} configuration is missing, abort initialization'
            .format(variable)
        )
    return value


def load_settings(app):
    """
    load setttings from environment variables
    SECRET_KEY: app secret key to encrypt session cookies
    ENCRYPTION_KEY: encryption key to encrypt credentials in database
    SQLALCHEMY_DATABASE_URI: database connection uri
    FENCE_BASE_URL: fence base url, eg: https://gen3_commons/user
    WTS_BASE_URL: base url for this workspace token service
    OIDC_CLIENT_ID: client id for the oidc client for this app
    OIDC_CLIENT_SECRET: client secret for the oidc client for this app
    AUTH_PLUGINS: a list of comma separate plugins, eg: k8s
    """
    app.secret_key = get_var('SECRET_KEY')
    app.encrytion_key = Fernet(get_var('ENCRYPTION_KEY'))
    if os.environ.get("DB_CREDS_FILE"):
        with open(os.environ["POSTGRES_CREDS_FILE"], "r") as f:
            creds = json.load(f)
            app.config["SQLALCHEMY_DATABASE_URI"] = (
                "postgresql://{db_username}:{db_password}@{db_host}:5432/{db_database}"
                .format(**creds)
            )
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            get_var('SQLALCHEMY_DATABASE_URI')
        )
    fence_base_url = get_var('FENCE_BASE_URL')

    plugins = get_var('AUTH_PLUGINS', 'default')
    plugins = set(plugins.split(','))
    app.config['AUTH_PLUGINS'] = plugins

    wts_base_url = get_var('WTS_BASE_URL')
    oauth_config = {
        "client_id": get_var('OIDC_CLIENT_ID'),
        "client_secret": get_var('OIDC_CLIENT_SECRET'),
        "api_base_url": fence_base_url,
        "authorize_url": fence_base_url + 'oauth2/authorize',
        "access_token_url": fence_base_url + 'oauth2/token',
        "refresh_token_url": fence_base_url + 'oauth2/token',
        "client_kwargs": {
            "redirect_uri": wts_base_url + 'oauth2/authorize',
            "scope": "openid data user"
        }
    }
    app.config['OIDC'] = oauth_config
    app.config['SESSION_COOKIE_NAME'] = 'wts'
    app.config['SESSION_COOKIE_SECURE'] = True


def _log_and_jsonify_exception(e):
    """
    Log an exception and return the jsonified version along with the code.
    This is the error handling mechanism for ``APIErrors`` and
    ``AuthError``.
    """
    app.logger.exception(e)
    if hasattr(e, 'json') and e.json:
        return flask.jsonify(**e.json), e.code
    else:
        return flask.jsonify(message=e.message), e.code


app.register_error_handler(APIError, _log_and_jsonify_exception)


@app.before_first_request
def setup():
    load_settings(app)
    app.oauth2_client = OAuthClient(**app.config['OIDC'])
    setup_plugins(app)
    db.init_app(app)
    Base.metadata.create_all(bind=db.engine)
    app.register_blueprint(oauth2.blueprint, url_prefix='/oauth2')
    app.register_blueprint(tokens.blueprint, url_prefix='/token')


@app.route("/_status", methods=["GET"])
def health_check():
    """
    Health check endpoint
    ---
    tags:
      - system
    responses:
        200:
            description: Healthy
        default:
            description: Unhealthy
    """
    try:
        db.session.query(RefreshToken).first()
        return "Healthy", 200
    except:
        return "Unhealthy", 500


@app.route('/')
def root():
    return flask.jsonify({
        '/token': 'get temporary token',
        '/oauth2': 'oauth2 resources'
    })



