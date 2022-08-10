import flask
import json
import mock
import os
import time
import uuid
import urllib

from wts.models import RefreshToken
from wts.resources.oauth2 import find_valid_refresh_token


def test_find_valid_refresh_token(persisted_refresh_tokens):

    # valid refresh token
    idp = "idp_a"
    username = persisted_refresh_tokens[idp][0]["username"]
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


def test_connected_endpoint_without_persisted_refresh_tokens(
    client, db_session, auth_header
):
    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 403


def test_connected_endpoint_with_persisted_refresh_tokens(
    client, auth_header, persisted_refresh_tokens
):
    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 200


def test_token_endpoint_with_default_idp(client, persisted_refresh_tokens, auth_header):
    res = client.get("/token/?idp=default", headers=auth_header)
    assert res.status_code == 403


def test_token_endpoint_with_idp_a(client, persisted_refresh_tokens, auth_header):
    # the token returned for a specific IDP should be created using the
    # corresponding refresh_token, using the logged in user's username
    res = client.get("/token/?idp=idp_a", headers=auth_header)
    assert res.status_code == 200

    original_refresh_token = persisted_refresh_tokens["idp_a"][0]["refresh_token"]
    assert res.json["token"] == f"access_token_for_{original_refresh_token}"


def test_token_endpoint_without_specifying_idp(
    client, persisted_refresh_tokens, auth_header
):
    res = client.get("/token/", headers=auth_header)
    assert res.status_code == 403


def test_token_endpoint_with_bogus_idp(client, persisted_refresh_tokens, auth_header):
    res = client.get("/token/?idp=bogus", headers=auth_header)
    assert res.status_code == 400


def test_token_endpoint_without_auth_header(client, persisted_refresh_tokens):
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

        original_refresh_token = str(
            flask.current_app.encryption_key.decrypt(bytes(t.token, encoding="utf8")),
            encoding="utf8",
        )
        if t.idp == "default":
            assert original_refresh_token == fake_tokens["default"]
        else:
            assert original_refresh_token == fake_tokens["idp_a"]


def test_authorization_url_endpoint(client):
    res = client.get("/oauth2/authorization_url?idp=idp_a")
    assert res.status_code == 302
    assert res.location.startswith("https://some.data.commons/user/oauth2/authorize")


def test_external_oidc_endpoint_without_persisted_refresh_tokens(
    client, db_session, auth_header
):
    with open(os.environ["SECRET_CONFIG"], "r") as f:
        configured_oidc = json.load(f)["external_oidc"]
    expected_oidc = {}
    for provider in configured_oidc:
        for idp, login_option in provider.get("login_options", {}).items():
            expected_oidc[idp] = login_option
            expected_oidc[idp]["base_url"] = provider["base_url"]
            expected_oidc[idp]["oidc_client_id"] = provider["oidc_client_id"]

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


def test_external_oidc_endpoint_with_persisted_refresh_tokens(
    client, persisted_refresh_tokens, auth_header
):
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
