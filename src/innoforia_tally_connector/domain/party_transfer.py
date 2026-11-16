"""Destination payloads and recorded field decisions; no transport dependencies."""
import hashlib
import json
from typing import Literal

from innoforia_tally_connector.domain.masters import PartyContent, PartyObservation, PartyType, Value, ConfirmedPartyLink

OPTIONAL_FIELDS = tuple(name for name in PartyContent.model_fields if name != "name")
NEW_FIELDS = ("country", "pan", "gst_reg_type")


def field_availability(source, field):
    if field in source.unavailable_fields or (source.content_schema < 2 and field in NEW_FIELDS
                                             and field not in source.content.model_fields_set):
        return "unavailable"
    if field not in source.content.model_fields_set:
        return "absent"
    value = getattr(source.content, field)
    return "null" if value is None else "empty" if value == "" else "present"


class PartyDraft(PartyContent):
    party_type: PartyType


class FieldDecision(Value):
    field: str
    status: Literal["included", "absent", "excluded", "unavailable", "invalid"]
    reason: str = ""


def source_fingerprint(source: PartyObservation):
    return hashlib.sha256(json.dumps(source.comparison(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_key(binding, side, identity):
    return json.dumps([binding.id, binding.generation, str(side), identity], separators=(",", ":"))


class TransferReview(Value):
    record: ConfirmedPartyLink | None = None
    source: PartyObservation | None = None
    candidates: tuple[PartyObservation, ...] = ()
    message: str = ""
