"""Only the two documented GET routes used by party discovery are enabled."""
import json
import time
from threading import local

import httpx

from innoforia_tally_connector.domain.errors import ReadError, ContextMismatch

BASE = "https://innoforia.com/201/h-bahi/bahi/web-api/"


class Client:
    def __init__(self, credential, client=None, stopped=lambda: False):
        self.credential = credential
        self.http = client or httpx.Client(timeout=15, follow_redirects=False)
        self.stopped = stopped
        self._auth = local()

    def get(self, route, params=None):
        if self.stopped():
            raise ReadError("Bahi read stopped during shutdown")
        if route not in {"check_api_biz_setup.php", "api-party.php"}:
            raise ReadError("Only business and party reads are enabled")
        started = time.monotonic()
        key = getattr(self._auth, "key", None)
        if key is None:
            raise ContextMismatch("Verify the authenticated business before reading parties")
        try:
            with self.http.stream("GET", BASE + route, params=params,
                                  follow_redirects=False,
                                  headers={"Authorization": "Bearer " + key,
                                           "Accept": "application/json"}) as response:
                if response.status_code != 200:
                    raise ReadError(f"Bahi read failed (HTTP {response.status_code}); check access and setup")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 8 * 1024 * 1024 or time.monotonic() - started > 15:
                        raise ReadError("Bahi response exceeded read limits")
                result = json.loads(data)
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
            raise ReadError("Bahi is unavailable or returned an invalid response") from None
        if not isinstance(result, dict) or result.get("success") is not True or "data" not in result:
            raise ReadError("Bahi rejected the read; check credentials, scopes and party group setup")
        return result

    def business(self, expected=52):
        if expected != 52:
            raise ContextMismatch("This discovery profile requires Bahi business 52")
        # Freeze credentials across this logical scan/detail operation. A key
        # replacement in Credential Manager must not change tenancy mid-scan.
        self._auth.key = self.credential()
        try:
            row = self.get("check_api_biz_setup.php")["data"]
        except Exception:
            self._auth.key = None
            raise
        if (not isinstance(row, dict) or type(row.get("biz_id")) is not int
                or row["biz_id"] != expected or not isinstance(row.get("biz_name"), str)
                or not row["biz_name"].strip()):
            self._auth.key = None
            raise ContextMismatch("Authenticated Bahi business does not match business 52")
        return row

    def close(self):
        self._auth.key = None
        self.http.close()
