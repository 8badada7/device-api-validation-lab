import pytest


@pytest.fixture
def connected_client(api_client):
    response = api_client.connect()

    assert response.status_code == 200
    assert response.json()["connected"] is True

    try:
        yield api_client
    finally:
        disconnect_response = api_client.disconnect()
        assert disconnect_response.status_code == 200
        assert disconnect_response.json()["connected"] is False


@pytest.fixture
def disconnected_client(api_client):
    response = api_client.disconnect()

    assert response.status_code == 200
    assert response.json()["connected"] is False

    try:
        yield api_client
    finally:
        disconnect_response = api_client.disconnect()
        assert disconnect_response.status_code == 200
        assert disconnect_response.json()["connected"] is False


@pytest.fixture
def preserved_register100(connected_client):
    original_response = connected_client.read(100)
    assert original_response.status_code == 200
    original_data = original_response.json()
    assert original_data["address"] == 100
    original_value = original_data["value"]

    try:
        yield connected_client
    finally:
        restore_response = connected_client.write(100, original_value)
        assert restore_response.status_code == 200
        assert restore_response.json() == {
            "address": 100,
            "value": original_value,
        }

        readback_response = connected_client.read(100)
        assert readback_response.status_code == 200
        assert readback_response.json() == {
            "address": 100,
            "value": original_value,
        }
