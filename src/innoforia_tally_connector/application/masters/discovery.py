"""Manual read/link workflow; concrete connections and storage are injected."""
from dataclasses import dataclass
from datetime import datetime, timezone

from innoforia_tally_connector.application.masters.mappings import confirm_party_link
from innoforia_tally_connector.application.masters.parties import compare_scans
from innoforia_tally_connector.domain.errors import ContextMismatch, ReadError
from innoforia_tally_connector.domain.masters import Binding, Classification, ConfirmedPartyLink, ConnectionSnapshot, PartyScan, ScanIssue, Side


@dataclass(frozen=True)
class Verified:
    snapshot: ConnectionSnapshot
    saved_setup: tuple[Binding, Classification, ConnectionSnapshot] | None


@dataclass(frozen=True)
class Bound:
    binding: Binding
    classification: Classification
    links: tuple[ConfirmedPartyLink, ...]
    has_more: bool = False
    snapshot: ConnectionSnapshot | None = None


@dataclass(frozen=True)
class SavedPage:
    links: tuple[ConfirmedPartyLink, ...]
    offset: int
    has_more: bool


class DiscoveryWorkflow:
    def __init__(self, verify, readers, validate_groups, store, links, credential_reference, experiments=None, transfers=None, batches=None, changes=None, updates=None, reverse_changes=None, reverse_updates=None):
        self.verify, self.readers, self.validate_groups = verify, readers, validate_groups
        self.store, self.links, self.credential_reference = store, links, credential_reference
        self.active = None
        self.experiments = experiments
        self.transfers = transfers
        self.batches = batches
        self.changes = changes
        self.updates = updates
        self.reverse_changes, self.reverse_updates = reverse_changes, reverse_updates

    def handle(self, command):
        if command.kind == "RESTORE":
            self.active = None
            old = self.store.setup()
            snapshot = self.verify()
            if old is None:
                return Verified(snapshot, None)
            binding, classification, previous = old
            if (snapshot.business_id != binding.business_id or snapshot.company_guid != binding.company_guid
                or snapshot.business_name != previous.business_name or snapshot.company_name != previous.company_name):
                raise ContextMismatch("Saved connection identity changed; review Settings")
            self.validate_groups(classification, snapshot.groups)
            def evidence(groups):
                by_id, by_name = {g.identity: g for g in groups}, {g.name: g for g in groups}
                result = set()
                for root in (classification.customer_root, classification.supplier_root):
                    group = by_id.get(root)
                    visited = set()
                    while group:
                        if group.identity in visited:
                            raise ContextMismatch("Saved classification ancestry is cyclic")
                        visited.add(group.identity)
                        result.add((group.identity, group.name, group.parent))
                        if not group.parent or group.parent == "Primary": break
                        group = by_name.get(group.parent)
                        if group is None:
                            raise ContextMismatch("Saved classification ancestry is unresolved")
                return result
            if evidence(snapshot.groups) != evidence(previous.groups):
                raise ContextMismatch("Saved classification changed; review Settings")
            self.active = (binding, classification, command.generation)
            links = self.links.list(binding, limit=201)
            return Bound(binding, classification, links[:200], len(links) > 200, snapshot)
        if command.kind == "VERIFY":
            self.active = None
            return Verified(self.verify(), self.store.setup())
        if command.kind == "BIND":
            self.active = None
            snapshot = self.verify()
            if command.classification is None:
                raise ReadError("Explicit customer and supplier group confirmation is required")
            self.validate_groups(command.classification, snapshot.groups)
            old = self.store.setup()
            binding = old[0] if old else Binding(id="bahi52-sis-dummy", business_id=snapshot.business_id,
                                                  company_guid=snapshot.company_guid, generation=1)
            if binding.business_id != snapshot.business_id or binding.company_guid != snapshot.company_guid:
                raise ContextMismatch("Saved binding no longer matches the verified pair")
            self.store.bind(binding, command.classification, snapshot, self.credential_reference)
            self.active = (binding, command.classification, command.generation)
            links = self.links.list(binding, limit=201)
            return Bound(binding, command.classification, links[:200], len(links) > 200, snapshot)
        if not self.active or command.binding != self.active[0] or command.generation != self.active[2]:
            raise ContextMismatch("Verify and explicitly confirm the current binding first")
        binding, classification, _ = self.active
        if command.kind.startswith("UPDATE_"):
            if self.updates is None: raise ReadError("Controlled state updates unavailable")
            direction = command.direction
            if command.experiment_id:
                record = self.updates.store.get(command.experiment_id, binding)
                if record: direction = record.preview.direction
            workflow = self.reverse_updates if direction == 'TALLY_TO_BAHI' else self.updates
            if workflow is None: raise ReadError('Linked updates unavailable for this direction')
            return workflow.handle(command, binding, classification)
        if command.kind == "PARTY_CHANGES":
            if self.changes is None:
                raise ReadError("Linked-party change review is unavailable")
            workflow = self.reverse_changes if command.direction == 'TALLY_TO_BAHI' else self.changes
            if workflow is None: raise ReadError('Linked review unavailable for this direction')
            return workflow.review(binding, classification, command.party_identity)
        if command.kind.startswith(("BATCH_", "POLICY_")):
            if self.batches is None:
                raise ReadError("Batch transfers unavailable")
            if command.kind == "BATCH_RECOVER" and self.experiments:
                for record in self.transfers.store.reconciliation_candidates(binding):
                    if record.preview.kind == "UPDATE" and self.updates:
                        workflow = self.reverse_updates if record.preview.direction == 'TALLY_TO_BAHI' else self.updates
                        workflow.handle(command.model_copy(update={"kind": "UPDATE_RECONCILE", "experiment_id": record.preview.id}), binding, classification)
                    if record.preview.kind == "EXPERIMENT" and record.attempted and record.target and record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                        self.experiments.handle(command.model_copy(update={"kind": "EXP_RECONCILE", "experiment_id": record.preview.id}), binding, classification)
            return self.batches.handle(command, binding, classification)
        if command.kind.startswith("TRANSFER_") or command.kind in {"ACTIVITY", "ACTIVITY_DETAIL"}:
            if self.transfers is None:
                raise ReadError("Party transfers are unavailable")
            return self.transfers.handle(command, binding, classification)
        if command.kind.startswith("EXP_"):
            if command.kind in {"EXP_PREPARE", "EXP_CREATE"}:
                raise ReadError("Legacy synthetic creation is retired; select a real source party for transfer")
            if self.experiments is None:
                raise ReadError("Controlled experiments are unavailable")
            return self.experiments.handle(command, binding, classification)
        if command.kind == "SAVED":
            links = self.links.list(binding, offset=command.offset, limit=201)
            return SavedPage(links[:200], command.offset, len(links) > 200)
        bahi, tally = self.readers(classification)
        if command.kind == "LOAD":
            scans = []
            for side, reader in ((Side.BAHI, bahi), (Side.TALLY, tally)):
                try:
                    scans.append(reader.scan(binding))
                except ContextMismatch:
                    raise
                except ReadError as error:
                    scans.append(PartyScan(binding=binding, side=side, records=(),
                        observed_at=datetime.now(timezone.utc), pages_read=(), total_pages=None,
                        failed_pages=(1,), issues=(ScanIssue(code="READ_FAILED", message=str(error)),)))
            return compare_scans(binding, *scans, self.links)
        if command.kind == "LINK":
            if command.bahi is None or command.tally is None or not command.reviewer or not command.reviewer.strip():
                raise ReadError("Select both records and enter the confirming reviewer")
            return confirm_party_link(binding, command.bahi, command.tally, bahi=bahi, tally=tally,
                links=self.links, confirmed_by=command.reviewer, review_reference=command.id, link_id=command.id)
        raise ReadError("Unsupported discovery command")
