"""Frozen causal V7 Tail -> Weak+Early five-lane forward scorer."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

from .corporate_actions import action_table, normalize_daily
from .bank_calendar import add_bank_business_days
from .endpoint_receipts import (
    ENDPOINT_COLUMNS, ENDPOINT_DATE_COLUMNS, ENDPOINT_NUMBER_COLUMNS,
    ENDPOINT_TEXT_COLUMNS, build_endpoint_receipts, source_digest,
)
from .trade_basis import PRICE_BASIS_VERSION, build_trade_economics, is_frozen_trade
from .progress import daily_phase


ROOT = Path(__file__).resolve().parents[1]
TVFREE = ROOT / "tvfree_screener"
PACK = ROOT / "research" / "repro_packs" / "weak_early_exact_v1"
sys.path.insert(0, str(TVFREE))
sys.path.insert(0, str(PACK))

import run as base  # noqa: E402
import v7_full_tail_research as v7  # noqa: E402
import select_shadow_candidates as shadow  # noqa: E402


TAIL_GATE = 0.999
MIN_TRAIN_ROWS = 30_000
TRAINING_PRICE_CAP = 1000.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_daily(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"], dtype={"symbol": str})
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return normalize_daily(frame)


def _eligible_live_mask(features: pd.DataFrame, price_cap: float = 0.0) -> pd.Series:
    """Evaluate gates on all sessions before selecting any rows."""
    previous_close = features.groupby("symbol")["actual_close"].shift(1)
    previous_volume = features.groupby("symbol")["actual_volume"].shift(1)
    mask = (
        (previous_volume >= 10_000)
        & (features["actual_volume"] >= 5_000)
        & (features["actual_close"] >= 20)
    )
    if "source_usable" in features:
        usable = features["source_usable"]
        mask &= usable & usable.groupby(features["symbol"]).shift(1).eq(True)
    if price_cap > 0:
        mask &= previous_close <= price_cap
    for column in base.FEATURES:
        mask &= features[column].notna()
    return mask


def eligible_live_rows(features: pd.DataFrame, price_cap: float = 0.0) -> pd.DataFrame:
    """Apply absolute gates to contemporaneous shares, never later split units."""
    mask = _eligible_live_mask(features, price_cap)
    return base._take_columns(features, mask.to_numpy().nonzero()[0])


def build_live_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Preserve session positions while keeping quarantined prices out of indicators."""
    with daily_phase("feature-source-validation"):
        raw = normalize_daily(raw)
    # Relative indicators use the provider's continuous split-adjusted series.
    # A later split scales a historical lookback uniformly; price*volume and
    # relative indicators stay invariant. Absolute gates use actual_* instead.
    feature_source = raw.copy(deep=False)
    quarantined = ~feature_source["source_usable"]
    for column in ("open", "high", "low", "close", "volume"):
        feature_source[column] = feature_source[column].mask(quarantined, float("nan"))
    del raw, quarantined
    with daily_phase("feature-build"):
        features = base.build_features(feature_source, memory_efficient=True)
    del feature_source
    groups = features.groupby("date")
    # Missing/isolated quotes are unknown, not a negative market vote.
    # Recompute across the complete universe after masking source inputs.
    for column, source in (("breadth_ret1_pos", "ret1"), ("breadth_ma20", "ma20_gap")):
        values = groups[source].apply(lambda series: series.dropna().gt(0).mean())
        features[column] = features["date"].map(values)
    return features


