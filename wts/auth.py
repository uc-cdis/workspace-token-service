from functools import wraps
import flask
from .auth_plugins import find_user
from cdiserrors import AuthError


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(flask.g, "user"):
            flask.g.user = find_user()
            if not flask.g.user:
                raise AuthError("You need to be authenticated to use this resource")
        return f(*args, **kwargs)

    return decorated_function


def async_login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if not hasattr(flask.g, "user"):
            flask.g.user = find_user()
            if not flask.g.user:
                raise AuthError("You need to be authenticated to use this resource")
        return await f(*args, **kwargs)

    return decorated_function
