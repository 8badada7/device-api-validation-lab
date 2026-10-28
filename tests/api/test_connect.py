import pytest


@pytest.mark.api
def test_connect_success(disconnected_client):
    response = disconnected_client.connect()

    assert response.status_code == 200
    assert response.json()["connected"] is True


@pytest.mark.api
def test_connect_repeated(disconnected_client):
    first_response = disconnected_client.connect()
    second_response = disconnected_client.connect()

    assert first_response.status_code == 200
    assert first_response.json()["connected"] is True
    assert second_response.status_code == 200
    assert second_response.json()["connected"] is True


@pytest.mark.api
def test_health_after_connect(disconnected_client):
    connect_response = disconnected_client.connect()

    assert connect_response.status_code == 200
    assert connect_response.json()["connected"] is True

    health_response = disconnected_client.health()

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
