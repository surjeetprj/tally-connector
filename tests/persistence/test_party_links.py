from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import event, select

from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, LinkConflict, Side
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import link_audit, party_links
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


def make_link(binding, observation, tally="2"):
    return ConfirmedPartyLink(id=str(uuid4()), binding=binding, bahi=observation(),
                              tally=observation(Side.TALLY, tally), confirmed_by="reviewer",
                              confirmed_at=datetime.now(timezone.utc), review_reference="synthetic review")


def test_restart_and_scoped_uniqueness(store, binding, observation):
    saved = make_link(binding, observation)
    store.save(saved)
    path = store.engine.url.database
    store.engine.dispose()
    reopened = metadata_engine(Path(path))
    try:
        runner.migrate(reopened)
        links = SqlPartyLinks(reopened)
        assert links.find(binding, Side.BAHI, "1") == saved
        with pytest.raises(LinkConflict):
            links.save(make_link(binding, observation, "3"))
        with pytest.raises(LinkConflict):
            links.save(saved.model_copy(update={"id": str(uuid4()), "bahi": observation(identity="9")}))
        with reopened.connect() as connection:
            assert len(connection.execute(select(link_audit)).all()) == 1
    finally:
        reopened.dispose()


def test_concurrent_confirmation_has_one_winner(store, binding, observation):
    candidates = [make_link(binding, observation, str(n)) for n in (2, 3)]
    def save(link):
        try:
            store.save(link)
            return True
        except LinkConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, candidates)) == [False, True]


def test_binding_identity_and_generation_guard(store, binding, observation):
    link = make_link(binding, observation)
    for changed in ({"business_id": 999}, {"company_guid": "other"}, {"generation": 2}):
        wrong = binding.model_copy(update=changed)
        altered = link.model_copy(update={"binding": wrong})
        with pytest.raises(ValueError, match="binding"):
            store.save(altered)


def test_audit_failure_rolls_back_link(store, binding, observation):
    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO party_link_audit"):
            raise RuntimeError("injected audit failure")
    event.listen(store.engine, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            store.save(make_link(binding, observation))
    finally:
        event.remove(store.engine, "before_cursor_execute", fail_audit)
    assert store.find(binding, Side.BAHI, "1") is None


def test_migration_failure_restarts_cleanly(tmp_path, monkeypatch):
    engine = metadata_engine(tmp_path / "metadata.db")
    def broken(connection):
        connection.exec_driver_sql("CREATE TABLE partial (id INTEGER)")
        raise RuntimeError("injected migration failure")
    with monkeypatch.context() as patch:
        patch.setattr(runner, "MIGRATIONS", (SimpleNamespace(VERSION=1, upgrade=broken),))
        with pytest.raises(RuntimeError):
            runner.migrate(engine)
    engine.dispose()
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 0
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='partial'").first() is None
        runner.migrate(engine)
        runner.migrate(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA synchronous").scalar_one() == 2
    finally:
        engine.dispose()


@pytest.mark.parametrize("setup", ["PRAGMA user_version=99", "CREATE TABLE task (id INTEGER)", "PRAGMA application_id=17"])
def test_foreign_or_newer_db_rejected(tmp_path, setup):
    engine = metadata_engine(tmp_path / "foreign.db")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(setup)
        with pytest.raises(ValueError):
            runner.migrate(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='party_links'").first() is None
    finally:
        engine.dispose()


def test_process_exit_during_migration_preserves_version_zero(tmp_path):
    path = tmp_path / "crash.db"
    code = """
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
def crash(connection):
    connection.exec_driver_sql('CREATE TABLE interrupted (id INTEGER)')
    connection.exec_driver_sql('INSERT INTO interrupted VALUES (1)')
    os._exit(23)
runner.MIGRATIONS = (SimpleNamespace(VERSION=1, upgrade=crash),)
runner.migrate(metadata_engine(Path(sys.argv[1])))
"""
    result = subprocess.run([sys.executable, "-c", code, str(path)], timeout=30, capture_output=True)
    assert result.returncode == 23, result.stderr.decode()
    engine = metadata_engine(path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 0
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='interrupted'").first() is None
        runner.migrate(engine)
    finally:
        engine.dispose()
