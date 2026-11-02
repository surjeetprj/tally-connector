"""Manual read/link workflow; concrete connections and storage are injected."""
from dataclasses import dataclass
from datetime import datetime, timezone

from innoforia_tally_connector.application.masters.mappings import confirm_party_link
from innoforia_tally_connector.application.masters.parties import compare_scans
from innoforia_tally_connector.domain.errors import ContextMismatch, ReadError
from innoforia_tally_connector.domain.masters import Binding, Classification, ConfirmedPartyLink, ConnectionSnapshot, PartyScan, ScanIssue, Side


@dataclass(frozen=True)
class Verified:
    snapshot: ConnectionSnapshot
    saved_setup: tuple[Binding, Classification, ConnectionSnapshot] | None


@dataclass(frozen=True)
class Bound:
    binding: Binding
    classification: Classification
    links: tuple[ConfirmedPartyLink, ...]
    has_more: bool = False


@dataclass(frozen=True)
class SavedPage:
    links: tuple[ConfirmedPartyLink, ...]
    offset: int
    has_more: bool


class DiscoveryWorkflow:
    def __init__(self, verify, readers, validate_groups, store, links, credential_reference):
        self.verify, self.readers, self.validate_groups = verify, readers, validate_groups
        self.store, self.links, self.credential_reference = store, links, credential_reference
        self.active = None

    def handle(self, command):
        if command.kind == "VERIFY":
            self.active = None
            return Verified(self.verify(), self.store.setup())
        if command.kind == "BIND":
            self.active = None
            snapshot = self.verify()
            if command.classification is None:
                raise ReadError("Explicit customer and supplier group confirmation is required")
            self.validate_groups(command.classification, snapshot.groups)
            old = self.store.setup()
            binding = old[0] if old else Binding(id="bahi52-sis-dummy", business_id=snapshot.business_id,
                                                  company_guid=snapshot.company_guid, generation=1)
            if binding.business_id != snapshot.business_id or binding.company_guid != snapshot.company_guid:
                raise ContextMismatch("Saved binding no longer matches the verified pair")
            self.store.bind(binding, command.classification, snapshot, self.credential_reference)
            self.active = (binding, command.classification, command.generation)
            links = self.links.list(binding, limit=201)
            return Bound(binding, command.classification, links[:200], len(links) > 200)
        if not self.active or command.binding != self.active[0] or command.generation != self.active[2]:
            raise ContextMismatch("Verify and explicitly confirm the current binding first")
        binding, classification, _ = self.active
        if command.kind == "SAVED":
            links = self.links.list(binding, offset=command.offset, limit=201)
            return SavedPage(links[:200], command.offset, len(links) > 200)
        bahi, tally = self.readers(classification)
        if command.kind == "LOAD":
            scans = []
            for side, reader in ((Side.BAHI, bahi), (Side.TALLY, tally)):
                try:
                    scans.append(reader.scan(binding))
                except ContextMismatch:
                    raise
                except ReadError as error:
                    scans.append(PartyScan(binding=binding, side=side, records=(),
                        observed_at=datetime.now(timezone.utc), pages_read=(), total_pages=None,
                        failed_pages=(1,), issues=(ScanIssue(code="READ_FAILED", message=str(error)),)))
            return compare_scans(binding, *scans, self.links)
        if command.kind == "LINK":
            if command.bahi is None or command.tally is None or not command.reviewer or not command.reviewer.strip():
                raise ReadError("Select both records and enter the confirming reviewer")
            return confirm_party_link(binding, command.bahi, command.tally, bahi=bahi, tally=tally,
                links=self.links, confirmed_by=command.reviewer, review_reference=command.id, link_id=command.id)
        raise ReadError("Unsupported discovery command")
