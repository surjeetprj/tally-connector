"""Shared journal + actual typed gateway/transport + SQLite, synthetic HTTP only."""
from pathlib import Path
from datetime import datetime, timezone
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import re
import time
import hashlib
import json
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from sqlalchemy import event, select
from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
from innoforia_tally_connector.application.masters.changes import LinkedPartyReviewWorkflow
from innoforia_tally_connector.application.masters.state_updates import StateUpdateWorkflow
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.masters import Classification, ConfirmedPartyLink, PartyContent
from innoforia_tally_connector.domain.experiments import Direction, new_preview, synthetic_supplier, Preflight
from innoforia_tally_connector.integrations.tally.gateway import Gateway,COMPANY_GUID
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.transfers import PartyDestination
from innoforia_tally_connector.integrations.tally.state_destination import StateDestination
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.batches import BatchStore
from innoforia_tally_connector.persistence.migrations.versions.v0006_state_update_audit import audit
from innoforia_tally_connector.domain.batches import TransferPolicy


@pytest.fixture
def rig(store,binding,observation):
    binding=binding.model_copy(update={'id':'state-test','business_id':52,'company_guid':COMPANY_GUID})
    store.register_binding(binding)
    classification=Classification(customer_root='a',supplier_root='b')
    identity=COMPANY_GUID+'-00000001'
    base=(Path(__file__).resolve().parents[1]/'fixtures/tally/state_update_native.xml').read_bytes()
    remote=SimpleNamespace(state='',version='1',other='Keep',mode='',imports=0,name='SIS Dummy')
    def handler(request):
        root=parse(request.content)
        assert request.headers['Content-Type']=='UTF-16'
        if root.findtext('HEADER/TALLYREQUEST')=='Import Data':
            ledger=root.find('.//LEDGER')
            assert ledger.attrib=={'NAME':'Synthetic supplier','ACTION':'Alter'}
            assert ledger.findtext('GUID')==identity
            assert [n.tag for n in ledger]==['GUID','LEDMAILINGDETAILS.LIST']
            remote.imports+=1
            if remote.mode!='ignore':remote.state=ledger.findtext('LEDMAILINGDETAILS.LIST/STATE')
            remote.version='2'
            if remote.mode=='other_change':remote.other='Unexpected mutation'
            if remote.mode=='timeout':raise httpx.ReadTimeout('Lost after commit')
            return httpx.Response(200,content=b'<RESPONSE><CREATED>0</CREATED><ALTERED>1</ALTERED><ERRORS>0</ERRORS></RESPONSE>')
        assert root.findtext('HEADER/TALLYREQUEST')=='Export'
        entity=root.findtext('HEADER/ID')
        if entity=='ConnectorReadCompany':
            return httpx.Response(200,content=f'<COLLECTION><COMPANY NAME="{remote.name}"><GUID>{COMPANY_GUID}</GUID></COMPANY></COLLECTION>'.encode())
        assert root.findtext('.//SVCURRENTCOMPANY')==remote.name
        if entity=='ConnectorReadGroup':
            return httpx.Response(200,content=b'<COLLECTION><GROUP NAME="Sundry Debtors"><GUID>a</GUID><ALTERID>1</ALTERID><PARENT>Primary</PARENT></GROUP><GROUP NAME="Sundry Creditors"><GUID>b</GUID><ALTERID>1</ALTERID><PARENT>Primary</PARENT></GROUP></COLLECTION>')
        raw=base.replace(b'<STATE></STATE>',f'<STATE>{remote.state}</STATE>'.encode()).replace(b'<LEDSTATENAME></LEDSTATENAME>',f'<LEDSTATENAME>{remote.state}</LEDSTATENAME>'.encode())
        raw=raw.replace(b'<ALTERID>1</ALTERID>',f'<ALTERID>{remote.version}</ALTERID>'.encode()).replace(b'<OTHER>Keep</OTHER>',f'<OTHER>{remote.other}</OTHER>'.encode())
        if remote.mode == 'metadata':
            raw = raw.replace(b'</LEDGER>', (f'<REMOTEALTGUID>{identity if remote.imports else ""}</REMOTEALTGUID></LEDGER>').encode())
            if remote.imports: raw = raw.replace(b'<LEDSTATENAME>', b'<LEDSTATENAME TYPE="String">')
            else: raw = raw.replace(b'<LEDSTATENAME></LEDSTATENAME>', b'')
        if '*' not in [n.text for n in root.findall('.//FETCH')]:
            raw=re.sub(rb'<GSTTYPE>.*?</GSTTYPE>',b'',raw)
        return httpx.Response(200,content=raw)
    remote.active=remote.maximum=0
    guard=Lock()
    def serialized_http(request):
        with guard:
            remote.active+=1;remote.maximum=max(remote.maximum,remote.active)
        try:
            time.sleep(0.001)
            return handler(request)
        finally:
            with guard:remote.active-=1
    gateway=Gateway(Transport(httpx.Client(transport=httpx.MockTransport(serialized_http))))
    tally=PartyReader(gateway,classification)
    baseline=observation(binding=binding,name='Synthetic supplier',identity='282',is_active=True,is_system=None,content_schema=2,
        content=PartyContent(name='Synthetic supplier',state=None,address='Exact – Delhi\n',country='India',pincode='012345'))
    link=ConfirmedPartyLink(id='linked',binding=binding,bahi=baseline,tally=tally.detail(binding,identity),
        confirmed_at=datetime.now(timezone.utc),confirmed_by='Reviewer',review_reference='explicit')
    store.save(link)
    current=SimpleNamespace(source=baseline.model_copy(update={'content':baseline.content.model_copy(update={'state':'Delhi'})}))
    class Source:
        def detail(self,binding,identity):
            assert identity=='282'
            return current.source.model_copy(update={'observed_at':datetime.now(timezone.utc)})
    records=ExperimentStore(store.engine);journal=DiscoveryStore(store.engine);policies=BatchStore(store.engine)
    policies.save_policy(TransferPolicy(binding=binding,operator='Reviewer'))
    changes=LinkedPartyReviewWorkflow(lambda _:(Source(),tally),lambda:SimpleNamespace(business_id=52,company_guid=COMPANY_GUID),store,policies.policy,lambda _:PartyDestination(gateway,classification),records.state_acknowledgement)
    workflow=StateUpdateWorkflow(records,changes,lambda _:StateDestination(gateway,classification))
    def run(kind,**values):
        command=Command(id=str(uuid4()),kind=kind,binding=binding,generation=1,**values)
        journal.capture(command);claimed=journal.claim(command.id)
        try:result=workflow.handle(claimed,binding,classification)
        except Exception as e:journal.finish(command.id,str(e));raise
        journal.finish(command.id);journal.dispatched(command.id)
        return result
    def prepare():return run('UPDATE_PREPARE',party_identity='282')
    def apply(record,**values):
        args=dict(experiment_id=record.preview.id,direction=Direction.TO_TALLY,approval_digest=record.preview.digest,reviewer='Reviewer',source_normal_party_confirmed=True)
        args.update(values);return run('UPDATE_APPLY',**args)
    yield SimpleNamespace(**locals())
    gateway.close()


