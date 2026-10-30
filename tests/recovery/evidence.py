"""Small JSON evidence records for tests that explicitly request them."""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _safe_json(value):
    """Copy JSON values, reject unsupported values, and redact sensitive keys."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Evidence numbers must be finite")
        return value
    if type(value) is list:
        return [_safe_json(item) for item in value]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Evidence object keys must be strings")
            safe_item = _safe_json(item)
            normalized_key = "".join(char for char in key.casefold() if char.isalnum())
            sensitive = any(
                part in normalized_key
                for part in (
                    "header", "token", "password", "passwd", "secret",
                    "credential", "auth", "proxy", "proxies", "cookie",
                    "apikey", "accesskey", "privatekey",
                )
            )
            result[key] = "[REDACTED]" if sensitive else safe_item
        return result
    raise TypeError("Evidence must contain only JSON values")


def exception_details(error):
    """Describe errors without messages, reprs, full paths, or tracebacks."""
    if not isinstance(error, BaseException):
        raise TypeError("error must be an exception")

    seen = set()

    def describe(current, depth):
        details = {"exception_type": type(current).__name__}
        traceback = current.__traceback__
        if traceback is not None:
            while traceback.tb_next is not None:
                traceback = traceback.tb_next
            filename = traceback.tb_frame.f_code.co_filename
            details["location"] = {
                "file": filename.replace("\\", "/").rsplit("/", 1)[-1],
                "line": traceback.tb_lineno,
            }

        if id(current) in seen or depth >= 2:
            return details
        seen.add(id(current))

        if current.__cause__ is not None:
            details["cause"] = describe(current.__cause__, depth + 1)
        elif current.__context__ is not None and not current.__suppress_context__:
            details["context"] = describe(current.__context__, depth + 1)

        if isinstance(current, BaseExceptionGroup):
            details["children"] = [
                describe(child, depth + 1) for child in current.exceptions[:3]
            ]
        return details

    return describe(error, 0)


class EvidenceRecorder:
    def __init__(self, nodeid):
        if not isinstance(nodeid, str) or not nodeid:
            raise ValueError("nodeid must be a non-empty string")
        self._nodeid = nodeid
        self._run_id = str(uuid4())
        self._started_at_utc = _utc_now()
        self._finished_at_utc = None
        self._events = []
        self._states = {"before": {}, "after": {}}
        self._cleanup_status = {}
        self._phases = {"setup": None, "call": None, "teardown": None}
        self._written_path = None

    def _ensure_writable(self):
        if self._written_path is not None:
            raise RuntimeError("Evidence has already been written")

    def record_event(self, stage, event_type, expected=None, observed=None):
        self._ensure_writable()
        if not isinstance(stage, str) or not stage:
            raise ValueError("stage must be a non-empty string")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        self._events.append(_safe_json({
            "timestamp_utc": _utc_now(),
            "stage": stage,
            "event_type": event_type,
            "expected": expected,
            "observed": observed,
        }))

    def set_state(self, moment, **facts):
        self._ensure_writable()
        if moment not in self._states:
            raise ValueError("moment must be before or after")
        self._states[moment].update(_safe_json(facts))

    def record_cleanup(self, name, **facts):
        self._ensure_writable()
        if not isinstance(name, str) or not name:
            raise ValueError("cleanup name must be a non-empty string")
        component = self._cleanup_status.setdefault(name, {})
        component.update(_safe_json(facts))
        self.record_event(
            "cleanup", "cleanup",
            observed={"component": name, "facts": component},
        )

    def record_phase(self, when, outcome, duration, error=None, *, start=None, stop=None):
        self._ensure_writable()
        if when not in self._phases:
            raise ValueError("Unknown pytest phase")
        if outcome not in ("passed", "failed", "skipped"):
            raise ValueError("Unknown pytest outcome")
        if type(duration) not in (int, float) or duration < 0:
            raise ValueError("duration must be a non-negative number")
        phase = {
            "outcome": outcome,
            "duration": duration,
            "error": None if error is None else exception_details(error),
            "started_at_utc": None if start is None else datetime.fromtimestamp(
                start, timezone.utc
            ).isoformat(timespec="microseconds"),
            "finished_at_utc": None if stop is None else datetime.fromtimestamp(
                stop, timezone.utc
            ).isoformat(timespec="microseconds"),
        }
        self._phases[when] = _safe_json(phase)
        if when == "setup" and phase["started_at_utc"] is not None:
            self._started_at_utc = phase["started_at_utc"]
        if when == "teardown" and phase["finished_at_utc"] is not None:
            self._finished_at_utc = phase["finished_at_utc"]

    def _status(self):
        setup, call, teardown = (self._phases[name] for name in self._phases)
        complete = (
            setup is not None
            and teardown is not None
            and (call is not None or setup["outcome"] in ("failed", "skipped"))
        )
        if any(phase and phase["outcome"] == "failed" for phase in (setup, teardown)):
            return "ERROR", complete
        if call and call["outcome"] == "failed":
            return "FAILED", complete
        if not complete:
            return "INCOMPLETE", False
        if any(phase and phase["outcome"] == "skipped" for phase in (setup, call, teardown)):
            return "SKIPPED", True
        if all(phase and phase["outcome"] == "passed" for phase in (setup, call, teardown)):
            return "PASSED", True
        return "INCOMPLETE", False

    def to_dict(self):
        final_status, reports_complete = self._status()
        return _safe_json({
            "schema_version": 1,
            "run_id": self._run_id,
            "nodeid": self._nodeid,
            "started_at_utc": self._started_at_utc,
            "finished_at_utc": self._finished_at_utc,
            "events": self._events,
            "state_before": self._states["before"],
            "state_after": self._states["after"],
            "cleanup_status": self._cleanup_status,
            "phases": self._phases,
            "final_status": final_status,
            "reports_complete": reports_complete,
        })

    def finish_and_write(self, directory):
        self._ensure_writable()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if self._finished_at_utc is None:
            self._finished_at_utc = _utc_now()
        content = json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False,
        ) + "\n"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = directory / f"{timestamp}_{self._run_id}.json"
        temporary_path = None
        reserved = False
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=directory,
                prefix=f".{target.stem}-", suffix=".tmp", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())

            # Exclusive creation protects any existing file; replace only our reservation.
            with target.open("x", encoding="utf-8"):
                pass
            reserved = True
            temporary_path.replace(target)
            temporary_path = None
            self._written_path = target
            return target
        except BaseException:
            for owned_path in (temporary_path, target if reserved else None):
                if owned_path is not None:
                    try:
                        owned_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
