import json
from pathlib import Path
import subprocess
import sys


def test_offline_xml_evidence_keeps_no_business_values(tmp_path):
    path = tmp_path / "owner-export.xml"
    path.write_text('<COLLECTION><LEDGER NAME="PRIVATE PARTY"><EMAIL>private@example.invalid</EMAIL>'
        '<ADDRESS.LIST><ADDRESS>Private address</ADDRESS></ADDRESS.LIST></LEDGER></COLLECTION>', encoding="utf-8")
    output = tmp_path / "evidence.json"
    script = Path(__file__).resolve().parents[3] / "scripts/master_sync/party_field_evidence.py"
    result = subprocess.run([sys.executable, str(script), "--xml-file", str(path), "--output", str(output)], timeout=30, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    raw = output.read_text(encoding="utf-8")
    assert "PRIVATE PARTY" not in raw and "private@example.invalid" not in raw and "Private address" not in raw
    assert json.loads(raw)["paths"]["/COLLECTION/LEDGER/ADDRESS.LIST/ADDRESS"] == 1
    rejected = subprocess.run([sys.executable, str(script), "--bahi-id", "1"], timeout=30, capture_output=True)
    assert rejected.returncode != 0 and b"--live-read" in rejected.stderr
