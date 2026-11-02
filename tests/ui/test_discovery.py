import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox

from innoforia_tally_connector.application.masters.parties import compare_scans
from innoforia_tally_connector.domain.commands import Event
from innoforia_tally_connector.domain.masters import PartyScan, Side
from innoforia_tally_connector.execution.consumer import Runtime
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.main_window import MainWindow
import sqlite3


def test_controller_discards_stale_events(qtbot, binding):
    class FakeRuntime:
        def submit(self, kind, generation, **values):
            return "current"
    bridge = Bridge()
    controller = Controller(FakeRuntime(), bridge)
    results = []
    controller.result.connect(results.append)
    controller.submit("VERIFY")
    bridge.event.emit(Event("old", controller.generation, "VERIFY", "wrong"))
    bridge.event.emit(Event("current", controller.generation - 1, "VERIFY", "wrong"))
    bridge.event.emit(Event("current", controller.generation, "VERIFY", "correct"))
    qtbot.waitUntil(lambda: len(results) == 1)
    assert results[0].result == "correct"


def test_worker_round_trip_and_gui_heartbeat(qtbot, store, tmp_path):
    bridge = Bridge()
    completed, thread_ids, beats = [], [], []
    def handler(command):
        thread_ids.append(threading.get_ident())
        time.sleep(0.15)
        return "synthetic result"
    runtime = Runtime(tmp_path, DiscoveryStore(store.engine), store, handler, bridge.event.emit)
    controller = Controller(runtime, bridge)
    controller.result.connect(completed.append)
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(5)
    runtime.start()
    try:
        identity = controller.submit("VERIFY")
        assert controller.submit("VERIFY") != identity  # New verification intentionally changes generation.
        qtbot.waitUntil(lambda: bool(completed), timeout=10000)
        assert completed[-1].result == "synthetic result"
        assert len(beats) > 5
        assert all(identity != threading.get_ident() for identity in thread_ids)
    finally:
        timer.stop()
        runtime.shutdown(lambda: None)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)


def test_native_candidate_review_and_manual_pair(qtbot, binding, observation, store, monkeypatch):
    left, right = observation(), observation(Side.TALLY, "2", name="Different name")
    now = datetime.now(timezone.utc)
    a = PartyScan(binding=binding, side=Side.BAHI, records=(left,), observed_at=now, pages_read=(1,), total_pages=1)
    b = PartyScan(binding=binding, side=Side.TALLY, records=(right,), observed_at=now, pages_read=(1,), total_pages=1)
    class FakeController:
        binding = None
        def submit(self, kind, **values):
            sent.append((kind, values))
    sent = []
    window = MainWindow()
    qtbot.addWidget(window)
    window.controller = FakeController()
    window.controller.binding = binding
    window.receive(Event("load", 1, "LOAD", compare_scans(binding, a, b, store)))
    window.show()
    window.bahi_view.selectRow(0)
    window.tally_view.selectRow(0)
    window.reviewer.setText("Synthetic reviewer")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.confirm_link()
    assert sent[0][0] == "LINK" and sent[0][1]["bahi"] == left
    assert "Different name" in window.details.toPlainText()
    assert "[absent]" in window.details.toPlainText()
    Path("build").mkdir(exist_ok=True)
    window.grab().save("build/party-discovery-synthetic.png")
    window.quitting = True
    window.close()


def test_inactive_party_is_visible_but_confirmation_blocked(qtbot, binding, observation):
    window = MainWindow()
    qtbot.addWidget(window)
    left, right = observation(is_active=False), observation(Side.TALLY, "2")
    window.bahi_model.replace([(left.content.name, left.party_type, False, left.identity)], [left])
    window.tally_model.replace([(right.content.name, right.party_type, right.identity)], [right])
    window.bahi_view.selectRow(0)
    window.tally_view.selectRow(0)
    window.confirm_link()
    assert "Inactive" in window.status.text()
    window.quitting = True


def test_capture_lock_wait_keeps_gui_responsive(qtbot, store, tmp_path):
    bridge, events, beats = Bridge(), [], []
    runtime = Runtime(tmp_path, DiscoveryStore(store.engine), store, lambda command: "done", bridge.event.emit)
    controller = Controller(runtime, bridge)
    controller.result.connect(events.append)
    runtime.start()
    locked = sqlite3.connect(store.engine.url.database)
    locked.execute("BEGIN IMMEDIATE")
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(5)
    try:
        identity = controller.submit("SAVED")
        assert controller.submit("SAVED") == identity
        QTimer.singleShot(100, locked.commit)
        qtbot.waitUntil(lambda: bool(events), timeout=10000)
        assert len(beats) > 5 and events[0].result == "done"
    finally:
        locked.close()
        timer.stop()
        runtime.shutdown(lambda: None)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)


def test_single_instance_rejects_live_owner(qapp, tmp_path):
    from innoforia_tally_connector.host.windows.single_instance import acquire
    lock = acquire(tmp_path)
    try:
        with pytest.raises(ValueError, match="already running"):
            acquire(tmp_path)
    finally:
        lock.unlock()


def test_quit_before_consumer_start_still_closes_resources(qtbot, store, tmp_path):
    cleaned = []
    runtime = Runtime(tmp_path, DiscoveryStore(store.engine), store,
                      lambda _: pytest.fail("No task may execute during startup shutdown"), lambda _: None)
    runtime.shutdown(lambda: cleaned.append(True))
    qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
    assert cleaned == [True] and not runtime.started
