from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from .artifact_store import (
    read_verified_parquet,
    read_verified_parquet_columns,
    write_parquet_artifact,
    write_parquet_batches,
)


class ArtifactStoreTests(unittest.TestCase):
    def test_parquet_round_trip_preserves_complete_pool_and_receipt(self) -> None:
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-04", "2024-01-04"]),
            "symbol": ["1111", "2222"],
            "raw_rank": [1, 2],
            "score": [0.8, 0.7],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_candidate_pool.parquet"
            receipt = write_parquet_artifact(
                frame, path, metadata={"family": "test", "spec_sha256": "abc"},
            )
            actual, loaded_receipt = read_verified_parquet(path)
            pd.testing.assert_frame_equal(actual, frame)
            self.assertEqual(receipt["rows"], 2)
            self.assertEqual(loaded_receipt["family"], "test")

    def test_future_outcomes_cannot_be_written_to_decision_pool(self) -> None:
        frame = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-04")],
            "symbol": ["1111"],
            "future_return": [0.5],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_candidate_pool.parquet"
            with self.assertRaisesRegex(ValueError, "outcome-like"):
                write_parquet_artifact(frame, path, metadata={})
            self.assertFalse(path.exists())

    def test_streaming_writer_keeps_every_batch_and_manifest_hash(self) -> None:
        first = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-04", "2024-01-05"]),
            "symbol": pd.Series(["1111", "1111"], dtype="string"),
            "feature": pd.Series([0.1, 0.2], dtype="float32"),
        })
        second = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-09"]),
            "symbol": pd.Series(["2222"], dtype="string"),
            "feature": pd.Series([0.3], dtype="float32"),
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "streamed_features.parquet"
            receipt = write_parquet_batches([first, second], path, metadata={"source_sha256": "abc"})
            actual, manifest = read_verified_parquet(path)
            self.assertEqual(len(actual), 3)
            self.assertEqual(receipt["rows"], 3)
            self.assertTrue(manifest["streamed_batches"])
            self.assertEqual(manifest["source_sha256"], "abc")

    def test_verified_projection_materializes_only_requested_columns(self) -> None:
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-04", "2024-01-05"]),
            "symbol": pd.Series(["1111", "2222"], dtype="string"),
            "open": [100.0, 200.0],
            "close": [101.0, 202.0],
            "feature": [0.1, 0.2],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feature_panel.parquet"
            write_parquet_artifact(frame, path, metadata={"labels_included": False})
            projected, receipt = read_verified_parquet_columns(path, ["date", "symbol", "open", "close"])
        self.assertEqual(list(projected.columns), ["date", "symbol", "open", "close"])
        self.assertEqual(len(projected), len(frame))
        self.assertEqual(receipt["rows"], 2)
        self.assertNotIn("feature", projected.columns)


if __name__ == "__main__":
    unittest.main()
