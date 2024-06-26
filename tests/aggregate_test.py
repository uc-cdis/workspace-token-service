import httpx
import json
import os
import uuid

from .conftest import (
    assert_authz_mapping_for_test_user_in_default_commons,
    assert_authz_mapping_for_test_user_in_idp_a_commons,
    assert_authz_mapping_for_user_without_access_token,
)


def get_number_of_configured_idps():
    with open(os.environ["SECRET_CONFIG"], "r") as f:
        external_idps = json.load(f)["external_oidc"]
    count = 0
    for provider in external_idps:
        count += len(provider.get("login_options", {}))
    return count


def test_aggregate_user_user_endpoint(
    app, client, persisted_refresh_tokens, auth_header
):
    """
    Test aggregate endpoint using `/user/user`. Expect a
    200 response with aggregate data returned from
    the default commons and "idp_a".
    """
    res = client.get("/aggregate/user/user", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == get_number_of_configured_idps()

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json
    assert len(res.json[default_commons_hostname]) == 3
    assert_authz_mapping_for_test_user_in_default_commons(
        res.json[default_commons_hostname]["authz"]
    )

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert idp_a_commons_hostname in res.json
    assert len(res.json[idp_a_commons_hostname]) == 3
    assert_authz_mapping_for_test_user_in_idp_a_commons(
        res.json[idp_a_commons_hostname]["authz"]
    )


def test_aggregate_user_user_endpoint_with_filters(
    app, client, persisted_refresh_tokens, auth_header
):
    """
    Test that aggregate endpoint successfully returns only specified filters.
    """
    res = client.get(
        "/aggregate/user/user?filters=authz&filters=role", headers=auth_header
    )
    assert res.status_code == 200
    assert len(res.json) == get_number_of_configured_idps()

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json
    assert len(res.json[default_commons_hostname]) == 2
    assert "role" in res.json[default_commons_hostname]
    assert "authz" in res.json[default_commons_hostname]
    assert_authz_mapping_for_test_user_in_default_commons(
        res.json[default_commons_hostname]["authz"]
    )

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert idp_a_commons_hostname in res.json
    assert len(res.json[idp_a_commons_hostname]) == 2
    assert "role" in res.json[idp_a_commons_hostname]
    assert "authz" in res.json[idp_a_commons_hostname]
    assert_authz_mapping_for_test_user_in_idp_a_commons(
        res.json[idp_a_commons_hostname]["authz"]
    )


def test_aggregate_user_user_endpoint_with_absent_filter(
    app, client, persisted_refresh_tokens, auth_header
):
    """
    Test that aggregate endpoint returns a successful response when filters
    specified are absent. Check that absence is indicated via a special
    value (i.e. JSON `null`).
    """
    res = client.get("/aggregate/user/user?filters=absent", headers=auth_header)
    assert res.status_code == 200

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert res.json[default_commons_hostname]["absent"] is None

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert res.json[idp_a_commons_hostname]["absent"] is None


def test_aggregate_endpoint_when_one_linked_commons_returns_500(
    app, client, persisted_refresh_tokens, auth_header, respx_mock
):
    """
    Test aggregate endpoint when one linked commons returns a 500.
    Expect that WTS still returns a 200.
    """
    idp_a_fence_url = app.config["OIDC"]["idp_a"]["api_base_url"].rstrip("/")
    respx_mock.get(f"{idp_a_fence_url}/user").mock(return_value=httpx.Response(500))
    res = client.get("/aggregate/user/user", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == get_number_of_configured_idps()

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json
    assert len(res.json[default_commons_hostname]) == 3
    assert_authz_mapping_for_test_user_in_default_commons(
        res.json[default_commons_hostname]["authz"]
    )

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert res.json[idp_a_commons_hostname] is None


def test_aggregate_endpoint_with_anonymous_request(
    app, client, persisted_refresh_tokens, respx_mock
):
    """
    Test aggregate endpoint when making an anonymous request. Expect
    a 200 response containing data from all configured commons.
    """
    commons_hostnames = app.config["COMMONS_HOSTNAMES"]
    for commons_hostname in commons_hostnames:
        respx_mock.get(f"https://{commons_hostname}/index/index").mock(
            return_value=httpx.Response(
                200, json={"records": [{"did": str(uuid.uuid4())}]}
            )
        )

    res = client.get("/aggregate/index/index")
    assert res.status_code == 200
    assert len(res.json) == len(commons_hostnames)
    for commons_hostname in commons_hostnames:
        assert commons_hostname in res.json
        assert list(res.json[commons_hostname].keys()) == ["records"]
        assert len(res.json[commons_hostname]["records"]) == 1
        assert list(res.json[commons_hostname]["records"][0].keys()) == ["did"]


def test_aggregate_with_endpoint_not_in_allowlist(client, auth_header):
    """
    Test that aggregate endpoint returns a 404 when the requested endpoint is
    not in configured allowlist.
    """
    res = client.get("/aggregate/user/credentials/api", headers=auth_header)
    assert res.status_code == 404


def test_aggregate_authz_mapping_endpoint_with_no_connected_commons(
    app, client, default_refresh_tokens, auth_header
):
    """
    Test aggregate endpoint using `/authz/mapping` when "idp_a" has no refresh_token. Expect a
    200 response with aggregate data returned from
    the default commons and "idp_a".
    """
    res = client.get("/aggregate/authz/mapping", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == get_number_of_configured_idps()

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json

    # Authz mapping returns both open and controlled access records
    assert len(res.json[default_commons_hostname]) == 2
    assert_authz_mapping_for_test_user_in_default_commons(
        res.json[default_commons_hostname]
    )

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert idp_a_commons_hostname in res.json

    # Authz mapping returns only open access records since no refresh_token for idp_a
    assert len(res.json[idp_a_commons_hostname]) == 1
    assert_authz_mapping_for_user_without_access_token(res.json[idp_a_commons_hostname])


def test_aggregate_authz_mapping_endpoint_with_connected_commons(
    app, client, persisted_refresh_tokens, auth_header
):
    """
    Test aggregate endpoint using `/authz/mapping` when "idp_a" also has a refresh_token. Expect a
    200 response with aggregate data returned from the default commons and "idp_a".
    """
    res = client.get("/aggregate/authz/mapping", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == get_number_of_configured_idps()

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json

    # Authz mapping returns both open and controlled access records
    assert len(res.json[default_commons_hostname]) == 2
    assert_authz_mapping_for_test_user_in_default_commons(
        res.json[default_commons_hostname]
    )

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert idp_a_commons_hostname in res.json

    # Authz mapping returns both open and controlled access records
    assert len(res.json[idp_a_commons_hostname]) == 2
    assert_authz_mapping_for_test_user_in_idp_a_commons(
        res.json[idp_a_commons_hostname]
    )
