from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

import no_tv_v47_clean_feature_materializer as v47


def make_daily():
    dates=pd.bdate_range("2024-08-01",periods=120)
    d=pd.DataFrame({
        "date":dates.strftime("%Y-%m-%d"),
        "open":np.linspace(90,110,len(dates)),
        "high":np.linspace(91,111,len(dates)),
        "low":np.linspace(89,109,len(dates)),
        "close":np.linspace(90.5,110.5,len(dates)),
        "volume":[20000]*len(dates),
    })
    d["next_open"]=d["open"].shift(-1)
    d["d5_close"]=d["close"].shift(-5)
    d["exit_date_5bd"]=d["date"].shift(-5)
    return d


def test_future_factor_boundary():
    sm={"X":[("2025-01-20",10.0),("2025-04-01",2.0)]}
    assert math.isclose(v47.future_factor(sm,"X","2025-01-19"),20.0)
    assert math.isclose(v47.future_factor(sm,"X","2025-01-20"),2.0)
    assert math.isclose(v47.future_factor(sm,"X","2025-04-01"),1.0)


def test_build_symbol_rows_uses_nominal_log_price_and_canonical_target():
    daily=make_daily()
    dt=daily.iloc[90]["date"]
    raw=pd.DataFrame({
        "ts":pd.to_datetime([
            f"{dt} 09:00:00+09:00",
            f"{dt} 10:00:00+09:00",
            f"{dt} 13:00:00+09:00",
            f"{dt} 14:00:00+09:00",
        ],utc=True).tz_convert("Asia/Tokyo"),
        "date":[dt]*4,
        "open":[100,101,102,103],
        "high":[102,103,104,105],
        "low":[99,100,101,102],
        "close":[101,102,103,104],
        "volume":[6000,7000,8000,9000],
    })
    sm={"X":[("2026-01-01",10.0)]}
    out=v47.build_symbol_rows("X",raw,daily,{dt},sm)
    assert len(out)==2
    first=out.sort_values("session").iloc[0]
    assert math.isclose(first["entry_pit"],first["entry_adjusted"]*10.0)
    assert math.isclose(first["log_price"],math.log(first["entry_pit"]))
    row=daily.set_index("date").loc[dt]
    expected=row["d5_close"]/row["next_open"]-1
    assert math.isclose(first["canonical_ret_5bd"],expected)
    assert first["exit_date_5bd"] == row["exit_date_5bd"]


def test_enrich_arm_filters_policy_before_cross_section():
    # Build a minimal valid frame with every v11 rank-base input already present.
    rows=[]
    for sym,val in [("A",1.0),("B",2.0),("C",3.0)]:
        rec={
            "date":"2025-01-06","session":9,"symbol":sym,
            "p_dummy":val,
        }
        # populate the base technical feature family with deterministic values
        import no_tv_v10_standalone as base
        import no_tv_v11_independent_selector as v11
        for i,c in enumerate(base.FEATURES):
            rec[c]=float(val+i/100)
        rec["stable_score"]=int(val)
        rows.append(rec)
    d=pd.DataFrame(rows)
    out=v47.enrich_arm(d,{("A","2025-01-06"),("C","2025-01-06")})
    assert set(out.symbol)=={"A","C"}
    assert out["market_candidate_count"].eq(2.0).all()


def main():
    tests=[
        test_future_factor_boundary,
        test_build_symbol_rows_uses_nominal_log_price_and_canonical_target,
        test_enrich_arm_filters_policy_before_cross_section,
    ]
    for fn in tests:
        fn(); print("PASS",fn.__name__)
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
