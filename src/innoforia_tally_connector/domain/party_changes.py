"""Read-only comparison evidence; an identity link grants no update permission."""
from typing import Literal
from pydantic import model_validator
from innoforia_tally_connector.domain.masters import Value, ConfirmedPartyLink, PartyObservation, Side

GST_UPDATE_FIELDS = ('gstin', 'gst_reg_type')
PARTY_UPDATE_FIELDS = ('email', 'phone', 'address', 'state', 'country', 'pincode', 'pan', *GST_UPDATE_FIELDS)


class FieldValue(Value):
    availability: Literal["present", "empty", "null", "absent", "unavailable"]
    value: str | None = None


class PartyFieldChange(Value):
    field: str
    saved_bahi: FieldValue
    current_bahi: FieldValue
    saved_tally: FieldValue
    current_tally: FieldValue
    status: Literal["Already matches", "Bahi changed", "Tally changed", "Conflict",
                    "Pre-existing difference", "Unavailable", "Out of scope", "Excluded by policy",
                    "Clearing needs review", "Invalid", "Blocked", "Fill missing destination"]
    reason: str


class AcknowledgedField(Value):
    operation_id: str
    source: FieldValue
    destination: FieldValue


class StateAcknowledgement(Value):
    """Last verified State only; never replaces the original link observations."""
    operation_id: str
    link_id: str
    bahi: PartyObservation
    tally: PartyObservation
    field_baselines: dict[str, AcknowledgedField] = {}

    @model_validator(mode="after")
    def verified_state(self):
        if (not self.operation_id or not self.link_id or self.bahi.side != Side.BAHI or self.tally.side != Side.TALLY
            or self.bahi.binding != self.tally.binding or self.bahi.party_type != self.tally.party_type
            or (not self.field_baselines and (not self.bahi.content.state or self.bahi.content.state != self.tally.content.state
                or "state" in self.bahi.unavailable_fields or "state" in self.tally.unavailable_fields))
            or any(field not in PARTY_UPDATE_FIELDS or baseline.source.availability != 'present'
                or baseline.source != baseline.destination for field,baseline in self.field_baselines.items())):
            raise ValueError("State acknowledgement requires matching verified identities and State values")
        return self


class LinkedPartyChanges(Value):
    link: ConfirmedPartyLink
    bahi: PartyObservation
    tally: PartyObservation
    fields: tuple[PartyFieldChange, ...]
    blockers: tuple[str, ...] = ()
    policy_version: int | None = None
    state_acknowledgement: StateAcknowledgement | None = None
    direction: Literal['BAHI_TO_TALLY', 'TALLY_TO_BAHI'] = 'BAHI_TO_TALLY'

    @model_validator(mode="after")
    def same_identities(self):
        for current, saved, side in ((self.bahi, self.link.bahi, Side.BAHI), (self.tally, self.link.tally, Side.TALLY)):
            if current.binding != self.link.binding or current.side != side or current.identity != saved.identity:
                raise ValueError("Change review is outside the confirmed identities")
        ack = self.state_acknowledgement
        if ack and (ack.link_id != self.link.id or any(
            saved.binding != self.link.binding or saved.side != current.side or saved.identity != current.identity
            for saved, current in ((ack.bahi, self.bahi), (ack.tally, self.tally)))):
            raise ValueError("State acknowledgement is outside the confirmed identities")
        return self
