from functools import wraps
import flask


class User(object):
    def __init__(self, userid, username=None):
        self.userid = userid
        self.username = username


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(flask.g, 'user'):
            # TODO: plugin auth mechanism
            flask.g.user = User(userid='test', username='test')
        return f(*args, **kwargs)
    return decorated_function
