"""State-only supplier update adapter, sharing the injected gateway."""
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.state_update import expected_native, preservation_matches
from innoforia_tally_connector.integrations.tally.xml_codec import parse


class StateDestination:
    def __init__(self, gateway, classification):
        self.gateway = gateway
        self.reader = PartyReader(gateway, classification)

    def prepare(self, binding, before, state):
        context, snapshot = self.gateway.state_snapshot(binding, before.identity)
        node = parse(snapshot.encode())
        if (node.findtext("ALTERID", "").strip() != (before.version or "").strip()
            or node.findtext("NAME") != before.content.name or node.findtext("PARENT") != "Sundry Creditors"):
            raise ReadError("Ledger version/name/group changed or is outside the supported supplier root")
        return context, snapshot, expected_native(snapshot, state)

    def apply(self, preview, preflight):
        return self.gateway.apply_state(preview)

    def read_back(self, preview):
        identity = preview.update.before.identity
        observation = self.reader.detail(preview.binding, identity)
        _, snapshot = self.gateway.state_snapshot(preview.binding, identity)
        node = parse(snapshot.encode())
        if node.findtext("ALTERID", "").strip() != (observation.version or "").strip():
            raise ReadError("Ledger changed during verification; retry reads only")
        matches = preservation_matches(preview.update.native_expected, snapshot, preview.party.state)
        return observation, snapshot, matches
