"""Binding-guarded unfiltered party paging and exact ID detail reads."""
from datetime import datetime, timezone
import math

from pydantic import ValidationError

from innoforia_tally_connector.domain.errors import ContextMismatch, ReadError
from innoforia_tally_connector.domain.masters import PartyContent, PartyObservation, PartyScan, PartyType, ScanIssue, Side
from innoforia_tally_connector.integrations.bahi.schemas.parties import Party, Pagination


class PartyReader:
    def __init__(self, client, progress=lambda *_: None, stopped=lambda: False, max_pages=100):
        self.client, self.progress, self.stopped = client, progress, stopped
        self.max_pages = max_pages

    def _observation(self, row, binding):
        values = row.model_dump(exclude_unset=True)
        content = {key: values[key] for key in PartyContent.model_fields if key in values}
        content["name"] = row.account_name
        return PartyObservation(binding=binding, side=Side.BAHI, identity=str(row.account_id),
                                party_type=PartyType(row.party_type), classification_evidence="Bahi party_type",
                                content=PartyContent(**content), version=row.updated_dtm,
                                is_active=row.is_active, observed_at=datetime.now(timezone.utc))

    def detail(self, binding, identity):
        self.client.business(binding.business_id)
        if not identity.isdecimal() or str(int(identity)) != identity or int(identity) <= 0:
            raise ReadError("Invalid Bahi party identity")
        try:
            row = Party.model_validate(self.client.get("api-party.php", {"id": identity})["data"])
        except ValidationError:
            raise ReadError("Bahi party detail does not match the documented contract") from None
        if str(row.account_id) != identity:
            raise ContextMismatch("Bahi returned a different party identity")
        return self._observation(row, binding)

    def scan(self, binding):
        self.client.business(binding.business_id)
        found, pages, issues, failed = [], [], [], []
        total_pages, expected_total, seen = None, None, set()
        for page in range(1, self.max_pages + 1):
            if self.stopped():
                issues.append(ScanIssue(code="STOPPED", message="Read stopped before completion"))
                break
            try:
                result = self.client.get("api-party.php", {"page": page, "limit": 200})
                paging = Pagination.model_validate(result.get("pagination"))
                if paging.page != page or paging.limit != 200:
                    raise ReadError("Bahi pagination differs from the requested page")
                if paging.total_pages != math.ceil(paging.total / paging.limit):
                    raise ReadError("Bahi pagination totals are inconsistent")
                if total_pages is not None and (paging.total_pages != total_pages or paging.total != expected_total):
                    raise ReadError("Bahi pagination changed during the scan; refresh")
                total_pages, expected_total = paging.total_pages, paging.total
                if not isinstance(result["data"], list):
                    raise ReadError("Bahi party list is invalid")
                rows = [Party.model_validate(row) for row in result["data"]]
                ids = [row.account_id for row in rows]
                if len(ids) != len(set(ids)) or seen.intersection(ids):
                    raise ReadError("Repeated Bahi identities across pages; refresh")
                expected_length = min(paging.limit, max(0, paging.total - (page - 1) * paging.limit))
                if len(rows) != expected_length:
                    raise ReadError("Bahi page count differs from pagination totals")
                observations = [self._observation(row, binding) for row in rows]
                found.extend(observations)
                seen.update(ids)
                if total_pages:
                    pages.append(page)
                self.progress("Bahi", f"Page {page}; {len(found)} parties observed")
                if page >= total_pages:
                    break
            except ContextMismatch:
                raise
            except (ReadError, ValidationError):
                failed.append(page)
                # If the server's totals shrank, retain the previous successful
                # coverage without contradicting PartyScan's page invariants.
                total_pages = max(total_pages or page, page)
                issues.append(ScanIssue(code="PAGE_FAILED", message=f"Bahi page {page} failed validation or reading; refresh"))
                break
        else:
            issues.append(ScanIssue(code="PAGE_LIMIT", message="Bahi page limit reached; scan is incomplete"))
        return PartyScan(binding=binding, side=Side.BAHI, records=tuple(found),
                         observed_at=datetime.now(timezone.utc), pages_read=tuple(pages),
                         total_pages=total_pages, failed_pages=tuple(failed), issues=tuple(issues))
