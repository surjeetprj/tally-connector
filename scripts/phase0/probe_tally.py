"""Sequential, read-only localhost Tally capability probe; no import requests."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def envelope(kind: str, name: str) -> tuple[ET.Element, ET.Element]:
    root = ET.Element("ENVELOPE")
    header = ET.SubElement(root, "HEADER")
    for tag, value in (("VERSION", "1"), ("TALLYREQUEST", "Export"),
                       ("TYPE", kind), ("ID", name)):
        ET.SubElement(header, tag).text = value
    desc = ET.SubElement(ET.SubElement(root, "BODY"), "DESC")
    static = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(static, "SVEXPORTFORMAT").text = "$$SysName:XML"
    return root, desc


def company_request() -> bytes:
    root, desc = envelope("Collection", "ConnectorPhase0Companies")
    msg = ET.SubElement(ET.SubElement(desc, "TDL"), "TDLMESSAGE")
    collection = ET.SubElement(msg, "COLLECTION", NAME="ConnectorPhase0Companies",
                               ISMODIFY="No", ISINITIALIZE="Yes")
    ET.SubElement(collection, "TYPE").text = "Company"
    for field in ("Name", "GUID", "Number", "CompanyNumber"):
        ET.SubElement(collection, "NATIVEMETHOD").text = field
        ET.SubElement(collection, "FETCH").text = field
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def about_request() -> bytes:
    root, _ = envelope("Data", "Product AboutPage")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def scoped_request(company: str, entity: str, after: int | None = None) -> bytes:
    name = f"ConnectorPhase0{entity}"
    root, desc = envelope("Collection", name)
    static = desc.find("STATICVARIABLES")
    ET.SubElement(static, "SVCURRENTCOMPANY").text = company
    msg = ET.SubElement(ET.SubElement(desc, "TDL"), "TDLMESSAGE")
    collection = ET.SubElement(msg, "COLLECTION", NAME=name, ISMODIFY="No",
                               ISINITIALIZE="Yes")
    ET.SubElement(collection, "TYPE").text = entity
    fields = ("Name", "GUID", "AlterID") if entity != "Voucher" else (
        "GUID", "MasterID", "AlterID", "Date")
    for field in fields:
        ET.SubElement(collection, "FETCH").text = field
    if after is not None:
        ET.SubElement(collection, "FILTER").text = "ConnectorPhase0AlterFilter"
        ET.SubElement(msg, "SYSTEM", NAME="ConnectorPhase0AlterFilter",
                      TYPE="Formulae").text = f"$AlterID > {after}"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def project_records(root: ET.Element, entity: str) -> dict:
    records = [node for collection in root.iter() if collection.tag.upper() == "COLLECTION"
               for node in collection if node.tag.upper() == entity.upper()]
    ids = []
    guid_count = 0
    for node in records:
        fields = {child.tag.upper(): (child.text or "").strip() for child in node}
        guid_count += bool(fields.get("GUID"))
        if fields.get("ALTERID", "").isdigit():
            ids.append(int(fields["ALTERID"]))
    return {"entity": entity, "record_count": len(records),
            "records_with_guid": guid_count, "records_with_numeric_alter_id": len(ids),
            "min_alter_id": min(ids) if ids else None,
            "max_alter_id": max(ids) if ids else None,
            "record_names_dates_and_identities": "not retained"}


def project_companies(root: ET.Element, target: str) -> dict:
    companies = [node for collection in root.iter() if collection.tag.upper() == "COLLECTION"
                 for node in collection if node.tag.upper() == "COMPANY"]
    matches = []
    for node in companies:
        fields = {child.tag.upper(): (child.text or "").strip() for child in node}
        name = fields.get("NAME") or node.attrib.get("NAME", "")
        if name == target:
            matches.append({key: value for key, value in fields.items()
                            if key in {"NAME", "GUID", "NUMBER", "COMPANYNUMBER"}})
            matches[-1]["NAME"] = name
    return {"company_count": len(companies), "target_company": target,
            "target_matches": matches, "other_company_details": "not retained"}


def project_about(root: ET.Element) -> dict:
    # Report values may contain serials, user names and paths: retain only a
    # strict allowlist of product/version labels, never the entire report.
    allowed = {"product", "product name", "version", "release", "edition", "mode"}
    result = []
    label = ""
    for node in root.iter():
        tag = node.tag.upper()
        value = " ".join((node.text or "").split())
        if tag == "ABOUTPAGEPROMPT":
            label = value.rstrip(":").strip()
        elif tag == "ABOUTPAGEINFO" and label.lower() in allowed:
            result.append({"label": label, "value": value})
            label = ""
    return {"product_fields": result,
            "note": "Unrecognized fields, license/serial, users and paths not retained"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", default="SIS Dummy")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[2] / "docs/api/tally/evidence"
    output.mkdir(parents=True, exist_ok=True)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    results = []
    probes = [
        ("companies", company_request(), lambda root: project_companies(root, args.company)),
        ("product-about", about_request(), project_about),
    ]
    # Export-only experiments; execute only after exactly one company GUID matched.
    for name, payload, project in probes:
        request_path = output / f"{name}.request.xml"
        request_path.write_bytes(payload)
        result = {"probe": name, "request": request_path.name,
                  "utc": datetime.now(timezone.utc).isoformat(),
                  "endpoint": "http://localhost:9000", "read_only": True}
        start = time.monotonic()
        try:
            request = Request("http://localhost:9000", data=payload, method="POST",
                              headers={"Content-Type": "application/xml",
                                       "Accept": "application/xml"})
            with opener.open(request, timeout=15) as response:
                raw = response.read(2_000_001)
                result["http_status"] = response.status
            if len(raw) > 2_000_000:
                raise ValueError("Response exceeds probe size limit")
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("DTD/entity declarations are not accepted")
            root = ET.fromstring(raw)
            result["response_sha256"] = hashlib.sha256(raw).hexdigest()
            result["response_bytes"] = len(raw)
            result["root_tag"] = root.tag
            result["error_tags_present"] = any(
                node.tag.upper() in {"LINEERROR", "ERROR", "LASTIMPORTERROR"}
                and (node.text or "").strip() for node in root.iter())
            result["observed"] = project(root)
            result["outcome"] = "tally_error" if result["error_tags_present"] else "parsed"
        except HTTPError as exc:
            result.update(outcome="http_error", http_status=exc.code)
        except (URLError, TimeoutError, OSError, ET.ParseError, ValueError) as exc:
            result.update(outcome="probe_failed", error_type=type(exc).__name__)
            reason = getattr(exc, "reason", exc)
            result["reason_type"] = type(reason).__name__
            result["os_error"] = getattr(reason, "winerror", None) or getattr(reason, "errno", None)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))
        if name == "product-about":
            matches = results[0].get("observed", {}).get("target_matches", [])
            if len(matches) == 1 and matches[0].get("GUID"):
                for entity in ("Unit", "Ledger", "StockItem", "Voucher"):
                    probes.append((f"{entity.lower()}-baseline",
                                   scoped_request(args.company, entity),
                                   lambda root, entity=entity: project_records(root, entity)))
        if name.endswith("-baseline") and result.get("outcome") == "parsed":
            observed = result["observed"]
            maximum = observed["max_alter_id"]
            if maximum is not None:
                entity = observed["entity"]
                probes.append((f"{entity.lower()}-after-{maximum}",
                               scoped_request(args.company, entity, maximum),
                               lambda root, entity=entity: project_records(root, entity)))
    (output / "read-only-probes.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(row["outcome"] == "parsed" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
