"""Reverse updates through real Bahi HTTP adapter and the shared SQLite journal."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import json
import httpx
import pytest
from sqlalchemy import select

from innoforia_tally_connector.application.masters.changes import LinkedPartyReviewWorkflow
from innoforia_tally_connector.application.masters.state_updates import StateUpdateWorkflow
from innoforia_tally_connector.application.masters.discovery import DiscoveryWorkflow
from innoforia_tally_connector.domain.batches import TransferPolicy
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.masters import ConfirmedPartyLink, PartyContent, PartyType, Side
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader
from innoforia_tally_connector.integrations.bahi.endpoints.updates import UpdateDestination
from innoforia_tally_connector.persistence.repositories.batches import BatchStore
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
from innoforia_tally_connector.persistence.migrations.versions.v0007_repeatable_state_updates import audit


@pytest.fixture(params=[PartyType.CUSTOMER, PartyType.SUPPLIER])
def reverse(store, binding, observation, request):
    binding = binding.model_copy(update={'id':'reverse-test','business_id':52})
    store.register_binding(binding)
    remote = SimpleNamespace(mode='', writes=[], row=dict(account_id=283, account_name='Linked party',
        party_type=str(request.param), is_active=True, gstin=None, pan=None, gst_reg_type='Regular',
        phone=None, address='Original\nAddress', country='India', state='Delhi', pincode='012345',
        contact_person='Keep me', note='Preserve unrelated values', updated_dtm=None))
    def http(req):
        if req.method == 'GET':
            data = {'biz_id':52,'biz_name':'Synthetic business'} if req.url.path.endswith('check_api_biz_setup.php') else remote.row
            return httpx.Response(200,json={'success':True,'data':data})
        assert req.method == 'PATCH' and req.url.params['id']=='283'
        payload=json.loads(req.content);remote.writes.append(payload)
        if remote.mode=='permission': return httpx.Response(403,json={'success':False})
        if remote.mode!='ignore': remote.row.update(payload)
        remote.row['updated_dtm']='2026-11-19 12:00:00'
        if remote.mode=='mutation': remote.row['note']='Unexpected edit'
        if remote.mode=='timeout': raise httpx.ReadTimeout('Lost after commit')
        if remote.mode=='malformed': return httpx.Response(200,content=b'not JSON')
        return httpx.Response(200,json={'success':True,'data':deepcopy(remote.row)})
    api=Client(lambda:'synthetic-key',httpx.Client(transport=httpx.MockTransport(http)))
    bahi=PartyReader(api)
    source=observation(Side.TALLY,'source-guid',binding=binding,party_type=request.param,
        is_active=True,is_system=None,content_schema=2,
        content=PartyContent(name='Linked party',gstin='09CNXPP6229G1Z7',pan='CNXPP6229G',gst_reg_type='Regular',
            phone='9736365019, INFO@EXAMPLE.INVALID',address='Original\nAddress',country='India',state='Delhi',pincode='012345'))
    remote.source=source
    class Tally:
        def detail(self,binding,identity):
            assert identity=='source-guid'
            return remote.source.model_copy(update={'observed_at':datetime.now(timezone.utc)})
    link=ConfirmedPartyLink(id='reverse-link',binding=binding,bahi=bahi.detail(binding,'283'),tally=source,
        confirmed_at=datetime.now(timezone.utc),confirmed_by='Owner',review_reference='explicit')
    store.save(link)
    records=ExperimentStore(store.engine);journal=DiscoveryStore(store.engine);policies=BatchStore(store.engine)
    policies.save_policy(TransferPolicy(binding=binding,operator='Owner'))
    changes=LinkedPartyReviewWorkflow(lambda _:(bahi,Tally()),lambda:SimpleNamespace(business_id=52,company_guid=binding.company_guid),
        store,policies.policy,lambda _:UpdateDestination(api),records.state_acknowledgement,reverse=True)
    workflow=StateUpdateWorkflow(records,changes,lambda _:UpdateDestination(api),reverse=True)
    dispatcher=DiscoveryWorkflow(None,None,None,None,None,None,changes=object(),
        updates=SimpleNamespace(store=records),reverse_changes=changes,reverse_updates=workflow)
    dispatcher.active=(binding,None,1)
    def run(kind,**values):
        command=Command(id=str(uuid4()),kind=kind,binding=binding,generation=1,direction=Direction.TO_BAHI,**values)
        journal.capture(command);claimed=journal.claim(command.id)
        try: result=dispatcher.handle(claimed)
        except Exception as error: journal.finish(command.id,str(error));raise
        journal.finish(command.id);journal.dispatched(command.id)
        return result
    def prepare(fields=('pan','gstin','gst_reg_type')):
        return run('UPDATE_PREPARE',party_identity='source-guid',update_fields=fields,accept_missing_fields=True)
    def apply(record,**values):
        args=dict(experiment_id=record.preview.id,approval_digest=record.preview.digest,reviewer='Owner',source_normal_party_confirmed=True)
        args.update(values);return run('UPDATE_APPLY',**args)
    yield SimpleNamespace(**locals())
    api.close()


def test_reverse_fills_tax_once_preserves_link_and_advances_baselines(reverse):
    r=reverse
    review=r.changes.review(r.binding,None,'source-guid')
    rows={f.field:f for f in review.fields}
    assert rows['phone'].status=='Invalid'
    assert rows['pan'].status==rows['gstin'].status=='Fill missing destination'
    p=r.prepare();assert not p.attempted and not r.remote.writes and p.target.kind=='BAHI_ID'
    result=r.apply(p)
    assert result.state=='SUCCEEDED' and all(result.comparisons.values())
    assert r.remote.writes==[{'pan':'CNXPP6229G','gstin':'09CNXPP6229G1Z7','gst_reg_type':'Regular'}]
    assert r.store.by_id(r.link.id)==r.link
    assert r.records.state_acknowledgement(r.link).bahi.identity=='283'
    assert r.records.state_acknowledgement(r.link).tally.identity=='source-guid'
    assert r.apply(p)==result and len(r.remote.writes)==1
    assert all(f.status=='Already matches' for f in r.changes.review(r.binding,None,'source-guid').fields if f.field in p.preview.update.fields)
    assert ExperimentStore(r.store.engine).latest_update(r.binding,'source-guid',Direction.TO_BAHI)==result
    # A later supported Tally edit uses the newly acknowledged baseline.
    r.remote.source=r.remote.source.model_copy(update={'content':r.remote.source.content.model_copy(update={'pan':'ABCDE1234F'})})
    assert next(f for f in r.changes.review(r.binding,None,'source-guid').fields if f.field=='pan').status=='Tally changed'
    assert r.apply(r.prepare(('pan',))).state=='SUCCEEDED' and len(r.remote.writes)==2


@pytest.mark.parametrize('mode',['timeout','malformed','ignore','mutation','permission'])
def test_reverse_unknown_mismatch_and_permission_never_resend(reverse,mode):
    r=reverse;p=r.prepare();r.remote.mode=mode
    result=r.apply(p)
    assert result.state==('FAILED' if mode=='permission' else 'OUTCOME_UNKNOWN' if mode in {'timeout','malformed'} else 'BLOCKED')
    r.records.recover()
    restored=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert restored.state==('SUCCEEDED' if mode in {'timeout','malformed'} else result.state)
    assert len(r.remote.writes)==1 and r.apply(p).state==restored.state
    if mode not in {'timeout','malformed'}:
        with r.store.engine.connect() as c: assert c.execute(select(audit.c.operation_id)).first() is None


@pytest.mark.parametrize('cause',['source','target','policy','expired','digest','normal','cancel'])
def test_reverse_stale_or_cancelled_approval_writes_nothing(reverse,cause):
    r=reverse;p=r.prepare();args={}
    if cause=='source':r.remote.source=r.remote.source.model_copy(update={'version':'changed'})
    if cause=='target':r.remote.row['note']='Another editor'
    if cause=='policy':r.policies.save_policy(r.policies.policy(r.binding))
    if cause=='expired':
        old=p.preview.model_copy(update={'created_at':p.preview.created_at-timedelta(minutes=10),'expires_at':p.preview.expires_at-timedelta(minutes=10)})
        with r.store.engine.begin() as c:c.execute(experiments.update().where(experiments.c.id==p.preview.id).values(preview_json=old.model_dump_json(exclude_unset=True)))
        p=r.records.get(p.preview.id,r.binding)
    if cause=='digest':args['approval_digest']='changed'
    if cause=='normal':args['source_normal_party_confirmed']=False
    if cause=='cancel':
        r.run('UPDATE_CANCEL',experiment_id=p.preview.id)
        assert r.apply(p).state=='CANCELLED'
    else:
        with pytest.raises(ValueError):r.apply(p,**args)
    assert not r.remote.writes and not r.records.get(p.preview.id,r.binding).attempted


def test_reverse_preserves_destination_edits_and_rejects_invalid_phone(reverse):
    r=reverse;r.remote.row['pan']='ABCDE1234F'
    with pytest.raises(ValueError):r.prepare(('pan',))
    with pytest.raises(ValueError):r.prepare(('phone',))
    assert not r.remote.writes


def test_reverse_local_completion_failure_recovers_without_another_patch(reverse,monkeypatch):
    r=reverse;p=r.prepare()
    original=r.records.complete_state_update
    def fail(*_args): raise RuntimeError('Simulated local completion failure')
    monkeypatch.setattr(r.records,'complete_state_update',fail)
    result=r.apply(p)
    assert result.state=='VERIFYING' and len(r.remote.writes)==1
    assert r.records.state_acknowledgement(r.link) is None
    monkeypatch.setattr(r.records,'complete_state_update',original)
    r.records.recover()
    result=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert result.state=='SUCCEEDED' and len(r.remote.writes)==1
    assert r.store.by_id(r.link.id)==r.link


def test_reverse_contact_and_mailing_changes_preserve_exact_values(reverse):
    r=reverse
    values={'phone':'00123456789','email':'accounts@example.invalid','address':'Exact – Delhi\nSecond line',
        'state':'Kerala','country':'India ','pincode':'001234'}
    r.remote.source=r.remote.source.model_copy(update={'content':r.remote.source.content.model_copy(update=values)})
    p=r.prepare(tuple(values))
    assert r.apply(p).state=='SUCCEEDED' and r.remote.writes==[values]
    assert r.remote.row['gstin'] is None and r.remote.row['pan'] is None
    assert r.remote.row['note']=='Preserve unrelated values'
    assert r.store.by_id(r.link.id)==r.link
