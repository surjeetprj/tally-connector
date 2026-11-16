"""Build an exact destination payload; omission always has a recorded decision."""
from innoforia_tally_connector.domain.party_transfer import OPTIONAL_FIELDS, FieldDecision, PartyDraft, field_availability


def select_fields(source, destination, exclusions):
    if set(exclusions) - set(OPTIONAL_FIELDS) or any(not reason.strip() for reason in exclusions.values()):
        raise ValueError("Only optional fields may be excluded, with a reason for each")
    values = {"name": source.content.name, "party_type": source.party_type}
    decisions = [FieldDecision(field="name", status="included")]
    for field in OPTIONAL_FIELDS:
        unavailable = field_availability(source, field) == "unavailable"
        if field in exclusions:
            decisions.append(FieldDecision(field=field, status="excluded", reason=exclusions[field]))
        elif unavailable:
            decisions.append(FieldDecision(field=field, status="unavailable", reason="Source representation unavailable; explicit exclusion required"))
        elif field not in source.content.model_fields_set:
            decisions.append(FieldDecision(field=field, status="absent", reason="Source field absent; destination default will be observed"))
        else:
            values[field] = getattr(source.content, field)
            decisions.append(FieldDecision(field=field, status="included"))
    draft = PartyDraft(**values)
    problems = destination.validate(draft)
    decisions = [FieldDecision(field=d.field, status="invalid", reason=problems[d.field])
                 if d.field in problems else d for d in decisions]
    return draft, tuple(decisions)
