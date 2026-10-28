from contextlib import closing
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import pytest
import requests

from src.device_api_client import DeviceApiClient


DUT_STARTUP_CODE = """
import sys
import time

from flask import jsonify
from dut.app import app

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
def recovery_dut():
    project_root = Path(__file__).resolve().parents[2]
    dut = RecoveryDut(project_root)
    try:
        yield dut
    finally:
        dut.stop()
