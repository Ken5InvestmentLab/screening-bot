import csv
import hashlib
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_cli import (
    candidate_from_row,
    load_candidate_rows,
    load_freeze_manifest,
    read_daily_csv,
    cmd_resolve,
)
from tvfree_screener.batch02.prospective_shadow import ShadowCandidate, append_candidates
from tvfree_screener.batch02.prospective_shadow_daily_endpoint_guard import build_daily_endpoint_manifest


class ProspectiveShadowCliTests(unittest.TestCase):
    def _manifest(self, path: Path) -> dict:
        payload = {
            "experiment_id": "EXP-1",
            "model_freeze_id": "FREEZE-1",
            "frozen_at": "2026-09-14T00:00:00+09:00",
            "model_spec_sha256": "a" * 64,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def test_manifest_sha_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "freeze.json"
            self._manifest(path)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            loaded = load_freeze_manifest(path, sha)
            self.assertEqual(loaded["model_freeze_id"], "FREEZE-1")
            with self.assertRaises(RuntimeError):
                load_freeze_manifest(path, "0" * 64)

    def test_candidate_cannot_override_freeze_identity(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "freeze.json"
            self._manifest(path)
            freeze = load_freeze_manifest(path)
            with self.assertRaises(ValueError):
                candidate_from_row({
                    "experiment_id": "OTHER",
                    "symbol": "1234",
                    "signal_date": "2026-09-14",
                    "bin_name": "AM_09_13",
                    "feature_cutoff": "2026-09-14T13:00:00+09:00",
                    "source_tag": "RAW_CAUSAL_INTRADAY",
                }, freeze)

    def test_csv_candidate_loader(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cand.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol", "signal_date"])
                w.writeheader()
                w.writerow({"symbol": "1234", "signal_date": "2026-09-14"})
            rows = load_candidate_rows(path)
            self.assertEqual(rows[0]["symbol"], "1234")

    def test_daily_sessions_are_derived_without_fill(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "daily.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol", "date", "open", "close"])
                w.writeheader()
                w.writerow({"symbol": "1234", "date": "2026-09-15", "open": "100", "close": "105"})
                w.writerow({"symbol": "1234", "date": "2026-09-16", "open": "106", "close": "107"})
            rows, sessions = read_daily_csv(path)
            self.assertEqual(sessions, ["2026-09-15", "2026-09-16"])
            self.assertEqual(rows[0]["open"], "100")


    def test_resolve_cli_blocks_rewrite_of_already_resolved_endpoint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "freeze.json"
            self._manifest(manifest_path)
            shadow = root / "shadow.jsonl"
            resolved = root / "resolved.jsonl"
            summary = root / "summary.json"

            append_candidates(
                shadow,
                [
                    ShadowCandidate(
                        experiment_id="EXP-1",
                        model_freeze_id="FREEZE-1",
                        symbol="1234",
                        signal_date="2026-09-15",
                        bin_name="AM_09_13",
                        feature_cutoff="2026-09-15T13:00:00+09:00",
                        source_tag="RAW_CAUSAL_INTRADAY",
                        rank=1,
                    )
                ],
            )

            def write_daily(path: Path, exit_close: str) -> None:
                dates = ["2026-09-15","2026-09-16","2026-09-17","2026-09-18","2026-09-24","2026-09-25"]
                with path.open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["symbol", "date", "open", "close"])
                    w.writeheader()
                    for i, date in enumerate(dates):
                        w.writerow({
                            "symbol": "1234",
                            "date": date,
                            "open": "100" if date == "2026-09-16" else "110",
                            "close": exit_close if date == "2026-09-25" else str(101 + i),
                        })

            def write_daily_manifest(daily_path: Path, manifest_path: Path) -> None:
                payload = build_daily_endpoint_manifest(
                    daily_path,
                    dataset_id=daily_path.stem,
                    source_name="Yahoo chart direct",
                    source_kind="REMOTE_MARKET_DATA",
                    acquired_at="2026-09-25T18:00:00+09:00",
                    expected_through_date="2026-09-25",
                    price_adjustment_semantics="PROVIDER_HISTORICAL_SPLIT_ADJUSTED_OHLC",
                )
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            daily1 = root / "daily1.csv"
            daily1_manifest = root / "daily1.manifest.json"
            write_daily(daily1, "120")
            write_daily_manifest(daily1, daily1_manifest)
            cmd_resolve(Namespace(
                freeze_manifest=str(manifest_path),
                freeze_sha256=None,
                shadow=str(shadow),
                daily=str(daily1),
                daily_manifest=str(daily1_manifest),
                sessions_csv=None,
                sessions_manifest=None,
                resolution_receipt=str(root / "resolution1.receipt.json"),
                resolved=str(resolved),
                summary=str(summary),
            ))
            snapshot = resolved.read_bytes()

            daily2 = root / "daily2.csv"
            daily2_manifest = root / "daily2.manifest.json"
            write_daily(daily2, "121")
            write_daily_manifest(daily2, daily2_manifest)
            with self.assertRaises(SystemExit) as cm:
                cmd_resolve(Namespace(
                    freeze_manifest=str(manifest_path),
                    freeze_sha256=None,
                    shadow=str(shadow),
                    daily=str(daily2),
                    daily_manifest=str(daily2_manifest),
                    sessions_csv=None,
                    sessions_manifest=None,
                    resolution_receipt=str(root / "resolution2.receipt.json"),
                    resolved=str(resolved),
                    summary=str(summary),
                ))
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(resolved.read_bytes(), snapshot)


    def test_resolve_cli_blocks_tampered_daily_manifest_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "freeze.json"
            self._manifest(manifest_path)
            shadow = root / "shadow.jsonl"
            resolved = root / "resolved.jsonl"
            summary = root / "summary.json"
            append_candidates(
                shadow,
                [ShadowCandidate(
                    experiment_id="EXP-1",
                    model_freeze_id="FREEZE-1",
                    symbol="1234",
                    signal_date="2026-09-15",
                    bin_name="AM_09_13",
                    feature_cutoff="2026-09-15T13:00:00+09:00",
                    source_tag="RAW_CAUSAL_INTRADAY",
                    rank=1,
                )],
            )
            daily = root / "daily.csv"
            with daily.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol","date","open","close"])
                w.writeheader()
                w.writerow({"symbol":"1234","date":"2026-09-16","open":"100","close":"101"})
                w.writerow({"symbol":"1234","date":"2026-09-25","open":"119","close":"120"})
            daily_manifest = root / "daily.manifest.json"
            payload = build_daily_endpoint_manifest(
                daily,
                dataset_id="daily-endpoint",
                source_name="Yahoo chart direct",
                source_kind="REMOTE_MARKET_DATA",
                acquired_at="2026-09-25T18:00:00+09:00",
                expected_through_date="2026-09-25",
                price_adjustment_semantics="PROVIDER_HISTORICAL_SPLIT_ADJUSTED_OHLC",
            )
            payload["csv_sha256"] = "0" * 64
            daily_manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(SystemExit) as cm:
                cmd_resolve(Namespace(
                    freeze_manifest=str(manifest_path),
                    freeze_sha256=None,
                    shadow=str(shadow),
                    daily=str(daily),
                    daily_manifest=str(daily_manifest),
                    sessions_csv=None,
                    sessions_manifest=None,
                    resolution_receipt=str(root / "tampered.receipt.json"),
                    resolved=str(resolved),
                    summary=str(summary),
                ))
            self.assertEqual(cm.exception.code, 2)
            self.assertFalse(resolved.exists())
            summary_payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["decision"], "BLOCK_CLI_DAILY_ENDPOINT_DATASET")


    def test_resolve_cli_refuses_existing_resolution_receipt_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "freeze.json"
            self._manifest(manifest_path)
            shadow = root / "shadow.jsonl"
            resolved = root / "resolved.jsonl"
            summary = root / "summary.json"
            receipt_path = root / "receipt.json"
            receipt_path.write_text("already", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                cmd_resolve(Namespace(
                    freeze_manifest=str(manifest_path),
                    freeze_sha256=None,
                    shadow=str(shadow),
                    daily=str(root / "daily.csv"),
                    daily_manifest=str(root / "daily.manifest.json"),
                    sessions_csv=None,
                    sessions_manifest=None,
                    resolution_receipt=str(receipt_path),
                    resolved=str(resolved),
                    summary=str(summary),
                ))
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(receipt_path.read_text(encoding="utf-8"), "already")
            self.assertFalse(resolved.exists())


if __name__ == "__main__":
    unittest.main()
