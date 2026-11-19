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
from copy import deepcopy
from lxml import etree
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from sqlalchemy import event, select
from innoforia_tally_connector.persistence.migrations.versions.v0004_party_transfers import experiments
from innoforia_tally_connector.application.masters.changes import LinkedPartyReviewWorkflow
from innoforia_tally_connector.application.masters.state_updates import StateUpdateWorkflow
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.masters import Classification, ConfirmedPartyLink, PartyContent, PartyType
from innoforia_tally_connector.domain.experiments import Direction, new_preview, synthetic_supplier, Preflight, ExperimentPreview, StateUpdateEvidence
from innoforia_tally_connector.domain.party_transfer import PartyDraft
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


@pytest.fixture(params=[False, True], ids=['dated', 'undated'])
def rig(store,binding,observation,request):
    binding=binding.model_copy(update={'id':'state-test','business_id':52,'company_guid':COMPANY_GUID})
    store.register_binding(binding)
    classification=Classification(customer_root='a',supplier_root='b')
    identity=COMPANY_GUID+'-00000001'
    base=(Path(__file__).resolve().parents[1]/'fixtures/tally/state_update_native.xml').read_bytes()
    base = base.replace(b'</LEDGER>',b'<INCOMETAXNUMBER/></LEDGER>')
    customer = request.param == 'customer'
    if customer: base=base.replace(b'Sundry Creditors',b'Sundry Debtors')
    native_projections = request.param == 'mailing-projections'
    tax_test = request.param in {'gst', 'gst-customer'}
    if request.param == 'gst-customer':
        customer = True
        base = base.replace(b'Sundry Creditors', b'Sundry Debtors')
    if tax_test:
        base = base.replace(b'</LEDGER>', b'<LEDGSTREGDETAILS.LIST/></LEDGER>')
    if native_projections:
        base = base.replace(b'</LEDGER>', b'<COUNTRYOFRESIDENCE TYPE="String"></COUNTRYOFRESIDENCE></LEDGER>')
    undated = request.param if not native_projections and not tax_test else False
    empty = request.param == 'empty'
    if undated:
        base = base.replace(b'<APPLICABLEFROM>20260401</APPLICABLEFROM>', b'')
    if empty:
        base = re.sub(rb'<LEDMAILINGDETAILS.LIST>.*?</LEDMAILINGDETAILS.LIST>', b'<LEDMAILINGDETAILS.LIST/>', base, flags=re.S)
    remote=SimpleNamespace(state='',version='1',other='Keep',mode='',imports=0,name='SIS Dummy', entry_date=None, direct_values={}, mail_payload=None)
    remote.gst_entries = []
    if tax_test: remote.state = 'Kerala'
    def handler(request):
        root=parse(request.content)
        assert request.headers['Content-Type']=='UTF-16'
        if root.findtext('HEADER/TALLYREQUEST')=='Import Data':
            ledger=root.find('.//LEDGER')
            assert ledger.attrib=={'NAME':'Synthetic supplier','ACTION':'Alter'}
            assert ledger.findtext('GUID')==identity
            assert ledger[0].tag=='GUID' and set(n.tag for n in ledger)<={'GUID','LEDMAILINGDETAILS.LIST','EMAIL','LEDGERPHONE','INCOMETAXNUMBER','LEDGSTREGDETAILS.LIST'}
            mailing = ledger.find('LEDMAILINGDETAILS.LIST')
            if mailing is not None: assert mailing.findtext('APPLICABLEFROM') == ('20260401' if empty or not undated else None)
            remote.imports+=1
            if remote.mode!='ignore':
                for n in ledger:
                    if n.tag in {'EMAIL','LEDGERPHONE','INCOMETAXNUMBER'}: remote.direct_values[n.tag] = etree.tostring(n)
                    if n.tag == 'LEDGSTREGDETAILS.LIST':
                        # Native import REPLACES this collection. A fake append
                        # would conceal loss of earlier effective-dated rows.
                        remote.gst_entries=[etree.tostring(row) for row in ledger.findall(n.tag)]
                if mailing is not None:
                    remote.mail_payload = etree.tostring(mailing)
                    if mailing.find('STATE') is not None: remote.state=mailing.findtext('STATE')
                    if empty: remote.entry_date=mailing.findtext('APPLICABLEFROM')
            remote.version=str(remote.imports+1)
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
        if remote.mail_payload:
            m = parse(remote.mail_payload)
            if m.find('STATE') is not None: m.find('STATE').text=remote.state
            if empty:
                for tag in ('PINCODE','MAILINGNAME','STATE','COUNTRY'):
                    if m.find(tag) is None: etree.SubElement(m,tag)
                order = ['ADDRESS.LIST','APPLICABLEFROM','PINCODE','MAILINGNAME','STATE','COUNTRY']
                m[:] = sorted(m,key=lambda n:order.index(n.tag))
            raw = re.sub(rb'<LEDMAILINGDETAILS.LIST(?:/>|>.*?</LEDMAILINGDETAILS.LIST>)',lambda _:etree.tostring(m),raw,flags=re.S)
        for tag,value in remote.direct_values.items():
            pattern = ('<'+tag+r'(?:/>|>.*?</'+tag+'>)').encode()
            if re.search(pattern,raw): raw=re.sub(pattern,lambda _:value,raw,flags=re.S)
            else: raw=raw.replace(b'</LEDGER>',value+b'</LEDGER>')
        if native_projections and remote.mail_payload:
            m = parse(remote.mail_payload)
            address = deepcopy(m.find('ADDRESS.LIST'))
            for line in address: line.set('TYPE', 'String')
            pin = etree.Element('PINCODE', TYPE='String'); pin.text = m.findtext('PINCODE')
            raw = raw.replace(b'</LEDGER>', etree.tostring(address) + etree.tostring(pin) + b'</LEDGER>')
        if remote.gst_entries:
            exported = []
            for entry in remote.gst_entries:
                n = parse(entry)
                for flag in ('ISOTHTERRITORYASSESSEE','CONSIDERPURCHASEFOREXPORT','ISTRANSPORTER','ISCOMMONPARTY'):
                    if n.find(flag) is None: etree.SubElement(n,flag)
                for tag in ('TRANSPORTERID','PLACEOFSUPPLY'):
                    if n.find(tag) is None: etree.SubElement(n,tag)
                order=['APPLICABLEFROM','GSTREGISTRATIONTYPE','TRANSPORTERID','STATE','PLACEOFSUPPLY','GSTIN',
                    'ISOTHTERRITORYASSESSEE','CONSIDERPURCHASEFOREXPORT','ISTRANSPORTER','ISCOMMONPARTY']
                n[:]=sorted(n,key=lambda child:order.index(child.tag))
                exported.append(etree.tostring(n))
            raw = raw.replace(b'<LEDGSTREGDETAILS.LIST/>', b''.join(reversed(exported)))
            last = parse(remote.gst_entries[-1])
            for root_tag,tax_tag in [('PARTYGSTIN','GSTIN'),('GSTREGISTRATIONTYPE','GSTREGISTRATIONTYPE'),('STATENAME','STATE')]:
                e = etree.Element(root_tag,TYPE='String'); e.text=last.findtext(tax_tag)
                raw=raw.replace(b'</LEDGER>',etree.tostring(e)+b'</LEDGER>')
        if empty and remote.entry_date:
            raw = raw.replace(b'<LEDMAILINGDETAILS.LIST/>', f'<LEDMAILINGDETAILS.LIST><APPLICABLEFROM>{remote.entry_date}</APPLICABLEFROM><PINCODE/><MAILINGNAME/><STATE>{remote.state}</STATE><COUNTRY/></LEDMAILINGDETAILS.LIST>'.encode())
        if remote.mode == 'date_change' and remote.imports:
            raw = (raw.replace(b'</LEDMAILINGDETAILS.LIST>', b'<APPLICABLEFROM>20250401</APPLICABLEFROM></LEDMAILINGDETAILS.LIST>')
                if undated else raw.replace(b'20260401', b'20250401'))
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
        party_type=PartyType.CUSTOMER if customer else PartyType.SUPPLIER,
        content=PartyContent(name='Synthetic supplier',state=None,address='Exact – Delhi\n',country='India',pincode='012345'))
    if tax_test:
        baseline=baseline.model_copy(update={'content':baseline.content.model_copy(update={'state':'Kerala','gstin':'','gst_reg_type':''})})
    link=ConfirmedPartyLink(id='linked',binding=binding,bahi=baseline,tally=tally.detail(binding,identity),
        confirmed_at=datetime.now(timezone.utc),confirmed_by='Reviewer',review_reference='explicit')
    store.save(link)
    current=SimpleNamespace(source=baseline.model_copy(update={'content':baseline.content.model_copy(update={'state':'Kerala' if tax_test else 'Delhi'})}))
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
    def prepare(effective_date=None):return run('UPDATE_PREPARE',party_identity='282',mailing_effective_date=effective_date)
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


