from pathlib import Path
from copy import deepcopy
from lxml import etree
import pytest

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally import gst_updates as gst
from innoforia_tally_connector.integrations.tally.state_update import native_snapshot
from innoforia_tally_connector.integrations.tally.party_update import expected_fields, fields_xml, fields_preserved, validate_fields_xml
from innoforia_tally_connector.integrations.tally.xml_codec import parse, records

VALUES = {'gstin': '32AAACA1234A1Z1', 'gst_reg_type': 'Regular'}
OPTIONS = {'gst_effective_date': '20260401', 'gst_state': 'Kerala'}


@pytest.fixture
def before():
    raw = (Path(__file__).parents[2]/'fixtures/tally/state_update_native.xml').read_bytes()
    raw = raw.replace(b'<STATE></STATE>', b'<STATE>Kerala</STATE>').replace(b'<LEDSTATENAME></LEDSTATENAME>', b'<LEDSTATENAME>Kerala</LEDSTATENAME>')
    raw = raw.replace(b'</LEDGER>', b'<LEDGSTREGDETAILS.LIST/></LEDGER>')
    return native_snapshot(raw, '0b212ad8-3be5-45fe-8719-e1a70e240d4c-00000001')


def returned(expected):
    node = parse(expected.encode())
    entry = node.findall(gst.TAG)[-1]
    for tag in gst.FLAGS:
        if entry.find(tag) is None: etree.SubElement(entry,tag).text = 'No'
    return etree.tostring(node,encoding='unicode')


def test_append_tax_xml_is_single_dated_entry_with_no_mailing_or_accounting_write(before):
    raw = fields_xml(before,VALUES,'SIS Dummy',**OPTIONS)
    validate_fields_xml(raw,before,VALUES,'SIS Dummy',**OPTIONS)
    ledger = parse(raw).find('.//LEDGER')
    assert [n.tag for n in ledger] == ['GUID',gst.TAG]
    entry = ledger.find(gst.TAG)
    assert entry.findtext('APPLICABLEFROM') == '20260401'
    assert entry.findtext('STATE') == 'Kerala'
    assert entry.findtext('GSTIN') == VALUES['gstin']
    assert entry.findtext('GSTREGISTRATIONTYPE') == 'Regular'
    assert not set(gst.FLAGS) & {n.tag for n in entry}
    expected = expected_fields(before,VALUES,**OPTIONS)
    assert fields_preserved(expected,returned(expected),VALUES,'Kerala',native_before=before,**OPTIONS)
    with pytest.raises(ReadError):
        validate_fields_xml(raw.replace(b'</LEDGER>',b'<PARTYGSTIN>root-only</PARTYGSTIN></LEDGER>'),before,VALUES,'SIS Dummy',**OPTIONS)


def test_repeat_registration_change_preserves_every_historical_entry(before):
    first = returned(expected_fields(before,VALUES,**OPTIONS))
    values = dict(VALUES,gst_reg_type='Composition')
    options = dict(OPTIONS,gst_effective_date='20260402')
    expected = expected_fields(first,values,**options)
    raw = fields_xml(first,values,'SIS Dummy',**options)
    assert len(parse(raw).findall('.//'+gst.TAG)) == 2
    assert [n.findtext('APPLICABLEFROM') for n in parse(raw).findall('.//'+gst.TAG)] == ['20260401','20260402']
    actual = parse(returned(expected).encode())
    entries = actual.findall(gst.TAG)
    for n in entries: actual.remove(n)
    for n in reversed(entries): actual.append(n)
    assert fields_preserved(expected,etree.tostring(actual,encoding='unicode'),values,'Kerala',native_before=first,**options)
    assert gst.content(actual.findall(gst.TAG)) == values
    actual.find(gst.TAG+'/GSTIN').text = '32AAACA1234A2Z1'
    assert not fields_preserved(expected,etree.tostring(actual,encoding='unicode'),values,'Kerala',native_before=first,**options)


@pytest.mark.parametrize('flag_value', ['', 'No'])
def test_first_tax_entry_accepts_only_verified_empty_or_no_padding(before,flag_value):
    expected=expected_fields(before,VALUES,**OPTIONS)
    n=parse(expected.encode()); entry=n.find(gst.TAG)
    for tag in gst.FLAGS | {'PLACEOFSUPPLY','TRANSPORTERID'}:
        etree.SubElement(entry,tag).text=flag_value if tag in gst.FLAGS else ''
    assert fields_preserved(expected,etree.tostring(n,encoding='unicode'),VALUES,'Kerala',native_before=before,**OPTIONS)
    entry.find('ISTRANSPORTER').text='Yes'
    assert not fields_preserved(expected,etree.tostring(n,encoding='unicode'),VALUES,'Kerala',native_before=before,**OPTIONS)
    entry.find('ISTRANSPORTER').text=flag_value
    entry.find('PLACEOFSUPPLY').text='Kerala'
    assert not fields_preserved(expected,etree.tostring(n,encoding='unicode'),VALUES,'Kerala',native_before=before,**OPTIONS)


