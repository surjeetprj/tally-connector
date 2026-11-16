"""Receipt parsing and typed experiment adapter; all IO stays in the gateway."""
from datetime import datetime, timezone
import json

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import TargetIdentity, UncertainWrite
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.xml_codec import parse


def import_receipt(raw, baseline):
    try:
        root = parse(raw, check_errors=False)
    except ReadError:
        raise UncertainWrite("Malformed Tally import response; do not create again") from None
    last = root.findtext(".//LASTMID", "0")
    target = TargetIdentity(kind="TALLY_MASTER_ID", identity=last) if last.isdecimal() and int(last) > 0 else None
    if any(len(root.findall(f".//{tag}")) > 1 for tag in ("LASTMID", "CREATED", "ALTERED", "ERRORS", "STATUS")):
        raise UncertainWrite("Duplicate Tally receipt fields; outcome requires investigation")
    good = {"CREATED": "1", "ALTERED": "0", "ERRORS": "0"}
    bad = any(root.findtext(f".//{key}") != value for key, value in good.items())
    for tag in ("DELETED", "COMBINED", "IGNORED", "CANCELLED", "EXCEPTIONS"):
        value = root.findtext(f".//{tag}", "0")
        bad = bad or not value.isdecimal() or int(value) != 0
    bad = bad or any((n.text or "").strip() for n in root.iter() if n.tag in {"LINEERROR", "LASTIMPORTERROR", "ERROR"})
    bad = bad or root.findtext(".//STATUS") == "0"
    if bad:
        raise UncertainWrite("Tally import counters/errors are not a verified create; reconcile through reads", target)
    return target or TargetIdentity(kind="TALLY_CREATED_EXPORT", baseline_guids=baseline)


class SupplierExperiment:
    def __init__(self, gateway, classification):
        self.gateway, self.reader = gateway, PartyReader(gateway, classification)
        self.classification = classification

    def preflight(self, binding, party):
        return self.gateway.preflight_test_supplier(binding, self.classification.supplier_root, party)

    def create(self, preview, preflight):
        preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
        return self.gateway.create_test_supplier(preview, self.classification.supplier_root, preflight)

    def read_back(self, preview, target):
        if target.kind == "TALLY_GUID" and target.identity:
            row = self.reader.detail(preview.binding, target.identity)
        else:
            rows = self.gateway.read("Ledger", preview.binding.company_guid)
            if target.kind == "TALLY_MASTER_ID" and target.identity:
                matches = [r for r in rows if r.get("MASTERID") == target.identity]
            elif target.kind == "TALLY_CREATED_EXPORT":
                matches = [r for r in rows if r.get("GUID") and r["GUID"] not in target.baseline_guids
                           and r.get("NAME") == preview.party.name]
            else:
                raise ReadError("An import receipt/identity is required; name searches cannot resolve an uncertain create")
            if len(matches) != 1 or not matches[0].get("GUID"):
                raise ReadError("Tally target identity is not uniquely verified; do not create again")
            row = self.reader.detail(preview.binding, matches[0]["GUID"])
        path = json.loads(row.classification_evidence)
        direct_group = bool(path) and path[0][0] == self.classification.supplier_root
        return row, TargetIdentity(kind="TALLY_GUID", identity=row.identity), direct_group
