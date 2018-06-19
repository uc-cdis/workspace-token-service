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
from .models import db, Base

app = Flask(__name__)
app.logger = get_logger(__name__)


def from_env_var(variable):
    '''
    get a environment variable, raise exception if it doesn't exist
    '''
    value = os.environ.get(variable)
    if not value:
        raise Exception(
            '{} is missing from environment variable, abort initialization'
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
    """
    app.secret_key = from_env_var('SECRET_KEY')
    app.encrytion_key = Fernet(from_env_var('ENCRYPTION_KEY'))
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        from_env_var('SQLALCHEMY_DATABASE_URI')
    )
    fence_base_url = from_env_var('FENCE_BASE_URL')
    wts_base_url = from_env_var('WTS_BASE_URL')
    oauth_config = {
        "client_id": from_env_var('OIDC_CLIENT_ID'),
        "client_secret": from_env_var('OIDC_CLIENT_SECRET'),
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
    print(app.config)


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


@app.route('/')
def root():
    return flask.jsonify({
        '/token': 'get temporary token',
        '/oauth2': 'oauth2 resources'
    })