@pytest.mark.parametrize('date', [None,'','20260230','99990401','2026011'])
def test_invalid_or_missing_gst_dates_never_build(before,date):
    with pytest.raises(ValueError): fields_xml(before,VALUES,'SIS Dummy',gst_effective_date=date,gst_state='Kerala')


@pytest.mark.parametrize('date', ['20250401','20260401'])
def test_previous_tax_dates_cannot_be_overwritten(before,date):
    first = returned(expected_fields(before,VALUES,**OPTIONS))
    with pytest.raises(ReadError,match='later than every existing'):
        fields_xml(first,VALUES,'SIS Dummy',gst_effective_date=date,gst_state='Kerala')


@pytest.mark.parametrize('values', [
    {'gstin': VALUES['gstin']}, {'gst_reg_type':'Regular'}, dict(VALUES,gstin=''),
    dict(VALUES,gstin=VALUES['gstin'].lower()), dict(VALUES,gst_reg_type='regular'),
    dict(VALUES,gst_reg_type='Unregistered'), dict(VALUES,gst_reg_type='Unknown'),
])
def test_unsupported_source_tax_representations_are_not_translated(before,values):
    with pytest.raises(ReadError): fields_xml(before,values,'SIS Dummy',**OPTIONS)


@pytest.mark.parametrize('mutation', ['missing','undated','duplicate_date','future','unknown_field','duplicate_field','nested'])
def test_unknown_or_ambiguous_gst_history_is_unavailable_and_blocks_writes(before,mutation):
    n = parse(expected_fields(before,VALUES,**OPTIONS).encode())
    entry = n.find(gst.TAG)
    if mutation=='missing': n.remove(entry)
    if mutation=='undated': entry.remove(entry.find('APPLICABLEFROM'))
    if mutation=='duplicate_date': n.append(deepcopy(entry))
    if mutation=='future': entry.find('APPLICABLEFROM').text='99990401'
    if mutation=='unknown_field': etree.SubElement(entry,'UNSUPPORTED').text='value'
    if mutation=='duplicate_field': etree.SubElement(entry,'GSTIN').text=VALUES['gstin']
    if mutation=='nested': etree.SubElement(entry.find('GSTIN'),'VALUE')
    with pytest.raises(ReadError):
        expected_fields(etree.tostring(n,encoding='unicode'),VALUES,gst_effective_date='20260402',gst_state='Kerala')
    wrapped=b'<COLLECTION>'+etree.tostring(n)+b'</COLLECTION>'
    row=records(wrapped,'Ledger')[0]
    if mutation!='missing': assert 'NESTED_GST_UNRESOLVED' in row and 'GST_CONTENT' not in row


@pytest.mark.parametrize('mutation', ['old_gstin','old_flag','new_gstin','new_type','new_date','state','yes_default','balance','mailing','extra_history','root_gstin'])
def test_tax_preservation_does_not_ignore_other_fields_or_history(before,mutation):
    first=returned(expected_fields(before,VALUES,**OPTIONS))
    values=dict(VALUES,gst_reg_type='Composition')
    options=dict(OPTIONS,gst_effective_date='20260402')
    expected=expected_fields(first,values,**options)
    n=parse(returned(expected).encode()); old,new=n.findall(gst.TAG)
    if mutation=='old_gstin': old.find('GSTIN').text='32AAACA1234A2Z1'
    if mutation=='old_flag': old.find('ISCOMMONPARTY').text='Yes'
    if mutation=='new_gstin': new.find('GSTIN').text='32AAACA1234A2Z1'
    if mutation=='new_type': new.find('GSTREGISTRATIONTYPE').text='Regular'
    if mutation=='new_date': new.find('APPLICABLEFROM').text='20260403'
    if mutation=='state': new.find('STATE').text='Delhi'
    if mutation=='yes_default': new.find('ISTRANSPORTER').text='Yes'
    if mutation=='balance': n.find('OPENINGBALANCE').text='100'
    if mutation=='mailing': n.find('LEDMAILINGDETAILS.LIST/STATE').text='Delhi'
    if mutation=='extra_history': n.append(deepcopy(old))
    if mutation=='root_gstin': etree.SubElement(n,'PARTYGSTIN').text='32AAACA1234A2Z1'
    assert not fields_preserved(expected,etree.tostring(n,encoding='unicode'),values,'Kerala',native_before=first,**options)
