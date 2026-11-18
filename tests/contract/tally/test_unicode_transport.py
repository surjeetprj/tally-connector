"""Unicode wire mode preserves values; strict XML and method gates still apply."""
import httpx
import pytest

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import synthetic_supplier, UncertainWrite
from innoforia_tally_connector.domain.masters import PartyType
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.builders.masters import supplier_xml
from innoforia_tally_connector.integrations.tally.builders.parties import party_xml
from innoforia_tally_connector.integrations.tally.experiment import import_receipt
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import parse, records


UNICODE = "Exact – café दिल्ली ₹ 😀"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le", "utf-16-be"])
def test_unicode_responses_with_or_without_bom_preserve_every_character(encoding):
    raw = f'<COLLECTION><LEDGER NAME="{UNICODE}"><PARENT>&#4; Primary</PARENT><EMAIL></EMAIL></LEDGER></COLLECTION>'.encode(encoding)
    row = records(raw, "Ledger")[0]
    assert row["NAME"] == UNICODE and row["PARENT"] == "Primary" and row["EMAIL"] == ""


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
@pytest.mark.parametrize("invalid", [
    '<!DOCTYPE X [<!ENTITY e SYSTEM "file:///secret">]><X>&e;</X>',
    '<X><NAME>&#4; Unexpected</NAME></X>', '<X>',
    '<X><NAME>\x04 Unexpected</NAME></X>',
])
def test_unicode_does_not_bypass_xml_guards(encoding, invalid):
    with pytest.raises(ReadError): parse(invalid.encode(encoding))


def test_malformed_utf16_is_not_repaired_or_replaced():
    for raw in (b'\xff\xfe<', b'<\0X\0>\0\x00\xd8<\0/\0X\0>\0'):
        with pytest.raises(ReadError): parse(raw)


@pytest.mark.parametrize("declared", ["UTF-8", "ASCII", "UTF-16BE"])
def test_mismatched_unicode_declarations_remain_invalid(declared):
    raw = f'<?xml version="1.0" encoding="{declared}"?><X/>'.encode('utf-16-le')
    with pytest.raises(ReadError): parse(raw)


def test_exports_request_unicode_and_decode_native_no_bom_reply():
    calls = []
    def remote(request):
        calls.append(request)
        assert request.headers["Content-Type"] == "UTF-16"
        assert request.content.startswith((b'\xff\xfe', b'\xfe\xff'))
        assert parse(request.content).findtext("HEADER/TALLYREQUEST") == "Export"
        assert parse(request.content).findtext(".//SVCURRENTCOMPANY") == UNICODE
        # The old request mode returned '?' on the actual deployment. This
        # independent Unicode response must reach the decoder unchanged.
        return httpx.Response(200, content=f'<COLLECTION><LEDGER NAME="{UNICODE}"/></COLLECTION>'.encode('utf-16-le'))
    transport = Transport(httpx.Client(transport=httpx.MockTransport(remote)))
    try:
        rows = records(transport.export(collection("Ledger", UNICODE)), "Ledger")
        assert rows[0]["NAME"] == UNICODE and len(calls) == 1
        with pytest.raises(ReadError): transport.export(b'<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER></ENVELOPE>')
        assert len(calls) == 1
    finally: transport.close()


@pytest.mark.parametrize("kind", list(PartyType))
def test_typed_creates_send_exact_unicode_and_parse_unicode_receipt(kind):
    draft = PartyDraft(name=UNICODE, party_type=kind, address=UNICODE + "\n\nLast", country="India")
    requests = []
    def remote(request):
        requests.append(request)
        assert request.headers["Content-Type"] == "UTF-16"
        root = parse(request.content)
        assert root.findtext(".//NAME") == UNICODE
        assert [n.text or "" for n in root.findall(".//ADDRESS")] == [UNICODE, "", "Last"]
        return httpx.Response(200, content='<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>42</LASTMID></RESPONSE>'.encode('utf-16-le'))
    transport = Transport(httpx.Client(transport=httpx.MockTransport(remote)))
    try:
        parent = "Sundry Debtors" if kind == PartyType.CUSTOMER else "Sundry Creditors"
        raw = transport.import_party(party_xml(draft, "SIS Dummy", parent, "20260401"))
        assert import_receipt(raw, ()).identity == "42" and len(requests) == 1
        with pytest.raises(ValueError):
            transport.import_party(party_xml(draft, "SIS Dummy", parent, "20260401").replace(b'ACTION="Create"', b'ACTION="Alter"'))
        assert len(requests) == 1
    finally: transport.close()


def test_legacy_typed_create_receipt_errors_remain_uncertain_in_unicode():
    calls = []
    def remote(request):
        calls.append(request)
        assert request.headers["Content-Type"] == "UTF-16"
        assert parse(request.content).findtext("HEADER/TALLYREQUEST") == "Import Data"
        return httpx.Response(200, content='<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>42</LASTMID><LINEERROR>échec – error</LINEERROR></RESPONSE>'.encode('utf-16-le'))
    transport = Transport(httpx.Client(transport=httpx.MockTransport(remote)))
    try:
        raw = transport.import_test_supplier(supplier_xml(synthetic_supplier(), "SIS Dummy", "Sundry Creditors"))
        with pytest.raises(UncertainWrite) as error: import_receipt(raw, ())
        assert error.value.target.identity == "42" and len(calls) == 1
    finally: transport.close()
