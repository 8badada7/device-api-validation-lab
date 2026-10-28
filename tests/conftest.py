import json
import math
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from src.device_api_client import DeviceApiClient


@pytest.fixture(scope="session")
def config():
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "configs" / "test_env.json"
    with config_path.open(encoding="utf-8") as config_file:
        settings = json.load(config_file)

    if not isinstance(settings, dict):
        raise ValueError("Test configuration must be a JSON object")

    base_url = settings.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be a non-empty HTTP URL string")
    parsed_url = urlsplit(base_url)
    if (
        parsed_url.scheme not in ("http", "https")
        or not parsed_url.hostname
        or any(character.isspace() for character in base_url)
    ):
        raise ValueError("base_url must be a valid HTTP URL")
    # Accessing port also rejects malformed or out-of-range URL ports.
    parsed_url.port

    timeout = settings.get("timeout")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
        or not math.isfinite(timeout)
    ):
        raise ValueError("timeout must be a finite number greater than 0")

    return settings


@pytest.fixture
def api_client(config):
    client = DeviceApiClient(config["base_url"], config["timeout"])
    try:
        yield client
    finally:
        client.close()
