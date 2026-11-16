"""Real SQLite approvals/outbox/attempts, synthetic remote systems only."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select, update
from innoforia_tally_connector.application.masters.batches import BatchWorkflow
from innoforia_tally_connector.application.masters.transfers import PartyTransferWorkflow
from innoforia_tally_connector.domain.batches import BatchApproval, TransferPolicy
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import Direction, Preflight, TargetIdentity, UncertainWrite, WriteRejected
from innoforia_tally_connector.domain.masters import Side, PartyContent, PartyScan, PartyType, ConfirmedPartyLink
from innoforia_tally_connector.persistence.repositories.batches import BatchStore
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.migrations.versions.v0005_batches import batches


@pytest.fixture
def rig(store, binding, observation):
    journal, records, batch_store = DiscoveryStore(store.engine), ExperimentStore(store.engine), BatchStore(store.engine)
    state = SimpleNamespace(creates=[], failures={}, destination={}, scans=0, collisions=0, context="root", mismatch=False)
    sources = {str(i): observation(identity=str(i), name=f"Party {i}", is_active=True, is_system=None, content_schema=2,
        content=PartyContent(name=f"Party {i}", email=f"party{i}@example.invalid", phone="00123")) for i in range(1, 4)}
    class Reader:
        def __init__(self, side): self.side = side
        def detail(self, binding, identity):
            return sources[identity].model_copy(update={"observed_at": datetime.now(timezone.utc)})
        def scan(self, binding):
            state.scans += 1
            rows = tuple(state.destination.values())
            return PartyScan(binding=binding, side=self.side, records=rows, observed_at=datetime.now(timezone.utc),
                pages_read=(1,) if rows else (), total_pages=1 if rows else 0)
    class Destination:
        def validate(self, draft):
            return {"email": "Invalid email"} if draft.email == "invalid" else {}
        def collision_names(self, binding, scan=None):
            state.collisions += 1
            return tuple(r.content.name for r in state.destination.values())
        def collisions(self, binding, name):
            return tuple(n for n in self.collision_names(binding) if n.casefold() == name.casefold())
        def preflight(self, binding, draft): return Preflight(destination="Synthetic", group_context=state.context)
        def create(self, preview, preflight):
            identity = preview.source.identity
            state.creates.append(identity)
            if identity in state.failures: raise state.failures[identity]
            side = Side.TALLY if preview.source.side == Side.BAHI else Side.BAHI
            target = TargetIdentity(kind="TALLY_GUID" if side == Side.TALLY else "BAHI_ID", identity="target" + identity)
            state.destination[target.identity] = observation(side, target.identity,
                party_type=preview.source.party_type, is_active=True, content_schema=2,
                content=PartyContent(**preview.party.model_dump(exclude={"party_type"}, exclude_unset=True)))
            return target
        def read_back(self, preview, target):
            row = state.destination[target.identity]
            if state.mismatch: row = row.model_copy(update={"content": PartyContent(name="Changed")})
            return row, target, True
    destination = Destination()
    transfers = PartyTransferWorkflow(records, lambda _: (Reader(Side.BAHI), Reader(Side.TALLY)),
        lambda *_: destination, lambda: SimpleNamespace(business_id=binding.business_id, company_guid=binding.company_guid), store)
    workflow = BatchWorkflow(batch_store, transfers)
    batch_store.save_policy(TransferPolicy(binding=binding, operator="Owner"))
    def execute(command):
        claimed = journal.claim(command.id)
        if not claimed: return None
        try:
            result = workflow.handle(claimed, binding, None)
        except Exception as error:
            journal.finish(command.id, str(error))
            raise
        journal.finish(command.id)
        journal.dispatched(command.id)
        return result
    def run(kind, **kwargs):
        command = Command(id=str(uuid4()), kind=kind, generation=1, binding=binding, **kwargs)
        journal.capture(command)
        return execute(command)
    def prepare(ids=("1", "2", "3")):
        side = sources[ids[0]].side
        return run("BATCH_PREPARE", sources=tuple(sources[i] for i in ids),
            direction=Direction.TO_TALLY if side == Side.BAHI else Direction.TO_BAHI)
    def approve(batch, **kwargs):
        values = dict(batch_id=batch.id, digest=batch.digest,
            ready_ids=tuple(i.preview.id for i in batch.items if i.status == "Ready"), normal_confirmed=True)
        values.update(kwargs)
        return run("BATCH_APPROVE", approval=BatchApproval(**values))
    def pump(one=False):
        for _ in range(101):
            pending = [journal.command(i) for i in journal.pending() if journal.command(i).kind == "BATCH_STEP"]
            if not pending: break
            journal.dispatched(pending[0].id)
            execute(pending[0])
            if one: return pending[0]
        else: pytest.fail("Unbounded dispatch loop")
    return SimpleNamespace(**locals())


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
@pytest.mark.parametrize("kind", [PartyType.CUSTOMER, PartyType.SUPPLIER])
def test_batch_creates_once_and_persists_mapping_per_party(rig, side, kind):
    r = rig
    for identity, source in r.sources.items():
        r.sources[identity] = source.model_copy(update={"side": side, "party_type": kind})
    batch = r.prepare()
    assert r.state.scans == 1 and r.state.collisions == 1
    assert not r.state.creates and all(i.status == "Ready" for i in batch.items)
    r.approve(batch)
    first_command = r.pump(one=True)
    assert r.state.creates == ["1"]
    assert r.execute(first_command) is None
    r.pump()
    restored = BatchStore(r.store.engine).get(batch.id, r.binding)
    assert restored.state == "SUCCEEDED" and r.state.creates == ["1", "2", "3"]
    for item in restored.items:
        assert item.result.source_normal_party_confirmed and item.result.reviewer == "Owner"
        link = r.store.by_id(item.preview.id)
        assert link.transfer_exclusions["gstin"].startswith("Saved field policy")
        assert link.source_eligibility_evidence.startswith("Named reviewer")
        assert all(item.result.comparisons.values())


@pytest.mark.parametrize("change", ["digest", "subset", "confirmation", "expired", "policy"])
def test_invalid_batch_approval_has_zero_attempts(rig, change):
    r = rig
    batch = r.prepare()
    kwargs = {}
    if change == "digest": kwargs["digest"] = "wrong"
    if change == "subset": kwargs["ready_ids"] = (batch.items[0].preview.id,)
    if change == "confirmation": kwargs["normal_confirmed"] = False
    if change == "policy": r.batch_store.save_policy(r.batch_store.policy(r.binding).model_copy(update={"operator": "Changed"}))
    if change == "expired":
        items = tuple(i.model_copy(update={"preview": i.preview.model_copy(update={
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=10), "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5)})}) for i in batch.items)
        batch = batch.model_copy(update={"items": items})
        with r.store.engine.begin() as c:
            c.execute(update(batches).where(batches.c.id == batch.id).values(evidence=batch.model_dump_json()))
    with pytest.raises(ValueError): r.approve(batch, **kwargs)
    assert not r.state.creates and not r.records.history(r.binding).records


def test_ready_subset_policy_omissions_and_internal_collisions(rig):
    r = rig
    r.sources["1"] = r.sources["1"].model_copy(update={"content": PartyContent(name="Party 1", email="invalid")})
    r.sources["2"] = r.sources["2"].model_copy(update={"content": PartyContent(name="Collision")})
    r.sources["3"] = r.sources["3"].model_copy(update={"content": PartyContent(name=" collision ")})
    batch = r.prepare()
    assert [i.status for i in batch.items] == ["Ready", "Needs review", "Needs review"]
    assert "email" not in batch.items[0].preview.party.model_fields_set
    assert any(d.field == "email" and "Invalid email" in d.reason for d in batch.items[0].preview.decisions)
    r.approve(batch); r.pump()
    assert r.state.creates == ["1"]


@pytest.mark.parametrize("failure", ["unknown", "rejected", "mismatch"])
def test_uncertainty_pauses_but_authoritative_rejection_continues(rig, failure):
    r = rig
    batch = r.prepare()
    if failure == "unknown": r.state.failures["1"] = UncertainWrite("Lost acknowledgement")
    elif failure == "rejected": r.state.failures["1"] = WriteRejected("Permission refused")
    else: r.state.mismatch = True
    r.approve(batch); r.pump()
    result = r.batch_store.get(batch.id, r.binding)
    if failure == "rejected":
        assert r.state.creates == ["1", "2", "3"] and result.state == "FAILED"
    else:
        assert r.state.creates == ["1"] and result.state == "BLOCKED"
        assert result.items[1].result.state == "CANCELLED"
        other = r.prepare(("2",))
        with pytest.raises(ValueError): r.approve(other)
        with pytest.raises(ValueError): r.records.save_preview(batch.items[1].preview)


def test_cancel_and_restart_never_send_remaining_creates(rig):
    r = rig
    batch = r.prepare(); r.approve(batch); r.pump(one=True)
    r.run("BATCH_CANCEL", batch_id=batch.id)
    r.pump()
    assert r.state.creates == ["1"]
    assert r.batch_store.get(batch.id, r.binding).state == "CANCELLED"
    newer = r.prepare(("2", "3")); r.approve(newer)
    r.journal.recover(r.store)
    r.pump()
    assert r.state.creates == ["1"]
    assert r.batch_store.get(newer.id, r.binding).state == "BLOCKED"
    assert not [r.journal.command(i) for i in r.journal.pending() if r.journal.command(i).kind == "BATCH_STEP"]


def test_changed_source_before_send_pauses_without_attempt(rig):
    r = rig
    batch = r.prepare(); r.approve(batch)
    r.sources["1"] = r.sources["1"].model_copy(update={"content": PartyContent(name="Changed")})
    r.pump()
    assert not r.state.creates
    assert r.batch_store.get(batch.id, r.binding).state == "BLOCKED"
    assert not r.records.get(batch.items[0].preview.id, r.binding).attempted


def test_obsolete_drafts_superseded_approved_history_unchanged(rig):
    r = rig
    old = r.prepare(); newer = r.prepare()
    assert r.batch_store.get(old.id, r.binding).state == "CANCELLED"
    r.approve(newer)
    saved = r.batch_store.save_policy(r.batch_store.policy(r.binding).model_copy(update={"operator": "Next operator"}))
    assert saved.version == 2
    r.pump()
    assert all(i.result.reviewer == "Owner" for i in r.batch_store.get(newer.id, r.binding).items)


def test_known_target_reconciles_then_remaining_requires_new_approval(rig):
    r = rig
    batch = r.prepare(); r.state.mismatch = True
    r.approve(batch); r.pump()
    assert r.state.creates == ["1"]
    r.state.mismatch = False
    r.run("BATCH_RECOVER")
    restored = r.batch_store.get(batch.id, r.binding)
    assert restored.items[0].result.state == "SUCCEEDED"
    assert r.state.creates == ["1"]  # Reconciliation performed reads/local completion only.
    remaining = r.prepare(("2", "3"))
    assert not any(i.result and i.result.attempted for i in remaining.items)
    r.approve(remaining); r.pump()
    assert r.state.creates == ["1", "2", "3"]


def test_cancel_captured_during_io_finishes_current_only(rig, monkeypatch):
    r = rig
    original = r.destination.create
    def create(preview, preflight):
        # Mirrors the dispatch actor persisting the cancel flag while the worker
        # is outside SQLite performing the current remote operation.
        r.batch_store.request_cancel(batch.id, r.binding)
        return original(preview, preflight)
    monkeypatch.setattr(r.destination, "create", create)
    batch = r.prepare(); r.approve(batch); r.pump()
    result = r.batch_store.get(batch.id, r.binding)
    assert result.state == "CANCELLED" and r.state.creates == ["1"]
    assert result.items[0].result.state == "SUCCEEDED"
    assert all(i.result.state == "CANCELLED" for i in result.items[1:])


def test_crash_after_local_completion_before_next_dispatch_never_replays(rig, monkeypatch):
    r = rig
    batch = r.prepare(); r.approve(batch)
    original = r.batch_store.finish_step
    monkeypatch.setattr(r.batch_store, "finish_step", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("dispatch gap")))
    with pytest.raises(RuntimeError): r.pump(one=True)
    monkeypatch.setattr(r.batch_store, "finish_step", original)
    r.journal.recover(r.store); r.pump()
    restored = r.batch_store.get(batch.id, r.binding)
    assert restored.state == "BLOCKED" and r.state.creates == ["1"]
    assert r.store.by_id(restored.items[0].preview.id)
    assert all(i.result.state == "CANCELLED" for i in restored.items[1:])


def test_expiry_between_children_does_not_reuse_approval(rig, monkeypatch):
    import innoforia_tally_connector.application.masters.transfers as module
    r = rig
    batch = r.prepare(); r.approve(batch); r.pump(one=True)
    class Later(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.now(tz) + timedelta(minutes=6)
    monkeypatch.setattr(module, "datetime", Later)
    r.pump()
    result = r.batch_store.get(batch.id, r.binding)
    assert result.state == "BLOCKED" and r.state.creates == ["1"]
    assert "expired" in result.items[1].message


def test_selected_linked_inactive_and_duplicate_records_do_not_create(rig):
    r = rig
    batch = r.prepare(("1",)); r.approve(batch); r.pump()
    r.sources["2"] = r.sources["2"].model_copy(update={"is_active": False})
    # A compatible existing destination candidate for record 3.
    source = r.sources["3"]
    r.state.destination["candidate"] = source.model_copy(update={"side": Side.TALLY, "identity": "candidate"})
    result = r.prepare()
    assert [i.status for i in result.items] == ["Already linked", "Needs review", "Needs review"]
    assert result.items[2].candidates[0].identity == "candidate"
    with pytest.raises(ValueError): r.approve(result)
    assert r.state.creates == ["1"]


def test_pending_legacy_preview_superseded_without_erasing_it(rig):
    from innoforia_tally_connector.domain.experiments import new_preview, synthetic_supplier
    r = rig
    old = new_preview(r.binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(destination="Synthetic", group_context=r.state.context))
    r.records.save_preview(old)
    r.prepare()
    assert r.records.get(old.id, r.binding).state == "CANCELLED"
    assert not r.records.get(old.id, r.binding).attempted


def test_attempted_legacy_operation_blocks_batch_approval(rig):
    from innoforia_tally_connector.domain.experiments import new_preview, synthetic_supplier
    r = rig
    old = new_preview(r.binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(destination="Synthetic", group_context=r.state.context))
    r.records.save_preview(old)
    command = Command(id=str(uuid4()), kind="EXP_CREATE", generation=1, binding=r.binding,
        experiment_id=old.id, direction=old.direction, approval_digest=old.digest, reviewer="Earlier owner")
    r.journal.capture(command); r.journal.claim(command.id)
    r.records.begin_attempt(old, command, old.preflight)
    r.records.result(old.id, command.id, "OUTCOME_UNKNOWN", message="Previous request uncertain")
    new = r.prepare()
    with pytest.raises(ValueError, match="earlier attempted"): r.approve(new)
    assert r.records.get(old.id, r.binding).state == "OUTCOME_UNKNOWN"
    assert not r.state.creates


def test_batch_history_paging_and_binding_scope(rig):
    r = rig
    for _ in range(52): r.prepare(("1",))
    first, second = r.batch_store.history(r.binding), r.batch_store.history(r.binding, 50)
    assert len(first.records) == 50 and first.has_more
    assert len(second.records) == 2 and not second.has_more
    assert not {b.id for b in first.records} & {b.id for b in second.records}
    assert not r.batch_store.history(r.binding.model_copy(update={"generation": 2})).records


def test_competing_batch_approvals_reserve_once(rig):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    r = rig
    batch = r.prepare()
    barrier = Barrier(2)
    def approve():
        barrier.wait(timeout=5)
        try:
            r.approve(batch)
            return "approved"
        except ValueError:
            return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))
    assert sorted(results) == ["approved", "blocked"]
    r.pump()
    assert r.state.creates == ["1", "2", "3"]


def test_mapping_audit_failure_reconciles_without_recreating(rig):
    from sqlalchemy import event
    r = rig
    batch = r.prepare(); r.approve(batch)
    failed = False
    def fail_audit(connection, cursor, statement, *args):
        nonlocal failed
        if "INSERT INTO party_link_audit" in statement and not failed:
            failed = True
            raise RuntimeError("Injected audit failure")
    event.listen(r.store.engine, "before_cursor_execute", fail_audit)
    try: r.pump()
    finally: event.remove(r.store.engine, "before_cursor_execute", fail_audit)
    paused = r.batch_store.get(batch.id, r.binding)
    assert paused.state == "BLOCKED" and r.state.creates == ["1"]
    assert paused.items[0].result.target is not None
    assert not r.store.by_id(paused.items[0].preview.id)
    r.run("BATCH_RECOVER")
    assert r.store.by_id(paused.items[0].preview.id)
    assert r.state.creates == ["1"]


def test_lost_ack_after_target_commit_stays_unknown_without_id(rig, monkeypatch):
    r = rig
    original = r.destination.create
    def lost_ack(preview, preflight):
        original(preview, preflight)
        raise UncertainWrite("Connection lost after target commit")
    monkeypatch.setattr(r.destination, "create", lost_ack)
    batch = r.prepare(); r.approve(batch); r.pump()
    assert r.state.creates == ["1"] and len(r.state.destination) == 1
    record = r.batch_store.get(batch.id, r.binding).items[0].result
    assert record.state == "OUTCOME_UNKNOWN" and record.target is None
    r.journal.recover(r.store); r.run("BATCH_RECOVER"); r.pump()
    assert r.state.creates == ["1"] and r.records.get(record.preview.id, r.binding).state == "OUTCOME_UNKNOWN"


def test_customers_and_suppliers_share_one_direction_batch(rig):
    r = rig
    r.sources["1"] = r.sources["1"].model_copy(update={"party_type": PartyType.CUSTOMER})
    batch = r.prepare(); r.approve(batch); r.pump()
    result = r.batch_store.get(batch.id, r.binding)
    assert result.state == "SUCCEEDED"
    assert [i.result.observation.party_type for i in result.items] == [PartyType.CUSTOMER, PartyType.SUPPLIER, PartyType.SUPPLIER]


def test_preparation_rejects_duplicate_ids_and_mixed_source_sides(rig):
    r = rig
    with pytest.raises(ValueError, match="unique"): r.prepare(("1", "1"))
    r.sources["2"] = r.sources["2"].model_copy(update={"side": Side.TALLY})
    with pytest.raises(ValueError, match="one current source side"): r.prepare()
    assert not r.state.creates
