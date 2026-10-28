import requests


class DeviceApiClient:
    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def health(self):
        return self.session.get(
            f"{self.base_url}/health", timeout=self.timeout
        )

    def connect(self):
        return self.session.post(
            f"{self.base_url}/connect", timeout=self.timeout
        )

    def disconnect(self):
        return self.session.post(
            f"{self.base_url}/disconnect", timeout=self.timeout
        )

    def read(self, address=None):
        params = {} if address is None else {"address": address}
        return self.session.get(
            f"{self.base_url}/read", params=params, timeout=self.timeout
        )

    def write(self, address=None, value=None):
        payload = {}
        if address is not None:
            payload["address"] = address
        if value is not None:
            payload["value"] = value
        return self.session.post(
            f"{self.base_url}/write", json=payload, timeout=self.timeout
        )

    def close(self):
        self.session.close()
