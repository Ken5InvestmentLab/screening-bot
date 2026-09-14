import unittest

import pandas as pd

from ohlcv_supplement import verify_and_select_supplements


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


POLICY = {
    "yahoo_chart_api_native": {
        "priority": 0,
        "formal_eligible": True,
        "allowed_timeframes": ["1h", "1d"],
    },
    "stooq_intraday_candidate": {
        "priority": 10,
        "formal_eligible": False,
        "allowed_timeframes": ["1h", "1d"],
    },
    "alpha_vantage_free": {
        "priority": 20,
        "formal_eligible": True,
        "allowed_timeframes": ["1d"],
    },
    "googlefinance_snapshot": {
        "priority": 30,
        "formal_eligible": False,
        "allowed_timeframes": ["snapshot"],
    },
}


def inventory(timeframe="1h"):
    return pd.DataFrame(
        [
            {
                "symbol": "7203",
                "timestamp": "2025-08-01T05:00:00Z",
                "timeframe": timeframe,
                "decision_ts": "2025-08-01T06:00:00Z",
            }
        ]
    )


def row(source, timeframe="1h", close=101.0, sha=SHA_A):
    return {
        "symbol": "7203.T",
        "timestamp": "2025-08-01T05:00:00Z",
        "timeframe": timeframe,
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": close,
        "volume": 1000,
        "source": source,
        "acquired_at": "2026-09-15T00:00:00Z",
        "latest_market_ts": "2025-08-01T05:00:00Z",
        "raw_sha256": sha,
    }


class OHLCVSupplementTests(unittest.TestCase):
    def test_accepts_only_predeclared_missing_pair(self):
        selected, audit, receipt = verify_and_select_supplements(
            inventory(),
            pd.DataFrame([row("yahoo_chart_api_native")]),
            POLICY,
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["accepted_n"], 1)
        self.assertEqual(selected.iloc[0]["provenance"], "supplemented")
        self.assertEqual(audit.iloc[0]["acceptance"], "ACCEPT")
        self.assertFalse(receipt["performance_opened"])
        self.assertEqual(receipt["receipt_sha256"].__len__(), 64)

    def test_rejects_row_not_in_original_missing_inventory(self):
        x = row("yahoo_chart_api_native")
        x["symbol"] = "6758"
        selected, audit, receipt = verify_and_select_supplements(
            inventory(), pd.DataFrame([x]), POLICY
        )
        self.assertTrue(selected.empty)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(audit.iloc[0]["acceptance"], "REJECT_NOT_IN_MISSING_INVENTORY")

    def test_unverified_stooq_is_not_formally_accepted(self):
        selected, audit, receipt = verify_and_select_supplements(
            inventory(),
            pd.DataFrame([row("stooq_intraday_candidate")]),
            POLICY,
        )
        self.assertTrue(selected.empty)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(audit.iloc[0]["acceptance"], "REJECT_SOURCE_NOT_FORMAL_ELIGIBLE")

    def test_alpha_vantage_free_is_daily_only(self):
        selected, audit, receipt = verify_and_select_supplements(
            inventory("1h"),
            pd.DataFrame([row("alpha_vantage_free", timeframe="1h")]),
            POLICY,
        )
        self.assertTrue(selected.empty)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(audit.iloc[0]["acceptance"], "REJECT_SOURCE_NOT_FORMAL_ELIGIBLE")

        selected2, _, receipt2 = verify_and_select_supplements(
            inventory("1d"),
            pd.DataFrame([row("alpha_vantage_free", timeframe="1d")]),
            POLICY,
        )
        self.assertEqual(receipt2["status"], "PASS")
        self.assertEqual(len(selected2), 1)

    def test_googlefinance_snapshot_never_becomes_intraday_ohlcv(self):
        selected, audit, receipt = verify_and_select_supplements(
            inventory(),
            pd.DataFrame([row("googlefinance_snapshot")]),
            POLICY,
        )
        self.assertTrue(selected.empty)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(audit.iloc[0]["acceptance"], "REJECT_SOURCE_NOT_FORMAL_ELIGIBLE")

    def test_conflicting_formal_sources_fail_closed(self):
        policy = dict(POLICY)
        policy["formal_alt"] = {
            "priority": 5,
            "formal_eligible": True,
            "allowed_timeframes": ["1h"],
        }
        rows = pd.DataFrame(
            [
                row("yahoo_chart_api_native", close=101.0, sha=SHA_A),
                row("formal_alt", close=101.5, sha=SHA_B),
            ]
        )
        selected, audit, receipt = verify_and_select_supplements(inventory(), rows, policy)
        self.assertTrue(selected.empty)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(receipt["conflicted_pair_n"], 1)
        self.assertTrue((audit["acceptance"] == "CONFLICT_FAIL_CLOSED").all())

    def test_agreeing_sources_use_frozen_priority_not_performance(self):
        policy = dict(POLICY)
        policy["formal_alt"] = {
            "priority": 5,
            "formal_eligible": True,
            "allowed_timeframes": ["1h"],
        }
        rows = pd.DataFrame(
            [
                row("formal_alt", close=101.0, sha=SHA_B),
                row("yahoo_chart_api_native", close=101.0, sha=SHA_A),
            ]
        )
        selected, audit, receipt = verify_and_select_supplements(inventory(), rows, policy)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(selected.iloc[0]["source"], "yahoo_chart_api_native")
        self.assertEqual(
            set(audit["acceptance"]), {"ACCEPT", "AGREEING_ALTERNATE_NOT_SELECTED"}
        )

    def test_invalid_ohlc_fails_before_selection(self):
        x = row("yahoo_chart_api_native")
        x["high"] = 98.0
        with self.assertRaisesRegex(ValueError, "high violates OHLC consistency"):
            verify_and_select_supplements(inventory(), pd.DataFrame([x]), POLICY)

    def test_future_market_timestamp_fails_before_selection(self):
        x = row("yahoo_chart_api_native")
        x["latest_market_ts"] = "2025-08-01T05:01:00Z"
        with self.assertRaisesRegex(ValueError, "latest_market_ts is after"):
            verify_and_select_supplements(inventory(), pd.DataFrame([x]), POLICY)


if __name__ == "__main__":
    unittest.main()
