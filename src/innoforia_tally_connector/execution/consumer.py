"""One embedded Huey worker; metadata/outbox capture stays off the GUI thread."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event as StopEvent, Lock, Thread
from uuid import uuid4

from huey import SqliteHuey

from innoforia_tally_connector.application.sync.execution import Runner
from innoforia_tally_connector.domain.commands import Command, Event


class Runtime:
    def __init__(self, directory, store, links, handler, emit):
        self.store, self.links, self.emit = store, links, emit
        self.stopping = StopEvent()
        self.closed = StopEvent()
        self.started = False
        self.actor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="connector-dispatch")
        self.guard, self.inflight = Lock(), {}
        self.commands, self.aliases = {}, {}
        self.queue = SqliteHuey("connector-discovery", filename=str(directory / "huey_queue.db"),
                               immediate=False, results=False)
        self.runner = Runner(store, handler, self._emit, self.stopping.is_set)

        @self.queue.task(name="connector.execute_operation", retries=0)
        def execute_operation(operation_id):
            try:
                self.runner.execute(operation_id)
            except Exception:
                try:
                    self.store.finish(operation_id, "Local storage failure; renewed review or read required")
                except Exception:
                    pass  # Leave durable evidence for startup recovery.
                command = self.commands.get(operation_id)
                if command:
                    if command.kind == "BATCH_STEP":
                        try:
                            self.store.pause_batch(command)
                        except Exception:
                            pass  # Durable attempt/lease survives until restart recovery.
                    message = ("Local storage failed. Restart and inspect the durable experiment; do not create again."
                               if command.kind in {"EXP_CREATE", "EXP_RECONCILE", "TRANSFER_CREATE", "TRANSFER_RECONCILE", "BATCH_APPROVE", "BATCH_STEP", "UPDATE_APPLY", "UPDATE_RECONCILE"} else
                               "Local storage failed. Restore storage access and restart; inspect saved links before confirming again")
                    self._emit(Event(command.id, command.generation, command.kind,
                        error=message))
            finally:
                if not self.stopping.is_set():
                    self.actor.submit(self._dispatch)
        self.task = execute_operation

        @self.queue.on_shutdown()
        def close_worker_storage():
            self.queue.storage.close()
        self.consumer = self.queue.create_consumer(workers=1, worker_type="thread", periodic=False,
            initial_delay=0.02, max_delay=0.1, scheduler_interval=1, shutdown_timeout=45)
        # Constructor runs on the startup thread, before any queue consumer.
        self._recover()

    def _emit(self, event):
        from dataclasses import replace
        original_id = event.request_id
        command = self.commands.get(original_id)
        alias = self.aliases.pop(original_id, None) if event.final else self.aliases.get(original_id)
        if alias:
            event = replace(event, request_id=alias)
        if event.final:
            self.commands.pop(original_id, None)
            with self.guard:
                record_id = (command.party_identity if command.kind == "PARTY_CHANGES" else command.experiment_id) if command else None
                key = self._key(event.kind, event.generation, record_id)
                if self.inflight.get(key) == event.request_id:
                    self.inflight.pop(key)
        self.emit(event)

    @staticmethod
    def _key(kind, generation, record_id=None):
        return (generation, kind, record_id) if kind in {"ACTIVITY_DETAIL", "PARTY_CHANGES"} else (generation, kind)

    def start(self):
        # Consumer.start registers signals: call on the process main thread.
        if self.stopping.is_set():
            return
        self.consumer.start()
        self.started = True

    def _recover(self):
        self.store.recover(self.links)
        self._dispatch()

    def _dispatch(self):
        for identity in self.store.pending():
            if self.stopping.is_set():
                break
            if identity not in self.commands:
                command = self.store.command(identity)
                if command:
                    self.commands[identity] = command
            self.task(identity)
            self.store.dispatched(identity)

    def submit(self, kind, generation, **values):
        if self.stopping.is_set():
            raise ValueError("Connector is shutting down")
        with self.guard:
            key = self._key(kind, generation, values.get("party_identity") if kind == "PARTY_CHANGES" else values.get("experiment_id"))
            if key in self.inflight:
                return self.inflight[key]
            command = Command(id=str(uuid4()), kind=kind, generation=generation, **values)
            self.inflight[key] = command.id
        self.actor.submit(self._capture, command)
        return command.id

    def _capture(self, command):
        try:
            actual = self.store.capture(command)
            self.commands[actual] = command
            if actual != command.id:
                self.aliases[actual] = command.id
            self._dispatch()
        except Exception:
            # Capture failures still need the targeted record ID to release
            # ACTIVITY_DETAIL's per-record in-flight key.
            self.commands[command.id] = command
            self._emit(Event(command.id, command.generation, command.kind,
                             error="Unable to persist or dispatch the request; retry after checking local storage"))

    def shutdown(self, cleanup):
        self.stopping.set()

        def finish():
            try:
                self.actor.shutdown(wait=True)
                if self.started:
                    self.consumer.stop(graceful=True)
                cleanup()
            finally:
                self.closed.set()
        Thread(target=finish, name="connector-shutdown", daemon=False).start()
