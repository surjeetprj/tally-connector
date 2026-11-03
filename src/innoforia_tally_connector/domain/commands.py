"""Durable read/local-link commands and transient queued events."""
from dataclasses import dataclass
from typing import Literal
from pydantic import Field

from innoforia_tally_connector.domain.masters import Binding, Classification, PartyObservation, Value
from innoforia_tally_connector.domain.experiments import Direction


class Command(Value):
    id: str
    kind: Literal["VERIFY", "BIND", "LOAD", "LINK", "SAVED", "EXP_PREPARE", "EXP_CREATE", "EXP_STATUS", "EXP_RECONCILE"]
    generation: int
    binding: Binding | None = None
    classification: Classification | None = None
    bahi: PartyObservation | None = None
    tally: PartyObservation | None = None
    reviewer: str | None = None
    offset: int = Field(default=0, ge=0)
    direction: Direction | None = None
    experiment_id: str | None = None
    approval_digest: str | None = None


@dataclass(frozen=True)
class Event:
    request_id: str
    generation: int
    kind: str
    result: object = None
    error: str | None = None
    final: bool = True
