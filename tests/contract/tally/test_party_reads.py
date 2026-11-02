from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

import httpx
import pytest

from innoforia_tally_connector.domain.errors import Busy, ContextMismatch, ReadError
from innoforia_tally_connector.domain.masters import Classification, GroupObservation
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader, ancestry, validate_classification
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally._transport import Transport


def groups():
    return tuple(GroupObservation(identity=identity, name=name, parent=parent, version="1") for identity, name, parent in
        [("a", "Debtors", "Primary"), ("b", "Creditors", "Primary"), ("c", "Sub-debtors", "Debtors")])


def test_classification_descendants_overlap_and_unknown(binding):
    roots = Classification(customer_root="a", supplier_root="b")
    validate_classification(roots, groups())
    with pytest.raises(ReadError, match="overlap"):
        validate_classification(Classification(customer_root="a", supplier_root="c"), groups())
    with pytest.raises(ReadError, match="ancestry"):
        ancestry("Missing", groups())
    cycle = (GroupObservation(identity="1", name="A", parent="B", version="1"),
             GroupObservation(identity="2", name="B", parent="A", version="1"))
    with pytest.raises(ReadError, match="cyclic"):
        ancestry("A", cycle)


def test_guid_detail_and_rename_keep_identity(binding):
    rows = [{"GUID": "stable-guid", "NAME": "Renamed", "ALTERID": "2", "PARENT": "Sub-debtors",
             "LEDGERPHONE": "00123"}]
    class FakeGateway:
        def read(self, entity, company_guid, guid=None):
            if entity == "Group":
                return [dict(GUID=g.identity, NAME=g.name, PARENT=g.parent, ALTERID=g.version) for g in groups()]
            assert guid == "stable-guid"
            return rows
    reader = PartyReader(FakeGateway(), Classification(customer_root="a", supplier_root="b"))
    detail = reader.detail(binding, "stable-guid")
    assert detail.content.name == "Renamed" and detail.content.phone == "00123"
    assert detail.party_type == "CUSTOMER" and "address" in detail.unavailable_fields
    rows.clear()
    with pytest.raises(ReadError, match="no name fallback"):
        reader.detail(binding, "stable-guid")


@pytest.mark.parametrize("raw", [b'<X><NAME>&#4; Business</NAME></X>',
    b'<!DOCTYPE x [<!ENTITY foo SYSTEM "file:///secret">]><X>&foo;</X>', b'<X>'])
def test_strict_xml_rejects_unverified_controls_and_entities(raw):
    with pytest.raises(ReadError):
        parse(raw)


@pytest.mark.parametrize("reference", [b"&#4;", b"&#x04;"])
def test_only_proven_primary_parent_sentinel_is_normalized(reference):
    assert parse(b'<X><PARENT TYPE="String">' + reference + b' Primary</PARENT></X>').findtext("PARENT") == "Primary"


def test_gateway_serialization_and_busy():
    class FakeTransport:
        active = 0
        maximum = 0
        guard = Lock()
        def export(self, request):
            with self.guard:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            time.sleep(0.005)
            try:
                if parse(request).findtext("HEADER/ID") == "ConnectorReadCompany":
                    return f'<COLLECTION><COMPANY NAME="Dummy"><GUID>{COMPANY_GUID}</GUID></COMPANY></COLLECTION>'.encode()
                return b'<COLLECTION><LEDGER NAME="Synthetic"><GUID>ledger</GUID></LEDGER></COLLECTION>'
            finally:
                with self.guard:
                    self.active -= 1
    transport = FakeTransport()
    gateway = Gateway(transport, lock_timeout=2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert all(executor.map(lambda _: gateway.read("Ledger"), range(8)))
    assert transport.maximum == 1
    gateway.lock.acquire()
    gateway.lock_timeout = 0.001
    try:
        with pytest.raises(Busy):
            gateway.read()
    finally:
        gateway.lock.release()
    with pytest.raises(ContextMismatch):
        gateway.read(company_guid="another-company")


def test_transport_refuses_import_and_redirect():
    calls = []
    def response(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "http://example.com"})
    transport = Transport(httpx.Client(transport=httpx.MockTransport(response), follow_redirects=False))
    try:
        with pytest.raises(ReadError, match="exports"):
            transport.export(b'<ENVELOPE><HEADER><TALLYREQUEST>Import</TALLYREQUEST></HEADER></ENVELOPE>')
        assert not calls
        with pytest.raises(ReadError, match="302"):
            transport.export(collection("Company"))
        assert len(calls) == 1
    finally:
        transport.close()
