from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

import verify_consensus_v47_raw1h_coverage as v


def test_full_coverage_passes():
    req=pd.DataFrame({"symbol":["A","A","B"],"date":["2025-01-01","2025-01-02","2025-01-01"]})
    av=req.copy()
    st,miss=v.evaluate_arm(req,av,{"B"})
    assert st["accepted"] is True
    assert len(miss)==0


def test_missing_whole_symbol_fails():
    req=pd.DataFrame({"symbol":["A","A","B"],"date":["2025-01-01","2025-01-02","2025-01-01"]})
    av=req[req.symbol=="A"].copy()
    st,_=v.evaluate_arm(req,av,{"B"})
    assert st["accepted"] is False
    assert st["completely_missing_required_symbols"]==["B"]


def test_arm_required_subset():
    c=pd.DataFrame({
      "symbol":["A","B","C"],
      "date_s":["2025-01-01"]*3,
      "eligible_nocap_daily":[True,True,True],
      "eligible_cap1000_daily":[True,False,True],
    })
    n=v.arm_required(c,"eligible_nocap_daily")
    p=v.arm_required(c,"eligible_cap1000_daily")
    assert len(n)==3
    assert set(p.symbol)=={"A","C"}


def main():
    tests=[test_full_coverage_passes,test_missing_whole_symbol_fails,test_arm_required_subset]
    for fn in tests:
        fn(); print("PASS",fn.__name__)
    print(f"{len(tests)}/{len(tests)} PASS")


if __name__=="__main__":
    main()
