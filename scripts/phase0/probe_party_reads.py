"""Opt-in export-only party contract experiment; no raw customer data retained."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from innoforia_tally_connector.integrations.tally.gateway import Gateway
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import records


def main():
    gateway = Gateway()
    result = {"utc": datetime.now(timezone.utc).isoformat(), "export_only": True}
    try:
        gateway.read()
        groups = gateway.read("Group")
        ledgers = gateway.read("Ledger")
        result["company_guid_matched"] = True
        result["group_count"] = len(groups)
        result["ledger_count"] = len(ledgers)
        result["ledger_fields"] = sorted(set().union(*(set(r) for r in ledgers)))
        result["group_fields"] = sorted(set().union(*(set(r) for r in groups)))
        result["group_parents_resolved"] = all(not g.get("PARENT") or g["PARENT"] in {r["NAME"] for r in groups}
                                                or g["PARENT"] == "Primary" for g in groups)
        checks = []
        for ledger in ledgers:
            found = gateway.read("Ledger", guid=ledger["GUID"])
            checks.append(len(found) == 1 and found[0] == ledger)
        result["guid_detail_checks"] = len(checks)
        result["guid_detail_matches"] = all(checks)
        result["missing_guid_returns_empty"] = gateway.read("Ledger", guid=str(uuid4()) + "-ffffffff") == []
        raw = gateway.transport.export(collection("Ledger", "Connector Missing Company " + str(uuid4())))
        try:
            invalid = records(raw, "Ledger")
            result["invalid_company_returned_count"] = len(invalid)
        except ValueError:
            result["invalid_company_rejected"] = True
        result["invalid_response_sha256"] = hashlib.sha256(raw).hexdigest()
        result["renamed_live_record"] = "not tested: no mutations authorized"
        target = Path("docs/api/tally/evidence/party-read-probes.json")
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        gateway.close()


if __name__ == "__main__":
    main()
