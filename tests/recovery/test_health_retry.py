from urllib.parse import urlencode

import pytest
import requests

from src.health_retry import check_health_with_retry


def _check_with_evidence(session, url, evidence, *, timeout=1):
    def record_attempt(attempt):
        evidence.record_event("call", "health_retry_attempt", observed=attempt)
        if attempt["attempt_number"] > 1:
            evidence.record_event(
                "call", "retry_continued",
                observed={
                    "from_attempt": attempt["attempt_number"] - 1,
                    "completed_attempt": attempt["attempt_number"],
                },
            )

    return check_health_with_retry(
        session, url,
        max_attempts=3,
        timeout=timeout,
        retry_interval=0.2,
        on_attempt=record_attempt,
    )


def _assert_result(result, evidence, *, success, attempts_used, stop_reason):
    evidence.record_event(
        "call", "health_retry_result",
        expected={
            "success": success,
            "attempts_used": attempts_used,
            "stop_reason": stop_reason,
        },
        observed=result,
    )
    assert result["success"] is success
    assert result["attempts_used"] == attempts_used
    assert result["max_attempts"] == 3
    assert result["stop_reason"] == stop_reason
    assert len(result["history"]) == attempts_used
    assert [entry["attempt_number"] for entry in result["history"]] == list(
        range(1, attempts_used + 1)
    )
    assert [entry["will_retry"] for entry in result["history"]] == (
        [True] * (attempts_used - 1) + [False]
    )


def _assert_server_count(session, dut, scenario, expected, evidence):
    # Query twice to also verify that reading statistics does not change them.
    for _ in range(2):
        with session.get(
            f"{dut.base_url}/__test__/retry-stats",
            params={"scenario": scenario},
            timeout=dut.request_timeout,
            allow_redirects=False,
        ) as response:
            evidence.record_event(
                "call", "server_request_count",
                expected={"http_status": 200, "request_count": expected},
                observed={"http_status": response.status_code},
            )
            assert response.status_code == 200
            data = response.json()
            evidence.record_event(
                "call", "server_request_count_value",
                expected={"scenario": scenario, "request_count": expected},
                observed=data,
            )
            assert data == {"scenario": scenario, "request_count": expected}


@pytest.mark.recovery
def test_health_retry_stops_after_first_success(fault_evidence, recovery_dut):
    recovery_dut.start()
    scenario = "immediate_200"
    with requests.Session() as session:
        session.trust_env = False
        result = _check_with_evidence(
            session,
            f"{recovery_dut.base_url}/__test__/retry-health?{urlencode({'scenario': scenario})}",
            fault_evidence,
        )
        _assert_result(
            result, fault_evidence,
            success=True, attempts_used=1, stop_reason="success",
        )
        assert result["history"] == [{
            "attempt_number": 1, "outcome": "healthy", "http_status": 200,
            "exception_type": None, "retryable": False, "will_retry": False,
        }]
        _assert_server_count(session, recovery_dut, scenario, 1, fault_evidence)


@pytest.mark.recovery
def test_health_retry_recovers_after_two_503(fault_evidence, recovery_dut):
    recovery_dut.start()
    scenario = "recover_after_two_503"
    with requests.Session() as session:
        session.trust_env = False
        result = _check_with_evidence(
            session,
            f"{recovery_dut.base_url}/__test__/retry-health?{urlencode({'scenario': scenario})}",
            fault_evidence,
        )
        _assert_result(
            result, fault_evidence,
            success=True, attempts_used=3, stop_reason="recovered",
        )
        assert [entry["http_status"] for entry in result["history"]] == [503, 503, 200]
        assert [entry["outcome"] for entry in result["history"]] == [
            "http_response", "http_response", "healthy",
        ]
        assert [entry["retryable"] for entry in result["history"]] == [True, True, False]
        assert all(entry["exception_type"] is None for entry in result["history"])
        _assert_server_count(session, recovery_dut, scenario, 3, fault_evidence)


