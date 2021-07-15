import json
import mock
import os
import time
import uuid

from wts.models import RefreshToken
from wts.resources.oauth2 import find_valid_refresh_token


def insert_into_refresh_token_table(db_session, idp, data):
    now = int(time.time())
    db_session.add(
        RefreshToken(
            idp=idp,
            token=data["refresh_token"],
            username=data["username"],
            userid=data["userid"],
            expires=data.get("expires", now + 100),
            jti=str(uuid.uuid4()),
        )
    )
    db_session.commit()


def create_logged_in_user_data(test_user, db_session):
    now = int(time.time())
    logged_in_user_data = {
        "default": {
            "username": test_user.username,
            "userid": test_user.userid,
            "refresh_token": "eyJhbGciOiJaaaa",
        },
        "idp_a": {
            "username": test_user.username,
            "userid": test_user.userid,
            "refresh_token": "eyJhbGciOiJbbbb",
        },
        "idp_with_expired_token": {
            "username": test_user.username,
            "userid": test_user.userid,
            "refresh_token": "eyJhbGciOiJcccc",
            "expires": now - 100,  # expired
        },
    }
    for idp, data in logged_in_user_data.items():
        insert_into_refresh_token_table(db_session, idp, data)
    return logged_in_user_data


def create_other_user_data(db_session):
    other_user_data = {
        "default": {
            "username": "someone_else",
            "userid": "123456",
            "refresh_token": "eyJhbGciOiJzzzz",
        },
        "idp_a": {
            "username": "someone_else",
            "userid": "123456",
            "refresh_token": "eyJhbGciOiJyyyy",
        },
    }
    for idp, data in other_user_data.items():
        insert_into_refresh_token_table(db_session, idp, data)
    return other_user_data


def test_find_valid_refresh_token(test_user, db_session):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)

    # valid refresh token
    idp = "idp_a"
    username = logged_in_user_data[idp]["username"]
    assert find_valid_refresh_token(username, idp)

    # expired refresh token
    idp = "idp_with_expired_token"
    assert not find_valid_refresh_token(username, idp)

    # no existing refresh token for this idp
    idp = "non_configured_idp"
    assert not find_valid_refresh_token(username, idp)

    # no existing refresh token for this user
    idp = "idp_a"
    username = "unknown_user"
    assert not find_valid_refresh_token(username, idp)


def test_connected_endpoint(client, test_user, db_session, auth_header):
    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 403

    create_logged_in_user_data(test_user, db_session)

    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 200


def test_token_endpoint_with_default_idp(client, test_user, db_session, auth_header):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)
    create_other_user_data(db_session)

    res = client.get("/token/?idp=default", headers=auth_header)
    assert res.status_code == 403


def test_token_endpoint_with_idp_a(client, test_user, db_session, auth_header):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)
    create_other_user_data(db_session)

    # the token returned for a specific IDP should be created using the
    # corresponding refresh_token, using the logged in user's username
    res = client.get("/token/?idp=idp_a", headers=auth_header)
    assert res.status_code == 200
    assert (
        res.json["token"]
        == "access_token_for_" + logged_in_user_data["idp_a"]["refresh_token"]
    )


def test_token_endpoint_without_specifying_idp(
    client, test_user, db_session, auth_header
):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)
    create_other_user_data(db_session)

    res = client.get("/token/", headers=auth_header)
    assert res.status_code == 403


def test_token_endpoint_with_bogus_idp(client, test_user, db_session, auth_header):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)
    create_other_user_data(db_session)

    # make sure the IDP we use is "default" when no IDP is requested
    res = client.get("/token/?idp=bogus", headers=auth_header)
    assert res.status_code == 400


def test_token_endpoint_without_auth_header(client, test_user, db_session):
    logged_in_user_data = create_logged_in_user_data(test_user, db_session)
    create_other_user_data(db_session)

    res = client.get("/token/")
    assert res.status_code == 403


