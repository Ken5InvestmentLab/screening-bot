from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from prospective_shadow import ShadowCandidate, append_candidates, resolve_shadow_file
from prospective_shadow_append_guard import compare_append_only_snapshots
from prospective_shadow_e2e_dry_run import run_synthetic_shadow_e2e
from prospective_shadow_postfreeze_guard import evaluate_postfreeze_rows
from shadow_preflight import validate_shadow_export_rows


class ProspectiveShadowE2EDryRunTest(unittest.TestCase):
    def test_full_synthetic_chain_passes(self):
        result = run_synthetic_shadow_e2e()
        self.assertEqual(result["decision"], "SYNTHETIC_E2E_PASS")
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["integrity"]["production_modified"])

    def test_preflight_rejects_noncausal_source(self):
        row = {
            "experiment_id": "E",
            "model_freeze_id": "F",
            "symbol": "1111.T",
            "signal_date": "2026-09-15",
            "bin_name": "AM_09_13",
            "feature_cutoff": "2026-09-15T13:00:00+09:00",
            "source_tag": "POSTCLOSE_RECON_ONLY",
        }
        with self.assertRaises(ValueError):
            validate_shadow_export_rows([row])

    def test_postfreeze_guard_rejects_equal_or_earlier_cutoff(self):
        manifest = {"experiment_id": "E", "model_freeze_id": "F", "frozen_at": "2026-09-15T13:00:00+09:00"}
        rows = [{"experiment_id": "E", "model_freeze_id": "F", "feature_cutoff": "2026-09-15T13:00:00+09:00"}]
        result = evaluate_postfreeze_rows(manifest, rows)
        self.assertFalse(result["postfreeze_valid"])
        self.assertEqual(result["decision"], "BLOCK_POSTFREEZE_SHADOW_ROWS")

    def test_append_guard_detects_historical_mutation(self):
        old = ['{"key":"A","status":"PENDING_5BD"}']
        new = ['{"key":"A","status":"RESOLVED"}', '{"key":"B","status":"PENDING_5BD"}']
        result = compare_append_only_snapshots(old, new)
        self.assertFalse(result["append_only_valid"])
        self.assertEqual(result["first_mismatch_row"], 1)

    def test_missing_endpoint_is_not_imputed(self):
        candidate = ShadowCandidate(
            experiment_id="E",
            model_freeze_id="F",
            symbol="1111.T",
            signal_date="2026-09-15",
            bin_name="AM_09_13",
            feature_cutoff="2026-09-15T13:00:00+09:00",
            source_tag="RAW_CAUSAL_INTRADAY",
        )
        sessions = ["2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22"]
        daily_rows = [{"symbol": "1111.T", "date": "2026-09-16", "open": 100.0, "close": 101.0}]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            shadow = root / "shadow.jsonl"
            resolved = root / "resolved.jsonl"
            append_candidates(shadow, [candidate])
            result = resolve_shadow_file(shadow, resolved, daily_rows, sessions)
        self.assertEqual(result["status_counts"], {"UNRESOLVED_ENDPOINT": 1})


if __name__ == "__main__":
    unittest.main()
