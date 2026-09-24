#!/usr/bin/env python3
"""Replay unchanged reconstructed Core and Monster gates on one raw 1H shard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from audit_core_canonical_endpoint import attach_canonical_label, make_fixed_core
from mtf_monster_model import make_candidate_pool
from reconstruct_4h_from_1h import load


def add_horizons(picks: pd.DataFrame, raw: pd.DataFrame, dates: list[str], entry_col: str) -> pd.DataFrame:
    daily = (raw.sort_values("timestamp").groupby(["symbol", "date"], as_index=False)
             .agg(outcome_close=("close", "last")))
    date_idx = {date: i for i, date in enumerate(dates)}
    out = picks.copy()
    for horizon in (10, 20, 40):
        target = {d: dates[i + horizon] if i + horizon < len(dates) else None
                  for d, i in date_idx.items()}
        key = f"exit{horizon}_date"
        out[key] = out["date"].map(target)
        out = out.merge(daily.rename(columns={"date": key, "outcome_close": f"exit{horizon}_close"}),
                        on=["symbol", key], how="left")
        out[f"ret{horizon}bd"] = out[f"exit{horizon}_close"] / out[entry_col] - 1.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    raw = load([args.input])
    raw = raw[(raw["date"] >= args.start) & (raw["date"] <= args.end)].copy()
    if raw.empty:
        raise SystemExit("no raw bars in fixed comparison period")
    dates = sorted(raw["date"].unique().tolist())
    core, _ = make_fixed_core(raw)
    core = attach_canonical_label(core, raw, dates)
    core = add_horizons(core, raw, dates, "entry_open")
    core["ret5bd"] = core["canonical_ret5bd"]
    core["lane"] = "Core"
    monster = make_candidate_pool(raw)
    monster = add_horizons(monster, raw, dates, "close")
    monster["lane"] = "Monster pool"
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    core.to_csv(out / "core.csv", index=False)
    monster.to_csv(out / "monster_pool.csv", index=False)
    meta = {"source": str(args.input), "source_sha256": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
            "start": args.start, "end": args.end, "market_dates_sha256": hashlib.sha256(
                "\n".join(dates).encode()).hexdigest(), "market_dates": len(dates),
            "raw_rows": len(raw), "raw_symbols": int(raw["symbol"].nunique()),
            "core_pre_cooldown_unavailable": True, "core_after_cooldown": len(core),
            "monster_pool_after_cooldown": len(monster)}
    (out / "extract_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
