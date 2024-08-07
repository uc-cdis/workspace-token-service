from alembic.config import main as alembic_main
from cryptography.fernet import Fernet
import flask
import httpx
import jwt
import mock
import pytest
import os
from sqlalchemy.exc import SQLAlchemyError
import time
import uuid
import urllib

from authutils.testing.fixtures import (
    rsa_public_key,
    _hazmat_rsa_private_key,
    rsa_private_key,
)

from wts.auth_plugins import find_user
from wts.auth_plugins.base import User
from wts.api import app as service_app
from wts.api import setup_app
from wts.models import RefreshToken, db as _db


def test_settings():
    settings = {
        "SECRET_CONFIG": "tests/test_settings.json",
        "ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
    }
    for k, v in settings.items():
        os.environ[k] = v


@pytest.fixture(scope="session")
def app():
    with service_app.app_context():
        test_settings()
        setup_test_database()
        setup_app(service_app)
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
    return User(userid="test", username="test")


@pytest.fixture(scope="function")
def other_user():
    return User(userid="123456", username="someone_else")


@pytest.fixture(scope="session")
def db(app, request):
    """Session-wide test database."""

    def teardown():
        with app.app_context():
            _db.drop_all()

    with app.app_context():
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
        session.rollback()
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
    default_scopes = ["openid", "access", "user", "test_aud"]
    claims = {
        "pur": "access",
        "aud": "https://localhost/user",
        "sub": test_user.userid,
        "iss": "https://localhost/user",
        "iat": now,
        "exp": now + 600,
        "jti": str(uuid.uuid4()),
        "scope": default_scopes,
        "context": {"user": {"name": test_user.username, "projects": []}},
    }
    token_headers = {"kid": default_kid}
    encoded_jwt = jwt.encode(
        claims, headers=token_headers, key=rsa_private_key, algorithm="RS256"
    )
    return [("Authorization", "Bearer {}".format(encoded_jwt))]


def insert_into_refresh_token_table(db_session, idp, data):
    now = int(time.time())
    token_bytes = bytes(data["refresh_token"], encoding="utf8")
    encrypted_token = flask.current_app.encryption_key.encrypt(token_bytes).decode(
        "utf-8"
    )
    db_session.add(
        RefreshToken(
            idp=idp,
            token=encrypted_token,
            username=data["username"],
            userid=data["userid"],
            expires=data.get("expires", now + 100),
            jti=str(uuid.uuid4()),
        )
    )
    db_session.commit()


@pytest.fixture(scope="function")
def default_refresh_tokens_json(test_user, other_user):
    return {
        "default": [
            {
                "username": test_user.username,
                "userid": test_user.userid,
                "refresh_token": "eyJhbGciOiJ.1",
            },
            {
                "username": other_user.username,
                "userid": other_user.userid,
                "refresh_token": "eyJhbGciOiJ.2",
            },
        ],
    }


@pytest.fixture(scope="function")
def refresh_tokens_json(test_user, other_user):
    now = int(time.time())
    return {
        "default": [
            {
                "username": test_user.username,
                "userid": test_user.userid,
                "refresh_token": "eyJhbGciOiJ.1",
            },
            {
                "username": other_user.username,
                "userid": other_user.userid,
                "refresh_token": "eyJhbGciOiJ.2",
            },
        ],
        "idp_a": [
            {
                "username": test_user.username,
                "userid": test_user.userid,
                "refresh_token": "eyJhbGciOiJ.3",
            },
            {
                "username": other_user.username,
                "userid": other_user.userid,
                "refresh_token": "eyJhbGciOiJ.4",
            },
        ],
        "idp_with_expired_token": [
            {
                "username": test_user.username,
                "userid": test_user.userid,
                "refresh_token": "eyJhbGciOiJ.5",
                "expires": now - 101,  # expired
            }
        ],
    }


def assert_authz_mapping_for_test_user_in_default_commons(authz_mapping):
    assert "/open" in authz_mapping
    assert "/1" in authz_mapping
    assert "/2" not in authz_mapping
    assert "/3" not in authz_mapping
    assert "/4" not in authz_mapping
    assert "/5" not in authz_mapping


def assert_authz_mapping_for_test_user_in_idp_a_commons(authz_mapping):
    assert "/open" in authz_mapping
    assert "/3" in authz_mapping
    assert "/1" not in authz_mapping
    assert "/2" not in authz_mapping
    assert "/4" not in authz_mapping
    assert "/5" not in authz_mapping