def test_state_update_once_preserves_original_link_and_appends_audit(rig):
    r=rig;p=r.prepare()
    assert p.target.identity==r.identity and not p.attempted and r.remote.imports==0
    result=r.apply(p)
    assert result.state=='SUCCEEDED' and all(result.comparisons.values()) and r.remote.imports==1
    assert r.store.by_id('linked')==r.link
    assert r.apply(p)==result and r.remote.imports==1
    assert r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)==result
    with r.store.engine.connect() as c:assert c.execute(select(audit.c.link_id)).scalar_one()=='linked'
    assert ExperimentStore(r.store.engine).latest_update(r.binding)==result


def test_update_and_competing_export_share_the_one_gateway(rig):
    r=rig;p=r.prepare()
    with ThreadPoolExecutor(max_workers=2) as pool:
        write=pool.submit(r.apply,p)
        read=pool.submit(r.gateway.read,'Ledger',COMPANY_GUID)
        assert write.result().state=='SUCCEEDED' and read.result()
    assert r.remote.maximum==1 and r.remote.imports==1


@pytest.mark.parametrize('reason',['digest','reviewer','normal','source','target','policy','company','expired'])
def test_invalidated_approval_sends_nothing(rig,reason):
    r=rig;p=r.prepare();args={}
    if reason=='digest':args['approval_digest']='wrong'
    if reason=='reviewer':args['reviewer']=' '
    if reason=='normal':args['source_normal_party_confirmed']=False
    if reason=='source':r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'state':'Other'})})
    if reason=='target':r.remote.other='New edit'
    if reason=='policy':r.policies.save_policy(r.policies.policy(r.binding))
    if reason=='company':r.remote.name='Changed company'
    if reason=='expired':
        old=p.preview.model_copy(update={'created_at':p.preview.created_at-timedelta(minutes=10),'expires_at':p.preview.expires_at-timedelta(minutes=10)})
        with r.store.engine.begin() as c:c.execute(experiments.update().where(experiments.c.id==p.preview.id).values(preview_json=old.model_dump_json(exclude_unset=True)))
        p=r.records.get(p.preview.id,r.binding)
    with pytest.raises(ValueError):r.apply(p,**args)
    assert r.remote.imports==0 and not r.records.get(p.preview.id,r.binding).attempted


