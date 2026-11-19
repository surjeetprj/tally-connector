"""Dispatch only; all network, database and queue work lives outside the UI."""
from PySide6.QtCore import QObject, Signal, Slot, Qt
import time


class Controller(QObject):
    result = Signal(object)
    progress = Signal(str)

    def __init__(self, runtime, bridge):
        super().__init__()
        self.runtime = runtime
        self.generation = time.time_ns()
        self.pending = {}
        self.binding = None
        bridge.event.connect(self.receive, Qt.ConnectionType.QueuedConnection)

    def submit(self, kind, **values):
        if kind in {"VERIFY", "RESTORE"}:
            self.generation += 1
            self.binding = None
            self.pending.clear()
        elif kind == "BIND":
            self.binding = None
        if kind in {"LOAD", "LINK", "SAVED", "ACTIVITY", "ACTIVITY_DETAIL", "PARTY_CHANGES"} or kind.startswith(("EXP_", "TRANSFER_", "BATCH_", "POLICY_", "UPDATE_")):
            values["binding"] = self.binding
        identity = self.runtime.submit(kind, self.generation, **values)
        self.pending[kind] = identity
        return identity

    @Slot(object)
    def receive(self, event):
        if event.kind == "BATCH_STEP" and event.generation == self.generation and self.binding:
            if not event.final:
                self.progress.emit(str(event.result))
            elif event.error or (event.result is not None and event.result.binding == self.binding):
                self.result.emit(event)
            return
        if event.generation != self.generation or self.pending.get(event.kind) != event.request_id:
            return
        if not event.final:
            self.progress.emit(str(event.result))
            return
        self.pending.pop(event.kind, None)
        if event.kind in {"BIND", "RESTORE"} and event.error is None and hasattr(event.result, "binding"):
            self.binding = event.result.binding
        self.result.emit(event)
