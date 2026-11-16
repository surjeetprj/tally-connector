import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from innoforia_tally_connector.domain.batches import TransferPolicy, TransferBatch, BatchItem
from innoforia_tally_connector.domain.experiments import ExperimentPreview, Direction, Preflight
from innoforia_tally_connector.domain.party_transfer import PartyDraft, FieldDecision
from innoforia_tally_connector.domain.commands import Event
from innoforia_tally_connector.domain.masters import Side
from innoforia_tally_connector.ui.pages.batch_review import BatchReview
from innoforia_tally_connector.ui.workspace import Workspace
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.bridge import Bridge


@pytest.fixture
def preview_batch(binding, observation):
    now = datetime.now(timezone.utc)
    items = []
    for n in range(2):
        source = observation(identity=str(n), name=f"Party {n}", is_active=True)
        preview = ExperimentPreview(id=f"preview{n}", binding=binding, generation=1, direction=Direction.TO_TALLY,
            kind="TRANSFER", source=source, source_confirmation_required=True,
            party=PartyDraft(name=source.content.name, party_type=source.party_type),
            created_at=now, expires_at=now + timedelta(minutes=5),
            preflight=Preflight(destination="Synthetic", group_context='{"group":"Suppliers"}'),
            decisions=(FieldDecision(field="name", status="included"),))
        items.append(BatchItem(source=source, status="Ready", preview=preview))
    return TransferBatch(id="batch", binding=binding, generation=1, direction=Direction.TO_TALLY,
        policy=TransferPolicy(binding=binding, operator="Owner"), created_at=now, items=tuple(items))


def test_one_confirmation_covers_exact_ready_subset(qtbot, preview_batch):
    parent = QWidget(); qtbot.addWidget(parent)
    sent = []
    page = BatchReview(parent, lambda kind, **values: sent.append((kind, values)), lambda *_: None)
    page.receive(preview_batch, 1)
    page.resize(750, 500); page.show(); qtbot.wait(10)
    assert not page.normal.isChecked() and not page.confirm.isEnabled()
    assert not page.candidates.isVisible() and not page.link_button.isVisible()
    assert page.confirm.isVisible() and page.details.height() > 50
    page.normal.setChecked(True); page.confirm.click()
    page.update_actions()
    assert not page.confirm.isEnabled()  # Timer cannot re-enable a pending approval.
    assert sent[0][0] == "BATCH_APPROVE"
    approval = sent[0][1]["approval"]
    assert approval.ready_ids == ("preview0", "preview1") and approval.normal_confirmed
    assert approval.digest == preview_batch.digest


@pytest.mark.parametrize("reason", ["expired", "generation"])
def test_stale_preview_refreshes_without_creating(qtbot, preview_batch, reason):
    parent = QWidget(); qtbot.addWidget(parent)
    sent = []
    page = BatchReview(parent, lambda kind, **values: sent.append((kind, values)), lambda *_: None)
    batch = preview_batch
    if reason == "expired":
        batch = batch.model_copy(update={"items": tuple(i.model_copy(update={"preview": i.preview.model_copy(update={
            "created_at": i.preview.created_at - timedelta(minutes=10), "expires_at": i.preview.expires_at - timedelta(minutes=10)})}) for i in batch.items)})
    page.receive(batch, 2 if reason == "generation" else 1)
    page.confirm.click()
    assert sent[0][0] == "BATCH_PREPARE"
    assert sent[0][1]["sources"] == tuple(i.source for i in batch.items)
    assert not any(kind == "BATCH_APPROVE" for kind, _ in sent)


def test_close_without_approval_sends_nothing(qtbot, preview_batch):
    parent = QWidget(); qtbot.addWidget(parent)
    sent = []
    page = BatchReview(parent, lambda *args, **kwargs: sent.append(args), lambda *_: None)
    page.receive(preview_batch, 1); page.show(); page.close_button.click()
    assert not sent


@pytest.mark.parametrize("side", [Side.BAHI, Side.TALLY])
def test_checked_multirow_button_and_internal_drag_agree(qtbot, binding, observation, monkeypatch, side):
    from innoforia_tally_connector.ui import party_drag
    window = Workspace(); window.quitting = True; qtbot.addWidget(window)
    sent = []
    window.controller = SimpleNamespace(binding=binding, generation=1, pending={},
        submit=lambda kind, **values: sent.append((kind, values)))
    window.policy = TransferPolicy(binding=binding, operator="Owner")
    window.discovery = SimpleNamespace()
    model, view = window.models[side], window.views[side]
    sources = tuple(observation(side, str(i), name=f"Source {i}", is_active=True) for i in range(2))
    model.replace([(r.content.name, r.party_type, "Available", r.identity) for r in sources], sources)
    for row in range(2): model.setData(model.index(row, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    window.drag_session.reset(binding, 1); window.update_controls()
    window.transfer_buttons[side].click()
    expected = sent.pop()
    class Drag:
        def __init__(self, origin): self.origin = origin
        def setMimeData(self, mime): self.mime = mime
        def exec(self, actions):
            area = party_drag.CreateDropArea(Side.TALLY if side == Side.BAHI else Side.BAHI, window.drag_session)
            area.review.connect(window.drop)
            drag = self
            class Drop:
                def mimeData(self): return drag.mime
                def source(self): return drag.origin
                def setDropAction(self, action): assert action == Qt.DropAction.CopyAction
                def accept(self): pass
                def ignore(self): pytest.fail("Valid multirow drop rejected")
            area.dropEvent(Drop())
            return actions
    monkeypatch.setattr(party_drag, "QDrag", Drag)
    view.startDrag(Qt.DropAction.CopyAction)
    assert sent == [expected] and expected[1]["sources"] == sources
    assert not window.drag_session.references
    window.prepare(tuple(sources[0] for _ in range(101)))
    assert len(sent) == 1 and "1–100" in window.status.text()


def test_batch_events_keep_generation_binding_and_errors(qtbot, binding):
    bridge = Bridge()
    controller = Controller(SimpleNamespace(), bridge)
    controller.binding = binding
    received = []
    controller.result.connect(received.append)
    generation = controller.generation
    controller.receive(Event("old", generation - 1, "BATCH_STEP", SimpleNamespace(binding=binding)))
    controller.receive(Event("other", generation, "BATCH_STEP", SimpleNamespace(binding=binding.model_copy(update={"generation": 2}))))
    assert not received
    controller.receive(Event("failure", generation, "BATCH_STEP", error="Storage interrupted; restart and inspect"))
    assert received[0].error.startswith("Storage interrupted")
