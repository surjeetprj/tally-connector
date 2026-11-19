import httpx
import pytest
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import TargetIdentity, UncertainWrite
from innoforia_tally_connector.integrations.tally.state_update import native_snapshot, expected_native, native_shape, state_xml, validate_state_xml, state_receipt, SENTINEL, preservation_matches
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally._transport import Transport

GUID = '11111111-2222-3333-4444-555555555555-00000001'


def native(state='', version='1', other='Keep', extra=''):
    return (f'<COLLECTION><LEDGER NAME="Synthetic &amp; supplier" RESERVEDNAME=""><GUID>{GUID}</GUID><MASTERID>1</MASTERID><ALTERID>{version}</ALTERID>'
        f'<PARENT>Sundry Creditors</PARENT><LEDSTATENAME>{state}</LEDSTATENAME><OTHER>{other}</OTHER><OPENINGBALANCE>0</OPENINGBALANCE>'
        '<GSTTYPE>&#4; Not Applicable</GSTTYPE><LEDMAILINGDETAILS.LIST><ADDRESS.LIST TYPE="String"><ADDRESS>Exact – दिल्ली</ADDRESS><ADDRESS></ADDRESS></ADDRESS.LIST>'
        f'<APPLICABLEFROM>20260401</APPLICABLEFROM><PINCODE>012345</PINCODE><MAILINGNAME>Synthetic &amp; supplier</MAILINGNAME><STATE>{state}</STATE><COUNTRY>India</COUNTRY></LEDMAILINGDETAILS.LIST>{extra}</LEDGER></COLLECTION>').encode()


def test_only_state_payload_with_lossless_native_preservation_evidence():
    before = native_snapshot(native(), GUID)
    after = native_snapshot(native('Delhi', version='2'), GUID)
    assert SENTINEL in before
    assert native_shape(expected_native(before, 'Delhi'), ignore_version=True) == native_shape(after, ignore_version=True)
    assert native_shape(expected_native(before, 'Delhi'), ignore_version=True) != native_shape(native_snapshot(native('Delhi', '2', other='Changed'), GUID), ignore_version=True)
    raw = state_xml(before, 'Delhi', 'SIS Dummy')
    validate_state_xml(raw, before, 'Delhi', 'SIS Dummy')
    ledger = parse(raw).find('.//LEDGER')
    assert ledger.attrib == {'NAME': 'Synthetic & supplier', 'ACTION': 'Alter'}
    assert [n.tag for n in ledger] == ['GUID', 'LEDMAILINGDETAILS.LIST']
    assert ledger.findtext('GUID') == GUID and ledger.findtext('LEDMAILINGDETAILS.LIST/STATE') == 'Delhi'
    assert ledger.findtext('LEDMAILINGDETAILS.LIST/APPLICABLEFROM') == '20260401'
    assert [n.text or '' for n in ledger.findall('.//ADDRESS')] == ['Exact – दिल्ली', '']
    assert all(x not in raw for x in (b'OPENINGBALANCE', b'GSTTYPE', SENTINEL.encode()))


@pytest.mark.parametrize('case', ['wrong_guid','duplicate_guid','unknown_control','dtd','reserved_token','history','future_date','no_date'])
def test_unknown_or_ambiguous_snapshot_blocks(case):
    raw = native()
    if case == 'wrong_guid': raw = raw.replace(GUID.encode(), b'wrong')
    if case == 'duplicate_guid': raw = raw.replace(b'</GUID>', b'</GUID><GUID>other</GUID>')
    if case == 'unknown_control': raw = raw.replace(b'<OTHER>Keep</OTHER>', b'<OTHER>&#4; Keep</OTHER>')
    if case == 'dtd': raw = b'<!DOCTYPE X [<!ENTITY e SYSTEM "file:///secret">]>' + raw
    if case == 'reserved_token': raw = raw.replace(b'Keep', SENTINEL.encode())
    if case == 'history': raw = native(extra='<LEDMAILINGDETAILS.LIST><APPLICABLEFROM>20250401</APPLICABLEFROM><STATE>Old</STATE></LEDMAILINGDETAILS.LIST>')
    if case == 'future_date': raw = raw.replace(b'20260401',b'99990401')
    if case == 'no_date': raw = raw.replace(b'<APPLICABLEFROM>20260401</APPLICABLEFROM>',b'')
    with pytest.raises((ReadError, ValueError)):
        snapshot = native_snapshot(raw, GUID)
        state_xml(snapshot, 'Delhi', 'SIS Dummy')


