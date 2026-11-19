"""Compare current linked parties with each side's separately confirmed observation."""
from datetime import datetime, timedelta, timezone

from innoforia_tally_connector.domain.errors import ContextMismatch, ReadError
from innoforia_tally_connector.domain.masters import PartyContent, Side
from innoforia_tally_connector.domain.batches import CONTACT_FIELDS
from innoforia_tally_connector.domain.party_transfer import PartyDraft, field_availability
from innoforia_tally_connector.domain.party_changes import FieldValue, PartyFieldChange, LinkedPartyChanges, PARTY_UPDATE_FIELDS, GST_UPDATE_FIELDS


def field_value(observation, field):
    availability = field_availability(observation, field)
    return FieldValue(availability=availability,
        value=getattr(observation.content, field) if availability in {"present", "empty", "null"} else None)


def compare_changes(link, bahi, tally, policy, validation_errors=None, state_acknowledgement=None, reverse=False):
    blockers = []
    for current, saved in ((bahi, link.bahi), (tally, link.tally)):
        if current.binding != link.binding or current.side != saved.side or current.identity != saved.identity:
            raise ContextMismatch("Change review identity/context changed; no name fallback is allowed")
        if current.party_type != saved.party_type or current.classification_evidence != saved.classification_evidence:
            blockers.append(f"{current.side}: classification changed since linking")
        if current.content.name != saved.content.name:
            blockers.append(f"{current.side}: name changed; rename review is outside this slice")
        if current.is_active is False or current.is_system is True:
            blockers.append(f"{current.side}: inactive or system party")
    if bahi.is_active is not True:
        blockers.append("Bahi active eligibility is unavailable or inactive")
    if policy is None:
        blockers.append("Save an operator and field policy before preparing updates")
    elif policy.binding != link.binding:
        raise ContextMismatch("Policy belongs to a different binding")
    fields = []
    saved_source, source, saved_target, target = (link.tally, tally, link.bahi, bahi) if reverse else (link.bahi, bahi, link.tally, tally)
    for field in PartyContent.model_fields:
        a, b, c, d = (field_value(obs, field) for obs in (saved_source, source, saved_target, target))
        baseline = state_acknowledgement.field_baselines.get(field) if state_acknowledgement else None
        if baseline:
            a, c = baseline.source, baseline.destination
        elif field == "state" and state_acknowledgement and not state_acknowledgement.field_baselines:
            a, c = (field_value(obs, field) for obs in ((state_acknowledgement.tally, state_acknowledgement.bahi) if reverse else (state_acknowledgement.bahi, state_acknowledgement.tally)))
        source_changed, target_changed = a != b, c != d
        enabled = policy is not None and (field in (policy.to_bahi if reverse else policy.to_tally) or field == 'pan' or field in GST_UPDATE_FIELDS)
        missing = b.availability == 'present' and d.availability in {'empty','null','absent'} and c.availability in {'empty','null','absent','unavailable'}
        if field not in PARTY_UPDATE_FIELDS:
            status, reason = "Out of scope", "Rename is not enabled"
        elif field in (validation_errors or {}):
            status, reason = "Invalid", validation_errors[field]
        elif missing and target_changed and c.availability != 'unavailable' and not blockers and enabled:
            status, reason = 'Fill missing destination', 'Destination was blank and is still blank; only its representation changed. Select explicitly and approve filling it.'
        elif missing and not source_changed and not blockers and enabled:
            status, reason = 'Fill missing destination', 'Destination is blank. Select explicitly and approve filling this pre-existing difference.'
        elif missing and ('unavailable' in {a.availability,c.availability}) and not blockers and enabled:
            status, reason = 'Fill missing destination', 'A historical value was unavailable; current destination is blank. Explicit approval is required.'
        elif field in GST_UPDATE_FIELDS and b.availability == d.availability == 'present' and b == d:
            status, reason = 'Already matches', 'Current GST value matches exactly; it may accompany the explicitly selected paired tax update.'
        elif "unavailable" in {a.availability, b.availability, c.availability, d.availability}:
            status, reason = "Unavailable", "A current or saved value is unavailable; absence must not be inferred"
        elif b == d:
            status, reason = "Already matches", "Current values match exactly; no update proposed"
        elif source_changed and target_changed:
            status, reason = "Conflict", "Both sides changed since their saved observations; preserve destination edits"
        elif target_changed:
            status, reason = ("Bahi changed" if reverse else "Tally changed"), "Destination changed since the saved observation; no overwrite proposed"
        elif not source_changed:
            status, reason = "Pre-existing difference", "These values already differed when linked; the link is not a sync baseline"
        elif blockers:
            status, reason = "Blocked", "; ".join(blockers)
        elif not enabled:
            status, reason = "Excluded by policy", f"Field disabled by saved policy v{policy.version}"
        elif b.availability != "present":
            status, reason = "Clearing needs review", "Null, empty or absent values are not permission to clear destination data"
        else:
            status, reason = ("Tally changed" if reverse else "Bahi changed"), "Exact source value differs; destination is unchanged since the saved observation"
        fields.append(PartyFieldChange(field=field, saved_bahi=c if reverse else a, current_bahi=d if reverse else b, saved_tally=a if reverse else c, current_tally=b if reverse else d,
            status=status, reason=reason))
    return LinkedPartyChanges(link=link, bahi=bahi, tally=tally, fields=tuple(fields),
        blockers=tuple(dict.fromkeys(blockers)), policy_version=policy.version if policy else None,
        state_acknowledgement=state_acknowledgement, direction='TALLY_TO_BAHI' if reverse else 'BAHI_TO_TALLY')


class LinkedPartyReviewWorkflow:
    def __init__(self, readers, verify, links, policy, destination, state_acknowledgement=lambda _link: None, *, reverse=False):
        self.readers, self.verify, self.links, self.policy, self.destination = readers, verify, links, policy, destination
        self.state_acknowledgement = state_acknowledgement
        self.reverse = reverse

    def review(self, binding, classification, identity):
        if not identity or not identity.strip():
            raise ReadError("Select one linked source party")
        snapshot = self.verify()
        if snapshot.business_id != binding.business_id or snapshot.company_guid != binding.company_guid:
            raise ContextMismatch("Verified connection changed; review Settings")
        link = self.links.find(binding, Side.TALLY if self.reverse else Side.BAHI, identity)
        if link is None:
            raise ReadError("This source party has no confirmed link; use party transfer/link review first")
        bahi, tally = self.readers(classification)
        source, target = bahi.detail(binding, link.bahi.identity), tally.detail(binding, link.tally.identity)
        for current, saved in ((source, link.bahi), (target, link.tally)):
            if current.binding != binding or current.side != saved.side or current.identity != saved.identity:
                raise ContextMismatch("Change review identity/context changed; no name fallback is allowed")
        now = datetime.now(timezone.utc)
        if any(not timedelta(0) <= now - row.observed_at <= timedelta(minutes=5) for row in (source, target)):
            raise ReadError("Change review received stale observations; refresh")
        origin = target if self.reverse else source
        values = {f: getattr(origin.content, f) for f in (PARTY_UPDATE_FIELDS if self.reverse else CONTACT_FIELDS) if field_availability(origin, f) == "present"}
        draft = PartyDraft(name=origin.content.name, party_type=origin.party_type, **values)
        errors = self.destination(classification).validate(draft)
        return compare_changes(link, source, target, self.policy(binding), errors, self.state_acknowledgement(link), reverse=self.reverse)
