#!/usr/bin/env python3
"""Compare OLD and JPX-wide Cloud with fixed gates and OLD-trained Monster models."""
from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from walkforward_4h_ensemble import (
    FOLDS, MIN_POS, MIN_TRAIN, TARGET, fit_ensemble, score_ensemble,
)

LANES = ("Core", "Monster Watch", "Monster Prime")
HORIZONS = (5, 10, 20, 40)
METRICS = ("mean", "median", "win", "ge10", "ge20", "le10", "max_up", "max_down")


def read_parts(pattern: str, filename: str) -> tuple[pd.DataFrame, list[dict]]:
    directory_pattern = pattern.rsplit("/", 1)[0]
    files = [Path(p) for p in sorted(glob.glob(directory_pattern + "/" + filename, recursive=True))]
    if not files:
        raise ValueError(f"no {filename} found: {pattern}")
    metas = []
    frames = []
    for file in files:
        meta = json.loads((file.parent / "extract_meta.json").read_text(encoding="utf-8"))
        metas.append(meta)
        frame = pd.read_csv(file, dtype={"symbol": "string", "date": "string"}, low_memory=False)
        frames.append(frame)
    hashes = {m["market_dates_sha256"] for m in metas}
    if len(hashes) != 1:
        raise ValueError("shards disagree on market dates; outcome labels are unsafe")
    result = pd.concat(frames, ignore_index=True, sort=False)
    if result.duplicated(["symbol", "date", "session"]).any():
        raise ValueError(f"duplicated candidates across shards: {filename}")
    return result, metas


def cohort(frame: pd.DataFrame, old_symbols: set[str], markets: dict[str, str]) -> pd.DataFrame:
    out = frame.copy()
    out["symbol"] = out["symbol"].astype(str)
    out["cohort"] = np.where(out["symbol"].isin(old_symbols),
                             np.where(out["symbol"].isin(markets), "retained_old", "old_not_current"),
                             "added")
    out["market"] = out["symbol"].map(markets).fillna("no_longer_listed")
    out["signal_month"] = out["date"].str[:7]
    price = pd.to_numeric(out["prev_daily_close"], errors="coerce")
    out["price_band"] = pd.cut(price, [-np.inf, 100, 300, 500, 1000, np.inf],
                               labels=["<=100", "101-300", "301-500", "501-1000", ">1000"])
    volume = pd.to_numeric(out["prev_daily_volume"], errors="coerce")
    out["liquidity_band"] = pd.cut(volume, [-np.inf, 10000, 50000, 100000, np.inf],
                                   labels=["<10000", "10000-49999", "50000-99999", ">=100000"],
                                   right=False)
    return out