@pytest.mark.parametrize('mode',['timeout','ignore','other_change','date_change'])
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
        patch.setattr(state_destination,'preservation_matches',lambda expected,actual,state,first_mailing_date=None:
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
    old['update'].pop('mailing_effective_date')
    old['update'].pop('fields')
    old['update'].pop('accepted_missing_fields')
    old['update'].pop('gst_effective_date')
    old['update'].pop('gst_state')
    original_hash = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert record.preview.digest == original_hash
    saved = record.preview.model_dump(mode='json', exclude_unset=True)
    saved['update'].pop('acknowledged_operation_id', None)
    saved['update'].pop('mailing_effective_date', None)
    saved['update'].pop('fields', None)
    saved['update'].pop('accepted_missing_fields', None)
    saved['update'].pop('gst_effective_date', None)
    saved['update'].pop('gst_state', None)
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


@pytest.mark.parametrize('rig', ['empty'], indirect=True)
def test_first_mailing_with_chosen_date_completes_without_other_field_writes(rig):
    r = rig
    with pytest.raises(ValueError): r.prepare()
    p = r.prepare('20260401')
    assert p.preview.update.mailing_effective_date == '20260401' and not p.attempted
    assert r.apply(p).state == 'SUCCEEDED' and r.remote.imports == 1
    assert r.store.by_id('linked') == r.link
    assert r.apply(p).state == 'SUCCEEDED' and r.remote.imports == 1


def retained_empty_failure(r):
    from lxml import etree
    context, before = r.gateway.state_snapshot(r.binding, r.identity)
    expected = parse(before.encode())
    etree.SubElement(expected.find('LEDMAILINGDETAILS.LIST'), 'STATE').text = 'Delhi'
    for derived in expected.findall('LEDSTATENAME'): derived.text = 'Delhi'
    now = datetime.now(timezone.utc)
    p = ExperimentPreview(id=str(uuid4()), binding=r.binding, generation=1, direction=Direction.TO_TALLY,
        party=PartyDraft(name=r.current.source.content.name, party_type=r.current.source.party_type, state='Delhi'),
        source=r.current.source, source_confirmation_required=True, kind='UPDATE', preflight=context,
        created_at=now, expires_at=now+timedelta(minutes=5), update=StateUpdateEvidence(link=r.link,
            before=r.tally.detail(r.binding,r.identity), native_before=before,
            native_expected=etree.tostring(expected,encoding='unicode'), policy_version=1))
    r.records.save_preview(p)
    cmd = Command(id=str(uuid4()), kind='UPDATE_APPLY', binding=r.binding, generation=1, experiment_id=p.id,
        direction=Direction.TO_TALLY, approval_digest=p.digest, reviewer='Reviewer', source_normal_party_confirmed=True)
    r.journal.capture(cmd); r.journal.claim(cmd.id); r.records.begin_attempt(p,cmd,context)
    r.remote.imports = 1; r.remote.version = '2'
    r.records.result(p.id,cmd.id,'VERIFYING')
    failed = r.run('UPDATE_RECONCILE', experiment_id=p.id)
    assert failed.state == 'BLOCKED' and failed.comparisons['state'] is False
    return failed


@pytest.mark.parametrize('rig', ['empty'], indirect=True)
def test_failed_empty_attempt_is_explicitly_closed_then_new_dated_intent_is_approved(rig):
    r = rig; old = retained_empty_failure(r)
    with pytest.raises(ValueError): r.prepare('20260401')
    closed = r.run('UPDATE_CLOSE_FAILED', experiment_id=old.preview.id, reviewer='Closer', source_normal_party_confirmed=True)
    assert closed.state == 'FAILED' and closed.attempted and r.remote.imports == 1
    assert r.apply(old).state == 'FAILED' and r.remote.imports == 1
    new = r.prepare('20260401')
    assert new.preview.id != old.preview.id and r.remote.imports == 1
    assert r.apply(new).state == 'SUCCEEDED' and r.remote.imports == 2
    assert r.records.get(old.preview.id,r.binding).state == 'FAILED'
    assert r.store.by_id('linked') == r.link


@pytest.mark.parametrize('rig', ['empty'], indirect=True)
@pytest.mark.parametrize('reason', ['unknown', 'reviewer', 'normal', 'changed', 'applied'])
def test_failed_closure_cannot_hide_uncertainty_edits_or_applied_changes(rig,reason):
    r = rig; old = retained_empty_failure(r)
    args = dict(experiment_id=old.preview.id,reviewer='Closer',source_normal_party_confirmed=True)
    if reason == 'unknown': r.records.result(old.preview.id,str(uuid4()),'OUTCOME_UNKNOWN')
    if reason == 'reviewer': args['reviewer'] = ''
    if reason == 'normal': args['source_normal_party_confirmed'] = False
    if reason == 'changed': r.remote.other = 'Other edit'
    if reason == 'applied': r.remote.state = 'Delhi'; r.remote.entry_date = '20260401'
    with pytest.raises(ValueError): r.run('UPDATE_CLOSE_FAILED', **args)
    assert r.remote.imports == 1 and r.records.get(old.preview.id,r.binding).state in {'BLOCKED','OUTCOME_UNKNOWN'}


@pytest.mark.parametrize('rig', ['empty'], indirect=True)
def test_closure_audit_rolls_back_and_restart_never_auto_closes(rig):
    r = rig; old = retained_empty_failure(r)
    def fail(_conn,_cursor,statement,*_):
        if statement.startswith('INSERT INTO party_state_update_verifications'): raise RuntimeError('Closure audit failed')
    event.listen(r.store.engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError):
            r.run('UPDATE_CLOSE_FAILED',experiment_id=old.preview.id,reviewer='Closer',source_normal_party_confirmed=True)
    finally: event.remove(r.store.engine,'before_cursor_execute',fail)
    assert r.records.get(old.preview.id,r.binding).state == 'BLOCKED'
    command = Command(id=str(uuid4()),kind='UPDATE_CLOSE_FAILED',binding=r.binding,generation=2,
        experiment_id=old.preview.id,reviewer='Closer',source_normal_party_confirmed=True)
    r.journal.capture(command); r.journal.recover(r.store)
    assert r.journal.claim(command.id) is None and r.remote.imports == 1
    assert r.records.get(old.preview.id,r.binding).state == 'BLOCKED'


@pytest.mark.parametrize('rig', ['empty'], indirect=True)
def test_saved_first_entry_padding_failure_reconciles_without_another_import(rig, monkeypatch):
    from innoforia_tally_connector.integrations.tally import state_destination
    from innoforia_tally_connector.integrations.tally.state_update import native_shape
    r = rig; preview = r.prepare('20260401')
    digest, expected = preview.preview.digest, preview.preview.update.native_expected
    with monkeypatch.context() as patch:
        patch.setattr(state_destination, 'preservation_matches', lambda a,b,state,first_mailing_date=None:
            native_shape(a,ignore_version=True)==native_shape(b,ignore_version=True))
        blocked = r.apply(preview)
    assert blocked.state == 'BLOCKED' and blocked.comparisons['state']
    assert not blocked.comparisons['native_preservation'] and r.remote.imports == 1
    completed = r.run('UPDATE_RECONCILE',experiment_id=preview.preview.id)
    assert completed.state == 'SUCCEEDED' and all(completed.comparisons.values())
    assert completed.preview.digest == digest and completed.preview.update.native_expected == expected
    assert r.remote.imports == 1 and r.store.by_id('linked') == r.link


@pytest.mark.parametrize('rig',[False,True,'customer'],indirect=True)
def test_selected_contact_mailing_pan_updates_and_independent_field_baselines(rig):
    r = rig
    values = dict(email='one@example.invalid',phone='00123',pan='AAACA1234A',address='Exact – दिल्ली\n\n Last ',state='Kerala',country='United Kingdom',pincode='001234')
    r.current.source = r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update=values)})
    first = r.run('UPDATE_PREPARE',party_identity='282',update_fields=tuple(values))
    result = r.apply(first)
    assert result.state=='SUCCEEDED' and r.remote.imports==1 and all(result.comparisons.values())
    assert r.store.by_id('linked')==r.link
    ack = r.records.state_acknowledgement(r.link)
    assert set(ack.field_baselines)==set(values)
    r.current.source = r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'email':'two@example.invalid','phone':'00999'})})
    second = r.run('UPDATE_PREPARE',party_identity='282',update_fields=('email',))
    assert r.apply(second).state=='SUCCEEDED' and r.remote.imports==2
    ack = r.records.state_acknowledgement(r.link)
    assert ack.field_baselines['email'].operation_id==second.preview.id
    assert ack.field_baselines['phone'].operation_id==first.preview.id
    review = r.changes.review(r.binding,r.classification,'282')
    assert next(f for f in review.fields if f.field=='phone').status=='Bahi changed'
    assert r.apply(first).state=='SUCCEEDED' and r.remote.imports==2


