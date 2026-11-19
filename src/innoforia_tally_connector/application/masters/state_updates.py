"""Approved linked-party field updates using the shared attempt lifecycle."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from innoforia_tally_connector.application.sync.external_create import apply_once
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import ExperimentPreview, StateUpdateEvidence, Direction
from innoforia_tally_connector.domain.party_transfer import PartyDraft, source_fingerprint
from innoforia_tally_connector.domain.masters import Side
from innoforia_tally_connector.domain.party_changes import PARTY_UPDATE_FIELDS, GST_UPDATE_FIELDS
from innoforia_tally_connector.domain.party_transfer import field_availability


class StateUpdateWorkflow:
    def __init__(self, store, changes, destinations, stopped=lambda: False, *, reverse=False):
        self.reverse = reverse
        self.direction = Direction.TO_BAHI if reverse else Direction.TO_TALLY
        self.source_side = Side.TALLY if reverse else Side.BAHI
        self.target_side = Side.BAHI if reverse else Side.TALLY
        self.store, self.changes, self.destinations, self.stopped = store, changes, destinations, stopped

    def _review(self, binding, classification, identity):
        review = self.changes.review(binding, classification, identity)
        if review.blockers or review.policy_version is None:
            raise ReadError("A fresh eligible linked-party review and saved operator are required")
        return review

    @staticmethod
    def _select(review, fields, accept_missing):
        if not fields or len(fields)!=len(set(fields)) or set(fields)-set(PARTY_UPDATE_FIELDS):
            raise ReadError('Select supported linked-party fields; rename is not enabled')
        rows = {r.field:r for r in review.fields}
        reverse = review.direction == Direction.TO_BAHI
        candidate_status = 'Tally changed' if reverse else 'Bahi changed'
        tax_selected = not reverse and bool(set(fields) & set(GST_UPDATE_FIELDS))
        if tax_selected and not set(GST_UPDATE_FIELDS) <= set(fields):
            raise ReadError('Select GSTIN and registration type together')
        if tax_selected and not any(rows[f].status in {'Bahi changed','Fill missing destination'} for f in GST_UPDATE_FIELDS):
            raise ReadError('No eligible GST registration change is selected')
        missing = []
        for field in fields:
            row = rows[field]
            if row.status == 'Fill missing destination' and accept_missing: missing.append(field)
            elif field in GST_UPDATE_FIELDS and row.status == 'Already matches': continue
            elif row.status != candidate_status:
                raise ReadError(f'{field}: {row.status}. Blank destination differences need explicit filling approval; conflicts cannot be overwritten')
        return tuple(missing)

    @staticmethod
    def _prepare(destination, binding, before, party, fields, date, gst_date=None, gst_state=None):
        if before.side == Side.TALLY and fields == ('state',):
            return destination.prepare(binding,before,party.state,*((date,) if date is not None else ()))
        tax = dict(gst_effective_date=gst_date,gst_state=gst_state) if gst_date is not None or gst_state is not None else {}
        return destination.prepare_fields(binding,before,{f:getattr(party,f) for f in fields},date,**tax)

    def handle(self, command, binding, classification):
        if command.kind == "UPDATE_STATUS":
            record = self.store.get(command.experiment_id, binding) if command.experiment_id else self.store.latest_update(binding, command.party_identity, self.direction)
            if record is not None and record.preview.kind != "UPDATE": raise ReadError("Select a state update")
            return record
        if command.kind == "UPDATE_CANCEL":
            record = self.store.get(command.experiment_id, binding)
            if record is None or record.preview.kind != "UPDATE": raise ReadError("Select a state update")
            return self.store.cancel(command.experiment_id, binding)
        destination = self.destinations(classification)
        if command.kind == "UPDATE_PREPARE":
            review = self._review(binding, classification, command.party_identity)
            fields = command.update_fields or ('state',)
            missing = self._select(review,fields,command.accept_missing_fields)
            tax_selected = not self.reverse and bool(set(fields) & set(GST_UPDATE_FIELDS))
            gst_state = None
            if tax_selected:
                if (any(field_availability(obs,f) != 'present' for obs in (review.bahi,review.tally) for f in ('state','country'))
                    or review.bahi.content.state != review.tally.content.state
                    or review.bahi.content.country != 'India' or review.tally.content.country != 'India'):
                    raise ReadError('GST updates require matching populated Indian mailing State/Country; review mailing changes first')
                gst_state = review.bahi.content.state
            elif command.gst_effective_date is not None:
                raise ReadError('A GST effective date requires paired GST fields')
            source, target = (review.tally, review.bahi) if self.reverse else (review.bahi, review.tally)
            party = PartyDraft(name=source.content.name, party_type=source.party_type,
                **{f:getattr(source.content,f) for f in fields})
            context, before, expected = self._prepare(destination,binding,target,party,fields,command.mailing_effective_date,command.gst_effective_date,gst_state)
            now = datetime.now(timezone.utc)
            preview = ExperimentPreview(id=str(uuid4()), binding=binding, generation=command.generation,
                direction=self.direction, party=party, preflight=context, created_at=now,
                expires_at=now+timedelta(minutes=5), kind="UPDATE", source=source,
                source_confirmation_required=source.is_system is None,
                update=StateUpdateEvidence(link=review.link, before=target, native_before=before, native_expected=expected,
                    policy_version=review.policy_version,
                    fields=fields, accepted_missing_fields=missing,
                    mailing_effective_date=command.mailing_effective_date,
                    gst_effective_date=command.gst_effective_date,gst_state=gst_state,
                    acknowledged_operation_id=review.state_acknowledgement.operation_id if review.state_acknowledgement else None))
            return self.store.save_preview(preview)
        record = self.store.get(command.experiment_id, binding)
        if record is None or record.preview.kind != "UPDATE": raise ReadError("Select the State update preview")
        if record.state in {"SUCCEEDED", "FAILED", "CANCELLED"}: return record
        preview = record.preview
        if preview.direction != self.direction: raise ReadError("Update direction differs from this workflow")
        if command.kind == "UPDATE_CLOSE_FAILED":
            if (self.reverse or record.state != 'BLOCKED' or not record.attempted or record.comparisons.get('state') is not False
                or preview.update.mailing_effective_date is not None
                or preview.update.fields != ('state',)
                or not command.reviewer or not command.reviewer.strip() or not command.source_normal_party_confirmed):
                raise ReadError("Named confirmation is required to close an unchanged empty-mailing failure; uncertain work cannot be closed")
            first, snapshot = destination.unchanged_empty_failure(preview)
            target, native = destination.unchanged_empty_failure(preview)
            if snapshot != native:
                raise ReadError("Ledger changed during closure checks; keep unresolved")
            return self.store.close_unchanged_state_failure(record, command, target, native)
        if command.kind == "UPDATE_APPLY":
            if record.attempted: return record
            preview.require_current(binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
            if command.direction != self.direction or not command.source_normal_party_confirmed:
                raise ReadError("Confirm normal parties and no competing editor for this State update")
            review = self._review(binding, classification, preview.source.identity)
            self._select(review,preview.update.fields,bool(preview.update.accepted_missing_fields))
            source, target = (review.tally, review.bahi) if self.reverse else (review.bahi, review.tally)
            if (source_fingerprint(source) != source_fingerprint(preview.source)
                or source_fingerprint(target) != source_fingerprint(preview.update.before)
                or review.link != preview.update.link or review.policy_version != preview.update.policy_version
                or (review.state_acknowledgement.operation_id if review.state_acknowledgement else None) != preview.update.acknowledged_operation_id):
                raise ReadError("Source/destination/link changed since preview; cancel and prepare again")
            context, before, expected = self._prepare(destination,binding,target,preview.party,preview.update.fields,preview.update.mailing_effective_date,
                preview.update.gst_effective_date,preview.update.gst_state)
            if before != preview.update.native_before or expected != preview.update.native_expected:
                raise ReadError("Native preservation snapshot changed; prepare again")
            if self.stopped(): raise ReadError("Shutdown started; no update attempted")
            record = apply_once(self.store, command, record, context, destination.apply)
            if record.state != "VERIFYING": return record
        elif command.kind != "UPDATE_RECONCILE":
            raise ReadError("Unsupported state update command")
        if not record.attempted: return record
        self.store.result(preview.id, command.id, "RECONCILING", message="Reading the known destination identity; no second update")
        try:
            target, native_after, preservation = destination.read_back(preview)
            comparisons = {"identity": target.identity == preview.update.before.identity and target.binding == binding and target.side == self.target_side,
                "classification": target.party_type == preview.update.before.party_type and target.classification_evidence == preview.update.before.classification_evidence,
                "native_preservation": preservation, "active": target.is_active is not False,
                "not_system": target.is_system is not True, "normal_confirmed": record.source_normal_party_confirmed}
            comparisons.update({field:getattr(target.content,field)==getattr(preview.party,field)
                and field not in target.unavailable_fields and field in target.content.model_fields_set for field in preview.update.fields})
            self.store.record_state_verification(record, command, target, native_after, comparisons)
            self.store.result(preview.id, command.id, "VERIFYING", comparisons=comparisons, observation=target)
            if not all(comparisons.values()):
                self.store.result(preview.id, command.id, "BLOCKED", comparisons=comparisons, observation=target,
                    message="Selected fields/preservation verification differs; never resend. Inspect retained evidence")
                return self.store.get(preview.id, binding)
            source = self.changes.readers(classification)[1 if self.reverse else 0].detail(binding, preview.source.identity)
            if source_fingerprint(source) != source_fingerprint(preview.source):
                raise ReadError("Source changed after approval; retain outcome and review")
            return self.store.complete_state_update(record, command, source, target, native_after, comparisons)
        except Exception:
            self.store.result(preview.id, command.id, "VERIFYING", message="Party update needs read-only verification/local completion; never resend")
            return self.store.get(preview.id, binding)
