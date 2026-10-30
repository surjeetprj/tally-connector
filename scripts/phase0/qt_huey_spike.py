"""Local-only Qt/Huey lifecycle experiment; no Bahi/Tally access or credentials."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument("--runtime-dir", type=Path, required=True)
PARSER.add_argument("--mode", choices=("seed", "run"), default="run")
ARGS = PARSER.parse_args()
RUNTIME = ARGS.runtime_dir.resolve()
RUNTIME.mkdir(parents=True, exist_ok=True)


def report_fatal(error_type, error, tb):
    # This process never loads business data or credentials. Keep startup failures
    # observable even in a windowless executable, without leaving a modal dialog.
    (RUNTIME / "fatal.json").write_text(json.dumps({
        "error_type": error_type.__name__, "message": str(error),
        "frozen": bool(getattr(sys, "frozen", False))}) + "\n", encoding="utf-8")


sys.excepthook = report_fatal

from huey import SqliteHuey
from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

METADATA = RUNTIME / "spike-metadata.db"
QUEUE = SqliteHuey("connector-phase0", filename=str(RUNTIME / "spike-queue.db"),
                  immediate=False, results=False)
MAIN_THREAD = threading.get_ident()
ACTIVE = 0
MAX_ACTIVE = 0
WORKER_THREADS = set()
COUNTER_LOCK = threading.Lock()


def db():
    conn = sqlite3.connect(METADATA, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


class Bridge(QObject):
    completed = Signal(str)


BRIDGE = None


@QUEUE.task(retries=1, retry_delay=1)
def execute_operation(operation_id: str):
    global ACTIVE, MAX_ACTIVE
    with db() as conn:
        row = conn.execute("SELECT state, attempts FROM operations WHERE id=?",
                           (operation_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown experiment operation")
        if row[0] == "SUCCEEDED":
            return
        conn.execute("UPDATE operations SET state='APPLYING', attempts=attempts+1 WHERE id=?",
                     (operation_id,))
    with COUNTER_LOCK:
        ACTIVE += 1
        MAX_ACTIVE = max(MAX_ACTIVE, ACTIVE)
        WORKER_THREADS.add(threading.get_ident())
    try:
        time.sleep(0.12)  # Bounded stand-in work; never external IO.
        if operation_id == "retry-once" and row[1] == 0:
            with db() as conn:
                conn.execute("UPDATE operations SET state='RETRY_WAIT' WHERE id=?", (operation_id,))
            raise RuntimeError("Expected Phase 0 retry experiment")
        with db() as conn:
            conn.execute("UPDATE operations SET state='SUCCEEDED' WHERE id=?", (operation_id,))
        BRIDGE.completed.emit(operation_id)
    finally:
        with COUNTER_LOCK:
            ACTIVE -= 1


def main():
    global BRIDGE
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, state TEXT, attempts INTEGER)")
        conn.execute("PRAGMA user_version=1")
    if ARGS.mode == "seed":
        with db() as conn:
            for name in ("first", "retry-once", "third"):
                conn.execute("INSERT OR IGNORE INTO operations VALUES (?, 'PENDING', 0)", (name,))
        for name in ("first", "retry-once", "third", "first"):
            execute_operation(name)
        print("Local experiment operation IDs persisted; consumer not started.")
        return 0

    app = QApplication([])
    BRIDGE = Bridge()

    class Monitor(QObject):
        def __init__(self):
            super().__init__()
            self.deliveries = []
            self.heartbeat_count = 0
            self.timed_out = False
            self.started = time.monotonic()

        @Slot(str)
        def record(self, operation_id):
            self.deliveries.append((operation_id, threading.get_ident() == MAIN_THREAD))

        @Slot()
        def poll(self):
            self.heartbeat_count += 1
            with db() as conn:
                succeeded = conn.execute("SELECT count(*) FROM operations WHERE state='SUCCEEDED'").fetchone()[0]
            if succeeded == 3 and QUEUE.pending_count() == 0 and ACTIVE == 0 and len(self.deliveries) == 3:
                app.quit()
            elif time.monotonic() - self.started > 15:
                self.timed_out = True
                app.quit()

    monitor = Monitor()
    BRIDGE.completed.connect(monitor.record, Qt.ConnectionType.QueuedConnection)
    timer = QTimer()
    timer.timeout.connect(monitor.poll)
    timer.start(25)
    # Supported nonblocking embedding API is called on the process main thread,
    # where Huey registers signal handlers; Qt then owns the event loop.
    consumer = QUEUE.create_consumer(workers=1, worker_type="thread", periodic=False,
                                     initial_delay=0.02, max_delay=0.1,
                                     scheduler_interval=1, shutdown_timeout=5)
    consumer.start()
    exit_code = app.exec()
    stop_start = time.monotonic()
    consumer.stop(graceful=True)
    stop_seconds = time.monotonic() - stop_start
    with db() as conn:
        rows = conn.execute("SELECT id,state,attempts FROM operations ORDER BY id").fetchall()
    assets = Path(__file__).resolve().parent / "spike_assets"
    template = (assets / "query.xml").read_text(encoding="utf-8")
    icon = QIcon(str(assets / "icon.svg"))
    icon_ok = not icon.pixmap(24, 24).isNull()
    attempts = {row[0]: row[2] for row in rows}
    checks = {
        "three_operations_succeeded": len(rows) == 3 and all(row[1] == "SUCCEEDED" for row in rows),
        "single_worker_serialized": MAX_ACTIVE == 1 and len(WORKER_THREADS) == 1,
        "worker_off_main_thread": MAIN_THREAD not in WORKER_THREADS,
        "queued_signals_on_main_thread": len(monitor.deliveries) == 3 and all(row[1] for row in monitor.deliveries),
        "duplicate_operation_no_extra_effect": attempts.get("first") == 1,
        "retry_once": attempts.get("retry-once") == 2,
        "qt_heartbeat": monitor.heartbeat_count > 5,
        "clean_event_loop_exit": exit_code == 0 and not monitor.timed_out,
        "bounded_graceful_stop": stop_seconds < 6,
        "template_loaded": "<TALLYREQUEST>Export</TALLYREQUEST>" in template,
        "icon_rendered": icon_ok,
    }
    result = {"utc": datetime.now(timezone.utc).isoformat(), "frozen": bool(getattr(sys, "frozen", False)),
              "python": sys.version.split()[0], "pyside6": version("PySide6"),
              "huey": version("huey"), "checks": checks, "operations": rows,
              "qt_heartbeats": monitor.heartbeat_count, "stop_seconds": round(stop_seconds, 3),
              "network_access": False}
    (RUNTIME / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