@pytest.mark.parametrize('mutation', ['create','delete','extra','guid','company','state','second'])
def test_transport_rejects_arbitrary_alterations_without_http(mutation):
    before = native_snapshot(native(), GUID)
    raw = state_xml(before, 'Delhi', 'SIS Dummy')
    if mutation in {'create','delete'}: raw=raw.replace(b'ACTION="Alter"', f'ACTION="{mutation.title()}"'.encode())
    if mutation == 'extra': raw=raw.replace(b'</LEDGER>',b'<OPENINGBALANCE>10</OPENINGBALANCE></LEDGER>')
    if mutation == 'guid': raw=raw.replace(GUID.encode(),b'wrong')
    if mutation == 'company': raw=raw.replace(b'SIS Dummy',b'Other')
    if mutation == 'state': raw=raw.replace(b'Delhi',b'Other')
    if mutation == 'second': raw=raw.replace(b'</TALLYMESSAGE>',b'<LEDGER ACTION="Alter"/></TALLYMESSAGE>')
    transport=Transport(httpx.Client(transport=httpx.MockTransport(lambda *_:pytest.fail('No HTTP allowed'))))
    try:
        with pytest.raises(ReadError): transport.alter_state(raw,before,'Delhi','SIS Dummy')
    finally: transport.close()


@pytest.mark.parametrize('extra', ['<CREATED>1</CREATED>','<STATUS>0</STATUS>','<STATUS>1</STATUS><STATUS>1</STATUS>','<LINEERROR>Refused</LINEERROR>','<IGNORED>1</IGNORED>'])
def test_bad_or_duplicate_receipts_retain_known_target(extra):
    target=TargetIdentity(kind='TALLY_GUID',identity=GUID)
    raw=('<RESPONSE><CREATED>0</CREATED><ALTERED>1</ALTERED><ERRORS>0</ERRORS>'+extra+'</RESPONSE>').encode('utf-16-le')
    with pytest.raises(UncertainWrite) as caught:state_receipt(raw,target)
    assert caught.value.target==target


def test_correct_receipt_still_requires_external_readback():
    target=TargetIdentity(kind='TALLY_GUID',identity=GUID)
    assert state_receipt(b'<RESPONSE><CREATED>0</CREATED><ALTERED>1</ALTERED><ERRORS>0</ERRORS></RESPONSE>',target)==target


@pytest.mark.parametrize('mutation', [None, 'foreign_guid', 'wrong_state', 'wrong_type', 'other_field', 'removed_projection', 'history'])
def test_observed_import_metadata_and_derived_state_are_narrowly_verified(mutation):
    # Before 7.0 export omitted the empty computed projection. After Alter it
    # appeared with TYPE=String; RemoteAltGUID changed empty -> object's own GUID.
    raw = native(extra='<REMOTEALTGUID></REMOTEALTGUID>').replace(b'<LEDSTATENAME></LEDSTATENAME>', b'')
    before = native_snapshot(raw, GUID)
    approved = expected_native(before, 'Delhi')
    actual_raw = native('Delhi', '2', extra=f'<REMOTEALTGUID>{GUID}</REMOTEALTGUID>').replace(b'<LEDSTATENAME>', b'<LEDSTATENAME TYPE="String">')
    if mutation == 'foreign_guid': actual_raw = actual_raw.replace(f'<REMOTEALTGUID>{GUID}</REMOTEALTGUID>'.encode(), b'<REMOTEALTGUID>other-guid</REMOTEALTGUID>')
    if mutation == 'wrong_state': actual_raw = actual_raw.replace(b'<LEDSTATENAME TYPE="String">Delhi', b'<LEDSTATENAME TYPE="String">Other')
    if mutation == 'wrong_type': actual_raw = actual_raw.replace(b'TYPE="String">Delhi', b'TYPE="Unknown">Delhi')
    if mutation == 'other_field': actual_raw = actual_raw.replace(b'<OPENINGBALANCE>0', b'<OPENINGBALANCE>1')
    if mutation == 'history': actual_raw = actual_raw.replace(b'20260401', b'20250401')
    if mutation == 'removed_projection':
        approved = expected_native(native_snapshot(native(extra='<REMOTEALTGUID></REMOTEALTGUID>'), GUID), 'Delhi')
        actual_raw = actual_raw.replace(b'<LEDSTATENAME TYPE="String">Delhi</LEDSTATENAME>', b'')
    actual = native_snapshot(actual_raw, GUID)
    assert preservation_matches(approved, actual, 'Delhi') == (mutation is None)
    assert '<REMOTEALTGUID' in approved  # Approval evidence remains unchanged.


def test_nonempty_import_identity_is_not_silently_replaced():
    before = native_snapshot(native(extra='<REMOTEALTGUID>prior-id</REMOTEALTGUID>'), GUID)
    actual = native_snapshot(native('Delhi','2',extra=f'<REMOTEALTGUID>{GUID}</REMOTEALTGUID>'),GUID)
    assert not preservation_matches(expected_native(before,'Delhi'),actual,'Delhi')
