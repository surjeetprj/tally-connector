"""Real customer/supplier create with final context/freshness checks."""
from datetime import datetime, timezone
import json
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import Preflight
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader
from innoforia_tally_connector.integrations.bahi.party_payload import validate


class PartyDestination:
    validate = staticmethod(validate)

    def __init__(self, client):
        self.client, self.reader = client, PartyReader(client)

    def collisions(self, binding, name):
        return tuple(n for n in self.collision_names(binding) if " ".join(n.casefold().split()) == " ".join(name.casefold().split()))

    def collision_names(self, binding, scan=None):
        scan = scan if scan is not None else self.reader.scan(binding)
        if scan.binding != binding or scan.side != "BAHI" or not scan.coverage_complete:
            raise ReadError("Incomplete Bahi coverage; creation blocked")
        return tuple(row.content.name for row in scan.records)

    def preflight(self, binding, draft):
        business = self.client.business(binding.business_id)
        context = json.dumps({"business_id": business["biz_id"], "business_name": business["biz_name"],
            "party_type": str(draft.party_type), "group": f"Server-configured {draft.party_type} group; code/id not exposed"}, sort_keys=True)
        return Preflight(group_context=context, destination=f"Bahi {business['biz_name']} (52)")

    def create(self, preview, preflight):
        if self.collisions(preview.binding, preview.party.name):
            raise ReadError("Name collision before transmission; creation blocked")
        current = self.preflight(preview.binding, preview.party)
        if current.group_context != preview.preflight.group_context:
            raise ReadError("Bahi destination/group changed after approval")
        expected = json.loads(current.group_context)
        def before_send(business):
            if business["biz_name"] != expected["business_name"]:
                raise ReadError("Bahi business changed")
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
        return self.client.create_party(preview.party, before_send)

    def read_back(self, preview, target):
        if target.kind != "BAHI_ID" or not target.identity:
            raise ReadError("Authoritative Bahi account ID required; no name fallback")
        row = self.reader.detail(preview.binding, target.identity)
        return row, target, row.party_type == preview.party.party_type
