from .base import DefaultPlugin
import flask


def setup_plugins(app):
    app.auth_plugins = []
    plugins = set(app.config.get('AUTH_PLUGINS', ['default']))
    for plugin in plugins:
        if plugin == 'default':
            app.auth_plugins.append(DefaultPlugin())


def find_user():
    for plugin in flask.current_app.auth_plugins:
        user = plugin.find_user()
        if user:
            return user
