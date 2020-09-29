import flask
import json
import os

from cdiserrors import UserError


def get_config_var(variable, default=None, secret_config={}):
    """
    get a secret from env var or mounted secret dir,
    raise exception if it doesn't exist
    """
    path = os.environ.get("SECRET_CONFIG")
    if not secret_config and path:
        with open(path, "r") as f:
            secret_config.update(json.load(f))
    value = secret_config.get(variable.lower(), os.environ.get(variable)) or default
    if value is None:
        raise Exception(
            "{} configuration is missing, abort initialization".format(variable)
        )
    return value


def get_oauth_client(idp=None):
    """
    Args:
        idp (str, optional): IDP for the OAuthClient to return. Usually
            the IDP argument of the current flask request. If not provided,
            will return the default OAuth2Session.

    Returns:
        (OAuth2Session, str) tuple
    """
    idp = idp or "default"
    try:
        client = flask.current_app.oauth2_clients[idp]
    except KeyError:
        flask.current_app.logger.exception(
            'Requested IDP "{}" is not configured'.format(idp)
        )
        raise UserError('Requested IDP "{}" is not configured'.format(idp))
    return client
