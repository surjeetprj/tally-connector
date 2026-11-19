from pathlib import Path
import pytest
from lxml import etree
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.state_update import native_snapshot
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally.party_update import expected_fields,fields_xml,validate_fields_xml,fields_preserved

GUID = '0b212ad8-3be5-45fe-8719-e1a70e240d4c-00000001'


@pytest.fixture
def before():
    return native_snapshot((Path(__file__).parents[2]/'fixtures/tally/state_update_native.xml').read_bytes(),GUID)


def test_all_fields_are_typed_and_unselected_native_data_stays_intact(before):
    values = dict(email='new@example.invalid',phone='00123',address=' Exact – दिल्ली\n\n Last ',state='Kerala',country='India',pincode='012345',pan='AAACA1234A')
    xml = fields_xml(before,values,'SIS Dummy')
    validate_fields_xml(xml,before,values,'SIS Dummy')
    n = parse(xml).find('.//LEDGER')
    assert [c.tag for c in n] == ['GUID','EMAIL','LEDGERPHONE','INCOMETAXNUMBER','LEDMAILINGDETAILS.LIST']
    assert '\n'.join(c.text or '' for c in n.findall('.//ADDRESS')) == values['address']
    assert n.findtext('.//APPLICABLEFROM')=='20260401'
    expected = expected_fields(before,values)
    assert fields_preserved(expected,expected,values,'Kerala')
    assert '<OPENINGBALANCE>0</OPENINGBALANCE>' in expected and b'OPENINGBALANCE' not in xml
    assert not fields_preserved(expected,expected.replace('<OPENINGBALANCE>0','<OPENINGBALANCE>1'),values,'Kerala')


@pytest.mark.parametrize('values',[{}, {'name':'Other'}, {'gstin':'32AAACA1234A1Z1'}, {'gst_reg_type':'Regular'},
    {'phone':''},{'email':None},{'email':'bad'},{'pan':'bad'},{'country':'A\rB'}])
def test_unknown_tax_rename_invalid_or_clearing_values_never_build(before,values):
    with pytest.raises(ReadError): fields_xml(before,values,'SIS Dummy')


@pytest.mark.parametrize('field',['email','phone','pan','address','country','state','pincode'])
def test_each_supported_field_writes_only_its_own_storage(before,field):
    values = dict(email='exact@example.invalid',phone='0099',pan='AAACA1234A',address=' First\n\nLast ',country='India',state='Kerala',pincode='001234')
    selected = {field:values[field]}
    xml = fields_xml(before,selected,'SIS Dummy')
    validate_fields_xml(xml,before,selected,'SIS Dummy')
    expected = expected_fields(before,selected)
    assert fields_preserved(expected,expected,selected,selected.get('state',''))
    with pytest.raises(ReadError):
        validate_fields_xml(xml.replace(b'</LEDGER>',b'<OPENINGBALANCE>3</OPENINGBALANCE></LEDGER>'),before,selected,'SIS Dummy')


def test_new_root_projection_must_equal_selected_mailing_value(before):
    expected = expected_fields(before,{'country':'India'})
    actual = expected.replace('</LEDGER>','<COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE></LEDGER>')
    assert fields_preserved(expected,actual,{'country':'India'},'')
    assert not fields_preserved(expected,actual.replace('COUNTRYOFRESIDENCE>India','COUNTRYOFRESIDENCE>Other'),{'country':'India'},'')


def test_selected_mail_fields_do_not_silently_set_effective_dates(before):
    with pytest.raises(ReadError): fields_xml(before,{'address':'New'},'SIS Dummy','20260401')
    node = parse(before.encode()); node.find('LEDMAILINGDETAILS.LIST').clear()
    empty = etree.tostring(node,encoding='unicode')
    expected = expected_fields(empty,{'address':'Exact\n','country':'India'},'20260401')
    xml = fields_xml(empty,{'address':'Exact\n','country':'India'},'SIS Dummy','20260401')
    assert parse(xml).findtext('.//APPLICABLEFROM')=='20260401'
    assert fields_preserved(expected,expected,{'address':'Exact\n','country':'India'},'','20260401')


