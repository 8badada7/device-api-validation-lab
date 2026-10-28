from contextlib import closing

import pytest
import requests

from src.device_api_client import DeviceApiClient


@pytest.mark.recovery
def test_service_stop_causes_connection_error(recovery_dut):
    recovery_dut.start()
    with closing(
        DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)
    ) as client:
        client.session.trust_env = False
        response = client.health()
        assert response.status_code == 200

        recovery_dut.stop()
        assert recovery_dut.process.poll() is not None

        with pytest.raises(requests.exceptions.ConnectionError):
            client.health()


@pytest.mark.recovery
def test_service_restart_restores_http_then_business(recovery_dut):
    recovery_dut.start()
    with closing(
        DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)
    ) as client:
        client.session.trust_env = False
        health_response = client.health()
        assert health_response.status_code == 200

        connect_response = client.connect()
        assert connect_response.status_code == 200
        assert connect_response.json()["connected"] is True

        read_response = client.read(100)
        assert read_response.status_code == 200
        assert read_response.json() == {"address": 100, "value": 1234}

        recovery_dut.stop()
        assert recovery_dut.process.poll() is not None

        with pytest.raises(requests.exceptions.ConnectionError):
            client.health()

        recovery_dut.restart()
        with closing(
            DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)
        ) as restarted_client:
            restarted_client.session.trust_env = False
            health_response = restarted_client.health()
            assert health_response.status_code == 200

            disconnected_read = restarted_client.read(100)
            assert disconnected_read.status_code == 409
            assert disconnected_read.json() == {"error": "not_connected"}

            connect_response = restarted_client.connect()
            assert connect_response.status_code == 200
            assert connect_response.json()["connected"] is True

            read_response = restarted_client.read(100)
            assert read_response.status_code == 200
            assert read_response.json() == {"address": 100, "value": 1234}

            disconnect_response = restarted_client.disconnect()
            assert disconnect_response.status_code == 200
            assert disconnect_response.json()["connected"] is False
