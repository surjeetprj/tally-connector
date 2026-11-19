"""Approved batch snapshots; business values never come from UI edits."""
import hashlib
from pydantic import AwareDatetime, Field, model_validator
from innoforia_tally_connector.domain.masters import Value, Binding, PartyObservation
from innoforia_tally_connector.domain.experiments import Direction, ExperimentPreview, ExperimentResult

CONTACT_FIELDS = ("email", "phone", "address", "country", "state", "pincode")
BAHI_FIELDS = (*CONTACT_FIELDS, 'gstin', 'pan', 'gst_reg_type')


class TransferPolicy(Value):
    binding: Binding
    version: int = Field(default=1, ge=1)
    operator: str
    to_bahi: tuple[str, ...] = BAHI_FIELDS
    to_tally: tuple[str, ...] = CONTACT_FIELDS

    @model_validator(mode="after")
    def valid(self):
        if not self.operator.strip():
            raise ValueError("Enter the operator name")
        if any(len(set(fields)) != len(fields) or set(fields) - set(allowed)
               for fields,allowed in ((self.to_bahi,BAHI_FIELDS),(self.to_tally,BAHI_FIELDS))):
            raise ValueError("Only destination-supported fields can be enabled")
        return self


class BatchItem(Value):
    source: PartyObservation
    status: str
    message: str = ""
    preview: ExperimentPreview | None = None
    result: ExperimentResult | None = None
    candidates: tuple[PartyObservation, ...] = ()


class TransferBatch(Value):
    id: str
    binding: Binding
    generation: int
    direction: Direction
    policy: TransferPolicy
    created_at: AwareDatetime
    items: tuple[BatchItem, ...]
    state: str = "PENDING"
    approved_ids: tuple[str, ...] = ()
    normal_confirmed: bool = False
    message: str = ""

    @property
    def digest(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class BatchApproval(Value):
    batch_id: str
    digest: str
    ready_ids: tuple[str, ...]
    normal_confirmed: bool = False


class BatchPage(Value):
    records: tuple[TransferBatch, ...]
    offset: int = 0
    has_more: bool = False
