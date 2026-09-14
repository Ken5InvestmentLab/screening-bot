import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from endpoint_provenance import (
    build_source_receipt,
    calendar_manifest_sha256,
    resolve_canonical_endpoints,
    verify_source_receipt,
)


def calendar_fixture() -> pd.DataFrame:
    rows = []
    for date in [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-14",
    ]:
        rows.append(
            {
                "date": date,
                "calendar_name": "XTKS",
                "calendar_version": "fixture-v1",
                "open_bar_ts": f"{date}T00:00:00Z",
                "close_bar_ts": f"{date}T05:00:00Z",
            }
        )
    return pd.DataFrame(rows)


class EndpointProvenanceTests(unittest.TestCase):
    def test_pinned_calendar_maps_next_open_and_fifth_close(self):
        cal = calendar_fixture()
        sha = calendar_manifest_sha256(cal)
        candidates = pd.DataFrame([{"symbol": "1234", "date": "2025-01-06"}])
        raw = pd.DataFrame(
            [
                {"symbol": "1234", "timestamp": "2025-01-07T00:00:00Z", "open": 100, "close": 101},
                {"symbol": "1234", "timestamp": "2025-01-14T05:00:00Z", "open": 109, "close": 110},
            ]
        )
        rows, receipt = resolve_canonical_endpoints(candidates, raw, cal, sha)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(rows.iloc[0]["entry_date"], "2025-01-07")
        self.assertEqual(rows.iloc[0]["exit_date"], "2025-01-14")
        self.assertAlmostEqual(float(rows.iloc[0]["canonical_ret5bd"]), 0.10)

    def test_missing_exact_close_fails_closed_without_last_available_fallback(self):
        cal = calendar_fixture()
        sha = calendar_manifest_sha256(cal)
        candidates = pd.DataFrame([{"symbol": "1234", "date": "2025-01-06"}])
        raw = pd.DataFrame(
            [
                {"symbol": "1234", "timestamp": "2025-01-07T00:00:00Z", "open": 100, "close": 101},
                {"symbol": "1234", "timestamp": "2025-01-14T04:00:00Z", "open": 109, "close": 110},
            ]
        )
        rows, receipt = resolve_canonical_endpoints(candidates, raw, cal, sha)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(receipt["unresolved_n"], 1)
        self.assertFalse(bool(rows.iloc[0]["endpoint_complete"]))
        self.assertTrue(pd.isna(rows.iloc[0]["canonical_ret5bd"]))

    def test_calendar_hash_tamper_is_rejected(self):
        cal = calendar_fixture()
        sha = calendar_manifest_sha256(cal)
        tampered = cal.copy()
        tampered.loc[1, "close_bar_ts"] = "2025-01-07T05:01:00Z"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            resolve_canonical_endpoints(
                pd.DataFrame([{"symbol": "1234", "date": "2025-01-06"}]),
                pd.DataFrame(
                    [
                        {"symbol": "1234", "timestamp": "2025-01-07T00:00:00Z", "open": 100, "close": 101},
                        {"symbol": "1234", "timestamp": "2025-01-14T05:00:00Z", "open": 109, "close": 110},
                    ]
                ),
                tampered,
                sha,
            )

    def test_duplicate_endpoint_rows_are_rejected(self):
        cal = calendar_fixture()
        sha = calendar_manifest_sha256(cal)
        raw = pd.DataFrame(
            [
                {"symbol": "1234", "timestamp": "2025-01-07T00:00:00Z", "open": 100, "close": 101},
                {"symbol": "1234", "timestamp": "2025-01-07T00:00:00Z", "open": 100, "close": 101},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate symbol/timestamp"):
            resolve_canonical_endpoints(
                pd.DataFrame([{"symbol": "1234", "date": "2025-01-06"}]),
                raw,
                cal,
                sha,
            )

    def test_unsorted_calendar_is_rejected(self):
        cal = calendar_fixture().iloc[[1, 0, 2, 3, 4, 5]].reset_index(drop=True)
        with self.assertRaisesRegex(ValueError, "strictly sorted"):
            calendar_manifest_sha256(cal)

    def test_source_receipt_binds_exact_bytes_and_calendar(self):
        cal_sha = calendar_manifest_sha256(calendar_fixture())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p1 = root / "ohlcv_1h_shard_00.csv"
            p2 = root / "ohlcv_1h_shard_01.csv"
            p1.write_text("symbol,timestamp,open,close\n1234,2025-01-07T00:00:00Z,100,101\n", encoding="utf-8")
            p2.write_text("symbol,timestamp,open,close\n5678,2025-01-07T00:00:00Z,200,202\n", encoding="utf-8")
            receipt = build_source_receipt(
                [p2, p1],
                source_run_id="34800000000",
                source_artifact_name="tentei-cloud-1h-extended",
                vendor="Yahoo Finance chart API",
                calendar_sha256=cal_sha,
            )
            verified = verify_source_receipt([p1, p2], receipt, expected_calendar_sha256=cal_sha)
            self.assertEqual(verified["source_run_id"], "34800000000")
            self.assertFalse(verified["performance_opened"])
            self.assertEqual([x["name"] for x in verified["files"]], [p1.name, p2.name])
            self.assertEqual(len(verified["receipt_sha256"]), 64)
            json.dumps(verified)

    def test_source_receipt_rejects_mutated_raw_bytes(self):
        cal_sha = calendar_manifest_sha256(calendar_fixture())
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ohlcv_1h_shard_00.csv"
            p.write_text("a,b\n1,2\n", encoding="utf-8")
            receipt = build_source_receipt(
                [p],
                source_run_id="1",
                source_artifact_name="fixture",
                vendor="fixture-vendor",
                calendar_sha256=cal_sha,
            )
            p.write_text("a,b\n1,3\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
                verify_source_receipt([p], receipt, expected_calendar_sha256=cal_sha)

    def test_source_receipt_rejects_metadata_tamper(self):
        cal_sha = calendar_manifest_sha256(calendar_fixture())
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ohlcv_1h_shard_00.csv"
            p.write_text("a,b\n1,2\n", encoding="utf-8")
            receipt = build_source_receipt(
                [p],
                source_run_id="1",
                source_artifact_name="fixture",
                vendor="fixture-vendor",
                calendar_sha256=cal_sha,
            )
            receipt["source_run_id"] = "2"
            with self.assertRaisesRegex(ValueError, "receipt SHA-256 mismatch"):
                verify_source_receipt([p], receipt, expected_calendar_sha256=cal_sha)


if __name__ == "__main__":
    unittest.main()
