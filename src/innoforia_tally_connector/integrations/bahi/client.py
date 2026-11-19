"""Guarded party reads and approved, typed customer/supplier creates and updates."""
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

    def update_party(self, identity, expected, values, before_send):
        """Apply approved nonempty party scalars to a known account.

        The caller owns durable intent/attempt recording; there is no retry.
        This does not expose arbitrary PATCH, deletion or invoice routes.
        """
        from innoforia_tally_connector.domain.party_transfer import PartyDraft
        from innoforia_tally_connector.domain.masters import PartyType
        from innoforia_tally_connector.integrations.bahi.party_payload import validate
        if not identity.isdecimal() or str(int(identity)) != identity or int(identity)<=0:
            raise ValueError('A canonical account ID is required')
        if not values or set(values)-{'email','phone','address','state','country','pincode','gstin','pan','gst_reg_type'} or any(not isinstance(v,str) or not v for v in values.values()):
            raise ValueError('Only supported nonempty linked-party fields may be updated')
        business=self.business(52)
        current=self.get('api-party.php',{'id':identity})['data']
        if current!=expected or str(current.get('account_id'))!=identity or current.get('is_active') is not True:
            raise ContextMismatch('Bahi party changed or is inactive; no update sent')
        validation_values = dict(values)
        if values.get('gstin') and 'gst_reg_type' not in values:
            validation_values['gst_reg_type'] = current.get('gst_reg_type')
        draft=PartyDraft(name=current['account_name'],party_type=PartyType(current['party_type']), **validation_values)
        if validate(draft): raise ValueError('Party update does not satisfy Bahi validation')
        if len(json.dumps(values, ensure_ascii=False).encode()) > 64 * 1024:
            raise ValueError('Party payload exceeds the documented body limit')
        before_send(business)  # Caller has recorded the exact one-attempt intent.
        if self.stopped(): raise ReadError('Update stopped before transmission')
        target=TargetIdentity(kind='BAHI_ID',identity=identity)
        try:
            with self.http.stream('PATCH',BASE+'api-party.php',params={'id':identity},json=values,follow_redirects=False,
                headers={'Authorization':'Bearer '+self._auth.key,'Accept':'application/json'}) as response:
                raw=bytearray();started=time.monotonic()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>8*1024*1024 or time.monotonic()-started>15:
                        raise UncertainWrite('Party update response exceeded limits; reads only',target)
                body=json.loads(raw);status=response.status_code
        except (httpx.HTTPError,json.JSONDecodeError,UnicodeDecodeError):
            raise UncertainWrite('Party update outcome uncertain; verify known account ID, never resend',target) from None
        if isinstance(body,dict) and body.get('success') is False and status in {401,403,409,422}:
            raise WriteRejected(f'Bahi refused party update (HTTP {status}); check party:update permission')
        if status!=200 or not isinstance(body,dict) or body.get('success') is not True:
            raise UncertainWrite('Party update needs known-ID read-back',target)
        return target

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
