"""Policy-driven preparation and sequential batch execution over shared transfers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from innoforia_tally_connector.application.masters.parties import search_name
from innoforia_tally_connector.application.masters.transfer_fields import select_fields
from innoforia_tally_connector.domain.batches import BatchItem, TransferBatch
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import Direction, ExperimentPreview
from innoforia_tally_connector.domain.party_transfer import OPTIONAL_FIELDS
from innoforia_tally_connector.domain.masters import Side
from innoforia_tally_connector.application.ports import PartyBatchStore


class BatchWorkflow:
    def __init__(self, store: PartyBatchStore, transfers, progress=lambda *_: None):
        self.store, self.transfers, self.progress = store, transfers, progress

    def handle(self, command, binding, classification):
        if command.kind == "POLICY_GET": return self.store.policy(binding)
        if command.kind == "POLICY_SAVE":
            if command.policy is None or command.policy.binding != binding:
                raise ReadError("Settings must belong to the current connection")
            return self.store.save_policy(command.policy)
        if command.kind == "BATCH_PREPARE": return self.prepare(command, binding, classification)
        if command.kind == "BATCH_APPROVE": return self.store.approve(command)
        if command.kind == "BATCH_GET": return self.store.get(command.batch_id, binding)
        if command.kind == "BATCH_LIST": return self.store.history(binding, command.offset)
        if command.kind == "BATCH_CANCEL": return self.store.cancel(command.batch_id, binding)
        if command.kind == "BATCH_STEP": return self.step(command, binding, classification)
        if command.kind == "BATCH_RECOVER":
            for record in self.transfers.store.reconciliation_candidates(binding):
                if record.attempted and record.target and record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    kind = "TRANSFER_RECONCILE" if record.preview.kind == "TRANSFER" else "EXP_RECONCILE"
                    if kind == "TRANSFER_RECONCILE":
                        child = command.model_copy(update={"kind": kind, "experiment_id": record.preview.id})
                        self.transfers.handle(child, binding, classification)
            self.store.release_resolved(binding)
            return self.store.history(binding)
        raise ReadError("Unsupported batch action")

    def prepare(self, command, binding, classification):
        policy = self.store.policy(binding)
        if policy is None:
            raise ReadError("Save operator and field policy in Settings first")
        sources = command.sources
        if not 1 <= len(sources) <= 100 or len({(r.side, r.identity) for r in sources}) != len(sources):
            raise ReadError("Select 1–100 unique source parties")
        side = sources[0].side
        direction = Direction.TO_TALLY if side == Side.BAHI else Direction.TO_BAHI
        if any(s.side != side or s.binding != binding for s in sources) or command.direction != direction:
            raise ReadError("A batch must use one current source side and destination")
        t = self.transfers
        t._context(binding)
        bahi, tally = t.readers(classification)
        source_reader, target_reader = (bahi, tally) if side == Side.BAHI else (tally, bahi)
        scan = target_reader.scan(binding)
        if scan.binding != binding or scan.side == side or not scan.coverage_complete or scan.failed_pages:
            raise ReadError("Complete destination coverage is required; refresh connections")
        destination = t.destinations(direction, classification)
        names = destination.collision_names(binding, scan)
        names = {search_name(name) for name in names}
        selected_names = {}
        selected_gstin = {}
        refreshed, failures = {}, {}
        for expected in sources:
            try:
                current = source_reader.detail(binding, expected.identity)
                if current.binding != binding or current.side != side or current.identity != expected.identity:
                    raise ReadError("Source identity changed")
                if not timedelta(0) <= datetime.now(timezone.utc) - current.observed_at <= timedelta(minutes=5):
                    raise ReadError("Source detail is stale")
                t._eligible(current)
                refreshed[expected.identity] = current
            except (ReadError, ValueError) as error:
                failures[expected.identity] = str(error)
        for source in refreshed.values():
            selected_names.setdefault(search_name(source.content.name), []).append(source.identity)
            if source.content.gstin:
                selected_gstin.setdefault((source.party_type, source.content.gstin), []).append(source.identity)
        included = policy.to_tally if direction == Direction.TO_TALLY else policy.to_bahi
        items = []
        for number, expected in enumerate(sources, 1):
            self.progress("Preparing", f"{number}/{len(sources)}")
            try:
                if expected.identity in failures:
                    raise ReadError(failures[expected.identity])
                source = refreshed[expected.identity]
                linked = t.links.find(binding, source.side, source.identity)
                if linked:
                    items.append(BatchItem(source=source, status="Already linked", message=f"Saved link {linked.id}"))
                    continue
                if (len(selected_names[search_name(source.content.name)]) > 1 or
                    (source.content.gstin and len(selected_gstin[(source.party_type, source.content.gstin)]) > 1)):
                    raise ReadError("Selected sources collide by name or GSTIN; review them separately")
                candidates = tuple(row for row in scan.records if search_name(row.content.name) == search_name(source.content.name)
                    or (row.party_type == source.party_type and source.content.gstin and row.content.gstin == source.content.gstin))
                if candidates or search_name(source.content.name) in names:
                    items.append(BatchItem(source=source, status="Needs review", candidates=candidates,
                        message="Possible destination match; review an existing identity link"))
                    continue
                exclusions = {f: f"Saved field policy v{policy.version}: field disabled" for f in OPTIONAL_FIELDS if f not in included}
                # Validation may expose dependencies after an optional value is omitted.
                for _ in range(len(OPTIONAL_FIELDS) + 1):
                    draft, decisions = select_fields(source, destination, exclusions)
                    invalid = [d for d in decisions if d.field in OPTIONAL_FIELDS and d.status in {"invalid", "unavailable"}]
                    if not invalid: break
                    exclusions.update({d.field: f"Saved policy v{policy.version}: {d.reason}" for d in invalid})
                if any(d.status in {"invalid", "unavailable"} for d in decisions):
                    raise ReadError("Required name cannot be represented by the destination")
                now = datetime.now(timezone.utc)
                preview = ExperimentPreview(id=str(uuid4()), binding=binding, generation=command.generation,
                    direction=direction, party=draft, preflight=destination.preflight(binding, draft),
                    created_at=now, expires_at=now + timedelta(minutes=5), kind="TRANSFER", source=source,
                    decisions=decisions, source_confirmation_required=source.is_system is None)
                items.append(BatchItem(source=source, status="Ready", preview=preview))
            except (ReadError, ValueError) as error:
                items.append(BatchItem(source=expected, status="Needs review", message=str(error)))
        batch = TransferBatch(id=str(uuid4()), binding=binding, generation=command.generation,
            direction=direction, policy=policy, created_at=datetime.now(timezone.utc), items=tuple(items))
        return self.store.save_draft(batch)

    def step(self, command, binding, classification):
        if not self.store.activate(command):
            self.store.finish_step(command, pause=True)
            return self.store.get(command.batch_id, binding)
        batch = self.store.get(command.batch_id, binding)
        record = self.transfers.store.get(command.experiment_id, binding)
        child = command.model_copy(update={"kind": "TRANSFER_CREATE", "direction": batch.direction,
            "approval_digest": record.preview.digest, "reviewer": batch.policy.operator,
            "source_normal_party_confirmed": batch.normal_confirmed})
        pause = True
        try:
            result = self.transfers.handle(child, binding, classification)
            pause = result.state not in {"SUCCEEDED", "FAILED"}
        except Exception as error:
            latest = self.transfers.store.get(record.preview.id, binding)
            if latest.attempted and latest.state in {"APPLYING", "VERIFYING", "RECONCILING"}:
                self.transfers.store.result(record.preview.id, command.id,
                    "VERIFYING" if latest.target else "OUTCOME_UNKNOWN", message="Interrupted execution; reads only, never recreate")
            elif not latest.attempted:
                self.transfers.store.result(record.preview.id, command.id, "PENDING",
                    message=str(error) if isinstance(error, ValueError) else "Local execution failed before transmission; refresh and review again")
        self.store.finish_step(command, pause=pause)
        return self.store.get(command.batch_id, binding)
