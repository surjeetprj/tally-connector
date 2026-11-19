"""v6 trial evidence becomes a reusable State baseline without rewriting it."""
from datetime import datetime, timezone
import json
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from innoforia_tally_connector.domain.experiments import Direction, Preflight, new_preview, synthetic_supplier
from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, PartyContent, Side
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions import v0007_repeatable_state_updates as v7
from innoforia_tally_connector.persistence.migrations.versions.v0006_state_update_audit import audit as old_audit
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


def legacy_database(tmp_path, binding, observation, monkeypatch):
    engine = metadata_engine(tmp_path / 'legacy.db')
    with monkeypatch.context() as patch:
        patch.setattr(runner, 'MIGRATIONS', runner.MIGRATIONS[:6]); runner.migrate(engine)
    links = SqlPartyLinks(engine); links.register_binding(binding)
    a = observation(content=PartyContent(name='Example Supplier', state='Delhi'))
    b = observation(Side.TALLY, 'target', content=PartyContent(name='Example Supplier', state='Delhi'))
    link = ConfirmedPartyLink(id='kept-link', binding=binding, bahi=a, tally=b,
        confirmed_at=datetime.now(timezone.utc), confirmed_by='Reviewer', review_reference='original')
    links.save(link)
    records = ExperimentStore(engine)
    preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(), Preflight(group_context='group', destination='Test'))
    records.save_preview(preview)
    evidence = json.dumps(dict(source_after=a.model_dump(mode='json'), target_after=b.model_dump(mode='json'),
        retained='unchanged legacy evidence'))
    with engine.begin() as c:
        c.execute(insert(old_audit).values(operation_id=preview.id, link_id=link.id, evidence_json=evidence))
    return engine, links, records, link, preview, evidence


def test_v7_backup_keeps_legacy_evidence_and_removes_only_per_link_uniqueness(tmp_path, binding, observation, monkeypatch):
    engine, links, records, link, preview, evidence = legacy_database(tmp_path, binding, observation, monkeypatch)
    try:
        old_digest = records.get(preview.id, binding).preview.digest
        runner.migrate(engine)
        assert records.get(preview.id, binding).preview.digest == old_digest
        assert links.by_id(link.id) == link
        ack = records.state_acknowledgement(link)
        assert ack.operation_id == preview.id and ack.bahi.content.state == ack.tally.content.state == 'Delhi'
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one() == 7
            assert c.exec_driver_sql('SELECT evidence_json FROM party_state_update_audit').scalar_one() == evidence
            assert c.exec_driver_sql('SELECT count(*) FROM party_link_audit').scalar_one() == 1
            assert not c.exec_driver_sql('PRAGMA foreign_key_check').all()
        with sqlite3.connect(next(tmp_path.glob('*.v6.*.backup'))) as saved:
            assert saved.execute('PRAGMA user_version').fetchone()[0] == 6
            assert saved.execute('SELECT evidence_json FROM party_state_update_audit').fetchone()[0] == evidence
        # A distinct operation can append a second audit for the same link.
        with engine.begin() as c:
            from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
            row = c.execute(experiments.select().where(experiments.c.id == preview.id)).mappings().one()
            c.execute(insert(experiments).values(**{**dict(row), 'id': 'second-op', 'active_binding': None}))
            c.execute(insert(v7.audit).values(operation_id='second-op', link_id=link.id, evidence_json=evidence))
            with pytest.raises(IntegrityError):
                c.execute(insert(v7.audit).values(operation_id='second-op', link_id=link.id, evidence_json=evidence))
        assert records.state_acknowledgement(link).operation_id == 'second-op'
    finally: engine.dispose()


def test_v7_failure_restores_v6_unique_schema_and_all_evidence(tmp_path, binding, observation, monkeypatch):
    engine, links, records, link, preview, evidence = legacy_database(tmp_path, binding, observation, monkeypatch)
    try:
        def fail(c):
            v7.upgrade(c)
            raise RuntimeError('After audit rebuild')
        with monkeypatch.context() as patch:
            patch.setattr(runner, 'MIGRATIONS', (*runner.MIGRATIONS[:6], SimpleNamespace(VERSION=7, upgrade=fail)))
            with pytest.raises(RuntimeError, match='audit rebuild'): runner.migrate(engine)
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one() == 6
            assert c.exec_driver_sql('SELECT evidence_json FROM party_state_update_audit').scalar_one() == evidence
            assert not c.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='state_update_audit_v6'").first()
        assert links.by_id(link.id) == link
        runner.migrate(engine)
        assert records.state_acknowledgement(link).operation_id == preview.id
    finally: engine.dispose()
