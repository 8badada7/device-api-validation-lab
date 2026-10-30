import pytest
import requests


@pytest.mark.recovery
def test_delayed_write_causes_read_timeout(preserved_recovery_register100):
    client, original_value = preserved_recovery_register100
    assert original_value == 1234

    with pytest.raises(requests.exceptions.ReadTimeout):
        client.session.post(
            f"{client.base_url}/__test__/write-delayed",
            json={"address": 100, "value": 4321},
            timeout=0.2,
        )


@pytest.mark.recovery
def test_write_takes_effect_despite_read_timeout(
    preserved_recovery_register100, recovery_dut
):
    client, original_value = preserved_recovery_register100
    assert original_value == 1234
    original_process = recovery_dut.process

    with pytest.raises(requests.exceptions.ReadTimeout):
        client.session.post(
            f"{client.base_url}/__test__/write-delayed",
            json={"address": 100, "value": 4321},
            timeout=0.2,
        )

    read_response = client.read(100)
    assert read_response.status_code == 200
    assert read_response.json() == {"address": 100, "value": 4321}
    assert recovery_dut.process is original_process
    assert original_process.poll() is None


@pytest.mark.recovery
def test_repeated_same_value_is_idempotent(preserved_recovery_register100):
    client, original_value = preserved_recovery_register100
    assert original_value == 1234

    with pytest.raises(requests.exceptions.ReadTimeout):
        client.session.post(
            f"{client.base_url}/__test__/write-delayed",
            json={"address": 100, "value": 4321},
            timeout=0.2,
        )

    first_read = client.read(100)
    assert first_read.status_code == 200
    assert first_read.json() == {"address": 100, "value": 4321}

    write_response = client.write(100, 4321)
    assert write_response.status_code == 200
    assert write_response.json() == {"address": 100, "value": 4321}

    second_read = client.read(100)
    assert second_read.status_code == 200
    assert second_read.json() == {"address": 100, "value": 4321}


@pytest.mark.recovery
def test_delayed_write_succeeds_with_sufficient_timeout(preserved_recovery_register100):
    client, original_value = preserved_recovery_register100
    assert original_value == 1234

    response = client.session.post(
        f"{client.base_url}/__test__/write-delayed",
        json={"address": 100, "value": 4321},
        timeout=3,
    )
    assert response.status_code == 200
    assert response.json() == {"address": 100, "value": 4321}

    read_response = client.read(100)
    assert read_response.status_code == 200
    assert read_response.json() == {"address": 100, "value": 4321}
