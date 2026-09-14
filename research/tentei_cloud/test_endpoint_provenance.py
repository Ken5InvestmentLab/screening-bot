import unittest

import pandas as pd

from endpoint_provenance import (
    calendar_manifest_sha256,
    resolve_canonical_endpoints,
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
                # A nearby but wrong final row exists. It must not be substituted for 05:00Z.
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


if __name__ == "__main__":
    unittest.main()
