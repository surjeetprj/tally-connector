"""Known-account scalar updates; never create, rename, clear or change groups."""
import json
from datetime import datetime, timezone

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.party_transfer import source_fingerprint, PartyDraft
from innoforia_tally_connector.integrations.bahi.endpoints.transfers import PartyDestination
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader
from innoforia_tally_connector.integrations.bahi.party_payload import validate


class UpdateDestination:
    validate = staticmethod(validate)

    def __init__(self, client):
        self.client, self.reader = client, PartyReader(client)
        self.preflight = PartyDestination(client).preflight

    def snapshot(self, binding, identity):
        self.client.business(binding.business_id)
        raw = self.client.get('api-party.php', {'id': identity})['data']
        observation = self.reader.detail(binding, identity)
        # Independent reads must agree, including fields outside our domain model.
        again = self.client.get('api-party.php', {'id': identity})['data']
        if raw != again:
            raise ReadError('Bahi party changed while reading; refresh the review')
        return observation, raw

    def prepare_fields(self, binding, before, values, effective_date=None, **tax):
        if effective_date or any(tax.values()):
            raise ReadError('Bahi scalar fields do not use Tally history dates')
        current, raw = self.snapshot(binding, before.identity)
        if source_fingerprint(current) != source_fingerprint(before):
            raise ReadError('Bahi party changed while preparing the update')
        expected = {**raw, **values}
        encode = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False)
        return self.preflight(binding, PartyDraft(name=current.content.name, party_type=current.party_type)), encode(raw), encode(expected)

    def apply(self, preview, preflight):
        if preview.kind != 'UPDATE' or preview.direction != Direction.TO_BAHI:
            raise ReadError('A linked Tally-to-Bahi update is required')
        context = json.loads(preflight.group_context)
        def before_send(business):
            if business['biz_id'] != preview.binding.business_id or business['biz_name'] != context['business_name']:
                raise ReadError('Bahi business changed after approval')
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
        values = {field: getattr(preview.party, field) for field in preview.update.fields}
        return self.client.update_party(preview.update.before.identity,
            json.loads(preview.update.native_before), values, before_send)

    def read_back(self, preview):
        current, raw = self.snapshot(preview.binding, preview.update.before.identity)
        expected = json.loads(preview.update.native_expected)
        # updated_dtm is the documented server-managed update timestamp.
        strip = lambda row: {k: v for k, v in row.items() if k != 'updated_dtm'}
        return current, json.dumps(raw, sort_keys=True, ensure_ascii=False), strip(raw) == strip(expected)
