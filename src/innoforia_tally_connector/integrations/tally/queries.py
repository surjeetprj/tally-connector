"""Export-only collection requests. No import XML is supported here."""
import xml.etree.ElementTree as ET
import re


def collection(entity: str, company: str | None = None, guid: str | None = None) -> bytes:
    if entity not in {"Company", "Group", "Ledger"}:
        raise ValueError("Unsupported read collection")
    root = ET.Element("ENVELOPE")
    header = ET.SubElement(root, "HEADER")
    name = f"ConnectorRead{entity}"
    for tag, value in (("VERSION", "1"), ("TALLYREQUEST", "Export"),
                       ("TYPE", "Collection"), ("ID", name)):
        ET.SubElement(header, tag).text = value
    desc = ET.SubElement(ET.SubElement(root, "BODY"), "DESC")
    static = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(static, "SVEXPORTFORMAT").text = "$$SysName:XML"
    if company is not None:
        ET.SubElement(static, "SVCURRENTCOMPANY").text = company
    msg = ET.SubElement(ET.SubElement(desc, "TDL"), "TDLMESSAGE")
    coll = ET.SubElement(msg, "COLLECTION", NAME=name, ISMODIFY="No")
    ET.SubElement(coll, "TYPE").text = entity
    fields = ["Name", "GUID", "MasterID", "AlterID"]
    if entity != "Company":
        fields.append("Parent")
    if entity == "Ledger":
        fields += ["Email", "LedgerPhone", "LedgerMobile", "Pincode", "PartyGSTIN", "Address", "LedStateName"]
    for field in fields:
        ET.SubElement(coll, "FETCH").text = field
    if guid is not None:
        if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?:-[0-9a-fA-F]{8})?", guid):
            raise ValueError("Invalid Tally GUID format")
        ET.SubElement(coll, "FILTER").text = "ConnectorGUID"
        ET.SubElement(msg, "SYSTEM", TYPE="Formulae", NAME="ConnectorGUID").text = f'$GUID = "{guid}"'
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