def score_monster(train_old: pd.DataFrame, old: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    train_old = train_old.copy()
    old = old.copy()
    new = new.copy()
    train_old["date_dt"] = pd.to_datetime(train_old["date"])
    train_old["target_date_dt"] = pd.to_datetime(train_old["target_date"], errors="coerce")
    old["date_dt"] = pd.to_datetime(old["date"])
    new["date_dt"] = pd.to_datetime(new["date"])
    rows = []
    metadata = []
    for fold, start, end in FOLDS:
        start_dt, end_dt = pd.Timestamp(start), pd.Timestamp(end)
        train = train_old[(train_old["date_dt"] >= pd.Timestamp("2024-11-01"))
                          & (train_old["target_date_dt"] < start_dt) & train_old["ret5bd"].notna()].copy()
        pos = int((train["ret5bd"] >= TARGET).sum())
        neg = len(train) - pos
        if len(train) < MIN_TRAIN or pos < MIN_POS or neg < MIN_POS:
            raise ValueError(f"frozen OLD Monster fold cannot be trained: {fold} n={len(train)} pos={pos}")
        models, watch_thr, prime_thr = fit_ensemble(train)
        metadata.append({"fold": fold, "train_source": "OLD_only", "train_n": len(train),
                         "train_pos": pos, "watch_threshold": watch_thr, "prime_threshold": prime_thr})
        for label, source in (("OLD", old), ("NEW", new)):
            test = source[(source["date_dt"] >= start_dt) & (source["date_dt"] <= end_dt)].copy()
            if test.empty:
                continue
            test["ensemble_score"], test["score_std"] = score_ensemble(models, test)
            test["fold"] = fold
            for lane, threshold in (("Monster Watch", watch_thr), ("Monster Prime", prime_thr)):
                selected = test[test["ensemble_score"] >= threshold].copy()
                selected["lane"] = lane
                selected["universe"] = label
                rows.append(selected)
    if not rows:
        raise ValueError("no Monster selections")
    all_rows = pd.concat(rows, ignore_index=True, sort=False)
    return all_rows[all_rows["universe"] == "OLD"].copy(), all_rows[all_rows["universe"] == "NEW"].copy(), metadata


def metrics(frame: pd.DataFrame, horizon: int = 5) -> dict:
    key = f"ret{horizon}bd"
    x = pd.to_numeric(frame[key], errors="coerce").dropna()
    result = {"signals_after_cooldown": len(frame), "n": len(x), "unresolved": len(frame) - len(x),
              "signal_symbols": int(frame["symbol"].nunique())}
    for metric in METRICS:
        result[metric] = None
    if len(x):
        result.update({"mean": float(x.mean()), "median": float(x.median()),
                       "win": float((x > 0).mean()), "ge10": float((x >= .10).mean()),
                       "ge20": float((x >= .20).mean()), "le10": float((x <= -.10).mean()),
                       "max_up": float(x.max()), "max_down": float(x.min())})
    return result


def append_metrics(rows: list[dict], universe: str, lane: str, frame: pd.DataFrame,
                   slice_type: str, slice_value: str):
    for horizon in HORIZONS:
        rows.append({"universe": universe, "lane": lane, "slice_type": slice_type,
                     "slice_value": slice_value, "horizon_bd": horizon, **metrics(frame, horizon)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-extract", required=True, help="recursive glob matching extracted shard files")
    ap.add_argument("--new-extract", required=True)
    ap.add_argument("--old-symbols", required=True)
    ap.add_argument("--jpx-universe", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    old_syms = {s.strip() for s in Path(a.old_symbols).read_text(encoding="utf-8").splitlines()
                if s.strip() and not s.startswith("#")}
    with Path(a.jpx_universe).open(encoding="utf-8", newline="") as f:
        jpx = list(csv.DictReader(f))
    markets = {r["code"]: r["market"] for r in jpx}
    new_syms = set(markets)
    old_core_replay, old_meta = read_parts(a.old_extract, "core.csv")
    new_core, new_meta = read_parts(a.new_extract, "core.csv")
    old_pool_replay, _ = read_parts(a.old_extract, "monster_pool.csv")
    new_pool, _ = read_parts(a.new_extract, "monster_pool.csv")
    if len(old_meta) != 8 or len(new_meta) != 12:
        raise ValueError("expected exactly 8 OLD and 12 NEW shards")
    if old_meta[0]["market_dates_sha256"] != new_meta[0]["market_dates_sha256"]:
        raise ValueError("OLD and NEW market dates differ")
    # Retained names must use the very same Yahoo retrieval in both arms.
    # The pinned OLD artifact supplies only the 24 names absent from today's JPX list.
    def controlled_old(old_replay: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        retained = new[new["symbol"].astype(str).isin(old_syms)].copy()
        removed = old_replay[~old_replay["symbol"].astype(str).isin(new_syms)].copy()
        return pd.concat([retained, removed], ignore_index=True, sort=False)
    old_core = controlled_old(old_core_replay, new_core)
    old_pool = controlled_old(old_pool_replay, new_pool)
    if set(old_core["symbol"].astype(str)) - old_syms or set(new_core["symbol"].astype(str)) - new_syms:
        raise ValueError("Core candidates outside declared universe")
    if set(old_pool["symbol"].astype(str)) - old_syms or set(new_pool["symbol"].astype(str)) - new_syms:
        raise ValueError("Monster candidates outside declared universe")
    monster_old, monster_new, model_meta = score_monster(old_pool_replay, old_pool, new_pool)
    start, end = FOLDS[0][1], FOLDS[-1][2]
    core_old = old_core[(old_core["date"] >= start) & (old_core["date"] <= end)].copy()
    core_new = new_core[(new_core["date"] >= start) & (new_core["date"] <= end)].copy()
    core_old["lane"] = core_new["lane"] = "Core"
    core_old["universe"] = "OLD"
    core_new["universe"] = "NEW"
    picks = pd.concat([core_old, core_new, monster_old, monster_new], ignore_index=True, sort=False)
    picks = cohort(picks, old_syms, markets)
    rows = []
    for lane in LANES:
        for universe in ("OLD", "NEW"):
            source = picks[(picks["lane"] == lane) & (picks["universe"] == universe)].copy()
            append_metrics(rows, universe, lane, source, "all", "ALL")
            if universe == "NEW":
                for value in ("retained_old", "added"):
                    append_metrics(rows, universe, lane, source[source["cohort"] == value], "cohort", value)
            for column in ("signal_month", "market", "price_band", "liquidity_band"):
                for value, group in source.groupby(column, observed=True, dropna=False):
                    append_metrics(rows, universe, lane, group, column, str(value))
    comparison = pd.DataFrame(rows)
    overall = comparison[(comparison["slice_type"] == "all") & (comparison["horizon_bd"] == 5)]
    deltas = []
    for lane in LANES:
        old = overall[(overall["lane"] == lane) & (overall["universe"] == "OLD")].iloc[0]
        new = overall[(overall["lane"] == lane) & (overall["universe"] == "NEW")].iloc[0]
        delta = {"lane": lane, "delta_n": int(new["n"] - old["n"]),
                 "delta_signals_after_cooldown": int(new["signals_after_cooldown"] - old["signals_after_cooldown"])}
        for metric in METRICS:
            delta[f"delta_{metric}"] = float(new[metric] - old[metric]) if pd.notna(new[metric]) and pd.notna(old[metric]) else None
        deltas.append(delta)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(out / "comparison_metrics.csv", index=False)
    pd.DataFrame(deltas).to_csv(out / "comparison_deltas.csv", index=False)
    keep = ["universe", "lane", "cohort", "market", "symbol", "date", "session", "fold",
            "prev_daily_close", "prev_daily_volume", "volume", "ret5bd", "ret10bd", "ret20bd", "ret40bd"]
    picks[[c for c in keep if c in picks.columns]].to_csv(out / "selected_signals.csv", index=False)
    monster_hits = picks[(picks["universe"] == "NEW") & (picks["cohort"] == "added")
                         & (picks["lane"].str.startswith("Monster")) & (picks["ret5bd"] >= .20)]
    monster_hits[[c for c in keep if c in monster_hits.columns]].to_csv(out / "new_monster_hits_ge20.csv", index=False)
    drift = []
    for lane, replay, controlled in (("Core", old_core_replay, old_core),
                                     ("Monster pool", old_pool_replay, old_pool)):
        replay_keys = set(zip(replay["symbol"].astype(str), replay["date"].astype(str), replay["session"].astype(str)))
        controlled_keys = set(zip(controlled["symbol"].astype(str), controlled["date"].astype(str), controlled["session"].astype(str)))
        drift.append({"lane": lane, "old_artifact_candidates": len(replay),
                      "controlled_old_candidates": len(controlled),
                      "only_old_artifact": len(replay_keys - controlled_keys),
                      "only_controlled": len(controlled_keys - replay_keys)})
    pd.DataFrame(drift).to_csv(out / "source_retrieval_drift.csv", index=False)
    meta = {"old_symbols": len(old_syms), "new_symbols": len(new_syms),
            "retained_symbols": len(old_syms & new_syms), "added_symbols": len(new_syms - old_syms),
            "old_no_longer_listed": len(old_syms - new_syms), "test_start": start, "test_end": end,
            "input_start": "2024-10-01", "input_end": "2026-09-10", "model": "OLD trained fixed 7-seed 4H ensemble",
            "monster_model_folds": model_meta, "core": "unchanged fixed reconstructed gate, canonical next-open entry",
            "monster": "unchanged fixed reconstructed TAIL gate, signal-close entry",
            "outcome": "5BD close, 10/20/40BD supplementary close, gross cost 0",
            "controlled_old_source": "NEW fetch for retained symbols plus pinned OLD fetch for old-only symbols",
            "monster_training_source": "pinned OLD fetch only; model thresholds reused unchanged for controlled OLD and NEW",
            "post_result_tuning": False, "survivorship_bias_free": False}
    (out / "comparison_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    print(overall.to_string(index=False))
    print(pd.DataFrame(deltas).to_string(index=False))


if __name__ == "__main__":
    main()
