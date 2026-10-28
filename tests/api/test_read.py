import pytest


@pytest.mark.api
@pytest.mark.parametrize(
    "address, expected",
    [
        (100, 1234),
        (101, 5678),
    ],
    ids=["reg-100", "reg-101"],
)
def test_read_valid_register(connected_client, address, expected):
    response = connected_client.read(address)

    assert response.status_code == 200
    data = response.json()
    assert data["address"] == address
    assert data["value"] == expected


@pytest.mark.api
@pytest.mark.parametrize(
    "address",
    [None, "abc", -1],
    ids=["missing-address", "non-integer", "negative-address"],
)
def test_read_invalid_address(connected_client, address):
    response = connected_client.read(address)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_address"


@pytest.mark.api
def test_read_register_not_found(connected_client):
    response = connected_client.read(999)

    assert response.status_code == 404
    assert response.json()["error"] == "register_not_found"
