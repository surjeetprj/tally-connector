"""Read observations and local identity links; no master mutation policy."""
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("*", mode="after")
    @classmethod
    def required_text_not_blank(cls, value, info):
        if isinstance(value, str) and cls.model_fields[info.field_name].is_required() and not value.strip():
            raise ValueError("Required text cannot be blank")
        return value


class Side(StrEnum):
    BAHI = "BAHI"
    TALLY = "TALLY"


class PartyType(StrEnum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"


class Binding(Value):
    id: str = Field(min_length=1)
    business_id: int = Field(gt=0)
    company_guid: str = Field(min_length=1)
    generation: int = Field(ge=1)


class PartyContent(Value):
    name: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    state: str | None = None
    pincode: str | None = None


class PartyObservation(Value):
    binding: Binding
    side: Side
    identity: str = Field(min_length=1)
    party_type: PartyType
    classification_evidence: str = Field(min_length=1)
    content: PartyContent
    version: str | None = None
    observed_at: AwareDatetime

    def comparison(self) -> dict:
        # Missing differs from explicit null; observation time is not content.
        return self.model_dump(mode="json", exclude={"observed_at"}, exclude_unset=True)


class PartyScan(Value):
    binding: Binding
    side: Side
    records: tuple[PartyObservation, ...]
    observed_at: AwareDatetime
    pages_read: tuple[int, ...]
    total_pages: int | None = Field(default=None, ge=0)
    failed_pages: tuple[int, ...] = ()
    stable_snapshot: bool = False

    @model_validator(mode="after")
    def consistent_scope(self):
        if any(r.binding != self.binding or r.side != self.side for r in self.records):
            raise ValueError("Record outside scan binding/side")
        if len({r.identity for r in self.records}) != len(self.records):
            raise ValueError("Repeated identity across scan pages; reload")
        for pages in (self.pages_read, self.failed_pages):
            if len(set(pages)) != len(pages) or any(p < 1 for p in pages):
                raise ValueError("Invalid page coverage")
        if set(self.pages_read) & set(self.failed_pages):
            raise ValueError("Page cannot be both successful and failed")
        if self.total_pages is not None and any(
            p > self.total_pages for p in (*self.pages_read, *self.failed_pages)
        ):
            raise ValueError("Page exceeds declared total")
        if self.records and not self.pages_read:
            raise ValueError("Records require successful page coverage")
        return self

    @property
    def coverage_complete(self) -> bool:
        return self.total_pages is not None and not self.failed_pages and (
            set(self.pages_read) == set(range(1, self.total_pages + 1))
        )

    @property
    def complete_baseline(self) -> bool:
        return self.coverage_complete and self.stable_snapshot


class ConfirmedPartyLink(Value):
    id: str = Field(min_length=1)
    binding: Binding
    bahi: PartyObservation
    tally: PartyObservation
    confirmed_by: str = Field(min_length=1)
    confirmed_at: AwareDatetime
    review_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_pair(self):
        if (self.bahi.binding != self.binding or self.tally.binding != self.binding
                or self.bahi.side != Side.BAHI or self.tally.side != Side.TALLY
                or self.bahi.party_type != self.tally.party_type):
            raise ValueError("Incompatible link identities or classification")
        return self


class LinkConflict(ValueError):
    """An identity is already linked; history must not be silently replaced."""
