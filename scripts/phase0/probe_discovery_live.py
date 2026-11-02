"""Read-only adapter check; experimental roots do not confirm a business policy."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from innoforia_tally_connector.domain.masters import Binding, Classification
from innoforia_tally_connector.host.windows.credentials import read_key
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader as BahiReader
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader as TallyReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-output", type=Path,
                        default=Path("docs/master-sync/evidence/live-discovery-reads.json"))
    args = parser.parse_args()
    client, gateway = Client(read_key), Gateway()
    try:
        binding = Binding(id="read-only-probe", business_id=52, company_guid=COMPANY_GUID, generation=1)
        groups = gateway.read("Group")
        roots = {r["NAME"]: r["GUID"] for r in groups}
        classification = Classification(customer_root=roots["Sundry Debtors"], supplier_root=roots["Sundry Creditors"])
        result = {"utc": datetime.now(timezone.utc).isoformat(), "remote_mutations": 0,
            "classification": "Experimental standard group roots; not a confirmed business mapping",
            "sides": {}}
        for side, reader in (("BAHI", BahiReader(client)), ("TALLY", TallyReader(gateway, classification))):
            scan = reader.scan(binding)
            matches = [reader.detail(binding, row.identity).comparison() == row.comparison() for row in scan.records]
            result["sides"][side] = dict(records=len(scan.records), pages=list(scan.pages_read),
                coverage_complete=scan.coverage_complete, stable_snapshot=scan.stable_snapshot,
                issues=len(scan.issues), detail_checks=len(matches), details_match=all(matches))
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        client.close()
        gateway.close()


if __name__ == "__main__":
    main()
