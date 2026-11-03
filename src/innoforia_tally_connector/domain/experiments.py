"""One synthetic destination-only supplier, never a fabricated source mapping."""
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
import re
from uuid import uuid4

from pydantic import AwareDatetime, model_validator

from innoforia_tally_connector.domain.masters import Binding, PartyObservation, Value


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


class ExperimentPreview(Value):
    id: str
    binding: Binding
    generation: int
    direction: Direction
    party: TestSupplier
    preflight: Preflight
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True,
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
