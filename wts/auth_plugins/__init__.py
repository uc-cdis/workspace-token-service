from .base import DefaultPlugin
from .k8s import K8SPlugin
import flask


def find_user():
    auth_header = flask.request.headers.get("Authorization")
    print("auth_header: " + str(auth_header))

    if auth_header:
        return DefaultPlugin().find_user()
    return K8SPlugin().find_user()
