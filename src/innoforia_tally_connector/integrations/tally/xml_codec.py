"""Strict XML; no DTDs, external entities, recovery or business-value rewriting."""
from lxml import etree
import logging
import re

from innoforia_tally_connector.domain.errors import ReadError


def parse(raw: bytes):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ReadError("Tally returned forbidden XML declarations")
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
    if any((n.text or "").strip() for n in root.iter() if n.tag in {"LINEERROR", "ERROR"}):
        raise ReadError("Tally rejected the read request")
    if root.findtext(".//STATUS") == "0":
        raise ReadError("Tally rejected the read request")
    return root


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
            row["NAME"] = row.get("NAME") or node.get("NAME", "")
            result.append(row)
    return result
