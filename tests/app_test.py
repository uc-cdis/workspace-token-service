import json
import mock
import os
import time
import uuid
import httpx
import respx
import urllib

from wts.models import RefreshToken
from wts.resources.oauth2 import find_valid_refresh_token


def test_find_valid_refresh_token(logged_in_users):

    # valid refresh token
    idp = "idp_a"
    username = logged_in_users[idp][0]["username"]
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


def test_connected_endpoint_without_logged_in_users(client, db_session, auth_header):
    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 403


def test_connected_endpoint_with_logged_in_users(client, auth_header, logged_in_users):
    res = client.get("/oauth2/connected", headers=auth_header)
    assert res.status_code == 200


def test_token_endpoint_with_default_idp(client, logged_in_users, auth_header):
    # the token returned for a specific IDP should be created using the
    # corresponding refresh_token, using the logged in user's username
    res = client.get("/token/?idp=default", headers=auth_header)
    assert res.status_code == 200
    assert (
        res.json["token"]
        == "access_token_for_" + logged_in_users["default"][0]["refresh_token"]
    )


def test_token_endpoint_with_idp_a(client, logged_in_users, auth_header):
    res = client.get("/token/?idp=idp_a", headers=auth_header)
    assert res.status_code == 200
    assert (
        res.json["token"]
        == "access_token_for_" + logged_in_users["idp_a"][0]["refresh_token"]
    )


def test_token_endpoint_without_specifying_idp(client, logged_in_users, auth_header):
    # make sure the IDP we use is "default" when no IDP is requested
    res = client.get("/token/", headers=auth_header)
    assert res.status_code == 200
    assert (
        res.json["token"]
        == "access_token_for_" + logged_in_users["default"][0]["refresh_token"]
    )


def test_token_endpoint_with_bogus_idp(client, logged_in_users, auth_header):
    res = client.get("/token/?idp=bogus", headers=auth_header)
    assert res.status_code == 400


def test_token_endpoint_without_auth_header(client, logged_in_users):
    res = client.get("/token/")
    assert res.status_code == 403


# test_aggregate_other_user_not_returned
# test_aggregate_one_commons_missing
# test_aggregate_all_commons_missing


def test_aggregate_user_user_endpoint(app, client, logged_in_users, auth_header):
    res = client.get("/aggregate/user/user", headers=auth_header)

    assert res.status_code == 200

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json

    default_commons_authz_mapping = res.json[default_commons_hostname]["authz"]
    assert "/a" in default_commons_authz_mapping
    assert "/b" not in default_commons_authz_mapping
    assert "/c" not in default_commons_authz_mapping
    assert "/y" not in default_commons_authz_mapping
    assert "/z" not in default_commons_authz_mapping

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert idp_a_commons_hostname in res.json

    idp_a_commons_authz_mapping = res.json[idp_a_commons_hostname]["authz"]
    assert "/b" in idp_a_commons_authz_mapping
    assert "/a" not in idp_a_commons_authz_mapping
    assert "/c" not in idp_a_commons_authz_mapping
    assert "/y" not in idp_a_commons_authz_mapping
    assert "/z" not in idp_a_commons_authz_mapping


def test_aggregate_with_endpoint_not_in_allowlist(client, auth_header):
    res = client.get("/aggregate/user/credentials/api", headers=auth_header)
    assert res.status_code == 404


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


# TODO review this endpoint if refactoring mocks
def test_authorization_url_endpoint(client):
    res = client.get("/oauth2/authorization_url?idp=idp_a")
    assert res.status_code == 302
    assert res.location.startswith("https://some.data.commons/user/oauth2/authorize")


def test_external_oidc_endpoint_without_logged_in_users(
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


def test_external_oidc_endpoint_with_logged_in_users(
    client, logged_in_users, auth_header
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
