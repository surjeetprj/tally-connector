"""Version-5 upgrade backs up existing journals and rolls back partial DDL."""
import sqlite3
from types import SimpleNamespace
import pytest
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions import v0005_batches
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks
from innoforia_tally_connector.domain.experiments import new_preview, Direction, synthetic_supplier, Preflight


def test_v5_backup_preserves_v4_pending_and_completed_evidence(tmp_path, binding, monkeypatch):
    engine = metadata_engine(tmp_path / "upgrade.db")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:4])
            runner.migrate(engine)
        SqlPartyLinks(engine).register_binding(binding)
        records = ExperimentStore(engine)
        preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(destination="Synthetic", group_context="root"))
        records.save_preview(preview)
        runner.migrate(engine)
        assert records.get(preview.id, binding).state == "PENDING"
        with engine.connect() as c:
            assert c.exec_driver_sql("PRAGMA user_version").scalar_one() == runner.MIGRATIONS[-1].VERSION
            assert c.exec_driver_sql("SELECT count(*) FROM party_batch_members").scalar_one() == 0
        with sqlite3.connect(next(tmp_path.glob("*.backup"))) as c:
            assert c.execute("PRAGMA user_version").fetchone()[0] == 4
            assert c.execute("SELECT id FROM party_experiments").fetchone()[0] == preview.id
    finally: engine.dispose()


def test_v5_partial_tables_rollback(tmp_path, monkeypatch):
    engine = metadata_engine(tmp_path / "rollback.db")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS[:4]); runner.migrate(engine)
        def broken(c):
            v0005_batches.upgrade(c)
            raise RuntimeError("Injected failure after batch tables")
        with monkeypatch.context() as patch:
            patch.setattr(runner, "MIGRATIONS", (*runner.MIGRATIONS[:4], SimpleNamespace(VERSION=5, upgrade=broken)))
            with pytest.raises(RuntimeError): runner.migrate(engine)
        with engine.connect() as c:
            assert c.exec_driver_sql("PRAGMA user_version").scalar_one() == 4
            assert not c.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='party_batches'").first()
        runner.migrate(engine)
    finally: engine.dispose()