@pytest.mark.recovery
def test_health_retry_stops_when_503_attempts_exhausted(fault_evidence, recovery_dut):
    recovery_dut.start()
    scenario = "always_503"
    with requests.Session() as session:
        session.trust_env = False
        result = _check_with_evidence(
            session,
            f"{recovery_dut.base_url}/__test__/retry-health?{urlencode({'scenario': scenario})}",
            fault_evidence,
        )
        _assert_result(
            result, fault_evidence,
            success=False, attempts_used=3, stop_reason="attempts_exhausted",
        )
        assert [entry["http_status"] for entry in result["history"]] == [503, 503, 503]
        assert all(entry["outcome"] == "http_response" for entry in result["history"])
        assert all(entry["retryable"] is True for entry in result["history"])
        assert all(entry["exception_type"] is None for entry in result["history"])
        _assert_server_count(session, recovery_dut, scenario, 3, fault_evidence)


@pytest.mark.recovery
@pytest.mark.parametrize(
    "scenario, status",
    [("always_400", 400), ("always_500", 500)],
    ids=["http-400", "http-500"],
)
def test_health_retry_stops_on_non_retryable_response(
    fault_evidence, recovery_dut, scenario, status
):
    recovery_dut.start()
    with requests.Session() as session:
        session.trust_env = False
        result = _check_with_evidence(
            session,
            f"{recovery_dut.base_url}/__test__/retry-health?{urlencode({'scenario': scenario})}",
            fault_evidence,
        )
        _assert_result(
            result, fault_evidence,
            success=False, attempts_used=1, stop_reason="non_retryable_response",
        )
        assert result["history"] == [{
            "attempt_number": 1, "outcome": "http_response", "http_status": status,
            "exception_type": None, "retryable": False, "will_retry": False,
        }]
        _assert_server_count(session, recovery_dut, scenario, 1, fault_evidence)


@pytest.mark.recovery
def test_health_retry_connection_error_attempts_exhausted(fault_evidence, recovery_dut):
    recovery_dut.start()
    with requests.Session() as session:
        session.trust_env = False
        with session.get(
            f"{recovery_dut.base_url}/health",
            timeout=recovery_dut.request_timeout,
            allow_redirects=False,
        ) as health:
            fault_evidence.record_event(
                "call", "health_before_stop",
                expected={"http_status": 200}, observed={"http_status": health.status_code},
            )
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}

        recovery_dut.stop()
        exited = recovery_dut.process.poll() is not None
        fault_evidence.record_event(
            "call", "service_stop",
            expected={"process_exited": True}, observed={"process_exited": exited},
        )
        assert exited

        result = _check_with_evidence(
            session, f"{recovery_dut.base_url}/health", fault_evidence,
        )
        _assert_result(
            result, fault_evidence,
            success=False, attempts_used=3, stop_reason="attempts_exhausted",
        )
        assert all(entry["outcome"] == "exception" for entry in result["history"])
        assert all(entry["http_status"] is None for entry in result["history"])
        assert all(
            entry["exception_type"] in ("ConnectionError", "ConnectTimeout")
            for entry in result["history"]
        )
        assert all(entry["retryable"] is True for entry in result["history"])
        assert recovery_dut.process.poll() is not None


@pytest.mark.recovery
def test_health_retry_read_timeout_attempts_exhausted(fault_evidence, recovery_dut):
    recovery_dut.start()
    original_process = recovery_dut.process
    with requests.Session() as session:
        session.trust_env = False
        result = _check_with_evidence(
            session, f"{recovery_dut.base_url}/__test__/slow", fault_evidence,
            timeout=0.2,
        )
        _assert_result(
            result, fault_evidence,
            success=False, attempts_used=3, stop_reason="attempts_exhausted",
        )
        assert all(entry["outcome"] == "exception" for entry in result["history"])
        assert all(entry["http_status"] is None for entry in result["history"])
        assert all(entry["exception_type"] == "ReadTimeout" for entry in result["history"])
        assert all(entry["retryable"] is True for entry in result["history"])
        assert recovery_dut.process is original_process
        assert original_process.poll() is None
