from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest

from innoforia_tally_connector.application.masters.changes import compare_changes, LinkedPartyReviewWorkflow
from innoforia_tally_connector.domain.batches import TransferPolicy
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.masters import PartyContent, ConfirmedPartyLink, Side, PartyType
from innoforia_tally_connector.domain.party_changes import StateAcknowledgement


@pytest.fixture
def linked(binding, observation):
    a = observation(identity="source", name="Linked party", is_active=True, is_system=False, content_schema=2,
        content=PartyContent(name="Linked party", email="old@example.invalid", state=None, phone="00123"))
    b = observation(Side.TALLY, "target", name="Linked party", is_system=False, content_schema=2,
        content=PartyContent(name="Linked party", email="old@example.invalid", phone="00123"))
    return ConfirmedPartyLink(id="confirmed", binding=binding, bahi=a, tally=b, confirmed_by="Reviewer",
        confirmed_at=datetime.now(timezone.utc), review_reference="explicit identity review")


def changed(row, **values):
    return row.model_copy(update={"content": row.content.model_copy(update=values)})


def fields(link, source=None, target=None, policy=None, **kwargs):
    review = compare_changes(link, source or link.bahi, target or link.tally,
        policy or TransferPolicy(binding=link.binding, operator="Reviewer"), **kwargs)
    return {f.field: f for f in review.fields}


def test_source_change_is_candidate_without_equating_saved_sides(linked):
    row = fields(linked, changed(linked.bahi, state="Delhi"))["state"]
    assert row.status == "Bahi changed"
    assert row.saved_bahi.availability == "null" and row.saved_tally.availability == "absent"
    assert row.current_bahi.value == "Delhi" and row.current_tally.availability == "absent"
    assert fields(linked)["state"].status == "Pre-existing difference"


def test_acknowledged_state_does_not_acknowledge_other_fields(linked):
    a = changed(linked.bahi, state='Delhi', email='intermediate@example.invalid')
    b = changed(linked.tally, state='Delhi', email='intermediate@example.invalid')
    ack = StateAcknowledgement(operation_id='verified-update', link_id=linked.id, bahi=a, tally=b)
    review = compare_changes(linked, changed(a, state='Karnataka', email='next@example.invalid'), b,
        TransferPolicy(binding=linked.binding, operator='Reviewer'), state_acknowledgement=ack)
    by_field = {f.field: f for f in review.fields}
    assert by_field['state'].status == 'Bahi changed'
    assert by_field['state'].saved_bahi.value == by_field['state'].saved_tally.value == 'Delhi'
    assert by_field['email'].status == 'Conflict'
    assert by_field['email'].saved_tally.value == 'old@example.invalid'
    with pytest.raises(ValueError, match='confirmed identities'):
        compare_changes(linked, a, b, TransferPolicy(binding=linked.binding, operator='Reviewer'),
            state_acknowledgement=ack.model_copy(update={'link_id': 'another-link'}))


@pytest.mark.parametrize("source,target,status", [
    ("new@example.invalid", "old@example.invalid", "Bahi changed"),
    ("old@example.invalid", "edited@example.invalid", "Tally changed"),
    ("new@example.invalid", "edited@example.invalid", "Conflict"),
    ("new@example.invalid", "new@example.invalid", "Already matches"),
    ("old@example.invalid", "old@example.invalid", "Already matches"),
])
def test_separate_side_history_and_conflicts(linked, source, target, status):
    row = fields(linked, changed(linked.bahi, email=source), changed(linked.tally, email=target))["email"]
    assert row.status == status


@pytest.mark.parametrize("value", [None, ""])
def test_clearing_is_not_an_update_instruction(linked, value):
    row = fields(linked, changed(linked.bahi, phone=value))["phone"]
    assert row.status == "Clearing needs review"
    assert row.current_bahi.availability == ("null" if value is None else "empty")
    assert row.current_tally.value == "00123"


def test_absent_and_unavailable_baseline_are_distinct(linked):
    source = changed(linked.bahi, country="India")
    legacy = linked.model_copy(update={"bahi": linked.bahi.model_copy(update={"content_schema": 1})})
    assert fields(linked, source)["country"].status == "Bahi changed"
    assert fields(legacy, source)["country"].status == "Unavailable"
    source = source.model_copy(update={"unavailable_fields": ("country",)})
    assert fields(linked, source)["country"].status == "Unavailable"