@pytest.mark.parametrize('rig',['empty'],indirect=True)
def test_blank_destination_filling_requires_explicit_field_acceptance(rig):
    r = rig
    args = dict(party_identity='282',update_fields=('address','country'),mailing_effective_date='20260401')
    with pytest.raises(ValueError): r.run('UPDATE_PREPARE',**args)
    prepared = r.run('UPDATE_PREPARE',**args,accept_missing_fields=True)
    assert set(prepared.preview.update.accepted_missing_fields)=={'address','country'}
    assert r.apply(prepared).state=='SUCCEEDED' and r.remote.imports==1
    assert set(r.records.state_acknowledgement(r.link).field_baselines)=={'address','country'}


@pytest.mark.parametrize('rig',['empty'],indirect=True)
def test_pin_padding_after_state_update_requires_explicit_fill_and_verifies_once(rig):
    r = rig
    state = r.prepare('20260401')
    assert r.apply(state).state == 'SUCCEEDED' and r.remote.imports == 1
    r.current.source = r.current.source.model_copy(update={
        'content': r.current.source.content.model_copy(update={'pincode': '683576'})})
    review = r.changes.review(r.binding, r.classification, '282')
    pin = next(f for f in review.fields if f.field == 'pincode')
    assert pin.saved_tally.availability == 'absent' and pin.current_tally.availability == 'empty'
    assert pin.status == 'Fill missing destination'
    args = dict(party_identity='282', update_fields=('pincode',))
    with pytest.raises(ValueError, match='explicit filling approval'):
        r.run('UPDATE_PREPARE', **args)
    assert r.remote.imports == 1
    prepared = r.run('UPDATE_PREPARE', **args, accept_missing_fields=True)
    assert prepared.preview.update.accepted_missing_fields == ('pincode',)
    assert r.remote.imports == 1 and not prepared.attempted
    result = r.apply(prepared)
    assert result.state == 'SUCCEEDED' and all(result.comparisons.values())
    assert r.remote.imports == 2
    assert r.apply(prepared).state == 'SUCCEEDED' and r.remote.imports == 2
    ack = r.records.state_acknowledgement(r.link)
    assert ack.field_baselines['pincode'].source.value == ack.field_baselines['pincode'].destination.value == '683576'
    assert ack.field_baselines['state'].operation_id == state.preview.id
    assert r.store.by_id('linked') == r.link


