"""Offscreen reverse-review wiring and scrollable immutable evidence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from innoforia_tally_connector.application.masters.changes import compare_changes
from innoforia_tally_connector.domain.batches import TransferPolicy
from innoforia_tally_connector.domain.commands import Event
from innoforia_tally_connector.domain.experiments import ExperimentPreview, ExperimentResult, Direction, Preflight, StateUpdateEvidence
from innoforia_tally_connector.domain.masters import Side, PartyContent, ConfirmedPartyLink
from innoforia_tally_connector.domain.party_transfer import PartyDraft, FieldDecision, OPTIONAL_FIELDS
from innoforia_tally_connector.ui.pages.party_changes import PartyChangesDialog
from innoforia_tally_connector.ui.pages.transfer import TransferPage
from innoforia_tally_connector.ui.workspace import Workspace
import pytest


def test_reverse_review_automatically_includes_missing_tax_and_uses_bahi_commands(qtbot,binding,observation,monkeypatch):
    bahi=observation(identity='283',is_active=True,is_system=None,content_schema=2,
        content=PartyContent(name='Example Supplier',gstin=None,pan=None,gst_reg_type='Regular'))
    tally=observation(Side.TALLY,'source-guid',is_active=True,is_system=None,content_schema=2,
        content=PartyContent(name='Example Supplier',gstin='09CNXPP6229G1Z7',pan='CNXPP6229G',gst_reg_type='Regular'))
    link=ConfirmedPartyLink(id='review-link',binding=binding,bahi=bahi,tally=tally,
        confirmed_by='Owner',confirmed_at=datetime.now(timezone.utc),review_reference='explicit')
    review=compare_changes(link,bahi,tally,TransferPolicy(binding=binding,operator='Owner'),reverse=True)
    sent=[]
    dialog=PartyChangesDialog(None,lambda kind,**args:sent.append((kind,args)))
    qtbot.addWidget(dialog);dialog.generation=1;dialog.receive(review);dialog.show()
    assert 'Review linked Tally' in dialog.windowTitle() and 'Bahi changes' in dialog.windowTitle()
    assert dialog.identity.text().startswith('Tally source-guid')
    assert dialog.model.checked=={'gstin','pan','gst_reg_type'}
    assert dialog.gst_date.isHidden() and dialog.effective_date.isHidden()
    dialog.prepare.click()
    kind,kwargs=sent[-1];assert kind=='UPDATE_PREPARE' and kwargs['direction']==Direction.TO_BAHI and kwargs['party_identity']=='source-guid'
    assert kwargs['gst_effective_date'] is None
    now=datetime.now(timezone.utc)
    p=ExperimentPreview(id='reverse-preview',binding=binding,generation=1,direction=Direction.TO_BAHI,kind='UPDATE',
        source=tally,source_confirmation_required=True,party=PartyDraft(name=tally.content.name,party_type=tally.party_type,
            gstin=tally.content.gstin,pan=tally.content.pan,gst_reg_type='Regular'),
        preflight=Preflight(destination='Bahi 52',group_context='{}'),created_at=now,expires_at=now+timedelta(minutes=5),
        update=StateUpdateEvidence(link=link,before=bahi,native_before='{}',native_expected='{}',policy_version=1,
            fields=('gstin','pan','gst_reg_type'),accepted_missing_fields=('gstin','pan')))
    dialog.show_update(ExperimentResult(preview=p,state='PENDING',attempted=False),'Owner')
    dialog.normal.setChecked(True)
    assert dialog.approve.isEnabled()
    monkeypatch.setattr('innoforia_tally_connector.ui.confirmations.confirm_plain',lambda *_:True)
    dialog.approve.click()
    assert sent[-1][0]=='UPDATE_APPLY' and sent[-1][1]['direction']==Direction.TO_BAHI
    assert 'Source: TALLY' in dialog.result.text() and 'Bahi 52' in dialog.result.text()
    window=Workspace();window.quitting=True;qtbot.addWidget(window)
    window.controller=SimpleNamespace(binding=binding,pending={},generation=1,submit=lambda kind,**args:sent.append((kind,args)))
    window.models[Side.TALLY].replace([('Example Supplier','Supplier','Linked','source-guid')],[tally])
    window.views[Side.TALLY].selectRow(0);window.linked={(Side.TALLY,'source-guid')}
    window.inspect_changes(Side.TALLY)
    assert sent[-1]==('PARTY_CHANGES',{'party_identity':'source-guid','direction':Direction.TO_BAHI})


def test_completed_evidence_table_scrolls_up_without_allowing_edits(qtbot,binding,observation):
    source=observation(Side.TALLY,'guid',is_active=True,is_system=None,content_schema=2)
    now=datetime.now(timezone.utc)
    p=ExperimentPreview(id='history',binding=binding,generation=1,direction=Direction.TO_BAHI,kind='TRANSFER',
        party=PartyDraft(name=source.content.name,party_type=source.party_type),source=source,source_confirmation_required=True,
        preflight=Preflight(destination='Bahi',group_context='{}'),created_at=now,expires_at=now+timedelta(minutes=5),
        decisions=tuple(FieldDecision(field=f,status='excluded',reason='Retained audit') for f in OPTIONAL_FIELDS))
    page=TransferPage(lambda *_args,**_kwargs:None,lambda *_:None);qtbot.addWidget(page)
    page.receive(Event('request',1,'ACTIVITY_DETAIL',ExperimentResult(preview=p,state='SUCCEEDED',attempted=True)))
    page.set_busy(False,True);page.fields.setFixedHeight(90);page.resize(800,600);page.show();qtbot.wait(20)
    bar=page.fields.verticalScrollBar();assert bar.maximum()>0
    bar.setValue(bar.maximum())
    event=QWheelEvent(QPointF(20,20),QPointF(page.fields.viewport().mapToGlobal(QPoint(20,20))),QPoint(),QPoint(0,120),
        Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(page.fields.viewport(),event)
    assert page.fields.isEnabled() and bar.value()<bar.maximum()
    for row in range(page.fields.rowCount()):
        for col in (3,4):
            flags=page.fields.item(row,col).flags()
            assert not flags & (Qt.ItemFlag.ItemIsEditable|Qt.ItemFlag.ItemIsUserCheckable)


@pytest.mark.parametrize('width,height,points',[(960,650,10),(1100,700,13),(1280,800,15)])
def test_historical_fields_remain_visible_inside_expanded_activity(qtbot,binding,observation,width,height,points):
    source=observation(Side.TALLY,'guid',is_active=True,is_system=None,content_schema=2)
    now=datetime.now(timezone.utc)
    p=ExperimentPreview(id='history',binding=binding,generation=1,direction=Direction.TO_BAHI,kind='TRANSFER',
        party=PartyDraft(name=source.content.name,party_type=source.party_type),source=source,source_confirmation_required=True,
        preflight=Preflight(destination='Bahi',group_context='{}'),created_at=now,expires_at=now+timedelta(minutes=5),
        decisions=tuple(FieldDecision(field=f,status='excluded',reason='Retained audit') for f in OPTIONAL_FIELDS))
    window=Workspace();window.quitting=True;qtbot.addWidget(window)
    window.controller=SimpleNamespace(binding=binding,generation=1,pending={},submit=lambda *_args,**_kwargs:None)
    font=window.font();font.setPointSize(points);window.setFont(font)
    window.resize(width,height);window.tabs.setCurrentIndex(1);window.show()
    window.receive(Event('inspect',1,'ACTIVITY_DETAIL',ExperimentResult(preview=p,state='SUCCEEDED',attempted=True)))
    qtbot.wait(20)
    view=window.technical.fields
    assert window.advanced.isChecked() and window.advanced_tabs.currentWidget()==window.technical
    assert view.isVisible() and view.rowCount()==len(OPTIONAL_FIELDS)
    assert view.viewport().height()>=100, f'Historical table collapsed to {view.height()}px'
    scroll=window.page_scrolls[1];scroll.ensureWidgetVisible(view)
    qtbot.wait(10)
    center=view.mapTo(scroll.viewport(),view.rect().center())
    assert scroll.viewport().rect().contains(center)
    assert window.width()<=width and window.height()<=height


@pytest.mark.parametrize('direction',[Direction.TO_BAHI,Direction.TO_TALLY])
def test_saved_updates_open_field_evidence_in_operation_details(qtbot,binding,observation,direction):
    from innoforia_tally_connector.domain.experiments import TargetIdentity
    bahi=observation(identity='283',is_active=True,is_system=None,content_schema=2,
        content=PartyContent(name='Example Supplier',pan=None))
    tally=observation(Side.TALLY,'source-guid',is_system=None,content_schema=2,
        content=PartyContent(name='Example Supplier',pan='CNXPP6229G'))
    if direction==Direction.TO_TALLY:
        bahi=bahi.model_copy(update={'content':bahi.content.model_copy(update={'pan':'CNXPP6229G'})})
        tally=tally.model_copy(update={'content':tally.content.model_copy(update={'pan':None})})
    link=ConfirmedPartyLink(id='link',binding=binding,bahi=bahi,tally=tally,confirmed_by='Owner',
        confirmed_at=datetime.now(timezone.utc),review_reference='explicit')
    source,before=(tally,bahi) if direction==Direction.TO_BAHI else (bahi,tally)
    now=datetime.now(timezone.utc)
    p=ExperimentPreview(id='saved-update',binding=binding,generation=1,direction=direction,kind='UPDATE',
        source=source,source_confirmation_required=True,party=PartyDraft(name=source.content.name,party_type=source.party_type,pan='CNXPP6229G'),
        preflight=Preflight(destination='Known destination',group_context='{}'),created_at=now,expires_at=now+timedelta(minutes=5),
        update=StateUpdateEvidence(link=link,before=before,native_before='{}',native_expected='{}',policy_version=1,fields=('pan',)))
    target=before.model_copy(update={'content':before.content.model_copy(update={'pan':'CNXPP6229G'})})
    result=ExperimentResult(preview=p,state='BLOCKED',attempted=True,observation=target,comparisons={'pan':True},
        target=TargetIdentity(kind='BAHI_ID' if direction==Direction.TO_BAHI else 'TALLY_GUID',identity=target.identity))
    window=Workspace();window.quitting=True;qtbot.addWidget(window)
    sent=[];window.controller=SimpleNamespace(binding=binding,generation=1,pending={},submit=lambda kind,**args:sent.append((kind,args)))
    window.show();window.receive(Event('history',1,'ACTIVITY_DETAIL',result));qtbot.wait(10)
    assert window.tabs.currentIndex()==1 and window.advanced.isChecked()
    assert window.advanced_tabs.currentWidget()==window.technical and not window.changes_review.isVisible()
    table=window.technical.fields
    assert table.isVisible() and table.rowCount()==1
    assert [table.item(0,col).text() for col in range(5)]==['pan','[null]',"'CNXPP6229G'","'CNXPP6229G'",'matches']
    assert table.horizontalHeaderItem(1).text()=='Before update'
    assert not window.technical.approve.isEnabled() and not window.technical.cancel.isEnabled()
    window.technical.reconcile.click()
    assert sent[-1]==('UPDATE_RECONCILE',{'experiment_id':p.id})
    window.receive(Event('reads',1,'UPDATE_RECONCILE',result.model_copy(update={'state':'SUCCEEDED'})))
    assert window.technical.record.state=='SUCCEEDED' and table.rowCount()==1
    assert not window.changes_review.isVisible()


def test_double_click_saved_link_loads_original_field_table_and_labels_snapshot(qtbot,binding,observation):
    now=datetime.now(timezone.utc)
    link=ConfirmedPartyLink(id='original-transfer',binding=binding,bahi=observation(is_active=True),tally=observation(Side.TALLY,'guid'),
        confirmed_at=now,confirmed_by='Owner',review_reference='original-transfer',transfer_fields=('name','address'))
    window=Workspace();window.quitting=True;qtbot.addWidget(window)
    sent=[];window.send=lambda kind,**args:sent.append((kind,args))
    window.show_links((link,));window.saved_view.selectRow(0)
    assert 'historical values, not a current read' in window.saved_details.toPlainText()
    window.saved_view.doubleClicked.emit(window.saved_model.index(0,0))
    assert sent==[('ACTIVITY_DETAIL',{'experiment_id':'original-transfer'})]
