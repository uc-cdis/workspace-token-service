import flask


from ..auth import login_required
from ..tokens import get_access_token


blueprint = flask.Blueprint('token', __name__)

blueprint.route('')


@blueprint.route('/')
@login_required
def get_token():
    expires = flask.request.args.get('expires')
    if expires:
        try:
            expires = int(expires)
        except ValueError:
            return flask.jsonify({
                'error': 'expires has to be an integer'}), 400
    return flask.jsonify({'token': get_access_token(expires=expires)})
