from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

import no_tv_v47_dev_price_policy as v


def test_strict5_uses_actual_trading_index():
    d=pd.DataFrame({
        "date":["2025-01-06","2025-01-08","2025-01-13"],
        "session":[9,9,9],
        "symbol":["A","A","A"],
        "cons_min":[.99,.99,.99],
        "canonical_ret_5bd":[.1,.2,.3],
    })
    ix={x:i for i,x in enumerate([
        "2025-01-06","2025-01-07","2025-01-08",
        "2025-01-09","2025-01-10","2025-01-13",
    ])}
    out=v.strict5_no_replacement(d,ix)
    assert out["date"].tolist()==["2025-01-06","2025-01-13"]


def test_stats_subtracts_half_percent_cost():
    d=pd.DataFrame({
        "canonical_ret_5bd":[.10,.20,.00,.05],
        "symbol":["A","B","C","D"],
    })
    s=v.stats(d)
    assert s["n"]==4
    assert math.isclose(s["mean_net_0p5_pct"],8.25)


def test_development_evaluator_rejects_h2_rows_before_fit():
    d=pd.DataFrame({
        "date":["2025-07-01"],
        "canonical_ret_5bd":[.1],
        "exit_date_5bd":["2025-07-08"],
    })
    try:
        v.prequential_select(d,"NOCAP")
    except RuntimeError as e:
        assert "H2 rows supplied" in str(e)
        return
    raise AssertionError("expected H2 lock failure")



def test_strict5_does_not_cross_identity_epoch():
    d=pd.DataFrame({
        "date":["2025-01-06","2025-01-07"],
        "session":[9,9],
        "symbol":["A","A"],
        "identity_epoch":[0,1],
        "cons_min":[.99,.99],
        "canonical_ret_5bd":[.1,.2],
    })
    ix={"2025-01-06":0,"2025-01-07":1}
    out=v.strict5_no_replacement(d,ix)
    assert out["date"].tolist()==["2025-01-06","2025-01-07"]


def main():
    tests=[
        test_strict5_uses_actual_trading_index,
        test_stats_subtracts_half_percent_cost,
        test_development_evaluator_rejects_h2_rows_before_fit,
        test_strict5_does_not_cross_identity_epoch,
    ]
    for fn in tests:
        fn(); print("PASS",fn.__name__)
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
