import flask

from .auth_plugins import find_user
from cdiserrors import AuthError


def authenticate(allow_access_token=False):
    flask.g.user = find_user(allow_access_token)
    if not flask.g.user:
        raise AuthError("You need to be authenticated to use this resource")
