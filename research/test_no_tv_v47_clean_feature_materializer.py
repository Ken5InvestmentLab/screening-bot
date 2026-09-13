from __future__ import annotations

import math
import tempfile
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
    d["identity_epoch"]=0
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
    out=v47.build_symbol_rows("X",raw,daily,{dt},sm,{})
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



def test_listing_epoch_prevents_prelisting_history_from_features_and_targets():
    dates=pd.bdate_range("2024-08-01",periods=140)
    daily=pd.DataFrame({
        "date":dates.strftime("%Y-%m-%d"),
        "open":np.linspace(90,120,len(dates)),
        "high":np.linspace(91,121,len(dates)),
        "low":np.linspace(89,119,len(dates)),
        "close":np.linspace(90.5,120.5,len(dates)),
        "volume":[20000]*len(dates),
        "symbol":["S"]*len(dates),
    })
    listing_date=daily.iloc[60]["date"]
    lmap={"S":[listing_date]}
    daily=v47.add_identity_epoch(daily,lmap)
    g=daily.groupby(["symbol","identity_epoch"],sort=False)
    daily["next_open"]=g["open"].shift(-1)
    daily["d5_close"]=g["close"].shift(-5)
    daily["exit_date_5bd"]=g["date"].shift(-5)

    # First post-listing days must not have enough identity-local history to
    # satisfy the 80-day technical minimum, despite abundant prelisting rows.
    dt=daily[daily["date"]>=listing_date].iloc[5]["date"]
    raw_dates=pd.bdate_range(pd.Timestamp(listing_date),periods=10)
    rows=[]
    for day in raw_dates:
        for hour in [9,10,13,14]:
            rows.append({
                "ts":pd.Timestamp(f"{day.strftime('%Y-%m-%d')} {hour}:00",tz="Asia/Tokyo"),
                "date":day.strftime("%Y-%m-%d"),
                "open":100.0,"high":102.0,"low":99.0,"close":101.0,"volume":6000.0,
            })
    raw=pd.DataFrame(rows)
    out=v47.build_symbol_rows("S",raw,daily,{dt},{},lmap)
    assert out.empty



def test_load_daily_restores_split_adjusted_volume_to_pit_scale():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        frozen=root/"frozen.csv"
        restored=root/"restored.csv"

        d=pd.DataFrame({
            "date":["2025-01-06","2025-01-07"],
            "open":[100.0,101.0],
            "high":[102.0,103.0],
            "low":[99.0,100.0],
            "close":[101.0,102.0],
            "volume":[50000.0,60000.0],
            "symbol":["X","X"],
        })
        d.to_csv(frozen,index=False)
        pd.DataFrame(columns=d.columns).to_csv(restored,index=False)

        split_map={"X":[("2025-04-01",10.0)]}
        out=v47.load_daily(frozen,restored,{},split_map)
        assert out["volume_adjusted"].tolist()==[50000.0,60000.0]
        assert out["volume"].tolist()==[5000.0,6000.0]
        assert out["future_split_factor_daily"].tolist()==[10.0,10.0]


def main():
    tests=[
        test_future_factor_boundary,
        test_build_symbol_rows_uses_nominal_log_price_and_canonical_target,
        test_enrich_arm_filters_policy_before_cross_section,
        test_listing_epoch_prevents_prelisting_history_from_features_and_targets,
        test_load_daily_restores_split_adjusted_volume_to_pit_scale,
    ]
    for fn in tests:
        fn(); print("PASS",fn.__name__)
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
