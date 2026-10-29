"""Small standard-library client used by reproducible local demonstration scripts."""

from __future__ import annotations
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def accounts():
    value = json.loads((ROOT / ".local" / "accounts.json").read_text())
    if isinstance(value, dict) and "accounts" in value:
        value = value["accounts"]
    if isinstance(value, list):
        return {row["role"]: row for row in value}
    return value


class Client:
    def __init__(self, base="http://127.0.0.1:8000"):
        self.base = base
        self.csrf = None
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def login(self, role):
        row = accounts()[role]
        response = self.request(
            "POST", "/auth/login", {"username": row.get("username", role), "password": row["password"]}
        )
        self.csrf = response["csrf"]
        return response

    def request(self, method, path, data=None, *, key=None, filename=None, raw=None, binary=False):
        headers = {"Origin": self.base}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if method != "GET":
            headers["Idempotency-Key"] = key or str(uuid.uuid4())
        if filename:
            boundary = "boreal-" + uuid.uuid4().hex
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
            body = (
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                    "Content-Type: application/octet-stream\r\n\r\n"
                ).encode()
                + raw
                + f"\r\n--{boundary}--\r\n".encode()
            )
        elif data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode()
        else:
            body = None
        request = urllib.request.Request(self.base + "/api" + path, data=body, headers=headers, method=method)
        with self.opener.open(request, timeout=120) as response:
            result = response.read()
            return result if binary else json.loads(result)

    def wait(self, job_id, timeout=180):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            result = self.request("GET", "/jobs/" + str(job_id))
            if result["status"] == "succeeded":
                return result
            if result["status"] == "failed":
                raise RuntimeError(f"Job failed: {result.get('error')}")
            time.sleep(0.25)
        raise TimeoutError(f"Job {job_id} did not finish in {timeout}s")
