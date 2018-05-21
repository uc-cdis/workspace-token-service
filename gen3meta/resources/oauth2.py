from authlib.client.errors import OAuthException
from authlib.specs.rfc6749.errors import OAuth2Error
from cdiserrors import AuthError
from ..models import RefreshToken, db
import flask
from jose import jwt


def client_do_authorize():
    redirect_uri = flask.current_app.oauth2_client.session.redirect_uri
    mismatched_state = (
        'state' not in flask.request.args
        or 'state' not in flask.session
        or flask.request.args['state'] != flask.session.pop('state')
    )
    if mismatched_state:
        raise AuthError(
            'could not authorize; state did not match across auth requests'
        )
    try:
        token = flask.current_app.oauth2_client.fetch_access_token(
            redirect_uri, **flask.request.args.to_dict()
        )
        return refresh_refresh_token(token['refresh_token'])
    except KeyError as e:
        raise AuthError('error in token response: {}'.format(token))
    except (OAuth2Error, OAuthException) as e:
        raise AuthError(str(e))


def refresh_refresh_token(token):
    options = {
        'verify_signature': False,
        'verify_aud': False,
        'verify_iat': False,
        'verify_exp': False,
        'verify_nbf': False,
        'verify_iss': False,
        'verify_sub': False,
        'verify_jti': False,
        'verify_at_hash': False,
        'leeway': 0
    }
    content = jwt.decode(token, key=None, options=options)
    for old_token in db.session.query(RefreshToken).filter_by(userid=flask.g.user.userid):
        db.session.delete(old_token)
    # TODO: encrypt
    new_token = RefreshToken(
        token=token, userid=flask.g.user.userid,
        username=flask.g.user.username,
        jti=content['jti'], expires=content['exp'])
    db.session.add(new_token)
    db.session.commit()
    return token
