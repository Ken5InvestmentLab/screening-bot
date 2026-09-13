from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def main():
    tmp=Path("research_artifacts/test_v47_alias_shortlist")
    tmp.mkdir(parents=True,exist_ok=True)

    receipt={
        "restored_daily_fetch":{
            "missing_symbols":["8940","9999"]
        }
    }
    (tmp/"receipt.json").write_text(json.dumps(receipt),encoding="utf-8")

    events=pd.DataFrame([
        {"event_date":"2025-11-28","code":"8940","event":"delisting"},
        {"event_date":"2025-12-01","code":"463A","event":"listing"},
        # Keep the unrelated predecessor outside the frozen 10-calendar-day shortlist window.
        {"event_date":"2025-10-01","code":"9999","event":"delisting"},
        {"event_date":"2025-12-02","code":"7777","event":"listing"},
    ])
    events.to_csv(tmp/"events.csv",index=False)

    daily=pd.DataFrame({
        "date":["2025-11-20","2025-12-01","2025-11-20","2025-12-02"],
        "symbol":["463A","463A","7777","7777"],
    })
    # Only 463A has a row strictly before its listing date.
    daily.loc[daily["symbol"]=="7777","date"]=["2025-12-02","2025-12-03"]
    daily.to_csv(tmp/"daily.csv",index=False)

    out=tmp/"aliases.csv"
    subprocess.run([
        sys.executable,
        "research/propose_v47_identity_aliases.py",
        "--daily-receipt",str(tmp/"receipt.json"),
        "--membership-events",str(tmp/"events.csv"),
        "--frozen-daily",str(tmp/"daily.csv"),
        "--output",str(out),
    ],check=True)
    r=pd.read_csv(out,dtype=str)
    assert len(r)==1
    assert r.iloc[0]["predecessor_code"]=="8940"
    assert r.iloc[0]["successor_candidate_code"]=="463A"
    print("1/1 PASS")


if __name__=="__main__":
    main()
