"""Frozen multi-event quality score for research only.

The candidate features are signal-time only. 2024 results are retrospective
development; any 2025 check needs its own committed freeze. No production
files or services are touched by this module.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import core_moderate_ridge_audit as label_builder
from tvfree_screener.batch01.evaluation import cohort_summary, daily_cohorts, label_summary
from tvfree_screener.batch01.feature_panel import build_feature_panel
from tvfree_screener.batch01.session_calendar import SessionCalendar


BATCH = Path(__file__).resolve().parent
B1 = BATCH.parent / "batch01"
REPORTS = BATCH / "reports"
CACHE = BATCH / ".cache"
SOURCE = B1 / ".cache/artifacts/tse_daily.csv"
PRESERVATION = B1 / "PRESERVATION_MANIFEST.json"
CALENDAR_PATH = B1 / "reference/xtks_sessions.csv"
CALENDAR_MANIFEST = B1 / "reference/xtks_sessions.manifest.json"
SPEC_PATH = REPORTS / "core_multi_event_quality_spec.json"
SPEC_SHA_PATH = REPORTS / "core_multi_event_quality_spec.sha256"
POOL_PATH = CACHE / "core_multi_event_quality_2024_event_pool.csv"
POOL_RECEIPT_PATH = REPORTS / "core_multi_event_quality_2024_pool_receipt.json"
POOL_REPRO_PATH = REPORTS / "core_multi_event_quality_2024_pool_reproduction.json"
DISCOVERY_PATH = REPORTS / "core_multi_event_quality_2024_development.json"
DISCOVERY_MD_PATH = REPORTS / "core_multi_event_quality_2024_development.md"
DISCOVERY_LABELS = CACHE / "core_multi_event_quality_2024_labels.csv"

EXPERIMENT_ID = "CORE-MULTI-EVENT-QUALITY-20260913-01"
FAMILY = "causal_multi_event_quality_top5_v1"
WINNER_THRESHOLD = 0.10
LOSER_THRESHOLD = -0.10
ROUND_TRIP_COST = 0.005
MAX_PER_DAY = 5
COOLDOWN_SESSIONS = 1
RIDGE_ALPHA = 30.0

MODEL_FEATURES = [
    "ret1", "ret3", "ret5", "ret10", "ret20", "ret40", "prev_ret5",
    "volr5", "volr10", "volr20", "rv_ratio", "range_expansion",
    "close_loc", "gap", "pos20", "pos60", "break20", "break60",
    "ret5_pct", "ret20_pct", "volr20_pct", "pos60_pct",
    "evt_reversal", "evt_ignition", "evt_breakout", "evt_gap_hold",
    "evt_compression_release", "evt_pullback_resume", "event_count",
]

VARIANTS: dict[str, dict[str, float]] = {
    "balanced": {"ret": 1.00, "hit10": 0.00, "loss10": 1.00, "gate": 0.15},
    "winner_aware": {"ret": 1.00, "hit10": 0.50, "loss10": 1.00, "gate": 0.20},
    "defensive": {"ret": 1.00, "hit10": 0.25, "loss10": 1.50, "gate": 0.10},
    "balanced_high_gate": {"ret": 1.00, "hit10": 0.00, "loss10": 1.00, "gate": 0.30},
}

EVENT_RULES = {
    "evt_reversal": "prev_ret5 <= -0.04 AND ret1 >= 0.01 AND close_loc >= 0.55 AND gap >= -0.06",
    "evt_ignition": "ret5 in [0.02,0.15] AND ret1 >= 0.015 AND volr20 >= 1.10 AND pos60 >= 0.50 AND close_loc >= 0.55",
    "evt_breakout": "break20 in [0.00,0.08] AND volr20 in [1.0,5.0] AND close_loc >= 0.60",
    "evt_gap_hold": "gap in [0.01,0.12] AND ret1 > 0 AND close_loc >= 0.60",
    "evt_compression_release": "rv_ratio <= 1.0 AND range_expansion >= 1.15 AND ret1 >= 0.015 AND volr20 >= 1.10 AND close_loc >= 0.55",
    "evt_pullback_resume": "ret20 >= 0.08 AND prev_ret5 <= 0 AND ret1 >= 0.015 AND pos60 >= 0.50",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BATCH.parents[1], text=True).strip()


def implementation_hashes() -> dict[str, str]:
    files = {
        "multi_event_quality": Path(__file__),
        "research_tests": BATCH / "test_core_multi_event_quality.py",
        "v4_model_reference": BATCH.parents[1] / "tvfree_screener/v4_event_quality_research.py",
        "feature_panel": B1 / "feature_panel.py",
        "canonical_label_builder": B1 / "core_moderate_ridge_audit.py",
        "evaluation": B1 / "evaluation.py",
        "session_calendar": B1 / "session_calendar.py",
        "artifact_store": B1 / "artifact_store.py",
    }
    return {name: sha256_file(path) for name, path in files.items()}


def verify_registered_inputs() -> tuple[dict[str, Any], SessionCalendar, dict[str, str]]:
    if not SPEC_PATH.exists() or not SPEC_SHA_PATH.exists():
        raise FileNotFoundError("multi-event spec and SHA sidecar must be committed first")
    spec_bytes = SPEC_PATH.read_bytes()
    spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    expected_spec_hash = SPEC_SHA_PATH.read_text(encoding="utf-8").strip().split()[0]
    if spec_hash != expected_spec_hash:
        raise ValueError("multi-event spec differs from its frozen SHA")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if spec.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("experiment ID differs from the registered spec")
    if spec.get("implementation_hashes") != implementation_hashes():
        raise ValueError("implementation or test code differs from the frozen spec")

    preservation = json.loads(PRESERVATION.read_text(encoding="utf-8"))
    source_member = next(item for item in preservation["artifacts"] if item["member"] == SOURCE.name)
    calendar_manifest = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    input_hashes = {
        "source_sha256": sha256_file(SOURCE),
        "preservation_manifest_sha256": sha256_file(PRESERVATION),
        "calendar_sha256": sha256_file(CALENDAR_PATH),
        "calendar_manifest_sha256": sha256_file(CALENDAR_MANIFEST),
    }
    if input_hashes["source_sha256"] != source_member["member_sha256"]:
        raise ValueError("daily source differs from the preserved artifact manifest")
    if input_hashes["calendar_sha256"] != calendar_manifest["csv_sha256"]:
        raise ValueError("session calendar differs from its manifest")
    expected_inputs = spec.get("input_hashes", {})
    if expected_inputs != input_hashes:
        raise ValueError("registered source or calendar hash differs")
    frozen_paths = (SPEC_PATH, SPEC_SHA_PATH, Path(__file__))
    if not all(_git_path_committed(path) for path in frozen_paths):
        raise ValueError("spec and implementation must be committed before feature preparation")
    calendar = SessionCalendar.from_csv(CALENDAR_PATH, expected_sha256=input_hashes["calendar_sha256"])
    return spec, calendar, input_hashes


def _group_transform(frame: pd.DataFrame, column: str, fn) -> pd.Series:
    return frame.groupby("symbol", sort=False, observed=True)[column].transform(fn)


def build_event_pool(panel: pd.DataFrame, sessions: Sequence[object], *, spec_hash: str) -> pd.DataFrame:
    """Build the feature-only event union; no outcome-like columns are accepted."""
    if any(name in panel.columns for name in ("gross_return", "target5_no", "target5_end", "future_return", "label_status")):
        raise ValueError("outcome columns must not be present during event-pool preparation")
    needed = {
        "date", "symbol", "open", "high", "low", "close", "volume", "ret1", "ret3", "ret5",
        "ret10", "ret20", "ret40", "volr5_inclusive", "volr20_inclusive", "pos20", "pos60",
        "range_pct", "close_location", "gap",
    }
    missing = sorted(needed.difference(panel.columns))
    if missing:
        raise ValueError(f"signal-time panel missing required columns: {missing}")
    x = panel.loc[:, sorted(needed)].copy()
    x["date"] = pd.to_datetime(x["date"], errors="raise").dt.normalize()
    x["symbol"] = x["symbol"].astype("string")
    if x.duplicated(["date", "symbol"]).any():
        raise ValueError("signal-time panel has duplicate symbol/session rows")
    session_list = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    session_map = {pd.Timestamp(day): i for i, day in enumerate(session_list)}
    x["session_index"] = x["date"].map(session_map)
    if x["session_index"].isna().any():
        raise ValueError("feature date is absent from XTKS calendar")
    x["session_index"] = x["session_index"].astype("int32")
    x = x.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    groups = x.groupby("symbol", sort=False, observed=True)
    delta = groups["session_index"].diff()
    x["adjacent_previous_session"] = delta.eq(1)

    x["prev_close"] = groups["close"].shift(1).where(x["adjacent_previous_session"])
    x["prev_volume"] = groups["volume"].shift(1).where(x["adjacent_previous_session"])
    x["prev_ret5"] = groups["ret5"].shift(1).where(x["adjacent_previous_session"])
    x["volr5"] = x["volr5_inclusive"]
    x["volr10"] = x["volume"] / _group_transform(x, "volume", lambda s: s.rolling(10, min_periods=10).mean())
    x["volr20"] = x["volr20_inclusive"]
    x["rv10"] = _group_transform(x, "ret1", lambda s: s.rolling(10, min_periods=10).std(ddof=0))
    x["rv40"] = _group_transform(x, "ret1", lambda s: s.rolling(40, min_periods=40).std(ddof=0))
    x["prev_rv10"] = x.groupby("symbol", sort=False)["rv10"].shift(1).where(x["adjacent_previous_session"])
    x["prev_rv40"] = x.groupby("symbol", sort=False)["rv40"].shift(1).where(x["adjacent_previous_session"])
    x["rv_ratio"] = x["prev_rv10"] / x["prev_rv40"].replace(0, np.nan)
    x["prev_avg_range10"] = _group_transform(
        x, "range_pct", lambda s: s.rolling(10, min_periods=10).mean().shift(1)
    )
    x["close_loc"] = x["close_location"]

    adjacency = x["adjacent_previous_session"].astype("float64")
    gapfree10 = adjacency.groupby(x["symbol"], sort=False).transform(
        lambda s: s.rolling(9, min_periods=9).sum().eq(9)
    )
    x["volr10"] = x["volr10"].where(gapfree10)
    x["prev_avg_range10"] = x["prev_avg_range10"].where(gapfree10.groupby(x["symbol"], sort=False).shift(1).fillna(False))
    x["range_expansion"] = x["range_pct"] / x["prev_avg_range10"].replace(0, np.nan)
    gapfree20 = adjacency.groupby(x["symbol"], sort=False).transform(
        lambda s: s.rolling(20, min_periods=20).sum().eq(20)
    )
    gapfree60 = adjacency.groupby(x["symbol"], sort=False).transform(
        lambda s: s.rolling(60, min_periods=60).sum().eq(60)
    )
    prev_high20 = _group_transform(x, "high", lambda s: s.rolling(20, min_periods=20).max().shift(1))
    prev_high60 = _group_transform(x, "high", lambda s: s.rolling(60, min_periods=60).max().shift(1))
    x["break20"] = (x["close"] / prev_high20 - 1.0).where(gapfree20)
    x["break60"] = (x["close"] / prev_high60 - 1.0).where(gapfree60)

    q = x.loc[x["date"].between("2022-07-01", "2024-12-20")].copy()
    ohlcv = q[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    clean = np.isfinite(ohlcv).all(axis=1)
    if len(q):
        opn, high, low, close, volume = ohlcv.T
        clean &= (ohlcv[:, :4] > 0).all(axis=1) & (volume > 0)
        clean &= (high >= np.maximum(opn, close)) & (low <= np.minimum(opn, close)) & (high >= low)
    gap_ratio = 1.0 + pd.to_numeric(q["gap"], errors="coerce").to_numpy(dtype="float64")
    clean &= np.isfinite(gap_ratio) & (gap_ratio >= 0.60) & (gap_ratio <= 1.40)
    clean &= q["close"].ge(20.0).to_numpy() & q["prev_close"].le(1000.0).to_numpy()
    clean &= q["prev_volume"].ge(10_000).to_numpy() & q["volume"].ge(5_000).to_numpy()
    q = q.loc[clean].copy().reset_index(drop=True)

    q["evt_reversal"] = ((q["prev_ret5"] <= -0.04) & (q["ret1"] >= 0.01) & (q["close_loc"] >= 0.55) & (q["gap"] >= -0.06))
    q["evt_ignition"] = (q["ret5"].between(0.02, 0.15) & (q["ret1"] >= 0.015) & (q["volr20"] >= 1.10) & (q["pos60"] >= 0.50) & (q["close_loc"] >= 0.55))
    q["evt_breakout"] = (q["break20"].between(0.0, 0.08) & q["volr20"].between(1.0, 5.0) & (q["close_loc"] >= 0.60))
    q["evt_gap_hold"] = (q["gap"].between(0.01, 0.12) & (q["ret1"] > 0) & (q["close_loc"] >= 0.60))
    q["evt_compression_release"] = ((q["rv_ratio"] <= 1.0) & (q["range_expansion"] >= 1.15) & (q["ret1"] >= 0.015) & (q["volr20"] >= 1.10) & (q["close_loc"] >= 0.55))
    q["evt_pullback_resume"] = ((q["ret20"] >= 0.08) & (q["prev_ret5"] <= 0.0) & (q["ret1"] >= 0.015) & (q["pos60"] >= 0.50))
    event_cols = list(EVENT_RULES)
    for column in event_cols:
        q[column] = q[column].fillna(False).astype("int8")
    q["event_count"] = q[event_cols].sum(axis=1).astype("int8")
    for column in ("ret5", "ret20", "volr20", "pos60"):
        q[f"{column}_pct"] = q.groupby("date", sort=False)[column].rank(pct=True, method="average")
    q = q.loc[q["event_count"].gt(0)].copy()
    q = q.dropna(subset=MODEL_FEATURES).copy()
    q["family"] = FAMILY
    q["spec_hash"] = str(spec_hash)
    q["identity_key"] = q["symbol"]
    q["candidate_id"] = q["date"].dt.strftime("%Y%m%d") + ":" + q["symbol"].astype("string")
    q["feature_timestamp"] = q["date"].dt.strftime("%Y-%m-%d") + " close"
    if any(any(token in name.lower() for token in ("target", "label", "future", "realized_return", "exit_date")) for name in q.columns):
        raise ValueError("outcome-like column leaked into the frozen event pool")
    keep = [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "feature_timestamp", "event_count", *(name for name in MODEL_FEATURES if name != "event_count"), "close",
    ]
    return q.loc[:, keep].sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)


def fit_linear_head(train: pd.DataFrame, pred: pd.DataFrame, target: pd.Series) -> np.ndarray:
    """Small deterministic ridge head; uses only NumPy, so no external runtime is needed."""
    x_train = train.loc[:, MODEL_FEATURES].to_numpy(dtype="float64", copy=True)
    x_pred = pred.loc[:, MODEL_FEATURES].to_numpy(dtype="float64", copy=True)
    means = x_train.mean(axis=0)
    scales = x_train.std(axis=0)
    scales[~np.isfinite(scales) | (scales < 1e-10)] = 1.0
    x_train = np.clip((x_train - means) / scales, -10.0, 10.0)
    x_pred = np.clip((x_pred - means) / scales, -10.0, 10.0)
    y = pd.to_numeric(target, errors="raise").to_numpy(dtype="float64")
    if not np.isfinite(x_train).all() or not np.isfinite(x_pred).all() or not np.isfinite(y).all():
        raise ValueError("ridge inputs contain non-finite values")
    y_mean = float(y.mean())
    gram = x_train.T @ x_train
    rhs = x_train.T @ (y - y_mean)
    coefficients = np.linalg.solve(gram + np.eye(gram.shape[0]) * RIDGE_ALPHA, rhs)
    return x_pred @ coefficients + y_mean


def fit_half(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    if len(train) < 1000 or pred.empty:
        raise ValueError(f"insufficient causal model data: train={len(train)} pred={len(pred)}")
    if not (pd.to_datetime(train["exit_date"]) < pd.to_datetime(pred["period_start"].iloc[0])).all():
        raise ValueError("training labels are not fully purged before prediction period")
    out = pred.copy()
    y_ret = train["gross_return"].clip(-0.30, 0.50)
    out["pred_ret"] = fit_linear_head(train, out, y_ret)
    out["pred_hit10"] = fit_linear_head(train, out, train["gross_return"].ge(WINNER_THRESHOLD).astype(int))
    out["pred_loss10"] = fit_linear_head(train, out, train["gross_return"].le(LOSER_THRESHOLD).astype(int))
    return out


def score_periods(events: pd.DataFrame, periods: Sequence[tuple[str, str, str]]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for label, start_text, end_text in periods:
        start, end = pd.Timestamp(start_text), pd.Timestamp(end_text)
        train = events.loc[(events["exit_date"] < start) & events["label_resolved"].astype(bool)].dropna(subset=MODEL_FEATURES).copy()
        pred = events.loc[events["date"].between(start, end)].dropna(subset=MODEL_FEATURES).copy()
        if train.empty or pred.empty:
            continue
        pred["period_start"] = start
        scored = fit_half(train, pred)
        scored["model_period"] = label
        parts.append(scored)
    if not parts:
        return pd.DataFrame()
    scored = pd.concat(parts, ignore_index=True)
    # Normalize each head within the signal-day candidate pool. This prevents
    # in-sample training predictions from defining the score scale.
    for source, target in (("pred_ret", "cdf_ret"), ("pred_hit10", "cdf_hit10"), ("pred_loss10", "cdf_loss10")):
        scored[target] = scored.groupby("date", sort=False)[source].rank(pct=True, method="average")
    return scored


def score_variant(scored: pd.DataFrame, variant: dict[str, float]) -> pd.DataFrame:
    if scored.empty:
        return scored.copy()
    out = scored.copy()
    out["score"] = variant["ret"] * out["cdf_ret"] + variant["hit10"] * out["cdf_hit10"] - variant["loss10"] * out["cdf_loss10"]
    return out.loc[out["score"].ge(variant["gate"])].copy()


def select_multi_per_day(
    scored: pd.DataFrame,
    variant: dict[str, float],
    sessions: Sequence[object],
    *,
    initial_last_selected_idx: dict[str, int] | None = None,
    max_per_day: int = MAX_PER_DAY,
    cooldown_sessions: int = COOLDOWN_SESSIONS,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Select up to five gated names/day; same-symbol cooldown is causal."""
    if max_per_day < 2:
        raise ValueError("the registered multi-selection policy must allow at least two names/day")
    z = score_variant(scored, variant)
    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    date_idx = {pd.Timestamp(day): i for i, day in enumerate(calendar)}
    if not set(pd.DatetimeIndex(z["date"].unique())).issubset(date_idx):
        raise ValueError("prediction date is absent from the XTKS calendar")
    last = dict(initial_last_selected_idx or {})
    rows: list[pd.Series] = []
    for date, day in z.sort_values(["date", "score", "symbol"], ascending=[True, False, True], kind="mergesort").groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        picked = 0
        for _, row in day.iterrows():
            symbol = str(row["symbol"])
            if idx - last.get(symbol, -10_000) <= cooldown_sessions:
                continue
            rows.append(row)
            last[symbol] = idx
            picked += 1
            if picked >= max_per_day:
                break
    result = pd.DataFrame(rows).reset_index(drop=True) if rows else z.iloc[0:0].copy()
    return result, last


