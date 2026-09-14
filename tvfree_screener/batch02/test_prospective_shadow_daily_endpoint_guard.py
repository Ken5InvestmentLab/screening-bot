from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from prospective_shadow_daily_endpoint_guard import (
    build_daily_endpoint_manifest,
    validate_daily_endpoint_dataset,
)


class DailyEndpointGuardTests(unittest.TestCase):
    def _write_daily(self, path: Path, rows=None):
        rows = rows or [
            {"symbol":"1111.T","date":"2026-09-16","open":"100","close":"101"},
            {"symbol":"1111.T","date":"2026-09-25","open":"119","close":"120"},
            {"symbol":"2222.T","date":"2026-09-16","open":"200","close":"201"},
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["symbol","date","open","close"])
            w.writeheader()
            w.writerows(rows)

    def _manifest(self, daily: Path):
        return build_daily_endpoint_manifest(
            daily,
            dataset_id="daily-endpoint-20260925",
            source_name="Yahoo chart direct",
            source_kind="REMOTE_MARKET_DATA",
            acquired_at="2026-09-25T18:00:00+09:00",
            price_adjustment_semantics="PROVIDER_HISTORICAL_SPLIT_ADJUSTED_OHLC",
        )

    def test_valid_dataset_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertTrue(out["endpoint_dataset_valid"])
            self.assertEqual(out["row_count"],3)
            self.assertEqual(out["symbol_count"],2)
            self.assertTrue(out["integrity"]["acquisition_not_before_last_data_date"])

    def test_sha_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            daily.write_text(daily.read_text()+"\n",encoding="utf-8")
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertFalse(out["endpoint_dataset_valid"])
            self.assertIn("daily_csv_sha256_mismatch",out["errors"])

    def test_row_count_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            manifest["row_count"]=999
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertFalse(out["endpoint_dataset_valid"])
            self.assertIn("row_count_mismatch",out["errors"])

    def test_duplicate_symbol_date_blocks_manifest_creation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"
            self._write_daily(daily,[
                {"symbol":"1111.T","date":"2026-09-16","open":"100","close":"101"},
                {"symbol":"1111.T","date":"2026-09-16","open":"100","close":"101"},
            ])
            with self.assertRaises(ValueError):
                self._manifest(daily)

    def test_naive_acquired_at_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            manifest["acquired_at"]="2026-09-25T18:00:00"
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertFalse(out["endpoint_dataset_valid"])
            self.assertTrue(any("timezone-aware" in e for e in out["errors"]))

    def test_manifest_creation_blocks_acquisition_before_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            with self.assertRaisesRegex(ValueError, "acquired_at_precedes_last_data_date"):
                build_daily_endpoint_manifest(
                    daily,
                    dataset_id="daily-endpoint-impossible",
                    source_name="Yahoo chart direct",
                    source_kind="REMOTE_MARKET_DATA",
                    acquired_at="2026-09-24T23:59:59+09:00",
                    price_adjustment_semantics="PROVIDER_HISTORICAL_SPLIT_ADJUSTED_OHLC",
                )

    def test_validation_blocks_acquisition_before_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            manifest["acquired_at"]="2026-09-24T23:59:59+09:00"
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertFalse(out["endpoint_dataset_valid"])
            self.assertIn("acquired_at_precedes_last_data_date",out["errors"])

    def test_placeholder_provenance_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"; self._write_daily(daily)
            manifest=self._manifest(daily)
            manifest["source_name"]="UNKNOWN"
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertFalse(out["endpoint_dataset_valid"])
            self.assertIn("source_name_missing_or_placeholder",out["errors"])

    def test_nonpositive_present_price_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"
            self._write_daily(daily,[{"symbol":"1111.T","date":"2026-09-16","open":"0","close":"101"}])
            with self.assertRaises(ValueError):
                self._manifest(daily)

    def test_blank_prices_can_be_pinned_as_unresolved_source_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); daily=root/"daily.csv"
            self._write_daily(daily,[{"symbol":"1111.T","date":"2026-09-16","open":"","close":""}])
            manifest=self._manifest(daily)
            out=validate_daily_endpoint_dataset(daily,manifest)
            self.assertTrue(out["endpoint_dataset_valid"])


if __name__ == "__main__":
    unittest.main()
