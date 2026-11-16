import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QMessageBox
from innoforia_tally_connector.domain.masters import Side, PartyContent, PartyType
from innoforia_tally_connector.domain.experiments import Direction, ExperimentResult, ExperimentPreview, Preflight
from innoforia_tally_connector.domain.party_transfer import PartyDraft, FieldDecision
from innoforia_tally_connector.ui.main_window import MainWindow
from innoforia_tally_connector.ui.pages.transfer import TransferPage


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
def test_mouse_gesture_starts_internal_copy_drag(qtbot, binding, observation, monkeypatch, side):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from innoforia_tally_connector.ui import party_drag
    window = MainWindow()
    window.quitting = True
    qtbot.addWidget(window)
    sent = []
    window.controller = SimpleNamespace(binding=binding, pending={}, generation=1,
        submit=lambda kind, **values: sent.append((kind, values)))
    window.discovery = object()
    model, view, area = ((window.bahi_model, window.bahi_view, window.tally_drop)
        if side == Side.BAHI else (window.tally_model, window.tally_view, window.bahi_drop))
    source = observation(side, is_active=True, is_system=False)
    model.replace([("Source", "Supplier", "Yes", "1")[:model.columnCount()]], [source])
    window.drag_session.reset(binding, 1)
    window.busy(False)
    window.show()
    qtbot.wait(10)
    drags = []
    class Drag:
        def __init__(self, origin): self.origin = origin
        def setMimeData(self, mime): self.mime = mime
        def exec(self, actions):
            assert actions == Qt.DropAction.CopyAction
            drags.append(self)
            drag = self
            class Drop:
                accepted = False
                def mimeData(self): return drag.mime
                def source(self): return drag.origin
                def setDropAction(self, action): assert action == Qt.DropAction.CopyAction
                def accept(self): self.accepted = True
                def ignore(self): self.accepted = False
            drop = Drop()
            area.dragEnterEvent(drop)
            assert drop.accepted
            area.dropEvent(drop)
            assert drop.accepted
            return actions
    monkeypatch.setattr(party_drag, "QDrag", Drag)
    start = view.visualRect(model.index(0, 0)).center()
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    # Send the pressed-button move through Qt's view event path, rather than
    # calling startDrag/dropEvent alone (which missed the model flag regression).
    for distance in (2, QApplication.startDragDistance() + 20):
        point = QPointF(start.x() + distance, start.y())
        event = QMouseEvent(QEvent.Type.MouseMove, point, QPointF(view.viewport().mapToGlobal(point.toPoint())),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(view.viewport(), event)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert len(drags) == 1
    assert [kind for kind, _ in sent] == ["TRANSFER_PREPARE"]
    assert sent[0][1]["source"] == source
    assert not window.drag_session.references
    assert not model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    assert not window.link_model.flags(window.link_model.index(0, 0)) & Qt.ItemFlag.ItemIsDragEnabled


def test_blocked_preview_opens_unfiltered_activity_without_creation(qtbot, binding):
    window = MainWindow()
    window.quitting = True
    qtbot.addWidget(window)
    sent = []
    window.controller = SimpleNamespace(binding=binding, pending={}, generation=1,
        submit=lambda kind, **values: sent.append((kind, values)))
    window.activity.status.setCurrentIndex(2)
    window.activity.kind.setCurrentIndex(1)
    window.receive(SimpleNamespace(kind="TRANSFER_PREPARE", result=None,
        error="An active or unresolved operation blocks another preview"))
    assert window.transfer.record is None
    assert not window.transfer.approve.isEnabled()
    assert "no create attempt" in window.transfer.report.toPlainText()
    window.transfer.activity.click()
    assert window.tabs.currentWidget() == window.activity
    assert sent == [("ACTIVITY", {"offset": 0, "status_filter": None, "type_filter": None})]


@pytest.mark.parametrize("kind", ["TRANSFER_PREPARE", "TRANSFER_CREATE", "ACTIVITY_DETAIL"])
def test_connection_failure_advice_depends_on_action(qtbot, kind):
    sent = []
    page = TransferPage(lambda *args, **kwargs: sent.append(args), lambda *args: None)
    qtbot.addWidget(page)
    page.receive(SimpleNamespace(kind=kind, result=None,
        error="Bahi GET check_api_biz_setup.php timed out; verify connections and retry the read"))
    page.set_busy(False, True)
    text = page.report.toPlainText()
    if kind == "TRANSFER_PREPARE":
        assert "this action sent no create request" in text
        assert "Verify connections" in text and "do not cancel unrelated work" in text
    else:
        assert "no create request" not in text
        assert "read-only reconciliation" in text
    assert "Cancel it only" not in text
    assert page.record is None and not page.approve.isEnabled()
    assert not sent


def test_existing_row_drop_opens_link_review_and_stale_reference_rejected(qtbot, binding, observation, monkeypatch):
    window = MainWindow()
    window.quitting = True
    qtbot.addWidget(window)
    sent = []
    window.controller = SimpleNamespace(binding=binding, pending={}, generation=1,
        submit=lambda kind, **values: sent.append((kind, values)))
    left = observation(is_active=True, is_system=False)
    right = observation(Side.TALLY, "2", name="Other name")
    window.bahi_model.replace([("Bahi", "Supplier", "Yes", "1")], [left])
    window.tally_model.replace([("Tally", "Supplier", "2")], [right])
    window.drag_session.reset(binding, 1)
    window.reviewer.setText("Link reviewer")
    window.show()
    qtbot.wait(10)
    mime = window.drag_session.issue(window.bahi_view, left)
    class Drop:
        accepted = False
        def mimeData(self): return mime
        def source(self): return window.bahi_view
        def position(self): return QPointF(window.tally_view.visualRect(window.tally_model.index(0, 0)).center())
        def setDropAction(self, action): assert action == Qt.DropAction.CopyAction
        def accept(self): self.accepted = True
        def ignore(self): self.accepted = False
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    drop = Drop()
    window.tally_view.dropEvent(drop)
    assert drop.accepted and sent[0][0] == "LINK"
    assert sent[0][1]["bahi"].identity == "1" and sent[0][1]["tally"].identity == "2"
    assert not any(kind == "TRANSFER_CREATE" for kind, _ in sent)
    window.drag_session.reset(binding, 2)
    window.tally_view.dropEvent(drop)
    assert not drop.accepted
    mime = window.drag_session.issue(window.bahi_view, left)
    window.tally_model.objects[0] = right.model_copy(update={"party_type": PartyType.CUSTOMER})
    window.tally_view.dropEvent(drop)
    assert not drop.accepted and len(sent) == 1


def test_exclusions_require_repreview_cancel_does_not_create(qtbot, binding, observation, monkeypatch):
    sent, notices = [], []
    page = TransferPage(lambda kind, **values: sent.append((kind, values)), lambda *args: None)
    qtbot.addWidget(page)
    source = observation(content=PartyContent(name="Source", email=None), content_schema=2, is_system=False)
    now = datetime.now(timezone.utc)
    preview = ExperimentPreview(id="preview", binding=binding, generation=1, direction=Direction.TO_TALLY,
        source=source, kind="TRANSFER", party=PartyDraft(name="Source", party_type=source.party_type, email=None),
        preflight=Preflight(group_context='{"group":"Sundry Creditors"}', destination="Test Tally"),
        created_at=now, expires_at=now + timedelta(minutes=5),
        decisions=(FieldDecision(field="name", status="included"), FieldDecision(field="email", status="invalid", reason="XML null unavailable")))
    page.receive(SimpleNamespace(error=None, result=ExperimentResult(preview=preview, state="PENDING", attempted=False)))
    page.set_busy(False, True)
    assert not page.approve.isEnabled()
    page.fields.item(0, 3).setCheckState(Qt.CheckState.Unchecked)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args))
    page.refresh.click()
    assert notices and not sent
    page.fields.item(0, 4).setText("Do not transfer unavailable null representation")
    page.refresh.click()
    assert sent[-1][0] == "TRANSFER_PREPARE" and sent[-1][1]["exclusions"] == {"email": "Do not transfer unavailable null representation"}
    # A completed revised preview, with exclusions in its digest, is separately approved.
    revised = preview.model_copy(update={"party": PartyDraft(name="Source", party_type=source.party_type),
        "decisions": (FieldDecision(field="email", status="excluded", reason="Reviewed exclusion"),)})
    page.receive(SimpleNamespace(error=None, result=ExperimentResult(preview=revised, state="PENDING", attempted=False)))
    page.set_busy(False, True)
    page.reviewer.setText("Reviewer")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
    page.approve.click()
    assert not any(kind == "TRANSFER_CREATE" for kind, _ in sent)
    page.generation = 2
    page.set_busy(False, True)
    assert not page.approve.isEnabled()  # Restart requires renewal, even within the old expiry.


def test_confirmation_preserves_literal_business_text(qtbot, monkeypatch):
    from innoforia_tally_connector.ui.confirmations import confirm_plain
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    text = "Name: <b>Source & party</b>\nEmail: source@example.invalid"
    def inspect(dialog):
        assert dialog.textFormat() == Qt.TextFormat.PlainText
        assert dialog.text() == text
        assert dialog.defaultButton() == dialog.button(QMessageBox.StandardButton.No)
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "exec", inspect)
    assert not confirm_plain(parent, "Review exact values", text)
