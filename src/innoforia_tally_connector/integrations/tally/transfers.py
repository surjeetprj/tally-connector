"""Real-party destination adapter; protocol and XML stay in the integration layer."""
import json
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import TargetIdentity
from innoforia_tally_connector.domain.masters import PartyType
from innoforia_tally_connector.integrations.tally.builders.parties import validate
from innoforia_tally_connector.integrations.tally.parties import PartyReader


class PartyDestination:
    validate = staticmethod(validate)

    def __init__(self, gateway, classification):
        self.gateway, self.classification = gateway, classification
        self.reader = PartyReader(gateway, classification)

    def root(self, party_type):
        return self.classification.customer_root if party_type == PartyType.CUSTOMER else self.classification.supplier_root

    def collisions(self, binding, name):
        return tuple(n for n in self.collision_names(binding) if " ".join(n.casefold().split()) == " ".join(name.casefold().split()))

    def collision_names(self, binding, scan=None):
        rows = self.gateway.read("Ledger", binding.company_guid)
        return tuple(row.get("NAME", "") for row in rows)

    def preflight(self, binding, draft):
        return self.gateway.preflight_party(binding, self.root(draft.party_type), draft)

    def create(self, preview, preflight):
        return self.gateway.create_party(preview, self.root(preview.party.party_type))

    def read_back(self, preview, target):
        mailing_date = json.loads(preview.preflight.group_context).get("mailing_applicable_from")
        if target.kind == "TALLY_GUID" and target.identity:
            row = self.reader.detail(preview.binding, target.identity, mailing_date=mailing_date)
        else:
            rows = self.gateway.read("Ledger", preview.binding.company_guid)
            if target.kind == "TALLY_MASTER_ID" and target.identity:
                matches = [row for row in rows if row.get("MASTERID") == target.identity]
            elif target.kind == "TALLY_CREATED_EXPORT":
                matches = [row for row in rows if row.get("GUID") and row["GUID"] not in target.baseline_guids and row.get("NAME") == preview.party.name]
            else:
                raise ReadError("No authoritative receipt/identity; name matches cannot reconcile uncertainty")
            if len(matches) != 1 or not matches[0].get("GUID"):
                raise ReadError("Created Tally identity cannot be resolved uniquely")
            row = self.reader.detail(preview.binding, matches[0]["GUID"], mailing_date=mailing_date)
        path = json.loads(row.classification_evidence)
        return row, TargetIdentity(kind="TALLY_GUID", identity=row.identity), bool(path) and path[0][0] == self.root(preview.party.party_type)
