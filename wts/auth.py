from functools import wraps
import flask
from .auth_plugins import find_user


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(flask.g, 'user'):
            # TODO: plugin auth mechanism
            flask.g.user = find_user()
        return f(*args, **kwargs)
    return decorated_function
