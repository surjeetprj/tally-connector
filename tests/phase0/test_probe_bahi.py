"""Offline projection checks; no credentials or API calls."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/phase0" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("store_bahi_key")
probe = load("probe_bahi")


class ProjectionTests(unittest.TestCase):
    def test_summary_retains_types_not_customer_values(self):
        result = probe.summary({"account_name": "Private Supplier", "phone": "123456"})
        self.assertEqual(result, {"field_types": {"account_name": "str", "phone": "str"}})

    def test_missing_status_is_not_inferred_from_payment_status(self):
        result = probe.summary({"payment_status": "PAID", "items": []}, invoice=True)
        self.assertFalse(result["invoice_status_present"])
        self.assertEqual(result["invoice_status"], "missing_or_unrecognized")

    def test_detail_items_project_only_shapes(self):
        result = probe.summary({"invoice_status": "ACTIVE", "items": [{"price": "100.00"}]}, True)
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["first_item_field_types"], {"price": "str"})
        self.assertEqual(result["invoice_status"], "ACTIVE")

    def test_malformed_status_does_not_crash(self):
        result = probe.summary({"invoice_status": []}, True)
        self.assertEqual(result["invoice_status"], "missing_or_unrecognized")

    def test_unstructured_error_is_not_retained(self):
        self.assertEqual(probe.safe_code({"error": {"code": "private error text"}}), "UNCLASSIFIED")
        self.assertEqual(probe.safe_code({"error": {"code": "ACCESS_DENIED"}}), "ACCESS_DENIED")


if __name__ == "__main__":
    unittest.main()
