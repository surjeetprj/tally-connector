"""One injected serialized gateway for Tally reads and typed party creates."""
from threading import Lock

from innoforia_tally_connector.domain.errors import Busy, ContextMismatch, ReadError
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import records
from innoforia_tally_connector.domain.experiments import Preflight
from innoforia_tally_connector.integrations.tally.builders.masters import supplier_xml
from innoforia_tally_connector.integrations.tally.builders.parties import party_xml, ROOTS, MAILING_FIELDS
from innoforia_tally_connector.integrations.tally.dates import xml_date
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.integrations.tally.experiment import import_receipt
from innoforia_tally_connector.integrations.tally.state_update import native_snapshot, native_shape, expected_native, state_xml, state_receipt
from innoforia_tally_connector.domain.experiments import TargetIdentity
from innoforia_tally_connector.integrations.tally.xml_codec import parse
import json
from datetime import datetime, timezone, timedelta

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

    def _state_snapshot(self, binding, identity):
        if binding.business_id != 52 or binding.company_guid != COMPANY_GUID:
            raise ContextMismatch("Controlled state updates support the confirmed test pair only")
        company = self._company(binding.company_guid)
        raw = self._export(collection("Ledger", company["NAME"], identity, complete=True))
        snapshot = native_snapshot(raw, identity)
        if self._company(binding.company_guid)["NAME"] != company["NAME"]:
            raise ContextMismatch("Company changed during state snapshot")
        return company, snapshot

    def state_snapshot(self, binding, identity):
        if not self.lock.acquire(timeout=self.lock_timeout): raise Busy("Tally busy; no state snapshot read")
        try:
            company, snapshot = self._state_snapshot(binding, identity)
            return Preflight(destination=f"Tally {company['NAME']} ({company['GUID']})",
                group_context=json.dumps({"company_guid": company["GUID"], "company_name": company["NAME"]}, sort_keys=True)), snapshot
        finally: self.lock.release()

    def apply_state(self, preview):
        if preview.kind != "UPDATE": raise ValueError("Typed state update required")
        if not self.lock.acquire(timeout=self.lock_timeout): raise Busy("Tally busy; no update sent")
        try:
            company, current = self._state_snapshot(preview.binding, preview.update.before.identity)
            expected_context = json.loads(preview.preflight.group_context)
            if company["NAME"] != expected_context["company_name"] or native_shape(current) != native_shape(preview.update.native_before):
                raise ContextMismatch("Ledger/company changed after approval; no update sent")
            # The official selector is NAME. Resolve it from GUID and reject a
            # duplicate name before transmission; never use a name on failed GUID lookup.
            name = parse(current.encode()).findtext("NAME")
            rows = records(self._export(collection("Ledger", company["NAME"])), "Ledger")
            matches = [r for r in rows if r.get("NAME", "").casefold() == name.casefold()]
            if (len(matches) != 1 or matches[0].get("GUID") != preview.update.before.identity
                or matches[0].get("ALTERID", "").strip() != parse(current.encode()).findtext("ALTERID", "").strip()):
                raise ContextMismatch("Ledger name no longer uniquely resolves to the approved GUID")
            if self._company(preview.binding.company_guid)["NAME"] != company["NAME"]:
                raise ContextMismatch("Company changed before state update")
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
            if self.stopped(): raise ReadError("Shutdown started; no update sent")
            raw = self.transport.alter_state(state_xml(current, preview.party.state, company["NAME"]),
                current, preview.party.state, company["NAME"])
            target = TargetIdentity(kind="TALLY_GUID", identity=preview.update.before.identity)
            return state_receipt(raw, target)
        finally: self.lock.release()

    def _supplier_preflight(self, binding, root_id, party, root_name="Sundry Creditors"):
        if binding.company_guid != COMPANY_GUID or binding.business_id != 52:
            raise ContextMismatch("Only the confirmed business-52/SIS-Dummy test pair can create")
        company = self._company(binding.company_guid)
        groups = records(self._export(collection("Group", company["NAME"])), "Group")
        matches = [g for g in groups if g.get("GUID") == root_id and g.get("NAME") == root_name]
        if len(matches) != 1:
            raise ContextMismatch(f"Confirmed party root must be the observed {root_name} group")
        ledgers = records(self._export(collection("Ledger", company["NAME"])), "Ledger")
        if any(r.get("NAME", "").casefold() == party.name.casefold() for r in ledgers):
            raise ReadError("Test party name already exists; no creation is allowed")
        if any(not r.get("GUID") for r in ledgers):
            raise ReadError("Tally baseline has missing identities; cannot prepare creation")
        after = self._company(binding.company_guid)
        if after["NAME"] != company["NAME"]:
            raise ContextMismatch("Company changed during preflight")
        context = {"company_guid": company["GUID"], "company_name": company["NAME"], "group": matches[0]}
        if isinstance(party, PartyDraft) and party.model_fields_set & MAILING_FIELDS:
            try:
                books_date = xml_date(company.get("BOOKSFROM"))
            except ValueError:
                raise ReadError("Tally company books date is unavailable/invalid; mailing creation is blocked") from None
            if books_date > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
                raise ReadError("Tally company books date is in the future; mailing creation is blocked")
            if after.get("BOOKSFROM") != company["BOOKSFROM"]:
                raise ContextMismatch("Company books date changed during preflight")
            context["mailing_applicable_from"] = company["BOOKSFROM"]
            context["mailing_date_source"] = "Company.BooksFrom"
        context = json.dumps(context, sort_keys=True)
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

    def preflight_party(self, binding, root_id, draft):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally busy; no party request sent")
        try:
            return self._supplier_preflight(binding, root_id, draft, ROOTS[draft.party_type])
        finally:
            self.lock.release()

    def create_party(self, preview, root_id):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally busy; no import sent")
        try:
            current = self._supplier_preflight(preview.binding, root_id, preview.party, ROOTS[preview.party.party_type])
            if current.group_context != preview.preflight.group_context or current.destination != preview.preflight.destination:
                raise ContextMismatch("Destination/group context changed; no import sent")
            preview.require_current(preview.binding, preview.generation, preview.digest, datetime.now(timezone.utc))
            if self.stopped():
                raise ReadError("Shutdown started; no import sent")
            context = json.loads(current.group_context)
            raw = self.transport.import_party(party_xml(preview.party, context["company_name"],
                ROOTS[preview.party.party_type], context.get("mailing_applicable_from")))
            return import_receipt(raw, current.baseline_guids)
        finally:
            self.lock.release()
