"""One injected serialized gateway for all application Tally reads."""
from threading import Lock

from innoforia_tally_connector.domain.errors import Busy, ContextMismatch, ReadError
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import records
from innoforia_tally_connector.domain.experiments import Preflight
from innoforia_tally_connector.integrations.tally.builders.masters import supplier_xml
from innoforia_tally_connector.integrations.tally.experiment import import_receipt
import json
from datetime import datetime, timezone

COMPANY_GUID = "0b212ad8-3be5-45fe-8719-e1a70e240d4c"


class Gateway:
    def __init__(self, transport=None, lock_timeout=1, stopped=lambda: False):
        self.transport = transport or Transport()
        self.lock = Lock()
        self.lock_timeout = lock_timeout
        self.stopped = stopped

    def _export(self, request):
        if self.stopped():
            raise ReadError("Tally read stopped during shutdown")
        return self.transport.export(request)

    def _company(self, guid):
        matches = [r for r in records(self._export(collection("Company")), "Company")
                   if r.get("GUID") == guid]
        if len(matches) != 1 or not matches[0].get("NAME"):
            raise ContextMismatch("Expected Tally company is not uniquely loaded")
        return matches[0]

    def read(self, entity="Company", company_guid=COMPANY_GUID, guid=None):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally read is busy; retry after the current request")
        try:
            before = self._company(company_guid)
            if entity == "Company":
                return [before]
            result = records(self._export(collection(entity, before["NAME"], guid)), entity)
            after = self._company(company_guid)
            if before["NAME"] != after["NAME"]:
                raise ContextMismatch("Tally company changed during the read")
            return result
        finally:
            self.lock.release()

    def close(self):
        self.transport.close()

    def _supplier_preflight(self, binding, root_id, party):
        if binding.company_guid != COMPANY_GUID or binding.business_id != 52:
            raise ContextMismatch("Only the confirmed business-52/SIS-Dummy test pair can create")
        company = self._company(binding.company_guid)
        groups = records(self._export(collection("Group", company["NAME"])), "Group")
        matches = [g for g in groups if g.get("GUID") == root_id and g.get("NAME") == "Sundry Creditors"]
        if len(matches) != 1:
            raise ContextMismatch("Confirmed supplier root must be the observed Sundry Creditors group")
        ledgers = records(self._export(collection("Ledger", company["NAME"])), "Ledger")
        if any(r.get("NAME", "").casefold() == party.name.casefold() for r in ledgers):
            raise ReadError("Test party name already exists; no creation is allowed")
        if any(not r.get("GUID") for r in ledgers):
            raise ReadError("Tally baseline has missing identities; cannot prepare creation")
        if self._company(binding.company_guid)["NAME"] != company["NAME"]:
            raise ContextMismatch("Company changed during preflight")
        context = json.dumps({"company_guid": company["GUID"], "company_name": company["NAME"],
                               "group": matches[0]}, sort_keys=True)
        return Preflight(group_context=context, destination=f"Tally {company['NAME']} ({company['GUID']})",
                         baseline_guids=tuple(sorted(r["GUID"] for r in ledgers)))

    def preflight_test_supplier(self, binding, root_id, party):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally is busy; creation preview was not prepared")
        try:
            return self._supplier_preflight(binding, root_id, party)
        finally:
            self.lock.release()

    def create_test_supplier(self, preview, root_id, preflight):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally is busy; no import sent")
        try:
            current = self._supplier_preflight(preview.binding, root_id, preview.party)
            if current.group_context != preview.preflight.group_context or current.destination != preview.preflight.destination:
                raise ContextMismatch("Tally destination/group changed after approval; no import sent")
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
            if self.stopped():
                raise ReadError("Creation stopped before import")
            context = json.loads(current.group_context)
            raw = self.transport.import_test_supplier(supplier_xml(preview.party, context["company_name"], "Sundry Creditors"))
            # No further IO before the application persists this receipt/identity.
            return import_receipt(raw, preflight.baseline_guids)
        finally:
            self.lock.release()
