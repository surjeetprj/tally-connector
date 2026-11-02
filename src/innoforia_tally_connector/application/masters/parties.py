"""Read-only discovery and candidate suggestions. Call from background execution."""
from dataclasses import dataclass
from heapq import merge

from innoforia_tally_connector.application.ports import PartyLinks, PartyReader
from innoforia_tally_connector.domain.masters import Binding, PartyObservation, PartyScan, PartyType, Side


@dataclass(frozen=True)
class Candidate:
    bahi: PartyObservation
    tally: PartyObservation
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Discovery:
    bahi: PartyScan
    tally: PartyScan
    candidates: tuple[Candidate, ...]


def search_name(value: str) -> str:
    return " ".join(value.casefold().split())


def discover(binding: Binding, bahi: PartyReader, tally: PartyReader,
             links: PartyLinks) -> Discovery:
    left, right = bahi.scan(binding), tally.scan(binding)
    if (left.binding != binding or right.binding != binding
            or left.side != Side.BAHI or right.side != Side.TALLY):
        raise ValueError("Discard stale or incorrectly scoped scan")
    # Eligibility belongs to this discovery call only. Confirmation still
    # re-reads the selected records and enforces unique links transactionally.
    sources = [record for record in left.records
               if not links.find(binding, Side.BAHI, record.identity)]
    targets = [(record, search_name(record.content.name)) for record in right.records
               if not links.find(binding, Side.TALLY, record.identity)]
    by_name: dict[tuple[PartyType, str], list[int]] = {}
    by_gstin: dict[tuple[PartyType, str], list[int]] = {}
    for position, (target, target_name) in enumerate(targets):
        by_name.setdefault((target.party_type, target_name), []).append(position)
        if target.content.gstin:
            by_gstin.setdefault((target.party_type, target.content.gstin), []).append(position)

    candidates = []
    for source in sources:
        source_name = search_name(source.content.name)
        name_positions = by_name.get((source.party_type, source_name), ())
        gstin_positions = (by_gstin.get((source.party_type, source.content.gstin), ())
                          if source.content.gstin else ())
        previous_position = None
        # Index lists already follow scan order. Merge without revisiting
        # unrelated targets or emitting a pair twice when both criteria match.
        for position in merge(name_positions, gstin_positions):
            if position == previous_position:
                continue
            previous_position = position
            target, target_name = targets[position]
            reasons = []
            if source_name == target_name:
                reasons.append("name")
            if source.content.gstin and source.content.gstin == target.content.gstin:
                reasons.append("gstin")
            if reasons:
                candidates.append(Candidate(source, target, tuple(reasons)))
    return Discovery(left, right, tuple(candidates))
