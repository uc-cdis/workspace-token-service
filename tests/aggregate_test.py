import httpx
import uuid

from .conftest import (
    assert_authz_mapping_for_test_user_in_default_commons,
    assert_authz_mapping_for_test_user_in_idp_a_commons,
)


def test_aggregate_user_user_endpoint(
    app, client, persisted_refresh_tokens, auth_header
):
    res = client.get("/aggregate/user/user", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == 2

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
    res = client.get(
        "/aggregate/user/user?filters=authz&filters=role", headers=auth_header
    )
    assert res.status_code == 200
    assert len(res.json) == 2

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert default_commons_hostname in res.json
    assert len(res.json[default_commons_hostname]) == 2
    assert "role" in res.json[default_commons_hostname]
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


def test_aggregate_user_user_endpoint_with_wrong_filter(
    app, client, persisted_refresh_tokens, auth_header
):
    res = client.get("/aggregate/user/user?filters=wrong", headers=auth_header)
    assert res.status_code == 200

    default_commons_hostname = app.config["OIDC"]["default"]["commons_hostname"]
    assert res.json[default_commons_hostname]["wrong"] is None

    idp_a_commons_hostname = app.config["OIDC"]["idp_a"]["commons_hostname"]
    assert res.json[idp_a_commons_hostname]["wrong"] is None


def test_aggregate_endpoint_when_one_linked_commons_returns_500(
    app, client, persisted_refresh_tokens, auth_header, respx_mock
):
    idp_a_fence_url = app.config["OIDC"]["idp_a"]["api_base_url"].rstrip("/")
    respx_mock.get(f"{idp_a_fence_url}/user").mock(return_value=httpx.Response(500))
    res = client.get("/aggregate/user/user", headers=auth_header)
    assert res.status_code == 200
    assert len(res.json) == 2

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
    res = client.get("/aggregate/user/credentials/api", headers=auth_header)
    assert res.status_code == 404
