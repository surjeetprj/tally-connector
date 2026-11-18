"""Company-derived mailing dates are approval context, never fixture defaults."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from innoforia_tally_connector.domain.experiments import Direction, ExperimentPreview
from innoforia_tally_connector.domain.masters import PartyContent, PartyType
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.integrations.tally.builders.parties import party_xml, validate_party_xml
from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
from innoforia_tally_connector.integrations.tally.xml_codec import parse


class Remote:
    books_from = "20250401"  # Deliberately different from the export fixture.
    after_date = None
    company_reads = 0
    imports = 0

    def export(self, request):
        root = parse(request)
        assert root.findtext("HEADER/TALLYREQUEST") == "Export"
        kind = root.findtext("HEADER/ID")
        if kind == "ConnectorReadCompany":
            assert "BooksFrom" in [n.text for n in root.findall(".//FETCH")]
            self.company_reads += 1
            date = self.after_date if self.company_reads % 2 == 0 and self.after_date is not None else self.books_from
            value = f'<BOOKSFROM>{date}</BOOKSFROM>' if date is not None else ''
            return f'<COLLECTION><COMPANY NAME="SIS Dummy"><GUID>{COMPANY_GUID}</GUID>{value}</COMPANY></COLLECTION>'.encode()
        assert root.findtext(".//SVCURRENTCOMPANY") == "SIS Dummy"
        if kind == "ConnectorReadGroup":
            return b'<COLLECTION><GROUP NAME="Sundry Creditors"><GUID>root</GUID><PARENT>Primary</PARENT><ALTERID>1</ALTERID></GROUP></COLLECTION>'
        return b'<COLLECTION/>'

    def import_party(self, request):
        validate_party_xml(request)
        assert parse(request).findtext(".//APPLICABLEFROM") == self.books_from
        self.imports += 1
        return b'<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>88</LASTMID></RESPONSE>'


@pytest.fixture
def mailing(binding, observation):
    context = binding.model_copy(update={"business_id": 52, "company_guid": COMPANY_GUID})
    draft = PartyDraft(name="Synthetic mailing", party_type=PartyType.SUPPLIER, address="Exact address", country="India")
    source = observation(binding=context, name=draft.name, is_system=False,
        content=PartyContent(name=draft.name, address=draft.address, country=draft.country))
    remote = Remote()
    gateway = Gateway(remote)
    return context, draft, source, remote, gateway


def preview_for(mailing):
    binding, draft, source, remote, gateway = mailing
    now = datetime.now(timezone.utc)
    return ExperimentPreview(id="mailing", binding=binding, generation=1, direction=Direction.TO_TALLY,
        kind="TRANSFER", source=source, party=draft, created_at=now, expires_at=now + timedelta(minutes=5),
        preflight=gateway.preflight_party(binding, "root", draft))


def test_preflight_and_import_use_company_date_and_bind_it_to_approval(mailing):
    context, draft, source, remote, gateway = mailing
    preview = preview_for(mailing)
    group = json.loads(preview.preflight.group_context)
    assert group["mailing_applicable_from"] == "20250401"
    assert group["mailing_date_source"] == "Company.BooksFrom"
    assert gateway.create_party(preview, "root").identity == "88" and remote.imports == 1


@pytest.mark.parametrize("date", [None, "", "2026-04-01", "20260230", "99990401"])
def test_missing_invalid_or_future_books_date_blocks_before_import(mailing, date):
    _, _, _, remote, gateway = mailing
    remote.books_from = date
    with pytest.raises(ValueError, match="books date"):
        preview_for(mailing)
    assert remote.imports == 0


def test_books_date_change_during_preflight_blocks(mailing):
    _, _, _, remote, gateway = mailing
    remote.after_date = "20240401"
    with pytest.raises(ValueError, match="changed during preflight"):
        preview_for(mailing)
    assert remote.imports == 0


def test_books_date_change_after_approval_blocks_without_new_import(mailing):
    _, _, _, remote, gateway = mailing
    preview = preview_for(mailing)
    remote.books_from = "20240401"
    changed = preview_for(mailing)
    assert preview.digest != changed.digest
    with pytest.raises(ValueError, match="context changed"):
        gateway.create_party(preview, "root")
    assert remote.imports == 0


@pytest.mark.parametrize("date", [None, "", "2026-04-01", "20260230"])
def test_builder_has_no_date_fallback(mailing, date):
    _, draft, _, _, _ = mailing
    with pytest.raises(ValueError):
        party_xml(draft, "SIS Dummy", "Sundry Creditors", date)


@pytest.mark.parametrize("extra", [
    b'<COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>',
    b'<ADDRESS.LIST><ADDRESS>Wrong root</ADDRESS></ADDRESS.LIST>',
    b'<LEDMAILINGDETAILS.LIST><APPLICABLEFROM>20250401</APPLICABLEFROM><COUNTRY>Other</COUNTRY></LEDMAILINGDETAILS.LIST>',
])
def test_strict_transport_rejects_legacy_root_or_multiple_mailing_payloads(mailing, extra):
    _, draft, _, _, _ = mailing
    raw = party_xml(draft, "SIS Dummy", "Sundry Creditors", "20250401")
    with pytest.raises(ValueError):
        validate_party_xml(raw.replace(b'</LEDGER>', extra + b'</LEDGER>'))
