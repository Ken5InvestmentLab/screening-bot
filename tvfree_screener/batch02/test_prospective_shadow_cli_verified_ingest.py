from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_admission_gate import evaluate_shadow_admission
from tvfree_screener.batch02.prospective_shadow_admission_receipt import build_admission_receipt
from tvfree_screener.batch02.prospective_shadow_cli import (
    build_parser,
    cmd_ingest,
    normalize_candidate_row,
)


class ProspectiveShadowCliVerifiedIngestTests(unittest.TestCase):
    def _manifest(self) -> dict:
        return {
            "experiment_id": "EXP-CLI-V",
            "model_freeze_id": "FREEZE-CLI-V",
            "frozen_at": "2026-09-14T00:00:00+09:00",
            "model_spec_sha256": "a" * 64,
        }

    def _row(self, **overrides) -> dict:
        row = {
            "symbol": "1234",
            "signal_date": "2026-09-14",
            "bin_name": "AM_09_13",
            "feature_cutoff": "2026-09-14T13:00:00+09:00",
            "source_tag": "RAW_CAUSAL_INTRADAY",
            "rank": 1,
            "eligibility_status": "ELIGIBLE",
            "data_sufficient": True,
            "skip_reason": "",
            "missing_fields": [],
        }
        row.update(overrides)
        return row

    def _write_fixture(self, root: Path, row: dict | None = None):
        manifest = self._manifest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        normalized = normalize_candidate_row(row or self._row(), manifest)
        candidates_path = root / "candidates.jsonl"
        candidates_path.write_text(json.dumps(normalized) + "\n", encoding="utf-8")

        admission = evaluate_shadow_admission(manifest, [normalized])
        admission_path = root / "admission.json"
        admission_path.write_text(json.dumps(admission), encoding="utf-8")

        receipt = build_admission_receipt(
            manifest,
            [normalized],
            admission,
            "2026-09-14T13:01:00+09:00",
        )
        receipt_path = root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return manifest_path, candidates_path, admission_path, receipt_path

    def _args(self, root: Path, manifest: Path, candidates: Path, admission: Path, receipt: Path):
        return argparse.Namespace(
            freeze_manifest=str(manifest),
            freeze_sha256=None,
            candidates=str(candidates),
            admission=str(admission),
            receipt=str(receipt),
            shadow=str(root / "shadow.jsonl"),
            summary=str(root / "summary.json"),
        )

    def test_ingest_parser_requires_admission_and_receipt(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "ingest",
                "--freeze-manifest", "m.json",
                "--candidates", "c.jsonl",
                "--shadow", "s.jsonl",
                "--summary", "sum.json",
            ])

    def test_csv_style_true_normalizes_to_boolean(self):
        row = self._row(data_sufficient="true", missing_fields="[]")
        normalized = normalize_candidate_row(row, self._manifest())
        self.assertIs(normalized["data_sufficient"], True)
        self.assertEqual(normalized["missing_fields"], [])

    def test_valid_verified_ingest_appends(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self._write_fixture(root)
            cmd_ingest(self._args(root, *fixture))
            shadow = root / "shadow.jsonl"
            self.assertTrue(shadow.exists())
            self.assertEqual(len([x for x in shadow.read_text().splitlines() if x.strip()]), 1)

    def test_tampered_receipt_blocks_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self._write_fixture(root)
            receipt_path = fixture[3]
            receipt = json.loads(receipt_path.read_text())
            receipt["row_count"] = 999
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaises(SystemExit):
                cmd_ingest(self._args(root, *fixture))
            self.assertFalse((root / "shadow.jsonl").exists())

    def test_ineligible_candidate_change_blocks_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = self._write_fixture(root)
            candidates_path = fixture[1]
            changed = normalize_candidate_row(self._row(data_sufficient=False), self._manifest())
            candidates_path.write_text(json.dumps(changed) + "\n")
            with self.assertRaises(SystemExit):
                cmd_ingest(self._args(root, *fixture))
            self.assertFalse((root / "shadow.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