@pytest.mark.parametrize('mode',['timeout','ignore','other_change'])
def test_uncertainty_or_preservation_failure_never_resends(rig,mode):
    r=rig;r.remote.mode=mode;p=r.prepare();result=r.apply(p)
    assert result.state==('OUTCOME_UNKNOWN' if mode=='timeout' else 'BLOCKED')
    if mode=='other_change': assert 'Unexpected mutation' in result.native_after
    assert result.target.identity==r.identity and result.attempted
    r.records.recover();r.journal.recover(r.store)
    result=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert result.state==('SUCCEEDED' if mode=='timeout' else 'BLOCKED') and r.remote.imports==1
    assert r.apply(p).state==result.state and r.remote.imports==1


def test_cancel_and_supersession_never_apply(rig):
    r=rig;p=r.prepare();new=r.prepare()
    assert r.records.get(p.preview.id,r.binding).state=='CANCELLED'
    assert r.apply(p).state=='CANCELLED'
    r.run('UPDATE_CANCEL',experiment_id=new.preview.id)
    assert r.apply(new).state=='CANCELLED' and r.remote.imports==0


def test_mapping_audit_failure_rolls_back_and_read_only_reconciliation_completes(rig):
    r=rig;p=r.prepare()
    def fail(_connection,_cursor,statement,*_):
        if statement.startswith('INSERT INTO party_state_update_audit'):raise RuntimeError('Injected failure')
    event.listen(r.store.engine,'before_cursor_execute',fail)
    try:assert r.apply(p).state=='VERIFYING'
    finally:event.remove(r.store.engine,'before_cursor_execute',fail)
    assert r.run('UPDATE_RECONCILE',experiment_id=p.preview.id).state=='SUCCEEDED'
    assert r.remote.imports==1 and r.store.by_id('linked')==r.link


def test_old_approved_record_reconciles_metadata_without_rewriting_or_resending(rig, monkeypatch):
    from innoforia_tally_connector.integrations.tally import state_destination
    from innoforia_tally_connector.integrations.tally.state_update import native_shape
    r=rig;r.remote.mode='metadata';p=r.prepare()
    original_hash=p.preview.digest
    with monkeypatch.context() as patch:
        patch.setattr(state_destination,'preservation_matches',lambda expected,actual,state:
            native_shape(expected,ignore_version=True)==native_shape(actual,ignore_version=True))
        result=r.apply(p)
    assert result.state=='BLOCKED' and result.comparisons['state'] and r.remote.imports==1
    result=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert result.state=='SUCCEEDED' and result.preview.digest==original_hash
    assert result.preview.update.native_expected==p.preview.update.native_expected
    assert r.remote.imports==1 and r.store.by_id('linked')==r.link


def test_binding_reservation_and_restart_confirmation_are_safe(rig):
    r=rig;p=r.prepare()
    other=new_preview(r.binding,1,Direction.TO_BAHI,synthetic_supplier(),Preflight(group_context='root',destination='Test'))
    with pytest.raises(ValueError):r.records.save_preview(other)
    command=Command(id=str(uuid4()),kind='UPDATE_APPLY',binding=r.binding,generation=1,experiment_id=p.preview.id)
    r.journal.capture(command);r.journal.claim(command.id);r.journal.recover(r.store)
    assert r.journal.claim(command.id) is None and r.remote.imports==0
    assert r.records.latest_update(r.binding).state=='PENDING'


def test_successive_updates_advance_only_state_baseline_and_survive_repository_restart(rig):
    r = rig
    first = r.apply(r.prepare())
    assert first.state == 'SUCCEEDED'
    # Reload through fresh repositories; acknowledgement is durable, not UI memory.
    reloaded = ExperimentStore(r.store.engine)
    ack = reloaded.state_acknowledgement(r.link)
    assert ack.operation_id == first.preview.id and ack.bahi.content.state == ack.tally.content.state == 'Delhi'
    r.current.source = r.current.source.model_copy(update={'content': r.current.source.content.model_copy(
        update={'state': 'Karnataka', 'email': 'new@example.invalid'})})
    review = r.changes.review(r.binding, r.classification, '282')
    fields = {f.field: f for f in review.fields}
    assert fields['state'].status == 'Bahi changed' and fields['state'].saved_tally.value == 'Delhi'
    # The acknowledgement did not bless unrelated fields or rewrite the original link.
    assert fields['email'].saved_bahi.availability == 'absent'
    second = r.prepare()
    assert second.preview.id != first.preview.id and second.preview.update.acknowledged_operation_id == first.preview.id
    assert not second.attempted and r.remote.imports == 1
    completed = r.apply(second)
    assert completed.state == 'SUCCEEDED' and r.remote.imports == 2
    assert r.apply(first).state == 'SUCCEEDED' and r.apply(second).state == 'SUCCEEDED' and r.remote.imports == 2
    assert r.store.by_id('linked') == r.link
    with r.store.engine.connect() as c:
        assert len(c.execute(select(audit.c.operation_id)).all()) == 2
    assert reloaded.state_acknowledgement(r.link).operation_id == second.preview.id
    assert r.run('UPDATE_STATUS', party_identity='282').preview.id == second.preview.id
    assert r.run('UPDATE_STATUS', party_identity='another-source') is None
    assert next(f for f in r.changes.review(r.binding, r.classification, '282').fields if f.field == 'state').status == 'Already matches'
    with pytest.raises(ValueError): r.prepare()
    assert r.remote.imports == 2


