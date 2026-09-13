from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

EXPECTED_DAILY_SHA = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
EXPECTED_SYMBOL_COUNT = 1810
EXPECTED_SYMBOL_SHA = "2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b"
H1_START = "2025-03-01"
H1_END = "2025-06-30"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_universe(daily_path: Path) -> tuple[list[str], dict]:
    actual = sha256_file(daily_path)
    if actual != EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")

    d = pd.read_csv(
        daily_path,
        usecols=["date","symbol","close","volume"],
        dtype={"date":"string","symbol":"string"},
        low_memory=False,
    )
    d["date"] = d["date"].astype(str).str[:10]
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["volume"] = pd.to_numeric(d["volume"], errors="coerce")

    sessions = sorted(d["date"].dropna().unique().tolist())
    prior = {sessions[i]: sessions[i-1] for i in range(1,len(sessions))}
    h1_sessions = [x for x in sessions if H1_START <= x <= H1_END]

    eligible = set()
    daily_counts = {}
    by_date = {date:g for date,g in d.groupby("date",sort=False)}
    for signal_date in h1_sessions:
        pdate = prior.get(signal_date)
        if pdate is None:
            continue
        q = by_date[pdate]
        q = q[(q["close"] <= 1000) & (q["volume"] >= 10000)]
        syms = set(q["symbol"].dropna().astype(str))
        daily_counts[signal_date] = len(syms)
        eligible.update(syms)

    symbols = sorted(eligible)
    payload = "\n".join(symbols) + "\n"
    symbol_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    receipt = {
        "receipt_id":"V20-H1-ELIGIBLE-UNIVERSE-20260914",
        "canonical_daily_sha256":actual,
        "h1_start":H1_START,
        "h1_end":H1_END,
        "h1_official_sessions":len(h1_sessions),
        "unique_eligible_symbols":len(symbols),
        "min_eligible_symbols_per_session":min(daily_counts.values()) if daily_counts else None,
        "max_eligible_symbols_per_session":max(daily_counts.values()) if daily_counts else None,
        "symbol_list_sha256":symbol_sha,
        "eligibility":"prior completed daily close<=1000 and prior completed daily volume>=10000",
        "strategy_outcomes_read":False,
    }
    if len(symbols) != EXPECTED_SYMBOL_COUNT or symbol_sha != EXPECTED_SYMBOL_SHA:
        raise RuntimeError(
            f"universe receipt mismatch count={len(symbols)} sha={symbol_sha}"
        )
    return symbols, receipt


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily",required=True,type=Path)
    ap.add_argument("--symbols-output",required=True,type=Path)
    ap.add_argument("--receipt-output",required=True,type=Path)
    a=ap.parse_args()

    symbols,receipt=build_universe(a.daily)
    a.symbols_output.parent.mkdir(parents=True,exist_ok=True)
    a.receipt_output.parent.mkdir(parents=True,exist_ok=True)
    a.symbols_output.write_text("\n".join(symbols)+"\n",encoding="utf-8")
    a.receipt_output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
