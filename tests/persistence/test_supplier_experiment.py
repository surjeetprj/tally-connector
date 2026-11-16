"""Real SQLite journal, fake destinations: no live writes in this suite."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func

from innoforia_tally_connector.application.masters.experiments import SupplierExperimentWorkflow
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import (
    Direction, Preflight, TargetIdentity, UncertainWrite, WriteRejected, new_preview, synthetic_supplier,
)
from innoforia_tally_connector.domain.masters import PartyContent
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import attempts


@pytest.fixture
def rig(store, binding, observation):
    journal, experiments = DiscoveryStore(store.engine), ExperimentStore(store.engine)
    class Destination:
        creates = 0
        reads = 0
        error = None
        mismatch = False
        unavailable = False
        context = Preflight(group_context='{"group":"server supplier"}', destination="Synthetic Bahi")
        def preflight(self, binding, party):
            return self.context
        def create(self, preview, current):
            self.creates += 1
            if self.error:
                raise self.error
            return TargetIdentity(kind="BAHI_ID", identity="1000")
        def read_back(self, preview, target):
            self.reads += 1
            assert target.identity == "1000"
            if self.unavailable:
                raise RuntimeError("offline")
            return observation(identity=target.identity, content=PartyContent(name=preview.party.name,
                email="changed@example.invalid" if self.mismatch else preview.party.email)), target, True
    destination = Destination()
    workflow = SupplierExperimentWorkflow(experiments, lambda *args: destination,
        lambda: SimpleNamespace(business_id=binding.business_id, company_guid=binding.company_guid))
    def run(kind, **values):
        command = Command(id=f"op-{len(commands)}", kind=kind, binding=binding, generation=1, **values)
        commands.append(command)
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
    commands = []
    def prepare():
        return run("EXP_PREPARE", direction=Direction.TO_BAHI)
    def create(record):
        return run("EXP_CREATE", experiment_id=record.preview.id, direction=record.preview.direction,
                   approval_digest=record.preview.digest, reviewer="Synthetic reviewer")
    return SimpleNamespace(**locals())


def test_verified_once_and_survives_repository_restart(rig, store, binding):
    result = rig.create(rig.prepare())
    assert result.state == "SUCCEEDED" and all(result.comparisons.values())
    assert result.target.identity == "1000" and result.reviewer == "Synthetic reviewer"
    assert ExperimentStore(store.engine).get(result.preview.id, binding) == result
    assert rig.create(result) == result
    assert rig.destination.creates == 1
    assert store.list(binding) == ()  # Synthetic input must never create a mapping.
    with store.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(attempts)).scalar_one() == 1


@pytest.mark.parametrize("change", ["direction", "digest", "generation", "reviewer", "context", "expired"])
def test_invalid_approval_never_creates(rig, change, binding):
    record = rig.prepare()
    values = dict(experiment_id=record.preview.id, direction=Direction.TO_BAHI,
                  approval_digest=record.preview.digest, reviewer="Reviewer")
    if change == "direction": values["direction"] = Direction.TO_TALLY
    if change == "digest": values["approval_digest"] = "changed"
    if change == "reviewer": values["reviewer"] = " "
    if change == "context": rig.destination.context = Preflight(group_context="changed", destination="other")
    if change == "generation":
        with pytest.raises(ValueError):
            record.preview.require_current(binding, 2, record.preview.digest, datetime.now(timezone.utc))
        assert rig.destination.creates == 0
        return
    if change == "expired":
        old = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), rig.destination.context,
                          datetime.now(timezone.utc) - timedelta(minutes=6))
        rig.experiments.save_preview(old)
        values.update(experiment_id=old.id, approval_digest=old.digest)
    with pytest.raises(ValueError): rig.run("EXP_CREATE", **values)
    assert rig.destination.creates == 0


def test_unselected_direction_and_superseded_preview(rig):
    with pytest.raises(ValueError): rig.run("EXP_PREPARE")
    first = rig.prepare()
    rig.prepare()
    with pytest.raises(ValueError): rig.create(first)
    assert rig.destination.creates == 0


@pytest.mark.parametrize("error", [UncertainWrite("timeout"), RuntimeError("disconnect"), SystemExit("crash")])
def test_uncertain_attempt_never_retries_even_after_restart(rig, store, binding, error):
    prepared = rig.prepare()
    rig.destination.error = error
    if isinstance(error, SystemExit):
        with pytest.raises(SystemExit): rig.create(prepared)
    else:
        assert rig.create(prepared).state == "OUTCOME_UNKNOWN"
    rig.journal.recover(store)
    record = rig.experiments.get(prepared.preview.id, binding)
    assert record.state == "OUTCOME_UNKNOWN"
    # The outer task failure handler cannot turn this into a retryable read failure.
    original = rig.commands[-1]
    rig.journal.finish(original.id, "outer task failure")
    assert rig.experiments.get(prepared.preview.id, binding).state == "OUTCOME_UNKNOWN"
    assert rig.create(record).state == "OUTCOME_UNKNOWN"
    assert rig.run("EXP_RECONCILE", experiment_id=record.preview.id).target is None
    with pytest.raises(ValueError): rig.prepare()
    assert rig.destination.creates == 1 and rig.destination.reads == 0


def test_known_id_reconciles_with_reads_only(rig, store, binding):
    rig.destination.unavailable = True
    record = rig.create(rig.prepare())
    assert record.state == "VERIFYING" and record.target.identity == "1000"
    rig.journal.recover(store)
    rig.destination.unavailable = False
    record = rig.run("EXP_RECONCILE", experiment_id=record.preview.id)
    assert record.state == "SUCCEEDED" and rig.destination.creates == 1


def test_readback_mismatch_blocks_another_experiment(rig):
    rig.destination.mismatch = True
    result = rig.create(rig.prepare())
    assert result.state == "BLOCKED" and result.comparisons["email"] is False
    with pytest.raises(ValueError): rig.prepare()
    assert rig.destination.creates == 1


def test_explicit_refusal_remains_visible_and_is_not_retried(rig):
    rig.destination.error = WriteRejected("Missing party:create permission")
    record = rig.create(rig.prepare())
    assert record.state == "FAILED" and "permission" in record.message
    assert rig.create(record).state == "FAILED" and rig.destination.creates == 1


def test_unsent_create_is_not_replayed_at_startup(rig, store):
    record = rig.prepare()
    command = Command(id="unsent", kind="EXP_CREATE", generation=1, binding=rig.binding,
                      experiment_id=record.preview.id, direction=Direction.TO_BAHI,
                      approval_digest=record.preview.digest, reviewer="Reviewer")
    rig.journal.capture(command)
    rig.journal.recover(store)
    assert "unsent" not in rig.journal.pending()
    with store.engine.connect() as connection:
        assert connection.execute(select(operations.c.state).where(operations.c.id == "unsent")).scalar_one() == "BLOCKED"
    assert rig.destination.creates == 0


@pytest.mark.parametrize("boundary", ["before_send", "after_receipt", "after_local_commit"])
def test_interrupted_boundaries_preserve_evidence(rig, store, binding, monkeypatch, boundary):
    record = rig.prepare()
    if boundary == "before_send":
        def crash(*args): raise SystemExit("crash before transmission")
        monkeypatch.setattr(rig.destination, "create", crash)
    elif boundary == "after_receipt":
        def crash(*args): raise SystemExit("crash during detail")
        monkeypatch.setattr(rig.destination, "read_back", crash)
    if boundary != "after_local_commit":
        with pytest.raises(SystemExit): rig.create(record)
    else:
        result = rig.create(record)
        rig.journal.finish(rig.commands[-1].id, "late outer failure")
        assert rig.experiments.get(record.preview.id, binding) == result
    rig.journal.recover(store)
    restored = ExperimentStore(store.engine).get(record.preview.id, binding)
    assert restored.attempted
    assert restored.state == ("SUCCEEDED" if boundary == "after_local_commit" else "OUTCOME_UNKNOWN")
    assert (restored.target is not None) == (boundary != "before_send")
    # A duplicate after recovery is an inspection, even when no network send occurred.
    before = rig.destination.creates
    rig.create(restored)
    assert rig.destination.creates == before


def test_v2_upgrade_preserves_link_audit_and_consistent_backup(tmp_path, binding, observation, monkeypatch):
    import sqlite3
    from innoforia_tally_connector.persistence.database import metadata_engine
    from innoforia_tally_connector.persistence.migrations import runner
    from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks
    from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, Side
    engine = metadata_engine(tmp_path / "upgrade.db")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:2])
            runner.migrate(engine)
        links = SqlPartyLinks(engine)
        links.register_binding(binding)
        saved = ConfirmedPartyLink(id="preserved-link", binding=binding, bahi=observation(),
            tally=observation(Side.TALLY, "2"), confirmed_by="Reviewer", confirmed_at=datetime.now(timezone.utc),
            review_reference="pre-upgrade")
        links.save(saved)
        runner.migrate(engine)
        assert links.by_id(saved.id) == saved
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 5
            assert connection.exec_driver_sql("SELECT count(*) FROM party_link_audit").scalar_one() == 1
        with sqlite3.connect(next(tmp_path.glob("*.backup"))) as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 2
            assert backup.execute("SELECT link_id FROM party_link_audit").fetchone()[0] == saved.id
    finally:
        engine.dispose()


@pytest.mark.parametrize("save_identity", [False, True])
def test_abrupt_process_exit_retains_attempt(tmp_path, binding, save_identity):
    import subprocess
    import sys
    from innoforia_tally_connector.persistence.database import metadata_engine
    from innoforia_tally_connector.persistence.migrations.runner import migrate
    from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks
    path = tmp_path / "crashed.db"
    code = '''
import os, sys
from pathlib import Path
from innoforia_tally_connector.domain.masters import Binding
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import *
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations.runner import migrate
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
engine = metadata_engine(Path(sys.argv[1])); migrate(engine)
binding = Binding.model_validate_json(sys.argv[2])
store = ExperimentStore(engine); journal = DiscoveryStore(engine)
preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(group_context="synthetic", destination="synthetic"))
store.save_preview(preview)
command = Command(id="crashed-create", kind="EXP_CREATE", generation=1, binding=binding, direction=Direction.TO_BAHI,
    experiment_id=preview.id, approval_digest=preview.digest, reviewer="Synthetic reviewer")
journal.capture(command); journal.claim(command.id); store.begin_attempt(preview, command, preview.preflight)
if sys.argv[3] == "True":
    store.result(preview.id, command.id, "VERIFYING", target=TargetIdentity(kind="BAHI_ID", identity="1000"))
os._exit(23)
'''
    completed = subprocess.run([sys.executable, "-c", code, str(path), binding.model_dump_json(), str(save_identity)],
                               timeout=30, capture_output=True)
    assert completed.returncode == 23, completed.stderr.decode()
    engine = metadata_engine(path)
    try:
        migrate(engine)
        journal = DiscoveryStore(engine)
        journal.recover(SqlPartyLinks(engine))
        record = ExperimentStore(engine).get(None, binding)
        assert record.state == "OUTCOME_UNKNOWN" and record.attempted
        assert (record.target is not None) == save_identity
        assert journal.claim("crashed-create") is None
        with pytest.raises(ValueError):
            ExperimentStore(engine).save_preview(new_preview(binding, 1, Direction.TO_BAHI,
                synthetic_supplier(), Preflight(group_context="synthetic", destination="synthetic")))
    finally:
        engine.dispose()
