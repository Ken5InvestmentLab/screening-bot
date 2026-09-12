"""Regression coverage for the frozen Ridge audit's decision-panel lifecycle."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from . import core_moderate_ridge_audit as audit


class FeaturePanelLifecycleTests(unittest.TestCase):
    def test_new_panel_returns_after_atomic_write_without_unbound_cleanup_name(self) -> None:
        frame = pd.DataFrame({"date": [pd.Timestamp("2023-12-29")], "symbol": ["1301"]})
        source_hash = "a" * 64

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tse_daily.csv"
            source.write_text("synthetic", encoding="utf-8")

            def write_batches(_batches, path: Path, *, metadata: dict[str, object]) -> dict[str, str]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"atomic-test-panel")
                self.assertEqual(metadata["source_sha256"], source_hash)
                return {"source_sha256": source_hash}

            with (
                patch.object(audit, "BATCH_DIR", root),
                patch.object(audit, "SOURCE_PATH", source),
                patch.object(audit, "_read_bars", return_value=pd.DataFrame({"symbol": ["1301"]})),
                patch.object(audit, "_expected_source_hash", return_value=source_hash),
                patch.object(audit, "sha256_file", return_value=source_hash),
                patch.object(audit, "iter_symbol_feature_batches", return_value=iter([frame])),
                patch.object(audit, "write_parquet_batches", side_effect=write_batches) as write_mock,
                patch.object(audit, "read_verified_parquet", return_value=(frame, {"source_sha256": source_hash})),
            ):
                actual = audit._feature_panel(
                    pd.Timestamp("2023-12-29"),
                    SimpleNamespace(sessions=(pd.Timestamp("2023-12-29"),), sha256="b" * 64),
                )

        pd.testing.assert_frame_equal(actual, frame)
        write_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
