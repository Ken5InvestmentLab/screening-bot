import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow import (
    ShadowCandidate,
    append_candidates,
    resolve_shadow_file,
)


class ShadowTests(unittest.TestCase):
    def test_rejects_postclose(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            candidate = ShadowCandidate(
                "E", "F", "1234", "2026-09-14", "AM", "2026-09-14T13:00:00+09:00", "POSTCLOSE_RECON_ONLY"
            )
            with self.assertRaises(ValueError):
                append_candidates(path, [candidate])

    def test_append_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shadow.jsonl"
            candidate = ShadowCandidate(
                "E", "F", "1234", "2026-09-14", "AM", "2026-09-14T13:00:00+09:00", "RAW_CAUSAL_INTRADAY"
            )
            self.assertEqual(append_candidates(path, [candidate])["added"], 1)
            self.assertEqual(append_candidates(path, [candidate])["skipped_duplicate"], 1)

    def test_resolution_uses_next_open_to_fifth_close(self):
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "shadow.jsonl"
            out = Path(td) / "resolved.jsonl"
            candidate = ShadowCandidate(
                "E", "F", "1234", "2026-09-14", "PM", "2026-09-14T16:00:00+09:00", "RAW_CAUSAL_INTRADAY"
            )
            append_candidates(inp, [candidate])
            sessions = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21"]
            daily = [
                {"symbol": "1234", "date": "2026-09-15", "open": 100},
                {"symbol": "1234", "date": "2026-09-21", "close": 120},
            ]
            summary = resolve_shadow_file(inp, out, daily, sessions)
            row = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(summary["status_counts"], {"RESOLVED": 1})
            self.assertAlmostEqual(row["ret5bd_gross"], 0.2)

    def test_unmatured_stays_pending(self):
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "shadow.jsonl"
            out = Path(td) / "resolved.jsonl"
            candidate = ShadowCandidate(
                "E", "F", "1234", "2026-09-14", "PM", "2026-09-14T16:00:00+09:00", "RAW_CAUSAL_INTRADAY"
            )
            append_candidates(inp, [candidate])
            resolve_shadow_file(inp, out, [], ["2026-09-14", "2026-09-15"])
            row = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(row["status"], "PENDING_5BD")


if __name__ == "__main__":
    unittest.main()
