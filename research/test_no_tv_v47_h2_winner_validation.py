from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

import no_tv_v47_h2_winner_validation as v


def test_attach_h2_labels_requires_and_matches_exit_date():
    blind=pd.DataFrame({
        "symbol":["A"],
        "date":["2025-07-01"],
        "exit_date_5bd":["2025-07-08"],
    })
    labels=pd.DataFrame({
        "symbol":["A"],
        "date":["2025-07-01"],
        "canonical_ret_5bd":[.1],
        "exit_date_calc":["2025-07-08"],
    })
    out=v.attach_h2_labels(blind,labels)
    assert out.loc[0,"canonical_ret_5bd"]==.1


def test_strict5_carries_development_state():
    dev=pd.DataFrame({
        "date":["2025-06-30"],
        "session":[13],
        "symbol":["A"],
    })
    h2=pd.DataFrame({
        "date":["2025-07-01","2025-07-07"],
        "session":[9,9],
        "symbol":["A","A"],
        "cons_min":[.99,.99],
        "canonical_ret_5bd":[.1,.2],
    })
    dates=[
        "2025-06-30","2025-07-01","2025-07-02",
        "2025-07-03","2025-07-04","2025-07-07",
    ]
    ix={d:i for i,d in enumerate(dates)}
    out=v.strict5_with_carry(h2,dev,ix)
    assert out["date"].tolist()==["2025-07-07"]


def main():
    tests=[
        test_attach_h2_labels_requires_and_matches_exit_date,
        test_strict5_carries_development_state,
    ]
    for fn in tests:
        fn(); print("PASS",fn.__name__)
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
