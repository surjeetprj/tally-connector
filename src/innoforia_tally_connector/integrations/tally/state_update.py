"""Typed supplier State alteration; native snapshots are evidence, never replay payloads."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import re
from lxml import etree
from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.experiments import UncertainWrite
from innoforia_tally_connector.integrations.tally.xml_codec import parse, xml_bytes
from innoforia_tally_connector.integrations.tally.dates import xml_date

# Observed only in full native export, 18 Nov 2026. Preserve these forbidden
# XML reference tokens as opaque evidence; never strip them or import them.
SENTINEL = "__CONNECTOR_NATIVE_U0004__"
NATIVE_TAGS = ("TAXCLASSIFICATIONNAME", "GSTTYPE", "APPROPRIATEFOR", "PAYTYPE", "PAYSTATTYPE",
               "SERVICECATEGORY", "EXCISEDUTYTYPE", "EXCISENATUREOFPURCHASE", "LEDGERFBTCATEGORY")


def native_snapshot(raw, guid):
    if len(raw) > 1024 * 1024:
        raise ReadError("Controlled ledger snapshot exceeds 1 MiB")
    raw = xml_bytes(raw)
    if SENTINEL.encode() in raw:
        raise ReadError("Native evidence contains a reserved token")
    tags = "|".join(NATIVE_TAGS)
    raw = re.sub(rb'(<(?:' + tags.encode() + rb')\b[^>]*>)&#4;', lambda m: m[1] + SENTINEL.encode(), raw)
    root = parse(raw)
    ledgers = root.findall(".//COLLECTION/LEDGER") if root.tag != "COLLECTION" else root.findall("LEDGER")
    if len(ledgers) != 1 or ledgers[0].findtext("GUID") != guid:
        raise ReadError("Native ledger GUID is missing/ambiguous; no name fallback")
    node = ledgers[0]
    if not node.findall("NAME") and node.get("NAME"):
        # Native FETCH * exports the name as an attribute, unlike explicit Fetch.
        etree.SubElement(node, "NAME").text = node.get("NAME")
    elif node.get("NAME") and node.findtext("NAME") != node.get("NAME"):
        raise ReadError("Conflicting native ledger names")
    for tag in ("GUID", "MASTERID", "ALTERID", "NAME", "PARENT"):
        if len(node.findall(tag)) != 1 or not node.findtext(tag, "").strip():
            raise ReadError("Native ledger identity/version/classification is incomplete")
    # Saved locally in the approval, never logged or committed as customer data.
    return etree.tostring(node, encoding="unicode")


def mailing_record(node):
    records = node.findall("LEDMAILINGDETAILS.LIST")
    if len(records) != 1:
        raise ReadError("State updates require exactly one existing dated mailing record")
    record = records[0]
    allowed = {"ADDRESS.LIST", "APPLICABLEFROM", "PINCODE", "MAILINGNAME", "STATE", "COUNTRY"}
    tags = [n.tag for n in record]
    if set(tags) - allowed or len(tags) != len(set(tags)) or SENTINEL in etree.tostring(record, encoding="unicode"):
        raise ReadError("Unsupported mailing structure; no state update prepared")
    for child in record:
        if child.tag == "ADDRESS.LIST":
            if child.attrib not in ({}, {"TYPE": "String"}) or any(n.tag != "ADDRESS" or len(n) or n.attrib for n in child):
                raise ReadError("Unsupported mailing address; cannot preserve it")
        elif len(child) or child.attrib:
            raise ReadError("Unsupported mailing scalar")
    if xml_date(record.findtext("APPLICABLEFROM")) > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
        raise ReadError("Future mailing dates are not supported for State updates")
    return record


def expected_native(snapshot, state):
    if not isinstance(state, str) or not state.strip() or any(ord(c) < 32 for c in state) or len(state) > 100:
        raise ReadError("State must be an exact nonempty supported string")
    node = parse(snapshot.encode())
    record = mailing_record(node)
    old = record.find("STATE")
    if old is None:
        old = etree.SubElement(record, "STATE")
    old.text = state
    # Native projection of the same mailing State, if exported explicitly.
    for derived in node.findall("LEDSTATENAME"):
        derived.text = state
    return etree.tostring(node, encoding="unicode")


def native_shape(snapshot, *, ignore_version=False):
    node = parse(snapshot.encode())
    if ignore_version:
        for n in node.findall("ALTERID"): node.remove(n)
    def shape(n):
        if not isinstance(n.tag, str): raise ReadError("Unsupported native snapshot node")
        return (n.tag, sorted(n.attrib.items()), (n.text or "").strip() if len(n) else n.text or "", [shape(c) for c in n])
    return json.dumps(shape(node), ensure_ascii=False, separators=(",", ":"))


def preservation_matches(approved_expected, actual, state):
    """Account only for observed derived State/import identity representations.

    Do not rewrite approval evidence or ignore arbitrary metadata differences.
    RemoteAltGUID's only permitted new value is the SAME approved object's GUID,
    and only when its existing scalar was empty. All other data stays exact.
    """
    expected, observed = parse(approved_expected.encode()), parse(actual.encode())
    guid = expected.findtext("GUID")
    if not guid or observed.findtext("GUID") != guid:
        return False
    projections = [root.findall("LEDSTATENAME") for root in (expected, observed)]
    if any(len(nodes) > 1 for nodes in projections) or (projections[0] and not projections[1]):
        return False
    if projections[0] and projections[1]:
        old_attrs, new_attrs = projections[0][0].attrib, projections[1][0].attrib
        if old_attrs != new_attrs and not (old_attrs == {} and new_attrs == {"TYPE": "String"}):
            return False
    for root, nodes in zip((expected, observed), projections):
        for node in nodes:
            if len(node) or node.attrib not in ({}, {"TYPE": "String"}) or (node.text or "") != state:
                return False
            root.remove(node)
    before_ids, after_ids = expected.findall("REMOTEALTGUID"), observed.findall("REMOTEALTGUID")
    if len(before_ids) > 1 or len(after_ids) > 1:
        return False
    if len(before_ids) == len(after_ids) == 1:
        old, new = before_ids[0], after_ids[0]
        if not len(old) and not len(new) and old.attrib == new.attrib and not (old.text or "") and new.text == guid:
            new.text = old.text
    return native_shape(etree.tostring(expected, encoding="unicode"), ignore_version=True) == native_shape(
        etree.tostring(observed, encoding="unicode"), ignore_version=True)


def state_xml(snapshot, state, company):
    before = parse(snapshot.encode())
    if before.findtext("PARENT") != "Sundry Creditors":
        raise ReadError("State updates currently support the supplier root only")
    after = parse(expected_native(snapshot, state).encode())
    if not company.strip() or SENTINEL in company:
        raise ReadError("Verified company is required")
    root = etree.Element("ENVELOPE")
    etree.SubElement(etree.SubElement(root, "HEADER"), "TALLYREQUEST").text = "Import Data"
    data = etree.SubElement(etree.SubElement(root, "BODY"), "IMPORTDATA")
    desc = etree.SubElement(data, "REQUESTDESC")
    etree.SubElement(desc, "REPORTNAME").text = "All Masters"
    etree.SubElement(etree.SubElement(desc, "STATICVARIABLES"), "SVCURRENTCOMPANY").text = company
    ledger = etree.SubElement(etree.SubElement(etree.SubElement(data, "REQUESTDATA"), "TALLYMESSAGE"), "LEDGER",
        NAME=before.findtext("NAME"), ACTION="Alter")
    # Documented name selector, resolved/rechecked by GUID under the gateway lock;
    # GUID is additionally supplied. This does not claim remote compare-and-swap.
    etree.SubElement(ledger, "GUID").text = before.findtext("GUID")
    ledger.append(deepcopy(mailing_record(after)))
    raw = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(raw) > 64 * 1024:
        raise ReadError("State update exceeds bounded payload size")
    return raw


def validate_state_xml(raw, snapshot, state, company):
    actual = parse(raw)
    expected = parse(state_xml(snapshot, state, company))
    if etree.tostring(actual, method="c14n") != etree.tostring(expected, method="c14n"):
        raise ReadError("Only the exact typed state alteration is allowed")


def state_receipt(raw, target):
    try:
        node = parse(raw, check_errors=False)
        if len(node.findall(".//STATUS")) > 1: raise ValueError("Duplicate status")
        for tag, expected in {"CREATED": "0", "ALTERED": "1", "ERRORS": "0"}.items():
            if len(node.findall(f".//{tag}")) != 1 or node.findtext(f".//{tag}") != expected:
                raise ValueError("Unexpected state update receipt")
        for tag in ("DELETED", "COMBINED", "IGNORED", "CANCELLED", "EXCEPTIONS"):
            if len(node.findall(f".//{tag}")) > 1 or node.findtext(f".//{tag}", "0") != "0": raise ValueError("Unexpected receipt")
        if any((n.text or "").strip() for n in node.iter() if n.tag in {"LINEERROR", "LASTIMPORTERROR", "ERROR"}) or node.findtext(".//STATUS") == "0":
            raise ValueError("Update not acknowledged")
    except (ValueError, ReadError):
        raise UncertainWrite("State update response is not verified; reconcile the known GUID, never send again", target) from None
    return target
