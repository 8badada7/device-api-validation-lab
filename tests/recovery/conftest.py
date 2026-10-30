from contextlib import closing
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import pytest
import requests

from evidence import EvidenceRecorder, exception_details
from src.device_api_client import DeviceApiClient


EVIDENCE_KEY = pytest.StashKey[EvidenceRecorder]()


@pytest.fixture
def fault_evidence(request):
    recorder = EvidenceRecorder(request.node.nodeid)
    request.node.stash[EVIDENCE_KEY] = recorder
    return recorder


def _evidence_for(request):
    if "fault_evidence" in request.fixturenames:
        return request.getfixturevalue("fault_evidence")
    return None


def _cleanup_evidence(recorder, component, **facts):
    if recorder is not None:
        recorder.record_cleanup(component, **facts)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    result = yield
    report = result.get_result()
    recorder = item.stash.get(EVIDENCE_KEY, None)
    if recorder is None:
        return

    try:
        recorder.record_phase(
            report.when,
            report.outcome,
            report.duration,
            error=call.excinfo.value if call.excinfo is not None else None,
            start=report.start,
            stop=report.stop,
        )
        if report.when == "teardown":
            output_dir = Path(__file__).resolve().parents[2] / "reports" / "evidence"
            recorder.finish_and_write(output_dir)
    except Exception as error:
        # Alter the real report before pytest logs it; do not raise an INTERNALERROR.
        original = str(report.longrepr) if report.failed else ""
        message = (
            f"Fault evidence recording failed ({type(error).__name__}); "
            "a complete JSON file in reports/evidence is not confirmed."
        )
        report.outcome = "failed"
        report.longrepr = f"{original}\n{message}".strip()
        try:
            recorder.record_phase(
                report.when, report.outcome, report.duration, error=error,
                start=report.start, stop=report.stop,
            )
        except Exception as update_error:
            report.longrepr += (
                "\nEvidence phase update also failed "
                f"({type(update_error).__name__})."
            )


DUT_STARTUP_CODE = """
import sys
import time
from threading import Lock

from flask import jsonify, request
from dut.app import app, write

token = sys.argv[1]

@app.after_request
def identify_recovery_dut(response):
    response.headers["X-Recovery-Dut"] = token
    return response

@app.get("/__test__/slow")
def slow_response():
    time.sleep(1.0)
    return jsonify({"status": "ok", "delay_seconds": 1.0}), 200

@app.get("/__test__/server-error")
def server_error_response():
    return jsonify({"error": "simulated_internal_error"}), 500

@app.post("/__test__/write-delayed")
def write_delayed():
    response = app.make_response(write())
    if response.status_code == 200:
        # The register has already been written before delaying the response.
        time.sleep(1.0)
    return response

retry_health_counts = dict.fromkeys(
    (
        "immediate_200",
        "recover_after_two_503",
        "always_503",
        "always_400",
        "always_500",
    ),
    0,
)
retry_health_lock = Lock()

@app.get("/__test__/retry-health")
def retry_health():
    scenario = request.args.get("scenario")
    with retry_health_lock:
        if scenario not in retry_health_counts:
            return jsonify({"error": "invalid_scenario"}), 400
        retry_health_counts[scenario] += 1
        count = retry_health_counts[scenario]

    if scenario == "immediate_200" or (
        scenario == "recover_after_two_503" and count >= 3
    ):
        return jsonify({"status": "ok"}), 200
    if scenario == "always_400":
        return jsonify({"error": "invalid_request"}), 400
    if scenario == "always_500":
        return jsonify({"error": "simulated_internal_error"}), 500
    return jsonify({"error": "temporarily_unavailable"}), 503

@app.get("/__test__/retry-stats")
def retry_stats():
    scenario = request.args.get("scenario")
    with retry_health_lock:
        if scenario not in retry_health_counts:
            return jsonify({"error": "invalid_scenario"}), 400
        count = retry_health_counts[scenario]
    return jsonify({"scenario": scenario, "request_count": count}), 200

app.run(
    host="127.0.0.1",
    port=18001,
    debug=False,
    use_reloader=False,
    threaded=True,
)
"""


