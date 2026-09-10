#!/usr/bin/env python3
"""Create a test-only reproducibility manifest for fixed-start TV-free research.

The manifest records dataset coverage plus SHA-256 fingerprints for rows at or
before a frozen historical cutoff. Later append-only runs can compare these
fingerprints: adding newer sessions should not alter the historical slices.

This tool does not write to production systems.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

OUT = Path("tvfree_screener/out")
CUTOFF = pd.Timestamp("2026-08-31")
FILES = [
    "v3_short_reconstruction_core.csv",
    "v3_short_reconstruction_defensive.csv",
    "v3_swing_v2_s_picks.csv",
]


def canonical_hash(path: Path, cutoff: pd.Timestamp) -> dict:
    if not path.exists():
        return {"exists": False}
    df = pd.read_csv(path, dtype={"symbol": str})
    if "date" not in df.columns:
        return {"exists": True, "rows": int(len(df)), "historical_hash": None, "note": "no date column"}
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    hist = df[df["date"] <= cutoff].copy()
    # Stable ordering and stable textual serialization for cross-run comparison.
    sort_cols = [c for c in ["date", "symbol", "model_period"] if c in hist.columns]
    if sort_cols:
        hist = hist.sort_values(sort_cols, kind="mergesort")
    payload = hist.to_csv(index=False, lineterminator="\n", float_format="%.12g").encode("utf-8")
    return {
        "exists": True,
        "rows": int(len(df)),
        "historical_rows": int(len(hist)),
        "historical_cutoff": cutoff.strftime("%Y-%m-%d"),
        "historical_sha256": hashlib.sha256(payload).hexdigest(),
        "min_date": None if df["date"].dropna().empty else df["date"].min().strftime("%Y-%m-%d"),
        "max_date": None if df["date"].dropna().empty else df["date"].max().strftime("%Y-%m-%d"),
    }


def cache_manifest(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    df = pd.read_csv(path, usecols=["date", "symbol"], dtype={"symbol": str})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    valid = df.dropna(subset=["date"])
    hist = valid[valid["date"] <= CUTOFF].sort_values(["date", "symbol"], kind="mergesort")
    payload = hist.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return {
        "exists": True,
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "min_date": None if valid.empty else valid["date"].min().strftime("%Y-%m-%d"),
        "max_date": None if valid.empty else valid["date"].max().strftime("%Y-%m-%d"),
        "historical_cutoff": CUTOFF.strftime("%Y-%m-%d"),
        "historical_rows": int(len(hist)),
        "historical_date_symbol_sha256": hashlib.sha256(payload).hexdigest(),
        "fixed_start_contract": "2022-01-01 -> current; symbols listed later naturally start later",
    }


def main() -> None:
    report = {
        "status": "research_only_no_production_writes",
        "purpose": "append-only reproducibility fingerprint",
        "cache": cache_manifest(OUT / "tse_daily.csv"),
        "outputs": {name: canonical_hash(OUT / name, CUTOFF) for name in FILES},
        "interpretation": "On later runs, historical hashes should remain unchanged unless Yahoo revises historical source data or research code/semantics intentionally changes.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "reproducibility_manifest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
