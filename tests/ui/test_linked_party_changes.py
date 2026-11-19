"""Offscreen native review through the shared worker, real Bahi reader and SQLite."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import time
import json
from pathlib import Path

import httpx
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from sqlalchemy import event

from innoforia_tally_connector.bootstrap.dependencies import build
from innoforia_tally_connector.domain.batches import TransferPolicy
from innoforia_tally_connector.domain.commands import Command, Event
from innoforia_tally_connector.domain.experiments import Preflight, TargetIdentity
from innoforia_tally_connector.domain.masters import Binding, Classification, ConnectionSnapshot, ConfirmedPartyLink, Side
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader as BahiReader
from innoforia_tally_connector.integrations.tally.gateway import COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader as TallyReader, group_observations
from innoforia_tally_connector.integrations.tally.state_update import native_snapshot
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations.runner import migrate
from innoforia_tally_connector.persistence.repositories.batches import BatchStore
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.workspace import Workspace


@pytest.mark.parametrize("execute_trial", [False, True])
def test_linked_changes_are_fresh_and_read_only_through_worker(qtbot, tmp_path, monkeypatch, execute_trial):
    state = SimpleNamespace(source_state=None, target_state=None, fail=False, detail_ids=[], imports=0)
    groups = [{"GUID": "a", "NAME": "Sundry Debtors", "PARENT": "Primary", "ALTERID": "1"},
        {"GUID": "b", "NAME": "Sundry Creditors", "PARENT": "Primary", "ALTERID": "1"}]
    identity = COMPANY_GUID + "-00000001"
    binding = Binding(id="synthetic", business_id=52, company_guid=COMPANY_GUID, generation=1)
    classification = Classification(customer_root="a", supplier_root="b")
    def source():
        return {"account_id": 1, "account_name": "Linked supplier", "party_type": "SUPPLIER", "is_active": True,
                "state": state.source_state, "address": "Exact – दिल्ली address", "country": "India"}
    def http(request):
        assert request.method == "GET", "Change review must never mutate Bahi"
        if request.url.path.endswith("check_api_biz_setup.php"):
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic business"}})
        if "id" in request.url.params:
            state.detail_ids.append(request.url.params["id"])
            time.sleep(0.04)
            if state.fail: return httpx.Response(503)
            return httpx.Response(200, json={"success": True, "data": source()})
        return httpx.Response(200, json={"success": True, "data": [source()],
            "pagination": {"page": 1, "limit": 200, "total": 1, "total_pages": 1}})
    class Gateway:
        stopped = lambda self: False
        def read(self, entity="Company", company_guid=COMPANY_GUID, guid=None):
            assert company_guid == COMPANY_GUID
            if entity == "Company": return [{"GUID": COMPANY_GUID, "NAME": "SIS Dummy"}]
            if entity == "Group": return groups
            if guid: assert guid == identity
            row = {"GUID": identity, "NAME": "Linked supplier", "PARENT": "Sundry Creditors", "ALTERID": "1",
                "MAILING_CONTENT": {"address": "Exact – दिल्ली address", "country": "India"}}
            if state.target_state is not None: row["MAILING_CONTENT"]["state"] = state.target_state
            return [row]
        def state_snapshot(self, binding, target):
            assert target == identity
            raw = (Path(__file__).resolve().parents[1] / 'fixtures/tally/state_update_native.xml').read_bytes()
            raw = raw.replace(b'Synthetic supplier', b'Linked supplier')
            value = (state.target_state or '').encode()
            raw = raw.replace(b'<STATE></STATE>', b'<STATE>' + value + b'</STATE>')
            raw = raw.replace(b'<LEDSTATENAME></LEDSTATENAME>', b'<LEDSTATENAME>' + value + b'</LEDSTATENAME>')
            return Preflight(destination='Tally SIS Dummy', group_context=json.dumps({'company_guid': COMPANY_GUID, 'company_name': 'SIS Dummy'})), native_snapshot(raw, identity)
        def apply_state(self, preview):
            assert execute_trial and preview.kind == 'UPDATE'
            state.imports += 1
            state.target_state = preview.party.state
            return TargetIdentity(kind='TALLY_GUID', identity=identity)
        def create_party(self, *_): pytest.fail("Change review must never create")
        def close(self): pass
    api = Client(lambda: "synthetic-key", httpx.Client(transport=httpx.MockTransport(http)))
    gateway = Gateway()
    engine = metadata_engine(tmp_path / "sync_metadata.db"); migrate(engine)
    links = SqlPartyLinks(engine)
    snap = ConnectionSnapshot(business_id=52, business_name="Synthetic business", company_guid=COMPANY_GUID,
        company_name="SIS Dummy", groups=group_observations(groups))
    DiscoveryStore(engine).bind(binding, classification, snap, "credential-reference-only")
    baseline = ConfirmedPartyLink(id="saved-link", binding=binding, bahi=BahiReader(api).detail(binding, "1"),
        tally=TallyReader(gateway, classification).detail(binding, identity), confirmed_by="Reviewer",
        confirmed_at=datetime.now(timezone.utc), review_reference="explicit")
    links.save(baseline)
    BatchStore(engine).save_policy(TransferPolicy(binding=binding, operator="Reviewer"))
    engine.dispose()
    state.source_state = "Delhi"  # Owner's later edit, after original link.
    bridge = Bridge()
    runtime, cleanup = build(tmp_path, bridge.event.emit, bahi_client=api, tally_gateway=gateway)
    window = Workspace(); qtbot.addWidget(window)
    runtime.start(); window.show(); window.attach(Controller(runtime, bridge))
    ticks = []
    timer = QTimer(); timer.timeout.connect(lambda: ticks.append(True)); timer.start(5)
    try:
        qtbot.waitUntil(lambda: window.discovery is not None and not window.controller.pending, timeout=10000)
        window.models[Side.BAHI].checked.add("1")
        before = len(ticks)
        window.review_changes.click()
        qtbot.waitUntil(lambda: window.changes_review.isVisible() and not window.controller.pending, timeout=10000)
        rows = {f.field: f for f in window.changes_review.model.objects}
        assert rows["state"].status == "Bahi changed"
        assert rows["state"].saved_bahi.availability == "null" and rows["state"].saved_tally.availability == "absent"
        assert rows["address"].status == "Already matches" and "– दिल्ली" in rows["address"].current_bahi.value
        assert len(ticks) > before
        assert runtime.links.by_id("saved-link") == baseline
        if execute_trial:
            monkeypatch.setattr(QMessageBox, 'exec', lambda *_: QMessageBox.StandardButton.Yes)
            page = window.changes_review
            page.prepare.click()
            qtbot.waitUntil(lambda: page.record is not None and not window.controller.pending, timeout=10000)
            record_id = page.record.preview.id
            assert page.record.state == 'PENDING' and state.imports == 0
            assert not page.approve.isEnabled()
            page.normal.setChecked(True)
            assert page.reviewer.text() == 'Reviewer' and page.approve.isEnabled()
            page.approve.click()
            qtbot.waitUntil(lambda: page.record is not None and page.record.state == 'SUCCEEDED' and not window.controller.pending, timeout=10000)
            assert state.imports == 1 and state.target_state == 'Delhi'
            assert not page.approve.isEnabled() and runtime.links.by_id('saved-link') == baseline
            assert next(f for f in page.model.objects if f.field == 'state').status == 'Already matches'
            assert 'test' not in page.prepare.text().lower() and 'test' not in page.result.text().lower()
            # The normal feature supports another approved update of this same link.
            state.source_state = 'Karnataka'
            page.refresh.click()
            qtbot.waitUntil(lambda: not window.controller.pending and any(
                f.field == 'state' and f.status == 'Bahi changed' for f in page.model.objects), timeout=10000)
            assert page.prepare.isEnabled()
            page.prepare.click()
            qtbot.waitUntil(lambda: page.record is not None and page.record.preview.id != record_id
                and page.record.state == 'PENDING' and not window.controller.pending, timeout=10000)
            assert page.record.preview.update.acknowledged_operation_id == record_id
            record_id = page.record.preview.id
            page.normal.setChecked(True); page.approve.click()
            qtbot.waitUntil(lambda: page.record is not None and page.record.state == 'SUCCEEDED'
                and not window.controller.pending, timeout=10000)
            assert state.imports == 2 and state.target_state == 'Karnataka'
            runtime.shutdown(cleanup); qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
            page.close(); window.quitting = True; window.close()
            api = Client(lambda: 'synthetic-key', httpx.Client(transport=httpx.MockTransport(http)))
            bridge = Bridge()
            runtime, cleanup = build(tmp_path, bridge.event.emit, bahi_client=api, tally_gateway=Gateway())
            window = Workspace(); qtbot.addWidget(window)
            runtime.start(); window.show(); window.attach(Controller(runtime, bridge))
            qtbot.waitUntil(lambda: window.discovery is not None and not window.controller.pending, timeout=10000)
            window.send('UPDATE_STATUS')
            qtbot.waitUntil(lambda: window.changes_review.record is not None and not window.controller.pending, timeout=10000)
            assert window.changes_review.record.state == 'SUCCEEDED'
            assert window.changes_review.record.preview.id == record_id and state.imports == 2
            # Restart also restores the State-only baseline for conflict detection.
            window.send('PARTY_CHANGES', party_identity='1')
            qtbot.waitUntil(lambda: not window.controller.pending and window.changes_review.review is not None, timeout=10000)
            assert window.changes_review.review.state_acknowledgement.operation_id == record_id
            assert next(f for f in window.changes_review.model.objects if f.field == 'state').status == 'Already matches'
            return
        # A later Tally edit is a conflict, rather than an instruction to overwrite.
        state.target_state = "Other state"
        window.changes_review.close(); window.review_changes.click()
        qtbot.waitUntil(lambda: window.changes_review.isVisible() and not window.controller.pending, timeout=10000)
        assert next(f for f in window.changes_review.model.objects if f.field == "state").status == "Conflict"
        # Errors don't leave a prior successful review on screen.
        state.fail = True
        window.changes_review.close(); window.review_changes.click()
        qtbot.waitUntil(lambda: not window.controller.pending, timeout=10000)
        assert not window.changes_review.isVisible() and "HTTP 503" in window.status.text()
        assert runtime.links.by_id("saved-link") == baseline
        window.resize(650, 450); window.changes_review.resize(570, 370)
        state.fail = False
        window.review_changes.click()
        qtbot.waitUntil(lambda: window.changes_review.isVisible() and not window.controller.pending, timeout=10000)
        assert window.changes_review.model.rowCount() == 10
        # Binding re-verification hides the previous binding's review immediately.
        window.send("VERIFY")
        assert not window.changes_review.isVisible()
        qtbot.waitUntil(lambda: not window.controller.pending, timeout=10000)
    finally:
        timer.stop()
        runtime.shutdown(cleanup)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
        window.changes_review.close(); window.quitting = True; window.close()


def test_review_commands_coalesce_by_source_and_preserve_link_tables(store, binding):
    journal = DiscoveryStore(store.engine)
    statements = []
    def track(_connection, _cursor, statement, *_): statements.append(statement)
    event.listen(store.engine, "before_cursor_execute", track)
    try:
        def command(source):
            return Command(id=str(uuid4()), kind="PARTY_CHANGES", generation=10, binding=binding, party_identity=source)
        first, duplicate, other = command("1"), command("1"), command("2")
        assert journal.capture(first) == first.id
        assert journal.capture(duplicate) == first.id
        assert journal.capture(other) == other.id
        assert set(journal.pending()) == {first.id, other.id}
        assert journal.command(first.id).party_identity == "1"
        assert not any(s.startswith(("INSERT INTO party_links", "UPDATE party_links", "INSERT INTO party_link_audit", "INSERT INTO party_experiments")) for s in statements)
        journal.recover(store)
        assert all(journal.command(i).kind == "PARTY_CHANGES" for i in journal.pending())
    finally: event.remove(store.engine, "before_cursor_execute", track)


def test_state_result_queries_coalesce_only_for_the_same_party_or_record(store, binding):
    journal = DiscoveryStore(store.engine)
    def command(**values):
        return Command(id=str(uuid4()), kind='UPDATE_STATUS', generation=10, binding=binding, **values)
    first, other = command(party_identity='1'), command(party_identity='2')
    assert journal.capture(first) == first.id
    assert journal.capture(command(party_identity='1')) == first.id
    assert journal.capture(other) == other.id
    explicit = command(experiment_id='historical')
    assert journal.capture(explicit) == explicit.id


def test_controller_discards_old_review_results_and_old_binding(qtbot, binding):
    class Runtime:
        def submit(self, kind, generation, **values):
            assert values["binding"] == binding
            return str(uuid4())
    bridge = Bridge(); controller = Controller(Runtime(), bridge); controller.binding = binding
    seen = []; controller.result.connect(seen.append)
    old = controller.submit("PARTY_CHANGES", party_identity="1")
    new = controller.submit("PARTY_CHANGES", party_identity="2")
    controller.receive(Event(old, controller.generation, "PARTY_CHANGES", "old"))
    controller.receive(Event(new, controller.generation-1, "PARTY_CHANGES", "wrong generation"))
    assert seen == []
    controller.receive(Event(new, controller.generation, "PARTY_CHANGES", "current"))
    assert seen[0].result == "current"
