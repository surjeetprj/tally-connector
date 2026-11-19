"""Typed single-ledger contact, mailing, PAN and dated GST creation XML."""
import xml.etree.ElementTree as ET
import re
from innoforia_tally_connector.integrations.tally.gst_updates import validate as validate_gst
from innoforia_tally_connector.domain.masters import PartyType
from innoforia_tally_connector.domain.party_transfer import PartyDraft
from innoforia_tally_connector.integrations.tally.xml_codec import parse
from innoforia_tally_connector.integrations.tally.dates import xml_date

TAGS = {"email": "EMAIL", "phone": "LEDGERPHONE", "pan": "INCOMETAXNUMBER"}
MAILING_TAGS = {"pincode": "PINCODE", "state": "STATE", "country": "COUNTRY"}
MAILING_FIELDS = frozenset({"address", *MAILING_TAGS})
ROOTS = {PartyType.CUSTOMER: "Sundry Debtors", PartyType.SUPPLIER: "Sundry Creditors"}


def validate(draft):
    errors = {}
    for field in draft.model_fields_set - {"party_type"}:
        value = getattr(draft, field)
        if value is None:
            errors[field] = "XML null representation unavailable; explicitly exclude"
        elif any(ord(char) < 32 and char not in "\n\t" for char in value):
            errors[field] = "Value contains unsupported XML/control or carriage-return representation"
    if 'pan' in draft.model_fields_set and (not isinstance(draft.pan,str) or not re.fullmatch(r'[A-Za-z]{5}[0-9]{4}[A-Za-z]',draft.pan)):
        errors['pan'] = 'PAN must retain its supported ten-character source representation'
    if draft.model_fields_set & {'gstin','gst_reg_type'}:
        try: validate_gst({'gstin':draft.gstin,'gst_reg_type':draft.gst_reg_type})
        except ValueError as error:
            errors.update({f:str(error) for f in ('gstin','gst_reg_type') if f in draft.model_fields_set})
        if not isinstance(draft.state,str) or not draft.state.strip() or draft.country != 'India':
            errors.update({f:'Dated GST creation requires populated source State and country India' for f in ('gstin','gst_reg_type') if f in draft.model_fields_set})
    return errors


def party_xml(draft, company, parent, applicable_from=None):
    if not isinstance(draft, PartyDraft) or validate(draft) or parent != ROOTS[draft.party_type] or not company.strip():
        raise ValueError("Invalid typed party or destination group")
    mailing_required = bool(draft.model_fields_set & MAILING_FIELDS)
    if mailing_required:
        xml_date(applicable_from)  # Must come from the verified company preflight.
    elif applicable_from is not None:
        raise ValueError("Mailing date without mailing fields is not allowed")
    root = ET.Element("ENVELOPE")
    ET.SubElement(ET.SubElement(root, "HEADER"), "TALLYREQUEST").text = "Import Data"
    data = ET.SubElement(ET.SubElement(root, "BODY"), "IMPORTDATA")
    desc = ET.SubElement(data, "REQUESTDESC")
    ET.SubElement(desc, "REPORTNAME").text = "All Masters"
    ET.SubElement(ET.SubElement(desc, "STATICVARIABLES"), "SVCURRENTCOMPANY").text = company
    ledger = ET.SubElement(ET.SubElement(ET.SubElement(data, "REQUESTDATA"), "TALLYMESSAGE"), "LEDGER", ACTION="Create")
    ET.SubElement(ledger, "NAME").text = draft.name
    ET.SubElement(ledger, "PARENT").text = parent
    for field, tag in TAGS.items():
        if field in draft.model_fields_set:
            ET.SubElement(ledger, tag).text = getattr(draft, field)
    if mailing_required:
        mailing = ET.SubElement(ledger, "LEDMAILINGDETAILS.LIST")
        if "address" in draft.model_fields_set:
            lines = ET.SubElement(mailing, "ADDRESS.LIST", TYPE="String")
            for line in draft.address.split("\n"):
                ET.SubElement(lines, "ADDRESS").text = line
        ET.SubElement(mailing, "APPLICABLEFROM").text = applicable_from
        for field, tag in MAILING_TAGS.items():
            if field in draft.model_fields_set:
                ET.SubElement(mailing, tag).text = getattr(draft, field)
    if draft.model_fields_set & {'gstin','gst_reg_type'}:
        xml_date(applicable_from)
        tax = ET.SubElement(ledger,'LEDGSTREGDETAILS.LIST')
        for tag,value in (('APPLICABLEFROM',applicable_from),('GSTREGISTRATIONTYPE',draft.gst_reg_type),('STATE',draft.state),('GSTIN',draft.gstin)):
            ET.SubElement(tax,tag).text = value
    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(raw) > 64 * 1024:
        raise ValueError("Party XML exceeds the bounded request size")
    return raw


def validate_party_xml(raw):
    root = parse(raw)
    ledgers = root.findall(".//LEDGER")
    if len(ledgers) != 1 or ledgers[0].attrib != {"ACTION": "Create"}:
        raise ValueError("Exactly one create-only ledger is allowed")
    ledger = ledgers[0]
    parent = ledger.findtext("PARENT")
    kinds = [kind for kind, name in ROOTS.items() if parent == name]
    if len(kinds) != 1:
        raise ValueError("Only the confirmed customer/supplier roots are allowed")
    values = {"name": ledger.findtext("NAME"), "party_type": kinds[0]}
    for field, tag in TAGS.items():
        if ledger.find(tag) is not None:
            values[field] = ledger.findtext(tag, "")
    mailing = ledger.find("LEDMAILINGDETAILS.LIST")
    applicable_from = None
    if mailing is not None:
        applicable_from = mailing.findtext("APPLICABLEFROM")
        for field, tag in MAILING_TAGS.items():
            if mailing.find(tag) is not None:
                values[field] = mailing.findtext(tag, "")
        address = mailing.find("ADDRESS.LIST")
        if address is not None:
            values["address"] = "\n".join(node.text or "" for node in address.findall("ADDRESS"))
    tax = ledger.find('LEDGSTREGDETAILS.LIST')
    if tax is not None:
        if tax.findtext('APPLICABLEFROM') != applicable_from or tax.findtext('STATE') != values.get('state'):
            raise ValueError('GST date/State differs from the approved mailing context')
        values.update(gstin=tax.findtext('GSTIN',''),gst_reg_type=tax.findtext('GSTREGISTRATIONTYPE',''))
    expected = parse(party_xml(PartyDraft(**values), root.findtext(".//SVCURRENTCOMPANY", ""), parent, applicable_from))
    def shape(node):
        return node.tag, sorted(node.attrib.items()), (node.text or "").strip() if len(node) else node.text or "", tuple(shape(child) for child in node)
    if shape(root) != shape(expected):
        raise ValueError("Unexpected fields, duplicate containers or arbitrary import XML")
