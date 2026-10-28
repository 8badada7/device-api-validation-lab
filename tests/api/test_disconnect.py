import pytest


@pytest.mark.api
def test_disconnect_success(connected_client):
    response = connected_client.disconnect()

    assert response.status_code == 200
    assert response.json()["connected"] is False


@pytest.mark.api
def test_disconnect_repeated(disconnected_client):
    first_response = disconnected_client.disconnect()
    second_response = disconnected_client.disconnect()

    assert first_response.status_code == 200
    assert first_response.json()["connected"] is False
    assert second_response.status_code == 200
    assert second_response.json()["connected"] is False


@pytest.mark.api
def test_health_after_disconnect(disconnected_client):
    response = disconnected_client.health()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.api
def test_read_when_disconnected(disconnected_client):
    response = disconnected_client.read(100)

    assert response.status_code == 409
    assert response.json() == {"error": "not_connected"}


@pytest.mark.api
def test_write_when_disconnected(disconnected_client):
    response = disconnected_client.write(100, 4321)

    assert response.status_code == 409
    assert response.json() == {"error": "not_connected"}


@pytest.mark.api
def test_disconnect_changes_read_behavior(connected_client):
    before_response = connected_client.read(100)
    assert before_response.status_code == 200

    disconnect_response = connected_client.disconnect()
    assert disconnect_response.status_code == 200
    assert disconnect_response.json()["connected"] is False

    after_response = connected_client.read(100)
    assert after_response.status_code == 409
    assert after_response.json() == {"error": "not_connected"}
