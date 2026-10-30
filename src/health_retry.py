"""Bounded retries for read-only HTTP health checks only."""

import math
import time

import requests


def _validate_seconds(name, value, *, allow_zero):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    try:
        seconds = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(seconds) or seconds < 0 or (not allow_zero and seconds == 0):
        bound = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {bound}")
    return seconds


def check_health_with_retry(
    session,
    url,
    *,
    max_attempts=3,
    timeout=1,
    retry_interval=0.2,
    on_attempt=None,
):
    """GET a health URL using a caller-owned Session without transport retries.

    Only HTTP 503, ConnectionError and ReadTimeout are retryable. HTTP 200
    requires exactly {"status": "ok"}; invalid JSON or other content stops.
    Redirects are disabled. This function never restarts or connects a device.
    Use a Session with adapter retries disabled; otherwise the attempt limit
    counts session.get calls rather than underlying network requests.

    The returned dictionary contains success, attempts_used, max_attempts,
    stop_reason and history. Stop reasons are success (first attempt), recovered
    (later success), attempts_exhausted, and non_retryable_response.
    Each history entry contains attempt_number, outcome (healthy,
    http_response, invalid_health_response, or exception), http_status,
    exception_type, retryable and will_retry. Inapplicable fields are None.
    Exception names are actual types; messages and response bodies are omitted.

    on_attempt receives a copy after each completed attempt, before any wait.
    will_retry is the decision to continue; a later history entry proves that
    the next request occurred. Callback errors propagate and interrupt retries.
    The caller owns the Session and must close it; responses are closed here.
    """
    if type(max_attempts) is not int or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer, not bool")
    timeout = _validate_seconds("timeout", timeout, allow_zero=False)
    retry_interval = _validate_seconds("retry_interval", retry_interval, allow_zero=True)
    if on_attempt is not None and not callable(on_attempt):
        raise TypeError("on_attempt must be callable or None")

    history = []
    for number in range(1, max_attempts + 1):
        attempt = {
            "attempt_number": number,
            "outcome": "http_response",
            "http_status": None,
            "exception_type": None,
            "retryable": False,
            "will_retry": False,
        }
        try:
            with session.get(url, timeout=timeout, allow_redirects=False) as response:
                attempt["http_status"] = response.status_code
                if response.status_code == 200:
                    try:
                        healthy = response.json() == {"status": "ok"}
                    except requests.exceptions.JSONDecodeError as error:
                        healthy = False
                        attempt["exception_type"] = type(error).__name__
                    attempt["outcome"] = "healthy" if healthy else "invalid_health_response"
                else:
                    attempt["retryable"] = response.status_code == 503
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as error:
            attempt.update(
                outcome="exception",
                exception_type=type(error).__name__,
                retryable=True,
            )

        success = attempt["outcome"] == "healthy"
        attempt["will_retry"] = attempt["retryable"] and number < max_attempts
        history.append(attempt)
        if on_attempt is not None:
            on_attempt(attempt.copy())

        if success:
            stop_reason = "success" if number == 1 else "recovered"
        elif not attempt["retryable"]:
            stop_reason = "non_retryable_response"
        elif not attempt["will_retry"]:
            stop_reason = "attempts_exhausted"
        else:
            time.sleep(retry_interval)
            continue

        return {
            "success": success,
            "attempts_used": number,
            "max_attempts": max_attempts,
            "stop_reason": stop_reason,
            "history": history,
        }
