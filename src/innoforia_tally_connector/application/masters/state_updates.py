"""Approved repeatable supplier State updates using the shared attempt lifecycle."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from innoforia_tally_connector.application.sync.external_create import apply_once
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import ExperimentPreview, StateUpdateEvidence, Direction
from innoforia_tally_connector.domain.party_transfer import PartyDraft, source_fingerprint
from innoforia_tally_connector.domain.masters import Side


class StateUpdateWorkflow:
    def __init__(self, store, changes, destinations, stopped=lambda: False):
        self.store, self.changes, self.destinations, self.stopped = store, changes, destinations, stopped

    def _review(self, binding, classification, identity):
        review = self.changes.review(binding, classification, identity)
        state = next(f for f in review.fields if f.field == "state")
        if review.blockers or state.status != "Bahi changed" or review.policy_version is None:
            raise ReadError("A fresh, eligible Bahi-only State change is required; review changes first")
        return review

    def handle(self, command, binding, classification):
        if command.kind == "UPDATE_STATUS":
            record = self.store.get(command.experiment_id, binding) if command.experiment_id else self.store.latest_update(binding, command.party_identity)
            if record is not None and record.preview.kind != "UPDATE": raise ReadError("Select a state update")
            return record
        if command.kind == "UPDATE_CANCEL":
            record = self.store.get(command.experiment_id, binding)
            if record is None or record.preview.kind != "UPDATE": raise ReadError("Select a state update")
            return self.store.cancel(command.experiment_id, binding)
        destination = self.destinations(classification)
        if command.kind == "UPDATE_PREPARE":
            review = self._review(binding, classification, command.party_identity)
            party = PartyDraft(name=review.bahi.content.name, party_type=review.bahi.party_type, state=review.bahi.content.state)
            context, before, expected = destination.prepare(binding, review.tally, party.state)
            now = datetime.now(timezone.utc)
            preview = ExperimentPreview(id=str(uuid4()), binding=binding, generation=command.generation,
                direction=Direction.TO_TALLY, party=party, preflight=context, created_at=now,
                expires_at=now+timedelta(minutes=5), kind="UPDATE", source=review.bahi,
                source_confirmation_required=review.bahi.is_system is None,
                update=StateUpdateEvidence(link=review.link, before=review.tally, native_before=before, native_expected=expected,
                    policy_version=review.policy_version,
                    acknowledged_operation_id=review.state_acknowledgement.operation_id if review.state_acknowledgement else None))
            return self.store.save_preview(preview)
        record = self.store.get(command.experiment_id, binding)
        if record is None or record.preview.kind != "UPDATE": raise ReadError("Select the State update preview")
        if record.state in {"SUCCEEDED", "FAILED", "CANCELLED"}: return record
        preview = record.preview
        if command.kind == "UPDATE_APPLY":
            if record.attempted: return record
            preview.require_current(binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
            if command.direction != Direction.TO_TALLY or not command.source_normal_party_confirmed:
                raise ReadError("Confirm normal parties and no competing editor for this State update")
            review = self._review(binding, classification, preview.source.identity)
            if (source_fingerprint(review.bahi) != source_fingerprint(preview.source)
                or source_fingerprint(review.tally) != source_fingerprint(preview.update.before)
                or review.link != preview.update.link or review.policy_version != preview.update.policy_version
                or (review.state_acknowledgement.operation_id if review.state_acknowledgement else None) != preview.update.acknowledged_operation_id):
                raise ReadError("Source/destination/link changed since preview; cancel and prepare again")
            context, before, expected = destination.prepare(binding, review.tally, preview.party.state)
            if before != preview.update.native_before or expected != preview.update.native_expected:
                raise ReadError("Native preservation snapshot changed; prepare again")
            if self.stopped(): raise ReadError("Shutdown started; no update attempted")
            record = apply_once(self.store, command, record, context, destination.apply)
            if record.state != "VERIFYING": return record
        elif command.kind != "UPDATE_RECONCILE":
            raise ReadError("Unsupported state update command")
        if not record.attempted: return record
        self.store.result(preview.id, command.id, "RECONCILING", message="Reading the known GUID; no second update")
        try:
            target, native_after, preservation = destination.read_back(preview)
            comparisons = {"identity": target.identity == preview.update.before.identity and target.binding == binding and target.side == Side.TALLY,
                "classification": target.party_type == preview.update.before.party_type and target.classification_evidence == preview.update.before.classification_evidence,
                "state": target.content.state == preview.party.state and "state" not in target.unavailable_fields,
                "native_preservation": preservation, "active": target.is_active is not False,
                "not_system": target.is_system is not True, "normal_confirmed": record.source_normal_party_confirmed}
            self.store.record_state_verification(record, command, target, native_after, comparisons)
            self.store.result(preview.id, command.id, "VERIFYING", comparisons=comparisons, observation=target)
            if not all(comparisons.values()):
                self.store.result(preview.id, command.id, "BLOCKED", comparisons=comparisons, observation=target,
                    message="State/preservation verification differs; never resend. Inspect retained evidence")
                return self.store.get(preview.id, binding)
            source = self.changes.readers(classification)[0].detail(binding, preview.source.identity)
            if source_fingerprint(source) != source_fingerprint(preview.source):
                raise ReadError("Source changed after approval; retain outcome and review")
            return self.store.complete_state_update(record, command, source, target, native_after, comparisons)
        except Exception:
            self.store.result(preview.id, command.id, "VERIFYING", message="State update needs read-only verification/local completion; never resend")
            return self.store.get(preview.id, binding)
