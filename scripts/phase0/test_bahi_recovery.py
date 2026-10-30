"""Known-ID post acknowledgment crash window on the existing Phase 0 test only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, build_opener

from probe_bahi import BASE, NoRedirect, credential_key

ROOT = Path(__file__).resolve().parents[2]
INTENT = ROOT / ".phase0-runtime/bahi-write/recovery-intent.json"


def persist(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(body, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("interrupted-post", "recover"))
    args = parser.parse_args()
    key = credential_key()
    opener = build_opener(NoRedirect())
    proof = json.loads((ROOT / "docs/api/bahi/evidence/controlled-post.json").read_text())
    invoice_id = proof["confirmed"]["invoice_id"]

    def call(method, endpoint):
        req = Request(BASE + endpoint, method=method,
                      headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
        with opener.open(req, timeout=30) as response:
            body = json.loads(response.read(2_000_000))
        if body.get("success") is not True:
            raise ValueError("Request not confirmed")
        return body["data"]

    if str(call("GET", "check_api_biz_setup.php").get("biz_id")) != "52":
        raise ValueError("Business mismatch")
    remote = call("GET", f"api-invoice.php?id={invoice_id}")
    if (remote.get("invoice_num") != proof["test_reference"]
            or remote.get("invoice_status") != "ACTIVE" or str(remote.get("biz_id")) != "52"):
        raise ValueError("Known test identity/status mismatch")
    if args.mode == "interrupted-post":
        if INTENT.exists():
            raise ValueError("Existing recovery intent; use recover, not another interruption")
        persist(INTENT, {"utc": datetime.now(timezone.utc).isoformat(),
                         "invoice_id": invoice_id, "business_id": 52,
                         "state": "APPLYING", "method": "POST", "test_reference": proof["test_reference"]})
        call("POST", f"api-invoice.php/{invoice_id}/post")
        # Deliberate hard exit after the server response, before local result
        # persistence. This is a repeated known-ID post, not another creation.
        os._exit(23)

    intent = json.loads(INTENT.read_text())
    if intent.get("state") != "APPLYING" or intent.get("invoice_id") != invoice_id:
        raise ValueError("Expected unresolved attempt for this test invoice")
    item = call("GET", "api-item.php?id=84")
    result = {"business_id": 52, "invoice_id": invoice_id,
              "invoice_status": remote["invoice_status"], "test_reference": proof["test_reference"],
              "unresolved_intent_found": True, "recovered_via_get_only": True,
              "recovery_creates": 0, "recovery_posts": 0,
              "item_quantity": str(item["avail_qty"]),
              "stock_unchanged": str(item["avail_qty"]) == proof["item_qty_after_repeat"],
              "scope": "Client exit after repeated known-ID post, before local acknowledgment",
              "server_crash_or_unknown_create_tested": False}
    if not result["stock_unchanged"]:
        raise ValueError("Unexpected stock change")
    persist(ROOT / "docs/api/bahi/evidence/controlled-recovery.json", result)
    persist(INTENT.with_name("recovery-resolution.json"), {"state": "SUCCEEDED", **result})
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
