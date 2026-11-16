"""Offline application -> shared lifecycle -> real SQLite integration; no live IO."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from innoforia_tally_connector.application.masters.transfers import PartyTransferWorkflow
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import Direction, Preflight, TargetIdentity, UncertainWrite
from innoforia_tally_connector.domain.masters import PartyContent, PartyScan, Side, PartyType, ConfirmedPartyLink, LinkConflict
from innoforia_tally_connector.domain.party_transfer import TransferReview
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import link_audit


@pytest.fixture
def transfer_rig(store, binding, observation):
    journal, records = DiscoveryStore(store.engine), ExperimentStore(store.engine)
    state = SimpleNamespace(side=Side.BAHI, kind=PartyType.SUPPLIER, creates=0, reads=0, error=None,
        mismatch=False, unavailable=False, after_create=None, candidates=(), collisions=(), incomplete=False,
        context=Preflight(group_context='{"group":"reviewed test root"}', destination="Synthetic destination"))
    state.source = observation(content=PartyContent(name="Actual test party", email="party@example.invalid"),
                               content_schema=2, is_active=True, is_system=False)
    class Reader:
        def __init__(self, side): self.side = side
        def detail(self, binding, identity):
            assert self.side == state.source.side and identity == state.source.identity
            return state.source.model_copy(update={"observed_at": datetime.now(timezone.utc)})
        def scan(self, binding):
            return PartyScan(binding=binding, side=self.side, records=state.candidates,
                observed_at=datetime.now(timezone.utc), pages_read=(1,) if state.candidates else (),
                total_pages=None if state.incomplete else (1 if state.candidates else 0))
    class Destination:
        def validate(self, draft): return {}
        def collisions(self, binding, name): return state.collisions
        def preflight(self, binding, draft): return state.context
        def create(self, preview, preflight):
            state.creates += 1
            if state.after_create: state.after_create()
            if state.error: raise state.error
            side = Side.TALLY if state.source.side == Side.BAHI else Side.BAHI
            return TargetIdentity(kind="TALLY_GUID" if side == Side.TALLY else "BAHI_ID", identity="900")
        def read_back(self, preview, target):
            state.reads += 1
            if state.unavailable: raise RuntimeError("offline")
            side = Side.TALLY if preview.source.side == Side.BAHI else Side.BAHI
            content = preview.party.model_dump(exclude={"party_type"}, exclude_unset=True)
            if state.mismatch: content["email"] = "changed@example.invalid"
            observed = observation(side, target.identity, content=PartyContent(**content), party_type=preview.source.party_type,
                                   content_schema=2, is_active=True, is_system=False)
            return observed, target, True
    destination = Destination()
    workflow = PartyTransferWorkflow(records, lambda _: (Reader(Side.BAHI), Reader(Side.TALLY)),
        lambda *_: destination, lambda: SimpleNamespace(business_id=binding.business_id, company_guid=binding.company_guid), store)
    def run(kind, **values):
        command = Command(id=str(uuid4()), kind=kind, generation=1, binding=binding, **values)
        journal.capture(command)
        claimed = journal.claim(command.id)
        assert claimed
        try:
            result = workflow.handle(claimed, binding, None)
        except Exception as error:
            journal.finish(command.id, str(error))
            raise
        journal.finish(command.id)
        return result
    def prepare(**kwargs):
        return run("TRANSFER_PREPARE", source=state.source,
            direction=Direction.TO_TALLY if state.source.side == Side.BAHI else Direction.TO_BAHI, **kwargs)
    def create(record, **changes):
        values = dict(experiment_id=record.preview.id, direction=record.preview.direction,
                      approval_digest=record.preview.digest, reviewer="Manual test reviewer")
        values.update(changes)
        return run("TRANSFER_CREATE", **values)
    return SimpleNamespace(**locals())


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
@pytest.mark.parametrize("kind", [PartyType.CUSTOMER, PartyType.SUPPLIER])
def test_each_direction_type_creates_once_and_atomically_links(transfer_rig, side, kind):
    r = transfer_rig
    r.state.source = r.state.source.model_copy(update={"side": side, "party_type": kind})
    preview = r.prepare()
    result = r.create(preview)
    assert result.state == "SUCCEEDED" and all(result.comparisons.values())
    link = r.store.by_id(result.preview.id)
    assert link.bahi.side == Side.BAHI and link.tally.side == Side.TALLY
    assert link.confirmed_by == "Manual test reviewer"
    assert r.create(preview).state == "SUCCEEDED" and r.state.creates == 1
    assert r.run("TRANSFER_RECONCILE", experiment_id=preview.preview.id).state == "SUCCEEDED"
    assert r.state.creates == 1
    assert ExperimentStore(r.store.engine).get(result.preview.id, r.binding) == result
    with r.store.engine.connect() as connection:
        assert connection.execute(select(link_audit.c.link_id)).scalar_one() == link.id
    already = r.prepare()
    assert isinstance(already, TransferReview) and already.record.id == link.id


def test_candidates_all_visible_and_never_dismissible(transfer_rig, observation):
    r = transfer_rig
    r.state.candidates = tuple(observation(Side.TALLY, str(i), name=" actual   TEST party ") for i in (2, 3))
    result = r.prepare()
    assert isinstance(result, TransferReview) and len(result.candidates) == 2
    assert not r.records.history(r.binding).records and r.state.creates == 0
    r.state.candidates = ()
    r.state.collisions = ("Non-party exact name collision",)
    assert "collision" in r.prepare().message


def test_incomplete_scan_blocks_prepare(transfer_rig):
    transfer_rig.state.incomplete = True
    with pytest.raises(ValueError, match="coverage"): transfer_rig.prepare()
    assert transfer_rig.state.creates == 0


@pytest.mark.parametrize("condition", ["changed", "context", "digest", "direction", "expired", "inactive", "system"])
def test_invalidated_approval_causes_zero_creates(transfer_rig, condition):
    r = transfer_rig
    preview = r.prepare()
    changes = {}
    if condition == "changed": r.state.source = r.state.source.model_copy(update={"version": "changed"})
    if condition == "context": r.state.context = Preflight(group_context="changed", destination="other")
    if condition == "digest": changes["approval_digest"] = "changed"
    if condition == "direction": changes["direction"] = Direction.TO_BAHI
    if condition == "inactive": r.state.source = r.state.source.model_copy(update={"is_active": False})
    if condition == "system": r.state.source = r.state.source.model_copy(update={"is_system": True})
    if condition == "expired":
        from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
        old = preview.preview.model_copy(update={"created_at": datetime.now(timezone.utc) - timedelta(minutes=7),
                                               "expires_at": datetime.now(timezone.utc) - timedelta(minutes=2)})
        with r.store.engine.begin() as c:
            c.execute(experiments.update().where(experiments.c.id == old.id).values(preview_json=old.model_dump_json(exclude_unset=True)))
        preview = r.records.get(old.id, r.binding)
    with pytest.raises(ValueError): r.create(preview, **changes)
    assert r.state.creates == 0


def test_reservation_blocks_second_preview_and_manual_link(transfer_rig, observation):
    r = transfer_rig
    preview = r.prepare()
    with pytest.raises(ValueError, match="active|unresolved"): r.prepare()
    link = ConfirmedPartyLink(id="manual", binding=r.binding, bahi=r.state.source,
        tally=observation(Side.TALLY, "2"), confirmed_by="Reviewer", confirmed_at=datetime.now(timezone.utc), review_reference="manual")
    with pytest.raises(LinkConflict, match="reserves"): r.store.save(link)
    assert not r.store.list(r.binding)
    r.run("TRANSFER_CANCEL", experiment_id=preview.preview.id)
    r.store.save(link)
    assert r.store.by_id(link.id)


def test_field_revision_cancel_and_history_do_not_hide_completed(transfer_rig):
    r = transfer_rig
    complete = r.create(r.prepare())
    r.state.source = r.state.source.model_copy(update={"identity": "second", "content": PartyContent(name="Second", email="p@example.invalid")})
    first = r.prepare()
    revised = r.prepare(experiment_id=first.preview.id, exclusions={"email": "Do not transfer this contact"})
    assert r.records.get(first.preview.id, r.binding).state == "CANCELLED"
    assert revised.preview.party.model_fields_set == {"name", "party_type"}
    history = r.records.history(r.binding)
    assert {record.preview.id for record in history.records} == {complete.preview.id, first.preview.id, revised.preview.id}
    assert r.records.history(r.binding, status="SUCCEEDED").records == (complete,)
    assert r.records.history(r.binding, kind="EXPERIMENT").records == ()
    r.run("TRANSFER_CANCEL", experiment_id=revised.preview.id)
    assert r.create(revised).state == "CANCELLED"
    assert r.state.creates == 1


@pytest.mark.parametrize("known_id", [False, True])
def test_uncertain_restart_is_read_only_and_blocks_new_creation(transfer_rig, known_id):
    r = transfer_rig
    r.state.error = UncertainWrite("timeout", TargetIdentity(kind="TALLY_GUID", identity="900") if known_id else None)
    result = r.create(r.prepare())
    assert result.state == "OUTCOME_UNKNOWN"
    r.journal.recover(r.store)
    with pytest.raises(ValueError): r.prepare()
    assert r.create(result).attempted and r.state.creates == 1
    result = r.run("TRANSFER_RECONCILE", experiment_id=result.preview.id)
    assert result.state == ("SUCCEEDED" if known_id else "OUTCOME_UNKNOWN")
    assert r.state.creates == 1 and r.state.reads == (1 if known_id else 0)


def test_mapping_failure_rolls_back_and_reconciliation_only_finishes_local_commit(transfer_rig):
    r = transfer_rig
    def fail_audit(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO party_link_audit"):
            raise RuntimeError("Injected local audit failure")
    event.listen(r.store.engine, "before_cursor_execute", fail_audit)
    try:
        result = r.create(r.prepare())
        assert result.state == "VERIFYING" and result.target.identity == "900"
        assert not r.store.list(r.binding)
    finally:
        event.remove(r.store.engine, "before_cursor_execute", fail_audit)
    result = r.run("TRANSFER_RECONCILE", experiment_id=result.preview.id)
    assert result.state == "SUCCEEDED" and r.state.creates == 1


def test_readback_mismatch_or_changed_source_after_creation_never_recreates(transfer_rig):
    r = transfer_rig
    r.state.mismatch = True
    result = r.create(r.prepare())
    assert result.state == "BLOCKED" and result.comparisons["email"] is False
    with pytest.raises(ValueError): r.prepare()
    r.state.mismatch = False
    r.state.source = r.state.source.model_copy(update={"version": "changed after create"})
    result = r.run("TRANSFER_RECONCILE", experiment_id=result.preview.id)
    assert result.state == "VERIFYING" and not r.store.list(r.binding)
    assert r.state.creates == 1


def test_exclusions_are_in_the_mapping_audit(transfer_rig):
    r = transfer_rig
    result = r.create(r.prepare(exclusions={"email": "Owner deliberately excluded contact"}))
    link = r.store.by_id(result.preview.id)
    assert link.transfer_exclusions == {"email": "Owner deliberately excluded contact"}
    assert "email" not in link.transfer_fields and link.bahi.content.email == "party@example.invalid"
    assert "email" not in link.tally.content.model_fields_set
    with r.store.engine.connect() as connection:
        raw = connection.execute(select(link_audit.c.evidence_json)).scalar_one()
        assert "Owner deliberately excluded contact" in raw


def test_unavailable_system_flag_requires_recorded_reviewer_confirmation(transfer_rig):
    r = transfer_rig
    r.state.source = r.state.source.model_copy(update={"is_system": None})
    preview = r.prepare()
    assert preview.preview.source_confirmation_required
    with pytest.raises(ValueError, match="confirmation"): r.create(preview)
    assert r.state.creates == 0 and not r.records.get(preview.preview.id, r.binding).attempted
    result = r.create(preview, source_normal_party_confirmed=True)
    assert result.state == "SUCCEEDED" and result.source_normal_party_confirmed
    assert "system flag unavailable" in r.store.by_id(result.preview.id).source_eligibility_evidence
    assert r.state.creates == 1


@pytest.mark.parametrize("boundary", ["before_send", "after_target_commit", "after_saved_receipt"])
def test_transfer_interruption_never_recreates(transfer_rig, monkeypatch, boundary):
    r = transfer_rig
    prepared = r.prepare()
    if boundary == "before_send":
        monkeypatch.setattr(r.destination, "create", lambda *args: (_ for _ in ()).throw(SystemExit("crash")))
    elif boundary == "after_target_commit":
        r.state.error = SystemExit("remote committed, receipt not saved")
    else:
        monkeypatch.setattr(r.destination, "read_back", lambda *args: (_ for _ in ()).throw(SystemExit("receipt saved, verification interrupted")))
    with pytest.raises(SystemExit): r.create(prepared)
    r.journal.recover(r.store)
    restored = r.records.get(prepared.preview.id, r.binding)
    assert restored.state == "OUTCOME_UNKNOWN" and restored.attempted
    assert (restored.target is not None) == (boundary == "after_saved_receipt")
    before = r.state.creates
    assert r.create(restored).state == "OUTCOME_UNKNOWN"
    assert r.state.creates == before
    with pytest.raises(ValueError): r.prepare()
