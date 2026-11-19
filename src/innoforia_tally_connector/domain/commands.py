"""Durable read/local-link commands and transient queued events."""
from dataclasses import dataclass
from typing import Literal
from pydantic import Field

from innoforia_tally_connector.domain.masters import Binding, Classification, PartyObservation, Value
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.batches import TransferPolicy, BatchApproval


class Command(Value):
    id: str
    kind: Literal["VERIFY", "BIND", "LOAD", "LINK", "SAVED", "EXP_PREPARE", "EXP_CREATE", "EXP_STATUS", "EXP_RECONCILE",
                  "TRANSFER_PREPARE", "TRANSFER_CREATE", "TRANSFER_RECONCILE", "ACTIVITY", "ACTIVITY_DETAIL", "TRANSFER_CANCEL",
                  "RESTORE", "POLICY_GET", "POLICY_SAVE", "BATCH_PREPARE", "BATCH_APPROVE", "BATCH_STEP", "BATCH_GET", "BATCH_LIST", "BATCH_CANCEL", "BATCH_RECOVER", "PARTY_CHANGES",
                  "UPDATE_PREPARE", "UPDATE_APPLY", "UPDATE_RECONCILE", "UPDATE_CANCEL", "UPDATE_STATUS", "UPDATE_CLOSE_FAILED"]
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
    source: PartyObservation | None = None
    exclusions: dict[str, str] = Field(default_factory=dict)
    status_filter: str | None = None
    type_filter: str | None = None
    source_normal_party_confirmed: bool = False
    sources: tuple[PartyObservation, ...] = Field(default=(), max_length=100)
    policy: TransferPolicy | None = None
    approval: BatchApproval | None = None
    batch_id: str | None = None
    party_identity: str | None = None
    mailing_effective_date: str | None = Field(default=None, pattern=r"^[0-9]{8}$")
    update_fields: tuple[str, ...] = ()
    accept_missing_fields: bool = False
    gst_effective_date: str | None = Field(default=None, pattern=r"^[0-9]{8}$")


@dataclass(frozen=True)
class Event:
    request_id: str
    generation: int
    kind: str
    result: object = None
    error: str | None = None
    final: bool = True
