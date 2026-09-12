"""Frozen Core-1 Ridge discovery and locked 2024 confirmation; never reads 2025/2026."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .artifact_store import read_verified_parquet, sha256_file, write_parquet_artifact, write_parquet_batches
from .core_moderate_ridge import (
    FAMILY_SPEC, FAMILY_SPEC_SHA256, FEATURES, fit_ridge,
    predict_ridge, signal_quality_mask,
)
from .evaluation import (
    cohort_summary, daily_cohorts, label_summary, return_metrics,
)
from .feature_panel import (
    FEATURE_COLUMNS, LOCAL_FEATURE_COLUMNS, MARKET_FEATURE_COLUMNS,
    build_market_return_table, compute_symbol_features,
)
from .selection import PolicySpec, apply_selection_policy, rank_candidate_pool
from .session_calendar import SessionCalendar
from .temporal_policy import validate_period_access


BATCH_DIR = Path(__file__).resolve().parent
REPORT_DIR = BATCH_DIR / "reports"
SOURCE_PATH = BATCH_DIR / ".cache" / "artifacts" / "tse_daily.csv"
CALENDAR_PATH = BATCH_DIR / "reference" / "xtks_sessions.csv"
CALENDAR_MANIFEST = BATCH_DIR / "reference" / "xtks_sessions.manifest.json"
PRESERVATION_MANIFEST = BATCH_DIR / "PRESERVATION_MANIFEST.json"
FROZEN_SPEC_PATH = REPORT_DIR / "core_moderate_ridge_spec_v2.json"
POLICY_LOCK_PATH = REPORT_DIR / "core_moderate_ridge_discovery_policy_lock_v2.json"
DISCOVERY_REPORT = REPORT_DIR / "core_moderate_ridge_v2_discovery.json"
VALIDATION_REPORT = REPORT_DIR / "core_moderate_ridge_v2_validation_2024.json"

CODE_PATHS = (
    "core_moderate_ridge.py",
    "core_moderate_ridge_audit.py",
    "feature_panel.py",
    "evaluation.py",
    "selection.py",
    "session_calendar.py",
    "temporal_policy.py",
    "artifact_store.py",
)
DATA_START = pd.Timestamp("2022-01-04")
DISCOVERY_START = pd.Timestamp("2022-07-01")
DISCOVERY_END = pd.Timestamp("2023-12-31")
VALIDATION_START = pd.Timestamp("2024-01-01")
VALIDATION_END = pd.Timestamp("2024-12-31")
ASSUMED_COST = 0.005


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _code_hashes() -> dict[str, str]:
    return {name: sha256_file(BATCH_DIR / name) for name in CODE_PATHS}


def _expected_source_hash() -> str:
    manifest = json.loads(PRESERVATION_MANIFEST.read_text(encoding="utf-8"))
    return str(next(item["member_sha256"] for item in manifest["artifacts"] if item["member"] == SOURCE_PATH.name))


def freeze_spec() -> dict[str, object]:
    if FROZEN_SPEC_PATH.exists():
        raise FileExistsError("registered Core-1 spec already exists; do not replace a frozen experiment")
    source_hash = sha256_file(SOURCE_PATH)
    if source_hash != _expected_source_hash():
        raise ValueError("daily source differs from preserved artifact SHA")
    calendar_meta = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR_PATH, expected_sha256=str(calendar_meta["csv_sha256"]))
    code_hashes = _code_hashes()
    frozen_at = datetime.now(timezone.utc).isoformat()
    core_payload = {
        "family_spec": FAMILY_SPEC,
        "family_spec_sha256": FAMILY_SPEC_SHA256,
        "source_sha256": source_hash,
        "calendar_sha256": calendar.sha256,
        "code_sha256": code_hashes,
    }
    receipt = {
        "schema_version": 1,
        **core_payload,
        "frozen_at_utc": frozen_at,
        "phase_opened_at_utc": None,
        "spec_sha256": _canonical_hash(core_payload),
        "source_date_range_used_by_discovery": ["2022-01-04", "2023-12-31"],
        "source_date_range_used_by_validation": ["2022-01-04", "2024-12-31"],
        "no_2025_2026_outcomes_read": True,
    }
    _write_json(FROZEN_SPEC_PATH, receipt)
    return receipt


def load_frozen_spec() -> dict[str, object]:
    receipt = json.loads(FROZEN_SPEC_PATH.read_text(encoding="utf-8"))
    expected = _canonical_hash({
        "family_spec": receipt["family_spec"],
        "family_spec_sha256": receipt["family_spec_sha256"],
        "source_sha256": receipt["source_sha256"],
        "calendar_sha256": receipt["calendar_sha256"],
        "code_sha256": receipt["code_sha256"],
    })
    if receipt.get("spec_sha256") != expected:
        raise ValueError("frozen Core-1 spec hash is invalid")
    if receipt["family_spec_sha256"] != FAMILY_SPEC_SHA256:
        raise ValueError("Core-1 family declaration changed after freeze")
    if receipt["code_sha256"] != _code_hashes():
        raise ValueError("Core-1 implementation changed after freeze; create a new experiment before reading outcomes")
    if receipt["source_sha256"] != sha256_file(SOURCE_PATH) or receipt["source_sha256"] != _expected_source_hash():
        raise ValueError("preserved daily source changed after freeze")
    calendar_meta = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    calendar = SessionCalendar.from_csv(CALENDAR_PATH, expected_sha256=str(calendar_meta["csv_sha256"]))
    if receipt["calendar_sha256"] != calendar.sha256:
        raise ValueError("calendar changed after freeze")
    return receipt


def _calendar() -> SessionCalendar:
    meta = json.loads(CALENDAR_MANIFEST.read_text(encoding="utf-8"))
    return SessionCalendar.from_csv(CALENDAR_PATH, expected_sha256=str(meta["csv_sha256"]))


def _read_bars(through: pd.Timestamp) -> pd.DataFrame:
    expected = _expected_source_hash()
    actual = sha256_file(SOURCE_PATH)
    if actual != expected:
        raise ValueError("OHLCV source differs from preservation manifest")
    expected_header = ["date", "open", "high", "low", "close", "volume", "symbol"]
    through_text = through.date().isoformat()
    chunks: list[pd.DataFrame] = []
    rows: list[list[str]] = []
    def flush() -> None:
        if not rows:
            return
        frame = pd.DataFrame.from_records(rows, columns=expected_header)
        frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
        frame["symbol"] = frame["symbol"].astype("string")
        chunks.append(frame)
        rows.clear()

    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if header != expected_header:
            raise ValueError("preserved daily CSV header differs from its frozen schema")
        for row in reader:
            if len(row) != len(expected_header):
                raise ValueError("preserved daily CSV has a malformed row")
            # ISO date comparison lets the streaming reader skip later OHLCV
            # values without converting or inspecting their numerical fields.
            if row[0] <= through_text:
                rows.append(row)
                if len(rows) >= 100_000:
                    flush()
    flush()
    if not chunks:
        raise ValueError("no daily bars exist through the requested research cutoff")
    bars = pd.concat(chunks, ignore_index=True)
    if bars.duplicated(["date", "symbol"]).any():
        raise ValueError("source contains duplicate symbol/session rows")
    return bars


def iter_symbol_feature_batches(
    bars: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    *,
    symbols_per_batch: int = 25,
):
    """Yield causal, full-market-context feature batches with bounded memory."""
    if symbols_per_batch < 1:
        raise ValueError("symbols_per_batch must be positive")
    market = build_market_return_table(bars, sessions=sessions).set_index("date")
    pending: list[pd.DataFrame] = []
    symbol_count = 0
    for _symbol, symbol_bars in bars.groupby("symbol", sort=True, observed=True):
        local = compute_symbol_features(symbol_bars, sessions=sessions)
        for column in (
            "market_median_ret1", "market_median_ret5",
            "market_median_ret1_lag1", "market_median_ret5_lag1",
        ):
            local[column] = local["date"].map(market[column]).astype("float32")
        local["rel_ret5_lag1"] = (
            local["ret5"] - local["market_median_ret5_lag1"]
        ).astype("float32")
        local["symbol"] = local["symbol"].astype("string")
        local = local.loc[:, ["date", "symbol", "open", "high", "low", "close", "volume", *FEATURE_COLUMNS]]
        if local.duplicated(["date", "symbol"]).any():
            raise RuntimeError("per-symbol feature batch contains duplicate date/symbol rows")
        pending.append(local)
        symbol_count += 1
        if symbol_count >= symbols_per_batch:
            yield pd.concat(pending, ignore_index=True)
            pending.clear()
            symbol_count = 0
    if pending:
        yield pd.concat(pending, ignore_index=True)


def _feature_panel(through: pd.Timestamp, calendar: SessionCalendar) -> pd.DataFrame:
    panel_path = BATCH_DIR / ".cache" / f"core_moderate_v2_features_through_{through.year}.parquet"
    if panel_path.exists():
        panel, metadata = read_verified_parquet(panel_path)
        if metadata.get("source_sha256") != sha256_file(SOURCE_PATH):
            raise ValueError("cached Core-1 panel source hash mismatch")
        if metadata.get("calendar_sha256") != calendar.sha256 or metadata.get("through") != through.date().isoformat():
            raise ValueError("cached Core-1 panel period or calendar mismatch")
        return panel
    bars = _read_bars(through)
    receipt = write_parquet_batches(
        iter_symbol_feature_batches(bars, calendar.sessions),
        panel_path,
        metadata={
            "schema_version": "tvfree-core-moderate-features-v1",
            "source_sha256": _expected_source_hash(),
            "calendar_sha256": calendar.sha256,
            "start": DATA_START.date().isoformat(),
            "through": through.date().isoformat(),
            "feature_timestamp": "official session close; no future data columns",
            "feature_columns": list(FEATURES),
            "labels_included": False,
            "later_numeric_ohlcv_values_parsed": False,
        },
    )
    if receipt["source_sha256"] != _expected_source_hash():
        raise ValueError("bounded feature panel references the wrong source artifact")
    del market, bars
    gc.collect()
    return read_verified_parquet(panel_path)[0]


def build_labels_for_eligible_signals(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    calendar: SessionCalendar,
) -> pd.DataFrame:
    """Vectorized by-symbol canonical labels with fail-closed daily actionability checks."""
    required = {"date", "symbol", "open", "high", "low", "close", "volume"}
    if not required.issubset(prices.columns):
        raise ValueError("label prices are missing required OHLCV fields")
    if not {"date", "symbol", "close"}.issubset(signals.columns):
        raise ValueError("label signals must contain date,symbol,close")
    if prices.duplicated(["date", "symbol"]).any() or signals.duplicated(["date", "symbol"]).any():
        raise ValueError("label inputs must be unique by date and symbol")
    session_index = {pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}
    price_groups = {str(symbol): group for symbol, group in prices.groupby("symbol", sort=False, observed=True)}
    outputs: list[pd.DataFrame] = []

    for symbol, signal_group in signals.groupby("symbol", sort=False, observed=True):
        symbol = str(symbol)
        price_group = price_groups.get(symbol)
        group = signal_group.loc[:, ["date", "symbol", "close"]].copy()
        group["date"] = pd.to_datetime(group["date"], errors="raise").dt.normalize()
        positions = group["date"].map(session_index).to_numpy(dtype="int64")
        count = len(group)
        status = np.full(count, "RESOLVED", dtype=object)
        end_position = positions + 5
        horizon_ok = end_position < len(calendar.sessions)
        status[~horizon_ok] = "CALENDAR_HORIZON_NOT_AVAILABLE"
        eligible = horizon_ok.copy()
        signal_close = pd.to_numeric(group["close"], errors="coerce").to_numpy(dtype="float64")
        invalid_signal = ~np.isfinite(signal_close) | (signal_close <= 0)
        status[eligible & invalid_signal] = "INVALID_SIGNAL_CLOSE"
        eligible &= ~invalid_signal

        if price_group is None:
            status[eligible] = "MISSING_ENTRY_BAR"
            eligible[:] = False
            aligned = None
        else:
            price_group = price_group.copy()
            price_group["date"] = pd.to_datetime(price_group["date"], errors="raise").dt.normalize()
            aligned = price_group.set_index("date").reindex(calendar.sessions)

        if aligned is not None:
            columns = {}
            for name in ("open", "high", "low", "close", "volume"):
                columns[name] = pd.to_numeric(aligned[name], errors="coerce").to_numpy(dtype="float64")
            row_exists = aligned["symbol"].notna().to_numpy()
            numeric = np.column_stack([columns[name] for name in ("open", "high", "low", "close", "volume")])
            finite = np.isfinite(numeric).all(axis=1)
            positive_price = (numeric[:, :4] > 0).all(axis=1)
            in_range = (
                (columns["high"] >= np.maximum(columns["open"], columns["close"]))
                & (columns["low"] <= np.minimum(columns["open"], columns["close"]))
                & (columns["high"] >= columns["low"])
            )
            volume_ok = columns["volume"] > 0
            previous_close = np.roll(columns["close"], 1)
            previous_close[0] = np.nan
            gap_ratio = columns["open"] / previous_close
            gap_ok = np.isfinite(gap_ratio) & (gap_ratio >= 0.60) & (gap_ratio <= 1.40)
            daily_ok = row_exists & finite & positive_price & in_range & volume_ok & gap_ok
            # Zero means no failure; positive offsets are missing bars and
            # negative codes distinguish invalid bars, zero volume, and gaps.
            first_bad = np.zeros(count, dtype="int8")
            for offset in range(1, 6):
                future = positions + offset
                active = eligible & (first_bad == 0)
                missing = active & ~row_exists[np.minimum(future, len(row_exists) - 1)]
                if missing.any():
                    first_bad[missing] = offset
                    continue_mask = active & ~missing
                else:
                    continue_mask = active
                valid = daily_ok[np.minimum(future, len(daily_ok) - 1)]
                bad = continue_mask & ~valid
                if bad.any():
                    ix = np.flatnonzero(bad)
                    fpos = future[ix]
                    numeric_bad = ~finite[fpos] | ~positive_price[fpos] | ~in_range[fpos]
                    zero_volume = finite[fpos] & positive_price[fpos] & in_range[fpos] & ~volume_ok[fpos]
                    gap_bad = finite[fpos] & positive_price[fpos] & in_range[fpos] & volume_ok[fpos] & ~gap_ok[fpos]
                    if numeric_bad.any():
                        first_bad[ix[numeric_bad]] = -offset
                    if zero_volume.any():
                        first_bad[ix[zero_volume]] = -10 - offset
                    if gap_bad.any():
                        first_bad[ix[gap_bad]] = -20 - offset
                eligible &= (first_bad == 0) | (first_bad > 0)

            for offset in range(1, 6):
                bad_mask = first_bad == offset
                if bad_mask.any():
                    status[bad_mask] = (
                        "MISSING_ENTRY_BAR" if offset == 1 else
                        "MISSING_EXIT_BAR" if offset == 5 else
                        "MISSING_HOLDING_SESSION_BAR"
                    )
                invalid_mask = first_bad == -offset
                if invalid_mask.any():
                    status[invalid_mask] = (
                        "INVALID_ENTRY_OHLCV" if offset == 1 else
                        "INVALID_EXIT_OHLCV" if offset == 5 else
                        "INVALID_HOLDING_OHLCV"
                    )
                volume_mask = first_bad == -10 - offset
                if volume_mask.any():
                    status[volume_mask] = "ENTRY_ZERO_OR_UNKNOWN_VOLUME" if offset == 1 else "ZERO_VOLUME_HOLDING_SESSION"
                gap_mask = first_bad == -20 - offset
                if gap_mask.any():
                    status[gap_mask] = "POTENTIAL_SPLIT_OR_EXTREME_GAP"

            entry_positions = np.minimum(positions + 1, len(calendar.sessions) - 1)
            exit_positions = np.minimum(positions + 5, len(calendar.sessions) - 1)
            entry = columns["open"][entry_positions]
            exit_ = columns["close"][exit_positions]
            resolved = (status == "RESOLVED") & horizon_ok & np.isfinite(entry) & np.isfinite(exit_) & (entry > 0)
            gross = np.full(count, np.nan, dtype="float64")
            gross[resolved] = exit_[resolved] / entry[resolved] - 1.0
        if aligned is None:
            entry = np.full(count, np.nan)
            exit_ = np.full(count, np.nan)
            gross = np.full(count, np.nan)
        exit_date = pd.Series(pd.NaT, index=np.arange(count), dtype="datetime64[ns]")
        exit_date.loc[horizon_ok] = pd.DatetimeIndex(calendar.sessions[end_position[horizon_ok]])
        outputs.append(pd.DataFrame({
            "date": group["date"].to_numpy(),
            "symbol": group["symbol"].astype("string").to_numpy(),
            "entry_date": pd.DatetimeIndex(calendar.sessions[np.minimum(positions + 1, len(calendar.sessions) - 1)]),
            "exit_date": exit_date.to_numpy(),
            "entry_price": entry,
            "exit_price": exit_,
            "gross_return": gross,
            "label_status": status,
            "label_resolved": status == "RESOLVED",
            "label_available_at": exit_date.to_numpy(),
        }))
    labels = pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
    if labels.duplicated(["date", "symbol"]).any():
        raise RuntimeError("canonical label builder created duplicate keys")
    labels["family"] = str(FAMILY_SPEC["family"])
    return labels.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)


def _prepare_panel(panel: pd.DataFrame, calendar: SessionCalendar) -> pd.DataFrame:
    columns = ["date", "symbol", "open", "high", "low", "close", "volume", *FEATURES]
    data = panel.loc[:, columns].copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    data["symbol"] = data["symbol"].astype("string")
    if data.duplicated(["date", "symbol"]).any():
        raise ValueError("feature panel has duplicate symbol/session rows")
    date_positions = {pd.Timestamp(day): index for index, day in enumerate(calendar.sessions)}
    data["session_index"] = data["date"].map(date_positions)
    if data["session_index"].isna().any():
        raise ValueError("feature panel contains a date outside frozen XTKS calendar")
    data["session_index"] = data["session_index"].astype("int32")
    data = data.loc[signal_quality_mask(data)].copy()
    return data.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)


def _quarter_ranges(calendar: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.DatetimeIndex]]:
    sessions = calendar[(calendar >= start) & (calendar <= end)]
    frame = pd.DataFrame({"date": sessions})
    ranges = []
    for _quarter, group in frame.groupby(frame["date"].dt.to_period("Q"), sort=True):
        dates = pd.DatetimeIndex(group["date"])
        ranges.append((pd.Timestamp(dates[0]), dates))
    return ranges


def score_by_quarter(
    panel: pd.DataFrame,
    labels: pd.DataFrame,
    calendar: SessionCalendar,
    *,
    score_start: pd.Timestamp,
    score_end: pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    """Quarter fits use only labels whose canonical exit preceded the quarter."""
    model_columns = ["date", "symbol", "session_index", *FEATURES]
    sampled_training = panel.loc[
        panel["date"].between(DATA_START, score_end)
        & panel["session_index"].mod(5).eq(0),
        model_columns,
    ]
    train_frame = sampled_training.merge(
        labels.loc[:, ["date", "symbol", "gross_return", "label_resolved", "label_available_at"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )
    score_frames: list[pd.DataFrame] = []
    fit_receipts: list[dict[str, object]] = []
    fitted_models: list[dict[str, object]] = []
    for fit_date, quarter_dates in _quarter_ranges(calendar.sessions, score_start, score_end):
        matured = train_frame.loc[
            train_frame["date"].lt(fit_date)
            & train_frame["label_resolved"].fillna(False).astype(bool)
            & pd.to_datetime(train_frame["label_available_at"], errors="coerce").lt(fit_date)
        ]
        if len(matured) < 500:
            raise ValueError(f"INCONCLUSIVE: fewer than 500 mature sampled training rows at {fit_date.date()}")
        model = fit_ridge(matured.loc[:, list(FEATURES)].to_numpy(), matured["gross_return"].to_numpy())
        current = panel.loc[panel["date"].isin(quarter_dates), model_columns].copy()
        if current.empty:
            continue
        current["predicted_capped_return"] = predict_ridge(model, current.loc[:, list(FEATURES)].to_numpy())
        current["model_fit_date"] = fit_date
        score_frames.append(current)
        fit_receipts.append({
            "fit_date": fit_date.date().isoformat(),
            "fit_n_resolved_sampled": int(len(matured)),
            "earliest_train_signal": matured["date"].min().date().isoformat(),
            "latest_train_signal": matured["date"].max().date().isoformat(),
            "latest_label_available_at": pd.to_datetime(matured["label_available_at"]).max().date().isoformat(),
            "target_mean_capped": model["target_mean"],
            "in_sample_r2_descriptive_only": model["training_r2_in_sample"],
        })
        fitted_models.append({
            "fit_date": fit_date.date().isoformat(),
            "n_train": model["n_train"],
            "target_mean": float(model["target_mean"]),
            "lower": np.asarray(model["lower"], dtype=float).tolist(),
            "upper": np.asarray(model["upper"], dtype=float).tolist(),
            "mean": np.asarray(model["mean"], dtype=float).tolist(),
            "scale": np.asarray(model["scale"], dtype=float).tolist(),
            "coefficient": np.asarray(model["coefficient"], dtype=float).tolist(),
            "intercept": float(model["intercept"]),
            "feature_order": list(FEATURES),
            "alpha": 10.0,
        })
    if not score_frames:
        raise ValueError("no quarterly Core-1 score frames were produced")
    scored = pd.concat(score_frames, ignore_index=True)
    scored = scored.loc[scored["date"].between(score_start, score_end)].copy()
    if scored.duplicated(["date", "symbol"]).any():
        raise RuntimeError("quarter scoring produced duplicate symbol/session rows")
    return scored.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True), fit_receipts, fitted_models


def _return_from_metric(value: object, cost: float = ASSUMED_COST) -> float | None:
    if value is None:
        return None
    return float(value) - cost


def _pool_daily(labels: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    grouped = labels.groupby("date", sort=True).agg(
        candidate_count=("symbol", "size"),
        resolved_count=("label_resolved", "sum"),
        cohort_gross=("gross_return", "mean"),
    )
    grouped["cohort_status"] = np.where(
        grouped["candidate_count"].eq(grouped["resolved_count"]), "COMPLETE", "PARTIAL_UNRESOLVED",
    )
    grouped["cohort_return"] = np.where(
        grouped["cohort_status"].eq("COMPLETE"), grouped["cohort_gross"] - ASSUMED_COST, np.nan,
    )
    out = pd.DataFrame({"date": calendar}).merge(grouped.reset_index(), on="date", how="left")
    out["candidate_count"] = out["candidate_count"].fillna(0).astype("int64")
    out["resolved_count"] = out["resolved_count"].fillna(0).astype("int64")
    out["cohort_status"] = out["cohort_status"].fillna("ABSTAIN")
    out.loc[out["candidate_count"].eq(0), "cohort_return"] = np.nan
    out["selected_count"] = out["candidate_count"]
    out["unresolved_count"] = out["candidate_count"] - out["resolved_count"]
    return out


def _selection_report(
    *,
    ranked: pd.DataFrame,
    labels: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    top_n: int,
    family: str,
    spec_hash: str,
    pool_metrics: dict[str, object],
    pool_daily: pd.DataFrame,
    phase_name: str,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    policy = PolicySpec("core", top_n, f"{family}-top{top_n}")
    result = apply_selection_policy(ranked, sessions=sessions, policy=policy)
    selected = result.selected
    selected_labels = selected.loc[:, ["date", "symbol", "family", "spec_hash"]].merge(
        labels,
        on=["date", "symbol", "family", "spec_hash"],
        how="left", validate="one_to_one",
    )
    if selected_labels["label_resolved"].isna().any():
        selected_labels["label_resolved"] = selected_labels["label_resolved"].fillna(False)
        selected_labels["label_status"] = selected_labels["label_status"].fillna("LABEL_ROW_MISSING")
    signal = label_summary(selected_labels, costs=(0.0, 0.005, 0.01))
    daily = daily_cohorts(selected, selected_labels, sessions=sessions)
    daily["cohort_return"] = daily["cohort_return"] - ASSUMED_COST
    cohorts = cohort_summary(daily, repetitions=2000)
    policy_active = daily.loc[daily["selected_count"].gt(0) & daily["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]]
    pool_active = pool_daily.loc[pool_daily["cohort_status"].eq("COMPLETE"), ["date", "cohort_return"]]
    paired = policy_active.merge(pool_active, on="date", how="inner", suffixes=("_policy", "_pool"), validate="one_to_one")
    pair_result = {
        "common_complete_active_days": int(len(paired)),
        "policy_mean_on_common_days": float(paired["cohort_return_policy"].mean()) if len(paired) else None,
        "pool_mean_on_common_days": float(paired["cohort_return_pool"].mean()) if len(paired) else None,
        "mean_difference": float((paired["cohort_return_policy"] - paired["cohort_return_pool"]).mean()) if len(paired) else None,
    }
    net_signal = signal["round_trip_cost_scenarios"]["0.005"]
    net_cohort_values = daily.loc[daily["cohort_status"].eq("COMPLETE"), "cohort_return"]
    net_cohort = return_metrics(net_cohort_values)
    pool_net = pool_metrics["round_trip_cost_scenarios"]["0.005"]
    gates = {
        "signal_mean_positive": net_signal["mean"] is not None and net_signal["mean"] > 0,
        "signal_median_positive": net_signal["median"] is not None and net_signal["median"] > 0,
        "signal_mean_ex_top3_positive": net_signal["mean_excluding_top3_winners"] is not None and net_signal["mean_excluding_top3_winners"] > 0,
        "cohort_mean_positive": net_cohort["mean"] is not None and net_cohort["mean"] > 0,
        "cohort_median_positive": net_cohort["median"] is not None and net_cohort["median"] > 0,
        "cohort_mean_ex_top3_positive": net_cohort["mean_excluding_top3_winners"] is not None and net_cohort["mean_excluding_top3_winners"] > 0,
        "ranking_value_add_common_day_count": pair_result["common_complete_active_days"] >= 20,
        "ranking_value_add_positive": pair_result["mean_difference"] is not None and pair_result["mean_difference"] > 0,
        "minus10_not_worse_than_pool": net_signal["minus10_rate"] is not None and pool_net["minus10_rate"] is not None and net_signal["minus10_rate"] <= pool_net["minus10_rate"],
        "minus20_not_worse_than_pool": net_signal["minus20_rate"] is not None and pool_net["minus20_rate"] is not None and net_signal["minus20_rate"] <= pool_net["minus20_rate"],
    }
    policy_months = pd.to_datetime(selected["date"]).dt.to_period("M") if len(selected) else pd.Series(dtype="period[M]")
    total_months = max(1, len(pd.period_range(sessions.min(), sessions.max(), freq="M")))
    frequency = {
        "selected_signals": int(len(selected)),
        "discovery_calendar_months": int(total_months),
        "signals_per_calendar_month": float(len(selected) / total_months),
        "five_per_month_objective_met": bool(len(selected) / total_months >= 5),
        "selected_months": int(policy_months.nunique()) if len(selected) else 0,
        "maximum_selected_per_day": int(selected.groupby("date").size().max()) if len(selected) else 0,
    }
    report = {
        "top_n": top_n,
        "policy_sha256": result.policy_sha256,
        "selection_sha256": result.selection_sha256,
        "signal_metrics": signal,
        "daily_cohort_net_metrics": net_cohort,
        "cohort_detail_including_month_week_bootstrap": cohorts,
        "ranking_value_add": pair_result,
        "frequency": frequency,
        "gates": gates,
        "passes_all_gates": all(gates.values()),
        "selected_symbols_by_month": {
            str(month): int(count)
            for month, count in selected.assign(month=pd.to_datetime(selected["date"]).dt.to_period("M").astype(str)).groupby("month")["symbol"].nunique().items()
        } if len(selected) else {},
        "selected_outcome_concentration": {
            "best_symbol_mean_net": float((selected_labels.assign(net=selected_labels["gross_return"] - ASSUMED_COST).dropna(subset=["net"]).groupby("symbol")["net"].mean().max())) if selected_labels["gross_return"].notna().any() else None,
            "best_month_mean_net": float((selected_labels.assign(month=pd.to_datetime(selected_labels["date"]).dt.to_period("M").astype(str), net=selected_labels["gross_return"] - ASSUMED_COST).dropna(subset=["net"]).groupby("month")["net"].mean().max())) if selected_labels["gross_return"].notna().any() else None,
        },
    }
    # The full rank trace is reproducible from the preserved pool and policy
    # and is intentionally not retained four times in memory.
    artifacts = {"selected": selected}
    return report, artifacts


def _phase(period: str) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, str]:
    if period == "discovery":
        return DISCOVERY_START, DISCOVERY_END, DISCOVERY_END, "discovery_selection"
    if period == "validation_2024":
        return VALIDATION_START, VALIDATION_END, VALIDATION_END, "locked_validation"
    raise ValueError(f"unsupported Core-1 period {period}")


def run_period(period: str) -> dict[str, object]:
    frozen = load_frozen_spec()
    start, period_end, source_end, access_intent = _phase(period)
    calendar_obj = _calendar()
    phase_opened_at = datetime.now(timezone.utc).isoformat()
    locked = None
    if period == "discovery":
        access = validate_period_access(
            intent="select_policy", start=start, end=period_end,
            spec_sha256=str(frozen["spec_sha256"]),
        )
        top_n_values = [1, 2, 3, 5]
        report_path = DISCOVERY_REPORT
    else:
        if not POLICY_LOCK_PATH.exists():
            raise ValueError("2024 is locked until a discovery Top-N policy passes and is frozen")
        locked = json.loads(POLICY_LOCK_PATH.read_text(encoding="utf-8"))
        if locked.get("spec_sha256") != frozen["spec_sha256"] or locked.get("decision") != "PROMOTE_TO_2024_CONFIRMATION":
            raise ValueError("2024 policy lock does not match a passing discovery spec")
        top_n_values = [int(locked["top_n"])]
        access = validate_period_access(
            intent="locked_validation", start=start, end=period_end,
            spec_sha256=str(frozen["spec_sha256"]),
            frozen_spec_sha256=str(locked["spec_sha256"]),
            spec_frozen_at=locked["frozen_at_utc"], phase_opened_at=phase_opened_at,
        )
        report_path = VALIDATION_REPORT

    last_session = calendar_obj.sessions[calendar_obj.sessions <= period_end][-1]
    panel = _feature_panel(last_session, calendar_obj)
    prepared = _prepare_panel(panel, calendar_obj)
    del panel
    gc.collect()
    prices = _read_bars(source_end)
    labels = build_labels_for_eligible_signals(prices, prepared, calendar_obj)
    del prices
    gc.collect()
    scored, fit_receipts, fitted_models = score_by_quarter(
        prepared, labels, calendar_obj,
        score_start=DISCOVERY_START if period == "discovery" else VALIDATION_START,
        score_end=period_end,
    )
    scored["family"] = str(FAMILY_SPEC["family"])
    scored["spec_hash"] = str(frozen["spec_sha256"])
    scored["identity_key"] = scored["symbol"].astype("string")
    scored["candidate_id"] = pd.to_datetime(scored["date"]).dt.strftime("%Y%m%d") + ":" + scored["symbol"].astype("string")
    scored["feature_timestamp"] = pd.to_datetime(scored["date"]).dt.strftime("%Y-%m-%d") + " close"

    date_to_pos = {pd.Timestamp(day): index for index, day in enumerate(calendar_obj.sessions)}
    end_pos = date_to_pos[pd.Timestamp(last_session)]
    scored["signal_session_index"] = scored["date"].map(date_to_pos).astype("int32")
    pool = scored.loc[
        scored["date"].between(start, period_end)
        & scored["signal_session_index"].add(5).le(end_pos)
    ].copy()
    if pool.empty:
        raise ValueError("Core-1 frozen period produced no eligible candidates")
    pool_decision = pool.loc[:, [
        "date", "symbol", "family", "spec_hash", "identity_key", "candidate_id",
        "feature_timestamp", "predicted_capped_return", *FEATURES,
    ]].copy()
    ranked = rank_candidate_pool(
        pool_decision,
        sessions=calendar_obj.sessions[(calendar_obj.sessions >= start) & (calendar_obj.sessions <= last_session)],
        feature_columns=FEATURES,
        ranking_terms=[("predicted_capped_return", False)],
    )
    eval_sessions = calendar_obj.sessions[(calendar_obj.sessions >= start) & (calendar_obj.sessions <= last_session)]
    pool_labels = pool.loc[:, ["date", "symbol", "family", "spec_hash"]].merge(
        labels,
        on=["date", "symbol", "family"], how="left", suffixes=("", "_label"), validate="one_to_one",
    )
    # The decision spec hash remains on the left; the labels table is outcome-only.
    pool_labels["spec_hash"] = str(frozen["spec_sha256"])
    pool_metrics = label_summary(pool_labels, costs=(0.0, 0.005, 0.01))
    pool_daily = _pool_daily(pool_labels, eval_sessions)
    policy_reports = []
    artifacts = {}
    for top_n in top_n_values:
        report, policy_artifacts = _selection_report(
            ranked=ranked,
            labels=pool_labels,
            sessions=eval_sessions,
            top_n=top_n,
            family=str(FAMILY_SPEC["family"]),
            spec_hash=str(frozen["spec_sha256"]),
            pool_metrics=pool_metrics,
            pool_daily=pool_daily,
            phase_name=period,
        )
        if period == "validation_2024" and report["policy_sha256"] != locked["policy_sha256"]:
            raise ValueError("2024 policy implementation hash differs from the frozen discovery policy")
        policy_reports.append(report)
        artifacts[str(top_n)] = policy_artifacts

    passed = [item for item in policy_reports if item["passes_all_gates"]]
    locked_top_n = None
    decision = "SELECTION_COUNT_UNRESOLVED"
    if period == "discovery" and passed:
        passed.sort(key=lambda item: (-float(item["daily_cohort_net_metrics"]["mean"]), int(item["top_n"])))
        locked_top_n = int(passed[0]["top_n"])
        decision = "PROMOTE_TO_2024_CONFIRMATION"
    elif period == "validation_2024":
        decision = "CONFIRMATION_PASS" if policy_reports[0]["passes_all_gates"] else "REJECT_AFTER_2024_CONFIRMATION"

    report = {
        "schema_version": 1,
        "experiment_id": FAMILY_SPEC["experiment_id"],
        "family_spec_sha256": FAMILY_SPEC_SHA256,
        "spec_sha256": frozen["spec_sha256"],
        "period": period,
        "period_access": access,
        "spec_frozen_at_utc": frozen["frozen_at_utc"],
        "phase_opened_at_utc": phase_opened_at,
        "source_sha256": frozen["source_sha256"],
        "calendar_sha256": frozen["calendar_sha256"],
        "feature_panel_rows": int(len(panel)),
        "eligible_rows_before_period_purge": int(len(prepared)),
        "candidate_pool_rows_after_period_purge": int(len(pool)),
        "candidate_pool_max_names_per_day": int(pool.groupby("date").size().max()),
        "candidate_pool_mean_names_per_active_day": float(pool.groupby("date").size().mean()),
        "candidate_pool_metrics": pool_metrics,
        "candidate_pool_daily_cohort_coverage": {
            "complete_days": int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
            "partial_unresolved_days": int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
            "abstain_days": int(pool_daily["cohort_status"].eq("ABSTAIN").sum()),
        },
        "quarterly_fits": fit_receipts,
        "selection_policies": policy_reports,
        "selection_policy_decision": decision,
        "locked_top_n": locked_top_n,
        "2025_2026_opened": False,
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "execution_cost_note": "0.5% round-trip is a sensitivity assumption, not observed slippage, commissions, tax, or fill quality.",
    }

    # Preserve a scored full pool without outcomes; preserve labels separately.
    pool_receipt = write_parquet_artifact(
        pool_decision.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True),
        BATCH_DIR / ".cache" / f"core_moderate_v2_{period}_candidate_pool.parquet",
        metadata={
            "experiment_id": FAMILY_SPEC["experiment_id"],
            "spec_sha256": frozen["spec_sha256"],
            "source_sha256": frozen["source_sha256"],
            "calendar_sha256": frozen["calendar_sha256"],
            "selection_sha256_excluded_from_pool": True,
            "future_columns_included": False,
            "period": period,
        },
    )
    labels_receipt = write_parquet_artifact(
        pool_labels.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True),
        BATCH_DIR / ".cache" / f"core_moderate_v2_{period}_labels.parquet",
        metadata={
            "experiment_id": FAMILY_SPEC["experiment_id"],
            "spec_sha256": frozen["spec_sha256"],
            "source_sha256": frozen["source_sha256"],
            "calendar_sha256": frozen["calendar_sha256"],
            "outcome_table_separate_from_selection": True,
            "period": period,
        },
    )
    model_directory = BATCH_DIR / ".cache" / "core_moderate_ridge_v2_models" / period
    model_hashes = {}
    for model in fitted_models:
        model_path = model_directory / f"ridge_{model['fit_date']}.json"
        _write_json(model_path, model)
        model_hashes[model["fit_date"]] = sha256_file(model_path)
    selected_hashes = {}
    for top_n, policy_artifacts in artifacts.items():
        receipt = write_parquet_artifact(
            policy_artifacts["selected"].sort_values(["date", "policy_rank"], kind="mergesort").reset_index(drop=True),
            BATCH_DIR / ".cache" / f"core_moderate_v2_{period}_selected_top{top_n}.parquet",
            metadata={"experiment_id": FAMILY_SPEC["experiment_id"], "spec_sha256": frozen["spec_sha256"], "future_columns_included": False, "top_n": int(top_n)},
        )
        selected_hashes[str(top_n)] = receipt["sha256"]
    report["artifacts"] = {
        "candidate_pool_sha256": pool_receipt["sha256"],
        "outcome_labels_sha256": labels_receipt["sha256"],
        "quarterly_model_sha256": model_hashes,
        "selected_policy_parquet_sha256_by_top_n": selected_hashes,
    }
    _write_json(report_path, report)
    if period == "discovery" and locked_top_n is not None:
        locked_report = next(item for item in policy_reports if int(item["top_n"]) == locked_top_n)
        _write_json(POLICY_LOCK_PATH, {
            "schema_version": 1,
            "experiment_id": FAMILY_SPEC["experiment_id"],
            "spec_sha256": frozen["spec_sha256"],
            "decision": decision,
            "top_n": locked_top_n,
            "selection_sha256": locked_report["selection_sha256"],
            "policy_sha256": locked_report["policy_sha256"],
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "selection_rule": "highest discovery complete-daily-cohort mean among policies passing every frozen gate; exact ties choose smaller N",
            "2024_required_unchanged": True,
        })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "discovery", "validation-2024"))
    args = parser.parse_args()
    if args.phase == "freeze":
        result = freeze_spec()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    result = run_period("discovery" if args.phase == "discovery" else "validation_2024")
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "period": result["period"],
        "selection_policy_decision": result["selection_policy_decision"],
        "locked_top_n": result["locked_top_n"],
        "candidate_pool_rows": result["candidate_pool_rows_after_period_purge"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