@pytest.mark.parametrize('field',['gstin','gst_reg_type','name'])
def test_unverified_tax_and_rename_fields_never_create_an_update_intent(rig,field):
    r = rig
    with pytest.raises(ValueError): r.run('UPDATE_PREPARE',party_identity='282',update_fields=(field,))
    assert r.remote.imports==0


@pytest.mark.parametrize('rig',['gst','gst-customer'],indirect=True)
def test_paired_gst_updates_append_history_and_acknowledge_only_selected_fields(rig):
    r=rig
    values=dict(gstin='32AAACA1234A1Z1',gst_reg_type='Regular')
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update=values)})
    first=r.run('UPDATE_PREPARE',party_identity='282',update_fields=tuple(values),gst_effective_date='20260401')
    assert not first.attempted and first.preview.update.gst_state=='Kerala' and r.remote.imports==0
    result=r.apply(first)
    assert result.state=='SUCCEEDED' and all(result.comparisons.values()) and r.remote.imports==1
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'gst_reg_type':'Composition'})})
    second=r.run('UPDATE_PREPARE',party_identity='282',update_fields=tuple(values),gst_effective_date='20260402')
    assert r.apply(second).state=='SUCCEEDED' and r.remote.imports==2
    assert len(r.remote.gst_entries)==2
    ack=r.records.state_acknowledgement(r.link)
    assert set(ack.field_baselines)==set(values) and ack.field_baselines['gst_reg_type'].destination.value=='Composition'
    r.records.recover(); r.journal.recover(r.store)
    assert r.records.get(second.preview.id,r.binding).state=='SUCCEEDED'
    assert r.run('UPDATE_RECONCILE',experiment_id=second.preview.id).state=='SUCCEEDED'
    assert r.apply(second).state=='SUCCEEDED' and r.remote.imports==2
    assert r.store.by_id('linked')==r.link


