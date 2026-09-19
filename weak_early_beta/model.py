"""Frozen causal V7 Tail -> Weak+Early five-lane forward scorer."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd


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
    return frame.dropna(
        subset=["date", "symbol", "open", "high", "low", "close", "volume"]
    ).sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")


def prepare_live(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep unlabeled prediction rows; labels exist only on matured rows."""
    features = base.build_features(raw)
    eligible = base.eligible_rows(features, price_cap=1000.0).copy()
    eligible["date"] = pd.to_datetime(eligible["date"])
    eligible["target_end_date"] = pd.to_datetime(eligible["target_end_date"], errors="coerce")
    labeled = eligible.dropna(subset=["target5_no", "target_end_date"]).copy()
    labeled["future_rank"] = labeled.groupby("date")["target5_no"].rank(
        pct=True, method="average"
    )
    labeled["y_top025"] = (labeled["future_rank"] >= 0.9975).astype(int)
    return eligible, labeled


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
    model.fit(train[base.FEATURES], y, verbose=False)
    train_probability = model.predict_proba(train[base.FEATURES])[:, 1]
    pred_probability = model.predict_proba(pred[base.FEATURES])[:, 1]
    pred["tail_p"] = pred_probability
    pred["tail_cdf"] = v7.cdf(train_probability, pred_probability)
    pred["model_period"] = str(month)
    return pred[pred["tail_cdf"] >= TAIL_GATE].copy()


def score_latest(raw: pd.DataFrame, as_of: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible, labeled = prepare_live(raw)
    latest = pd.Timestamp(as_of) if as_of else eligible["date"].max()
    latest = latest.normalize()
    month = latest.to_period("M")
    tail = causal_tail_for_month(eligible, labeled, month)
    tail_latest = tail[tail["date"].eq(latest)].copy()
    if tail_latest.empty:
        return tail_latest, pd.DataFrame()
    selected = shadow.select_candidates(tail_latest)
    return tail_latest, selected


def attach_forward_rows(
    selected: pd.DataFrame,
    raw: pd.DataFrame,
    company_names: dict[str, str] | None = None,
    source_sha256: str = "",
) -> pd.DataFrame:
    from .config import selector_info
    from .ledger import LEDGER_COLUMNS

    if selected.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    company_names = company_names or {}
    calendar = pd.DatetimeIndex(pd.to_datetime(raw["date"].unique())).sort_values()
    date_pos = {date: pos for pos, date in enumerate(calendar)}
    prices = raw.set_index(["symbol", "date"])[["open", "close"]]
    rows = []
    for record in selected.to_dict(orient="records"):
        signal_date = pd.Timestamp(record["date"]).normalize()
        symbol = str(record["symbol"])
        selector_id = str(record["selector"])
        pos = date_pos[signal_date]
        entry_date = calendar[pos + 1] if pos + 1 < len(calendar) else pd.NaT
        exit_date = calendar[pos + 5] if pos + 5 < len(calendar) else pd.NaT
        entry_open = float("nan")
        exit_close = float("nan")
        if pd.notna(entry_date) and (symbol, entry_date) in prices.index:
            entry_open = float(prices.loc[(symbol, entry_date), "open"])
        if pd.notna(exit_date) and (symbol, exit_date) in prices.index:
            exit_close = float(prices.loc[(symbol, exit_date), "close"])
        mature = pd.notna(entry_open) and pd.notna(exit_close) and entry_open > 0
        gross = exit_close / entry_open - 1 if mature else float("nan")
        row = {
            **record,
            "detection_id": f"{signal_date:%Y-%m-%d}|{symbol}|{selector_id}",
            "signal_date": signal_date,
            "symbol": symbol,
            "company_name": company_names.get(symbol, ""),
            "selector_id": selector_id,
            "selector_name": selector_info(selector_id).display_name,
            "status": "mature" if mature else ("entered" if pd.notna(entry_open) else "pending_entry"),
            "entry_date": entry_date,
            "entry_open": entry_open,
            "fifth_xtks_exit_date": exit_date,
            "fifth_xtks_exit_close": exit_close,
            "gross_return": gross,
            "one_hundred_shares_pl_yen": (exit_close - entry_open) * 100 if mature else float("nan"),
            "source_scope": "FORWARD_CAUSAL",
            "source_sha256": source_sha256,
            "signal_discord_url": "",
            "notified_at": "",
            "fundamental_status": "queued",
            "fundamental_discord_url": "",
            "fundamental_html": "",
            "created_at": now,
            "updated_at": now,
        }
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)


def refresh_forward_endpoints(ledger: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Fill entry/exit receipts for already-recorded forward detections."""
    if ledger.empty:
        return ledger.copy()
    result = ledger.copy()
    result["signal_date"] = pd.to_datetime(result["signal_date"])
    calendar = pd.DatetimeIndex(pd.to_datetime(raw["date"].unique())).sort_values()
    date_pos = {date: pos for pos, date in enumerate(calendar)}
    prices = raw.set_index(["symbol", "date"])[["open", "close"]]
    mask = result["source_scope"].eq("FORWARD_CAUSAL")
    for index, row in result[mask].iterrows():
        signal_date = pd.Timestamp(row["signal_date"]).normalize()
        symbol = str(row["symbol"])
        if signal_date not in date_pos:
            continue
        pos = date_pos[signal_date]
        entry_date = calendar[pos + 1] if pos + 1 < len(calendar) else pd.NaT
        exit_date = calendar[pos + 5] if pos + 5 < len(calendar) else pd.NaT
        entry_open = float("nan")
        exit_close = float("nan")
        if pd.notna(entry_date) and (symbol, entry_date) in prices.index:
            entry_open = float(prices.loc[(symbol, entry_date), "open"])
        if pd.notna(exit_date) and (symbol, exit_date) in prices.index:
            exit_close = float(prices.loc[(symbol, exit_date), "close"])
        mature = pd.notna(entry_open) and pd.notna(exit_close) and entry_open > 0
        result.at[index, "entry_date"] = entry_date
        result.at[index, "entry_open"] = entry_open
        result.at[index, "fifth_xtks_exit_date"] = exit_date
        result.at[index, "fifth_xtks_exit_close"] = exit_close
        result.at[index, "gross_return"] = exit_close / entry_open - 1 if mature else float("nan")
        result.at[index, "one_hundred_shares_pl_yen"] = (
            (exit_close - entry_open) * 100 if mature else float("nan")
        )
        result.at[index, "status"] = (
            "mature" if mature else ("entered" if pd.notna(entry_open) else "pending_entry")
        )
        result.at[index, "updated_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    return result