def _net_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return summary["round_trip_cost_scenarios"]["0.005"]


def selection_summary(
    picks: pd.DataFrame,
    sessions: Sequence[object],
    *,
    start: object,
    end: object,
) -> dict[str, Any]:
    base = label_summary(picks, costs=(0.0, 0.005, 0.01))
    out: dict[str, Any] = {"signals": base}
    out["monthly"] = {
        str(key): label_summary(group, costs=(0.0, 0.005, 0.01))
        for key, group in picks.groupby(picks["date"].dt.to_period("M"), sort=True)
    }
    out["weekly"] = {
        str(key): label_summary(group, costs=(0.0, 0.005, 0.01))
        for key, group in picks.groupby(picks["date"].dt.strftime("%G-W%V"), sort=True)
    }
    period_sessions = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    period_sessions = period_sessions[(period_sessions >= pd.Timestamp(start)) & (period_sessions <= pd.Timestamp(end))]
    daily = daily_cohorts(picks, picks, sessions=period_sessions, join_columns=("date", "symbol", "family", "spec_hash"))
    complete = daily["cohort_status"].eq("COMPLETE")
    daily.loc[complete, "cohort_return"] = daily.loc[complete, "cohort_return"] - ROUND_TRIP_COST
    out["complete_daily_cohorts"] = cohort_summary(daily, repetitions=2000)
    symbols = picks.groupby("symbol", sort=True).size().sort_values(ascending=False)
    out["symbol_concentration"] = {
        "unique_symbols": int(len(symbols)),
        "top1_signal_share": float(symbols.iloc[:1].sum() / len(picks)) if len(picks) else None,
        "top3_signal_share": float(symbols.iloc[:3].sum() / len(picks)) if len(picks) else None,
        "top10_signal_share": float(symbols.iloc[:10].sum() / len(picks)) if len(picks) else None,
    }
    return out


