from .base import DefaultPlugin
from .k8s import K8SPlugin
import flask


def find_user():
    if flask.request.headers.get("Authorization"):
        return DefaultPlugin().find_user()
    return K8SPlugin().find_user()
