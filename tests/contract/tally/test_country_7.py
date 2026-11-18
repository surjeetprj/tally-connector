"""Actual export tag shape, with synthetic identities; no remote calls."""
from pathlib import Path
import httpx
import pytest
from innoforia_tally_connector.domain.masters import Classification, PartyType
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.builders.parties import party_xml, validate_party_xml
from innoforia_tally_connector.integrations.tally.xml_codec import parse, records

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/tally/party_country_7.xml"


def test_country_7_query_decode_and_typed_import_agree(binding):
    raw = FIXTURE.read_bytes()
    guid = records(raw, "Ledger")[0]["GUID"]
    calls = []
    def response(request):
        root = parse(request.content)
        assert root.findtext("HEADER/TALLYREQUEST") == "Export"
        calls.append(request)
        entity = root.findtext("HEADER/ID")
        if entity == "ConnectorReadCompany":
            return httpx.Response(200, content=f'<COLLECTION><COMPANY><GUID>{COMPANY_GUID}</GUID><NAME>SIS Dummy</NAME></COMPANY></COLLECTION>'.encode())
        assert root.findtext(".//SVCURRENTCOMPANY") == "SIS Dummy"
        if entity == "ConnectorReadGroup":
            return httpx.Response(200, content=b'<COLLECTION><GROUP><GUID>debtors</GUID><NAME>Sundry Debtors</NAME><PARENT>Primary</PARENT><ALTERID>1</ALTERID></GROUP><GROUP><GUID>creditors</GUID><NAME>Sundry Creditors</NAME><PARENT>Primary</PARENT><ALTERID>1</ALTERID></GROUP></COLLECTION>')
        fetches = [node.text for node in root.findall(".//FETCH")]
        assert "CountryofResidence" in fetches and "CountryName" not in fetches
        assert guid in root.findtext(".//SYSTEM")
        return httpx.Response(200, content=raw)
    gateway = Gateway(Transport(httpx.Client(transport=httpx.MockTransport(response))))
    try:
        context = binding.model_copy(update={"company_guid": COMPANY_GUID})
        result = PartyReader(gateway, Classification(customer_root="debtors", supplier_root="creditors")).detail(context, guid)
        assert result.content.country == "India" and "country" not in result.unavailable_fields
        draft = PartyDraft(name="Synthetic country supplier", party_type=PartyType.SUPPLIER, country=result.content.country)
        xml = party_xml(draft, "SIS Dummy", "Sundry Creditors")
        validate_party_xml(xml)
        assert parse(xml).findtext(".//COUNTRYOFRESIDENCE") == "India"
        assert parse(xml).find(".//COUNTRYNAME") is None
        assert parse(xml).find(".//LEDMAILINGDETAILS.LIST") is None  # No guessed effective date.
    finally:
        gateway.close()


@pytest.mark.parametrize("country", [None, "", "India"])
def test_country_absence_empty_and_conflicting_values(binding, country):
    reader = PartyReader(None, Classification(customer_root="a", supplier_root="b"))
    from innoforia_tally_connector.domain.masters import GroupObservation
    groups = (GroupObservation(identity="a", name="Debtors", parent="Primary", version="1"),
        GroupObservation(identity="b", name="Creditors", parent="Primary", version="1"))
    row = {"GUID": "synthetic", "NAME": "Party", "ALTERID": "1", "PARENT": "Creditors"}
    if country is not None: row["COUNTRYOFRESIDENCE"] = country
    result = reader._observation(row, binding, groups)
    assert ("country" in result.content.model_fields_set) == (country is not None)
    if country is not None:
        assert result.content.country == country
        row["COUNTRYNAME"] = "Different country"
        conflict = reader._observation(row, binding, groups)
        assert "country" in conflict.unavailable_fields
