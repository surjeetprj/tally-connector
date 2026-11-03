"""Narrow single-ledger experiment template, based on official master XML."""
from jinja2 import Environment, StrictUndefined

from innoforia_tally_connector.domain.experiments import TestSupplier
from innoforia_tally_connector.integrations.tally.xml_codec import parse

TEMPLATE = Environment(autoescape=True, undefined=StrictUndefined).from_string('''<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>
<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME><STATICVARIABLES>
<SVCURRENTCOMPANY>{{ company }}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>
<REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER ACTION="Create">
<NAME>{{ name }}</NAME><PARENT>{{ parent }}</PARENT><EMAIL>{{ email }}</EMAIL>
</LEDGER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>''')


def supplier_xml(party: TestSupplier, company: str, parent: str):
    if not isinstance(party, TestSupplier) or parent != "Sundry Creditors":
        raise ValueError("Only the controlled supplier under Sundry Creditors is enabled")
    raw = TEMPLATE.render(company=company, parent=parent, name=party.name, email=party.email).encode()
    validate_supplier_xml(raw)
    return raw


def validate_supplier_xml(raw):
    root = parse(raw)
    ledgers = root.findall(".//LEDGER")
    if (root.findtext("HEADER/TALLYREQUEST") != "Import Data"
        or root.findtext(".//REPORTNAME") != "All Masters"
        or not root.findtext(".//SVCURRENTCOMPANY") or len(ledgers) != 1
        or ledgers[0].attrib != {"ACTION": "Create"}
        or [node.tag for node in ledgers[0]] != ["NAME", "PARENT", "EMAIL"]
        or ledgers[0].findtext("PARENT") != "Sundry Creditors"):
        raise ValueError("Only one create-only synthetic supplier import is allowed")
    # Reject extra request data/TDL, alternate actions and concealed sibling masters.
    expected = {"ENVELOPE", "HEADER", "TALLYREQUEST", "BODY", "IMPORTDATA", "REQUESTDESC", "REPORTNAME",
                "STATICVARIABLES", "SVCURRENTCOMPANY", "REQUESTDATA", "TALLYMESSAGE", "LEDGER", "NAME", "PARENT", "EMAIL"}
    if any(node.tag not in expected for node in root.iter()) or len(root.findall(".//TALLYMESSAGE")) != 1:
        raise ValueError("Unexpected elements in controlled import")
    TestSupplier(name=ledgers[0].findtext("NAME"), email=ledgers[0].findtext("EMAIL"))
    expected_root = parse(TEMPLATE.render(company=root.findtext(".//SVCURRENTCOMPANY"),
        name=ledgers[0].findtext("NAME"), parent="Sundry Creditors", email=ledgers[0].findtext("EMAIL")).encode())
    def shape(node):
        return node.tag, sorted(node.attrib.items()), tuple(shape(child) for child in node)
    if shape(root) != shape(expected_root):
        raise ValueError("Controlled import structure differs from the single-ledger template")
