import pytest


@pytest.mark.api
@pytest.mark.parametrize(
    "address, value",
    [
        (100, 0),
        (100, 1),
        (100, 4321),
        (100, 65535),
    ],
    ids=["min-0", "value-1", "value-4321", "max-65535"],
)
def test_write_readback(preserved_register100, address, value):
    response = preserved_register100.write(address, value)

    assert response.status_code == 200
    data = response.json()
    assert data["address"] == address
    assert data["value"] == value

    readback_response = preserved_register100.read(address)
    assert readback_response.status_code == 200
    assert readback_response.json() == {"address": address, "value": value}


@pytest.mark.api
@pytest.mark.parametrize(
    "value",
    [None, -1, 65536, "abc", True],
    ids=["missing-value", "below-min", "above-max", "string-value", "bool-value"],
)
def test_write_invalid_value(preserved_register100, value):
    original_response = preserved_register100.read(100)
    assert original_response.status_code == 200
    original_data = original_response.json()

    response = preserved_register100.write(100, value)

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_value"}

    readback_response = preserved_register100.read(100)
    assert readback_response.status_code == 200
    assert readback_response.json() == original_data


@pytest.mark.api
@pytest.mark.parametrize(
    "address",
    [None, "100", -1],
    ids=["missing-address", "string-address", "negative-address"],
)
def test_write_invalid_address(preserved_register100, address):
    original_response = preserved_register100.read(100)
    assert original_response.status_code == 200
    original_data = original_response.json()

    response = preserved_register100.write(address, 4321)

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_address"}

    readback_response = preserved_register100.read(100)
    assert readback_response.status_code == 200
    assert readback_response.json() == original_data


@pytest.mark.api
def test_write_register_not_found(preserved_register100):
    original_response = preserved_register100.read(100)
    assert original_response.status_code == 200
    original_data = original_response.json()

    response = preserved_register100.write(999, 4321)

    assert response.status_code == 404
    assert response.json() == {"error": "register_not_found"}

    readback_response = preserved_register100.read(100)
    assert readback_response.status_code == 200
    assert readback_response.json() == original_data
