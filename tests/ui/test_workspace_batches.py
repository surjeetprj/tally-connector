"""Production workspace -> queued Qt -> Huey -> adapters -> SQLite, fake remotes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import time
import pytest
import httpx
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox
from innoforia_tally_connector.bootstrap.dependencies import build
from innoforia_tally_connector.domain.experiments import TargetIdentity, Preflight
from innoforia_tally_connector.domain.masters import Side
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.tally.gateway import COMPANY_GUID
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.workspace import Workspace


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
@pytest.mark.parametrize("kind", ["CUSTOMER", "SUPPLIER"])
def test_workspace_batch_and_automatic_restart(qtbot, tmp_path, monkeypatch, side, kind):
    parent = "Sundry Debtors" if kind == "CUSTOMER" else "Sundry Creditors"
    groups = [{"GUID": "debtors", "NAME": "Sundry Debtors", "PARENT": "Primary", "ALTERID": "1"},
              {"GUID": "creditors", "NAME": "Sundry Creditors", "PARENT": "Primary", "ALTERID": "1"}]
    state = {"parties": [], "ledgers": [], "posts": 0, "imports": 0}
    for number in (1, 2):
        if side == Side.BAHI:
            state["parties"].append({"account_id": number, "account_name": f"Source {number}", "party_type": kind,
                "is_active": True, "email": f"source{number}@example.invalid", "phone": "00123", "pincode": "012345"})
        else:
            state["ledgers"].append({"GUID": COMPANY_GUID + f"-{number:08x}", "NAME": f"Source {number}",
                "MASTERID": str(number), "ALTERID": "1", "PARENT": parent,
                "EMAIL": f"source{number}@example.invalid", "LEDGERPHONE": "00123", "PINCODE": "012345"})
    def http(request):
        if request.url.path.endswith("check_api_biz_setup.php"):
            return httpx.Response(200, json={"success": True, "data": {"biz_id": 52, "biz_name": "Synthetic business"}})
        if request.method == "POST":
            time.sleep(0.03)
            state["posts"] += 1
            row = {"account_id": 20 + state["posts"], "is_active": True, **json.loads(request.content)}
            state["parties"].append(row)
            return httpx.Response(201, json={"success": True, "data": row})
        if "id" in request.url.params:
            row = next(r for r in state["parties"] if str(r["account_id"]) == request.url.params["id"])
            return httpx.Response(200, json={"success": True, "data": row})
        count = len(state["parties"])
        return httpx.Response(200, json={"success": True, "data": state["parties"],
            "pagination": {"page": 1, "limit": 200, "total": count, "total_pages": 1 if count else 0}})
    class Gateway:
        stopped = lambda self: False
        def read(self, entity="Company", company_guid=COMPANY_GUID, guid=None):
            if entity == "Company": return [{"GUID": COMPANY_GUID, "NAME": "SIS Dummy"}]
            if entity == "Group": return groups
            return [r for r in state["ledgers"] if guid is None or r["GUID"] == guid]
        def preflight_party(self, binding, root, draft):
            return Preflight(destination="SIS Dummy", group_context=json.dumps({"group": {"GUID": root, "NAME": parent}}))
        def create_party(self, preview, root):
            time.sleep(0.03)
            state["imports"] += 1
            identity = COMPANY_GUID + f"-{20 + state['imports']:08x}"
            row = {"GUID": identity, "MASTERID": str(20 + state["imports"]), "ALTERID": "1",
                "NAME": preview.party.name, "PARENT": parent}
            for field, tag in {"email": "EMAIL", "phone": "LEDGERPHONE", "pincode": "PINCODE"}.items():
                if field in preview.party.model_fields_set: row[tag] = getattr(preview.party, field)
            state["ledgers"].append(row)
            return TargetIdentity(kind="TALLY_GUID", identity=identity)
        def close(self): pass
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    def launch():
        bridge = Bridge()
        api = Client(lambda: "synthetic-key", httpx.Client(transport=httpx.MockTransport(http)))
        runtime, cleanup = build(tmp_path, bridge.event.emit, bahi_client=api, tally_gateway=Gateway())
        window = Workspace()
        qtbot.addWidget(window)
        runtime.start()
        window.show()
        window.attach(Controller(runtime, bridge))
        return window, runtime, cleanup, bridge
    def shutdown(window, runtime, cleanup):
        runtime.shutdown(cleanup)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
        window.quitting = True
        window.review.close()
        window.close()
    window, runtime, cleanup, bridge = launch()
    batch_id = None
    ticks = []
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: ticks.append(True))
    heartbeat.start(10)
    try:
        qtbot.waitUntil(lambda: window.customers.count() == 3, timeout=10000)
        assert [window.tabs.tabText(i) for i in range(3)] == ["Parties", "Activity", "Settings"]
        window.customers.setCurrentIndex(window.customers.findData("debtors"))
        window.suppliers.setCurrentIndex(window.suppliers.findData("creditors"))
        window.bind.click()
        qtbot.waitUntil(lambda: window.controller.binding is not None and not window.controller.pending, timeout=10000)
        assert window.policy is None
        window.operator.setText("Owner")
        window.save_policy.click()
        try:
            qtbot.waitUntil(lambda: window.policy is not None and window.discovery is not None and not window.controller.pending, timeout=10000)
        except Exception:
            pytest.fail(f"Setup did not finish: {window.status.text()}; pending={window.controller.pending}; inflight={runtime.inflight}")
        model, view = window.models[side], window.views[side]
        for row in range(2): model.setData(model.index(row, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        window.transfer_buttons[side].click()
        qtbot.waitUntil(lambda: window.current_batch is not None and not window.controller.pending, timeout=10000)
        batch_id = window.current_batch.id
        assert state["posts"] + state["imports"] == 0
        assert not window.review.normal.isChecked() and not window.review.confirm.isEnabled()
        assert all(i.status == "Ready" for i in window.current_batch.items)
        assert window.review.view.height() > 100 and window.review.details.height() > 80
        window.review.normal.setChecked(True)
        before_ticks = len(ticks)
        window.review.confirm.click()
        qtbot.waitUntil(lambda: window.current_batch.state == "SUCCEEDED" and not window.controller.pending, timeout=10000)
        assert state["posts"] + state["imports"] == 2
        assert len(ticks) - before_ticks >= 2
        assert window.saved_model.rowCount() == 2
        assert all(i.result.source_normal_party_confirmed for i in window.current_batch.items)
    finally:
        shutdown(window, runtime, cleanup)
        heartbeat.stop()
    window, runtime, cleanup, bridge = launch()
    try:
        # No Verify, group selection, Bind, operator entry or Load clicks on restart.
        qtbot.waitUntil(lambda: window.discovery is not None and window.policy is not None and not window.controller.pending, timeout=10000)
        assert window.operator.text() == "Owner" and window.saved_model.rowCount() == 2
        assert state["posts"] + state["imports"] == 2
        assert batch_id in {b.id for b in window.batch_model.objects}
        restored = next(b for b in window.batch_model.objects if b.id == batch_id)
        assert restored.state == "SUCCEEDED"
        window.models[side].checked.add(window.models[side].objects[0].identity)
        window.transfer_buttons[side].click()
        qtbot.waitUntil(lambda: window.current_batch is not None and not window.controller.pending, timeout=10000)
        assert window.current_batch.items[0].status == "Already linked"
        assert state["posts"] + state["imports"] == 2
    finally:
        shutdown(window, runtime, cleanup)
