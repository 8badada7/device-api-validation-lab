"""Run the existing suite with a supervised 8000 DUT; Recovery owns 18001."""

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_URL = "http://127.0.0.1:8000/health"
STARTUP_TIMEOUT = 15
MAX_HEALTH_ATTEMPTS = 60


def ensure_port_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            raise RuntimeError("Port 8000 is occupied; no existing process was stopped")


def wait_until_ready(process):
    deadline = time.monotonic() + STARTUP_TIMEOUT
    last_observation = "No health response received"
    with requests.Session() as session:
        session.trust_env = False
        for attempt in range(1, MAX_HEALTH_ATTEMPTS + 1):
            if process.poll() is not None:
                raise RuntimeError(
                    f"DUT exited before readiness, exit code {process.returncode}"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                with session.get(
                    HEALTH_URL,
                    timeout=min(0.5, remaining),
                    allow_redirects=False,
                ) as response:
                    last_observation = f"HTTP {response.status_code}"
                    if response.status_code == 200:
                        try:
                            healthy = response.json() == {"status": "ok"}
                        except requests.exceptions.JSONDecodeError:
                            healthy = False
                            last_observation = "HTTP 200 with invalid JSON"
                        else:
                            if not healthy:
                                last_observation = "HTTP 200 with unexpected health JSON"
                        if healthy:
                            if process.poll() is not None:
                                raise RuntimeError("DUT exited during readiness check")
                            print(f"DUT ready after {attempt} health probe(s)", flush=True)
                            return
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as error:
                last_observation = type(error).__name__
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.2, remaining))
    raise RuntimeError(
        f"DUT readiness failed within {STARTUP_TIMEOUT}s / "
        f"{MAX_HEALTH_ATTEMPTS} probes: {last_observation}"
    )


def stop_dut(process):
    # Only this Popen's child is eligible for termination; never search by name.
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    else:
        process.wait(timeout=5)
    if process.poll() is None:
        raise RuntimeError("CI DUT did not exit")
    print(f"CI DUT PID {process.pid} exited: {process.returncode}", flush=True)


def show_log_tail(log_path):
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
    except OSError as error:
        print(f"Could not read DUT log ({type(error).__name__})", flush=True)
    else:
        print("--- logs/ci_dut.log (last 8000 characters) ---", flush=True)
        print(tail if tail else "DUT log is empty", flush=True)


def terminate_requested(signum, _frame):
    # A normal SIGTERM still unwinds finally; a forced kill cannot do so.
    raise SystemExit(128 + signum)


def main():
    log_path = PROJECT_ROOT / "logs" / "ci_dut.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "reports").mkdir(parents=True, exist_ok=True)
    pid_path = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / (
        f"device-api-validation-ci-dut-{os.getpid()}.pid"
    )
    process = None
    exit_code = 1
    try:
        with log_path.open("wb", buffering=0) as log_file:
            try:
                ensure_port_free()
                process = subprocess.Popen(
                    [sys.executable, "-u", "dut/app.py"],
                    cwd=PROJECT_ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                # Diagnostic PID record; cleanup uses the owned Popen, not this file.
                with pid_path.open("x", encoding="ascii") as pid_file:
                    pid_file.write(f"{process.pid}\n")
                print(f"Started CI DUT PID {process.pid}; PID saved in {pid_path}", flush=True)
                wait_until_ready(process)
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "--junitxml=reports/pytest-results.xml",
                    ],
                    cwd=PROJECT_ROOT,
                    check=False,
                )
                exit_code = completed.returncode
            finally:
                if process is not None:
                    try:
                        stop_dut(process)
                    except Exception as error:
                        print(
                            f"::error::CI DUT cleanup failed ({type(error).__name__}): {error}",
                            flush=True,
                        )
                        if exit_code == 0:
                            exit_code = 1
    except Exception as error:
        print(f"::error::CI run failed ({type(error).__name__}): {error}", flush=True)
        if exit_code == 0:
            exit_code = 1
    finally:
        if exit_code != 0:
            show_log_tail(log_path)
    return exit_code


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate_requested)
    raise SystemExit(main())
