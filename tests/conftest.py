from alembic.config import main as alembic_main
from cryptography.fernet import Fernet
import jwt
import mock
import pytest
import requests
import os
from sqlalchemy.exc import SQLAlchemyError
import time
import uuid

from authutils.testing.fixtures import (
    rsa_public_key,
    _hazmat_rsa_private_key,
    rsa_private_key,
)

from wts.auth_plugins import find_user
from wts.api import app as service_app
from wts.api import _setup
from wts.models import db as _db


def test_settings():

    settings = {
        "SECRET_CONFIG": "tests/test_settings.json",
        "ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
    }
    for k, v in settings.items():
        os.environ[k] = v


@pytest.fixture(scope="session")
def app():
    test_settings()
    setup_test_database()
    with service_app.app_context():
        _setup(service_app)
    return service_app


def setup_test_database():
    """
    Update the test DB to the latest version. The migration code is able to
    handle both updating an existing, pre-migration code DB (local tests)
    and creating a new DB (automated tests)
    """
    alembic_main(["--raiseerr", "upgrade", "head"])


@pytest.fixture(scope="function")
def test_user():
    return find_user()


@pytest.fixture(scope="session")
def db(app, request):
    """Session-wide test database."""

    def teardown():
        _db.drop_all()

    _db.app = app
    _db.create_all()

    request.addfinalizer(teardown)
    return _db


@pytest.fixture(scope="function")
def db_session(db, request):
    """Creates a new database session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()
    options = dict(bind=connection, binds={})
    session = db.create_scoped_session(options=options)
    db.session = session

    def teardown():
        transaction.rollback()
        connection.close()
        session.remove()

    request.addfinalizer(teardown)
    return session


@pytest.fixture(scope="session")
def default_kid():
    return "key-01"


@pytest.fixture(scope="function")
def auth_header(test_user, rsa_private_key, default_kid):
    """
    Return an authorization header containing the example JWT.

    Args:
        encoded_jwt (str): fixture

    Return:
        List[Tuple[str, str]]: the authorization header
    """
    now = int(time.time())
    default_audiences = ["openid", "access", "user", "test_aud"]
    claims = {
        "pur": "access",
        "aud": default_audiences,
        "sub": test_user.userid,
        "iss": "localhost",
        "iat": now,
        "exp": now + 600,
        "jti": str(uuid.uuid4()),
        "context": {"user": {"name": test_user.username, "projects": []}},
    }
    token_headers = {"kid": default_kid}
    encoded_jwt = jwt.encode(
        claims, headers=token_headers, key=rsa_private_key, algorithm="RS256"
    )
    encoded_jwt = encoded_jwt.decode("utf-8")
    return [("Authorization", "Bearer {}".format(encoded_jwt))]


@pytest.fixture(scope="function")
def mock_requests(request, client, default_kid, rsa_public_key):
    """
    Mock GET requests for:
    - obtaining JWT keys from Fence
    Mock POST requests for:
    - getting an access token from Fence using a refresh token
    """

    def do_patch():
        def make_mock_get_response(*args, **kwargs):
            mocked_response = mock.MagicMock(requests.Response)
            request_url = args[0]
            if request_url.endswith("/jwt/keys"):
                mocked_response.status_code = 200
                mocked_response.json = lambda: {"keys": [[default_kid, rsa_public_key]]}
                return mocked_response
            else:
                client.get(request_url, args=args, kwargs=kwargs)

        def make_mock_post_response(*args, **kwargs):
            mocked_response = mock.MagicMock(requests.Response)
            request_url = args[0]
            request_params = kwargs["data"]

            if request_url.endswith("/oauth2/token"):
                mocked_response.status_code = 200
                assert "refresh_token" in request_params
                mocked_response.json = lambda: {
                    "access_token": "access_token_for_"
                    + request_params["refresh_token"]
                }
                return mocked_response
            else:
                client.post(request_url, args=args, kwargs=kwargs)

        mocked_get_request = mock.MagicMock(side_effect=make_mock_get_response)
        patched_get_request = mock.patch("requests.get", mocked_get_request)
        patched_get_request.start()
        request.addfinalizer(patched_get_request.stop)

        mocked_post_request = mock.MagicMock(side_effect=make_mock_post_response)
        patched_post_request = mock.patch("requests.post", mocked_post_request)
        patched_post_request.start()
        request.addfinalizer(patched_post_request.stop)

    return do_patch


@pytest.fixture(autouse=True)
def mock_all_requests(mock_requests):
    mock_requests()
