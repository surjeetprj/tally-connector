"""Explicit, local-only confirmation after re-reading the selected identities."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from innoforia_tally_connector.application.ports import PartyLinks, PartyReader
from innoforia_tally_connector.domain.masters import Binding, ConfirmedPartyLink, PartyObservation, Side


def confirm_party_link(binding: Binding, expected_bahi: PartyObservation,
                       expected_tally: PartyObservation, *, bahi: PartyReader,
                       tally: PartyReader, links: PartyLinks, confirmed_by: str,
                       review_reference: str,
                       max_age: timedelta = timedelta(minutes=5)) -> ConfirmedPartyLink:
    if max_age <= timedelta(0):
        raise ValueError("Positive freshness bound required")
    for expected, side in ((expected_bahi, Side.BAHI), (expected_tally, Side.TALLY)):
        if expected.binding != binding or expected.side != side:
            raise ValueError("Discard stale selection")
    current_bahi = bahi.detail(binding, expected_bahi.identity)
    current_tally = tally.detail(binding, expected_tally.identity)
    now = datetime.now(timezone.utc)
    for expected, current in ((expected_bahi, current_bahi), (expected_tally, current_tally)):
        if current.comparison() != expected.comparison():
            raise ValueError("Selected record changed; reload and review")
        if not timedelta(0) <= now - current.observed_at <= max_age:
            raise ValueError("Detail observation is stale or future dated")
    link = ConfirmedPartyLink(
        id=str(uuid4()), binding=binding, bahi=current_bahi, tally=current_tally,
        confirmed_by=confirmed_by, confirmed_at=now, review_reference=review_reference,
    )
    # Readers have finished: the repository opens only a bounded local transaction.
    links.save(link)
    return link