@pytest.mark.parametrize('rig',['gst'],indirect=True)
@pytest.mark.parametrize('case',['no_date','future','bad_gstin','bad_type','wrong_state','partial','expired','cancelled','date_changed'])
def test_gst_rejected_or_changed_approvals_send_zero_imports(rig,case):
    r=rig
    values=dict(gstin='32AAACA1234A1Z1',gst_reg_type='Regular')
    if case=='bad_gstin': values['gstin']='not-a-gstin'
    if case=='bad_type': values['gst_reg_type']='regular'
    if case=='wrong_state': values['state']='Delhi'
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update=values)})
    args=dict(party_identity='282',update_fields=('gstin','gst_reg_type'),gst_effective_date='20260401')
    if case=='no_date': args['gst_effective_date']=None
    if case=='future': args['gst_effective_date']='99990401'
    if case=='partial': args['update_fields']=('gstin',)
    if case in {'expired','cancelled','date_changed'}:
        p=r.run('UPDATE_PREPARE',**args)
        if case=='cancelled':
            r.run('UPDATE_CANCEL',experiment_id=p.preview.id)
            assert r.apply(p).state=='CANCELLED'
        else:
            if case=='expired':
                old=p.preview.model_copy(update={'created_at':datetime.now(timezone.utc)-timedelta(minutes=10),'expires_at':datetime.now(timezone.utc)-timedelta(minutes=5)})
                with r.store.engine.begin() as c: c.execute(experiments.update().where(experiments.c.id==p.preview.id).values(preview_json=old.model_dump_json(exclude_unset=True)))
            else:
                p=p.model_copy(update={'preview':p.preview.model_copy(update={'update':p.preview.update.model_copy(update={'gst_effective_date':'20260402'})})})
            with pytest.raises(ValueError): r.apply(p)
    else:
        with pytest.raises(ValueError): r.run('UPDATE_PREPARE',**args)
    assert r.remote.imports==0


