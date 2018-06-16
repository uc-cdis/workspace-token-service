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


def load_settings(app):
    setting_path = os.environ.get('GEN3_WTS')
    if setting_path and os.path.exists(setting_path):
        app.logger.info('Loading settings from {}'.format(setting_path))
        with open(setting_path, 'r') as f:
            app.config.update(json.load(f))
        app.secret_key = app.config.get('SECRET_KEY')
        if 'ENCRYPTION_KEY' in app.config:
            app.encryption_key = Fernet(app.config['ENCRYPTION_KEY'])


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
    if 'OAUTH2' in app.config:
        app.oauth2_client = OAuthClient(**app.config['OAUTH2'])
    setup_plugins(app)
    db.init_app(app)
    Base.metadata.create_all(bind=db.engine)
    app.register_blueprint(oauth2.blueprint, url_prefix='/oauth2')
    app.register_blueprint(tokens.blueprint, url_prefix='/token')

    # print(app.__dict__)
    print(app.oauth2_client.session.redirect_uri)
    print('setup')


@app.route('/')
def root():
    return flask.jsonify({
        '/token': 'get temporary token',
        '/oauth2': 'oauth2 resources'
    })



