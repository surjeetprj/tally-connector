"""Allowlisted linked contact/mailing/PAN alterations; never arbitrary import XML."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import re
from lxml import etree

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.party_changes import PARTY_UPDATE_FIELDS
from innoforia_tally_connector.integrations.tally.dates import xml_date
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally.state_update import mailing_record, preservation_matches, native_shape
from innoforia_tally_connector.integrations.tally import gst_updates

DIRECT = {'email': 'EMAIL', 'phone': 'LEDGERPHONE', 'pan': 'INCOMETAXNUMBER'}
MAILING = {'address': 'ADDRESS.LIST', 'state': 'STATE', 'country': 'COUNTRY', 'pincode': 'PINCODE'}
PROJECTIONS = {'state': ('LEDSTATENAME',), 'country': ('COUNTRYOFRESIDENCE','COUNTRYNAME'), 'pincode': ('PINCODE',), 'address': ('ADDRESS.LIST',)}
ORDER = ['ADDRESS.LIST','APPLICABLEFROM','PINCODE','MAILINGNAME','STATE','COUNTRY']


def validate_values(values):
    if not values or set(values) - set(PARTY_UPDATE_FIELDS):
        raise ReadError('Select supported linked-party fields; rename is not enabled')
    for field,value in values.items():
        if not isinstance(value,str) or not value.strip() or any(ord(c)<32 and c not in '\n\t' for c in value):
            raise ReadError('Only exact nonempty values are supported; no clearing, truncation or control characters')
        if field != 'address' and any(c in value for c in '\n\t'):
            raise ReadError('A scalar field cannot contain line breaks or tabs')
        patterns = {'email': r'[^\s@]+@[^\s@]+\.[^\s@]+', 'pan': r'[A-Za-z]{5}[0-9]{4}[A-Za-z]'}
        if field in patterns and not re.fullmatch(patterns[field],value):
            raise ReadError(f'Invalid {field}; source values are not rewritten')
    if set(values) & set(gst_updates.FIELDS): gst_updates.validate(values)


def replace(root, tag, value):
    nodes = root.findall(tag)
    if len(nodes)>1: raise ReadError('Ambiguous native field')
    old = nodes[0] if nodes else None
    if tag == 'ADDRESS.LIST':
        attrs = dict(old.attrib) if old is not None else {'TYPE':'String'}
        new = etree.Element(tag, **attrs)
        for line in value.split('\n'): etree.SubElement(new,'ADDRESS').text = line
    else:
        if old is not None and len(old): raise ReadError('Unsupported scalar structure')
        new = deepcopy(old) if old is not None else etree.Element(tag)
        new.text = value
    if old is not None:
        root.replace(old,new)
    else: root.append(new)


def expected_fields(snapshot, values, effective_date=None, *, gst_effective_date=None, gst_state=None):
    validate_values(values)
    node = parse(snapshot.encode())
    if node.findtext('PARENT') not in {'Sundry Creditors','Sundry Debtors'}:
        raise ReadError('Linked updates require the confirmed customer/supplier root')
    for field,tag in DIRECT.items():
        if field in values: replace(node,tag,values[field])
    if set(values) & set(MAILING):
        record = mailing_record(node,allow_empty=effective_date is not None)
        if effective_date is not None:
            if len(record) or record.attrib or (record.text or '').strip():
                raise ReadError('An effective date can be chosen only for an empty first mailing entry')
            try: chosen = xml_date(effective_date)
            except ValueError: raise ReadError('Choose a valid effective date (YYYYMMDD)') from None
            if chosen > datetime.now(timezone(timedelta(hours=5,minutes=30))).date():
                raise ReadError('Mailing date cannot be in the future')
            etree.SubElement(record,'APPLICABLEFROM').text = effective_date
        for field,tag in MAILING.items():
            if field in values: replace(record,tag,values[field])
        record[:] = sorted(record,key=lambda n: ORDER.index(n.tag))
        for field,tags in PROJECTIONS.items():
            if field in values:
                for tag in tags:
                    # Mailing Country has its own storage. Native 7.0 evidence
                    # leaves CountryOfResidence unchanged after a mailing edit.
                    if tag != 'COUNTRYOFRESIDENCE' and node.find(tag) is not None:
                        replace(node,tag,values[field])
    elif effective_date is not None:
        raise ReadError('A mailing date requires selected mailing fields')
    if set(values) & set(gst_updates.FIELDS):
        gst_updates.append_entry(node, values, gst_effective_date, gst_state)
    elif gst_effective_date is not None or gst_state is not None:
        raise ReadError('A GST date/State requires selected GST fields')
    return etree.tostring(node,encoding='unicode')


def fields_xml(snapshot, values, company, effective_date=None, *, gst_effective_date=None, gst_state=None):
    before = parse(snapshot.encode())
    expected = parse(expected_fields(snapshot,values,effective_date,gst_effective_date=gst_effective_date,gst_state=gst_state).encode())
    if not company.strip(): raise ReadError('Verified company is required')
    root = etree.Element('ENVELOPE')
    etree.SubElement(etree.SubElement(root,'HEADER'),'TALLYREQUEST').text = 'Import Data'
    data = etree.SubElement(etree.SubElement(root,'BODY'),'IMPORTDATA')
    desc = etree.SubElement(data,'REQUESTDESC')
    etree.SubElement(desc,'REPORTNAME').text = 'All Masters'
    etree.SubElement(etree.SubElement(desc,'STATICVARIABLES'),'SVCURRENTCOMPANY').text = company
    ledger = etree.SubElement(etree.SubElement(etree.SubElement(data,'REQUESTDATA'),'TALLYMESSAGE'),'LEDGER', NAME=before.findtext('NAME'), ACTION='Alter')
    etree.SubElement(ledger,'GUID').text = before.findtext('GUID')
    for field,tag in DIRECT.items():
        if field in values: ledger.append(deepcopy(expected.find(tag)))
    if set(values) & set(MAILING): ledger.append(deepcopy(expected.find('LEDMAILINGDETAILS.LIST')))
    if set(values) & set(gst_updates.FIELDS):
        # Verified 7.0 contract: this collection is replaced by the import.
        # Reconstruct all approved history through its scalar allowlist, then
        # the new row. Never pass through arbitrary native XML instructions.
        for entry in gst_updates.history(expected.findall(gst_updates.TAG)):
            typed = etree.SubElement(ledger, gst_updates.TAG)
            for child in sorted(entry,key=lambda n:gst_updates.ORDER.index(n.tag)):
                scalar = etree.SubElement(typed,child.tag,**dict(child.attrib))
                scalar.text = child.text
    raw = etree.tostring(root,encoding='utf-8',xml_declaration=True)
    if len(raw)>64*1024: raise ReadError('Party update exceeds bounded payload size')
    return raw


def validate_fields_xml(raw, snapshot, values, company, effective_date=None, *, gst_effective_date=None, gst_state=None):
    if etree.tostring(parse(raw),method='c14n') != etree.tostring(parse(fields_xml(snapshot,values,company,effective_date,gst_effective_date=gst_effective_date,gst_state=gst_state)),method='c14n'):
        raise ReadError('Only exact approved field alterations are allowed')


def fields_preserved(approved, actual, values, state, effective_date=None, *, native_before=None, gst_effective_date=None, gst_state=None):
    """Compare values exactly while allowing verified projections, not business defaults."""
    expected, observed = parse(approved.encode()),parse(actual.encode())
    before = parse(native_before.encode()) if native_before is not None else expected
    if before.findtext('GUID') != expected.findtext('GUID'): return False
    if set(values) & set(gst_updates.FIELDS):
        if native_before is None or not gst_updates.verified_history(expected,observed,before,values,gst_effective_date,gst_state):
            return False
    # Root projections may appear at their native export position. Check content
    # before removing them from temporary comparison trees; evidence is immutable.
    for field,tags in {**{f:(tag,) for f,tag in DIRECT.items()}, **PROJECTIONS}.items():
        if field not in values: continue
        for tag in tags:
            left,right = expected.findall(tag),observed.findall(tag)
            if len(left)>1 or len(right)>1 or (left and not right): return False
            if field in DIRECT and len(right)!=1: return False
            permitted = {values[field]}
            if tag == 'COUNTRYOFRESIDENCE':
                original = before.findall(tag)
                if len(original)>1 or (original and not right): return False
                if original:
                    old = original[0]
                    if len(old) or old.attrib not in ({},{'TYPE':'String'}): return False
                    permitted.add(old.text or '')
            for node in right:
                if tag=='ADDRESS.LIST':
                    if node.attrib not in ({},{'TYPE':'String'}) or any(n.tag!='ADDRESS' or n.attrib not in ({},{'TYPE':'String'}) or len(n) for n in node): return False
                    if '\n'.join(n.text or '' for n in node)!=values[field]: return False
                elif len(node) or node.attrib not in ({},{'TYPE':'String'}) or (node.text or '') not in permitted: return False
            if left and right and left[0].attrib!=right[0].attrib and not (not left[0].attrib and right[0].attrib=={'TYPE':'String'}): return False
            for root,nodes in ((expected,left),(observed,right)):
                for node in nodes: root.remove(node)
    if effective_date is not None:
        left,right = expected.findall('LEDMAILINGDETAILS.LIST'),observed.findall('LEDMAILINGDETAILS.LIST')
        if len(left)!=1 or len(right)!=1 or left[0].findtext('APPLICABLEFROM')!=effective_date: return False
        tags = [n.tag for n in right[0]]
        if len(tags)!=len(set(tags)): return False
        for n in right[0][:]:
            if n.tag in {'PINCODE','MAILINGNAME','COUNTRY','STATE'} and left[0].find(n.tag) is None:
                if len(n) or n.attrib or n.text not in (None,''): return False
                right[0].remove(n)
    return preservation_matches(etree.tostring(expected,encoding='unicode'),etree.tostring(observed,encoding='unicode'),state)