def test_authorize_endpoint(client, test_user, db_session, auth_header):
    fake_tokens = {"default": "eyJhbGciOiJtttt", "idp_a": "eyJhbGciOiJuuuu"}

    # mock `fetch_access_token` to avoid external calls
    mocked_response = mock.MagicMock()
    mocked_response.side_effect = [
        # returned object for IDP "default":
        {"refresh_token": fake_tokens["default"], "id_token": "eyJhbGciOiJ"},
        # returned object for IDP "idp_a":
        {"refresh_token": fake_tokens["idp_a"], "id_token": "eyJhbGciOiJ"},
    ]
    patched_fetch_access_token = mock.patch(
        "authlib.oauth2.client.OAuth2Client.fetch_token", mocked_response
    )
    patched_fetch_access_token.start()

    # mock `jwt.decode` to return fake data
    now = int(time.time())
    mocked_jwt_response = mock.MagicMock()
    mocked_jwt_response.side_effect = [
        # decoded id_token for IDP "default":
        {"context": {"user": {"name": test_user.username}}},
        # decoded refresh_token for IDP "default":
        {"jti": str(uuid.uuid4()), "exp": now + 100, "sub": test_user.userid},
        # decoded id_token for IDP "idp_a":
        {"context": {"user": {"name": test_user.username}}},
        # decoded refresh_token for IDP "idp_a":
        {"jti": str(uuid.uuid4()), "exp": now + 100, "sub": test_user.userid},
    ]
    patched_jwt_decode = mock.patch("jose.jwt.decode", mocked_jwt_response)
    patched_jwt_decode.start()

    # get refresh token for IDP "default"
    fake_state = "qwerty"
    with client.session_transaction() as session:
        session["state"] = fake_state
    res = client.get(
        "/oauth2/authorize?state={}".format(fake_state), headers=auth_header
    )
    assert res.status_code == 200, res.json

    # get refresh token for IDP "idp_a"
    with client.session_transaction() as session:
        session["state"] = fake_state
        session["idp"] = "idp_a"
    res = client.get(
        "/oauth2/authorize?state={}".format(fake_state), headers=auth_header
    )
    assert res.status_code == 200

    # make sure the refresh tokens are in the DB
    refresh_tokens = db_session.query(RefreshToken).all()
    for t in refresh_tokens:
        assert t.username == test_user.username
        if t.idp == "default":
            assert t.token == fake_tokens["default"]
        else:
            assert t.token == fake_tokens["idp_a"]


def test_authorization_url_endpoint(client):
    res = client.get("/oauth2/authorization_url?idp=idp_a")
    assert res.status_code == 302
    assert res.location.startswith("https://some.data.commons/user/oauth2/authorize")


def test_external_oidc_endpoint(client, test_user, db_session, auth_header):
    with open(os.environ["SECRET_CONFIG"], "r") as f:
        configured_oidc = json.load(f)["external_oidc"]
    expected_oidc = {}
    for provider in configured_oidc:
        for idp, login_option in provider.get("login_options", {}).items():
            expected_oidc[idp] = login_option
            expected_oidc[idp]["base_url"] = provider["base_url"]
            expected_oidc[idp]["oidc_client_id"] = provider["oidc_client_id"]

    # GET /external_oidc before logging in
    res = client.get("/external_oidc/", headers=auth_header)
    assert res.status_code == 200
    actual_oidc = res.json["providers"]

    # the listed providers should be the configured providers
    print("Configured providers: {}".format(expected_oidc))
    print("Returned providers: {}".format(actual_oidc))
    for provider in actual_oidc:
        assert provider["idp"] in expected_oidc
        data = expected_oidc[provider["idp"]]
        assert provider["base_url"] == data["base_url"]
        assert provider["name"] == data["name"]
        assert provider["urls"][0]["url"].endswith(
            "/oauth2/authorization_url?idp={}".format(provider["idp"])
        )
        assert provider["refresh_token_expiration"] == None

    create_logged_in_user_data(test_user, db_session)

    # GET /external_oidc after logging in
    res = client.get("/external_oidc/", headers=auth_header)
    assert res.status_code == 200
    actual_oidc = res.json["providers"]
    print("Returned providers after logging in: {}".format(actual_oidc))

    for provider in actual_oidc:
        if provider["idp"] == "idp_a":  # test user is logged into this IDP
            assert provider["refresh_token_expiration"] != None
        else:
            assert provider["refresh_token_expiration"] == None


def test_app_config(app):
    assert (
        app.config["OIDC"]["idp_a"]["redirect_uri"]
        == "https://workspace.planx-pla.net/wts-callback"
    )
    assert app.config["OIDC"]["idp_a"]["state_prefix"] == "test"
    assert (
        app.config["OIDC"]["default"]["redirect_uri"]
        == "https://test.workspace.planx-pla.net/wts/oauth2/authorize"
    )
    assert app.config["OIDC"]["default"]["state_prefix"] == ""
    client = app.oauth2_clients["idp_a"]
    assert client.redirect_uri == "https://workspace.planx-pla.net/wts-callback"
    assert client.metadata["state_prefix"] == "test"
    assert (
        client.metadata["authorize_url"]
        == "https://some.data.commons/user/oauth2/authorize?idp=google"
    )
    assert client.metadata["api_base_url"] == "https://some.data.commons/user/"
