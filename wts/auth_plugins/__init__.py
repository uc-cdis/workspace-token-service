from .base import DefaultPlugin
from .k8s import K8SPlugin
import flask


def find_user():
    if flask.request.headers.get("Authorization"):
        user = DefaultPlugin().find_user()
        if user:
            return user
    return K8SPlugin().find_user()
