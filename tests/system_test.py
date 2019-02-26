def test_status_endpoint(client):
    res = client.get("/_status")
    assert res.status_code == 200
