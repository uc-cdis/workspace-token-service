from flask import Blueprint, request


blueprint = Blueprint("something", __name__)


@blueprint.route("", methods=["GET"])
def get_something():
    """
    Get something
    ---
    responses:
        200:
            description: Success
    """
    return "I got something", 200


@blueprint.route("", methods=["PUT"])
def put_something():
    """
    Put something
    ---
    responses:
        200:
            description: Success
    """
    return "I put something", 200


@blueprint.route("/put-get", methods=["GET", "PUT"])
def get_put_something():
    """
    Several methods for the same function

    GET and PUT have the same documentation:
    ---
    responses:
        200:
            description: Success
    """
    if request.method == "GET":
        return "I got something, did not put", 200
    else:
        return "I put something, did not get", 200


@blueprint.route("/bar", methods=["GET"])
def do_something_bar():
    """
    bar!
    ---
    responses:
        200:
            description: Success
    """
    return do_something()


@blueprint.route("/foo/<param>", methods=["GET"])
def do_something_foo(param):
    """
    foo!
    ---
    parameters:
      - in: path
        name: param
        type: string
        required: true
    responses:
        200:
            description: Success
    """
    return do_something(param)


def do_something(param=None):
    """
    Several routes for the same function

    FOO and BAR have different documentation
    ---
    """
    return "I did something with {}".format(request.url_rule), 200
