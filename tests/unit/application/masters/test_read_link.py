from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from innoforia_tally_connector.application.masters.mappings import confirm_party_link
from innoforia_tally_connector.application.masters.parties import discover
from innoforia_tally_connector.domain.masters import PartyContent, PartyScan, PartyType, Side


def confirm(binding, left, right, reader, store, **overrides):
    args = dict(bahi=reader([left]), tally=reader([right]), links=store,
                confirmed_by="local reviewer", review_reference="synthetic manual link review")
    args.update(overrides)
    return confirm_party_link(binding, left, right, **args)


def test_candidates_keep_ambiguity_and_never_persist(binding, observation, reader, store):
    left = observation(name=" Example  Supplier ")
    targets = [observation(Side.TALLY, str(n)) for n in (2, 3)]
    result = discover(binding, reader([left]), reader(targets), store)
    assert len(result.candidates) == 2
    assert result.bahi.coverage_complete
    assert not result.bahi.complete_baseline
    assert store.find(binding, Side.BAHI, "1") is None
    assert left.content.name == " Example  Supplier "


def test_gstin_candidates_and_incompatible_types(binding, observation, reader, store):
    left = observation(content=PartyContent(name="Branch A", gstin="synthetic-tax-id"))
    targets = [observation(Side.TALLY, "2", content=PartyContent(name="Branch B", gstin="synthetic-tax-id")),
               observation(Side.TALLY, "3", party_type=PartyType.CUSTOMER)]
    result = discover(binding, reader([left]), reader(targets), store)
    assert [c.reasons for c in result.candidates] == [("gstin",)]


def test_link_keeps_differences_and_leading_zeroes(binding, observation, reader, store):
    left = observation(content=PartyContent(name="Example Supplier", phone="00123", pincode="012345"))
    right = observation(Side.TALLY, "2", name="Different name")
    saved = confirm(binding, left, right, reader, store)
    assert saved.bahi.content != saved.tally.content
    loaded = store.find(binding, Side.TALLY, "2")
    assert loaded == saved
    assert loaded.bahi.content.phone == "00123"
    assert "acknowledged" not in loaded.model_dump_json()
    result = discover(binding, reader([left]), reader([right]), store)
    assert result.candidates == ()


@pytest.mark.parametrize("change", ["content", "version", "identity", "binding", "classification"])
def test_changed_detail_rejects_confirmation(change, binding, observation, reader, store):
    left, right = observation(), observation(Side.TALLY, "2")
    changes = {
        "content": {"content": PartyContent(name="Edited")},
        "version": {"version": "new"}, "identity": {"identity": "unexpected"},
        "binding": {"binding": binding.model_copy(update={"generation": 2})},
        "classification": {"party_type": PartyType.CUSTOMER},
    }
    current = left.model_copy(update=changes[change])
    class ChangedReader:
        def detail(self, *_):
            return current
    with pytest.raises(ValueError, match="changed"):
        confirm(binding, left, right, reader, store, bahi=ChangedReader())
    assert store.find(binding, Side.BAHI, left.identity) is None


@pytest.mark.parametrize("minutes", [-10, 10])
def test_stale_or_future_details_block(minutes, binding, observation, reader, store):
    left = observation(observed_at=datetime.now(timezone.utc) + timedelta(minutes=minutes))
    with pytest.raises(ValueError, match="stale or future"):
        confirm(binding, left, observation(Side.TALLY, "2"), reader, store)


def test_wrong_selection_context_fails_before_reads(binding, observation, reader, store):
    left = observation()
    wrong = binding.model_copy(update={"generation": 2})
    with pytest.raises(ValueError, match="stale selection"):
        confirm(wrong, left, observation(Side.TALLY, "2"), reader, store)


def test_incompatible_confirmation_rejected(binding, observation, reader, store):
    with pytest.raises(ValidationError, match="Incompatible"):
        confirm(binding, observation(), observation(Side.TALLY, "2", party_type=PartyType.CUSTOMER), reader, store)


def test_missing_null_and_balance_exclusion():
    assert PartyContent(name="A").model_dump(exclude_unset=True) != PartyContent(name="A", phone=None).model_dump(exclude_unset=True)
    with pytest.raises(ValidationError):
        PartyContent(name="A", balance="10")


def test_partial_coverage_is_not_baseline(binding):
    scan = PartyScan(binding=binding, side=Side.BAHI, records=(),
                     observed_at=datetime.now(timezone.utc), pages_read=(1,),
                     total_pages=2, failed_pages=(2,))
    assert not scan.coverage_complete
    assert not scan.complete_baseline


def test_scan_rejects_duplicates_and_wrong_binding(binding, observation):
    args = dict(binding=binding, side=Side.BAHI, observed_at=datetime.now(timezone.utc), pages_read=(1,))
    with pytest.raises(ValidationError, match="Repeated identity"):
        PartyScan(records=(observation(), observation()), **args)
    with pytest.raises(ValidationError, match="outside scan"):
        PartyScan(records=(observation(Side.TALLY),), **args)


def test_wrong_scan_context_is_discarded(binding, observation, reader, store):
    with pytest.raises(ValueError, match="scoped scan"):
        discover(binding, reader([observation(Side.TALLY)]), reader([observation(Side.TALLY)]), store)
