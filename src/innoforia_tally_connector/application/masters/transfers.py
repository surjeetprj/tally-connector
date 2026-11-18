"""Supervised real-party creation and mapping; all IO is injected through ports."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Callable

from innoforia_tally_connector.application.masters.parties import search_name as normalized_name
from innoforia_tally_connector.application.masters.transfer_fields import select_fields
from innoforia_tally_connector.application.sync.external_create import apply_once
from innoforia_tally_connector.application.ports import PartyDestination, PartyLinks, PartyReader, PartyTransferStore
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import Direction, ExperimentPreview
from innoforia_tally_connector.domain.masters import Classification, ConnectionSnapshot, Side
from innoforia_tally_connector.domain.party_transfer import TransferReview, source_fingerprint


class PartyTransferWorkflow:
    def __init__(self, store: PartyTransferStore, readers: Callable[[Classification], tuple[PartyReader, PartyReader]],
                 destinations: Callable[[Direction, Classification], PartyDestination], verify: Callable[[], ConnectionSnapshot],
                 links: PartyLinks, stopped: Callable[[], bool] = lambda: False):
        self.store, self.readers, self.destinations, self.verify, self.links, self.stopped = store, readers, destinations, verify, links, stopped

    def _context(self, binding):
        snapshot = self.verify()
        if snapshot.business_id != binding.business_id or snapshot.company_guid != binding.company_guid:
            raise ReadError("Connection context changed; verify the pair again")

    @staticmethod
    def _eligible(source):
        if source.is_active is False or source.is_system is True:
            raise ReadError("Inactive or system parties cannot transfer")
        if source.side == Side.BAHI and source.is_active is not True:
            raise ReadError("Bahi active eligibility is unavailable; refresh source evidence before transfer")

    def _fresh_source(self, expected, reader):
        current = reader.detail(expected.binding, expected.identity)
        if current.binding != expected.binding or current.side != expected.side or current.identity != expected.identity:
            raise ReadError("Source identity changed")
        if source_fingerprint(current) != source_fingerprint(expected):
            raise ReadError("Source changed; reload and prepare a new preview")
        if not timedelta(0) <= datetime.now(timezone.utc) - current.observed_at <= timedelta(minutes=5):
            raise ReadError("Source detail is stale")
        self._eligible(current)
        return current

    def _candidates(self, binding, source, reader, destination):
        scan = reader.scan(binding)
        if scan.binding != binding or scan.side == source.side or not scan.coverage_complete or scan.failed_pages:
            raise ReadError("Complete destination coverage is required before transfer")
        found = tuple(row for row in scan.records if (
            normalized_name(row.content.name) == normalized_name(source.content.name)
            or (row.party_type == source.party_type and source.content.gstin not in (None, "")
                and row.content.gstin == source.content.gstin)))
        # Adapter checks all ledger names, including unclassified/non-party ledgers.
        collisions = destination.collisions(binding, source.content.name)
        return found, collisions

    def handle(self, command, binding, classification):
        if command.kind == "ACTIVITY":
            return self.store.history(binding, command.offset, command.status_filter, command.type_filter)
        if command.kind == "ACTIVITY_DETAIL":
            return self.store.get(command.experiment_id, binding)
        if command.kind == "TRANSFER_CANCEL":
            return self.store.cancel(command.experiment_id, binding)
        bahi, tally = self.readers(classification)
        if command.kind == "TRANSFER_PREPARE":
            expected = command.source
            if expected is None or expected.binding != binding:
                raise ReadError("Select a current source party")
            direction = Direction.TO_TALLY if expected.side == Side.BAHI else Direction.TO_BAHI
            if command.direction != direction:
                raise ReadError("Direction does not match the selected source")
            self._context(binding)
            source_reader, target_reader = (bahi, tally) if expected.side == Side.BAHI else (tally, bahi)
            source = self._fresh_source(expected, source_reader)
            linked = self.links.find(binding, source.side, source.identity)
            if linked:
                return TransferReview(record=linked, source=source, message="Already linked; no new creation")
            destination = self.destinations(direction, classification)
            candidates, collisions = self._candidates(binding, source, target_reader, destination)
            if candidates or collisions:
                return TransferReview(source=source, candidates=candidates,
                    message="Possible destination match/collision. Link an existing compatible party or cancel. " + "; ".join(collisions))
            draft, decisions = select_fields(source, destination, command.exclusions)
            preflight = destination.preflight(binding, draft)
            now = datetime.now(timezone.utc)
            preview = ExperimentPreview(id=str(uuid4()), binding=binding, generation=command.generation,
                direction=direction, party=draft, preflight=preflight, created_at=now, expires_at=now + timedelta(minutes=5),
                kind="TRANSFER", source=source, decisions=decisions, source_confirmation_required=source.is_system is None)
            return self.store.save_preview(preview, replaces=command.experiment_id)
        record = self.store.get(command.experiment_id, binding)
        if record is None or record.preview.kind != "TRANSFER":
            raise ReadError("Select a real transfer in activity history")
        if record.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return record
        preview = record.preview
        destination = self.destinations(preview.direction, classification)
        source_reader, target_reader = (bahi, tally) if preview.source.side == Side.BAHI else (tally, bahi)
        if command.kind == "TRANSFER_CREATE":
            if record.attempted:
                return record
            preview.require_current(binding, command.generation, command.approval_digest, datetime.now(timezone.utc))
            if command.direction != preview.direction or any(d.status in {"invalid", "unavailable"} for d in preview.decisions):
                raise ReadError("Review direction and explicitly exclude unavailable/invalid optional fields")
            if preview.source_confirmation_required and not command.source_normal_party_confirmed:
                raise ReadError("Explicit reviewer confirmation of a normal non-system source is required; the source flag is unavailable")
            included = {d.field for d in preview.decisions if d.status == "included"}
            if included != preview.party.model_fields_set - {"party_type"} or "name" not in included:
                raise ReadError("Incomplete field manifest; renew the preview")
            if any(field not in preview.source.content.model_fields_set or
                   getattr(preview.party, field) != getattr(preview.source.content, field) for field in included):
                raise ReadError("Transfer values must preserve the selected source; renew the preview")
            self._context(binding)
            self._fresh_source(preview.source, source_reader)
            if destination.validate(preview.party):
                raise ReadError("Destination field support changed; renew the preview")
            if self.links.find(binding, preview.source.side, preview.source.identity):
                raise ReadError("Source is now linked")
            candidates, collisions = self._candidates(binding, preview.source, target_reader, destination)
            if candidates or collisions:
                raise ReadError("Destination candidates changed; creation blocked")
            current = destination.preflight(binding, preview.party)
            if self.stopped():
                raise ReadError("Shutdown started; no create attempted")
            record = apply_once(self.store, command, record, current, destination.create)
            if record.state != "VERIFYING":
                return record
        elif command.kind != "TRANSFER_RECONCILE":
            raise ReadError("Unsupported transfer command")
        if not record.attempted or record.target is None:
            return record  # Unknown target never resolved by name, never re-created.
        self.store.result(preview.id, command.id, "RECONCILING", message="Reading the saved destination identity")
        try:
            observed, target, group_ok = destination.read_back(preview, record.target)
            # Save a newly resolved GUID even if later comparisons or mapping fail.
            self.store.result(preview.id, command.id, "VERIFYING", target=target, observation=observed)
            expected_side = Side.TALLY if preview.source.side == Side.BAHI else Side.BAHI
            comparisons = {"identity_context": observed.binding == binding and observed.side == expected_side,
                "identity": observed.identity == target.identity and target.kind == ("TALLY_GUID" if expected_side == Side.TALLY else "BAHI_ID"),
                "party_type": observed.party_type == preview.party.party_type, "group_semantics": group_ok,
                "active": observed.is_active is not False}
            if observed.is_system is not None:
                comparisons["not_system"] = observed.is_system is False
            if preview.source_confirmation_required:
                comparisons["reviewer_confirmed_normal_source"] = record.source_normal_party_confirmed
            for field in preview.party.model_fields_set - {"party_type"}:
                comparisons[field] = (field in observed.content.model_fields_set and field not in observed.unavailable_fields
                                     and getattr(observed.content, field) == getattr(preview.party, field))
            if not all(comparisons.values()):
                differences = ", ".join(sorted(field for field, matches in comparisons.items() if not matches))
                self.store.result(preview.id, command.id, "BLOCKED", target=target, observation=observed,
                                  comparisons=comparisons, message=f"Created target differs: {differences}; no retry or correction is enabled")
            else:
                self.store.result(preview.id, command.id, "VERIFYING", target=target, observation=observed, comparisons=comparisons)
                source = self._fresh_source(preview.source, source_reader)
                return self.store.complete_transfer(record, command, source, observed, comparisons, target)
        except Exception:
            self.store.result(preview.id, command.id, "VERIFYING",
                message="Target/source or mapping completion needs review. Reconcile through reads only; do not create again.")
        return self.store.get(preview.id, binding)
