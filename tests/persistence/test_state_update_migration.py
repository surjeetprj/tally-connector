import hashlib
import json
import sqlite3
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations import runner
from innoforia_tally_connector.persistence.migrations.versions import v0006_state_update_audit
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.domain.masters import ConfirmedPartyLink,Side
from innoforia_tally_connector.domain.experiments import new_preview,synthetic_supplier,Preflight,Direction


def test_v6_consistent_backup_and_preservation(tmp_path,binding,observation,monkeypatch):
    engine=metadata_engine(tmp_path/'upgrade.db')
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner,'MIGRATIONS',runner.MIGRATIONS[:5]);runner.migrate(engine)
        links=SqlPartyLinks(engine);links.register_binding(binding)
        link=ConfirmedPartyLink(id='kept',binding=binding,bahi=observation(),tally=observation(Side.TALLY,'2'),
            confirmed_at=datetime.now(timezone.utc),confirmed_by='Reviewer',review_reference='kept')
        links.save(link)
        old=new_preview(binding,1,Direction.TO_BAHI,synthetic_supplier(),Preflight(group_context='root',destination='Test'))
        records=ExperimentStore(engine);records.save_preview(old)
        # This is the exact pre-update-model hash: the new optional field did not exist.
        old_data=old.model_dump(mode='json');old_data.pop('update')
        legacy_hash=hashlib.sha256(json.dumps(old_data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        runner.migrate(engine)
        assert records.get(old.id,binding).preview.digest==legacy_hash
        assert links.by_id(link.id)==link
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one()==runner.MIGRATIONS[-1].VERSION
            assert c.exec_driver_sql('SELECT count(*) FROM party_state_update_audit').scalar_one()==0
            assert c.exec_driver_sql('SELECT count(*) FROM party_link_audit').scalar_one()==1
        with sqlite3.connect(next(tmp_path.glob('*.backup'))) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0]==5
            assert c.execute('SELECT id FROM party_links').fetchone()[0]==link.id
    finally:engine.dispose()


def test_v6_failure_rolls_back_ddl_and_version(tmp_path,monkeypatch):
    engine=metadata_engine(tmp_path/'rollback.db')
    try:
        with monkeypatch.context() as patch:
            patch.setattr(runner,'MIGRATIONS',runner.MIGRATIONS[:5]);runner.migrate(engine)
        def fail(c):
            v0006_state_update_audit.upgrade(c)
            raise RuntimeError('Injected after audit table')
        with monkeypatch.context() as patch:
            patch.setattr(runner,'MIGRATIONS',(*runner.MIGRATIONS[:5],SimpleNamespace(VERSION=6,upgrade=fail)))
            with pytest.raises(RuntimeError):runner.migrate(engine)
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one()==5
            assert not c.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='party_state_update_audit'").first()
        runner.migrate(engine)
    finally:engine.dispose()
