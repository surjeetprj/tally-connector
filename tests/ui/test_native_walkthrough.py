"""Actual Qt -> controller -> Huey -> workflow -> SQLite -> queued Qt results."""
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from innoforia_tally_connector.application.masters.discovery import DiscoveryWorkflow
from innoforia_tally_connector.domain.masters import ConnectionSnapshot, GroupObservation, PartyScan, Side
from innoforia_tally_connector.execution.consumer import Runtime
from innoforia_tally_connector.integrations.tally.parties import validate_classification
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.main_window import MainWindow


def test_native_link_survives_restart(qtbot, qapp, tmp_path, store, observation, monkeypatch):
    groups = (GroupObservation(identity="a", name="Synthetic Debtors", parent="Primary", version="1"),
              GroupObservation(identity="b", name="Synthetic Creditors", parent="Primary", version="1"))
    snapshot = ConnectionSnapshot(business_id=52, business_name="Synthetic only", company_guid="synthetic-company",
                                  company_name="Synthetic only", groups=groups)

    class Reader:
        def __init__(self, side):
            self.side = side

        def detail(self, binding, identity):
            return observation(self.side, identity, binding=binding, is_active=True if self.side == Side.BAHI else None)

        def scan(self, binding):
            identities = ["1"] if self.side == Side.BAHI else ["2", "3"]
            return PartyScan(binding=binding, side=self.side,
                records=tuple(self.detail(binding, identity) for identity in identities),
                observed_at=datetime.now(timezone.utc), pages_read=(1,), total_pages=1)

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    journal = DiscoveryStore(store.engine)

    def launch():
        bridge = Bridge()
        workflow = DiscoveryWorkflow(lambda: snapshot, lambda _: (Reader(Side.BAHI), Reader(Side.TALLY)),
                                     validate_classification, journal, store, "synthetic credential reference")
        runtime = Runtime(tmp_path, journal, store, workflow.handle, bridge.event.emit)
        controller = Controller(runtime, bridge)
        window = MainWindow()
        qtbot.addWidget(window)
        window.attach(controller)
        runtime.start()
        window.show()
        window.verify.click()
        qtbot.waitUntil(lambda: window.customers.count() == 3, timeout=10000)
        window.customers.setCurrentIndex(window.customers.findData("a"))
        window.suppliers.setCurrentIndex(window.suppliers.findData("b"))
        window.bind.click()
        qtbot.waitUntil(lambda: controller.binding is not None, timeout=10000)
        return window, runtime, controller, bridge

    def shutdown(window, runtime):
        runtime.shutdown(lambda: None)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
        window.quitting = True
        window.close()

    window, runtime, controller, bridge = launch()
    try:
        window.load.click()
        qtbot.waitUntil(lambda: window.discovery is not None, timeout=10000)
        assert len(window.discovery.candidates) == 2
        assert window.link_model.rowCount() == 0
        window.tabs.setCurrentIndex(1)
        window.candidate_view.selectRow(1)  # Explicitly choose the second ambiguous candidate.
        window.reviewer.setText("Synthetic UI reviewer")
        window.link.click()
        qtbot.waitUntil(lambda: window.link_model.rowCount() == 1, timeout=10000)
        assert window.link_model.objects[0].tally.identity == "3"
        assert len(store.list(controller.binding)) == 1
        window.tabs.setCurrentIndex(2)
        Path("build").mkdir(exist_ok=True)
        window.grab().save("build/party-native-walkthrough.png")
    finally:
        shutdown(window, runtime)
    window, runtime, controller, bridge = launch()
    try:
        qtbot.waitUntil(lambda: window.link_model.rowCount() == 1, timeout=10000)
        assert window.link_model.objects[0].tally.identity == "3"
        assert window.discovery is None  # Restart never fabricates a fresh scan.
        print("Native walkthrough platform:", qapp.platformName())
    finally:
        shutdown(window, runtime)