def assert_authz_mapping_for_user_without_access_token(authz_mapping):
    assert "/open" in authz_mapping
    assert "/1" not in authz_mapping
    assert "/2" not in authz_mapping
    assert "/3" not in authz_mapping
    assert "/4" not in authz_mapping
    assert "/5" not in authz_mapping


@pytest.fixture(scope="function")
def persisted_refresh_tokens(refresh_tokens_json, db_session):
    for idp, refresh_tokens in refresh_tokens_json.items():
        for refresh_token in refresh_tokens:
            insert_into_refresh_token_table(db_session, idp, refresh_token)
    return refresh_tokens_json


@pytest.fixture(scope="function")
def default_refresh_tokens(default_refresh_tokens_json, db_session):
    for idp, refresh_tokens in default_refresh_tokens_json.items():
        for refresh_token in refresh_tokens:
            insert_into_refresh_token_table(db_session, idp, refresh_token)
    return default_refresh_tokens_json


@pytest.fixture(scope="function")
def mock_requests(
    app, respx_mock, refresh_tokens_json, request, client, default_kid, rsa_public_key
):
    """
    Mock GET requests for:
    - obtaining JWT keys from Fence
    - Fence's user info endpoint
    Mock POST requests for:
    - getting an access token from Fence (and others) using a refresh token
    """
    access_token_to_authz_resource = {}
    for refresh_tokens in refresh_tokens_json.values():
        for refresh_token in refresh_tokens:
            content = refresh_token["refresh_token"].split(".")[1]
            # example: { "access_token_for_eyJhbGciOiJ.1": "/1", ... }
            access_token_to_authz_resource[
                f"access_token_for_{refresh_token['refresh_token']}"
            ] = f"/{content}"

    def do_patch():
        def post_fence_token_side_effect(request):
            request_data = urllib.parse.parse_qs(request.content.decode())
            assert "refresh_token" in request_data
            refresh_token = request_data["refresh_token"][0]
            return httpx.Response(
                200, json={"access_token": f"access_token_for_{refresh_token}"}
            )

        def get_fence_user_side_effect(request):
            access_token = request.headers.get("Authorization", "").split(" ")
            access_token = access_token[1] if len(access_token) > 0 else ""
            if access_token not in access_token_to_authz_resource:
                print(
                    "Mocked request '/user/user': no access token was provided. Assuming anonymous; returning empty access."
                )
                data = {
                    "authz": {},
                    "is_admin": False,
                    "role": "user",
                }
            else:
                data = {
                    "authz": {
                        access_token_to_authz_resource[access_token]: [
                            {"method": "read", "service": "*"}
                        ],
                        "/open": [{"method": "read", "service": "*"}],
                    },
                    "is_admin": True,
                    "role": "admin",
                }
            return httpx.Response(200, json=data)

        def get_arborist_authz_side_effect(request):
            access_token = (
                request.headers["Authorization"].split(" ")[1]
                if "Authorization" in request.headers
                else None
            )
            response_data = {"/open": [{"method": "read", "service": "*"}]}
            if access_token in access_token_to_authz_resource:
                response_data[access_token_to_authz_resource[access_token]] = [
                    {"method": "read", "service": "*"}
                ]
            return httpx.Response(200, json=response_data)

        def create_mocks_for_user(app, respx_mock):
            for idp_config in app.config["OIDC"].values():
                fence_url = idp_config["api_base_url"].rstrip("/")

                # mock getting tokens
                respx_mock.post(f"{fence_url}/oauth2/token").mock(
                    side_effect=post_fence_token_side_effect
                )
                respx_mock.post(
                    "https://external.data.repository/auth/realms/xyz/protocol/openid-connect/token"
                ).mock(side_effect=post_fence_token_side_effect)

                # mock userinfo endpoint
                respx_mock.get(f"{fence_url}/user").mock(
                    side_effect=get_fence_user_side_effect
                )
                respx_mock.get("https://external.data.repository/user/user").mock(
                    side_effect=get_fence_user_side_effect
                )

                commons_base_url = f'https://{idp_config["commons_hostname"]}'
                authz_mapping_url = f"{commons_base_url}/authz/mapping"
                respx_mock.get(authz_mapping_url).mock(
                    side_effect=get_arborist_authz_side_effect
                )

        create_mocks_for_user(app, respx_mock)

        default_fence_url = app.config["OIDC"]["default"]["api_base_url"].rstrip("/")
        respx_mock.get(f"{default_fence_url}/jwt/keys").mock(
            return_value=httpx.Response(
                200, json={"keys": [[default_kid, rsa_public_key]]}
            )
        )

    return do_patch


@pytest.fixture(autouse=True)
def mock_all_requests(mock_requests):
    mock_requests()
