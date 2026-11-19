"""Typed linked-party update adapter, sharing the injected gateway."""
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.state_update import expected_native, preservation_matches
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally.party_update import expected_fields, fields_preserved


class StateDestination:
    def __init__(self, gateway, classification):
        self.gateway = gateway
        self.reader = PartyReader(gateway, classification)

    def prepare(self, binding, before, state, effective_date=None):
        context, snapshot = self.gateway.state_snapshot(binding, before.identity)
        node = parse(snapshot.encode())
        if (node.findtext("ALTERID", "").strip() != (before.version or "").strip()
            or node.findtext("NAME") != before.content.name or node.findtext("PARENT") not in {"Sundry Creditors","Sundry Debtors"}):
            raise ReadError("Ledger version/name/group changed or is outside the supported supplier root")
        return context, snapshot, expected_native(snapshot, state, effective_date)

    def prepare_fields(self,binding,before,values,effective_date=None, *, gst_effective_date=None,gst_state=None):
        context,snapshot = self.gateway.state_snapshot(binding,before.identity)
        node = parse(snapshot.encode())
        if node.findtext('ALTERID','').strip()!=(before.version or '').strip() or node.findtext('NAME')!=before.content.name:
            raise ReadError('Ledger changed while preparing linked fields')
        tax = dict(gst_effective_date=gst_effective_date,gst_state=gst_state) if gst_effective_date is not None or gst_state is not None else {}
        return context,snapshot,expected_fields(snapshot,values,effective_date,**tax)

    def unchanged_empty_failure(self, preview):
        """Read-only evidence for operator closure of the known empty-entry rejection."""
        before = parse(preview.update.native_before.encode())
        entries = before.findall('LEDMAILINGDETAILS.LIST')
        if len(entries) != 1 or len(entries[0]) or entries[0].attrib or (entries[0].text or '').strip():
            raise ReadError("Only the unchanged empty-mailing failure can be closed here")
        target, native, _ = self.read_back(preview)
        if (target.identity != preview.update.before.identity or target.binding != preview.binding
            or target.party_type != preview.update.before.party_type
            or target.classification_evidence != preview.update.before.classification_evidence
            or target.is_active is False or target.is_system is True
            or not preservation_matches(preview.update.native_before, native, preview.update.before.content.state or '')):
            raise ReadError("Ledger differs from the original evidence; keep unresolved and inspect it")
        return target, native

    def apply(self, preview, preflight):
        return self.gateway.apply_state(preview)

    def read_back(self, preview):
        identity = preview.update.before.identity
        observation = self.reader.detail(preview.binding, identity)
        _, snapshot = self.gateway.state_snapshot(preview.binding, identity)
        node = parse(snapshot.encode())
        if node.findtext("ALTERID", "").strip() != (observation.version or "").strip():
            raise ReadError("Ledger changed during verification; retry reads only")
        if preview.update.fields == ('state',):
            matches = preservation_matches(preview.update.native_expected, snapshot, preview.party.state,
                preview.update.mailing_effective_date)
        else:
            values = {f:getattr(preview.party,f) for f in preview.update.fields}
            matches = fields_preserved(preview.update.native_expected,snapshot,values,
                values.get('state',preview.update.before.content.state or ''),preview.update.mailing_effective_date,
                native_before=preview.update.native_before,gst_effective_date=preview.update.gst_effective_date,gst_state=preview.update.gst_state)
        return observation, snapshot, matches
