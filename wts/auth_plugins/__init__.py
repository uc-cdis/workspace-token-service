from .base import AccessTokenPlugin
from .k8s import K8SPlugin
import flask


def find_user(allow_access_token=False):
    if allow_access_token and flask.request.headers.get("Authorization"):
        return AccessTokenPlugin().find_user()
    return K8SPlugin().find_user()