def passes_2024_gate(h1: dict[str, Any], h2: dict[str, Any]) -> bool:
    for metrics in (h1, h2):
        net = _net_metrics(metrics["signals"])
        daily = metrics["complete_daily_cohorts"]
        if net["n"] < 30 or net["mean"] <= 0 or net["median"] <= 0 or net["win_rate"] < 0.55:
            return False
        if net["plus10_rate"] < 0.10 or net["minus10_rate"] > 0.15 or net["mean_excluding_top3_winners"] <= 0:
            return False
        if daily["n"] < 20 or daily["mean"] <= 0 or daily["median"] <= 0:
            return False
    return True


def development_utility(h1: dict[str, Any], h2: dict[str, Any]) -> float:
    a, b = _net_metrics(h1["signals"]), _net_metrics(h2["signals"])
    return float(min(a["mean"], b["mean"]) + 0.40 * min(a["median"], b["median"]) + 0.025 * min(a["win_rate"], b["win_rate"]) + 0.035 * min(a["plus10_rate"], b["plus10_rate"]) - 0.10 * max(a["minus10_rate"], b["minus10_rate"]))


def _git_path_committed(path: Path) -> bool:
    relative = path.relative_to(BATCH.parents[1]).as_posix()
    status = subprocess.check_output(["git", "status", "--porcelain", "--", relative], cwd=BATCH.parents[1], text=True)
    return not status.strip() and subprocess.run(["git", "cat-file", "-e", f"HEAD:{relative}"], cwd=BATCH.parents[1], capture_output=True).returncode == 0