def prepare_live(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Predict without an upper price limit using the frozen capped training pool."""
    features = build_live_features(raw)
    # Keep the original training rows and cross-sectional labels. Expanding
    # prediction coverage must not redefine the fitted model or its Tail CDF.
    eligible_mask = _eligible_live_mask(features)
    training_mask = _eligible_live_mask(features, price_cap=TRAINING_PRICE_CAP)
    training_mask &= features["target5_no"].notna()
    training_mask &= pd.to_datetime(features["target_end_date"], errors="coerce").notna()
    eligible = base._take_columns(features, eligible_mask.to_numpy().nonzero()[0])
    labeled = base._take_columns(features, training_mask.to_numpy().nonzero()[0])
    del features, eligible_mask, training_mask
    eligible["date"] = pd.to_datetime(eligible["date"])
    eligible["target_end_date"] = pd.to_datetime(eligible["target_end_date"], errors="coerce")
    labeled["date"] = pd.to_datetime(labeled["date"])
    labeled["target_end_date"] = pd.to_datetime(labeled["target_end_date"], errors="coerce")
    labeled["future_rank"] = labeled.groupby("date")["target5_no"].rank(
        pct=True, method="average"
    )
    labeled["y_top025"] = (labeled["future_rank"] >= 0.9975).astype(int)
    return eligible, labeled


def _actual_price(prices: pd.DataFrame, symbol: str, date: pd.Timestamp, column: str) -> float:
    if pd.isna(date) or (symbol, date) not in prices.index:
        return float("nan")
    row = prices.loc[(symbol, date)]
    return float(row[column]) if bool(row["source_usable"]) else float("nan")


def causal_tail_for_month(
    eligible: pd.DataFrame,
    labeled: pd.DataFrame,
    month: pd.Period,
) -> pd.DataFrame:
    month_start = month.start_time
    month_end = month.end_time.normalize()
    train = labeled[labeled["target_end_date"] < month_start].copy()
    pred = eligible[
        (eligible["date"] >= month_start) & (eligible["date"] <= month_end)
    ].copy()
    if len(train) < MIN_TRAIN_ROWS:
        raise RuntimeError(f"insufficient causal training rows: {len(train)} < {MIN_TRAIN_ROWS}")
    if pred.empty:
        return pd.DataFrame()
    y = train["y_top025"].astype(int)
    if y.nunique() < 2:
        raise RuntimeError("degenerate y_top025 training labels")
    model = v7.model(y)
    with daily_phase("monthly-model-fit"):
        model.fit(train[base.FEATURES], y, verbose=False)
    with daily_phase("monthly-model-predict"):
        train_probability = model.predict_proba(train[base.FEATURES])[:, 1]
        pred_probability = model.predict_proba(pred[base.FEATURES])[:, 1]
    pred["tail_p"] = pred_probability
    pred["tail_cdf"] = v7.cdf(train_probability, pred_probability)
    pred["model_period"] = str(month)
    return pred[pred["tail_cdf"] >= TAIL_GATE].copy()


def _delisting_prediction_gate(eligible: pd.DataFrame, delistings: list[dict] | None) -> pd.DataFrame:
    """Remove post-delisting predictions while keeping historical training intact."""
    if not delistings or eligible.empty:
        return eligible
    blocked = pd.Series(False, index=eligible.index)
    symbols = eligible["symbol"].astype(str)
    present = set(symbols.unique())
    for row in delistings:
        if row.get("delisting_date") and str(row["code"]) in present:
            interval = (symbols.eq(str(row["code"]))
                        & eligible["date"].ge(pd.Timestamp(row["delisting_date"])))
            if row.get("relisting_date"):
                interval &= eligible["date"].lt(pd.Timestamp(row["relisting_date"]))
            blocked |= interval
    return eligible.loc[~blocked].copy()


def score_latest(raw: pd.DataFrame, as_of: str | None = None, *, delistings: list[dict] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible, labeled = prepare_live(raw)
    latest = pd.Timestamp(as_of) if as_of else eligible["date"].max()
    latest = latest.normalize()
    eligible = _delisting_prediction_gate(eligible, delistings)
    if eligible.empty:
        return eligible.copy(), pd.DataFrame()
    month = latest.to_period("M")
    tail = causal_tail_for_month(eligible, labeled, month)
    if tail.empty:
        return eligible.iloc[:0].copy(), pd.DataFrame()
    tail_latest = tail[tail["date"].eq(latest)].copy()
    if tail_latest.empty:
        return tail_latest, pd.DataFrame()
    selected = shadow.select_candidates(tail_latest)
    return tail_latest, selected


def score_range(
    raw: pd.DataFrame,
    start: str,
    end: str | None = None,
    *,
    delistings: list[dict] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score an inclusive forward date range, fitting each causal month only once."""
    eligible, labeled = prepare_live(raw)
    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize() if end else eligible["date"].max().normalize()
    if end_date < start_date:
        raise ValueError(f"end date {end_date:%Y-%m-%d} is before start date {start_date:%Y-%m-%d}")
    eligible = _delisting_prediction_gate(eligible, delistings)
    if eligible.empty:
        return eligible.copy(), pd.DataFrame()
    months = pd.period_range(start_date.to_period("M"), end_date.to_period("M"), freq="M")
    tail_parts = []
    selected_parts = []
    for month in months:
        month_tail = causal_tail_for_month(eligible, labeled, month)
        if month_tail.empty:
            continue
        month_tail = month_tail[
            month_tail["date"].between(start_date, end_date, inclusive="both")
        ].copy()
        if month_tail.empty:
            continue
        tail_parts.append(month_tail)
        selected = shadow.select_candidates(month_tail)
        if not selected.empty:
            selected_parts.append(selected)
    tail = pd.concat(tail_parts, ignore_index=True) if tail_parts else pd.DataFrame()
    selected = (
        pd.concat(selected_parts, ignore_index=True)
        if selected_parts else pd.DataFrame()
    )
    return tail, selected


def attach_forward_rows(
    selected: pd.DataFrame,
    raw: pd.DataFrame,
    company_names: dict[str, str] | None = None,
    source_sha256: str = "",
) -> pd.DataFrame:
    from .config import selector_info
    from .ledger import EXIT_REMINDER_COLUMNS, LEDGER_COLUMNS

    if selected.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    raw = normalize_daily(raw)
    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    company_names = company_names or {}
    prices = raw.set_index(["symbol", "date"])
    actions = action_table(raw)
    endpoint_digest = source_digest(raw, source_sha256)
    rows = []
    for record in selected.to_dict(orient="records"):
        signal_date = pd.Timestamp(record["date"]).normalize()
        symbol = str(record["symbol"])
        selector_id = str(record["selector"])
        entry_date = pd.Timestamp(add_bank_business_days(signal_date.date(), 1))
        exit_date = pd.Timestamp(add_bank_business_days(signal_date.date(), 5))
        signal_close = float("nan")
        signal_volume = float("nan")
        if (symbol, signal_date) in prices.index:
            if not bool(prices.loc[(symbol, signal_date), "source_usable"]):
                raise ValueError(f"selected signal has quarantined source prices: {symbol} {signal_date:%Y-%m-%d}")
            signal_close = float(prices.loc[(symbol, signal_date), "actual_close"])
            signal_volume = float(prices.loc[(symbol, signal_date), "actual_volume"])
        entry_open = _actual_price(prices, symbol, entry_date, "actual_open")
        exit_close = _actual_price(prices, symbol, exit_date, "actual_close")
        basis_date = prices.loc[(symbol, signal_date), "basis_asof"]
        economics = build_trade_economics(
            entry_date, exit_date, entry_open, exit_close, actions,
            symbol=symbol, basis_date=basis_date, source_sha256=source_sha256,
        )
        row = {
            **record,
            "detection_id": f"{signal_date:%Y-%m-%d}|{symbol}|{selector_id}",
            "signal_date": signal_date,
            "symbol": symbol,
            "company_name": company_names.get(symbol, ""),
            "signal_close": signal_close,
            "signal_volume": signal_volume,
            "selector_id": selector_id,
            "selector_name": selector_info(selector_id).display_name,
            "entry_date": entry_date,
            "entry_open": entry_open,
            "fifth_xtks_exit_date": exit_date,
            "fifth_xtks_exit_close": exit_close,
            **economics,
            "d5_price_observed_at": now if economics["status"] == "mature" else "",
            "source_scope": "FORWARD_CAUSAL",
            "source_sha256": source_sha256,
            "signal_discord_url": "",
            "notified_at": "",
            "fundamental_status": "queued",
            "fundamental_discord_url": "",
            "fundamental_html": "",
            **dict.fromkeys(EXIT_REMINDER_COLUMNS, ""),
            "created_at": now,
            "updated_at": now,
        }
        row.update(build_endpoint_receipts(
            row, prices, actions, digest=endpoint_digest, observed_at=now,
        ))
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)


