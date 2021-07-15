import flask

from authutils.user import current_user

from wts.utils import get_oauth_client


class User(object):
    def __init__(self, userid, username=None):
        self.userid = userid
        self.username = username


class AccessTokenPlugin(object):
    def __init__(self):
        pass

    def find_user(self):
        """
        find user identified in current request
        returns None if no user can be identified
        """
        # `current_user` validates the token and relies on `OIDC_ISSUER`
        # to know the issuer
        default_oauth_client = get_oauth_client(idp="default")
        flask.current_app.config["OIDC_ISSUER"] = default_oauth_client.metadata[
            "api_base_url"
        ].rstrip("/")

        user = current_user
        return User(userid=user.id, username=user.username)
