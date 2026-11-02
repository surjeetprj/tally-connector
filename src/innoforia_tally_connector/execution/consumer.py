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
                    self._emit(Event(command.id, command.generation, command.kind,
                        error="Local storage failed. Restore storage access and restart; inspect saved links before confirming again"))
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
        alias = self.aliases.pop(original_id, None) if event.final else self.aliases.get(original_id)
        if alias:
            event = replace(event, request_id=alias)
        if event.final:
            self.commands.pop(original_id, None)
            with self.guard:
                key = (event.generation, event.kind)
                if self.inflight.get(key) == event.request_id:
                    self.inflight.pop(key)
        self.emit(event)

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
            self.task(identity)
            self.store.dispatched(identity)

    def submit(self, kind, generation, **values):
        if self.stopping.is_set():
            raise ValueError("Connector is shutting down")
        with self.guard:
            key = (generation, kind)
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
