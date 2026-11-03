from datetime import datetime, timezone
import json

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import Preflight
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader


class SupplierExperiment:
    def __init__(self, client):
        self.client, self.reader = client, PartyReader(client)

    def preflight(self, binding, party):
        business = self.client.business(binding.business_id)
        scan = self.reader.scan(binding)
        if not scan.coverage_complete:
            raise ReadError("Complete Bahi party coverage is required before the test")
        if any(row.content.name.casefold() == party.name.casefold() for row in scan.records):
            raise ReadError("The test party name already exists; creation is blocked")
        context = json.dumps({"business_id": business["biz_id"], "business_name": business["biz_name"],
            "party_type": "SUPPLIER", "group": "Server-configured SUPPLIER group; code/id not exposed"}, sort_keys=True)
        return Preflight(group_context=context, destination=f"Bahi {business['biz_name']} (52)")

    def create(self, preview, preflight):
        current = self.preflight(preview.binding, preview.party)
        if current.group_context != preview.preflight.group_context or current.destination != preview.preflight.destination:
            raise ReadError("Bahi destination changed after preview; no creation sent")
        expected = json.loads(current.group_context)
        def before_send(business):
            if business["biz_name"] != expected["business_name"]:
                raise ReadError("Bahi business changed before transmission")
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
        return self.client.create_test_supplier(preview.party, before_send)

    def read_back(self, preview, target):
        if target.kind != "BAHI_ID" or not target.identity:
            raise ReadError("An authoritative Bahi account ID is required for reconciliation")
        row = self.reader.detail(preview.binding, target.identity)
        return row, target, row.party_type == "SUPPLIER"