class RecoveryDut:
    host = "127.0.0.1"
    port = 18001
    base_url = "http://127.0.0.1:18001"
    request_timeout = 1
    startup_timeout = 8

    def __init__(self, project_root):
        self.project_root = project_root
        self.process = None
        self.log_path = project_root / "logs" / f"recovery_dut_{uuid4().hex}.log"
        self._log_file = None
        self._token = None

    def start(self):
        if self.process is not None:
            if self.process.poll() is None:
                raise RuntimeError("This recovery DUT is already running")
            self.stop()
            self.process = None

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_check:
            # Detect an existing listener without an exclusive bind after restart.
            port_check.settimeout(0.25)
            if port_check.connect_ex((self.host, self.port)) == 0:
                raise RuntimeError(
                    f"Recovery DUT port {self.host}:{self.port} is already occupied. "
                    "No existing process was stopped."
                )

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_path.open("ab", buffering=0)
        self._token = uuid4().hex
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-c", DUT_STARTUP_CODE, self._token],
                cwd=self.project_root,
                stdin=subprocess.DEVNULL,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._wait_until_ready()
        except Exception as error:
            self.stop()
            log_tail = self.log_path.read_text(
                encoding="utf-8", errors="replace"
            )[-4000:]
            exit_code = self.process.returncode if self.process is not None else None
            raise RuntimeError(
                f"Recovery DUT startup failed: {error}\n"
                f"Exit code: {exit_code}\nLog: {self.log_path}\n{log_tail}"
            ) from error
        return self

    def _wait_until_ready(self):
        deadline = time.monotonic() + self.startup_timeout
        last_error = "No health response received"
        with closing(DeviceApiClient(self.base_url, timeout=0.25)) as probe:
            # Recovery traffic must reach the loopback DUT, not an environment proxy.
            probe.session.trust_env = False
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError("Recovery DUT exited before becoming ready")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                probe.timeout = min(0.25, remaining)
                try:
                    response = probe.health()
                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                ) as error:
                    last_error = str(error)
                else:
                    with response:
                        if self.process.poll() is not None:
                            raise RuntimeError("Recovery DUT exited during readiness check")
                        if response.headers.get("X-Recovery-Dut") != self._token:
                            raise RuntimeError(
                                "Port 18001 responded from a different service"
                            )
                        if (
                            response.status_code == 200
                            and response.json() == {"status": "ok"}
                        ):
                            return
                        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        raise RuntimeError(
            f"Recovery DUT was not ready within {self.startup_timeout}s: {last_error}"
        )

    def stop(self):
        try:
            if self.process is None:
                return
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            else:
                self.process.wait(timeout=5)
            if self.process.poll() is None:
                raise RuntimeError("Recovery DUT process did not exit")
        finally:
            if self._log_file is not None:
                self._log_file.close()
                self._log_file = None

    def restart(self):
        self.stop()
        return self.start()


@pytest.fixture
def recovery_dut(request):
    # The opt-in recorder has no DUT dependencies, so this cannot form a cycle.
    recorder = _evidence_for(request)
    project_root = Path(__file__).resolve().parents[2]
    dut = RecoveryDut(project_root)
    try:
        yield dut
    finally:
        facts = {"attempted": True, "success": False}
        try:
            dut.stop()
            facts.update(
                success=True,
                process_started=dut.process is not None,
                exited=dut.process is None or dut.process.poll() is not None,
                exit_code=dut.process.returncode if dut.process is not None else None,
            )
        except Exception as error:
            facts["error"] = exception_details(error)
            raise
        finally:
            _cleanup_evidence(recorder, "process", **facts)
            if recorder is not None:
                recorder.set_state(
                    "after", process_running=dut.process is not None and dut.process.poll() is None
                )


@pytest.fixture
def preserved_recovery_register100(recovery_dut, request):
    recorder = _evidence_for(request)
    recovery_dut.start()
    with closing(
        DeviceApiClient(recovery_dut.base_url, recovery_dut.request_timeout)
    ) as client:
        client.session.trust_env = False
        original_value = None
        try:
            connect_response = client.connect()
            assert connect_response.status_code == 200
            assert connect_response.json()["connected"] is True

            original_response = client.read(100)
            assert original_response.status_code == 200
            original_data = original_response.json()
            assert original_data["address"] == 100
            assert type(original_data["value"]) is int
            original_value = original_data["value"]
            if recorder is not None:
                recorder.set_state("before", connected=True, register100=original_value)
                recorder.record_event(
                    "setup",
                    "register_snapshot",
                    expected={"http_status": 200, "address": 100},
                    observed={"http_status": 200, "address": 100, "value": original_value},
                )

            yield client, original_value
        finally:
            try:
                if original_value is not None:
                    facts = {
                        "attempted": True,
                        "original_value": original_value,
                        "write_succeeded": False,
                        "readback_verified": False,
                        "success": False,
                    }
                    try:
                        restore_response = client.write(100, original_value)
                        facts["write_status"] = restore_response.status_code
                        assert restore_response.status_code == 200
                        restore_data = restore_response.json()
                        facts.update(
                            write_address=restore_data.get("address"),
                            write_value=restore_data.get("value"),
                        )
                        assert restore_data == {
                            "address": 100,
                            "value": original_value,
                        }
                        facts["write_succeeded"] = True

                        readback_response = client.read(100)
                        facts["readback_status"] = readback_response.status_code
                        assert readback_response.status_code == 200
                        readback_data = readback_response.json()
                        facts.update(
                            readback_address=readback_data.get("address"),
                            readback_value=readback_data.get("value"),
                        )
                        assert readback_data == {
                            "address": 100,
                            "value": original_value,
                        }
                        facts.update(readback_verified=True, success=True)
                    except Exception as error:
                        facts["error"] = exception_details(error)
                        raise
                    finally:
                        _cleanup_evidence(recorder, "register100", **facts)
                        if recorder is not None and "readback_value" in facts:
                            recorder.set_state("after", register100=facts["readback_value"])
                else:
                    _cleanup_evidence(
                        recorder,
                        "register100",
                        attempted=False,
                        success=None,
                        reason="original_value_unavailable",
                    )
            finally:
                facts = {"attempted": True, "success": False}
                try:
                    disconnect_response = client.disconnect()
                    facts["http_status"] = disconnect_response.status_code
                    assert disconnect_response.status_code == 200
                    disconnect_data = disconnect_response.json()
                    facts["connected"] = disconnect_data.get("connected")
                    assert disconnect_data["connected"] is False
                    facts["success"] = True
                except Exception as error:
                    facts["error"] = exception_details(error)
                    raise
                finally:
                    _cleanup_evidence(recorder, "disconnect", **facts)
                    if recorder is not None and "connected" in facts:
                        recorder.set_state("after", connected=facts["connected"])
