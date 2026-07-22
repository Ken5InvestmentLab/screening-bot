#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-symbol research backtest for the standalone TradingView strategy.

The script intentionally ignores alerts_raw and signals_archive.  By default it
uses the official JPX list of domestic Prime, Standard, and Growth stocks,
downloads split/dividend-adjusted daily OHLCV from Yahoo Finance, and compares a
compact set of trend/pullback rules.  Orders are filled on the next daily open
and the simulator includes one-way trading costs, adverse gap handling, partial
profit taking, and an optional single add-on entry.

This is a research tool, not a production Bot path and not an execution system.
It never writes to Google Sheets.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE = BASE_DIR / ".cache" / "yahoo_daily_adjusted.json.gz"
DEFAULT_RESULTS = BASE_DIR / ".cache" / "entry_strategy_results.json"
READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
JPX_LIST_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xls"
)


@dataclass(frozen=True)
class EntrySpec:
    name: str
    mode: str
    fast: int
    slow: int
    trend: int
    rsi_min: float
    rsi_max: float
    volume_min: float
    pullback_tolerance: float = 0.01
    breakout_lookback: int = 20
    turnover_min: float = 100_000_000.0
    atr_pct_max: float = 0.06
    market_filter: bool = True


@dataclass(frozen=True)
class StrategySpec:
    entry: EntrySpec
    exit_mode: str
    stop_atr: float
    tp1_r: float
    tp2_r: float
    trail_atr: float
    add_enabled: bool
    add_trigger_r: float = 0.75
    add_breakout: int = 10
    max_hold_bars: int = 80

    @property
    def key(self) -> str:
        add_tag = "add" if self.add_enabled else "noadd"
        return (
            f"{self.entry.name}|{self.exit_mode}|sl{self.stop_atr:g}|tp{self.tp1_r:g}-"
            f"{self.tp2_r:g}|tr{self.trail_atr:g}|{add_tag}"
        )


@dataclass
class Lot:
    weight: float
    entry_price: float
    remaining: float = 1.0


@dataclass
class Trade:
    symbol: str
    entry_date: str
    exit_date: str
    bars_held: int
    return_fraction: float
    allocated_weight: float
    added: bool
    tp1_hit: bool
    exit_reason: str


def stable_bucket(symbol: str, buckets: int = 5) -> int:
    digest = hashlib.sha256(symbol.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % buckets


def clean_symbol(value: object) -> str:
    text = str(value or "").strip().upper().split(":")[-1]
    return text if re.fullmatch(r"(?:\d{4,5}|\d{3}[A-Z])", text) else ""


def credentials_path() -> Path:
    configured = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GOOGLE_CREDENTIALS_PATH")
        or os.environ.get("CREDENTIALS_PATH")
    )
    return (
        Path(configured).expanduser().resolve()
        if configured
        else REPO_DIR / "credentials.json"
    )


def fetch_sheet_universe() -> list[str]:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    import optimize_screener as opt

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path()), scopes=[READONLY_SCOPE]
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=opt.SPREADSHEET_ID, range="ohlcv_4h!C2:C")
        .execute()
    )
    symbols = {
        clean_symbol(row[0])
        for row in response.get("values", [])
        if row and clean_symbol(row[0])
    }
    return sorted(symbols)


