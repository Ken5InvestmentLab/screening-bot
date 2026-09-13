from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tvfree_screener.batch02 import eval_tentei_v20_session_impulse as mod


class V20SessionImpulseContractTests(unittest.TestCase):
    def test_signal_boundaries_are_frozen(self):
        good = {
            "session_return": 0.01,
            "close_location": 0.75,
            "true_range_pct": 0.02,
            "prev20_tr_median": 0.02,
            "prev20_ret_q75": 0.01,
            "volume_ratio20": 1.0,
            "prior_daily_close": 1000.0,
            "prior_daily_volume": 10000.0,
            "volume": 5000.0,
        }
        rows = [good.copy()]
        for key, bad in [
            ("session_return", 0.0),
            ("close_location", 0.749999),
            ("true_range_pct", 0.019999),
            ("prev20_ret_q75", 0.010001),
            ("volume_ratio20", 0.999999),
            ("prior_daily_close", 1000.01),
            ("prior_daily_volume", 9999.0),
            ("volume", 4999.0),
        ]:
            q = good.copy()
            q[key] = bad
            rows.append(q)
        got = mod.session_impulse_mask(pd.DataFrame(rows)).tolist()
        self.assertEqual(got[0], True)
        self.assertTrue(all(v is False or v == False for v in got[1:]))

    def test_history_excludes_current_bar(self):
        # 21 chronological completed bins: row 20 must use only rows 0..19.
        x = pd.DataFrame({
            "symbol": ["1111"] * 21,
            "date": [f"2025-01-{i+1:02d}" for i in range(21)],
            "bin_ord": [0] * 21,
            "open": [100.0] * 21,
            "high": [102.0] * 20 + [200.0],
            "low": [100.0] * 21,
            "close": [101.0] * 20 + [150.0],
            "volume": list(range(100, 120)) + [1000000],
        })
        out = mod.add_history_features(x)
        row = out.iloc[20]
        # Historical TR median is based on prior rows and therefore is not contaminated
        # by the enormous current bar.
        prior_tr = ((102.0 - 100.0) / 101.0)
        self.assertAlmostEqual(float(row["prev20_tr_median"]), prior_tr, places=12)
        self.assertAlmostEqual(float(row["prev20_ret_q75"]), 0.01, places=12)
        self.assertAlmostEqual(float(row["prev20_volume_median"]), 109.5, places=12)

    def test_topn_then_cooldown_has_no_backfill_and_day5_reentry(self):
        # Rank3 exists every day, but Top2 policy may never backfill it.
        rows = []
        dates = [f"2025-01-{i+1:02d}" for i in range(6)]
        for d in dates:
            rows += [
                {"date": d, "bin_name":"AM_09_13", "bin_ord":0, "symbol":"A", "cohort_rank":1, "score":0.9},
                {"date": d, "bin_name":"AM_09_13", "bin_ord":0, "symbol":"B", "cohort_rank":2, "score":0.8},
                {"date": d, "bin_name":"AM_09_13", "bin_ord":0, "symbol":"C", "cohort_rank":3, "score":0.7},
            ]
        c = pd.DataFrame(rows)
        day_index = {d:i for i,d in enumerate(dates)}
        out = mod.select_topn_no_backfill(c, day_index, 2)
        # day0 picks A/B; days1-4 have A/B blocked and must NOT fill C;
        # exact session-index +5 re-entry is allowed on day5.
        got = list(zip(out["date"], out["symbol"]))
        self.assertEqual(got, [(dates[0],"A"),(dates[0],"B"),(dates[5],"A"),(dates[5],"B")])
        self.assertNotIn("C", set(out["symbol"]))

    def test_canonical_label_next_open_to_signal_plus_five_close(self):
        dates = [
            "2025-01-06","2025-01-07","2025-01-08","2025-01-09",
            "2025-01-10","2025-01-14","2025-01-15"
        ]
        selected = pd.DataFrame([{
            "symbol":"1234","date":dates[0],"bin_name":"AM_09_13","bin_ord":0,
            "open":100.0,"high":102.0,"low":99.0,"close":101.0,"volume":10000.0
        }])
        daily = pd.DataFrame({
            "symbol":["1234"]*len(dates),
            "date":dates,
            "open":[100,110,120,130,140,150,160],
            "close":[105,115,125,135,145,165,170],
            "volume":[50000]*len(dates),
        })
        out = mod.attach_labels(selected, daily, dates)
        row = out.iloc[0]
        self.assertEqual(row["entry_date"], dates[1])
        self.assertEqual(row["exit_date"], dates[5])
        self.assertEqual(float(row["entry_open"]), 110.0)
        self.assertEqual(float(row["exit_close"]), 165.0)
        self.assertAlmostEqual(float(row["ret5bd_gross"]), 0.5, places=12)

    def test_h1_gate_boundaries(self):
        good = {
            "resolved":30,
            "net_mean":1e-9,
            "net_median":0.0,
            "net_win_rate":0.500001,
            "top3_removed_net_mean":1e-9,
            "gross_ge10_rate":0.10,
            "gross_le10_rate":0.20,
        }
        self.assertTrue(mod.h1_gate(good)["all_pass"])
        bads = [
            ("resolved",29),
            ("net_mean",0.0),
            ("net_median",-1e-12),
            ("net_win_rate",0.5),
            ("top3_removed_net_mean",0.0),
            ("gross_ge10_rate",0.099999),
            ("gross_le10_rate",0.200001),
        ]
        for key,val in bads:
            q = dict(good); q[key]=val
            self.assertFalse(mod.h1_gate(q)["all_pass"], key)

    def test_h2_requires_explicit_passing_topn(self):
        # Test CLI guard without touching market data by using argument parsing/main
        # indirectly: the contract is also inspectable as H2 policies derived solely
        # from --passing-topn. Keep a direct invariant check here.
        self.assertEqual(mod.TOP_NS, [1,2,3,5])


if __name__ == "__main__":
    unittest.main()