def refresh_forward_endpoints(
    ledger: pd.DataFrame, raw: pd.DataFrame, source_sha256: str = "",
) -> pd.DataFrame:
    """Fill forward receipts, independently of the frozen D5 economics."""
    if ledger.empty:
        return ledger.copy()
    raw = normalize_daily(raw)
    result = ledger.copy()
    for column in ENDPOINT_COLUMNS:
        if column not in result:
            result[column] = pd.NaT if column in ENDPOINT_DATE_COLUMNS else (float("nan") if column in ENDPOINT_NUMBER_COLUMNS else "")
        elif column in ENDPOINT_TEXT_COLUMNS:
            result[column] = result[column].astype(object)
    # Legacy CSVs have all-empty new metadata columns, inferred as float64.
    # Make their string contract explicit before filling a forward receipt.
    for column in ("price_basis", "price_basis_date", "price_basis_source_sha256", "applied_actions_json", "d5_price_observed_at"):
        if column not in result:
            result[column] = ""
        else:
            result[column] = result[column].astype(object)
    result["signal_date"] = pd.to_datetime(result["signal_date"])
    prices = raw.set_index(["symbol", "date"])
    actions = action_table(raw)
    endpoint_digest = source_digest(raw, source_sha256)
    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    mask = result["source_scope"].eq("FORWARD_CAUSAL")
    from .jpx_holds import COLUMN as JPX_HOLD, verify as verify_jpx_hold
    held_symbols = {symbol for symbol, group in raw.groupby("symbol", sort=False) if JPX_HOLD in group and verify_jpx_hold(group)}
    from .endpoint_holds import audit as endpoint_hold_audit
    held_symbols.update(e["symbol"] for e in endpoint_hold_audit(raw))
    for index, row in result[mask].iterrows():
        if str(row["symbol"]) in held_symbols:
            continue  # Preserve all prior endpoint receipts/economics/updated_at.
        receipts = build_endpoint_receipts(
            row, prices, actions, digest=endpoint_digest, observed_at=now,
        )
        changed = False
        for column, value in receipts.items():
            prior = row.get(column)
            same = (pd.isna(prior) and pd.isna(value)) or (pd.notna(prior) and pd.notna(value) and prior == value)
            if not same:
                result.at[index, column] = value
                changed = True
        if changed:
            result.at[index, "updated_at"] = now
        if is_frozen_trade(row):
            continue
        signal_date = pd.Timestamp(row["signal_date"]).normalize()
        symbol = str(row["symbol"])
        if (symbol, signal_date) not in prices.index:
            continue
        entry_date = pd.Timestamp(add_bank_business_days(signal_date.date(), 1))
        exit_date = pd.Timestamp(add_bank_business_days(signal_date.date(), 5))
        entry_open = _actual_price(prices, symbol, entry_date, "actual_open")
        exit_close = _actual_price(prices, symbol, exit_date, "actual_close")
        if not bool(prices.loc[(symbol, signal_date), "source_usable"]):
            continue
        basis_date = prices.loc[(symbol, signal_date), "basis_asof"]
        # Once entered on the actual-share basis, the original cost is fixed.
        if row.get("price_basis") == PRICE_BASIS_VERSION and pd.notna(row.get("entry_open")):
            if pd.Timestamp(row["entry_date"]).normalize() != entry_date:
                raise ValueError(f"entry session revision requires review: {row['detection_id']}")
            if pd.notna(row.get("fifth_xtks_exit_date")) and pd.Timestamp(row["fifth_xtks_exit_date"]).normalize() != exit_date:
                raise ValueError(f"exit session revision requires review: {row['detection_id']}")
            if pd.notna(entry_open) and abs(entry_open - float(row["entry_open"])) > max(0.01, abs(float(row["entry_open"])) * 1e-6):
                raise ValueError(f"entry price revision requires review: {row['detection_id']}")
            entry_open = float(row["entry_open"])
        economics = build_trade_economics(
            entry_date, exit_date, entry_open, exit_close, actions,
            symbol=symbol, basis_date=basis_date,
            source_sha256=source_sha256 or str(row.get("source_sha256", "")),
        )
        # Legacy forward records gain an explicit basis only after verified
        # action-aware source data is available. Historical canonical rows stay
        # outside this migration.
        if row.get("price_basis") != PRICE_BASIS_VERSION:
            result.at[index, "signal_close"] = float(prices.loc[(symbol, signal_date), "actual_close"])
            result.at[index, "signal_volume"] = float(prices.loc[(symbol, signal_date), "actual_volume"])
        result.at[index, "entry_date"] = entry_date
        result.at[index, "entry_open"] = entry_open
        result.at[index, "fifth_xtks_exit_date"] = exit_date
        result.at[index, "fifth_xtks_exit_close"] = exit_close
        for column, value in economics.items():
            result.at[index, column] = value
        if economics["status"] == "mature" and not str(row.get("d5_price_observed_at", "") if pd.notna(row.get("d5_price_observed_at")) else "").strip():
            result.at[index, "d5_price_observed_at"] = now
        result.at[index, "updated_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    return result

