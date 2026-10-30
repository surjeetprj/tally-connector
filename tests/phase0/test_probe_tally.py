"""Offline checks for the read-only experiment, not the future app gateway."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/phase0/probe_tally.py"
SPEC = importlib.util.spec_from_file_location("phase0_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_collection_records_exclude_header_counters(self):
        root = ET.fromstring('''<ENVELOPE><HEADER><CMPINFO><VOUCHER>10</VOUCHER>
          </CMPINFO></HEADER><BODY><DATA><COLLECTION><VOUCHER>
          <GUID>example-guid</GUID><ALTERID>17</ALTERID></VOUCHER>
          </COLLECTION></DATA></BODY></ENVELOPE>''')
        result = probe.project_records(root, "Voucher")
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["max_alter_id"], 17)
        self.assertEqual(result["records_with_guid"], 1)

    def test_empty_collection_is_zero_records(self):
        root = ET.fromstring('''<ENVELOPE><HEADER><CMPINFO><LEDGER>0</LEDGER>
          </CMPINFO></HEADER><BODY><DATA><COLLECTION/></DATA></BODY></ENVELOPE>''')
        self.assertEqual(probe.project_records(root, "Ledger")["record_count"], 0)

    def test_company_projection_retains_only_target_identity(self):
        root = ET.fromstring('''<ENVELOPE><HEADER><COMPANY>2</COMPANY></HEADER>
          <COLLECTION><COMPANY NAME="SIS Dummy"><GUID>test-guid</GUID>
          <COMPANYNUMBER>100006</COMPANYNUMBER><EMAIL>private@example.com</EMAIL>
          </COMPANY><COMPANY NAME="Other"/></COLLECTION></ENVELOPE>''')
        result = probe.project_companies(root, "SIS Dummy")
        self.assertEqual(result["company_count"], 2)
        self.assertEqual(len(result["target_matches"]), 1)
        self.assertNotIn("EMAIL", result["target_matches"][0])

    def test_requests_are_exports_and_scope_is_escaped(self):
        for entity in ("Unit", "Ledger", "StockItem", "Voucher"):
            root = ET.fromstring(probe.scoped_request('SIS & Dummy', entity, 7))
            self.assertEqual(root.findtext("HEADER/TALLYREQUEST"), "Export")
            self.assertEqual(root.findtext(".//SVCURRENTCOMPANY"), 'SIS & Dummy')
            self.assertEqual(root.findtext(".//SYSTEM"), "$AlterID > 7")
            self.assertIsNone(root.find(".//IMPORTDATA"))

    def test_about_projection_excludes_serial_and_paths(self):
        root = ET.fromstring('''<ENVELOPE><ABOUTPAGEPROMPT>Serial Number</ABOUTPAGEPROMPT>
          <ABOUTPAGEINFO>secret-serial</ABOUTPAGEINFO><ABOUTPAGEPROMPT>Release</ABOUTPAGEPROMPT>
          <ABOUTPAGEINFO>6.2</ABOUTPAGEINFO></ENVELOPE>''')
        self.assertEqual(probe.project_about(root)["product_fields"],
                         [{"label": "Release", "value": "6.2"}])


if __name__ == "__main__":
    unittest.main()
