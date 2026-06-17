#!/usr/bin/env python3
"""Experimental scoring logic explorer.

This is intentionally not wired into production workflows. It evaluates wider
logic shapes against the Mega validation report dataset after signal-candle
feature fixing:

- N-of-K score thresholds
- simple weighted scores
- parameter threshold-derived conditions
- multi walk-forward slices
- live/unconfirmed watch gates
- Mega40 OR branches
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

import generate_mega_validation_report as report
import optimize_screener as opt


MODE_DEFS = [
    {
        "id": "stable_s6",
        "eval_days": 5,
        "target": 0.10,
        "current": report.STABLE_CONDITIONS,
        "min_full": 20,
        "min_split": 3,
        "max_pool": 14,
        "sizes": (5, 6, 7),
        "thresholds": {5: (5, 4), 6: (6, 5), 7: (6, 5)},
        "seed": ["ich_chikou", "ich_price_kijun", "rsi5070", "stoch60"],
    },
    {
        "id": "sniper",
        "eval_days": 5,
        "target": 0.0,
        "current": report.SNIPER_CONDITIONS,
        "min_full": 15,
        "min_split": 2,
        "max_pool": 14,
        "sizes": (4, 5, 6),
        "thresholds": {4: (4, 3), 5: (5, 4), 6: (6, 5)},
        "seed": [
            "vol12",
            "vol15",
            "atr3",
            "hb20",
            "rsi5070",
            "rsi4060",
            "ich_chikou",
            "rci9_os",
            "rci26_os",
            "stoch75",
        ],
    },
    {
        "id": "mega5_rebound",
        "eval_days": 5,
        "target": 0.20,
        "current": next(c["conditions"] for c in report.CANDIDATES if c["id"] == "mega5_rebound"),
        "min_full": 8,
        "min_split": 1,
        "max_pool": 14,
        "sizes": (3, 4, 5, 6),
        "thresholds": {3: (3,), 4: (4, 3), 5: (4, 3), 6: (5, 4)},
        "seed": ["stoch75", "ich_chikou", "rsi5070", "rsi4060", "ich_price_kijun", "vol12"],
    },
    {
        "id": "mega40_deep_reversal",
        "eval_days": 40,
        "target": 0.30,
        "current": next(c["conditions"] for c in report.CANDIDATES if c["id"] == "mega40_deep_reversal"),
        "min_full": 8,
        "min_split": 1,
        "max_pool": 14,
        "sizes": (3, 4, 5, 6),
        "thresholds": {3: (3,), 4: (4, 3), 5: (4, 3), 6: (5, 4)},
        "seed": ["macdgc", "gap_up", "atr5", "stoch75", "vol30", "ich_tk", "ich_price_tenkan"],
    },
    {
        "id": "mega40_wick_recovery",
        "eval_days": 40,
        "target": 0.50,
        "current": next(c["conditions"] for c in report.CANDIDATES if c["id"] == "mega40_wick_recovery"),
        "min_full": 5,
        "min_split": 1,
        "max_pool": 14,
        "sizes": (3, 4, 5, 6),
        "thresholds": {3: (3,), 4: (4, 3), 5: (4, 3), 6: (5, 4)},
        "seed": ["macdgc", "gap_up", "atr5", "vol30", "stoch75", "stoch60", "ich_tk"],
    },
]


@dataclass(frozen=True)
class Candidate:
    kind: str
    conditions: tuple[str, ...]
    threshold: int
    weights: tuple[int, ...] = ()
    branch: tuple["Candidate", "Candidate"] | None = None

    @property
    def label(self) -> str:
        if self.branch:
            return f"or({self.branch[0].label})|({self.branch[1].label})"
        if self.kind == "weighted":
            pairs = ",".join(f"{c}:{w}" for c, w in zip(self.conditions, self.weights))
            return f"weighted>={self.threshold}[{pairs}]"
        return f"{self.kind}>={self.threshold}/{len(self.conditions)}[{','.join(self.conditions)}]"


def is_finite(value) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def pct(value) -> str:
    return "NA" if not is_finite(value) else f"{float(value) * 100:.1f}%"


def add_perf_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for days in (5, 10, 20, 40):
        price_col = f"price_{days}bd"
        perf_col = f"perf_{days}bd"
        existing = (
            pd.to_numeric(frame[perf_col], errors="coerce")
            if perf_col in frame.columns
            else pd.Series(np.nan, index=frame.index)
        )
        if price_col in frame.columns:
            price = pd.to_numeric(frame[price_col], errors="coerce")
            entry = pd.to_numeric(frame.get("entry", np.nan), errors="coerce")
            computed = pd.Series(
                np.where(np.isfinite(price) & np.isfinite(entry) & (entry > 0), price / entry - 1.0, np.nan),
                index=frame.index,
            )
        else:
            computed = pd.Series(np.nan, index=frame.index)
        frame[perf_col] = existing.where(np.isfinite(existing), computed)
    frame["signal_dt"] = pd.to_datetime(frame.get("signal_dt", frame.get("date")), errors="coerce")
    return frame


def add_threshold_conditions(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    frame = frame.copy()
    created: list[str] = []

    def add(name: str, series):
        frame[name] = series.fillna(False).astype(bool)
        created.append(name)

    specs = [
        ("_body", "body_ge", ">=", [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]),
        ("_atr", "atr_lt", "<", [3.0, 5.0, 7.0, 10.0]),
        ("_stoch", "stoch_ge", ">=", [40, 50, 60, 70, 75, 80]),
        ("_bbpct", "bbpct_ge", ">=", [0.50, 0.65, 0.80, 0.90]),
        ("_bbpct", "bbpct_le", "<=", [0.20, 0.35]),
        ("_rci9", "rci9_le", "<=", [-80, -70, -60, -50, -40]),
        ("_rci26", "rci26_le", "<=", [-80, -70, -60, -50, -40]),
        ("_cci", "cci_le", "<=", [-200, -150, -100, -50]),
        ("_vsurge", "vsurge_ge", ">=", [1.0, 1.2, 1.5, 2.0]),
    ]
    for raw_col, prefix, op, values in specs:
        if raw_col not in frame.columns:
            continue
        values_series = pd.to_numeric(frame[raw_col], errors="coerce")
        for threshold in values:
            suffix = str(threshold).replace("-", "m").replace(".", "p")
            name = f"{prefix}_{suffix}"
            if op == ">=":
                add(name, values_series >= threshold)
            elif op == "<=":
                add(name, values_series <= threshold)
            else:
                add(name, values_series < threshold)
    return frame, created


def stats(mask: np.ndarray, perf: np.ndarray, target: float) -> dict:
    vals = perf[np.asarray(mask, dtype=bool) & np.isfinite(perf)]
    n = int(vals.size)
    if n == 0:
        return {"n": 0, "avg": np.nan, "wr": np.nan, "hits": 0, "rate": 0.0, "m10": 0}
    decisive = vals[vals != 0]
    hits = int(np.sum(vals >= target))
    return {
        "n": n,
        "avg": float(vals.mean()),
        "wr": float(np.mean(decisive > 0)) if decisive.size else np.nan,
        "hits": hits,
        "rate": float(hits / n),
        "m10": int(np.sum(vals <= -0.10)),
    }


def fmt_stats(item: dict) -> str:
    return (
        f"n={item['n']} avg={pct(item['avg'])} win={pct(item['wr'])} "
        f"target={item['hits']}/{pct(item['rate'])} m10={item['m10']}"
    )


def split_frames(frame: pd.DataFrame, perf_col: str) -> dict[str, pd.DataFrame]:
    perf = pd.to_numeric(frame[perf_col], errors="coerce")
    confirmed = frame[np.isfinite(perf)].copy()
    confirmed = confirmed.sort_values(["signal_dt", "symbol", "alert_id"], na_position="last").reset_index(drop=True)
    n = len(confirmed)
    return {
        "all": confirmed,
        "train": confirmed.iloc[: int(n * 0.60)].copy(),
        "valid": confirmed.iloc[int(n * 0.60) : int(n * 0.80)].copy(),
        "lock": confirmed.iloc[int(n * 0.80) :].copy(),
    }


def walk_forward_slices(confirmed: pd.DataFrame, min_slice: int = 80) -> list[pd.DataFrame]:
    n = len(confirmed)
    if n < min_slice * 2:
        return []
    slices = []
    for start_frac in (0.45, 0.55, 0.65, 0.75):
        start = int(n * start_frac)
        end = min(n, start + max(min_slice, int(n * 0.12)))
        if end > start:
            slices.append(confirmed.iloc[start:end].copy())
    return slices


def arrays(df: pd.DataFrame, columns: list[str], perf_col: str) -> dict:
    return {
        "matrix": df[columns].to_numpy(dtype=np.bool_) if len(df) else np.zeros((0, len(columns)), dtype=np.bool_),
        "perf": pd.to_numeric(df[perf_col], errors="coerce").to_numpy(dtype=float) if len(df) else np.array([], dtype=float),
    }


def candidate_mask(matrix: np.ndarray, candidate: Candidate, col_index: dict[str, int]) -> np.ndarray:
    if candidate.branch:
        return candidate_mask(matrix, candidate.branch[0], col_index) | candidate_mask(matrix, candidate.branch[1], col_index)
    idxs = [col_index[c] for c in candidate.conditions]
    if not idxs:
        return np.ones(matrix.shape[0], dtype=bool)
    sub = matrix[:, idxs].astype(np.int16)
    if candidate.kind == "weighted":
        weights = np.array(candidate.weights, dtype=np.int16)
        return (sub * weights).sum(axis=1) >= candidate.threshold
    return sub.sum(axis=1) >= candidate.threshold


def evaluate(candidate: Candidate, arr_by_split: dict[str, dict], fold_arrs: list[dict], watch_arr: dict, col_index: dict[str, int], target: float) -> dict:
    out = {}
    for name, arr in arr_by_split.items():
        out[name] = stats(candidate_mask(arr["matrix"], candidate, col_index), arr["perf"], target)
    out["watch"] = stats(candidate_mask(watch_arr["matrix"], candidate, col_index), watch_arr["perf"], 0.0)
    out["folds"] = [
        stats(candidate_mask(arr["matrix"], candidate, col_index), arr["perf"], target)
        for arr in fold_arrs
    ]
    return out


def stable_score(row: pd.Series) -> int:
    return sum(1 for cond in report.STABLE_CONDITIONS if bool(row.get(cond, False)))


def row_key(row: pd.Series) -> tuple:
    alert_id = str(row.get("alert_id", "") or "").strip()
    if alert_id:
        return ("id", alert_id)
    return ("symbol_date", str(row.get("symbol", "")), str(row.get("date", ""))[:10])


def row_summary(row: pd.Series, perf_col: str) -> dict:
    perf = row.get(perf_col)
    confirmed = is_finite(perf)
    if not confirmed:
        perf = row.get("cur_perf")
    return {
        "symbol": str(row.get("symbol", "")),
        "name": str(row.get("name", "")),
        "date": str(row.get("date", ""))[:10],
        "status": "confirmed" if confirmed else "watch",
        "perf": float(perf) if is_finite(perf) else None,
        "perf_text": pct(perf),
        "stable_star": stable_score(row),
        "alert_id": str(row.get("alert_id", "") or ""),
    }


def selected_rows(frame: pd.DataFrame, candidate: Candidate, columns: list[str], perf_col: str) -> list[dict]:
    col_index = {col: idx for idx, col in enumerate(columns)}
    matrix = frame[columns].to_numpy(dtype=np.bool_) if len(frame) else np.zeros((0, len(columns)), dtype=np.bool_)
    mask = candidate_mask(matrix, candidate, col_index)
    rows = frame[mask].copy()
    if "signal_dt" in rows.columns:
        rows = rows.sort_values(["signal_dt", "symbol"], ascending=[False, True], na_position="last")
    return [row_summary(row, perf_col) for _, row in rows.iterrows()]


def row_diffs(current_rows: list[dict], candidate_rows: list[dict]) -> dict:
    def key(item: dict) -> tuple:
        alert_id = str(item.get("alert_id", "") or "").strip()
        if alert_id:
            return ("id", alert_id)
        return ("symbol_date", item.get("symbol", ""), item.get("date", ""))

    current_by_key = {key(item): item for item in current_rows}
    candidate_by_key = {key(item): item for item in candidate_rows}
    added_keys = [k for k in candidate_by_key if k not in current_by_key]
    removed_keys = [k for k in current_by_key if k not in candidate_by_key]
    common_keys = [k for k in candidate_by_key if k in current_by_key]
    return {
        "added": [candidate_by_key[k] for k in added_keys],
        "removed": [current_by_key[k] for k in removed_keys],
        "common": [candidate_by_key[k] for k in common_keys],
    }


def condition_pool(
    splits: dict[str, pd.DataFrame],
    columns: list[str],
    perf_col: str,
    target: float,
    current: Iterable[str],
    seed: Iterable[str],
    max_pool: int,
) -> list[str]:
    scored = []
    for col in columns:
        all_stats = stats(splits["all"][col].to_numpy(dtype=bool), pd.to_numeric(splits["all"][perf_col], errors="coerce").to_numpy(dtype=float), target)
        valid_stats = stats(splits["valid"][col].to_numpy(dtype=bool), pd.to_numeric(splits["valid"][perf_col], errors="coerce").to_numpy(dtype=float), target)
        lock_stats = stats(splits["lock"][col].to_numpy(dtype=bool), pd.to_numeric(splits["lock"][perf_col], errors="coerce").to_numpy(dtype=float), target)
        if all_stats["n"] < 12:
            continue
        score = (
            lock_stats["rate"] * 3
            + valid_stats["rate"] * 2
            + all_stats["rate"]
            + (lock_stats["avg"] if is_finite(lock_stats["avg"]) else -1.0)
            + (valid_stats["avg"] if is_finite(valid_stats["avg"]) else -1.0)
        )
        scored.append((score, col))
    scored.sort(reverse=True)
    pool = []
    for col in itertools.chain(current, seed):
        if col in columns and col not in pool:
            pool.append(col)
    for _, col in scored:
        if col not in pool:
            pool.append(col)
        if len(pool) >= max_pool:
            break
    return pool


def gate(metrics: dict, current_metrics: dict, mode: dict) -> tuple[bool, tuple]:
    full = metrics["all"]
    valid = metrics["valid"]
    lock = metrics["lock"]
    watch = metrics["watch"]
    current_watch = current_metrics["watch"]

    if full["n"] < mode["min_full"] or full["hits"] < 1:
        return False, ()
    if valid["n"] < mode["min_split"] or lock["n"] < mode["min_split"]:
        return False, ()
    if valid["avg"] < -0.03 or lock["avg"] < -0.03:
        return False, ()
    if current_watch["n"] and watch["n"]:
        if watch["m10"] > current_watch["m10"]:
            return False, ()
        if is_finite(watch["avg"]) and is_finite(current_watch["avg"]) and watch["avg"] < current_watch["avg"] - 0.02:
            return False, ()

    fold_stats = [s for s in metrics["folds"] if s["n"] > 0]
    fold_passes = sum(1 for s in fold_stats if s["avg"] >= -0.02 and s["rate"] > 0)
    fold_ratio = fold_passes / len(fold_stats) if fold_stats else 0.0
    if fold_stats and fold_ratio < 0.50:
        return False, ()

    if mode["id"] == "sniper":
        full_wr = full["wr"] if is_finite(full["wr"]) else -1.0
        valid_wr = valid["wr"] if is_finite(valid["wr"]) else -1.0
        lock_wr = lock["wr"] if is_finite(lock["wr"]) else -1.0
        rank = (
            full_wr,
            full["rate"],
            valid_wr,
            valid["rate"],
            -full["m10"],
            full["avg"],
            valid["avg"],
            min(full["n"], 30) / 30.0,
            min(valid["n"], 10) / 10.0,
            min(lock["n"], 5) / 5.0,
            lock_wr,
            lock["avg"],
            -watch["m10"],
            watch["avg"] if is_finite(watch["avg"]) else -9.0,
        )
        return True, rank

    rank = (
        fold_ratio,
        lock["rate"],
        lock["avg"],
        valid["rate"],
        valid["avg"],
        -watch["m10"],
        watch["avg"] if is_finite(watch["avg"]) else -9.0,
        full["rate"],
        full["avg"],
        min(full["n"], 100),
    )
    return True, rank


def weight_for_condition(name: str, single_scores: dict[str, float]) -> int:
    score = single_scores.get(name, 0.0)
    return 2 if score >= 0.0 else 1


def candidate_signature(candidate: Candidate) -> tuple:
    if (
        not candidate.branch
        and candidate.kind in ("and", "score")
        and candidate.threshold == len(candidate.conditions)
    ):
        return ("all", tuple(candidate.conditions))
    if (
        not candidate.branch
        and candidate.kind == "weighted"
        and candidate.weights
        and candidate.threshold >= sum(candidate.weights)
    ):
        return ("all", tuple(candidate.conditions))
    return (
        candidate.kind,
        tuple(candidate.conditions),
        candidate.threshold,
        tuple(candidate.weights),
        tuple(candidate_signature(item) for item in candidate.branch) if candidate.branch else (),
    )


def choose_decision(mode_id: str, current: dict, top_items: list[dict]) -> dict:
    if not top_items:
        return {
            "action": "keep_current",
            "reason": "No candidate passed the adoption gate.",
            "candidate_label": None,
        }

    top = top_items[0]
    current_metrics = current["metrics"]
    candidate_metrics = top["metrics"]
    current_candidate = current["candidate"]
    candidate = top["candidate"]

    if candidate_signature(candidate) == candidate_signature(current_candidate):
        return {
            "action": "keep_current",
            "reason": "The best-ranked candidate is the current logic.",
            "candidate_label": candidate.label,
        }

    full = candidate_metrics["all"]
    valid = candidate_metrics["valid"]
    watch = candidate_metrics["watch"]
    cur_full = current_metrics["all"]
    cur_valid = current_metrics["valid"]
    cur_watch = current_metrics["watch"]

    if mode_id == "sniper":
        full_wr = full["wr"] if is_finite(full["wr"]) else -1.0
        valid_wr = valid["wr"] if is_finite(valid["wr"]) else -1.0
        cur_full_wr = cur_full["wr"] if is_finite(cur_full["wr"]) else -1.0
        cur_valid_wr = cur_valid["wr"] if is_finite(cur_valid["wr"]) else -1.0
        watch_ok = (not cur_watch["n"] or not watch["n"] or watch["m10"] <= cur_watch["m10"])
        high_quality = (
            full["n"] >= 15
            and full_wr >= 0.80
            and full["rate"] >= 0.80
            and valid["n"] >= 5
            and valid_wr >= 0.75
            and valid["rate"] >= 0.75
            and full["m10"] <= cur_full["m10"]
            and watch_ok
        )
        improves_current = (
            full_wr > cur_full_wr + 0.05
            and valid_wr >= max(0.75, cur_valid_wr)
            and full["avg"] >= cur_full["avg"]
        )
        if high_quality and improves_current:
            return {
                "action": "adopt_candidate",
                "reason": "Sniper prioritizes high confirmed win rate, validation win rate, limited drawdowns, and no watch deterioration.",
                "candidate_label": candidate.label,
            }

    full_better = (
        full["n"] >= cur_full["n"]
        and full["wr"] > cur_full["wr"]
        and full["avg"] > cur_full["avg"]
        and full["m10"] <= cur_full["m10"]
    )
    valid_better = (
        valid["n"] >= cur_valid["n"]
        and valid["wr"] >= cur_valid["wr"]
        and valid["avg"] >= cur_valid["avg"]
    )
    watch_ok = (not cur_watch["n"] or not watch["n"] or watch["m10"] <= cur_watch["m10"])
    if full_better and valid_better and watch_ok:
        return {
            "action": "adopt_candidate",
            "reason": "Candidate improves confirmed and validation performance without worsening watch drawdowns.",
            "candidate_label": candidate.label,
        }

    return {
        "action": "keep_current",
        "reason": "Best candidate did not clear the adoption decision rule.",
        "candidate_label": candidate.label,
    }


def search_mode(frame: pd.DataFrame, mode: dict, columns: list[str]) -> dict:
    perf_col = f"perf_{mode['eval_days']}bd"
    target = float(mode["target"])
    splits = split_frames(frame, perf_col)
    watch_mask = np.isnan(pd.to_numeric(frame[perf_col], errors="coerce")) & np.isfinite(pd.to_numeric(frame["cur_perf"], errors="coerce"))
    watch_df = frame[watch_mask].copy()
    folds = walk_forward_slices(splits["all"])

    pool = condition_pool(splits, columns, perf_col, target, mode["current"], mode.get("seed", []), mode["max_pool"])
    col_index = {col: idx for idx, col in enumerate(columns)}
    arr_by_split = {name: arrays(df, columns, perf_col) for name, df in splits.items()}
    fold_arrs = [arrays(df, columns, perf_col) for df in folds]
    watch_arr = arrays(watch_df, columns, "cur_perf")

    current = Candidate("and", tuple(c for c in mode["current"] if c in col_index), len([c for c in mode["current"] if c in col_index]))
    current_metrics = evaluate(current, arr_by_split, fold_arrs, watch_arr, col_index, target)

    single_scores = {}
    for col in pool:
        candidate = Candidate("and", (col,), 1)
        m = evaluate(candidate, arr_by_split, fold_arrs, watch_arr, col_index, target)
        single_scores[col] = m["lock"]["rate"] + m["valid"]["rate"] + m["lock"]["avg"] + m["valid"]["avg"]

    candidates: list[tuple[tuple, Candidate, dict]] = []
    pool_tuple = tuple(pool)
    for size in mode["sizes"]:
        if size > len(pool_tuple):
            continue
        thresholds = mode["thresholds"].get(size, (size,))
        for conds in itertools.combinations(pool_tuple, size):
            for threshold in thresholds:
                candidate = Candidate("score", conds, threshold)
                metrics = evaluate(candidate, arr_by_split, fold_arrs, watch_arr, col_index, target)
                ok, rank = gate(metrics, current_metrics, mode)
                if ok:
                    candidates.append((rank, candidate, metrics))

                weights = tuple(weight_for_condition(c, single_scores) for c in conds)
                max_weight = sum(weights)
                for weighted_threshold in sorted({max_weight, max_weight - 1, max(1, math.ceil(max_weight * 0.75))}, reverse=True):
                    weighted = Candidate("weighted", conds, int(weighted_threshold), weights)
                    weighted_metrics = evaluate(weighted, arr_by_split, fold_arrs, watch_arr, col_index, target)
                    ok, rank = gate(weighted_metrics, current_metrics, mode)
                    if ok:
                        candidates.append((rank, weighted, weighted_metrics))
        candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = candidates[:300]

    candidates.sort(key=lambda x: x[0], reverse=True)
    current_rows = selected_rows(frame, current, columns, perf_col)
    top_items = []
    for rank, candidate, metrics in candidates[:10]:
        rows = selected_rows(frame, candidate, columns, perf_col)
        diff = row_diffs(current_rows, rows)
        top_items.append({
            "rank": rank,
            "candidate": candidate,
            "metrics": metrics,
            "rows": rows,
            "diff": diff,
        })
    decision = choose_decision(mode["id"], {"candidate": current, "metrics": current_metrics}, top_items)
    return {
        "mode": mode["id"],
        "splits": {name: len(df) for name, df in splits.items()},
        "folds": [len(df) for df in folds],
        "pool": pool,
        "current": {"candidate": current, "metrics": current_metrics, "rows": current_rows},
        "top": top_items,
        "decision": decision,
    }


def make_mega40_or(deep_result: dict, wick_result: dict, frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    mode = {
        "id": "mega40_or",
        "eval_days": 40,
        "target": 0.30,
        "current": [],
        "min_full": 8,
        "min_split": 1,
    }
    perf_col = "perf_40bd"
    target = 0.30
    splits = split_frames(frame, perf_col)
    watch_mask = np.isnan(pd.to_numeric(frame[perf_col], errors="coerce")) & np.isfinite(pd.to_numeric(frame["cur_perf"], errors="coerce"))
    watch_df = frame[watch_mask].copy()
    folds = walk_forward_slices(splits["all"])
    col_index = {col: idx for idx, col in enumerate(columns)}
    arr_by_split = {name: arrays(df, columns, perf_col) for name, df in splits.items()}
    fold_arrs = [arrays(df, columns, perf_col) for df in folds]
    watch_arr = arrays(watch_df, columns, "cur_perf")

    current_deep = deep_result["current"]["candidate"]
    current_wick = wick_result["current"]["candidate"]
    current = Candidate("or", (), 0, branch=(current_deep, current_wick))
    current_metrics = evaluate(current, arr_by_split, fold_arrs, watch_arr, col_index, target)

    results = []
    for deep in deep_result["top"][:5]:
        for wick in wick_result["top"][:5]:
            candidate = Candidate("or", (), 0, branch=(deep["candidate"], wick["candidate"]))
            metrics = evaluate(candidate, arr_by_split, fold_arrs, watch_arr, col_index, target)
            ok, rank = gate(metrics, current_metrics, mode)
            if ok:
                results.append({"rank": rank, "candidate": candidate, "metrics": metrics})
    results.sort(key=lambda x: x["rank"], reverse=True)
    return [{"current": current_metrics, **item} for item in results[:10]]


def build_frame(use_cache: bool) -> pd.DataFrame:
    cache_path = os.path.join(tempfile.gettempdir(), "screening_signal_candle_frame_explore.pkl")
    if use_cache and os.path.exists(cache_path):
        return pd.read_pickle(cache_path)
    frame, _, meta = report.build_alert_frame(include_unconfirmed=True)
    frame = add_perf_columns(frame)
    frame, derived = add_threshold_conditions(frame)
    for cond in opt.BOOL_CONDS:
        if cond in frame.columns:
            frame[cond] = frame[cond].astype(bool)
        else:
            frame[cond] = False
    frame.attrs["meta"] = meta
    frame.attrs["derived_conditions"] = derived
    frame.to_pickle(cache_path)
    return frame


def serializable_candidate(item) -> dict:
    if isinstance(item, Candidate):
        return {
            "kind": item.kind,
            "conditions": list(item.conditions),
            "threshold": item.threshold,
            "weights": list(item.weights),
            "label": item.label,
            "branch": [serializable_candidate(x) for x in item.branch] if item.branch else None,
        }
    return item


def fmt_rows(rows: list[dict], limit: int = 20) -> str:
    if not rows:
        return "(none)"
    shown = [
        f"{r['symbol']}({r['date']} {r['perf_text']} {r['status']} S{r['stable_star']})"
        for r in rows[:limit]
    ]
    if len(rows) > limit:
        shown.append(f"...+{len(rows) - limit}")
    return ", ".join(shown)


def fmt_pct_value(value, digits: int = 1) -> str:
    if not is_finite(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def html_escape(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def html_stats(metrics: dict) -> str:
    return (
        f"件数 {int(metrics.get('n') or 0)} / "
        f"平均 {fmt_pct_value(metrics.get('avg'))} / "
        f"勝率 {fmt_pct_value(metrics.get('wr'))} / "
        f"目標 {int(metrics.get('hits') or 0)}/{fmt_pct_value(metrics.get('rate'))} / "
        f"-10%以下 {int(metrics.get('m10') or 0)}"
    )


def html_rows_table(rows: list[dict], title: str) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html_escape(row.get('symbol'))}</td>"
            f"<td>{html_escape(row.get('name'))}</td>"
            f"<td>{html_escape(row.get('date'))}</td>"
            f"<td>{html_escape(row.get('status'))}</td>"
            f"<td>{html_escape(row.get('stable_star'))}</td>"
            f"<td>{html_escape(row.get('perf_text'))}</td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="6" class="muted">なし</td></tr>')
    return (
        f"<h4>{html_escape(title)} <span>{len(rows)}件</span></h4>"
        "<div class=\"table-wrap\"><table>"
        "<thead><tr><th>コード</th><th>銘柄名</th><th>シグナル日</th><th>状態</th><th>Stable★</th><th>騰落</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def html_mode_section(result: dict) -> str:
    current = result["current"]
    top = result["top"][0] if result["top"] else None
    decision = result.get("decision", {})
    parts = [
        f"<section><h2>{html_escape(result['mode'])}</h2>",
        (
            f"<p class=\"decision\">判断: <strong>{html_escape(decision.get('action', '-'))}</strong>"
            f" / {html_escape(decision.get('reason', ''))}</p>"
        ),
        "<div class=\"cards\">",
        "<article>",
        "<h3>現行ロジック</h3>",
        f"<p class=\"logic\">{html_escape(current['candidate'].label)}</p>",
        f"<p>{html_stats(current['metrics']['all'])}</p>",
        f"<p class=\"muted\">検証 {html_stats(current['metrics']['valid'])}</p>",
        f"<p class=\"muted\">Lockbox {html_stats(current['metrics']['lock'])}</p>",
        f"<p class=\"muted\">未確定 {html_stats(current['metrics']['watch'])}</p>",
        "</article>",
    ]
    if top:
        parts.extend(
            [
                "<article>",
                "<h3>最上位候補</h3>",
                f"<p class=\"logic\">{html_escape(top['candidate'].label)}</p>",
                f"<p>{html_stats(top['metrics']['all'])}</p>",
                f"<p class=\"muted\">検証 {html_stats(top['metrics']['valid'])}</p>",
                f"<p class=\"muted\">Lockbox {html_stats(top['metrics']['lock'])}</p>",
                f"<p class=\"muted\">未確定 {html_stats(top['metrics']['watch'])}</p>",
                "</article>",
            ]
        )
    parts.append("</div>")
    parts.append(html_rows_table(current.get("rows", []), "現行銘柄"))
    if top:
        diff = top.get("diff", {})
        parts.append(html_rows_table(top.get("rows", []), "候補銘柄"))
        parts.append('<div class="diff-grid">')
        parts.append(html_rows_table(diff.get("added", []), "候補で追加"))
        parts.append(html_rows_table(diff.get("removed", []), "候補で除外"))
        parts.append(html_rows_table(diff.get("common", []), "共通"))
        parts.append("</div>")
    parts.append("</section>")
    return "\n".join(parts)


def write_html_report(path: str, results: list[dict]) -> None:
    generated = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = "\n".join(html_mode_section(result) for result in results)
    document = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>スコアロジック探査 比較レポート</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #17202a; background: #f6f8fb; }}
    header {{ position: sticky; top: 0; background: #ffffff; border-bottom: 1px solid #d8dee9; padding: 16px 24px; z-index: 1; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    section {{ background: #fff; border: 1px solid #d8dee9; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    h1, h2, h3, h4 {{ margin: 0 0 12px; }}
    h4 span {{ color: #607085; font-weight: 500; }}
    .decision {{ padding: 10px 12px; background: #eef6ff; border-left: 4px solid #2878c8; }}
    .cards, .diff-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    article {{ border: 1px solid #d8dee9; border-radius: 8px; padding: 14px; background: #fbfcfe; }}
    .logic {{ font-family: Consolas, "Courier New", monospace; overflow-wrap: anywhere; }}
    .muted {{ color: #607085; font-size: 0.92rem; }}
    .table-wrap {{ overflow-x: auto; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; background: #fff; }}
    th, td {{ border-bottom: 1px solid #e1e6ef; padding: 8px 10px; text-align: left; white-space: nowrap; }}
    th {{ background: #f0f4f9; }}
    @media (max-width: 760px) {{ main {{ padding: 14px; }} header {{ padding: 12px 14px; }} section {{ padding: 14px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>スコアロジック探査 比較レポート</h1>
    <p class="muted">生成日時: {html_escape(generated)} / 現行、候補、追加、除外、共通銘柄を比較</p>
  </header>
  <main>
    {sections}
  </main>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)


def print_result(result: dict):
    current = result["current"]
    print(f"\nMODE {result['mode']}")
    print(f"  splits={result['splits']} folds={result['folds']}")
    print(f"  pool={','.join(result['pool'])}")
    decision = result.get("decision", {})
    if decision:
        print(f"  decision={decision.get('action')} reason={decision.get('reason')}")
        if decision.get("candidate_label"):
            print(f"    decision_candidate={decision.get('candidate_label')}")
    print(f"  current {current['candidate'].label}")
    print(f"    all={fmt_stats(current['metrics']['all'])} valid={fmt_stats(current['metrics']['valid'])} lock={fmt_stats(current['metrics']['lock'])} watch={fmt_stats(current['metrics']['watch'])}")
    print(f"    current_rows[{len(current.get('rows', []))}]={fmt_rows(current.get('rows', []))}")
    if not result["top"]:
        print("  top: none")
        return
    for i, item in enumerate(result["top"][:5], 1):
        m = item["metrics"]
        print(f"  TOP{i} {item['candidate'].label}")
        print(f"    all={fmt_stats(m['all'])} valid={fmt_stats(m['valid'])} lock={fmt_stats(m['lock'])} watch={fmt_stats(m['watch'])}")
        diff = item.get("diff", {})
        added = diff.get("added", [])
        removed = diff.get("removed", [])
        common = diff.get("common", [])
        print(f"    candidate_rows[{len(item.get('rows', []))}]={fmt_rows(item.get('rows', []))}")
        print(f"    added[{len(added)}]={fmt_rows(added)}")
        print(f"    removed[{len(removed)}]={fmt_rows(removed)}")
        print(f"    common[{len(common)}]={fmt_rows(common)}")
        continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument("--modes", default="", help="Comma-separated mode ids to run")
    parser.add_argument("--json-output", default="")
    parser.add_argument("--html-output", default="")
    args = parser.parse_args()

    started = time.time()
    frame = build_frame(args.use_cache)
    derived = frame.attrs.get("derived_conditions", [])
    columns = [c for c in opt.BOOL_CONDS + derived if c in frame.columns]
    print(f"rows={len(frame)} derived_conditions={len(derived)} elapsed_build={time.time() - started:.1f}s")
    if frame.attrs.get("meta"):
        print(f"meta={frame.attrs['meta']}")

    results = []
    by_mode = {}
    wanted_modes = {item.strip() for item in args.modes.split(",") if item.strip()}
    modes_to_run = [mode for mode in MODE_DEFS if not wanted_modes or mode["id"] in wanted_modes]
    for mode in modes_to_run:
        result = search_mode(frame, mode, columns)
        by_mode[mode["id"]] = result
        results.append(result)
        print_result(result)

    if "mega40_deep_reversal" in by_mode and "mega40_wick_recovery" in by_mode:
        or_results = make_mega40_or(by_mode["mega40_deep_reversal"], by_mode["mega40_wick_recovery"], frame, columns)
        print("\nMODE mega40_or")
        if not or_results:
            print("  top: none")
        for i, item in enumerate(or_results[:5], 1):
            m = item["metrics"]
            print(f"  TOP{i} {item['candidate'].label}")
            print(f"    all={fmt_stats(m['all'])} valid={fmt_stats(m['valid'])} lock={fmt_stats(m['lock'])} watch={fmt_stats(m['watch'])}")

    if args.json_output:
        payload = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "results": [
                {
                    "mode": r["mode"],
                    "splits": r["splits"],
                    "folds": r["folds"],
                    "pool": r["pool"],
                    "current": {
                        "candidate": serializable_candidate(r["current"]["candidate"]),
                        "metrics": r["current"]["metrics"],
                        "rows": r["current"].get("rows", []),
                    },
                    "decision": r.get("decision", {}),
                    "top": [
                        {
                            "candidate": serializable_candidate(item["candidate"]),
                            "metrics": item["metrics"],
                            "rank": list(item["rank"]),
                            "rows": item.get("rows", []),
                            "diff": item.get("diff", {}),
                        }
                        for item in r["top"]
                    ],
                }
                for r in results
            ],
        }
        with open(args.json_output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    if args.html_output:
        write_html_report(args.html_output, results)
    print(f"\ndone elapsed={time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
