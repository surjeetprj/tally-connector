"""Append a dated GST registration while preserving every earlier record."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import re
from lxml import etree

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.dates import xml_date
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally.state_update import native_shape, mailing_record

TAG = 'LEDGSTREGDETAILS.LIST'
FIELDS = {'gstin': 'GSTIN', 'gst_reg_type': 'GSTREGISTRATIONTYPE'}
REGISTRATION_TYPES = {'Regular', 'Composition'}
FLAGS = {'ISOTHTERRITORYASSESSEE', 'CONSIDERPURCHASEFOREXPORT', 'ISTRANSPORTER', 'ISCOMMONPARTY'}
ORDER = ['APPLICABLEFROM', 'GSTREGISTRATIONTYPE', 'TRANSPORTERID', 'STATE', 'PLACEOFSUPPLY', 'GSTIN',
         'ISOTHTERRITORYASSESSEE', 'CONSIDERPURCHASEFOREXPORT', 'ISTRANSPORTER', 'ISCOMMONPARTY']


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def history(nodes):
    if not nodes or len(nodes) > 100:
        raise ReadError('GST history is unavailable or exceeds the supported bound')
    populated = [n for n in nodes if len(n) or (n.text or '').strip()]
    if not populated:
        if len(nodes) != 1 or nodes[0].attrib:
            raise ReadError('Ambiguous empty GST history')
        return []
    if len(populated) != len(nodes):
        raise ReadError('GST history mixes empty and populated entries')
    dates = []
    for node in populated:
        tags = [n.tag for n in node]
        if node.attrib or len(tags) != len(set(tags)) or set(tags) - set(ORDER):
            raise ReadError('Unsupported or duplicate GST history fields')
        if any(len(n) or n.attrib not in ({}, {'TYPE': 'String'}) for n in node):
            raise ReadError('Unsupported GST history scalar')
        try: date = xml_date(node.findtext('APPLICABLEFROM'))
        except (TypeError, ValueError): raise ReadError('GST history needs valid dated entries') from None
        if date > today(): raise ReadError('Future GST history requires review')
        dates.append(date)
    if len(dates) != len(set(dates)):
        raise ReadError('Duplicate GST effective dates require review')
    return sorted(populated, key=lambda n: n.findtext('APPLICABLEFROM'))


def content(nodes):
    rows = history(nodes)
    if not rows: return {'gstin': '', 'gst_reg_type': ''}
    last = rows[-1]
    return {field: last.findtext(tag, '') for field, tag in FIELDS.items()}


def validate(values):
    if not set(FIELDS) <= set(values):
        raise ReadError('Select GSTIN and registration type together; no guessed tax defaults')
    if not isinstance(values['gstin'], str) or not re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]', values['gstin']):
        raise ReadError('GSTIN must be the exact supported 15-character uppercase source value')
    if values['gst_reg_type'] not in REGISTRATION_TYPES:
        raise ReadError('Supported GST registration types are exactly Regular and Composition; source values are not translated')


def append_entry(node, values, effective_date, gst_state):
    validate(values)
    try: chosen = xml_date(effective_date)
    except (TypeError, ValueError): raise ReadError('Choose a GST effective date as YYYYMMDD') from None
    if chosen > today(): raise ReadError('GST effective date cannot be in the future')
    if not gst_state or not gst_state.strip() or any(ord(c) < 32 for c in gst_state):
        raise ReadError('GST updates require an explicitly approved State')
    rows = history(node.findall(TAG))
    if rows and effective_date <= rows[-1].findtext('APPLICABLEFROM'):
        raise ReadError('Choose a GST date later than every existing entry; historical rows cannot be overwritten')
    if rows:
        entry = deepcopy(rows[-1])
        old_state = entry.findtext('STATE')
        if old_state and old_state != gst_state:
            raise ReadError('GST State differs from the reviewed State; tax-State changes need separate review')
    else:
        entry = etree.Element(TAG)
        # Initial State is the exact, separately approved source/destination
        # mailing State. No tax rate, supply place or boolean default is invented.
        mailing = mailing_record(node)
        if mailing.findtext('STATE') != gst_state or mailing.findtext('COUNTRY') != 'India':
            raise ReadError('First GST entry needs matching populated Indian mailing State/Country')
        for old in node.findall(TAG): node.remove(old)
    for tag, value in {'APPLICABLEFROM': effective_date, 'GSTREGISTRATIONTYPE': values['gst_reg_type'],
                       'STATE': gst_state, 'GSTIN': values['gstin']}.items():
        scalar = entry.find(tag)
        if scalar is None: scalar = etree.SubElement(entry, tag)
        scalar.text = value
    entry[:] = sorted(entry, key=lambda n: ORDER.index(n.tag))
    node.append(entry)


def verified_history(expected, observed, before, values, effective_date, gst_state):
    """Remove only fully checked tax nodes from temporary comparison trees."""
    try:
        validate(values)
        old = history(before.findall(TAG))
        wanted = history(expected.findall(TAG))
        actual = history(observed.findall(TAG))
    except (ReadError, ValueError): return False
    old_by_date = {n.findtext('APPLICABLEFROM'): n for n in old}
    left = {n.findtext('APPLICABLEFROM'): n for n in wanted}
    right = {n.findtext('APPLICABLEFROM'): n for n in actual}
    if not effective_date or set(left) != set(right) or set(left) != set(old_by_date) | {effective_date}:
        return False
    if effective_date in old_by_date: return False
    for date, row in old_by_date.items():
        if native_shape(etree.tostring(row, encoding='unicode')) != native_shape(etree.tostring(right[date], encoding='unicode')):
            return False
        if native_shape(etree.tostring(row, encoding='unicode')) != native_shape(etree.tostring(left[date], encoding='unicode')):
            return False
    new, returned = left[effective_date], deepcopy(right[effective_date])
    if any(returned.findtext(tag) != value for tag, value in
           {'GSTIN': values['gstin'], 'GSTREGISTRATIONTYPE': values['gst_reg_type'], 'STATE': gst_state}.items()):
        return False
    # Native 7.0 pads a first entry with empty optional scalar slots; supplied
    # native examples also use No flags. These are verified only for newly
    # omitted fields; existing flags/settings and earlier rows remain exact.
    for scalar in returned[:]:
        original = new.find(scalar.tag)
        padding = (scalar.tag in FLAGS and scalar.text in (None,'','No')
                   or scalar.tag in {'TRANSPORTERID','PLACEOFSUPPLY'} and scalar.text in (None,''))
        if original is None and padding and not scalar.attrib:
            returned.remove(scalar)
        elif original is not None and not original.attrib and scalar.attrib == {'TYPE': 'String'}:
            scalar.attrib.clear()
    returned[:] = sorted(returned, key=lambda n: ORDER.index(n.tag))
    if native_shape(etree.tostring(new, encoding='unicode')) != native_shape(etree.tostring(returned, encoding='unicode')):
        return False
    projections = {'PARTYGSTIN': values['gstin'], 'GSTREGISTRATIONTYPE': values['gst_reg_type'], 'STATENAME': gst_state}
    for tag, selected in projections.items():
        prior, a, b = before.findall(tag), expected.findall(tag), observed.findall(tag)
        if max(len(prior), len(a), len(b)) > 1 or (prior and not b): return False
        permitted = {selected}
        if prior: permitted.add(prior[0].text or '')
        for n in b:
            if len(n) or n.attrib not in ({}, {'TYPE': 'String'}) or (n.text or '') not in permitted: return False
        if prior and b and prior[0].attrib != b[0].attrib and not (not prior[0].attrib and b[0].attrib == {'TYPE':'String'}): return False
        for root, nodes in ((expected, a), (observed, b)):
            for n in nodes: root.remove(n)
    for root in (expected, observed):
        for row in root.findall(TAG): root.remove(row)
    return True