def prepare_2024_pool() -> dict[str, Any]:
    spec, calendar, input_hashes = verify_registered_inputs()
    if POOL_PATH.exists() or POOL_RECEIPT_PATH.exists():
        raise FileExistsError("2024 event pool or receipt already exists")
    prices = load_bounded_prices_2024(spec)
    panel = build_feature_panel(prices, sessions=calendar.sessions)
    pool = build_event_pool(panel, calendar.sessions, spec_hash=SPEC_SHA_PATH.read_text(encoding="utf-8").split()[0])
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = pool.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.12g", lineterminator="\n").encode("utf-8")
    POOL_PATH.write_bytes(payload)
    counts = pool.groupby(pool["date"].dt.year).size().astype(int).to_dict()
    receipt = {
        "experiment_id": EXPERIMENT_ID,
        "git_sha": git_sha(),
        "spec_sha256": hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
        "input_hashes": input_hashes,
        "implementation_hashes": implementation_hashes(),
        "event_pool_rows": int(len(pool)),
        "event_pool_rows_by_year": {str(year): count for year, count in counts.items()},
        "event_pool_sha256": sha256_file(POOL_PATH),
        "event_pool_rows_sha256": hashlib.sha256(payload).hexdigest(),
        "labels_included": False,
        "2025_plus_numeric_ohlcv_parsed": False,
        "decision": "FEATURE_ONLY_POOL_FROZEN_BEFORE_OUTCOME_ACCESS",
    }
    POOL_RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def reproduce_2024_pool() -> dict[str, Any]:
    """Rebuild the outcome-free pool independently and compare its canonical CSV digest."""
    spec, calendar, input_hashes = verify_registered_inputs()
    if not _git_path_committed(POOL_RECEIPT_PATH):
        raise ValueError("pool receipt must be committed before reproducibility check")
    if POOL_REPRO_PATH.exists():
        raise FileExistsError("pool reproducibility report already exists")
    receipt = json.loads(POOL_RECEIPT_PATH.read_text(encoding="utf-8"))
    prices = load_bounded_prices_2024(spec)
    panel = build_feature_panel(prices, sessions=calendar.sessions)
    pool = build_event_pool(panel, calendar.sessions, spec_hash=receipt["spec_sha256"])
    payload = pool.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.12g", lineterminator="\n").encode("utf-8")
    reproduced_hash = hashlib.sha256(payload).hexdigest()
    report = {
        "experiment_id": EXPERIMENT_ID,
        "git_sha": git_sha(),
        "input_hashes": input_hashes,
        "registered_event_pool_sha256": receipt["event_pool_sha256"],
        "reproduced_event_pool_sha256": reproduced_hash,
        "registered_rows": receipt["event_pool_rows"],
        "reproduced_rows": int(len(pool)),
        "row_count_match": int(len(pool)) == int(receipt["event_pool_rows"]),
        "byte_sha256_match": reproduced_hash == receipt["event_pool_sha256"],
        "labels_included": False,
        "2025_plus_numeric_ohlcv_parsed": False,
    }
    report["reproducibility_pass"] = report["row_count_match"] and report["byte_sha256_match"]
    POOL_REPRO_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return report


