"""Shared local command execution, with durable claims and safe result events."""
import logging

from pydantic import ValidationError

from innoforia_tally_connector.domain.commands import Event
from innoforia_tally_connector.domain.errors import ReadError


class Runner:
    def __init__(self, store, handler, emit, stopped=lambda: False):
        self.store, self.handler, self.emit, self.stopped = store, handler, emit, stopped

    def execute(self, identity):
        if self.stopped():
            return  # Still durable PENDING; startup recovery repairs dispatch.
        command = self.store.claim(identity)
        if command is None:
            return
        result, error = None, None
        try:
            result = self.handler(command)
        except ValidationError:
            error = "Read contract validation failed; refresh and inspect connection evidence"
        except (ReadError, ValueError) as failure:
            error = str(failure)
        except Exception as failure:
            logging.getLogger(__name__).error("Operation %s failed: %s", identity, type(failure).__name__)
            error = "Local discovery failed; inspect redacted diagnostics and retry a safe read"
        self.store.finish(identity, error)
        self.emit(Event(command.id, command.generation, command.kind, result, error))
