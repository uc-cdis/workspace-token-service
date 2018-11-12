from .base import DefaultPlugin
from .k8s import K8SPlugin
import flask


def setup_plugins(app):
    app.auth_plugins = []
    for plugin in app.config['AUTH_PLUGINS']:
        if plugin == 'default':
            app.auth_plugins.append(DefaultPlugin())
        elif plugin == 'k8s':
            app.auth_plugins.append(K8SPlugin())


def find_user():
    for plugin in flask.current_app.auth_plugins:
        user = plugin.find_user()
        if user:
            return user
