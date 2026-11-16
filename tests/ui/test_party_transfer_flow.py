"""Qt/controller/Huey/bootstrap/adapters/SQLite flow, using only in-memory remote fakes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json

import httpx
import pytest
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtWidgets import QMessageBox

from innoforia_tally_connector.bootstrap.dependencies import build
from innoforia_tally_connector.domain.experiments import TargetIdentity
from innoforia_tally_connector.domain.masters import Side
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.tally.gateway import COMPANY_GUID
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.main_window import MainWindow
from innoforia_tally_connector.ui.party_drag import MIME


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
@pytest.mark.parametrize("kind", ["CUSTOMER", "SUPPLIER"])
def test_full_offline_transfer_and_restart(qtbot, tmp_path, monkeypatch, side, kind):
    state = {"posts": 0, "imports": 0, "parties": [], "ledgers": []}
    source_guid = COMPANY_GUID + "-00000100"
    parent = "Sundry Debtors" if kind == "CUSTOMER" else "Sundry Creditors"
    groups = [{"GUID": "debtors", "NAME": "Sundry Debtors", "PARENT": "Primary", "ALTERID": "1"},
              {"GUID": "creditors", "NAME": "Sundry Creditors", "PARENT": "Primary", "ALTERID": "1"}]
    if side == Side.BAHI:
        state["parties"] = [{"account_id": 10, "account_name": "Selected source", "party_type": kind, "is_active": True,
            "email": "source@example.invalid", "phone": "00123", "address": "One\nTwo",
            "country": "India", "state": "State", "pincode": "012345"}]
    else:
        state["ledgers"] = [{"GUID": source_guid, "MASTERID": "10", "ALTERID": "1", "NAME": "Selected source",
            "PARENT": parent, "EMAIL": "source@example.invalid", "LEDGERPHONE": "00123", "ADDRESS_LINES": ("One", "Two"),
            "COUNTRYNAME": "India", "LEDSTATENAME": "State", "PINCODE": "012345"}]

    def http(request):
        if request.url.path.endswith("check_api_biz_setup.php"):
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Test business"}})
        if request.method == "POST":
            state["posts"] += 1
            row = {"account_id": 20, "is_active": True, **json.loads(request.content)}
            state["parties"].append(row)
            return httpx.Response(201, json={"success": True, "data": row})
        if "id" in request.url.params:
            row = next(r for r in state["parties"] if str(r["account_id"]) == request.url.params["id"])
            return httpx.Response(200, json={"success": True, "data": row})
        count = len(state["parties"])
        return httpx.Response(200, json={"success": True, "data": state["parties"],
            "pagination": {"page": 1, "limit": 200, "total": count, "total_pages": 1 if count else 0}})

    class Gateway:
        def read(self, entity="Company", company_guid=COMPANY_GUID, guid=None):
            if entity == "Company": return [{"GUID": COMPANY_GUID, "NAME": "SIS Dummy"}]
            if entity == "Group": return groups
            return [r for r in state["ledgers"] if guid is None or r["GUID"] == guid]
        def preflight_party(self, binding, root_id, draft):
            from innoforia_tally_connector.domain.experiments import Preflight
            return Preflight(destination="SIS Dummy", group_context=json.dumps({"group": {"NAME": parent, "GUID": root_id}}))
        def create_party(self, preview, root_id):
            state["imports"] += 1
            row = {"GUID": COMPANY_GUID + "-00000200", "MASTERID": "20", "ALTERID": "1", "NAME": preview.party.name, "PARENT": parent}
            for field, tag in {"email": "EMAIL", "phone": "LEDGERPHONE", "pincode": "PINCODE", "country": "COUNTRYNAME", "state": "LEDSTATENAME"}.items():
                if field in preview.party.model_fields_set: row[tag] = getattr(preview.party, field)
            if "address" in preview.party.model_fields_set: row["ADDRESS_LINES"] = tuple(preview.party.address.split("\n"))
            state["ledgers"].append(row)
            return TargetIdentity(kind="TALLY_GUID", identity=row["GUID"])
        def close(self): pass

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    def launch():
        bridge = Bridge()
        client = Client(lambda: "synthetic", httpx.Client(transport=httpx.MockTransport(http)))
        runtime, cleanup = build(tmp_path, bridge.event.emit, bahi_client=client, tally_gateway=Gateway())
        window = MainWindow()
        qtbot.addWidget(window)
        window.attach(Controller(runtime, bridge))
        runtime.start()
        window.show()
        window.verify.click()
        qtbot.waitUntil(lambda: window.customers.count() == 3, timeout=10000)
        window.customers.setCurrentIndex(window.customers.findData("debtors"))
        window.suppliers.setCurrentIndex(window.suppliers.findData("creditors"))
        window.bind.click()
        qtbot.waitUntil(lambda: window.controller.binding is not None, timeout=10000)
        return window, runtime, cleanup, bridge
    def shutdown(window, runtime, cleanup):
        runtime.shutdown(cleanup)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
        window.quitting = True
        window.close()

    window, runtime, cleanup, bridge = launch()
    transfer_id = None
    try:
        window.load.click()
        qtbot.waitUntil(lambda: window.discovery is not None, timeout=10000)
        model, view, button = (window.bahi_model, window.bahi_view, window.to_tally) if side == Side.BAHI else (window.tally_model, window.tally_view, window.to_bahi)
        view.selectRow(0)
        source = model.objects[0]
        # Check internal references and external/stale rejection without computer-use automation.
        mime = window.drag_session.issue(view, source)
        target_side = Side.TALLY if side == Side.BAHI else Side.BAHI
        assert window.drag_session.resolve(mime, view, target_side) == source
        assert window.drag_session.resolve(mime, view, side) is None
        assert window.drag_session.resolve(mime, object(), target_side) is None
        external = QMimeData(); external.setText("external party")
        assert window.drag_session.resolve(external, view, target_side) is None
        if kind == "SUPPLIER":
            class Drop:
                accepted = False
                def mimeData(self): return mime
                def source(self): return view
                def setDropAction(self, action): assert action == Qt.DropAction.CopyAction
                def accept(self): self.accepted = True
                def ignore(self): self.accepted = False
            drop = Drop()
            area = window.tally_drop if side == Side.BAHI else window.bahi_drop
            area.dropEvent(drop)
            assert drop.accepted
        else:
            button.click()
        assert state["posts"] + state["imports"] == 0
        qtbot.waitUntil(lambda: window.transfer.record is not None, timeout=10000)
        first = window.transfer.record
        for row in range(window.transfer.fields.rowCount()):
            if window.transfer.fields.item(row, 2).text().startswith(("unavailable", "invalid")):
                window.transfer.fields.item(row, 3).setCheckState(Qt.CheckState.Unchecked)
                window.transfer.fields.item(row, 4).setText("Unavailable source representation; reviewed exclusion")
        if window.transfer.exclusions():
            window.transfer.refresh.click()
            qtbot.waitUntil(lambda: window.transfer.record is not None and window.transfer.record.preview.id != first.preview.id, timeout=10000)
        assert window.transfer.record.preview.source_confirmation_required
        assert not window.transfer.approve.isEnabled() and not window.transfer.normal_party.isChecked()
        window.transfer.normal_party.setChecked(True)
        assert window.transfer.approve.isEnabled()
        transfer_id = window.transfer.record.preview.id
        window.transfer.reviewer.setText("Offline integration reviewer")
        window.transfer.approve.click()
        qtbot.waitUntil(lambda: window.transfer.record is not None and window.transfer.record.state == "SUCCEEDED", timeout=10000)
        qtbot.waitUntil(lambda: not window.controller.pending, timeout=10000)
        assert state["posts"] == (1 if side == Side.TALLY else 0)
        assert state["imports"] == (1 if side == Side.BAHI else 0)
        assert window.link_model.rowCount() == 1
        assert not window.transfer.approve.isEnabled()
    finally:
        shutdown(window, runtime, cleanup)
    window, runtime, cleanup, bridge = launch()
    try:
        window.activity.load(0)
        qtbot.waitUntil(lambda: window.activity.model.rowCount() > 0, timeout=10000)
        records = window.activity.model.objects
        row = next(i for i, r in enumerate(records) if r.preview.id == transfer_id)
        window.activity.view.selectRow(row)
        window.activity.inspect.click()
        qtbot.waitUntil(lambda: window.transfer.record is not None, timeout=10000)
        assert window.transfer.record.state == "SUCCEEDED" and window.transfer.record.target.identity
        assert window.transfer.record.source_normal_party_confirmed
        assert window.link_model.rowCount() == 1
        assert state["posts"] + state["imports"] == 1
        assert not window.transfer.approve.isEnabled()
    finally:
        shutdown(window, runtime, cleanup)