@pytest.mark.parametrize('source_change,target_change,expected', [
    ('Karnataka', 'Punjab', 'Conflict'), ('Delhi', 'Punjab', 'Tally changed'),
    (None, 'Delhi', 'Clearing needs review'), ('', 'Delhi', 'Clearing needs review'),
])
def test_post_success_conflicts_destination_edits_and_clears_never_write(rig, source_change, target_change, expected):
    r = rig
    first = r.apply(r.prepare())
    r.current.source = r.current.source.model_copy(update={'content': r.current.source.content.model_copy(update={'state': source_change})})
    r.remote.state = target_change
    review = r.changes.review(r.binding, r.classification, '282')
    assert next(f for f in review.fields if f.field == 'state').status == expected
    with pytest.raises(ValueError): r.prepare()
    assert r.remote.imports == 1 and r.records.state_acknowledgement(r.link).operation_id == first.preview.id


def test_second_uncertain_update_keeps_last_success_baseline_and_blocks_new_write(rig):
    r = rig
    first = r.apply(r.prepare())
    r.current.source = r.current.source.model_copy(update={'content': r.current.source.content.model_copy(update={'state': 'Karnataka'})})
    second = r.prepare()
    r.remote.mode = 'timeout'
    result = r.apply(second)
    assert result.state == 'OUTCOME_UNKNOWN' and r.remote.imports == 2
    assert r.records.state_acknowledgement(r.link).operation_id == first.preview.id
    r.current.source = r.current.source.model_copy(update={'content': r.current.source.content.model_copy(update={'state': 'Punjab'})})
    with pytest.raises(ValueError): r.prepare()
    assert r.remote.imports == 2
    r.current.source = second.preview.source
    result = r.run('UPDATE_RECONCILE', experiment_id=second.preview.id)
    assert result.state == 'SUCCEEDED' and r.remote.imports == 2
    assert r.records.state_acknowledgement(r.link).operation_id == second.preview.id


def test_state_approval_hash_retains_old_controlled_preview_shape(rig):
    r = rig
    record = r.prepare()
    old = record.preview.model_dump(mode='json')
    old['update'].pop('acknowledged_operation_id')
    original_hash = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert record.preview.digest == original_hash
    saved = record.preview.model_dump(mode='json', exclude_unset=True)
    saved['update'].pop('acknowledged_operation_id', None)
    with r.store.engine.begin() as c:
        c.execute(experiments.update().where(experiments.c.id == record.preview.id).values(preview_json=json.dumps(saved)))
    assert r.apply(r.records.get(record.preview.id, r.binding)).state == 'SUCCEEDED'


def test_stale_acknowledgement_is_rejected_transactionally_before_attempt(rig):
    r = rig
    first = r.apply(r.prepare())
    r.current.source = r.current.source.model_copy(update={'content': r.current.source.content.model_copy(update={'state': 'Karnataka'})})
    current = r.prepare()
    stale = current.preview.model_copy(update={'update': current.preview.update.model_copy(update={'acknowledged_operation_id': None})})
    command = Command(id=str(uuid4()), kind='UPDATE_APPLY', binding=r.binding, generation=1,
        experiment_id=stale.id, direction=Direction.TO_TALLY, approval_digest=stale.digest,
        reviewer='Reviewer', source_normal_party_confirmed=True)
    r.journal.capture(command); r.journal.claim(command.id)
    with pytest.raises(ValueError, match='baseline changed'):
        r.records.begin_attempt(stale, command, stale.preflight)
    assert not r.records.get(stale.id, r.binding).attempted and r.remote.imports == 1
    assert r.records.state_acknowledgement(r.link).operation_id == first.preview.id
