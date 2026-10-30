"""No-network checks of comparison and uncertain-create safeguards."""
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
load("probe_bahi")
probe = load("test_bahi_posting")


class ControlledPurchaseTests(unittest.TestCase):
    def test_preflight_stop_does_not_imply_an_external_write(self):
        self.assertIsNone(probe.prior_invoice_id([{"event": "STOPPED"}]))

    def test_unknown_create_cannot_be_replayed(self):
        with self.assertRaisesRegex(RuntimeError, "no create replay"):
            probe.prior_invoice_id([{"event": "WRITE_INTENT", "method": "POST", "endpoint": "api-invoice.php"}])

    def test_known_id_resumes_without_creating_again(self):
        self.assertEqual(probe.prior_invoice_id([{"event": "CREATED_ID", "invoice_id": 69}]), 69)

    def test_conflicting_ids_block(self):
        with self.assertRaisesRegex(RuntimeError, "Conflicting"):
            probe.prior_invoice_id([{"invoice_id": 69}, {"invoice_id": 70}])

    def test_comparison_rejects_changed_amount_and_identity(self):
        payload = {"invoice_num": "TEST", "ref_doc_no": "TEST", "ref_doc_date": "2026-10-29",
                   "invoice_dt": "2026-10-29", "txn_type": "PURCHASE", "invoice_cust_id": 274,
                   "items": [{"item_id": 84, "qty": "1.000", "price": "1.00", "gst_pct": "18.00"}]}
        remote = {**payload, "biz_id": 52, "invoice_id": 69, "invoice_status": "ACTIVE",
                  "total_amt": "1.00", "cgst": "0.09", "sgst": "0.09", "igst": "0.00", "net_amt": "1.18"}
        self.assertEqual(probe.verify_invoice(remote, payload)["total"], "1.18")
        with self.assertRaisesRegex(ValueError, "Net total"):
            probe.verify_invoice({**remote, "net_amt": "2.18"}, payload)
        with self.assertRaisesRegex(ValueError, "business"):
            probe.verify_invoice({**remote, "biz_id": 53}, payload)


if __name__ == "__main__":
    unittest.main()
