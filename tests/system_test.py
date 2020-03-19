def test_status_endpoint(client, db_session):
    res = client.get("/_status")
    assert res.status_code == 200
