from contextlib import closing

import pytest
import requests

from src.device_api_client import DeviceApiClient


@pytest.mark.recovery
def test_write_timeout_evidence(fault_evidence, preserved_recovery_register100, recovery_dut):
    client, original_value = preserved_recovery_register100
    assert original_value == 1234
    fault_evidence.set_state("before", process_running=recovery_dut.process.poll() is None)
    fault_evidence.record_event(
        "call", "write_request",
        expected={"exception_type": "ReadTimeout"},
        observed={"address": 100, "target_value": 4321, "timeout_seconds": 0.2},
    )
    with pytest.raises(requests.exceptions.ReadTimeout) as captured:
        response = client.session.post(
            f"{client.base_url}/__test__/write-delayed",
            json={"address": 100, "value": 4321}, timeout=0.2,
        )
        fault_evidence.record_event(
            "call", "unexpected_write_response",
            expected={"exception_type": "ReadTimeout"},
            observed={"http_status": response.status_code},
        )
    fault_evidence.record_event(
        "call", "ReadTimeout",
        expected={"exception_type": "ReadTimeout"},
        observed={"exception_type": type(captured.value).__name__},
    )

    readback = client.read(100)
    fault_evidence.record_event(
        "call", "read_after_timeout",
        expected={"http_status": 200, "register100": 4321},
        observed={"http_status": readback.status_code},
    )
    assert readback.status_code == 200
    value = readback.json()["value"]
    fault_evidence.record_event(
        "call", "register_value_after_timeout",
        expected={"register100": 4321}, observed={"register100": value},
    )
    fault_evidence.set_state("after", register100=value)
    assert value == 4321
    assert recovery_dut.process.poll() is None


@pytest.mark.recovery
def test_http_500_evidence(fault_evidence, recovery_dut):
    recovery_dut.start()
    fault_evidence.set_state("before", process_running=recovery_dut.process.poll() is None)
    with closing(DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)) as client:
        client.session.trust_env = False
        response = client.session.get(
            f"{client.base_url}/__test__/server-error", timeout=client.timeout
        )
        fault_evidence.record_event(
            "call", "http_error_response",
            expected={"http_status": 500, "error": "simulated_internal_error"},
            observed={"http_status": response.status_code},
        )
        assert response.status_code == 500
        error_code = response.json()["error"]
        fault_evidence.record_event(
            "call", "HTTP500",
            expected={"error": "simulated_internal_error"},
            observed={"http_status": response.status_code, "error": error_code},
        )
        assert response.json() == {"error": "simulated_internal_error"}

        health = client.health()
        fault_evidence.record_event(
            "call", "health_after_http_500",
            expected={"http_status": 200}, observed={"http_status": health.status_code},
        )
        fault_evidence.set_state(
            "after", health_status=health.status_code,
            process_running=recovery_dut.process.poll() is None,
        )
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}


@pytest.mark.recovery
def test_connection_error_evidence(fault_evidence, recovery_dut):
    recovery_dut.start()
    with closing(DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)) as client:
        client.session.trust_env = False
        health = client.health()
        fault_evidence.record_event(
            "call", "health_before_stop",
            expected={"http_status": 200}, observed={"http_status": health.status_code},
        )
        fault_evidence.set_state(
            "before", health_status=health.status_code,
            process_running=recovery_dut.process.poll() is None,
        )
        assert health.status_code == 200

        recovery_dut.stop()
        exited = recovery_dut.process.poll() is not None
        fault_evidence.record_event(
            "call", "service_stop",
            expected={"process_exited": True}, observed={"process_exited": exited},
        )
        assert exited
        with pytest.raises(requests.exceptions.ConnectionError) as captured:
            response = client.health()
            fault_evidence.record_event(
                "call", "unexpected_health_response",
                expected={"exception_type": "ConnectionError"},
                observed={"http_status": response.status_code},
            )
        fault_evidence.record_event(
            "call", "ConnectionError",
            expected={"exception_type": "ConnectionError"},
            observed={"exception_type": type(captured.value).__name__},
        )

        recovery_dut.restart()
        with closing(DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)) as restarted_client:
            restarted_client.session.trust_env = False
            health = restarted_client.health()
            running = recovery_dut.process.poll() is None
            fault_evidence.record_event(
                "call", "http_recovery",
                expected={"http_status": 200, "process_running": True},
                observed={"http_status": health.status_code, "process_running": running},
            )
            fault_evidence.set_state("after", health_status=health.status_code, process_running=running)
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}
            assert running
