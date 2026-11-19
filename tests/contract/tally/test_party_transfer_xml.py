import httpx
import pytest

from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.domain.masters import PartyType
from innoforia_tally_connector.integrations.tally.builders.parties import party_xml, validate_party_xml, validate, ROOTS
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.xml_codec import parse, records
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.domain.experiments import UncertainWrite
from innoforia_tally_connector.integrations.tally.experiment import import_receipt


@pytest.mark.parametrize("kind", list(PartyType))
def test_structured_mailing_create_and_readback(kind, binding):
    draft = PartyDraft(name="Source & <party>", party_type=kind, email="a@example.invalid", phone="00123",
                      address="First\n\nThird", pincode="012345", country="India", state="State")
    raw = party_xml(draft, "SIS & Dummy", ROOTS[kind], "20260401")
    validate_party_xml(raw)
    assert parse(raw).findtext(".//SVCURRENTCOMPANY") == "SIS & Dummy"
    assert [node.text or "" for node in parse(raw).findall(".//ADDRESS.LIST/ADDRESS")] == ["First", "", "Third"]
    ledger = parse(raw).find(".//LEDGER")
    assert ledger.findtext("LEDMAILINGDETAILS.LIST/APPLICABLEFROM") == "20260401"
    assert ledger.findtext("LEDMAILINGDETAILS.LIST/COUNTRY") == "India"
    assert ledger.findtext("LEDMAILINGDETAILS.LIST/STATE") == "State"
    assert ledger.findtext("LEDMAILINGDETAILS.LIST/PINCODE") == "012345"
    assert all(ledger.find(tag) is None for tag in ("ADDRESS.LIST", "COUNTRYOFRESIDENCE", "COUNTRYNAME", "LEDSTATENAME", "PINCODE"))
    calls = []
    def handler(request):
        calls.append(request)
        validate_party_xml(request.content)
        return httpx.Response(200, content=b"<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>22</LASTMID></RESPONSE>")
    transport = Transport(httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        assert import_receipt(transport.import_party(raw), ()).identity == "22"
        with pytest.raises(ValueError): transport.export(raw)
        assert len(calls) == 1
    finally:
        transport.close()
    ledger = parse(raw).find(".//LEDGER")
    from lxml import etree
    response = b"<COLLECTION>" + etree.tostring(ledger) + b"</COLLECTION>"
    row = records(response, "Ledger")[0]
    assert row["MAILING_CONTENT"] == {"address": "First\n\nThird", "state": "State", "country": "India", "pincode": "012345"}
    assert parse(raw).find(".//COUNTRYNAME") is None


@pytest.mark.parametrize("mutation", ["alter", "delete", "extra", "multiple", "context"])
def test_arbitrary_xml_rejected(mutation):
    raw = party_xml(PartyDraft(name="Party", party_type=PartyType.CUSTOMER), "SIS Dummy", "Sundry Debtors")
    if mutation in {"alter", "delete"}: raw = raw.replace(b'Create', mutation.title().encode())
    if mutation == "extra": raw = raw.replace(b"</LEDGER>", b"<OPENINGBALANCE>1</OPENINGBALANCE></LEDGER>")
    if mutation == "multiple": raw = raw.replace(b"</TALLYMESSAGE>", b"<LEDGER ACTION='Create'/></TALLYMESSAGE>")
    if mutation == "context": raw = raw.replace(b"SIS Dummy", b"")
    with pytest.raises(ValueError): validate_party_xml(raw)


def test_unverified_tax_and_null_values_fail_closed():
    for field in ("gstin", "pan", "gst_reg_type"):
        draft = PartyDraft(name="Party", party_type=PartyType.SUPPLIER, **{field: "value"})
        assert field in validate(draft)
        with pytest.raises(ValueError): party_xml(draft, "SIS Dummy", "Sundry Creditors")
    assert "email" in validate(PartyDraft(name="Party", party_type=PartyType.SUPPLIER, email=None))
    with pytest.raises(UncertainWrite):
        import_receipt(b"<RESPONSE><CREATED>1</CREATED><CREATED>0</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS></RESPONSE>", ())


@pytest.mark.parametrize('kind',list(PartyType))
def test_tax_create_contains_only_supported_dated_values_and_checks_date_on_readback(kind,binding):
    from innoforia_tally_connector.domain.masters import Classification
    from lxml import etree
    draft=PartyDraft(name='Tax party',party_type=kind,pan='CNXPP6229G',gstin='09CNXPP6229G1Z7',
        gst_reg_type='Regular',state='Uttar Pradesh',country='India',pincode='001234')
    raw=party_xml(draft,'SIS Dummy',ROOTS[kind],'20260401')
    validate_party_xml(raw)
    ledger=parse(raw).find('.//LEDGER')
    assert ledger.findtext('INCOMETAXNUMBER')==draft.pan
    assert ledger.findtext('LEDGSTREGDETAILS.LIST/GSTIN')==draft.gstin
    assert ledger.findtext('LEDGSTREGDETAILS.LIST/APPLICABLEFROM')=='20260401'
    assert ledger.find('PARTYGSTIN') is None and ledger.find('OPENINGBALANCE') is None
    etree.SubElement(ledger,'GUID').text='party'
    etree.SubElement(ledger,'ALTERID').text='1'
    row=records(b'<COLLECTION>'+etree.tostring(ledger)+b'</COLLECTION>','Ledger')[0]
    class Gateway:
        def read(self,entity,company_guid,guid=None):
            if entity=='Group':return [{'GUID':'root','NAME':ROOTS[kind],'PARENT':'Primary','ALTERID':'1'},
                    {'GUID':'other','NAME':'Sundry Creditors' if kind==PartyType.CUSTOMER else 'Sundry Debtors','PARENT':'Primary','ALTERID':'1'}]
            return [row]
    classification=Classification(customer_root='root' if kind==PartyType.CUSTOMER else 'other',
        supplier_root='root' if kind==PartyType.SUPPLIER else 'other')
    reader=PartyReader(Gateway(),classification)
    target=reader.detail(binding,'party',mailing_date='20260401',gst_date='20260401')
    assert not {'pan','gstin','gst_reg_type'} & set(target.unavailable_fields)
    assert target.content.gstin==draft.gstin and target.content.pan==draft.pan
    row['GST_APPLICABLE_FROM']='20260501'
    assert {'gstin','gst_reg_type'}<=set(reader.detail(binding,'party',gst_date='20260401').unavailable_fields)
    row.pop('GST_APPLICABLE_FROM')  # Root echoes/ignored history never prove success.
    assert 'gstin' in reader.detail(binding,'party',gst_date='20260401').unavailable_fields
    bad=raw.replace(b'<APPLICABLEFROM>20260401</APPLICABLEFROM>',b'<APPLICABLEFROM>20260501</APPLICABLEFROM>',1)
    with pytest.raises(ValueError): validate_party_xml(bad)


def test_tally_multiline_reader_and_new_field_availability(binding):
    from innoforia_tally_connector.domain.masters import Classification
    class Gateway:
        def read(self, entity, company_guid, guid=None):
            if entity == "Group":
                return [{"GUID": "a", "NAME": "Sundry Debtors", "PARENT": "Primary", "ALTERID": "1"},
                        {"GUID": "b", "NAME": "Sundry Creditors", "PARENT": "Primary", "ALTERID": "1"}]
            return [{"GUID": "party", "NAME": "Party", "PARENT": "Sundry Debtors", "ALTERID": "1",
                     "ADDRESS_LINES": ("One", "Two"), "COUNTRYNAME": "India"}]
    row = PartyReader(Gateway(), Classification(customer_root="a", supplier_root="b")).detail(binding, "party")
    assert row.content.address == "One\nTwo" and row.content.country == "India"
    assert row.content_schema == 2 and {"pan", "gst_reg_type"} <= set(row.unavailable_fields)


@pytest.mark.parametrize("kind", list(PartyType))
def test_general_gateway_create_and_exports_never_overlap(kind, binding, observation):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta, timezone
    from threading import Lock
    import time
    from innoforia_tally_connector.domain.experiments import Direction, ExperimentPreview
    from innoforia_tally_connector.domain.masters import PartyContent
    from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
    class Remote:
        guard = Lock()
        active = maximum = imports = 0
        changed = False
        def enter(self):
            with self.guard:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            time.sleep(0.002)
        def leave(self):
            with self.guard: self.active -= 1
        def export(self, request):
            self.enter()
            try:
                entity = parse(request).findtext("HEADER/ID")
                if entity == "ConnectorReadCompany":
                    return f'<COLLECTION><COMPANY NAME="SIS Dummy"><GUID>{COMPANY_GUID}</GUID></COMPANY></COLLECTION>'.encode()
                if entity == "ConnectorReadGroup":
                    name = "Changed root" if self.changed else ROOTS[kind]
                    return f'<COLLECTION><GROUP NAME="{name}"><GUID>root</GUID><PARENT>Primary</PARENT></GROUP></COLLECTION>'.encode()
                return b'<COLLECTION><LEDGER NAME="Existing"><GUID>existing</GUID></LEDGER></COLLECTION>'
            finally: self.leave()
        def import_party(self, request):
            self.enter()
            try:
                validate_party_xml(request)
                assert parse(request).findtext(".//PARENT") == ROOTS[kind]
                assert parse(request).findtext(".//SVCURRENTCOMPANY") == "SIS Dummy"
                self.imports += 1
                return b'<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>88</LASTMID></RESPONSE>'
            finally: self.leave()
    live_binding = binding.model_copy(update={"business_id": 52, "company_guid": COMPANY_GUID})
    draft = PartyDraft(name="Actual source", party_type=kind, email="party@example.invalid")
    source = observation(name=draft.name, party_type=kind, binding=live_binding,
        content=PartyContent(name=draft.name, email=draft.email), is_system=False)
    remote = Remote()
    gateway = Gateway(remote, lock_timeout=2)
    preflight = gateway.preflight_party(live_binding, "root", draft)
    now = datetime.now(timezone.utc)
    preview = ExperimentPreview(id="actual-transfer", binding=live_binding, generation=1,
        direction=Direction.TO_TALLY, source=source, kind="TRANSFER", party=draft, preflight=preflight,
        created_at=now, expires_at=now + timedelta(minutes=5))
    with ThreadPoolExecutor(max_workers=2) as executor:
        create = executor.submit(gateway.create_party, preview, "root")
        read = executor.submit(gateway.read, "Ledger")
        assert create.result().identity == "88" and read.result()
    assert remote.maximum == 1 and remote.imports == 1
    remote.changed = True
    with pytest.raises(ValueError): gateway.create_party(preview, "root")
    assert remote.imports == 1