def fetch_jpx_universe() -> list[str]:
    request = urllib.request.Request(
        JPX_LIST_URL,
        headers={"User-Agent": "Mozilla/5.0 screening-bot-strategy-research/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        workbook = response.read()
    frame = pd.read_excel(BytesIO(workbook))
    if frame.shape[1] < 4:
        raise RuntimeError("Unexpected JPX listed-issues workbook schema")
    code_column = frame.columns[1]
    market_column = frame.columns[3]
    domestic = frame[market_column].astype(str).str.contains(
        "（内国株式）", regex=False, na=False
    )
    symbols = {
        clean_symbol(value)
        for value in frame.loc[domestic, code_column].tolist()
        if clean_symbol(value)
    }
    if len(symbols) < 3000:
        raise RuntimeError(f"JPX universe is unexpectedly small: {len(symbols)}")
    return sorted(symbols)


def yahoo_ticker(symbol: str) -> str:
    return f"{symbol}.T"


def valid_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fetch_yahoo_daily_adjusted(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    timeout: float = 15.0,
    retries: int = 3,
) -> list[dict]:
    period1 = int(
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    )
    period2 = int(
        datetime.combine(
            end_date + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
    )
    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(yahoo_ticker(symbol))}?{query}"
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 screening-bot-strategy-research/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            error = payload.get("chart", {}).get("error")
            results = payload.get("chart", {}).get("result") or []
            if error or not results:
                raise RuntimeError(f"Yahoo chart error: {error or 'empty result'}")
            result = results[0]
            timestamps = result.get("timestamp") or []
            indicators = result.get("indicators") or {}
            quote = (indicators.get("quote") or [{}])[0]
            adjclose = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []
            bars: list[dict] = []
            for index, timestamp in enumerate(timestamps):
                try:
                    raw_close = quote.get("close", [])[index]
                    adjusted_close = adjclose[index]
                    if not valid_number(raw_close) or not valid_number(adjusted_close):
                        continue
                    raw_close = float(raw_close)
                    adjusted_close = float(adjusted_close)
                    if raw_close <= 0 or adjusted_close <= 0:
                        continue
                    factor = adjusted_close / raw_close
                    values = {
                        key: float(quote.get(key, [])[index]) * factor
                        for key in ("open", "high", "low", "close")
                    }
                    volume = float(quote.get("volume", [])[index] or 0.0)
                except (IndexError, TypeError, ValueError):
                    continue
                if (
                    not all(math.isfinite(value) and value > 0 for value in values.values())
                    or values["high"] < max(values["open"], values["close"])
                    or values["low"] > min(values["open"], values["close"])
                    or not math.isfinite(volume)
                    or volume < 0
                ):
                    continue
                bars.append(
                    {
                        "date": datetime.fromtimestamp(int(timestamp), JST).strftime(
                            "%Y-%m-%d"
                        ),
                        **values,
                        "volume": volume,
                    }
                )
            return bars
        except (
            OSError,
            RuntimeError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.6 * (2**attempt))
    raise RuntimeError(f"Yahoo daily fetch failed for {symbol}: {last_error}")


def load_cache(path: Path, start_date: date, end_date: date) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if (
            payload.get("start_date") != start_date.isoformat()
            or payload.get("end_date") != end_date.isoformat()
        ):
            return {}
        return payload.get("bars_by_symbol", {})
    except (OSError, ValueError, TypeError):
        return {}


def save_cache(
    path: Path,
    start_date: date,
    end_date: date,
    bars_by_symbol: dict[str, list[dict]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "saved_at": datetime.now(JST).isoformat(),
        "bars_by_symbol": bars_by_symbol,
    }
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def load_market_data(
    symbols: list[str],
    start_date: date,
    end_date: date,
    cache_path: Path,
    *,
    workers: int,
    refresh: bool,
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    cached = {} if refresh else load_cache(cache_path, start_date, end_date)
    output = {symbol: cached[symbol] for symbol in symbols if symbol in cached}
    missing = [symbol for symbol in symbols if symbol not in output]
    failures: dict[str, str] = {}
    if missing:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 12))) as executor:
            futures = {
                executor.submit(fetch_yahoo_daily_adjusted, symbol, start_date, end_date): symbol
                for symbol in missing
            }
            completed = 0
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    bars = future.result()
                    if bars:
                        output[symbol] = bars
                    else:
                        failures[symbol] = "empty result"
                except Exception as exc:  # noqa: BLE001 - preserve per-symbol progress
                    failures[symbol] = str(exc)
                completed += 1
                if completed % 100 == 0 or completed == len(missing):
                    print(f"  Yahoo: {completed}/{len(missing)} symbols", flush=True)
        save_cache(cache_path, start_date, end_date, output)
    return output, failures


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    relative = gain / loss.replace(0, np.nan)
    result = 100 - 100 / (1 + relative)
    return result.where(loss != 0, 100.0)


def prepare_frame(bars: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(bars)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = (
        frame.dropna(subset=["date", "open", "high", "low", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    frame["rsi14"] = rsi(frame["close"], 14)
    frame["rsi2"] = rsi(frame["close"], 2)
    frame["vol20_prev"] = frame["volume"].rolling(20).mean().shift(1)
    frame["volume_ratio"] = frame["volume"] / frame["vol20_prev"].replace(0, np.nan)
    frame["turnover20_prev"] = (
        (frame["close"] * frame["volume"]).rolling(20).mean().shift(1)
    )
    frame["atr_pct"] = frame["atr14"] / frame["close"].replace(0, np.nan)
    for length in (5, 10, 20, 50, 75, 150, 200):
        frame[f"ema{length}"] = frame["close"].ewm(
            span=length, adjust=False
        ).mean()
    for length in (10, 20, 50):
        frame[f"prior_high{length}"] = frame["high"].rolling(length).max().shift(1)
    frame["prior_low10"] = frame["low"].rolling(10).min().shift(1)
    return frame


def entry_signal(frame: pd.DataFrame, spec: EntrySpec) -> pd.Series:
    fast = frame[f"ema{spec.fast}"]
    slow = frame[f"ema{spec.slow}"]
    trend = frame[f"ema{spec.trend}"]
    liquid = (
        (frame["turnover20_prev"] >= spec.turnover_min)
        & (frame["atr_pct"] <= spec.atr_pct_max)
    )
    market_ok = (
        frame.get("market_ok", pd.Series(False, index=frame.index))
        if spec.market_filter
        else pd.Series(True, index=frame.index)
    )
    standard_trend = (
        (frame["close"] > trend)
        & (fast > slow)
        & (slow > slow.shift(5))
        & (frame["rsi14"] >= spec.rsi_min)
        & (frame["rsi14"] <= spec.rsi_max)
        & (frame["volume_ratio"] >= spec.volume_min)
    )
    reclaim = (
        (frame["low"] <= fast * (1 + spec.pullback_tolerance))
        & (frame["close"] > fast)
        & (frame["close"] > frame["open"])
        & (frame["close"].shift(1) <= fast.shift(1) * (1 + spec.pullback_tolerance))
    )
    breakout = frame["close"] > frame[f"prior_high{spec.breakout_lookback}"]
    if spec.mode == "pullback":
        signal = standard_trend & reclaim & liquid & market_ok
    elif spec.mode == "breakout":
        signal = standard_trend & breakout & liquid & market_ok
    elif spec.mode == "hybrid":
        signal = standard_trend & (reclaim | breakout) & liquid & market_ok
    elif spec.mode == "rsi_pullback":
        signal = (
            (frame["close"] > trend)
            & (slow > trend)
            & (trend > trend.shift(10))
            & (frame["rsi14"].shift(1) < spec.rsi_min)
            & (frame["rsi14"] >= spec.rsi_min)
            & (frame["rsi14"] <= spec.rsi_max)
            & (frame["close"] > frame["open"])
            & (frame["volume_ratio"] >= spec.volume_min)
            & liquid
            & market_ok
        )
    elif spec.mode in {"oversold2", "oversold_reversal"}:
        base = (
            (frame["close"] > trend)
            & (slow > trend)
            & (trend > trend.shift(20))
            & (frame["volume_ratio"] >= spec.volume_min)
        )
        if spec.mode == "oversold2":
            trigger = (frame["rsi2"] <= spec.rsi_min) & (
                frame["close"] < frame[f"ema{spec.fast}"]
            )
        else:
            trigger = (
                (frame["rsi2"].shift(1) <= spec.rsi_min)
                & (frame["rsi2"] > frame["rsi2"].shift(1))
                & (frame["close"] > frame["open"])
            )
        signal = base & trigger & liquid & market_ok
    else:
        raise ValueError(f"Unknown entry mode: {spec.mode}")
    return signal.fillna(False)


def exit_lots(
    lots: list[Lot],
    fraction: float,
    price: float,
    one_way_cost: float,
) -> float:
    pnl = 0.0
    fraction = min(1.0, max(0.0, fraction))
    for lot in lots:
        sold = lot.remaining * fraction
        if sold <= 0:
            continue
        exposure = lot.weight * sold
        pnl += exposure * (price / lot.entry_price - 1.0)
        pnl -= exposure * (price / lot.entry_price) * one_way_cost
        lot.remaining -= sold
    return pnl


def simulate_symbol(
    symbol: str,
    frame: pd.DataFrame,
    spec: StrategySpec,
    *,
    one_way_cost: float,
) -> list[Trade]:
    if len(frame) < max(spec.entry.trend + 15, 220):
        return []
    signals = entry_signal(frame, spec.entry).to_numpy(dtype=bool)
    dates = frame["date"].dt.strftime("%Y-%m-%d").to_numpy()
    opens = frame["open"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    atrs = frame["atr14"].to_numpy(dtype=float)
    prior_lows = frame["prior_low10"].to_numpy(dtype=float)
    prior_add_highs = frame[f"prior_high{spec.add_breakout}"].to_numpy(dtype=float)
    fast_emas = frame[f"ema{spec.entry.fast}"].to_numpy(dtype=float)
    slow_emas = frame[f"ema{spec.entry.slow}"].to_numpy(dtype=float)
    rsi2_values = frame["rsi2"].to_numpy(dtype=float)
    trades: list[Trade] = []
    in_position = False
    pending_entry = False
    pending_add = False
    pending_exit = ""
    lots: list[Lot] = []
    entry_index = -1
    entry_date = ""
    initial_entry = math.nan
    hard_stop = math.nan
    risk = math.nan
    tp1 = math.nan
    tp2 = math.nan
    highest_close = -math.inf
    active_stop = math.nan
    pnl = 0.0
    added = False
    tp1_hit = False

    for index in range(1, len(frame)):
        open_price = opens[index]
        high = highs[index]
        low = lows[index]
        close = closes[index]

        if in_position and pending_exit:
            pnl += exit_lots(lots, 1.0, open_price, one_way_cost)
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_date=entry_date,
                    exit_date=dates[index],
                    bars_held=index - entry_index,
                    return_fraction=pnl,
                    allocated_weight=sum(lot.weight for lot in lots),
                    added=added,
                    tp1_hit=tp1_hit,
                    exit_reason=pending_exit,
                )
            )
            in_position = False
            pending_exit = ""
            lots = []

        if not in_position and pending_entry:
            atr = atrs[index - 1]
            swing_low = prior_lows[index - 1]
            if math.isfinite(atr) and atr > 0 and math.isfinite(swing_low):
                atr_distance = spec.stop_atr * atr
                swing_distance = max(atr, open_price - (swing_low - 0.2 * atr))
                risk = min(atr_distance, swing_distance)
                risk = max(atr, risk)
                initial_entry = open_price
                hard_stop = initial_entry - risk
                tp1 = initial_entry + spec.tp1_r * risk
                tp2 = initial_entry + spec.tp2_r * risk
                active_stop = hard_stop
                highest_close = close
                lots = [Lot(weight=0.5, entry_price=initial_entry)]
                pnl = -0.5 * one_way_cost
                in_position = True
                entry_index = index
                entry_date = dates[index]
                added = False
                tp1_hit = False
            pending_entry = False

        if in_position and pending_add:
            lots.append(Lot(weight=0.5, entry_price=open_price))
            pnl -= 0.5 * one_way_cost
            added = True
            pending_add = False

        if in_position:
            stop_fill = min(open_price, active_stop) if open_price <= active_stop else active_stop
            if low <= active_stop:
                pnl += exit_lots(lots, 1.0, stop_fill, one_way_cost)
                trades.append(
                    Trade(
                        symbol=symbol,
                        entry_date=entry_date,
                        exit_date=dates[index],
                        bars_held=index - entry_index,
                        return_fraction=pnl,
                        allocated_weight=sum(lot.weight for lot in lots),
                        added=added,
                        tp1_hit=tp1_hit,
                        exit_reason="stop",
                    )
                )
                in_position = False
                pending_exit = ""
                lots = []
                continue

            if not tp1_hit and high >= tp1 and spec.exit_mode != "mean":
                if spec.exit_mode == "partial":
                    pnl += exit_lots(lots, 0.5, tp1, one_way_cost)
                tp1_hit = True

            if spec.exit_mode != "mean" and tp1_hit and high >= tp2:
                pnl += exit_lots(lots, 1.0, tp2, one_way_cost)
                trades.append(
                    Trade(
                        symbol=symbol,
                        entry_date=entry_date,
                        exit_date=dates[index],
                        bars_held=index - entry_index,
                        return_fraction=pnl,
                        allocated_weight=sum(lot.weight for lot in lots),
                        added=added,
                        tp1_hit=True,
                        exit_reason="tp2",
                    )
                )
                in_position = False
                pending_exit = ""
                lots = []
                continue

            highest_close = max(highest_close, close)
            if tp1_hit:
                atr = atrs[index]
                weighted_entry = sum(lot.weight * lot.entry_price for lot in lots) / sum(
                    lot.weight for lot in lots
                )
                trail = highest_close - spec.trail_atr * atr
                ema_stop = fast_emas[index]
                candidate = max(hard_stop, weighted_entry, trail, ema_stop)
                if candidate < close:
                    active_stop = max(active_stop, candidate)

            bars_held = index - entry_index
            if spec.exit_mode == "mean":
                mean_reached = close >= fast_emas[index] or rsi2_values[index] >= 70
                if mean_reached:
                    pending_exit = "mean"
            elif spec.exit_mode == "runner":
                trend_floor = fast_emas[index] if tp1_hit else slow_emas[index]
                if close < trend_floor:
                    pending_exit = "trend"
            elif close < slow_emas[index]:
                pending_exit = "trend"
            if not pending_exit and bars_held >= spec.max_hold_bars:
                pending_exit = "time"

            if (
                spec.add_enabled
                and not added
                and not tp1_hit
                and not pending_exit
                and bars_held >= 2
                and close >= initial_entry + spec.add_trigger_r * risk
                and close > prior_add_highs[index]
                and close > fast_emas[index]
            ):
                pending_add = True

        if not in_position and not pending_entry and signals[index]:
            pending_entry = True

    if in_position:
        pnl += exit_lots(lots, 1.0, closes[-1], one_way_cost)
        trades.append(
            Trade(
                symbol=symbol,
                entry_date=entry_date,
                exit_date=dates[-1],
                bars_held=len(frame) - 1 - entry_index,
                return_fraction=pnl,
                allocated_weight=sum(lot.weight for lot in lots),
                added=added,
                tp1_hit=tp1_hit,
                exit_reason="end",
            )
        )
    return trades


def metric_summary(trades: list[Trade]) -> dict:
    if not trades:
        return {
            "trades": 0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "median_return_pct": 0.0,
            "avg_bars": 0.0,
            "return_per_bar_pct": 0.0,
            "profitable_symbol_rate": 0.0,
            "add_rate": 0.0,
            "tp1_rate": 0.0,
            "worst_trade_pct": 0.0,
        }
    returns = np.array([trade.return_fraction for trade in trades], dtype=float)
    positives = returns[returns > 0].sum()
    negatives = -returns[returns < 0].sum()
    bars = np.array([max(1, trade.bars_held) for trade in trades], dtype=float)
    by_symbol: dict[str, float] = {}
    for trade in trades:
        by_symbol[trade.symbol] = by_symbol.get(trade.symbol, 0.0) + trade.return_fraction
    return {
        "trades": len(trades),
        "profit_factor": float(positives / negatives) if negatives > 0 else 99.0,
        "win_rate": float((returns > 0).mean()),
        "avg_return_pct": float(returns.mean() * 100),
        "median_return_pct": float(np.median(returns) * 100),
        "avg_bars": float(bars.mean()),
        "return_per_bar_pct": float((returns / bars).mean() * 100),
        "profitable_symbol_rate": float(
            np.mean([value > 0 for value in by_symbol.values()])
        ),
        "add_rate": float(np.mean([trade.added for trade in trades])),
        "tp1_rate": float(np.mean([trade.tp1_hit for trade in trades])),
        "worst_trade_pct": float(returns.min() * 100),
    }


def selection_score(training: dict, validation: dict) -> float:
    if training["trades"] < 100 or validation["trades"] < 30:
        return -1e9
    weakest_pf = min(training["profit_factor"], validation["profit_factor"], 3.0)
    weakest_avg = min(training["avg_return_pct"], validation["avg_return_pct"])
    return (
        math.log(max(1.0, training["trades"] + validation["trades"]))
        * (
            weakest_pf - 1.0
            + max(-1.0, weakest_avg) / 4.0
        )
    )


def entry_specs() -> list[EntrySpec]:
    return [
        EntrySpec("PB20-50-150", "pullback", 20, 50, 150, 45, 68, 0.8),
        EntrySpec("RSI40-50-200", "rsi_pullback", 20, 50, 200, 40, 62, 0.8),
        EntrySpec(
            "BO20-50-150",
            "breakout",
            20,
            50,
            150,
            50,
            74,
            1.1,
            breakout_lookback=20,
            turnover_min=200_000_000.0,
            atr_pct_max=0.08,
        ),
        EntrySpec(
            "BO50-50-200",
            "breakout",
            20,
            50,
            200,
            50,
            75,
            1.2,
            breakout_lookback=50,
            turnover_min=300_000_000.0,
            atr_pct_max=0.08,
        ),
        EntrySpec(
            "OS2-50-200",
            "oversold2",
            5,
            50,
            200,
            10,
            100,
            0.5,
            atr_pct_max=0.08,
        ),
        EntrySpec(
            "OS2R-50-200",
            "oversold_reversal",
            5,
            50,
            200,
            10,
            100,
            0.5,
            atr_pct_max=0.08,
        ),
    ]


def strategy_specs() -> list[StrategySpec]:
    specs: list[StrategySpec] = []
    for entry in entry_specs():
        if entry.mode in {"oversold2", "oversold_reversal"}:
            for stop_atr in (1.5, 2.0, 2.5):
                specs.append(
                    StrategySpec(
                        entry=entry,
                        exit_mode="mean",
                        stop_atr=stop_atr,
                        tp1_r=99.0,
                        tp2_r=100.0,
                        trail_atr=2.5,
                        add_enabled=False,
                        max_hold_bars=20,
                    )
                )
            continue
        for stop_atr in (1.5, 2.0, 2.5):
            for trail_atr in (2.0, 2.5, 3.0):
                for add_enabled in (False, True):
                    specs.append(
                        StrategySpec(
                            entry=entry,
                            exit_mode="runner",
                            stop_atr=stop_atr,
                            tp1_r=1.5,
                            tp2_r=6.0,
                            trail_atr=trail_atr,
                            add_enabled=add_enabled,
                        )
                    )
    return specs


def run_spec(
    spec: StrategySpec,
    frames: dict[str, pd.DataFrame],
    *,
    one_way_cost: float,
) -> list[Trade]:
    trades: list[Trade] = []
    for symbol, frame in frames.items():
        trades.extend(
            simulate_symbol(symbol, frame, spec, one_way_cost=one_way_cost)
        )
    return trades


def subset_trades(
    trades: list[Trade],
    *,
    symbols: set[str] | None = None,
    entry_before: str | None = None,
    entry_from: str | None = None,
) -> list[Trade]:
    return [
        trade
        for trade in trades
        if (symbols is None or trade.symbol in symbols)
        and (entry_before is None or trade.entry_date < entry_before)
        and (entry_from is None or trade.entry_date >= entry_from)
    ]


def round_metrics(metrics: dict) -> dict:
    return {
        key: value if isinstance(value, int) else round(float(value), 4)
        for key, value in metrics.items()
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--years", type=int, default=5)
    result.add_argument("--workers", type=int, default=8)
    result.add_argument("--max-symbols", type=int, default=0)
    result.add_argument(
        "--universe-source",
        choices=("jpx", "sheet"),
        default="jpx",
        help="Use all domestic TSE stocks from JPX (default) or the local ohlcv_4h symbols.",
    )
    result.add_argument("--refresh", action="store_true")
    result.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    result.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    result.add_argument(
        "--one-way-cost-pct",
        type=float,
        default=0.15,
        help="Commission plus slippage charged on every fill (default: 0.15%%).",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    end_date = datetime.now(JST).date()
    start_date = end_date - timedelta(days=max(2, args.years) * 366)
    cutoff = (end_date - timedelta(days=365)).isoformat()

    if args.universe_source == "jpx":
        print("Reading the domestic-stock universe from the official JPX workbook...")
        symbols = fetch_jpx_universe()
    else:
        print("Reading symbol universe from ohlcv_4h (no signal-history read)...")
        symbols = fetch_sheet_universe()
    if args.max_symbols > 0:
        symbols = sorted(symbols, key=lambda item: hashlib.sha256(item.encode()).hexdigest())[
            : args.max_symbols
        ]
    print(f"Universe: {len(symbols)} symbols")

    benchmark_symbol = "1306"
    download_symbols = sorted(set(symbols) | {benchmark_symbol})
    bars_by_symbol, failures = load_market_data(
        download_symbols,
        start_date,
        end_date,
        args.cache,
        workers=args.workers,
        refresh=args.refresh,
    )
    frames = {
        symbol: frame
        for symbol, bars in bars_by_symbol.items()
        if symbol in symbols
        if len(frame := prepare_frame(bars)) >= 220
    }
    benchmark = prepare_frame(bars_by_symbol.get(benchmark_symbol, []))
    if benchmark.empty or len(benchmark) < 220:
        raise RuntimeError("TOPIX ETF benchmark data is unavailable")
    benchmark["market_ok"] = (
        (benchmark["close"] > benchmark["ema200"])
        & (benchmark["ema50"] > benchmark["ema200"])
        & (benchmark["ema200"] > benchmark["ema200"].shift(20))
    )
    market_by_date = benchmark.set_index("date")["market_ok"]
    for frame in frames.values():
        frame["market_ok"] = frame["date"].map(market_by_date).fillna(False)
    print(
        f"Usable: {len(frames)} symbols / failures: {len(failures)} / "
        f"range: {start_date}..{end_date}"
    )

    development_symbols = {s for s in frames if stable_bucket(s) != 0}
    unseen_symbols = set(frames) - development_symbols
    one_way_cost = max(0.0, args.one_way_cost_pct) / 100.0

    candidates: list[dict] = []
    all_trades_by_key: dict[str, list[Trade]] = {}
    specs = strategy_specs()
    for position, spec in enumerate(specs, start=1):
        trades = run_spec(spec, frames, one_way_cost=one_way_cost)
        all_trades_by_key[spec.key] = trades
        selection = metric_summary(
            subset_trades(
                trades,
                symbols=development_symbols,
                entry_before=cutoff,
            )
        )
        recent_validation = metric_summary(
            subset_trades(
                trades,
                symbols=development_symbols,
                entry_from=cutoff,
            )
        )
        unseen = metric_summary(subset_trades(trades, symbols=unseen_symbols))
        unseen_recent = metric_summary(
            subset_trades(
                trades,
                symbols=unseen_symbols,
                entry_from=cutoff,
            )
        )
        candidates.append(
            {
                "key": spec.key,
                "spec": asdict(spec),
                "selection": round_metrics(selection),
                "recent_validation": round_metrics(recent_validation),
                "unseen_symbols": round_metrics(unseen),
                "unseen_recent": round_metrics(unseen_recent),
                "score": selection_score(selection, recent_validation),
            }
        )
        if position % 10 == 0 or position == len(specs):
            print(f"  Backtest: {position}/{len(specs)} candidates", flush=True)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    best_spec_dict = best["spec"]
    best_spec = next(spec for spec in specs if spec.key == best["key"])
    paired = replace(best_spec, add_enabled=not best_spec.add_enabled)
    paired_trades = all_trades_by_key[paired.key]
    best_trades = all_trades_by_key[best_spec.key]

    best["all"] = round_metrics(metric_summary(best_trades))
    best["matched_add_comparison"] = {
        "key": paired.key,
        "all": round_metrics(metric_summary(paired_trades)),
        "selection": round_metrics(
            metric_summary(
                subset_trades(
                    paired_trades,
                    symbols=development_symbols,
                    entry_before=cutoff,
                )
            )
        ),
        "recent_validation": round_metrics(
            metric_summary(
                subset_trades(
                    paired_trades,
                    symbols=development_symbols,
                    entry_from=cutoff,
                )
            )
        ),
        "unseen_symbols": round_metrics(
            metric_summary(subset_trades(paired_trades, symbols=unseen_symbols))
        ),
        "unseen_recent": round_metrics(
            metric_summary(
                subset_trades(
                    paired_trades,
                    symbols=unseen_symbols,
                    entry_from=cutoff,
                )
            )
        ),
    }

    folds = []
    fold_start = pd.Timestamp(start_date)
    while fold_start < pd.Timestamp(end_date):
        fold_end = fold_start + pd.DateOffset(years=1)
        fold_trades = [
            trade
            for trade in best_trades
            if fold_start.strftime("%Y-%m-%d")
            <= trade.entry_date
            < fold_end.strftime("%Y-%m-%d")
        ]
        folds.append(
            {
                "from": fold_start.strftime("%Y-%m-%d"),
                "to": fold_end.strftime("%Y-%m-%d"),
                **round_metrics(metric_summary(fold_trades)),
            }
        )
        fold_start = fold_end
    best["yearly_folds"] = folds

    output = {
        "generated_at": datetime.now(JST).isoformat(),
        "data": {
            "universe_source": (
                "official JPX domestic Prime/Standard/Growth listed-issues workbook"
                if args.universe_source == "jpx"
                else "unique symbols in ohlcv_4h column C"
            ),
            "price_source": "Yahoo Finance daily chart API, adjusted OHLC",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols_requested": len(symbols),
            "symbols_usable": len(frames),
            "symbols_failed": len(failures),
            "development_symbols": len(development_symbols),
            "unseen_symbols": len(unseen_symbols),
            "recent_oos_cutoff": cutoff,
            "one_way_cost_pct": args.one_way_cost_pct,
            "market_filter": "1306 TOPIX ETF above rising EMA200 with EMA50 above EMA200",
        },
        "selection_policy": (
            "Rank on both older and latest-year trades from development symbols; "
            "reserve a deterministic 20% of symbols as the untouched OOS set."
        ),
        "best": best,
        "top_candidates": candidates[:10],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\nBEST")
    print(json.dumps(best, ensure_ascii=False, indent=2))
    print(f"\nSaved: {args.output}")
    if failures:
        sample = dict(list(sorted(failures.items()))[:10])
        print(f"Failure sample: {json.dumps(sample, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