def test_policy_and_invalid_source_values_are_explained(linked):
    source = changed(linked.bahi, email="new@example.invalid")
    policy = TransferPolicy(binding=linked.binding, operator="Reviewer", to_tally=())
    assert fields(linked, source, policy=policy)["email"].status == "Excluded by policy"
    row = fields(linked, source, validation_errors={"email": "Unsupported value"})["email"]
    assert row.status == "Invalid" and row.reason == "Unsupported value"


def test_exact_unicode_whitespace_and_line_breaks_are_preserved(linked):
    value = " Exact – दिल्ली ₹\n\n  Last "
    row = fields(linked, changed(linked.bahi, address=value))["address"]
    assert row.status == "Bahi changed" and row.current_bahi.value == value
    assert fields(linked, changed(linked.bahi, phone="00123 "))["phone"].status == "Bahi changed"


@pytest.mark.parametrize("change", ["inactive", "system", "classification", "name", "unknown_active"])
def test_eligibility_and_identity_changes_block_candidates(linked, change):
    source = changed(linked.bahi, state="Delhi")
    if change == "inactive": source = source.model_copy(update={"is_active": False})
    if change == "unknown_active": source = source.model_copy(update={"is_active": None})
    if change == "system": source = source.model_copy(update={"is_system": True})
    if change == "classification": source = source.model_copy(update={"party_type": PartyType.CUSTOMER})
    if change == "name": source = changed(source, name="Renamed")
    assert fields(linked, source)["state"].status == "Blocked"


def test_tax_differences_never_become_update_candidates(linked):
    result = fields(linked, changed(linked.bahi, gstin="source", pan="source", gst_reg_type="Regular"))
    assert all(result[f].status == "Out of scope" for f in ("gstin", "pan", "gst_reg_type", "name"))


@pytest.mark.parametrize("change", ["identity", "side", "binding", "policy"])
def test_review_rejects_cross_context_snapshots(linked, change):
    source = changed(linked.bahi, state="Delhi")
    policy = TransferPolicy(binding=linked.binding, operator="Reviewer")
    if change == "identity": source = source.model_copy(update={"identity": "other"})
    if change == "side": source = source.model_copy(update={"side": Side.TALLY})
    if change == "binding": source = source.model_copy(update={"binding": linked.binding.model_copy(update={"generation": 2})})
    if change == "policy": policy = policy.model_copy(update={"binding": linked.binding.model_copy(update={"generation": 2})})
    with pytest.raises(ReadError): compare_changes(linked, source, linked.tally, policy)


def test_workflow_freshly_reads_only_confirmed_ids_and_propagates_errors(linked):
    calls = []
    source = changed(linked.bahi, state="Delhi")
    class Reader:
        def __init__(self, row): self.row = row
        def detail(self, binding, identity):
            calls.append((self.row.side, binding, identity))
            return self.row
    class Links:
        def find(self, binding, side, identity):
            return linked if binding == linked.binding and side == Side.BAHI and identity == linked.bahi.identity else None
    readers = (Reader(source), Reader(linked.tally))
    snapshot = SimpleNamespace(business_id=linked.binding.business_id, company_guid=linked.binding.company_guid)
    workflow = LinkedPartyReviewWorkflow(lambda _: readers, lambda: snapshot, Links(),
        lambda _: TransferPolicy(binding=linked.binding, operator="Reviewer"), lambda _: SimpleNamespace(validate=lambda draft: {}))
    review = workflow.review(linked.binding, None, "source")
    assert review.bahi.content.state == "Delhi"
    assert [c[2] for c in calls] == ["source", "target"]
    with pytest.raises(ReadError, match="no confirmed link"): workflow.review(linked.binding, None, "not-linked")
    assert len(calls) == 2
    readers[1].row = linked.tally.model_copy(update={"identity": "wrong-target"})
    with pytest.raises(ReadError, match="identity/context"): workflow.review(linked.binding, None, "source")
    readers[1].row = linked.tally.model_copy(update={"observed_at": datetime.now(timezone.utc)-timedelta(minutes=6)})
    with pytest.raises(ReadError, match="stale"): workflow.review(linked.binding, None, "source")
    def unavailable(*_): raise ReadError("Offline")
    readers[1].detail = unavailable
    with pytest.raises(ReadError, match="Offline"): workflow.review(linked.binding, None, "source")
    snapshot.company_guid = "wrong-company"
    with pytest.raises(ReadError, match="connection changed"): workflow.review(linked.binding, None, "source")
