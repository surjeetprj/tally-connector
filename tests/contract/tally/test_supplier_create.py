import pytest

from innoforia_tally_connector.domain.experiments import synthetic_supplier, UncertainWrite
from innoforia_tally_connector.integrations.tally.builders.masters import supplier_xml, validate_supplier_xml
from innoforia_tally_connector.integrations.tally.experiment import import_receipt


def test_single_supplier_company_scoped_xml():
    party = synthetic_supplier()
    raw = supplier_xml(party, "SIS Dummy", "Sundry Creditors")
    validate_supplier_xml(raw)
    assert b"SIS Dummy" in raw and party.email.encode() in raw
    assert b"OPENINGBALANCE" not in raw and b"VOUCHER" not in raw


@pytest.mark.parametrize("mode", ["Alter", "Delete", "multiple", "balance", "company", "container"])
def test_reject_arbitrary_imports(mode):
    raw = supplier_xml(synthetic_supplier(), "SIS Dummy", "Sundry Creditors")
    if mode in {"Alter", "Delete"}: raw = raw.replace(b'ACTION="Create"', f'ACTION="{mode}"'.encode())
    if mode == "multiple": raw = raw.replace(b"</TALLYMESSAGE>", b'<LEDGER ACTION="Create"/></TALLYMESSAGE>')
    if mode == "balance": raw = raw.replace(b"</LEDGER>", b"<OPENINGBALANCE>1</OPENINGBALANCE></LEDGER>")
    if mode == "company": raw = raw.replace(b"SIS Dummy", b"")
    if mode == "container": raw = raw.replace(b"</REQUESTDESC>", b"<REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>")
    with pytest.raises(ValueError): validate_supplier_xml(raw)


@pytest.mark.parametrize("extra", [b"<ERRORS>1</ERRORS>", b"<LINEERROR>bad</LINEERROR>", b"<ALTERED>1</ALTERED>", b"<STATUS>0</STATUS>"])
def test_receipt_errors_never_succeed(extra):
    raw = b"<RESPONSE><CREATED>1</CREATED><LASTMID>7</LASTMID>" + extra + b"</RESPONSE>"
    with pytest.raises(UncertainWrite) as caught: import_receipt(raw, ())
    assert caught.value.target.identity == "7"


def test_positive_receipt_is_only_identity_resolution_evidence():
    raw = b"<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS></RESPONSE>"
    result = import_receipt(raw, ("existing",))
    assert result.kind == "TALLY_CREATED_EXPORT" and result.baseline_guids == ("existing",)
    assert import_receipt(raw.replace(b"</RESPONSE>", b"<LASTMID>42</LASTMID></RESPONSE>"), ()).identity == "42"
    with pytest.raises(UncertainWrite): import_receipt(b"<broken", ())


def test_typed_gateway_serializes_create_with_exports_and_rechecks_context(binding):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time
    from innoforia_tally_connector.domain.experiments import Direction, new_preview
    from innoforia_tally_connector.integrations.tally.gateway import Gateway, COMPANY_GUID
    from innoforia_tally_connector.integrations.tally.xml_codec import parse
    class Transport:
        guard = Lock()
        active = maximum = imports = 0
        changed = False
        def enter(self):
            with self.guard:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
            time.sleep(0.003)
        def leave(self):
            with self.guard: self.active -= 1
        def export(self, request):
            self.enter()
            try:
                entity = parse(request).findtext("HEADER/ID")
                if entity == "ConnectorReadCompany":
                    return f'<COLLECTION><COMPANY NAME="SIS Dummy"><GUID>{COMPANY_GUID}</GUID></COMPANY></COLLECTION>'.encode()
                if entity == "ConnectorReadGroup":
                    name = "Renamed Creditors" if self.changed else "Sundry Creditors"
                    return f'<COLLECTION><GROUP NAME="{name}"><GUID>root</GUID><PARENT>Primary</PARENT></GROUP></COLLECTION>'.encode()
                return b'<COLLECTION><LEDGER NAME="Existing"><GUID>existing</GUID></LEDGER></COLLECTION>'
            finally: self.leave()
        def import_test_supplier(self, request):
            self.enter()
            try:
                validate_supplier_xml(request)
                assert parse(request).findtext(".//SVCURRENTCOMPANY") == "SIS Dummy"
                self.imports += 1
                return b'<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><LASTMID>99</LASTMID></RESPONSE>'
            finally: self.leave()
    transport = Transport()
    gateway = Gateway(transport, lock_timeout=2)
    binding = binding.model_copy(update={"business_id": 52, "company_guid": COMPANY_GUID})
    party = synthetic_supplier()
    preflight = gateway.preflight_test_supplier(binding, "root", party)
    preview = new_preview(binding, 1, Direction.TO_TALLY, party, preflight)
    with ThreadPoolExecutor(max_workers=2) as pool:
        create = pool.submit(gateway.create_test_supplier, preview, "root", preflight)
        read = pool.submit(gateway.read, "Ledger")
        assert create.result().identity == "99" and read.result()
    assert transport.maximum == 1 and transport.imports == 1
    transport.changed = True
    with pytest.raises(ValueError): gateway.create_test_supplier(preview, "root", preflight)
    assert transport.imports == 1