@pytest.mark.parametrize('rig',['gst'],indirect=True)
@pytest.mark.parametrize('mode',['timeout','ignore','other_change'])
def test_gst_uncertainty_and_preservation_failures_reconcile_without_resend(rig,mode):
    r=rig
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'gstin':'32AAACA1234A1Z1','gst_reg_type':'Regular'})})
    p=r.run('UPDATE_PREPARE',party_identity='282',update_fields=('gstin','gst_reg_type'),gst_effective_date='20260401')
    r.remote.mode=mode
    result=r.apply(p)
    assert result.state==('OUTCOME_UNKNOWN' if mode=='timeout' else 'BLOCKED')
    assert r.remote.imports==1 and r.records.state_acknowledgement(r.link) is None
    r.records.recover(); r.journal.recover(r.store)
    result=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert result.state==('SUCCEEDED' if mode=='timeout' else 'BLOCKED')
    assert r.apply(p).state==result.state and r.remote.imports==1


@pytest.mark.parametrize('mode',['ignore','timeout'])
def test_contact_outcomes_use_known_identity_and_never_repeat_import(rig,mode):
    r=rig
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'email':'new@example.invalid'})})
    p=r.run('UPDATE_PREPARE',party_identity='282',update_fields=('email',))
    r.remote.mode=mode
    result=r.apply(p)
    assert result.state==('OUTCOME_UNKNOWN' if mode=='timeout' else 'BLOCKED') and r.remote.imports==1
    assert r.records.state_acknowledgement(r.link) is None
    r.records.recover(); r.journal.recover(r.store)
    result=r.run('UPDATE_RECONCILE',experiment_id=p.preview.id)
    assert result.state==('SUCCEEDED' if mode=='timeout' else 'BLOCKED') and r.remote.imports==1
    assert r.apply(p).state==result.state and r.remote.imports==1


