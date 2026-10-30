"""Read-only populated AlterID filter checks against the existing dummy company."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET

from probe_tally import NoRedirect, company_request, project_companies, project_records, scoped_request


def main():
    folder = Path(__file__).resolve().parents[2] / "docs/api/tally/evidence"
    prior = json.loads((folder / "read-only-probes.json").read_text(encoding="utf-8"))
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def export(payload):
        req = Request("http://localhost:9000", data=payload, method="POST",
                      headers={"Content-Type": "application/xml"})
        with opener.open(req, timeout=15) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Unexpected response")
        root = ET.fromstring(raw)
        if any(node.tag.upper() in {"LINEERROR", "ERROR"} and (node.text or "").strip()
               for node in root.iter()):
            raise ValueError("Tally export error")
        return root, hashlib.sha256(raw).hexdigest()

    company, _ = export(company_request())
    matches = project_companies(company, "SIS Dummy")["target_matches"]
    original = prior[0]["observed"]["target_matches"]
    if len(matches) != 1 or matches[0].get("GUID") != original[0].get("GUID"):
        raise ValueError("Company identity changed; no further probes performed")
    results = []
    for row in prior:
        if not row["probe"].endswith("-baseline"):
            continue
        base = row["observed"]
        threshold = base["max_alter_id"] - 1
        entity = base["entity"]
        payload = scoped_request("SIS Dummy", entity, threshold)
        filename = f"{entity.lower()}-selective.request.xml"
        (folder / filename).write_bytes(payload)
        root, digest = export(payload)
        observed = project_records(root, entity)
        passed = (observed["record_count"] > 0
                  and observed["record_count"] == observed["records_with_numeric_alter_id"]
                  and observed["min_alter_id"] > threshold)
        results.append({"utc": datetime.now(timezone.utc).isoformat(),
                        "entity": entity, "after": threshold, "request": filename,
                        "observed": observed, "filter_predicate_verified": passed,
                        "response_sha256": digest})
    (folder / "selective-probes.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results))
    return 0 if len(results) == 4 and all(row["filter_predicate_verified"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
