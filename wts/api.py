import flask
import logging
import time

from . import auth
from .errors import AuthZError, JWTError
from .admin_endpoints import blueprint as admin_bp
from .some_endpoints import blueprint as some_bp


app = flask.Flask(__name__)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(some_bp, url_prefix="/something")


@app.route("/user_endpoint", methods=["GET"])
def do_something_connected():
    """
    User endpoint
    ---
    responses:
        200:
            description: Success
        401:
            description: Unauthorized
    """
    token = flask.request.headers.get("Authorization")
    try:
        user = auth.current_user  # raises error if user is not connected
        return "Success! User is {}".format(user.username), 200
    except JWTError as e:
        return e.message, e.code


@app.route("/_status", methods=["GET"])
def health_check():
    """
    Health check endpoint
    ---
    tags:
      - system
    responses:
        200:
            description: Healthy
        default:
            description: Unhealthy
    """
    return "Healthy", 200


def app_init(app):
    app.logger.info("Initializing app")
    start = time.time()

    # do the necessary here!

    end = int(round(time.time() - start))
    app.logger.info("Initialization complete in {} sec".format(end))


def run_for_development(**kwargs):
    app.logger.setLevel(logging.INFO)

    # import os
    # for key in ["http_proxy", "https_proxy"]:
    #     if os.environ.get(key):
    #         del os.environ[key]

    # load configuration
    app.config.from_object("wts.dev_settings")

    try:
        app_init(app)
    except:
        app.logger.exception("Couldn't initialize application, continuing anyway")
    app.run(**kwargs)
