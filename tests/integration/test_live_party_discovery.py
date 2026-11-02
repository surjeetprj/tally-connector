"""Explicitly enabled only; ordinary regression runs make no network calls."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.environ.get("CONNECTOR_LIVE_READS") != "1", reason="Opt-in GET/export reads only")
def test_live_party_details(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/phase0/probe_discovery_live.py"
    evidence = tmp_path / "sanitized-live-reads.json"
    result = subprocess.run([sys.executable, str(script), "--evidence-output", str(evidence)],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, "Live GET/export probe failed; inspect connection availability"
    observed = json.loads(evidence.read_text(encoding="utf-8"))
    assert observed["remote_mutations"] == 0
    assert all(side["coverage_complete"] and side["details_match"] for side in observed["sides"].values())
