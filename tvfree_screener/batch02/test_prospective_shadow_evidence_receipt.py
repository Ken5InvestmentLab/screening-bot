import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_evidence_receipt import build_receipt


class EvidenceReceiptTests(unittest.TestCase):
    def test_receipt_hash_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.json"
            p.write_text('{"x":1}\n', encoding="utf-8")
            audit = {"experiment_id": "E", "model_freeze_id": "F", "decision": "EVIDENCE_CHAIN_OK", "ok": True}
            r1 = build_receipt({"manifest": p}, audit)
            r2 = build_receipt({"manifest": p}, audit)
            self.assertEqual(r1["receipt_sha256"], r2["receipt_sha256"])

    def test_input_hash_matches_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"
            p.write_bytes(b"abc")
            r = build_receipt({"x": p}, {})
            self.assertEqual(r["inputs"]["x"]["sha256"], hashlib.sha256(b"abc").hexdigest())

    def test_changed_input_changes_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"
            p.write_text("one", encoding="utf-8")
            r1 = build_receipt({"x": p}, {})
            p.write_text("two", encoding="utf-8")
            r2 = build_receipt({"x": p}, {})
            self.assertNotEqual(r1["receipt_sha256"], r2["receipt_sha256"])

    def test_receipt_carries_audit_identity(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"
            p.write_text("x", encoding="utf-8")
            audit = {"experiment_id": "EXP", "model_freeze_id": "FREEZE", "decision": "STOP_EVIDENCE_REVIEW", "ok": False}
            r = build_receipt({"x": p}, audit)
            self.assertEqual(r["experiment_id"], "EXP")
            self.assertEqual(r["model_freeze_id"], "FREEZE")
            self.assertFalse(r["audit_ok"])


if __name__ == "__main__":
    unittest.main()
