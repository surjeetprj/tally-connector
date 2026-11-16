from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from innoforia_tally_connector.domain.experiments import Direction, ExperimentResult, Preflight, new_preview, synthetic_supplier
from innoforia_tally_connector.ui.pages.experiment import ExperimentPage
from innoforia_tally_connector.ui.main_window import MainWindow
from innoforia_tally_connector.domain.commands import Command


def test_main_window_experiment_dispatch(qtbot, binding):
    sent = []
    window = MainWindow()
    window.quitting = True
    qtbot.addWidget(window)
    class Controller:
        def submit(self, kind, **values):
            Command(id="native-preview", kind=kind, generation=1, **values)
            sent.append((kind, values))
    window.controller = Controller()
    window.controller.binding = binding
    window.busy(False)
    window.activity.load(0)
    assert sent == [("ACTIVITY", {"offset": 0, "status_filter": None, "type_filter": None})]


def test_direction_approval_cancellation_and_exact_digest(qtbot, binding, monkeypatch):
    sent = []
    page = ExperimentPage(lambda kind, **values: sent.append((kind, values)))
    qtbot.addWidget(page)
    page.set_busy(False, True)
    assert page.direction.currentData() is None and not page.prepare.isEnabled()
    page.prepare_preview()
    assert sent == []
    page.direction.setCurrentIndex(2)
    page.prepare.click()
    assert sent == [("EXP_PREPARE", {"direction": Direction.TO_BAHI})]
    sent.clear()
    preview = new_preview(binding, 1, Direction.TO_BAHI, synthetic_supplier(),
                          Preflight(group_context='{"group":"server configured; code/id not exposed"}', destination="Synthetic"))
    page.receive(SimpleNamespace(error=None, result=ExperimentResult(preview=preview, state="PENDING", attempted=False)))
    page.set_busy(False, True)
    assert page.approve.isEnabled() and preview.party.email in page.report.toPlainText()
    page.reviewer.setText("Reviewer")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    page.approve_create()
    assert sent == []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    page.approve_create()
    assert sent == [("EXP_CREATE", dict(experiment_id=preview.id, direction=Direction.TO_BAHI,
                                       approval_digest=preview.digest, reviewer="Reviewer"))]
    page.direction.setCurrentIndex(1)
    assert page.record is None and not page.approve.isEnabled()
