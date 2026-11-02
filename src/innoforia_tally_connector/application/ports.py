"""Only capabilities required by the local read/link milestone."""
from typing import Protocol

from innoforia_tally_connector.domain.masters import (
    Binding, ConfirmedPartyLink, PartyObservation, PartyScan, Side,
)


class PartyReader(Protocol):
    # Implementations must verify authenticated business / company identity and
    # classification, not simply stamp the requested binding on returned data.
    def scan(self, binding: Binding) -> PartyScan: ...
    def detail(self, binding: Binding, identity: str) -> PartyObservation: ...


class PartyLinks(Protocol):
    def save(self, link: ConfirmedPartyLink) -> None: ...
    def find(self, binding: Binding, side: Side, identity: str) -> ConfirmedPartyLink | None: ...
