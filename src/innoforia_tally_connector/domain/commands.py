"""Durable read/local-link commands and transient queued events."""
from dataclasses import dataclass
from typing import Literal
from pydantic import Field

from innoforia_tally_connector.domain.masters import Binding, Classification, PartyObservation, Value


class Command(Value):
    id: str
    kind: Literal["VERIFY", "BIND", "LOAD", "LINK", "SAVED"]
    generation: int
    binding: Binding | None = None
    classification: Classification | None = None
    bahi: PartyObservation | None = None
    tally: PartyObservation | None = None
    reviewer: str | None = None
    offset: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class Event:
    request_id: str
    generation: int
    kind: str
    result: object = None
    error: str | None = None
    final: bool = True
