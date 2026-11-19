"""Strict XML; no DTDs, external entities, recovery or business-value rewriting."""
from lxml import etree
from datetime import datetime, timezone, timedelta
import logging
import re

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.dates import xml_date


def mailing_content(nodes):
    """One effective dated record, or explicitly unresolved; never pick a history row."""
    populated = [node for node in nodes if len(node) or (node.text or "").strip()]
    if not populated:
        return {}  # Empty native aggregates mean absent mailing values.
    if len(populated) != 1:
        raise ValueError("Multiple dated mailing records need review")
    node = populated[0]
    tags = [child.tag for child in node]
    if (len(tags) != len(set(tags)) or
        set(tags) - {"APPLICABLEFROM", "MAILINGNAME", "ADDRESS.LIST", "STATE", "COUNTRY", "PINCODE"} or
        any(len(child) for child in node if child.tag != "ADDRESS.LIST")):
        raise ValueError("Unsupported dated mailing structure")
    if xml_date(node.findtext("APPLICABLEFROM")) > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
        raise ValueError("Mailing record is not effective yet")
    content = {field: node.findtext(tag, "") for tag, field in
               (("STATE", "state"), ("COUNTRY", "country"), ("PINCODE", "pincode"))
               if node.find(tag) is not None}
    address = node.find("ADDRESS.LIST")
    if address is not None:
        if any(child.tag != "ADDRESS" or len(child) for child in address):
            raise ValueError("Unsupported mailing address structure")
        content["address"] = "\n".join(child.text or "" for child in address)
    return content


def xml_bytes(raw: bytes):
    # Tally's documented UTF-16 HTTP mode preserves characters that the legacy
    # response replaces with '?'. Observed replies are little-endian without a
    # BOM/declaration; accept those exact XML signatures and BOM-marked UTF-16.
    encoding = ("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else
                "utf-16-le" if raw.startswith(b"<\x00") else
                "utf-16-be" if raw.startswith(b"\x00<") else None)
    if encoding:
        try:
            decoded = raw.decode(encoding, errors="strict")
            declaration = re.match(r'''\A<\?xml\b[^?]*\bencoding\s*=\s*(["'])([^"']+)\1''', decoded)
            if declaration:
                declared = declaration[2].lower()
                endian = "le" if raw.startswith((b"\xff\xfe", b"<\x00")) else "be"
                if declared not in {"utf-16", "utf-16" + endian}:
                    raise ReadError("Tally XML encoding declaration does not match its bytes")
            decoded = re.sub(r'''\A(<\?xml\b[^?]*\bencoding\s*=\s*)(["'])[^"']+\2''',
                             r'\1"UTF-8"', decoded, count=1)
            raw = decoded.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ReadError("Tally returned invalid Unicode XML") from None
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ReadError("Tally returned forbidden XML declarations")
    return raw


def parse(raw: bytes, check_errors=True):
    raw = xml_bytes(raw)
    # Verified on release 6.2: root Group PARENT uses the invalid U+0004
    # sentinel followed by " Primary". Do not strip controls elsewhere.
    raw, count = re.subn(rb'(<PARENT\b[^>]*>)(?:&#0*4;|&#x0*4;) Primary(</PARENT>)',
                         rb'\1Primary\2', raw, flags=re.IGNORECASE)
    if count:
        logging.getLogger(__name__).info("Normalized %d verified Primary sentinels", count)
    try:
        root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True,
                                                   load_dtd=False, recover=False))
    except etree.XMLSyntaxError:
        raise ReadError("Tally returned invalid XML") from None
    if root.getroottree().docinfo.doctype:
        raise ReadError("Tally returned forbidden XML declarations")
    if check_errors and any((n.text or "").strip() for n in root.iter() if n.tag in {"LINEERROR", "ERROR"}):
        raise ReadError("Tally rejected the read request")
    if check_errors and root.findtext(".//STATUS") == "0":
        raise ReadError("Tally rejected the read request")
    return root


def unicode_request(raw: bytes) -> bytes:
    """Lossless wire encoding after the caller's export/typed-import guards."""
    return etree.tostring(parse(raw), encoding="UTF-16", xml_declaration=True)


def records(raw: bytes, entity: str) -> list[dict[str, str]]:
    root = parse(raw)
    collections = root.findall(".//COLLECTION")
    if root.tag == "COLLECTION":
        collections = [root]
    if not collections:
        raise ReadError("Tally collection is missing")
    result = []
    for coll in collections:
        for node in coll.findall(entity.upper()):
            row = {child.tag: child.text or "" for child in node if len(child) == 0}
            addresses = node.findall("ADDRESS.LIST")
            if len(addresses) > 1 or (addresses and any(child.tag != "ADDRESS" or len(child) for child in addresses[0])):
                row["ADDRESS_UNRESOLVED"] = "Mailing structure requires explicit exclusion or further evidence"
            elif addresses:
                row["ADDRESS_LINES"] = tuple(child.text or "" for child in addresses[0].findall("ADDRESS"))
            mailings = node.findall("LEDMAILINGDETAILS.LIST")
            if mailings:
                try:
                    row["MAILING_CONTENT"] = mailing_content(mailings)
                    populated = [part for part in mailings if len(part) or (part.text or "").strip()]
                    if populated:
                        row["MAILING_APPLICABLE_FROM"] = populated[0].findtext("APPLICABLEFROM")
                except ValueError:
                    row["MAILING_UNRESOLVED"] = "Dated mailing records require further evidence"
            if node.find("LEDGSTREGDETAILS.LIST") is not None or node.find("LEDGSTREGDETAILS") is not None:
                row["NESTED_GST_UNRESOLVED"] = "Yes"
            row["NAME"] = row.get("NAME") or node.get("NAME", "")
            result.append(row)
    return result
