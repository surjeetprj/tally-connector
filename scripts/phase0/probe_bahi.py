"""Read-only Bahi contract checks; credentials never enter output or files."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from store_bahi_key import Credential, REFERENCE

BASE = "https://innoforia.com/201/h-bahi/bahi/web-api/"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def credential_key() -> str:
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    row = ctypes.POINTER(Credential)()
    if not api.CredReadW(REFERENCE, 1, 0, ctypes.byref(row)):
        raise RuntimeError("Credential unavailable")
    try:
        return ctypes.string_at(row.contents.CredentialBlob,
                                row.contents.CredentialBlobSize).decode("utf-8")
    finally:
        api.CredFree(row)


def shape(record: dict) -> dict:
    return {key: type(value).__name__ for key, value in sorted(record.items())}


def summary(record: dict, invoice=False) -> dict:
    result = {"field_types": shape(record)}
    if invoice:
        result["invoice_status_present"] = "invoice_status" in record
        state = record.get("invoice_status")
        result["invoice_status"] = state if isinstance(state, str) and state in {"DRAFT", "ACTIVE", "CANCELLED", "VOID"} else "missing_or_unrecognized"
        items = record.get("items")
        result["items_present"] = isinstance(items, list)
        if isinstance(items, list):
            result["item_count"] = len(items)
            result["first_item_field_types"] = shape(items[0]) if items and isinstance(items[0], dict) else {}
    return result


def safe_code(body: dict) -> str:
    value = body.get("error", {})
    code = value.get("code", "") if isinstance(value, dict) else ""
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", code) else "UNCLASSIFIED"


def main() -> int:
    output = Path(__file__).resolve().parents[2] / "docs/api/bahi/evidence"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        key = credential_key()
    except (OSError, RuntimeError, UnicodeError):
        print("Credential unavailable; API was not contacted.")
        return 1
    opener = build_opener(NoRedirect())

    def get(endpoint: str, **params):
        row = {"utc": datetime.now(timezone.utc).isoformat(), "method": "GET",
               "endpoint": endpoint, "query": params}
        results.append(row)
        url = BASE + endpoint + ("?" + urlencode(params) if params else "")
        try:
            request = Request(url, method="GET", headers={
                "Authorization": "Bearer " + key, "Accept": "application/json"})
            try:
                response = opener.open(request, timeout=20)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(2_000_001)
                row["http_status"] = response.code
            if len(raw) > 2_000_000:
                row["outcome"] = "response_too_large"
                return None
            row["response_bytes"] = len(raw)
            row["response_sha256"] = hashlib.sha256(raw).hexdigest()
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                row["outcome"] = "non_json"
                return None
            if not isinstance(body, dict):
                row["outcome"] = "invalid_envelope"
                return None
            if row["http_status"] != 200 or body.get("success") is not True:
                row.update(outcome="api_error", error_code=safe_code(body))
                return None
            row["outcome"] = "read_ok"
            return body
        except (URLError, TimeoutError, OSError):
            row["outcome"] = "network_error"
            return None

    body = get("check_api_biz_setup.php")
    identity = body.get("data") if body else None
    verified = isinstance(identity, dict) and str(identity.get("biz_id")) == "52"
    if verified:
        results[-1]["business"] = {"biz_id": identity["biz_id"],
                                   "expected_business_matched": True}
    else:
        results[-1]["expected_business_matched"] = False

    if verified:
        for endpoint, id_field, filters in (
            ("api-party.php", "account_id", {"type": "SUPPLIER"}),
            ("api-item-group.php", "grp_id", {}),
            ("api-item.php", "item_id", {}),
            ("api-invoice.php", "invoice_id", {"txn_type": "PURCHASE"}),
        ):
            ids = set()
            first_id = None
            for page in range(1, 101):
                body = get(endpoint, page=page, limit=200, **filters)
                if body is None:
                    break
                records = body.get("data")
                pagination = body.get("pagination")
                if not isinstance(records, list) or not isinstance(pagination, dict):
                    results[-1]["outcome"] = "invalid_list_contract"
                    break
                results[-1]["record_count"] = len(records)
                results[-1]["first_record"] = summary(records[0], endpoint == "api-invoice.php") if records and isinstance(records[0], dict) else None
                results[-1]["pagination"] = {name: value for name, value in pagination.items()
                                            if name in {"page", "limit", "total", "total_pages"}
                                            and isinstance(value, int)}
                page_ids = [str(record.get(id_field, "")) for record in records if isinstance(record, dict)]
                if len(page_ids) != len(records) or any(not value.isdigit() or int(value) <= 0 for value in page_ids):
                    results[-1]["outcome"] = "invalid_record_identity"
                    break
                if len(set(page_ids)) != len(page_ids) or ids.intersection(page_ids):
                    results[-1]["outcome"] = "repeated_pagination_identity"
                    break
                ids.update(page_ids)
                if page_ids and first_id is None:
                    first_id = int(page_ids[0])
                total_pages = pagination.get("total_pages")
                if isinstance(total_pages, bool) or not isinstance(total_pages, int) or total_pages < 0:
                    results[-1]["outcome"] = "invalid_pagination_contract"
                    break
                if not records or page >= total_pages:
                    break
            else:
                results[-1]["outcome"] = "probe_page_limit"
            if first_id is not None:
                body = get(endpoint, id=first_id)
                record = body.get("data") if body else None
                if isinstance(record, dict):
                    results[-1]["record"] = summary(record, endpoint == "api-invoice.php")
                elif body is not None:
                    results[-1]["outcome"] = "invalid_detail_contract"
    # Retain contract shape/aggregate evidence only, never payload values or key.
    document = {"base_url": BASE, "read_only": True, "business_verified": verified,
                "requests": results}
    (output / "read-only-probes.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8")
    for row in results:
        print(json.dumps(row))
    return 0 if verified and all(row["outcome"] == "read_ok" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
