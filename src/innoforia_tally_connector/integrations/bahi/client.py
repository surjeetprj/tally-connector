"""Guarded party GETs and approved, typed customer/supplier POST payloads."""
import json
import time
from threading import local

import httpx

from innoforia_tally_connector.domain.errors import ReadError, ContextMismatch
from innoforia_tally_connector.domain.experiments import TestSupplier, TargetIdentity, UncertainWrite, WriteRejected
from innoforia_tally_connector.integrations.bahi.party_payload import payload as party_payload

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
                    raise ReadError(f"Bahi GET {route} failed (HTTP {response.status_code}); check access and setup")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 8 * 1024 * 1024 or time.monotonic() - started > 15:
                        raise ReadError("Bahi response exceeded read limits")
                result = json.loads(data)
        except httpx.TimeoutException:
            raise ReadError(f"Bahi GET {route} timed out; verify connections and retry the read") from None
        except httpx.ConnectError:
            raise ReadError(f"Bahi GET {route} could not connect securely; check network, HTTPS and server availability") from None
        except httpx.HTTPError:
            raise ReadError(f"Bahi GET {route} transport failed; verify connections and retry the read") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ReadError(f"Bahi GET {route} returned invalid JSON or text encoding; check the API/server response") from None
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

    def create_test_supplier(self, party: TestSupplier, before_send=lambda business: None):
        if not isinstance(party, TestSupplier):
            raise ValueError("Only a validated synthetic supplier can be created")
        return self._post_party({"party_type": "SUPPLIER", "account_name": party.name, "email": party.email}, before_send)

    def create_party(self, draft, before_send):
        return self._post_party(party_payload(draft), before_send)

    def _post_party(self, payload, before_send):
        business = self.business(52)
        before_send(business)
        if self.stopped():
            raise ReadError("Creation stopped before transmission")
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 64 * 1024:
            raise ValueError("Party payload exceeds the documented body limit")
        started = time.monotonic()
        try:
            with self.http.stream("POST", BASE + "api-party.php", json=payload, follow_redirects=False,
                headers={"Authorization": "Bearer " + self._auth.key, "Accept": "application/json"}) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 8 * 1024 * 1024 or time.monotonic() - started > 15:
                        raise UncertainWrite("Create response exceeded limits; do not create again")
                body = json.loads(raw)
                status = response.status_code
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
            raise UncertainWrite("Bahi create outcome is unknown; do not create again") from None
        data = body.get("data") if isinstance(body, dict) else None
        identity = data.get("account_id") if isinstance(data, dict) else None
        target = TargetIdentity(kind="BAHI_ID", identity=str(identity)) if type(identity) is int and identity > 0 else None
        if isinstance(body, dict) and body.get("success") is False and target is None and status in {401, 403, 409, 422}:
            raise WriteRejected(f"Bahi refused creation (HTTP {status}); inspect party:create permission or validation")
        if status != 201 or not isinstance(body, dict) or body.get("success") is not True or target is None:
            raise UncertainWrite("Bahi create response is not authoritative; reconcile through reads", target)
        return target
