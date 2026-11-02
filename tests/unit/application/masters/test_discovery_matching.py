"""Indexed matching must preserve the original search semantics and order."""
from collections import Counter
from datetime import datetime, timezone

import pytest

from innoforia_tally_connector.application.masters.parties import discover
from innoforia_tally_connector.domain.masters import PartyContent, PartyScan, PartyType, Side


class MappingChecks:
    def __init__(self, linked=()):
        self.linked = set(linked)
        self.calls = []

    def find(self, binding, side, identity):
        self.calls.append((side, identity))
        return object() if (side, identity) in self.linked else None

    def save(self, link):
        pytest.fail("Discovery must not save links")


def test_order_ambiguity_deduplication_and_exact_gstin(binding, observation, reader):
    def party(side, identity, name, gstin=None, party_type=PartyType.SUPPLIER):
        return observation(side, identity, party_type=party_type,
                           content=PartyContent(name=name, gstin=gstin))

    left = [party(Side.BAHI, "1", " Example  Supplier ", "ABC"),
            party(Side.BAHI, "2", "EXAMPLE SUPPLIER", ""),
            party(Side.BAHI, "3", "Unmatched", None),
            party(Side.BAHI, "4", "Example Supplier", "ABC")]
    right = [party(Side.TALLY, "0", "Branch A", "ABC"),
             party(Side.TALLY, "1", "example supplier", "other"),
             party(Side.TALLY, "2", "Example Supplier", "ABC"),
             party(Side.TALLY, "3", "Branch B", "ABC"),
             party(Side.TALLY, "4", "Example Supplier", "ABC", PartyType.CUSTOMER),
             party(Side.TALLY, "5", "Example Supplier", "ABC"),
             party(Side.TALLY, "6", "Example-Supplier", None),
             party(Side.TALLY, "7", "Different", "abc"),
             party(Side.TALLY, "8", "Different", " ABC "),
             party(Side.TALLY, "9", "Different", "")]
    links = MappingChecks(((Side.BAHI, "4"), (Side.TALLY, "5")))
    result = discover(binding, reader(left), reader(right), links)
    actual = [(c.bahi.identity, c.tally.identity, c.reasons) for c in result.candidates]
    assert actual == [
        ("1", "0", ("gstin",)), ("1", "1", ("name",)),
        ("1", "2", ("name", "gstin")), ("1", "3", ("gstin",)),
        ("2", "1", ("name",)), ("2", "2", ("name",)),
    ]
    assert Counter(links.calls) == Counter(
        [(Side.BAHI, r.identity) for r in left] + [(Side.TALLY, r.identity) for r in right])
    assert all(c.bahi is left[int(c.bahi.identity) - 1] for c in result.candidates)
    assert all(c.tally is right[int(c.tally.identity)] for c in result.candidates)
    assert left[0].content.name == " Example  Supplier "


@pytest.mark.parametrize("wrong_side", [Side.BAHI, Side.TALLY])
def test_invalid_scan_context_precedes_mapping_checks(wrong_side, binding, observation, reader):
    left, right = observation(), observation(Side.TALLY, "2")
    wrong = binding.model_copy(update={"generation": 2})
    if wrong_side == Side.BAHI:
        left = left.model_copy(update={"binding": wrong})
    else:
        right = right.model_copy(update={"binding": wrong})

    class WrongContextReader:
        def scan(self, requested_binding):
            record = left if wrong_side == Side.BAHI else right
            return PartyScan(binding=wrong, side=wrong_side, records=(record,),
                             observed_at=datetime.now(timezone.utc), pages_read=(1,), total_pages=1)

    links = MappingChecks()
    with pytest.raises(ValueError, match="scoped scan"):
        discover(binding, WrongContextReader() if wrong_side == Side.BAHI else reader([left]),
                 WrongContextReader() if wrong_side == Side.TALLY else reader([right]), links)
    assert links.calls == []


@pytest.mark.parametrize("failing_side", [Side.BAHI, Side.TALLY])
def test_mapping_errors_propagate(failing_side, binding, observation, reader):
    class FailingChecks(MappingChecks):
        def find(self, binding, side, identity):
            if side == failing_side:
                raise RuntimeError("Mapping read failed")
            return super().find(binding, side, identity)

    with pytest.raises(RuntimeError, match="Mapping read failed"):
        discover(binding, reader([observation()]), reader([observation(Side.TALLY, "2")]), FailingChecks())


def test_discovery_rechecks_link_eligibility_each_call(binding, observation, reader):
    bahi, tally = reader([observation()]), reader([observation(Side.TALLY, "2")])
    links = MappingChecks()
    assert len(discover(binding, bahi, tally, links).candidates) == 1
    links.linked.add((Side.TALLY, "2"))
    assert discover(binding, bahi, tally, links).candidates == ()
    assert Counter(links.calls) == Counter({(Side.BAHI, "1"): 2, (Side.TALLY, "2"): 2})


def test_discovery_preserves_partial_scan_metadata(binding, observation):
    observed_at = datetime.now(timezone.utc)
    left = PartyScan(binding=binding, side=Side.BAHI, records=(observation(),),
                     observed_at=observed_at, pages_read=(1,), total_pages=2, failed_pages=(2,))
    right = PartyScan(binding=binding, side=Side.TALLY, records=(observation(Side.TALLY, "2"),),
                      observed_at=observed_at, pages_read=(1,))

    class ScanReader:
        def __init__(self, scan):
            self.result = scan

        def scan(self, binding):
            return self.result

    result = discover(binding, ScanReader(left), ScanReader(right), MappingChecks())
    assert result.bahi is left
    assert result.tally is right
    assert not result.bahi.coverage_complete
    assert not result.tally.complete_baseline
    assert len(result.candidates) == 1
