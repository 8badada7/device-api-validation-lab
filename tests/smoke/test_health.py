import pytest


@pytest.mark.smoke
def test_health(api_client):
    response = api_client.health()

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