def test_selected_fields_cannot_overwrite_a_destination_edit(rig):
    r=rig
    r.current.source=r.current.source.model_copy(update={'content':r.current.source.content.model_copy(update={'email':'new@example.invalid'})})
    p=r.run('UPDATE_PREPARE',party_identity='282',update_fields=('email',))
    r.remote.direct_values['EMAIL']=b'<EMAIL>destination-edit@example.invalid</EMAIL>'
    with pytest.raises(ValueError): r.apply(p)
    assert not r.records.get(p.preview.id,r.binding).attempted and r.remote.imports==0


@pytest.mark.parametrize('rig', ['mailing-projections'], indirect=True)
@pytest.mark.parametrize('legacy_preview', [False, True])
def test_native_mailing_projection_readback_and_legacy_read_only_recovery(rig, monkeypatch, legacy_preview):
    from innoforia_tally_connector.integrations.tally import state_destination
    r = rig
    values = dict(address='Exact – synthetic\n\n Last ', pincode='001234', country='United Kingdom')
    r.current.source = r.current.source.model_copy(update={
        'content': r.current.source.content.model_copy(update=values)})
    with monkeypatch.context() as patch:
        if legacy_preview:
            builder = state_destination.expected_fields
            def previous_prediction(*args):
                node = parse(builder(*args).encode())
                node.find('COUNTRYOFRESIDENCE').text = values['country']
                return etree.tostring(node, encoding='unicode')
            patch.setattr(state_destination, 'expected_fields', previous_prediction)
        prepared = r.run('UPDATE_PREPARE', party_identity='282', update_fields=tuple(values))
    digest, expected = prepared.preview.digest, prepared.preview.update.native_expected
    if legacy_preview:
        with pytest.raises(ValueError, match='preservation snapshot changed'):
            r.apply(prepared)
        assert r.remote.imports == 0 and not r.records.get(prepared.preview.id, r.binding).attempted
    with monkeypatch.context() as patch:
        if legacy_preview:
            patch.setattr(state_destination, 'expected_fields', previous_prediction)
            patch.setattr(state_destination, 'fields_preserved', lambda *_args, **_kwargs: False)
        result = r.apply(prepared)
    assert r.remote.imports == 1
    if legacy_preview:
        assert result.state == 'BLOCKED' and not result.comparisons['native_preservation']
        assert all(result.comparisons[f] for f in values)
        r.records.recover(); r.journal.recover(r.store)
        result = r.run('UPDATE_RECONCILE', experiment_id=prepared.preview.id)
    assert result.state == 'SUCCEEDED' and all(result.comparisons.values())
    assert result.preview.digest == digest and result.preview.update.native_expected == expected
    assert r.remote.imports == 1 and r.store.by_id('linked') == r.link
    ack = r.records.state_acknowledgement(r.link)
    assert set(ack.field_baselines) == set(values)
    assert all(ack.field_baselines[f].destination.value == values[f] for f in values)
    assert r.apply(prepared).state == 'SUCCEEDED' and r.remote.imports == 1
