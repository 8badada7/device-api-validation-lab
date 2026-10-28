import pytest
import requests


@pytest.mark.recovery
def test_slow_response_causes_read_timeout(recovery_dut):
    recovery_dut.start()
    with requests.Session() as session:
        session.trust_env = False
        health_response = session.get(
            f"{recovery_dut.base_url}/health",
            timeout=recovery_dut.request_timeout,
        )
        assert health_response.status_code == 200

        with pytest.raises(requests.exceptions.ReadTimeout):
            session.get(f"{recovery_dut.base_url}/__test__/slow", timeout=0.2)


@pytest.mark.recovery
def test_slow_response_succeeds_with_sufficient_timeout(recovery_dut):
    recovery_dut.start()
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(
            f"{recovery_dut.base_url}/__test__/slow", timeout=3
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "delay_seconds": 1.0}


@pytest.mark.recovery
def test_health_and_business_after_read_timeout(recovery_dut):
    recovery_dut.start()
    original_process = recovery_dut.process
    with requests.Session() as slow_session:
        slow_session.trust_env = False
        health_response = slow_session.get(
            f"{recovery_dut.base_url}/health",
            timeout=recovery_dut.request_timeout,
        )
        assert health_response.status_code == 200

        with pytest.raises(requests.exceptions.ReadTimeout):
            slow_session.get(f"{recovery_dut.base_url}/__test__/slow", timeout=0.2)

    assert recovery_dut.process is original_process
    assert original_process.poll() is None

    with requests.Session() as session:
        session.trust_env = False
        health_response = session.get(
            f"{recovery_dut.base_url}/health",
            timeout=recovery_dut.request_timeout,
        )
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}

        connect_response = session.post(
            f"{recovery_dut.base_url}/connect",
            timeout=recovery_dut.request_timeout,
        )
        assert connect_response.status_code == 200
        assert connect_response.json()["connected"] is True

        read_response = session.get(
            f"{recovery_dut.base_url}/read",
            params={"address": 100},
            timeout=recovery_dut.request_timeout,
        )
        assert read_response.status_code == 200
        assert read_response.json() == {"address": 100, "value": 1234}

        disconnect_response = session.post(
            f"{recovery_dut.base_url}/disconnect",
            timeout=recovery_dut.request_timeout,
        )
        assert disconnect_response.status_code == 200
        assert disconnect_response.json()["connected"] is False

    assert recovery_dut.process is original_process
    assert original_process.poll() is None


@pytest.mark.recovery
def test_http_500_is_response_not_timeout(recovery_dut):
    recovery_dut.start()
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(
            f"{recovery_dut.base_url}/__test__/server-error",
            timeout=recovery_dut.request_timeout,
        )

        assert isinstance(response, requests.Response)
        assert response.status_code == 500
        assert response.json() == {"error": "simulated_internal_error"}

        health_response = session.get(
            f"{recovery_dut.base_url}/health",
            timeout=recovery_dut.request_timeout,
        )
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}
