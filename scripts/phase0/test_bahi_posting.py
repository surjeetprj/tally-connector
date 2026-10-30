"""Authorized single-record Bahi draft/post test with durable local attempts.

Never uses an uncertain create as permission to create again. No DELETE calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from probe_bahi import BASE, NoRedirect, credential_key

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / ".phase0-runtime/bahi-write/attempts.jsonl"
REFERENCE = "P0CT-261029-01"


def record(event, **values):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    row = {"utc": datetime.now(timezone.utc).isoformat(), "event": event, **values}
    with JOURNAL.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def verify_invoice(data, payload):
    if not isinstance(data, dict) or str(data.get("biz_id")) != "52":
        raise ValueError("Wrong or missing business identity")
    for field in ("invoice_num", "ref_doc_no", "ref_doc_date", "invoice_dt", "txn_type"):
        if data.get(field) != payload[field]:
            raise ValueError(f"Invoice comparison failed: {field}")
    if str(data.get("invoice_cust_id")) != str(payload["invoice_cust_id"]):
        raise ValueError("Supplier comparison failed")
    items = data.get("items")
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("Expected exactly one test line")
    actual, expected = items[0], payload["items"][0]
    if str(actual.get("item_id")) != str(expected["item_id"]):
        raise ValueError("Item comparison failed")
    for field in ("qty", "price", "gst_pct"):
        if Decimal(str(actual[field])) != Decimal(expected[field]):
            raise ValueError(f"Line comparison failed: {field}")
    taxable = Decimal(expected["qty"]) * Decimal(expected["price"])
    if Decimal(str(data["total_amt"])) != taxable:
        raise ValueError("Taxable total comparison failed")
    taxes = sum(Decimal(str(data.get(field, "0"))) for field in ("cgst", "sgst", "igst"))
    if abs(taxes - (taxable * Decimal(expected["gst_pct"]) / 100)) > Decimal("0.01"):
        raise ValueError("Tax total comparison failed")
    if Decimal(str(data["net_amt"])) != taxable + taxes:
        raise ValueError("Net total comparison failed")
    if data.get("invoice_status") not in {"DRAFT", "ACTIVE"}:
        raise ValueError("Unexpected test invoice lifecycle")
    return {"invoice_id": data["invoice_id"], "invoice_num": data["invoice_num"],
            "invoice_status": data["invoice_status"], "taxable": str(taxable),
            "tax": str(taxes), "total": str(data["net_amt"])}


def prior_invoice_id(events):
    ids = {row["invoice_id"] for row in events
           if type(row.get("invoice_id")) is int and row["invoice_id"] > 0}
    if len(ids) > 1:
        raise RuntimeError("Conflicting journal identities; reconcile before further writes")
    uncertain_create = any(row.get("event") == "WRITE_INTENT"
                           and row.get("method") == "POST"
                           and row.get("endpoint") == "api-invoice.php"
                           for row in events)
    if uncertain_create and not ids:
        raise RuntimeError("Prior attempt exists without a resolved ID; no create replay permitted")
    return next(iter(ids)) if ids else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform the authorized test writes")
    args = parser.parse_args()
    if not args.execute:
        print("Use --execute only for the authorized Phase 0 test in business 52.")
        return 0
    key = credential_key()
    opener = build_opener(NoRedirect())

    def call(method, endpoint, payload=None, **params):
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        if method != "GET":
            record("WRITE_INTENT", method=method, endpoint=endpoint,
                   body_sha256=hashlib.sha256(body or b"").hexdigest())
        req = Request(BASE + endpoint + ("?" + urlencode(params) if params else ""),
                      data=body, method=method, headers={"Authorization": "Bearer " + key,
                                                       "Content-Type": "application/json"})
        try:
            response = opener.open(req, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(2_000_001)
            status = response.code
        if len(raw) > 2_000_000:
            raise ValueError("Unexpected response size")
        result = json.loads(raw)
        if method != "GET":
            data = result.get("data", {}) if isinstance(result, dict) else {}
            record("WRITE_RESPONSE", method=method, endpoint=endpoint, http_status=status,
                   invoice_id=data.get("invoice_id") if isinstance(data, dict) else None,
                   response_sha256=hashlib.sha256(raw).hexdigest())
        if status not in {200, 201} or not isinstance(result, dict) or result.get("success") is not True:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            message = str(error.get("message", "Request rejected")).replace(key, "[redacted]")[:500]
            record("REQUEST_REJECTED", method=method, http_status=status,
                   error_code=str(error.get("code", "UNKNOWN"))[:100], message=message)
            raise RuntimeError(f"API rejected {method}: HTTP {status}; {message}")
        return result

    if str(call("GET", "check_api_biz_setup.php")["data"].get("biz_id")) != "52":
        raise ValueError("Key does not match the authorized business")
    supplier = call("GET", "api-party.php", id=274)["data"]
    item = call("GET", "api-item.php", id=84)["data"]
    if supplier.get("party_type") != "SUPPLIER" or supplier.get("is_active") is not True:
        raise ValueError("Expected active supplier 274")
    if str(item.get("biz_id")) != "52" or item.get("avail_status") != "Y":
        raise ValueError("Expected active item 84 in business 52")
    if item.get("tracking_mode") not in {None, "", "NONE"}:
        raise ValueError("Tracked items excluded from the test")
    if item.get("item_type") not in {"GOODS", "SERVICE", "CHARGE"} or not item.get("item_uom"):
        raise ValueError("Expected supported existing item with a unit")
    tax = item
    if item.get("tax_source") == "GROUP":
        tax = call("GET", "api-item-group.php", id=int(item["item_grp_id"]))["data"]
    if Decimal(str(tax.get("cess") or "0")) != 0:
        raise ValueError("Cess excluded from test")
    rate = Decimal(str(tax.get("gst", tax.get("gst_rate", "0"))))
    if not Decimal("0") <= rate <= Decimal("100"):
        raise ValueError("Invalid master tax rate")
    payload = {"txn_type": "PURCHASE", "invoice_dt": "2026-10-29",
               "invoice_num": REFERENCE, "invoice_cust_id": 274,
               "ref_doc_no": REFERENCE, "ref_doc_date": "2026-10-29",
               "note": "Connector Phase 0 authorised test purchase; retain for audit.",
               "round_off": "0.00", "items": [{"item_id": 84, "qty": "1.000",
               "price": "1.00", "gst_pct": str(rate), "discount_mode": "NONE"}]}
    existing_events = [json.loads(line) for line in JOURNAL.read_text().splitlines()] if JOURNAL.exists() else []
    invoice_id = prior_invoice_id(existing_events)
    if invoice_id is None:
        # Explicit duplicate scan precedes the single create, including cancelled records.
        for page in range(1, 101):
            result = call("GET", "api-invoice.php", txn_type="PURCHASE", page=page, limit=200)
            for row in result["data"]:
                if row.get("invoice_num") == REFERENCE or (row.get("ref_doc_no") == REFERENCE
                    and str(row.get("invoice_cust_id")) == "274"):
                    raise RuntimeError("Test reference already exists; explicit reconciliation needed")
            if page >= result["pagination"]["total_pages"]:
                break
        else:
            raise ValueError("Duplicate scan exceeded probe limit")
        record("TEST_PREPARED", payload=payload, initial_item_qty=str(item["avail_qty"]))
        created = call("POST", "api-invoice.php", payload)["data"]
        invoice_id = created.get("invoice_id")
        if not isinstance(invoice_id, int) or invoice_id <= 0:
            raise RuntimeError("Create outcome unknown; no second create permitted")
        record("CREATED_ID", invoice_id=invoice_id)

    before = call("GET", "api-invoice.php", id=invoice_id)["data"]
    verify_invoice(before, payload)
    if before["invoice_status"] == "DRAFT":
        # Exercise DRAFT-only PATCH without changing economic values.
        call("PATCH", "api-invoice.php", {"note": payload["note"]}, id=invoice_id)
        verify_invoice(call("GET", "api-invoice.php", id=invoice_id)["data"], payload)
        call("POST", f"api-invoice.php/{invoice_id}/post")
        # Intentionally do not use the successful POST body as completion evidence.
        record("POST_BODY_DISCARDED", invoice_id=invoice_id,
               purpose="Known-ID read reconciliation; not a real network-timeout simulation")
    active = call("GET", "api-invoice.php", id=invoice_id)["data"]
    verify_invoice(active, payload)
    if active["invoice_status"] != "ACTIVE":
        raise ValueError("Posting not confirmed ACTIVE")
    after_first = call("GET", "api-item.php", id=84)["data"]
    expected_delta = Decimal("1") if item["item_type"] == "GOODS" and before["invoice_status"] == "DRAFT" else Decimal("0")
    if Decimal(str(after_first["avail_qty"])) - Decimal(str(item["avail_qty"])) != expected_delta:
        raise ValueError("Unexpected stock effect for the item type; investigate")
    repeated = call("POST", f"api-invoice.php/{invoice_id}/post")["data"]
    if repeated.get("invoice_id") != invoice_id or repeated.get("invoice_status") != "ACTIVE":
        raise ValueError("Repeat-post identity/status mismatch")
    after_repeat = call("GET", "api-item.php", id=84)["data"]
    if Decimal(str(after_first["avail_qty"])) != Decimal(str(after_repeat["avail_qty"])):
        raise ValueError("Stock changed across repeat post; investigate before more writes")
    final = verify_invoice(call("GET", "api-invoice.php", id=invoice_id)["data"], payload)
    result = {"business_id": 52, "test_reference": REFERENCE, "confirmed": final,
              "supplier_id": 274, "item_id": 84, "quantity": "1.000", "price": "1.00",
              "item_type": item["item_type"], "stock_movement_expected": item["item_type"] == "GOODS",
              "item_qty_before": str(item["avail_qty"]),
              "item_qty_after_first_post": str(after_first["avail_qty"]),
              "item_qty_after_repeat": str(after_repeat["avail_qty"]),
              "repeat_post_stock_unchanged": True, "deletion_or_reversal_performed": False,
              "read_reconciliation_after_discarded_body": True,
              "real_timeout_or_crash_simulated": False}
    record("TEST_COMPLETED", invoice_id=invoice_id, result=result)
    output = ROOT / "docs/api/bahi/evidence/controlled-post.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        record("STOPPED", error_type=type(error).__name__)
        print(f"Stopped: {type(error).__name__}: {error}")
        raise SystemExit(1)
