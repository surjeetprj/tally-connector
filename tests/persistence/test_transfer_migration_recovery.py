from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3

import pytest
from sqlalchemy import insert

from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import Direction, Preflight, synthetic_supplier, new_preview
from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, Side
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions.v0003_experiments import experiments as legacy
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


def test_v3_upgrade_preserves_legacy_results_links_and_backup(tmp_path, binding, observation, monkeypatch):
    path = tmp_path / "metadata.db"
    engine = metadata_engine(path)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:3])
            runner.migrate(engine)
        links = SqlPartyLinks(engine)
        links.register_binding(binding)
        saved = ConfirmedPartyLink(id="prior-link", binding=binding, bahi=observation(), tally=observation(Side.TALLY, "2"),
            confirmed_by="Owner", confirmed_at=datetime.now(timezone.utc), review_reference="old review")
        links.save(saved)
        preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(group_context='{"group":"legacy"}', destination="Test"))
        with engine.begin() as connection:
            connection.execute(insert(legacy).values(id=preview.id, binding_id=binding.id, state="SUCCEEDED",
                preview_json=preview.model_dump_json(exclude_unset=True), reviewer="Owner", target_json='{"kind":"BAHI_ID","identity":"275"}',
                comparisons_json='{"name":true}'))
        runner.migrate(engine)
        assert links.by_id(saved.id) == saved
        record = ExperimentStore(engine).history(binding).records[0]
        assert record.preview.kind == "EXPERIMENT" and record.state == "SUCCEEDED" and record.target.identity == "275"
        with sqlite3.connect(next(tmp_path.glob("*.backup"))) as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 3
            assert backup.execute("SELECT state FROM party_experiments").fetchone()[0] == "SUCCEEDED"
            assert backup.execute("SELECT count(*) FROM party_link_audit").fetchone()[0] == 1
    finally:
        engine.dispose()


def test_history_pages_and_binding_generation_filters(store, binding):
    records = ExperimentStore(store.engine)
    for i in range(52):
        preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(group_context="test", destination="Test"))
        records.save_preview(preview)
        records.cancel(preview.id, binding)
    first, second = records.history(binding), records.history(binding, 50)
    assert len(first.records) == 50 and first.has_more
    assert len(second.records) == 2 and not second.has_more
    assert not {r.preview.id for r in first.records} & {r.preview.id for r in second.records}
    newer = binding.model_copy(update={"generation": 2})
    assert records.history(newer).records == ()
    with pytest.raises(ValueError): records.cancel(first.records[0].preview.id, newer)


def test_pending_transfer_create_never_replays_on_restart(store, binding, observation):
    records, journal = ExperimentStore(store.engine), DiscoveryStore(store.engine)
    legacy_preview = new_preview(binding, 1, Direction.TO_TALLY, synthetic_supplier(), Preflight(group_context="test", destination="Test"))
    preview = legacy_preview.model_copy(update={"kind": "TRANSFER", "source": observation(),
        "party": PartyDraft(name=observation().content.name, party_type=observation().party_type), "source_confirmation_required": True})
    records.save_preview(preview)
    command = Command(id="never-send", kind="TRANSFER_CREATE", binding=binding, generation=1,
        experiment_id=preview.id, direction=preview.direction, approval_digest=preview.digest, reviewer="Owner")
    journal.capture(command)
    journal.recover(store)
    assert journal.claim(command.id) is None and command.id not in journal.pending()
    restored = records.get(preview.id, binding)
    assert restored.state == "PENDING" and not restored.attempted


def test_racing_preview_and_local_link_have_one_winner(store, binding, observation):
    records = ExperimentStore(store.engine)
    source, target = observation(), observation(Side.TALLY, "2")
    preview = new_preview(binding, 1, Direction.TO_TALLY, synthetic_supplier(), Preflight(group_context="test", destination="Test"))
    preview = preview.model_copy(update={"kind": "TRANSFER", "source": source,
        "party": PartyDraft(name=source.content.name, party_type=source.party_type), "source_confirmation_required": True})
    link = ConfirmedPartyLink(id="racing-link", binding=binding, bahi=source, tally=target,
        confirmed_by="Owner", confirmed_at=datetime.now(timezone.utc), review_reference="race")
    def attempt(action):
        try:
            action()
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [executor.submit(attempt, lambda: records.save_preview(preview)), executor.submit(attempt, lambda: store.save(link))]
        assert sum(result.result() for result in outcomes) == 1
    assert (store.by_id(link.id) is not None) != (records.get(preview.id, binding) is not None)


def test_v4_alter_and_index_failure_rolls_back_to_v3(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from innoforia_tally_connector.persistence.migrations.versions import v0004_party_transfers
    engine = metadata_engine(tmp_path / "rollback.db")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:3])
            runner.migrate(engine)
        def broken(connection):
            v0004_party_transfers.upgrade(connection)
            raise RuntimeError("After v4 ALTER/INDEX failure")
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", (*runner.MIGRATIONS[:3], SimpleNamespace(VERSION=4, upgrade=broken)))
            with pytest.raises(RuntimeError): runner.migrate(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 3
            assert "source_key" not in {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(party_experiments)")}
        runner.migrate(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 5
    finally:
        engine.dispose()
