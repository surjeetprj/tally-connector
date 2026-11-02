from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions import v0001_party_links
from innoforia_tally_connector.persistence.migrations.versions.v0002_discovery import operations
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore


def test_capture_coalesce_claim_and_dispatch_gap(store):
    journal = DiscoveryStore(store.engine)
    first = Command(id="first", kind="VERIFY", generation=1)
    assert journal.capture(first) == "first"
    assert journal.capture(Command(id="second", kind="VERIFY", generation=1)) == "first"
    assert journal.pending() == ["first"]
    journal.dispatched("first")
    assert journal.claim("first") == first
    assert journal.claim("first") is None
    journal.recover(store)
    assert journal.pending() == ["first"]
    assert journal.claim("first") == first
    journal.finish("first")
    assert journal.claim("first") is None


def test_interrupted_confirmation_is_not_replayed(store):
    journal = DiscoveryStore(store.engine)
    for kind in ("LINK", "BIND"):
        journal.capture(Command(id=kind, kind=kind, generation=1))
        journal.claim(kind)
    journal.recover(store)
    assert journal.pending() == []
    with store.engine.connect() as connection:
        rows = connection.execute(select(operations)).mappings().all()
        assert all(row["state"] == "BLOCKED" and "renewed review" in row["error"] for row in rows)


def test_link_commit_before_operation_completion_is_recovered(store, binding, observation, reader):
    from innoforia_tally_connector.application.masters.mappings import confirm_party_link
    from innoforia_tally_connector.domain.masters import Side
    journal = DiscoveryStore(store.engine)
    journal.capture(Command(id="local-link", kind="LINK", generation=1, binding=binding))
    journal.claim("local-link")
    left, right = observation(), observation(Side.TALLY, "2")
    saved = confirm_party_link(binding, left, right, bahi=reader([left]), tally=reader([right]),
        links=store, confirmed_by="Synthetic reviewer", review_reference="test", link_id="local-link")
    journal.recover(store)
    assert store.by_id("local-link") == saved
    with store.engine.connect() as connection:
        assert connection.execute(select(operations.c.state)).scalar_one() == "SUCCEEDED"
    assert journal.pending() == []


def test_upgrade_has_consistent_backup_and_rollback(tmp_path, monkeypatch):
    path = tmp_path / "metadata.db"
    engine = metadata_engine(path)
    with monkeypatch.context() as patch:
        patch.setattr(runner, "MIGRATIONS", (v0001_party_links,))
        runner.migrate(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO company_bindings VALUES ('preserved',1,52,'company')")
    def broken(connection):
        connection.exec_driver_sql("CREATE TABLE partial_upgrade (id INTEGER)")
        raise RuntimeError("injected upgrade failure")
    with monkeypatch.context() as patch:
        patch.setattr(runner, "MIGRATIONS", (v0001_party_links, SimpleNamespace(VERSION=2, upgrade=broken)))
        with pytest.raises(RuntimeError):
            runner.migrate(engine)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='partial_upgrade'").first() is None
        backup = next(tmp_path.glob("*.backup"))
        with sqlite3.connect(backup) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
            assert connection.execute("SELECT id FROM company_bindings").fetchone()[0] == "preserved"
        runner.migrate(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT id FROM company_bindings").scalar_one() == "preserved"
            assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == 2
    finally:
        engine.dispose()


def test_command_roundtrip_preserves_missing_fields(store, observation):
    journal = DiscoveryStore(store.engine)
    expected = observation()
    command = Command(id="missing-versus-null", kind="LINK", generation=1, bahi=expected)
    journal.capture(command)
    restored = journal.claim(command.id)
    assert restored.bahi.comparison() == expected.comparison()
    assert "phone" not in restored.bahi.content.model_fields_set


def test_saved_links_have_bounded_stable_pages(store, binding, observation):
    from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, Side
    from datetime import datetime, timezone
    for identity in range(1, 202):
        store.save(ConfirmedPartyLink(id=f"link-{identity}", binding=binding,
            bahi=observation(identity=str(identity)), tally=observation(Side.TALLY, str(identity)),
            confirmed_by="Synthetic reviewer", confirmed_at=datetime.now(timezone.utc), review_reference="paging test"))
    assert len(store.list(binding)) == 200
    assert store.list(binding)[0].id == "link-201"
    assert [link.id for link in store.list(binding, offset=200)] == ["link-1"]
    with pytest.raises(ValueError):
        store.list(binding, limit=10000)