@pytest.fixture
def native_mailing_update(before):
    """Sanitized 7.0 shapes: typed root address/PIN and independent residence."""
    node = parse(before.encode())
    etree.SubElement(node, 'COUNTRYOFRESIDENCE', TYPE='String')
    original = etree.tostring(node, encoding='unicode')
    values = dict(address=' Exact – address\n\n Last ', pincode='001234', country='United Kingdom')
    actual = parse(original.encode())
    mailing = actual.find('LEDMAILINGDETAILS.LIST')
    mailing.find('ADDRESS.LIST').clear()
    mailing.find('ADDRESS.LIST').set('TYPE', 'String')
    root_address = etree.Element('ADDRESS.LIST', TYPE='String')
    for line in values['address'].split('\n'):
        etree.SubElement(mailing.find('ADDRESS.LIST'), 'ADDRESS').text = line
        etree.SubElement(root_address, 'ADDRESS', TYPE='String').text = line
    actual.insert(0, root_address)
    mailing.find('PINCODE').text = values['pincode']
    mailing.find('COUNTRY').text = values['country']
    etree.SubElement(actual, 'PINCODE', TYPE='String').text = values['pincode']
    actual.find('ALTERID').text = '2'
    return original, values, actual


def test_typed_address_projection_and_unchanged_residence_are_verified(native_mailing_update):
    before, values, actual = native_mailing_update
    expected = expected_fields(before, values)
    assert parse(expected.encode()).findtext('COUNTRYOFRESIDENCE') == ''
    assert fields_preserved(expected, etree.tostring(actual, encoding='unicode'), values, '', native_before=before)
    # Retained pre-repair previews predicted a residence echo that Tally did not
    # make. Recover them from original evidence without rewriting that approval.
    legacy = parse(expected.encode())
    legacy.find('COUNTRYOFRESIDENCE').text = values['country']
    legacy = etree.tostring(legacy, encoding='unicode')
    assert not fields_preserved(legacy, etree.tostring(actual, encoding='unicode'), values, '')
    assert fields_preserved(legacy, etree.tostring(actual, encoding='unicode'), values, '', native_before=before)


@pytest.mark.parametrize('mutation', [
    'address_text', 'address_type', 'address_attribute', 'address_child', 'address_duplicate',
    'root_pin', 'mailing_address', 'mailing_country', 'mailing_pin', 'mailing_date',
    'unselected_state', 'residence_changed', 'residence_removed', 'residence_duplicate',
    'other_field', 'balance', 'guid',
])
def test_mailing_projection_allowances_do_not_hide_content_changes(native_mailing_update, mutation):
    before, values, node = native_mailing_update
    expected = expected_fields(before, values)
    if mutation == 'address_text': node.find('ADDRESS.LIST/ADDRESS').text = values['address'].split('\n')[0].strip()
    if mutation == 'address_type': node.find('ADDRESS.LIST/ADDRESS').set('TYPE', 'Number')
    if mutation == 'address_attribute': node.find('ADDRESS.LIST/ADDRESS').set('EXTRA', 'unexpected')
    if mutation == 'address_child': etree.SubElement(node.find('ADDRESS.LIST/ADDRESS'), 'UNEXPECTED')
    if mutation == 'address_duplicate': node.append(parse(etree.tostring(node.find('ADDRESS.LIST'))))
    if mutation == 'root_pin': node.find('PINCODE').text = '1234'
    if mutation == 'mailing_address': node.find('LEDMAILINGDETAILS.LIST/ADDRESS.LIST/ADDRESS').text = 'Wrong'
    if mutation == 'mailing_country': node.find('LEDMAILINGDETAILS.LIST/COUNTRY').text = 'Other'
    if mutation == 'mailing_pin': node.find('LEDMAILINGDETAILS.LIST/PINCODE').text = '1234'
    if mutation == 'mailing_date': node.find('LEDMAILINGDETAILS.LIST/APPLICABLEFROM').text = '20250401'
    if mutation == 'unselected_state': node.find('LEDMAILINGDETAILS.LIST/STATE').text = 'Changed'
    if mutation == 'residence_changed': node.find('COUNTRYOFRESIDENCE').text = 'Unexpected'
    if mutation == 'residence_removed': node.remove(node.find('COUNTRYOFRESIDENCE'))
    if mutation == 'residence_duplicate': etree.SubElement(node, 'COUNTRYOFRESIDENCE')
    if mutation == 'other_field': node.find('OTHER').text = 'Changed'
    if mutation == 'balance': node.find('OPENINGBALANCE').text = '1'
    if mutation == 'guid': node.find('GUID').text = 'another-ledger'
    assert not fields_preserved(expected, etree.tostring(node, encoding='unicode'), values, '', native_before=before)


def test_unselected_address_projection_is_not_ignored(before):
    values = {'pincode': '001234'}
    expected = expected_fields(before, values)
    actual = parse(expected.encode())
    etree.SubElement(etree.SubElement(actual, 'ADDRESS.LIST', TYPE='String'), 'ADDRESS', TYPE='String').text = 'Unexpected'
    assert not fields_preserved(expected, etree.tostring(actual, encoding='unicode'), values, '', native_before=before)
