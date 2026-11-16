"""Supplied party handbook validation; no silent rewriting of business content."""
import re
from innoforia_tally_connector.domain.party_transfer import PartyDraft

LIMITS = {"name": 128, "email": 255, "phone": 16, "address": 255, "state": 64,
          "country": 64, "pincode": 6, "gstin": 16, "pan": 10, "gst_reg_type": 32}


def validate(draft):
    errors = {}
    for field, limit in LIMITS.items():
        if field not in draft.model_fields_set:
            continue
        value = getattr(draft, field)
        if value is None:
            if field in {"name", "country", "gst_reg_type"}:
                errors[field] = "Destination cannot accept null"
            continue
        if len(value) > limit:
            errors[field] = f"Destination limit is {limit} characters; no truncation"
        if field == "name" and not value.strip():
            errors[field] = "A nonblank name is required"
        patterns = {"email": r"[^\s@]+@[^\s@]+\.[^\s@]+", "pincode": r"[0-9]{6}",
                    "pan": r"[A-Za-z]{5}[0-9]{4}[A-Za-z]", "gstin": r"[0-9]{2}[A-Za-z]{5}[0-9]{4}[A-Za-z][0-9A-Za-z]Z[0-9A-Za-z]"}
        if value and field in patterns and not re.fullmatch(patterns[field], value, flags=re.IGNORECASE):
            errors[field] = "Value does not satisfy the destination format"
    # A Bahi registration label is free text. No country/code or registration-type translation is invented.
    if draft.gstin and not draft.gst_reg_type:
        errors["gstin"] = "GSTIN requires an observed registration type; exclude GSTIN too if registration is unavailable"
    return errors


def payload(draft):
    if not isinstance(draft, PartyDraft) or validate(draft):
        raise ValueError("Invalid approved party payload")
    result = draft.model_dump(exclude_unset=True)
    result["account_name"] = result.pop("name")
    return result