def load_bounded_prices_2024(spec: dict[str, Any]) -> pd.DataFrame:
    """Read rows through the 2024 purge cutoff by date prefix before OHLC parse."""
    target = CACHE / "core_multi_event_daily_through_2024.csv"
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    source_hash = spec["input_hashes"]["source_sha256"]
    cache_valid = False
    if target.exists() and manifest_path.exists():
        cache_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cache_valid = (
            cache_manifest.get("source_sha256") == source_hash
            and cache_manifest.get("through") == "2024-12-30"
            and cache_manifest.get("sha256") == sha256_file(target)
        )
    if not cache_valid:
        target.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        with SOURCE.open("rb") as src, target.open("xb") as out:
            header = src.readline()
            out.write(header)
            kept = 0
            filtered = 0
            for line in src:
                date_text = line.partition(b",")[0].decode("ascii")
                if "2022-01-04" <= date_text <= "2024-12-30":
                    out.write(line)
                    kept += 1
                elif date_text > "2024-12-30":
                    filtered += 1
            if kept == 0:
                raise ValueError("no bounded 2024 OHLCV rows found")
            out.flush()
        manifest_path.write_text(json.dumps({
            "source_sha256": source_hash,
            "sha256": sha256_file(target),
            "through": "2024-12-30",
            "kept_rows": kept,
            "post_cutoff_lines_filtered_before_numeric_parse": filtered,
            "post_cutoff_numeric_ohlcv_parsed": False,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prices = pd.read_csv(target, usecols=["date", "symbol", "open", "high", "low", "close", "volume"], parse_dates=["date"], dtype={"symbol": "string"})
    prices["date"] = pd.to_datetime(prices["date"], errors="raise").dt.normalize()
    if prices["date"].max() > pd.Timestamp("2024-12-30"):
        raise ValueError("bounded price file contains post-2024 rows")
    return prices.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)


def discover_2024() -> dict[str, Any]:
    spec, calendar, input_hashes = verify_registered_inputs()
    if not _git_path_committed(POOL_RECEIPT_PATH):
        raise ValueError("2024 pool receipt must be committed before outcome access")
    receipt = json.loads(POOL_RECEIPT_PATH.read_text(encoding="utf-8"))
    if not _git_path_committed(POOL_REPRO_PATH):
        raise ValueError("independent pool reproduction report must be committed before outcome access")
    reproduction = json.loads(POOL_REPRO_PATH.read_text(encoding="utf-8"))
    if reproduction.get("reproducibility_pass") is not True:
        raise ValueError("feature-only event pool failed independent reproduction")
    if receipt["event_pool_sha256"] != sha256_file(POOL_PATH):
        raise ValueError("event pool artifact hash differs from the committed receipt")
    if DISCOVERY_PATH.exists() or DISCOVERY_MD_PATH.exists() or DISCOVERY_LABELS.exists():
        raise FileExistsError("2024 model or report artifacts already exist")
    pool = pd.read_csv(POOL_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    prices = load_bounded_prices_2024(spec)
    signal_keys = pool[["date", "symbol", "close"]].copy()
    labels = label_builder.build_labels_for_eligible_signals(prices, signal_keys, calendar)
    labels["family"] = FAMILY
    labels["spec_hash"] = receipt["spec_sha256"]
    labels["target5_end"] = labels["exit_date"]
    labels["target5_no"] = labels["gross_return"]
    DISCOVERY_LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(DISCOVERY_LABELS, index=False, date_format="%Y-%m-%d", float_format="%.12g")
    events = pool.merge(labels, on=["date", "symbol", "family", "spec_hash"], how="left", validate="one_to_one")
    events = events.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    periods = [("2024H1", "2024-01-01", "2024-06-30"), ("2024H2", "2024-07-01", "2024-12-20")]
    scored = score_periods(events, periods)
    if scored.empty:
        raise ValueError("no 2024 walk-forward event rows were scored")
    date_sessions = calendar.sessions
    variants_report: dict[str, Any] = {}
    for name, variant in VARIANTS.items():
        picks, _state = select_multi_per_day(scored, variant, date_sessions)
        h1 = selection_summary(
            picks.loc[picks["date"].between("2024-01-01", "2024-06-30")], date_sessions,
            start="2024-01-01", end="2024-06-30",
        )
        h2 = selection_summary(
            picks.loc[picks["date"].between("2024-07-01", "2024-12-20")], date_sessions,
            start="2024-07-01", end="2024-12-20",
        )
        passed = passes_2024_gate(h1, h2)
        variants_report[name] = {
            "variant": variant, "2024H1": h1, "2024H2": h2,
            "gate_pass": passed,
            "robust_utility": development_utility(h1, h2) if passed else None,
            "selected_rows": int(len(picks)),
            "max_names_any_day": int(picks.groupby("date").size().max()) if not picks.empty else 0,
            "last_session_selected_symbols": sorted(picks.loc[picks["date"].eq(pd.Timestamp("2024-12-20")), "symbol"].astype(str).tolist()),
        }
    eligible = [(v["robust_utility"], name) for name, v in variants_report.items() if v["gate_pass"]]
    locked = max(eligible)[1] if eligible else None
    report = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "git_sha": git_sha(),
        "decision": "LOCK_VARIANT_FOR_SEPARATE_2025_FREEZE" if locked else "REJECT_MULTI_EVENT_QUALITY",
        "evidence_level": "RETROSPECTIVE_2024_DEVELOPMENT",
        "spec_sha256": hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
        "input_hashes": input_hashes,
        "implementation_hashes": implementation_hashes(),
        "event_pool_sha256": receipt["event_pool_sha256"],
        "pool_reproduction_sha256": sha256_file(POOL_REPRO_PATH),
        "pool_reproduction_pass": reproduction["reproducibility_pass"],
        "labels_sha256": sha256_file(DISCOVERY_LABELS),
        "signal_rows": int(len(scored)),
        "resolved_rows": int(scored["label_resolved"].astype(bool).sum()),
        "variants_2024_only": variants_report,
        "locked_variant": locked,
        "implementation_complexity": {
            "event_rules": len(EVENT_RULES),
            "model_features": len(MODEL_FEATURES),
            "linear_heads": 3,
            "fixed_score_variants": len(VARIANTS),
            "model_refits_in_2024": 2,
            "additional_python_packages_required": [],
            "production_integrations": 0,
        },
        "2025_plus_features_or_outcomes_opened": False,
        "production_modified": False,
    }
    DISCOVERY_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Multi-event quality score — 2024 development", "", f"- Decision: `{report['decision']}`.", "- 2024 is retrospective development, not OOS. 2025+ data were not read.", "- Each model variant may select up to five names per XTKS session; same-symbol one-session cooldown is applied after score gating.", "", "| Variant | H1 n | H1 net mean | H1 net median | H1 win | H2 n | H2 net mean | H2 net median | H2 win | Gate |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for name, row in variants_report.items():
        a, b = _net_metrics(row["2024H1"]["signals"]), _net_metrics(row["2024H2"]["signals"])
        lines.append(f"| {name} | {a['n']} | {a['mean']:.4%} | {a['median']:.4%} | {a['win_rate']:.1%} | {b['n']} | {b['mean']:.4%} | {b['median']:.4%} | {b['win_rate']:.1%} | {row['gate_pass']} |")
    lines.extend(["", "The JSON report contains all win/loss thresholds, top-winner exclusions, monthly/weekly cohorts, bootstrap intervals, symbol concentration, unresolved counts, and the frozen variant scores."])
    DISCOVERY_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-2024", "reproduce-2024-pool", "discover-2024"))
    args = parser.parse_args()
    if args.command == "prepare-2024":
        result = prepare_2024_pool()
    elif args.command == "reproduce-2024-pool":
        result = reproduce_2024_pool()
    else:
        result = discover_2024()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
