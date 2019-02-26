import pytest

from wts.api import app as service_app, app_init


@pytest.fixture(scope="session")
def app():
    # load configuration
    # service_app.config.from_object('wts.test_settings')
    app_init(service_app)
    return service_app
