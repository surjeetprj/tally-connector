"""Real XML/HTTP adapters, shared workflow and SQLite; synthetic remote responses."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from innoforia_tally_connector.application.masters.transfers import PartyTransferWorkflow
from innoforia_tally_connector.domain.commands import Command
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.masters import Classification, PartyContent, PartyType
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.parties import PartyReader
from innoforia_tally_connector.integrations.tally.transfers import PartyDestination
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.experiments import ExperimentStore
from innoforia_tally_connector.persistence.migrations.versions.v0001_party_links import link_audit


@pytest.mark.parametrize("tax_create",[False,True])
@pytest.mark.parametrize("kind", list(PartyType))
@pytest.mark.parametrize("ignored_mailing", [False, True])
@pytest.mark.parametrize("unicode_address", [False, True])
def test_dated_transfer_and_known_id_recovery_never_repeat_create(store, binding, observation, kind, ignored_mailing, unicode_address, tax_create):
    binding = binding.model_copy(update={"id": "mailing-binding", "business_id": 52, "company_guid": COMPANY_GUID})
    store.register_binding(binding)
    classification = Classification(customer_root="debtors", supplier_root="creditors")
    parent = "Sundry Debtors" if kind == PartyType.CUSTOMER else "Sundry Creditors"
    name = "Synthetic country supplier"
    first_line = "First – दिल्ली ₹" if unicode_address else "First"
    source = observation(binding=binding, name=name, party_type=kind, is_active=True, is_system=False, content_schema=2,
        content=PartyContent(name=name, address=first_line + "\n\nThird", state="State", country="India", pincode="012345"))
    if tax_create:
        source=source.model_copy(update={'content':source.content.model_copy(update={'pan':'CNXPP6229G','gstin':'09CNXPP6229G1Z7','gst_reg_type':'Regular'})})
    # Independent native-export fixture, not an echo of the builder/request.
    canonical = (Path(__file__).resolve().parents[1] / "fixtures/tally/party_country_7.xml").read_bytes()
    canonical = canonical.replace(b"Sundry Creditors", parent.encode())
    canonical = canonical.replace(b'>First<', ('>' + first_line + '<').encode('utf-8'))
    if tax_create:
        canonical=canonical.replace(b'</LEDGER>', b'<INCOMETAXNUMBER>CNXPP6229G</INCOMETAXNUMBER>'
            b'<LEDGSTREGDETAILS.LIST><APPLICABLEFROM>20260401</APPLICABLEFROM><GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>'
            b'<STATE>State</STATE><GSTIN>09CNXPP6229G1Z7</GSTIN></LEDGSTREGDETAILS.LIST></LEDGER>')
    ignored = (b'<COLLECTION><LEDGER NAME="Synthetic country supplier">'
        b'<GUID>11111111-2222-3333-4444-555555555555-00000001</GUID><MASTERID>1</MASTERID><ALTERID>1</ALTERID>'
        b'<NAME>Synthetic country supplier</NAME><PARENT>' + parent.encode() + b'</PARENT>'
        b'<COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE><LEDMAILINGDETAILS.LIST/></LEDGER></COLLECTION>')
    state = SimpleNamespace(imports=0, corrected=not ignored_mailing)

    def remote(request):
        assert request.headers["Content-Type"] == "UTF-16"
        root = parse(request.content)
        if root.findtext("HEADER/TALLYREQUEST") == "Import Data":
            state.imports += 1
            ledger = root.find(".//LEDGER")
            mailing = ledger.find("LEDMAILINGDETAILS.LIST")
            if tax_create:
                assert ledger.findtext('INCOMETAXNUMBER')=='CNXPP6229G'
                assert ledger.findtext('LEDGSTREGDETAILS.LIST/GSTIN')=='09CNXPP6229G1Z7'
                assert ledger.findtext('LEDGSTREGDETAILS.LIST/APPLICABLEFROM')=='20260401'
            assert root.findtext(".//SVCURRENTCOMPANY") == "SIS Dummy"
            assert ledger.findtext("PARENT") == parent
            assert mailing.findtext("APPLICABLEFROM") == "20260401"
            assert mailing.findtext("COUNTRY") == "India"
            assert mailing.findtext("STATE") == "State"
            assert mailing.findtext("PINCODE") == "012345"
            assert [n.text or "" for n in mailing.findall("ADDRESS.LIST/ADDRESS")] == [first_line, "", "Third"]
            assert ledger.find("COUNTRYOFRESIDENCE") is None and ledger.find("ADDRESS.LIST") is None
            return httpx.Response(200, content=b'<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>1</LASTMID></RESPONSE>')
        assert root.findtext("HEADER/TALLYREQUEST") == "Export"
        entity = root.findtext("HEADER/ID")
        if entity == "ConnectorReadCompany":
            return httpx.Response(200, content=f'<COLLECTION><COMPANY NAME="SIS Dummy"><GUID>{COMPANY_GUID}</GUID><BOOKSFROM>20260401</BOOKSFROM></COMPANY></COLLECTION>'.encode())
        if entity == "ConnectorReadGroup":
            return httpx.Response(200, content=b'<COLLECTION><GROUP NAME="Sundry Debtors"><GUID>debtors</GUID><PARENT>Primary</PARENT><ALTERID>1</ALTERID></GROUP>'
                b'<GROUP NAME="Sundry Creditors"><GUID>creditors</GUID><PARENT>Primary</PARENT><ALTERID>1</ALTERID></GROUP></COLLECTION>')
        assert "LedMailingDetails.*" in [n.text for n in root.findall(".//FETCH")]
        body = (canonical if state.corrected else ignored) if state.imports else b'<COLLECTION/>'
        if unicode_address:
            # Actual native HTTP shape: UTF-16LE without BOM/declaration.
            from lxml import etree
            body = etree.tostring(parse(body), encoding='unicode').encode('utf-16-le')
        return httpx.Response(200, content=body)

    gateway = Gateway(Transport(httpx.Client(transport=httpx.MockTransport(remote))))
    reader = PartyReader(gateway, classification)
    destination = PartyDestination(gateway, classification)
    class SourceReader:
        def detail(self, context, identity):
            assert context == binding and identity == source.identity
            return source.model_copy(update={"observed_at": datetime.now(timezone.utc)})
    records = ExperimentStore(store.engine)
    journal = DiscoveryStore(store.engine)
    workflow = PartyTransferWorkflow(records, lambda _: (SourceReader(), reader), lambda *_: destination,
        lambda: SimpleNamespace(business_id=52, company_guid=COMPANY_GUID), store)
    def run(kind, **kwargs):
        command = Command(id=str(uuid4()), binding=binding, generation=1, kind=kind, **kwargs)
        journal.capture(command)
        command = journal.claim(command.id)
        result = workflow.handle(command, binding, classification)
        journal.finish(command.id)
        return result
    try:
        prepared = run("TRANSFER_PREPARE", direction=Direction.TO_TALLY, source=source)
        result = run("TRANSFER_CREATE", direction=Direction.TO_TALLY, experiment_id=prepared.preview.id,
            approval_digest=prepared.preview.digest, reviewer="Synthetic reviewer")
        assert result.attempted and state.imports == 1
        assert result.target.kind == "TALLY_GUID"
        if ignored_mailing:
            assert result.state == "BLOCKED" and not store.by_id(result.preview.id)
            assert all(result.comparisons[field] is False for field in ("address", "state", "pincode", "country"))
            assert all(field in result.message for field in ("address", "country", "pincode", "state"))
            # Restart retrieval and unchanged reads cannot turn this into a new create.
            assert ExperimentStore(store.engine).get(result.preview.id, binding) == result
            result = run("TRANSFER_RECONCILE", experiment_id=result.preview.id)
            assert result.state == "BLOCKED" and state.imports == 1
            state.corrected = True  # Simulate owner correction of this SAME GUID.
            result = run("TRANSFER_RECONCILE", experiment_id=result.preview.id)
        assert result.state == "SUCCEEDED" and all(result.comparisons.values())
        link = store.by_id(result.preview.id)
        assert link.bahi.content == source.content and link.tally.content.address == source.content.address
        again = run("TRANSFER_CREATE", experiment_id=result.preview.id, direction=Direction.TO_TALLY,
            approval_digest=prepared.preview.digest, reviewer="Synthetic reviewer")
        assert again == result and state.imports == 1
        with store.engine.connect() as connection:
            assert connection.execute(select(link_audit.c.link_id)).scalar_one() == link.id
    finally:
        gateway.close()
