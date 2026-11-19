"""Journal snapshots for legacy synthetic experiments and real party transfers."""
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
import re
from uuid import uuid4
from typing import Literal

from pydantic import AwareDatetime, model_validator

from innoforia_tally_connector.domain.masters import Binding, PartyObservation, Side, Value, ConfirmedPartyLink, PartyType
from innoforia_tally_connector.domain.party_transfer import FieldDecision, PartyDraft


class Direction(StrEnum):
    TO_TALLY = "BAHI_TO_TALLY"
    TO_BAHI = "TALLY_TO_BAHI"


class OperationState(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    APPLYING = "APPLYING"
    VERIFYING = "VERIFYING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    RECONCILING = "RECONCILING"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TestSupplier(Value):
    name: str
    email: str

    @model_validator(mode="after")
    def namespace(self):
        match = re.fullmatch(r"MST004-SUP-(\d{8})-([0-9a-f]{8})", self.name)
        if not match or self.email != f"mst004-{match[2]}@example.invalid":
            raise ValueError("Only the generated MST-004 supplier namespace is enabled")
        datetime.strptime(match[1], "%Y%m%d")
        return self


class Preflight(Value):
    group_context: str
    destination: str
    baseline_guids: tuple[str, ...] = ()


class StateUpdateEvidence(Value):
    link: ConfirmedPartyLink
    before: PartyObservation
    native_before: str
    native_expected: str
    policy_version: int
    acknowledged_operation_id: str | None = None


class ExperimentPreview(Value):
    id: str
    binding: Binding
    generation: int
    direction: Direction
    party: TestSupplier | PartyDraft
    preflight: Preflight
    created_at: AwareDatetime
    expires_at: AwareDatetime
    kind: Literal["EXPERIMENT", "TRANSFER", "UPDATE"] = "EXPERIMENT"
    source: PartyObservation | None = None
    decisions: tuple[FieldDecision, ...] = ()
    source_confirmation_required: bool = False
    update: StateUpdateEvidence | None = None

    @model_validator(mode="after")
    def consistent_intent(self):
        if self.kind in {"TRANSFER", "UPDATE"}:
            expected_side = Side.BAHI if self.direction == Direction.TO_TALLY else Side.TALLY
            if (not isinstance(self.party, PartyDraft) or self.source is None or self.source.binding != self.binding
                or self.source.side != expected_side or self.source.party_type != self.party.party_type
                or self.source.content.name != self.party.name
                or self.source_confirmation_required != (self.source.is_system is None)):
                raise ValueError("Transfer identity, classification, name and direction must match the selected source")
            if self.kind == "UPDATE":
                if (self.update is None or self.direction != Direction.TO_TALLY or self.party.party_type != PartyType.SUPPLIER
                    or self.party.model_fields_set != {"name", "party_type", "state"} or not self.party.state or not self.party.state.strip()
                    or self.update.link.binding != self.binding or self.update.link.bahi.identity != self.source.identity
                    or self.update.before.binding != self.binding or self.update.before.side != Side.TALLY
                    or self.update.before.party_type != self.party.party_type
                    or self.update.before.identity != self.update.link.tally.identity):
                    raise ValueError("Only one linked supplier state update is allowed")
        elif self.source is not None or not isinstance(self.party, TestSupplier):
            raise ValueError("Legacy experiment cannot represent a real source transfer")
        if self.kind != "UPDATE" and self.update is not None:
            raise ValueError("Update evidence cannot be attached to creation")
        return self

    @property
    def digest(self):
        data = self.model_dump(mode="json")
        if self.update is None: data.pop("update")  # Preserve legacy approval hashes.
        elif self.update.acknowledged_operation_id is None:
            data["update"].pop("acknowledged_operation_id")  # Preserve controlled-trial hashes.
        return hashlib.sha256(json.dumps(data, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()

    def require_current(self, binding, generation, digest, now):
        if binding != self.binding or generation != self.generation or digest != self.digest:
            raise ValueError("Experiment preview changed; prepare and review it again")
        if not self.created_at <= now <= self.expires_at:
            raise ValueError("Experiment preview expired; prepare and review it again")


class TargetIdentity(Value):
    kind: str
    identity: str | None = None
    baseline_guids: tuple[str, ...] = ()


class ExperimentResult(Value):
    preview: ExperimentPreview
    state: str
    attempted: bool
    target: TargetIdentity | None = None
    comparisons: dict[str, bool] = {}
    message: str = ""
    reviewer: str | None = None
    observation: PartyObservation | None = None
    source_normal_party_confirmed: bool = False
    native_after: str | None = None


class ActivityPage(Value):
    records: tuple[ExperimentResult, ...] = ()
    offset: int = 0
    has_more: bool = False


def new_preview(binding, generation, direction, party, preflight, now=None):
    now = now or datetime.now(timezone.utc)
    return ExperimentPreview(id=str(uuid4()), binding=binding, generation=generation,
        direction=direction, party=party, preflight=preflight, created_at=now, expires_at=now + timedelta(minutes=5))


def synthetic_supplier():
    token = uuid4().hex[:8]
    day = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y%m%d")
    return TestSupplier(name=f"MST004-SUP-{day}-{token}", email=f"mst004-{token}@example.invalid")


class WriteRejected(ValueError):
    """A documented explicit refusal before application; still never auto-retried."""


class UncertainWrite(ValueError):
    def __init__(self, message, target=None):
        super().__init__(message)
        self.target = target
