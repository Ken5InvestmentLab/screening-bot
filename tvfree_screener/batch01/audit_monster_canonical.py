#!/usr/bin/env python3
"""Freeze and audit the V20 weak+early Monster candidate family.

Research-only. The freeze phase reads signal-time fields only. Evaluation is
split into 2023 discovery, a frozen 2024 confirmation, and an optional locked
2025 replay. No 2026 labels are opened by this module.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from .evaluation import (
    build_five_session_labels,
    cohort_summary,
    daily_cohorts,
    label_summary,
    return_metrics,
)
from .selection import PolicySpec, apply_selection_policy, rank_candidate_pool
from .session_calendar import SessionCalendar


BATCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BATCH_DIR.parents[1]
ARTIFACTS = BATCH_DIR / ".cache" / "artifacts"
TAIL_PATH = ARTIFACTS / "v7_causal_tail_cache_2023_2025.csv"
TAIL_META_PATH = ARTIFACTS / "v7_causal_tail_cache_meta.json"
DAILY_PATH = ARTIFACTS / "tse_daily.csv"
MARKET_PATH = BATCH_DIR / ".cache" / "market_returns.parquet"
CALENDAR_PATH = BATCH_DIR / "reference" / "xtks_sessions.csv"
V18_PATH = REPO_ROOT / "tvfree_screener" / "v18_consensus_monster.py"
V20_PATH = REPO_ROOT / "tvfree_screener" / "v20_consensus_early.py"
REPORT_DIR = BATCH_DIR / "reports"
CACHE_DIR = BATCH_DIR / ".cache"
SPEC_PATH = REPORT_DIR / "monster_canonical_spec.json"
REPORT_PATH = REPORT_DIR / "monster_canonical_audit.json"
POOL_PATH = CACHE_DIR / "monster_canonical_candidate_pool.parquet"
LABEL_PATH = CACHE_DIR / "monster_canonical_labels.parquet"

EXPECTED_HASHES = {
    "daily_sha256": "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0",
    "calendar_sha256": "74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68",
    "market_sha256": "321c238cd89a63f25e790911484f8a8b6b88f8f5220232c5b0e4d8a3c58fa90c",
    "tail_sha256": "0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d",
}
RET10_MAX = 0.5735294117647058
TAIL_GATE = 0.999
COST = 0.005
FAMILY = "monster_weak_early_v20_lag1"
SPEC_KEYS = ("date", "symbol", "family", "spec_hash")
PRICE_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _load_v18_functions() -> tuple[dict[str, Any], str]:
    """Execute the exact historical selector functions without importing XGBoost."""
    source = V18_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(V18_PATH))
    wanted = {"cooldown_pick", "select_v16", "select_v17", "consensus"}
    body: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "RMAX" for target in node.targets
        ):
            body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            body.append(node)
    if {n.name for n in body if isinstance(n, ast.FunctionDef)} != wanted:
        raise ValueError("could not load all canonical historical V18 selector functions")
    namespace: dict[str, Any] = {"pd": pd}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(V18_PATH), "exec"), namespace)
    return namespace, _sha(V18_PATH)


def _v20_constant() -> tuple[float, str]:
    source = V20_PATH.read_text(encoding="utf-8")
    match = re.search(r"^RET10_MAX\s*=\s*([0-9.]+)\s*$", source, flags=re.MULTILINE)
    if not match:
        raise ValueError("V20 ret10 source constant is missing")
    return float(match.group(1)), _sha(V20_PATH)


def _threshold_provenance() -> dict[str, Any]:
    v20_value, v20_sha = _v20_constant()
    if v20_value != RET10_MAX:
        raise ValueError("audited V20 ret10 constant differs from the registered value")
    selector, v18_sha = _load_v18_functions()
    cols = ["date", "symbol", "ret1", "ret10", "volr20", "range_pct", "med_ret5", "tail_cdf", "tail_p"]
    tail = pd.read_csv(TAIL_PATH, usecols=cols, parse_dates=["date"], dtype={"symbol": "string"})
    tail = tail.loc[(tail["date"] >= "2023-01-01") & (tail["date"] <= "2023-12-31")].copy()
    calendar = pd.read_csv(CALENDAR_PATH, usecols=["date"], parse_dates=["date"])
    sessions = pd.DatetimeIndex(calendar["date"])
    v16 = selector["select_v16"](tail, sessions)
    v17 = selector["select_v17"](tail, sessions)
    consensus = selector["consensus"](v16, v17)
    median = float(pd.to_numeric(consensus["ret10"], errors="coerce").median()) if not consensus.empty else None
    verified = median is not None and math.isclose(median, RET10_MAX, rel_tol=0.0, abs_tol=1e-12)
    return {
        "declared_source": "2023 V18 consensus median ret10",
        "source_v18_sha256": v18_sha,
        "source_v20_sha256": v20_sha,
        "reconstruction": "AST-extracted exact cooldown_pick/select_v16/select_v17/consensus functions from V18; V16/V17 same-date market med_ret5<=0, original top4-before-cooldown behavior",
        "rows": {"v7_tail_2023": int(len(tail)), "v16_selected": int(len(v16)), "v17_selected": int(len(v17)), "exact_date_symbol_consensus": int(len(consensus))},
        "consensus_date_range": [str(consensus["date"].min().date()), str(consensus["date"].max().date())] if not consensus.empty else None,
        "ret10_median_reconstructed": median,
        "ret10_max_in_v20": v20_value,
        "matches_within_1e-12": bool(verified),
        "known_limitation": "V7 tail cache begins in 2023, so this verifies source provenance but does not provide a pre-2023 discovery sample.",
    }


def freeze_spec() -> dict[str, Any]:
    hashes = {
        "daily_sha256": _sha(DAILY_PATH),
        "calendar_sha256": _sha(CALENDAR_PATH),
        "market_sha256": _sha(MARKET_PATH),
        "tail_sha256": _sha(TAIL_PATH),
        "tail_metadata_sha256": _sha(TAIL_META_PATH),
    }
    for name, expected in EXPECTED_HASHES.items():
        if hashes[name] != expected:
            raise ValueError(f"preserved input hash mismatch: {name}")
    provenance = _threshold_provenance()
    spec: dict[str, Any] = {
        "spec_id": "monster_weak_early_volr20_low_canonical_v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Research-only independent Monster candidate family; never a production write.",
        "scanned_universe": "V7 monthly causal top-0.25% Tail candidate rows retained in the frozen 2023-2025 cache; not the full TSE universe.",
        "candidate_pool": "Every cached V7 Tail row with tail_cdf>=0.999, previous official-session cross-sectional median ret5<=0, and signal-date ret10<=0.5735294117647058. Keep all qualifying symbols and dates before ranking or selection.",
        "eligible_universe_reference": "Same-date V7 Tail rows satisfying previous-session market median ret5<=0 before the ret10 maturity gate.",
        "feature_timestamp": "Signal-date TSE close for individual features; market median is computed on the immediately preceding official XTKS session.",
        "market_feature": "market_median_ret5_lag1, threshold<=0; previous-business-day only.",
        "ret10_gate": {"feature": "signal-date ret10", "operator": "<=", "value": RET10_MAX, "provenance": provenance},
        "ranking": [["volr20", "ascending"], ["tail_cdf", "descending"], ["tail_p", "descending"], ["symbol", "ascending"]],
        "missing_data": "Missing market gate is outside the candidate pool and counted. A candidate passing fixed gates but missing volr20 is retained in the pool and ranks last; no substitute candidate is inserted.",
        "selection_count": "Not fixed during candidate generation. If discovery family gates pass, compare only Top1/Top2/Top3/Top5 and candidate-pool equal-weight reference.",
        "cooldown": "One immediately preceding official XTKS session; independently simulated for each Top-N; only selected symbols update state; state carries across year/fold edges.",
        "target": "Next official XTKS session open to close of the fifth official XTKS session after signal (the fifth session including entry). Daily OHLCV actionability checks; missing bars remain unresolved.",
        "evaluation_order": ["2023 discovery; labels exiting after 2023-12-29 are purged", "freeze selection policy before opening 2024 labels", "2024 directional confirmation; labels exiting after 2024-12-30 are purged", "2025 locked replay only after a passing 2024 confirmation", "2026 not opened"],
        "cost_scenarios": [0.0, 0.005, 0.01],
        "cost_note": "Round-trip costs are sensitivity assumptions, not measured fills.",
        "calendar": "Full XTKS official-session calendar, never weekday approximation.",
        "input_hashes": hashes,
        "audit_script_sha256": _sha(Path(__file__).resolve()),
        "not_reproduced": ["V7 Tail model training from raw prices; preserved model outcomes are not used for selection, only cached signal-time tail features."],
        "implementation_complexity": "High for a production replacement: monthly causal 45-feature V7 model training/scoring, model/version storage and full-universe daily feature generation are not reproduced by this audit; this batch consumes only the frozen Tail feature cache.",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL; historical candidate family has prior exposure.",
    }
    canonical = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    spec["spec_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _json_write(SPEC_PATH, spec)
    return spec


def _read_tail_features(end_date: str) -> pd.DataFrame:
    cols = ["date", "symbol", "ret10", "ret1", "volr20", "tail_cdf", "tail_p", "med_ret5", "range_pct"]
    tail = pd.read_csv(TAIL_PATH, usecols=cols, parse_dates=["date"], dtype={"symbol": "string"})
    tail = tail.loc[(tail["date"] <= pd.Timestamp(end_date)) & (tail["tail_cdf"] >= TAIL_GATE)].copy()
    market = pd.read_parquet(MARKET_PATH, columns=["date", "market_median_ret5_lag1"])
    market["date"] = pd.to_datetime(market["date"], errors="raise").dt.normalize()
    tail = tail.merge(market, on="date", how="left", validate="many_to_one")
    tail["date"] = pd.to_datetime(tail["date"], errors="raise").dt.normalize()
    for column in ("ret10", "ret1", "volr20", "tail_cdf", "tail_p", "market_median_ret5_lag1"):
        tail[column] = pd.to_numeric(tail[column], errors="coerce")
    return tail


def _split_pool(tail: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    market_ok = tail["market_median_ret5_lag1"].notna() & tail["market_median_ret5_lag1"].le(0)
    weak = tail.loc[market_ok].copy()
    gate = weak["ret10"].notna() & weak["ret10"].le(RET10_MAX)
    pool = weak.loc[gate].copy()
    pool["family"] = FAMILY
    pool["spec_hash"] = str(spec["spec_sha256"])
    pool["identity_key"] = pool["symbol"].astype("string")
    pool["volr20_rank_value"] = pd.to_numeric(pool["volr20"], errors="coerce").fillna(np.inf)
    counts = {
        "v7_tail_rows": int(len(tail)),
        "market_lag1_missing": int(tail["market_median_ret5_lag1"].isna().sum()),
        "market_weak_rows": int(len(weak)),
        "ret10_missing_after_market_gate": int(weak["ret10"].isna().sum()),
        "candidate_pool_rows": int(len(pool)),
        "candidate_missing_volr20_retained": int(pool["volr20"].isna().sum()),
        "candidate_dates": int(pool["date"].nunique()),
        "candidate_symbols": int(pool["symbol"].nunique()),
        "maximum_candidates_per_day": int(pool.groupby("date").size().max()) if len(pool) else 0,
    }
    return weak, pool, counts


def _rank(pool: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    return rank_candidate_pool(
        pool,
        sessions=pd.read_csv(CALENDAR_PATH, usecols=["date"], parse_dates=["date"])["date"],
        feature_columns=["ret1", "ret10", "volr20", "tail_cdf", "tail_p", "market_median_ret5_lag1"],
        ranking_terms=[("volr20_rank_value", True), ("tail_cdf", False), ("tail_p", False)],
    )


def _price_subset(signals: pd.DataFrame, calendar: SessionCalendar, max_date: str) -> pd.DataFrame:
    allowed_dates: set[str] = set()
    for signal_date in pd.to_datetime(signals["date"]).dt.normalize().unique():
        position = calendar.position(signal_date)
        for offset in range(0, 6):
            if position + offset < len(calendar.sessions):
                day = pd.Timestamp(calendar.sessions[position + offset])
                if day <= pd.Timestamp(max_date):
                    allowed_dates.add(day.strftime("%Y-%m-%d"))
    symbols = set(signals["symbol"].astype(str))
    pieces: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        DAILY_PATH,
        usecols=list(PRICE_COLUMNS),
        dtype={"date": "string", "symbol": "string"},
        chunksize=250_000,
    ):
        keep = chunk["symbol"].isin(symbols) & chunk["date"].isin(allowed_dates)
        if keep.any():
            pieces.append(chunk.loc[keep].copy())
    if not pieces:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    price = pd.concat(pieces, ignore_index=True)
    price["date"] = pd.to_datetime(price["date"], format="%Y-%m-%d", errors="raise")
    for column in ("open", "high", "low", "close", "volume"):
        price[column] = pd.to_numeric(price[column], errors="coerce")
    return price


def _periodized(frame: pd.DataFrame, year: int, cutoff: str) -> pd.DataFrame:
    out = frame.loc[pd.to_datetime(frame["date"]).dt.year.eq(year)].copy()
    crosses = out["exit_date"].notna() & pd.to_datetime(out["exit_date"]).gt(pd.Timestamp(cutoff))
    out.loc[crosses, "label_resolved"] = False
    out.loc[crosses, "label_status"] = "PURGED_SPLIT_BOUNDARY"
    out.loc[crosses, "gross_return"] = np.nan
    return out


def _net_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    result = label_summary(rows, costs=(0.0, COST, 0.01))
    return result


def _signal_diagnostics(rows: pd.DataFrame) -> dict[str, Any]:
    resolved = rows.loc[
        rows["label_resolved"].astype(bool), ["date", "symbol", "gross_return"]
    ].copy()
    resolved["net_return"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - COST
    resolved = resolved.loc[resolved["net_return"].notna()].copy()
    if resolved.empty:
        return {"n": 0, "monthly": {}, "weekly": {}, "symbol_concentration": {"unique_symbols": 0}}
    resolved["date"] = pd.to_datetime(resolved["date"], errors="raise").dt.normalize()

    def grouped(column: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, group in resolved.groupby(column, sort=True):
            result[str(key)] = return_metrics(group["net_return"])
        return result

    resolved["month"] = resolved["date"].dt.to_period("M").astype(str)
    resolved["week"] = resolved["date"].dt.strftime("%G-W%V")
    monthly = grouped("month")
    weekly = grouped("week")
    month_means = resolved.groupby("month")["net_return"].mean()
    week_means = resolved.groupby("week")["net_return"].mean()
    by_symbol = resolved.groupby("symbol", sort=True)["net_return"].agg(["size", "mean"])
    by_symbol = by_symbol.sort_values(["size", "mean"], ascending=[False, False], kind="mergesort")
    top1_symbols = set(by_symbol.head(1).index.astype(str))
    top3_symbols = set(by_symbol.head(3).index.astype(str))
    return {
        "n": int(len(resolved)),
        "monthly": monthly,
        "weekly": weekly,
        "mean_excluding_best_month": float(resolved.loc[~resolved["month"].eq(str(month_means.idxmax())), "net_return"].mean()) if len(month_means) > 1 else None,
        "mean_excluding_best_week": float(resolved.loc[~resolved["week"].eq(str(week_means.idxmax())), "net_return"].mean()) if len(week_means) > 1 else None,
        "best_month_signal_share": float((resolved["month"] == str(month_means.idxmax())).mean()) if len(month_means) else None,
        "best_week_signal_share": float((resolved["week"] == str(week_means.idxmax())).mean()) if len(week_means) else None,
        "symbol_concentration": {
            "unique_symbols": int(len(by_symbol)),
            "most_frequent_symbol_signal_share": float(by_symbol.iloc[0]["size"] / len(resolved)),
            "top3_symbols_signal_share": float(by_symbol.head(3)["size"].sum() / len(resolved)),
            "mean_excluding_most_frequent_symbol": float(resolved.loc[~resolved["symbol"].astype(str).isin(top1_symbols), "net_return"].mean()) if len(top1_symbols) < len(resolved) else None,
            "mean_excluding_top3_most_frequent_symbols": float(resolved.loc[~resolved["symbol"].astype(str).isin(top3_symbols), "net_return"].mean()) if len(top3_symbols) < len(resolved) else None,
        },
    }


def _cohorts(rows: pd.DataFrame, labels: pd.DataFrame, calendar: SessionCalendar, year: int, policy: bool) -> tuple[dict[str, Any], pd.DataFrame]:
    start = pd.Timestamp(f"{year}-01-01")
    end = pd.Timestamp(f"{year}-12-31")
    sessions = calendar.sessions[(calendar.sessions >= start) & (calendar.sessions <= end)]
    keys = list(SPEC_KEYS)
    if policy:
        keys += ["policy_id", "top_n"]
    net_labels = labels.copy()
    net_labels["gross_return"] = np.where(
        net_labels["label_resolved"].astype(bool),
        pd.to_numeric(net_labels["gross_return"], errors="coerce") - COST,
        np.nan,
    )
    daily = daily_cohorts(rows, net_labels, sessions=sessions, join_columns=keys)
    return cohort_summary(daily, repetitions=2000), daily


def _paired_daily_mean(a: pd.DataFrame, b: pd.DataFrame) -> dict[str, Any]:
    left = a.loc[a["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]].rename(columns={"cohort_return": "candidate"})
    right = b.loc[b["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]].rename(columns={"cohort_return": "reference"})
    paired = left.merge(right, on="date", how="inner", validate="one_to_one")
    return {
        "common_complete_dates": int(len(paired)),
        "candidate_mean": float(paired["candidate"].mean()) if len(paired) else None,
        "reference_mean": float(paired["reference"].mean()) if len(paired) else None,
        "mean_difference": float((paired["candidate"] - paired["reference"]).mean()) if len(paired) else None,
    }


def _attach(labels: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    out = labels.copy()
    out["family"] = FAMILY
    out["spec_hash"] = str(spec["spec_sha256"])
    return out


def _evaluate_discovery(spec: dict[str, Any], calendar: SessionCalendar) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tail = _read_tail_features("2023-12-31")
    weak, pool, counts = _split_pool(tail, spec)
    ranked = _rank(pool, spec)
    pool_payload = ranked.copy()
    pool_payload.to_parquet(POOL_PATH, index=False)
    weak_signals = weak.loc[:, ["date", "symbol"]].drop_duplicates().copy()
    weak_signals["family"] = FAMILY
    weak_signals["spec_hash"] = str(spec["spec_sha256"])
    prices = _price_subset(weak_signals, calendar, "2023-12-29")
    labels = build_five_session_labels(prices, weak_signals, calendar)
    labels = _attach(labels, spec)
    labels.to_parquet(LABEL_PATH, index=False)
    pool_outcomes = ranked.merge(
        labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved", "entry_price", "exit_price", "entry_fill_quality", "label_definition"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    weak_outcomes = weak_signals.merge(
        labels.loc[:, ["date", "symbol", "gross_return", "exit_date", "label_status", "label_resolved"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    weak_outcomes["family"] = FAMILY
    weak_outcomes["spec_hash"] = str(spec["spec_sha256"])
    pool_period = _periodized(pool_outcomes, 2023, "2023-12-29")
    weak_period = _periodized(weak_outcomes, 2023, "2023-12-29")
    pool_daily, pool_daily_frame = _cohorts(pool_period, pool_period, calendar, 2023, policy=False)
    active = set(pool_period["date"])
    reference = weak_period.loc[weak_period["date"].isin(active)].copy()
    ref_daily, ref_daily_frame = _cohorts(reference, reference, calendar, 2023, policy=False)
    pool_metrics = _net_metrics(pool_period)
    ref_metrics = _net_metrics(reference)
    pool_net = pool_metrics["round_trip_cost_scenarios"]["0.005"]
    ref_net = ref_metrics["round_trip_cost_scenarios"]["0.005"]
    family_pass = (
        float(pool_net["mean"] or 0.0) > 0
        and float(pool_daily_frame.loc[pool_daily_frame["cohort_status"].eq("COMPLETE"), "cohort_return"].mean() or 0.0) > 0
        and int((pool_period.loc[pool_period["label_resolved"].astype(bool), "gross_return"] >= 0.20).sum()) >= 2
        and pool_net["mean"] is not None and ref_net["mean"] is not None and pool_net["mean"] > ref_net["mean"]
        and pool_net["plus20_rate"] is not None and ref_net["plus20_rate"] is not None and pool_net["plus20_rate"] > ref_net["plus20_rate"]
    )
    report: dict[str, Any] = {
        "status": "DISCOVERY_COMPLETED",
        "decision": "KEEP_PROCEED_TO_SELECTION_STUDY" if family_pass else "REJECT_MONSTER_FAMILY",
        "discovery_year": 2023,
        "candidate_counts": counts,
        "candidate_pool": pool_metrics,
        "candidate_pool_signal_diagnostics_net_0_5pct": _signal_diagnostics(pool_period),
        "candidate_pool_daily_cohorts_net_0_5pct": pool_daily,
        "same_active_date_weak_tail_reference": ref_metrics,
        "weak_tail_reference_signal_diagnostics_net_0_5pct": _signal_diagnostics(reference),
        "same_active_date_reference_daily_cohorts_net_0_5pct": ref_daily,
        "paired_complete_daily_cohort_difference": _paired_daily_mean(
            pool_daily_frame,
            ref_daily_frame,
        ),
        "family_gate": {
            "signal_net_mean_positive": bool(pool_net["mean"] is not None and pool_net["mean"] > 0),
            "daily_cohort_net_mean_positive": bool(pool_daily["mean"] is not None and pool_daily["mean"] > 0),
            "at_least_two_plus20_winners": int((pool_period.loc[pool_period["label_resolved"].astype(bool), "gross_return"] >= 0.20).sum()) >= 2,
            "mean_exceeds_same_active_date_reference": bool(pool_net["mean"] is not None and ref_net["mean"] is not None and pool_net["mean"] > ref_net["mean"]),
            "plus20_rate_exceeds_same_active_date_reference": bool(pool_net["plus20_rate"] is not None and ref_net["plus20_rate"] is not None and pool_net["plus20_rate"] > ref_net["plus20_rate"]),
        },
        "purge": {"signals_whose_exit_is_after_2023-12-29_remain_in_requested_n_but_are_unresolved": int(pool_period["label_status"].eq("PURGED_SPLIT_BOUNDARY").sum())},
        "artifacts": {
            "candidate_pool_path": str(POOL_PATH.relative_to(BATCH_DIR)),
            "candidate_pool_sha256": _sha(POOL_PATH),
            "label_cache_path": str(LABEL_PATH.relative_to(BATCH_DIR)),
            "label_cache_sha256": _sha(LABEL_PATH),
        },
        "2026_outcomes_opened": False,
    }
    return report, ranked, labels, weak_outcomes


def _selection_study(
    discovery: dict[str, Any], ranked: pd.DataFrame, labels: pd.DataFrame,
    weak_outcomes: pd.DataFrame, calendar: SessionCalendar, spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if discovery["decision"] != "KEEP_PROCEED_TO_SELECTION_STUDY":
        return {"status": "SKIPPED_FAMILY_REJECTED"}, None
    results: list[dict[str, Any]] = []
    for n in (1, 2, 3, 5):
        policy = PolicySpec(lane="Monster", top_n=n, policy_id=f"{FAMILY}_top{n}")
        selected = apply_selection_policy(ranked, sessions=calendar.sessions, policy=policy).selected
        selected = selected.loc[pd.to_datetime(selected["date"]).dt.year.eq(2023)].copy()
        if selected.empty:
            results.append({"top_n": n, "status": "NO_SELECTED_SIGNALS"})
            continue
        selected["family"] = FAMILY
        selected["spec_hash"] = str(spec["spec_sha256"])
        policy_labels = labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved"]].copy()
        selected["policy_id"] = policy.policy_id
        selected["top_n"] = n
        selected_out = selected.merge(
            policy_labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved"]],
            on=["date", "symbol"], how="left", validate="one_to_one",
        )
        period = _periodized(selected_out, 2023, "2023-12-29")
        signal = _net_metrics(period)
        cohort, cohort_frame = _cohorts(period, period, calendar, 2023, policy=True)
        active = set(period["date"])
        candidate_ref = ranked.loc[ranked["date"].isin(active)].copy()
        candidate_ref = candidate_ref.merge(
            labels.loc[:, ["date", "symbol", "gross_return", "exit_date", "label_status", "label_resolved"]],
            on=["date", "symbol"], how="left", validate="one_to_one",
        )
        candidate_ref["policy_id"] = policy.policy_id
        candidate_ref["top_n"] = n
        candidate_ref = _periodized(candidate_ref, 2023, "2023-12-29")
        ref_cohort, ref_frame = _cohorts(candidate_ref, candidate_ref, calendar, 2023, policy=True)
        signal_net = signal["round_trip_cost_scenarios"]["0.005"]
        reference_net = _net_metrics(candidate_ref)["round_trip_cost_scenarios"]["0.005"]
        cnet = cohort
        rnet = ref_cohort
        winners20 = int((period.loc[period["label_resolved"].astype(bool), "gross_return"] >= 0.20).sum())
        passes = (
            signal_net["mean"] is not None and signal_net["mean"] > 0
            and cnet["mean"] is not None and cnet["mean"] > 0
            and reference_net["mean"] is not None and signal_net["mean"] > reference_net["mean"]
            and signal_net["plus20_rate"] is not None and reference_net["plus20_rate"] is not None and signal_net["plus20_rate"] > reference_net["plus20_rate"]
            and winners20 >= 2
        )
        results.append({
            "top_n": n, "status": "PASS" if passes else "FAIL",
            "selected_signal_metrics": signal,
            "selected_signal_diagnostics_net_0_5pct": _signal_diagnostics(period),
            "selected_daily_cohorts_net_0_5pct": cohort,
            "candidate_pool_reference_same_active_dates": _net_metrics(candidate_ref),
            "candidate_pool_reference_signal_diagnostics_net_0_5pct": _signal_diagnostics(candidate_ref),
            "candidate_pool_reference_daily_cohorts_net_0_5pct": ref_cohort,
        "paired_complete_cohort_difference": _paired_daily_mean(
                cohort_frame,
                ref_frame,
            ),
            "plus20_winners": winners20,
            "active_days": int(period["date"].nunique()),
            "policy_sha256": apply_selection_policy(ranked, sessions=calendar.sessions, policy=policy).policy_sha256,
            "selection_sha256": apply_selection_policy(ranked, sessions=calendar.sessions, policy=policy).selection_sha256,
        })
    passing = [row for row in results if row.get("status") == "PASS"]
    chosen = None
    if passing:
        passing.sort(key=lambda row: (
            -(row["selected_daily_cohorts_net_0_5pct"]["mean"] or -math.inf),
            int(row["top_n"]),
        ))
        chosen = passing[0]
    return {
        "status": "FROZEN_POLICY_SELECTED" if chosen else "SELECTION_COUNT_UNRESOLVED",
        "policies": results,
        "chosen_top_n": int(chosen["top_n"]) if chosen else None,
        "choice_rule": "Among policy gates passing in 2023, highest discovery net daily-cohort mean; tie-break smaller N. No alternate N after 2024 confirmation.",
    }, chosen


def _validate_2024(
    spec: dict[str, Any], discovery: dict[str, Any], selection: dict[str, Any],
    chosen: dict[str, Any] | None, calendar: SessionCalendar,
) -> dict[str, Any]:
    tail = _read_tail_features("2024-12-31")
    weak, pool, counts = _split_pool(tail, spec)
    ranked_all = _rank(pool, spec)
    weak_signals = weak.loc[:, ["date", "symbol"]].drop_duplicates().copy()
    weak_signals["family"] = FAMILY
    weak_signals["spec_hash"] = str(spec["spec_sha256"])
    prices = _price_subset(weak_signals, calendar, "2024-12-30")
    labels = build_five_session_labels(prices, weak_signals, calendar)
    labels = _attach(labels, spec)
    if chosen is None:
        candidate = ranked_all.loc[pd.to_datetime(ranked_all["date"]).dt.year.eq(2024)].copy()
        candidate = candidate.merge(
            labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved"]],
            on=["date", "symbol"], how="left", validate="one_to_one",
        )
        candidate = _periodized(candidate, 2024, "2024-12-30")
        weak_2024 = weak_signals.loc[pd.to_datetime(weak_signals["date"]).dt.year.eq(2024)].copy()
        weak_2024 = weak_2024.merge(
            labels.loc[:, ["date", "symbol", "gross_return", "exit_date", "label_status", "label_resolved"]],
            on=["date", "symbol"], how="left", validate="one_to_one",
        )
        weak_2024 = _periodized(weak_2024, 2024, "2024-12-30")
        active = set(candidate["date"])
        reference = weak_2024.loc[weak_2024["date"].isin(active)].copy()
        candidate_summary = _net_metrics(candidate)
        reference_summary = _net_metrics(reference)
        candidate_cohort, candidate_daily = _cohorts(candidate, candidate, calendar, 2024, policy=False)
        reference_cohort, reference_daily = _cohorts(reference, reference, calendar, 2024, policy=False)
        policy_unresolved = selection.get("status") == "SELECTION_COUNT_UNRESOLVED"
        return {
            "status": "SELECTION_COUNT_UNRESOLVED_POOL_DIAGNOSTIC_ONLY" if policy_unresolved else "FAMILY_REJECTED_POOL_DIAGNOSTIC_ONLY",
            "candidate_counts": counts,
            "candidate_pool": candidate_summary,
            "candidate_pool_signal_diagnostics_net_0_5pct": _signal_diagnostics(candidate),
            "candidate_pool_daily_cohorts_net_0_5pct": candidate_cohort,
            "same_active_date_weak_tail_reference": reference_summary,
            "weak_tail_reference_signal_diagnostics_net_0_5pct": _signal_diagnostics(reference),
            "same_active_date_reference_daily_cohorts_net_0_5pct": reference_cohort,
            "paired_complete_daily_cohort_difference": _paired_daily_mean(candidate_daily, reference_daily),
            "family_was_already_decided_from_2023_discovery": discovery["decision"],
            "selection_study_status": selection.get("status"),
            "2026_outcomes_opened": False,
        }

    n = int(chosen["top_n"])
    policy = PolicySpec(lane="Monster", top_n=n, policy_id=f"{FAMILY}_top{n}")
    selected_all = apply_selection_policy(ranked_all, sessions=calendar.sessions, policy=policy).selected
    selected = selected_all.loc[pd.to_datetime(selected_all["date"]).dt.year.eq(2024)].copy()
    selected["family"] = FAMILY
    selected["spec_hash"] = str(spec["spec_sha256"])
    selected["policy_id"] = policy.policy_id
    selected["top_n"] = n
    policy_labels = labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved"]].copy()
    selected_out = selected.merge(
        policy_labels.loc[:, ["date", "symbol", "gross_return", "entry_date", "exit_date", "label_status", "label_resolved"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    selected_out = _periodized(selected_out, 2024, "2024-12-30")
    signal_metrics = _net_metrics(selected_out)
    selected_cohort, selected_daily = _cohorts(selected_out, selected_out, calendar, 2024, policy=True)
    active = set(selected_out["date"])
    pool_ref = ranked_all.loc[
        ranked_all["date"].dt.year.eq(2024) & ranked_all["date"].isin(active)
    ].copy()
    pool_ref = pool_ref.merge(
        labels.loc[:, ["date", "symbol", "gross_return", "exit_date", "label_status", "label_resolved"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    pool_ref["policy_id"] = policy.policy_id
    pool_ref["top_n"] = n
    pool_ref = _periodized(pool_ref, 2024, "2024-12-30")
    ref_metrics = _net_metrics(pool_ref)
    ref_cohort, ref_daily = _cohorts(pool_ref, pool_ref, calendar, 2024, policy=True)
    snet = signal_metrics["round_trip_cost_scenarios"]["0.005"]
    rnet = ref_metrics["round_trip_cost_scenarios"]["0.005"]
    cnet = selected_cohort
    winners20 = int((selected_out.loc[selected_out["label_resolved"].astype(bool), "gross_return"] >= 0.20).sum())
    passes = (
        snet["mean"] is not None and snet["mean"] > 0
        and cnet["mean"] is not None and cnet["mean"] > 0
        and rnet["mean"] is not None and snet["mean"] > rnet["mean"]
        and snet["plus20_rate"] is not None and rnet["plus20_rate"] is not None and snet["plus20_rate"] > rnet["plus20_rate"]
        and winners20 >= 2
    )
    return {
        "status": "FROZEN_POLICY_CONFIRMED" if passes else "SELECTION_COUNT_UNRESOLVED",
        "decision": "KEEP_FOR_LOCKED_2025_REPLAY" if passes else "NO_2025_RESCUE_OR_ALTERNATE_N",
        "top_n": n,
        "candidate_counts": counts,
        "selected_metrics": signal_metrics,
        "selected_signal_diagnostics_net_0_5pct": _signal_diagnostics(selected_out),
        "selected_daily_cohorts_net_0_5pct": selected_cohort,
        "candidate_pool_reference_same_active_dates": ref_metrics,
        "candidate_pool_reference_signal_diagnostics_net_0_5pct": _signal_diagnostics(pool_ref),
        "candidate_pool_reference_daily_cohorts_net_0_5pct": ref_cohort,
        "paired_complete_cohort_difference": _paired_daily_mean(
            selected_daily,
            ref_daily,
        ),
        "plus20_winners": winners20,
        "confirmation_gate_pass": bool(passes),
        "2026_outcomes_opened": False,
    }


def _replay_2025(spec: dict[str, Any], prior: dict[str, Any], calendar: SessionCalendar) -> dict[str, Any]:
    if prior.get("status") != "FROZEN_POLICY_CONFIRMED" or not prior.get("confirmation_gate_pass"):
        raise ValueError("2025 replay requires a passing frozen 2024 policy confirmation")
    n = int(prior["top_n"])
    tail = _read_tail_features("2025-12-31")
    weak, pool, counts = _split_pool(tail, spec)
    ranked = _rank(pool, spec)
    policy = PolicySpec(lane="Monster", top_n=n, policy_id=f"{FAMILY}_top{n}")
    selections = apply_selection_policy(ranked, sessions=calendar.sessions, policy=policy).selected
    selections = selections.loc[pd.to_datetime(selections["date"]).dt.year.eq(2025)].copy()
    selections["family"] = FAMILY
    selections["spec_hash"] = str(spec["spec_sha256"])
    selections["policy_id"] = policy.policy_id
    selections["top_n"] = n
    weak_signals = weak.loc[:, ["date", "symbol"]].drop_duplicates().copy()
    weak_signals["family"] = FAMILY
    weak_signals["spec_hash"] = str(spec["spec_sha256"])
    prices = _price_subset(weak_signals, calendar, "2025-12-30")
    labels = _attach(build_five_session_labels(prices, weak_signals, calendar), spec)
    selected_labels = labels.merge(
        selections.loc[:, ["date", "symbol"]], on=["date", "symbol"], how="inner", validate="one_to_one"
    )
    selected_labels["policy_id"] = policy.policy_id
    selected_labels["top_n"] = n
    selected_labels = _periodized(selected_labels, 2025, "2025-12-30")
    return {
        "status": "LOCKED_2025_REPLAY_COMPLETED",
        "top_n": n,
        "candidate_counts": counts,
        "selected_metrics": _net_metrics(selected_labels),
        "selected_signal_diagnostics_net_0_5pct": _signal_diagnostics(selected_labels),
        "selected_count": int(len(selected_labels)),
        "2026_outcomes_opened": False,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL; historical periods had prior exposure.",
    }


def _load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    recorded = spec.pop("spec_sha256")
    canonical = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    spec["spec_sha256"] = recorded
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != recorded:
        raise ValueError("frozen Monster spec hash mismatch")
    for name, expected in EXPECTED_HASHES.items():
        path = {
            "daily_sha256": DAILY_PATH,
            "calendar_sha256": CALENDAR_PATH,
            "market_sha256": MARKET_PATH,
            "tail_sha256": TAIL_PATH,
        }[name]
        if _sha(path) != expected:
            raise ValueError(f"preserved input changed after freeze: {name}")
    if spec.get("audit_script_sha256") != _sha(Path(__file__).resolve()):
        raise ValueError("Monster audit implementation changed after the spec freeze")
    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true", help="verify V20 threshold provenance and freeze the canonical feature-only spec")
    group.add_argument("--evaluate", action="store_true", help="run purged 2023 discovery then frozen 2024 confirmation; never opens 2025/2026")
    group.add_argument("--replay-2025", action="store_true", help="run a locked 2025 replay only after a passing 2024 frozen policy")
    args = parser.parse_args()
    if args.freeze:
        spec = freeze_spec()
        print(json.dumps({"spec_path": str(SPEC_PATH), **spec}, ensure_ascii=False, indent=2))
        return
    spec = _load_spec()
    calendar = SessionCalendar.from_csv(CALENDAR_PATH, expected_sha256=EXPECTED_HASHES["calendar_sha256"])
    if args.evaluate:
        discovery, ranked, labels, weak = _evaluate_discovery(spec, calendar)
        selection, chosen = _selection_study(discovery, ranked, labels, weak, calendar, spec)
        validation = _validate_2024(spec, discovery, selection, chosen, calendar)
        report = {
            "spec_id": spec["spec_id"], "spec_sha256": spec["spec_sha256"],
            "threshold_provenance": spec["ret10_gate"]["provenance"],
            "2023_discovery": discovery, "selection_study": selection, "2024_confirmation": validation,
            "not_run": {"2025": "Not opened; requires a passing 2024 selection-policy confirmation.", "2026": "Reporting-only and not opened."},
            "decision": (
                validation.get("decision")
                or ("SELECTION_COUNT_UNRESOLVED" if selection.get("status") == "SELECTION_COUNT_UNRESOLVED" else discovery["decision"])
            ),
        }
        _json_write(REPORT_PATH, report)
        print(json.dumps({"report_path": str(REPORT_PATH), "decision": report["decision"], "threshold_verified": spec["ret10_gate"]["provenance"]["matches_within_1e-12"], "candidate_pool_rows_2023": discovery["candidate_counts"]["candidate_pool_rows"], "2024_status": validation["status"]}, ensure_ascii=False, indent=2))
        return
    prior = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    confirmation = prior.get("2024_confirmation", {})
    replay = _replay_2025(spec, confirmation, calendar)
    prior["2025_locked_replay"] = replay
    prior["decision"] = replay["status"]
    _json_write(REPORT_PATH, prior)
    print(json.dumps({"report_path": str(REPORT_PATH), "replay": replay}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
