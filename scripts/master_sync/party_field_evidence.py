"""Owner-invoked, read-only field evidence. Never posts/imports or saves party values."""
import argparse
from collections import Counter
import json
from pathlib import Path

from innoforia_tally_connector.domain.masters import Binding, Classification, PartyContent
from innoforia_tally_connector.host.windows.credentials import read_key
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader as BahiReader
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader as TallyReader
from innoforia_tally_connector.integrations.tally.xml_codec import parse


def xml_shapes(raw):
    root = parse(raw)
    counts = Counter()
    def visit(node, parent=""):
        if not isinstance(node.tag, str):
            return
        path = parent + "/" + node.tag
        counts[path] += 1
        for child in node:
            visit(child, path)
    visit(root)
    return {"mode": "offline XML shape inspection", "paths": dict(sorted(counts.items())),
            "values_retained": False, "note": "Paths/counts only; this does not verify field meanings or create/read-back"}


def availability(observation):
    return {"mode": "explicit live detail read", "side": str(observation.side), "content_schema": observation.content_schema,
            "system_flag": "unavailable" if observation.is_system is None else "reported system" if observation.is_system else "reported normal",
            "fields": {field: "unavailable" if field in observation.unavailable_fields else
                "absent" if field not in observation.content.model_fields_set else
                "null" if getattr(observation.content, field) is None else
                "empty" if getattr(observation.content, field) == "" else "present"
                for field in PartyContent.model_fields}, "values_retained": False,
            "note": "Read-only field availability; not permission or write compatibility evidence"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--xml-file", type=Path, help="Inspect a ledger XML export supplied by the owner; offline")
    sources.add_argument("--bahi-id", help="Read one existing party by account ID; requires --live-read")
    sources.add_argument("--tally-guid", help="Read one existing ledger by GUID; requires --live-read")
    parser.add_argument("--live-read", action="store_true", help="Explicitly opt in to GET/export requests only")
    parser.add_argument("--output", type=Path, default=Path("build/party-field-evidence.json"))
    args = parser.parse_args()
    if args.xml_file:
        if args.xml_file.stat().st_size > 8 * 1024 * 1024:
            parser.error("XML input exceeds the 8 MiB limit")
        evidence = xml_shapes(args.xml_file.read_bytes())
    else:
        if not args.live_read:
            parser.error("Explicit --live-read is required; no requests were sent")
        binding = Binding(id="read-only-field-evidence", business_id=52, company_guid=COMPANY_GUID, generation=1)
        if args.bahi_id:
            api = Client(read_key)
            try:
                evidence = availability(BahiReader(api).detail(binding, args.bahi_id))
            finally:
                api.close()
        else:
            gateway = Gateway()
            try:
                groups = gateway.read("Group", COMPANY_GUID)
                def root(name):
                    matches = [row["GUID"] for row in groups if row.get("NAME") == name]
                    if len(matches) != 1:
                        raise ValueError("Expected root is not uniquely observed")
                    return matches[0]
                classification = Classification(customer_root=root("Sundry Debtors"), supplier_root=root("Sundry Creditors"))
                evidence = availability(TallyReader(gateway, classification).detail(binding, args.tally_guid))
            finally:
                gateway.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Saved field paths/availability only. No create, update, delete or posting request was sent.")


if __name__ == "__main__":
    main()
