#!/usr/bin/env python3
"""Experimental interpretable scoring lab for BOTTOM signals.

This script is intentionally isolated from production bot files. It reads
spreadsheet data, builds leakage-safe features as of each signal date, selects
interpretable predicates on a chronological validation split, and writes only
aggregate experiment artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SPREADSHEET_ID = "1pcD6-462nyv1A1bcW5UeWwaxBr7A1RIJ6Ofixeo5Xb8"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ALERTS_SHEET = "alerts_raw"
OHLCV_SHEET = "ohlcv_4h"

MAX_CONDITIONS = 12
MAX_PER_FAMILY = 2
MIN_SELECTED_VALID = 15


@dataclass
class Stats:
    n: int = 0
    win_rate: float = 0.0
    avg: float = 0.0
    median: float = 0.0
    win10_rate: float = 0.0
    lose10_rate: float = 0.0
    min_perf: float = 0.0
    max_perf: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "win_rate": round(self.win_rate, 6),
            "avg": round(self.avg, 6),
            "median": round(self.median, 6),
            "win10_rate": round(self.win10_rate, 6),
            "lose10_rate": round(self.lose10_rate, 6),
            "min_perf": round(self.min_perf, 6),
            "max_perf": round(self.max_perf, 6),
        }


@dataclass(frozen=True)
class Predicate:
    feature: str
    family: str
    op: str
    threshold: float | None = None
    low: float | None = None
    high: float | None = None
    label: str = ""

    def matches(self, row: dict[str, Any]) -> bool:
        v = row.get(self.feature)
        if not is_finite(v):
            return False
        value = float(v)
        if self.op == ">=":
            return self.threshold is not None and value >= self.threshold
        if self.op == "<=":
            return self.threshold is not None and value <= self.threshold
        if self.op == "between":
            return (
                self.low is not None
                and self.high is not None
                and self.low <= value <= self.high
            )
        raise ValueError(f"Unsupported predicate op: {self.op}")

    def key(self) -> tuple[Any, ...]:
        return (
            self.feature,
            self.op,
            round(self.threshold, 6) if self.threshold is not None else None,
            round(self.low, 6) if self.low is not None else None,
            round(self.high, 6) if self.high is not None else None,
        )

    def description(self) -> str:
        if self.op == "between":
            return f"{self.label or self.feature} between {fmt_num(self.low)} and {fmt_num(self.high)}"
        return f"{self.label or self.feature} {self.op} {fmt_num(self.threshold)}"

    def to_json(self, weight: int | None = None, validation: Stats | None = None) -> dict[str, Any]:
        payload = {
            "feature": self.feature,
            "family": self.family,
            "operator": self.op,
            "description": self.description(),
        }
        if self.threshold is not None:
            payload["threshold"] = round(self.threshold, 6)
        if self.low is not None:
            payload["low"] = round(self.low, 6)
        if self.high is not None:
            payload["high"] = round(self.high, 6)
        if weight is not None:
            payload["weight"] = weight
        if validation is not None:
            payload["validation_stats"] = validation.to_json()
        return payload


@dataclass
class SelectionStep:
    predicate: Predicate
    score: float
    weight: int = 1
    validation_stats: Stats = field(default_factory=Stats)


FEATURE_FAMILIES: dict[str, str] = {
    "ret_1d": "returns",
    "ret_3d": "returns",
    "ret_5d": "returns",
    "ret_10d": "returns",
    "ret_20d": "returns",
    "ema5_gap": "trend",
    "ema10_gap": "trend",
    "ema25_gap": "trend",
    "ema75_gap": "trend",
    "ema25_slope_5": "trend",
    "ema75_slope_5": "trend",
    "vol_ratio_5": "volume",
    "vol_ratio_10": "volume",
    "vol_ratio_20": "volume",
    "volume_z20": "volume",
    "atr14_pct": "risk",
    "true_range_pct": "risk",
    "realized_vol_10": "risk",
    "body_pct": "candle",
    "upper_wick_pct": "candle",
    "lower_wick_pct": "candle",
    "close_pos_day": "candle",
    "rsi14": "oscillator",
    "stoch14": "oscillator",
    "macd_line_pct": "momentum",
    "macd_hist_pct": "momentum",
    "macd_hist_slope_3": "momentum",
    "bb_pct": "range",
    "bb_width_pct": "range",
    "range_pos_5": "range",
    "range_pos_20": "range",
    "drawdown_20": "range",
    "rebound_5": "range",
    "liquidity_20": "liquidity",
}

FEATURE_LABELS: dict[str, str] = {
    "ret_1d": "1d return",
    "ret_3d": "3d return",
    "ret_5d": "5d return",
    "ret_10d": "10d return",
    "ret_20d": "20d return",
    "ema5_gap": "close vs EMA5",
    "ema10_gap": "close vs EMA10",
    "ema25_gap": "close vs EMA25",
    "ema75_gap": "close vs EMA75",
    "ema25_slope_5": "EMA25 5d slope",
    "ema75_slope_5": "EMA75 5d slope",
    "vol_ratio_5": "volume vs prior 5d",
    "vol_ratio_10": "volume vs prior 10d",
    "vol_ratio_20": "volume vs prior 20d",
    "volume_z20": "volume z-score 20d",
    "atr14_pct": "ATR14 percent",
    "true_range_pct": "true range percent",
    "realized_vol_10": "10d realized volatility",
    "body_pct": "candle body percent",
    "upper_wick_pct": "upper wick percent",
    "lower_wick_pct": "lower wick percent",
    "close_pos_day": "close position in day",
    "rsi14": "RSI14",
    "stoch14": "Stochastic K14",
    "macd_line_pct": "MACD line percent",
    "macd_hist_pct": "MACD histogram percent",
    "macd_hist_slope_3": "MACD histogram 3d slope",
    "bb_pct": "Bollinger position",
    "bb_width_pct": "Bollinger width percent",
    "range_pos_5": "5d range position",
    "range_pos_20": "20d range position",
    "drawdown_20": "20d drawdown",
    "rebound_5": "5d rebound from low",
    "liquidity_20": "20d average traded value",
}


def normalize_date_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("/", "-")
    return text[:10]


def parse_float(value: Any) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def parse_perf(value: Any) -> float:
    if value is None:
        return float("nan")
    raw = str(value)
    number = parse_float(value)
    if not math.isfinite(number):
        return float("nan")
    return number / 100.0 if "%" in raw else number


def clean_symbol(value: Any) -> str:
    text = str(value or "").strip()
    return text.split(":")[-1] if ":" in text else text


def is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def fmt_num(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1000:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.2f}"
    return f"{value:.3f}"


def pct(value: float) -> str:
    return f"{value * 100:+.1f}%"


def header_index(header: list[str], name: str) -> int:
    lower = [h.lower().strip() for h in header]
    return lower.index(name) if name in lower else -1


def row_get(row: list[Any], index: int) -> Any:
    return row[index] if 0 <= index < len(row) else ""


def parse_alerts(rows: list[list[Any]], objective: str = "perf_5bd") -> list[dict[str, Any]]:
    if len(rows) < 5:
        return []
    header = [str(h).lower().strip() for h in rows[3]]
    idx = {
        "alert_id": header_index(header, "alert_id"),
        "signal_type": header_index(header, "signal_type"),
        "symbol": header_index(header, "symbol_code"),
        "name": header_index(header, "symbol_name"),
        "date": header_index(header, "signal_date"),
        "entry": header_index(header, "entry_price"),
        objective: header_index(header, objective),
    }
    if idx["symbol"] < 0 or idx["date"] < 0 or idx[objective] < 0:
        raise ValueError(f"alerts_raw is missing a required column for {objective}")

    seen_alert_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for raw in rows[4:]:
        if not raw:
            continue
        if str(row_get(raw, idx["signal_type"])).strip().upper() != "BOTTOM":
            continue
        symbol = clean_symbol(row_get(raw, idx["symbol"]))
        signal_date = normalize_date_key(row_get(raw, idx["date"]))
        perf = parse_perf(row_get(raw, idx[objective]))
        if not symbol or not signal_date or not math.isfinite(perf):
            continue

        alert_id = str(row_get(raw, idx["alert_id"])).strip() if idx["alert_id"] >= 0 else ""
        if alert_id:
            if alert_id in seen_alert_ids:
                continue
            seen_alert_ids.add(alert_id)

        records.append(
            {
                "alert_id": alert_id,
                "symbol": symbol,
                "name": str(row_get(raw, idx["name"])).strip() if idx["name"] >= 0 else symbol,
                "date": signal_date,
                "entry": parse_float(row_get(raw, idx["entry"])),
                "perf": perf,
            }
        )
    return sorted(records, key=lambda r: (r["date"], r["symbol"], r.get("alert_id", "")))


def parse_ohlcv(rows: list[list[Any]]) -> dict[str, list[dict[str, float | str]]]:
    if len(rows) < 2:
        return {}
    header = [str(h).lower().strip() for h in rows[0]]
    idx = {
        "timestamp": header_index(header, "timestamp"),
        "symbol": header_index(header, "symbol"),
        "open": header_index(header, "open"),
        "high": header_index(header, "high"),
        "low": header_index(header, "low"),
        "close": header_index(header, "close"),
        "volume": header_index(header, "volume"),
    }
    if min(idx.values()) < 0:
        raise ValueError("ohlcv_4h is missing one or more required columns")

    grouped: dict[str, list[dict[str, float | str]]] = {}
    for raw in rows[1:]:
        if not raw:
            continue
        symbol = clean_symbol(row_get(raw, idx["symbol"]))
        date = normalize_date_key(row_get(raw, idx["timestamp"]))
        bar = {
            "date": date,
            "open": parse_float(row_get(raw, idx["open"])),
            "high": parse_float(row_get(raw, idx["high"])),
            "low": parse_float(row_get(raw, idx["low"])),
            "close": parse_float(row_get(raw, idx["close"])),
            "volume": parse_float(row_get(raw, idx["volume"])),
        }
        if (
            symbol
            and date
            and all(is_finite(bar[k]) for k in ("open", "high", "low", "close", "volume"))
        ):
            grouped.setdefault(symbol, []).append(bar)

    return {sym: aggregate_daily(sorted(bars, key=lambda b: str(b["date"]))) for sym, bars in grouped.items()}


def aggregate_daily(bars: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    daily: dict[str, dict[str, float | str]] = {}
    for bar in bars:
        date = normalize_date_key(bar.get("date"))
        if not date:
            continue
        if date not in daily:
            daily[date] = {
                "date": date,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": float(bar["volume"]),
            }
        else:
            day = daily[date]
            day["high"] = max(float(day["high"]), float(bar["high"]))
            day["low"] = min(float(day["low"]), float(bar["low"]))
            day["close"] = float(bar["close"])
            day["volume"] = float(day["volume"]) + float(bar["volume"])
    return sorted(daily.values(), key=lambda b: str(b["date"]))


def moving_average(values: list[float], period: int, end: int) -> float:
    if end - period + 1 < 0:
        return float("nan")
    window = values[end - period + 1 : end + 1]
    return sum(window) / period


def ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    result: list[float | None] = [None] * (period - 1)
    ema = sum(values[:period]) / period
    result.append(ema)
    for value in values[period:]:
        ema = value * k + ema * (1 - k)
        result.append(ema)
    return result


def pct_change(current: float, previous: float) -> float:
    if not is_finite(current) or not is_finite(previous) or previous == 0:
        return float("nan")
    return current / previous - 1.0


def ratio_to_avg(values: list[float], last: int, lookback: int) -> float:
    if last <= 0:
        return float("nan")
    start = max(0, last - lookback)
    window = values[start:last]
    if not window:
        return float("nan")
    avg = sum(window) / len(window)
    return values[last] / avg if avg > 0 else float("nan")


def stddev(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    return statistics.pstdev(values)


def compute_features(daily_bars: list[dict[str, Any]], signal_date: str) -> dict[str, Any] | None:
    signal_key = normalize_date_key(signal_date)
    bars = [b for b in daily_bars if str(b["date"]) <= signal_key]
    if len(bars) < 30:
        return None

    last = len(bars) - 1
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    volumes = [float(b["volume"]) for b in bars]
    close = closes[last]
    high = highs[last]
    low = lows[last]
    open_ = opens[last]
    if close <= 0:
        return None

    ema5 = ema_series(closes, 5)
    ema10 = ema_series(closes, 10)
    ema12 = ema_series(closes, 12)
    ema25 = ema_series(closes, 25)
    ema26 = ema_series(closes, 26)
    ema75 = ema_series(closes, 75)

    tr_values = []
    for i in range(1, len(bars)):
        tr_values.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    atr14 = sum(tr_values[-14:]) / min(14, len(tr_values)) if tr_values else float("nan")

    returns = [pct_change(closes[i], closes[i - 1]) for i in range(1, len(closes))]
    gains = [max(0.0, x) for x in returns[-14:] if is_finite(x)]
    losses = [max(0.0, -x) for x in returns[-14:] if is_finite(x)]
    avg_gain = sum(gains) / 14 if len(returns) >= 14 else 0.0
    avg_loss = sum(losses) / 14 if len(returns) >= 14 else 0.0
    rsi14 = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) if avg_loss > 0 else 100.0

    lo14 = min(lows[max(0, last - 13) : last + 1])
    hi14 = max(highs[max(0, last - 13) : last + 1])
    stoch14 = (close - lo14) / (hi14 - lo14) * 100.0 if hi14 > lo14 else 50.0

    bb_window = closes[max(0, last - 19) : last + 1]
    bb_mean = sum(bb_window) / len(bb_window)
    bb_std = statistics.pstdev(bb_window) if len(bb_window) > 1 else 0.0
    bb_pct = ((close - (bb_mean - 2 * bb_std)) / (4 * bb_std)) if bb_std > 0 else 0.5
    bb_width_pct = (4 * bb_std / close) if close > 0 else float("nan")

    macd_line: list[float | None] = []
    for a, b in zip(ema12, ema26):
        macd_line.append(a - b if a is not None and b is not None else None)
    valid_macd = [x for x in macd_line if x is not None]
    macd_signal = ema_series(valid_macd, 9)
    if valid_macd and macd_signal and macd_signal[-1] is not None:
        macd_hist = valid_macd[-1] - float(macd_signal[-1])
        macd_line_pct = valid_macd[-1] / close
        macd_hist_pct = macd_hist / close
        macd_hist_slope_3 = (
            (valid_macd[-1] - float(macd_signal[-1]))
            - (valid_macd[-4] - float(macd_signal[-4]))
            if len(valid_macd) >= 4 and len(macd_signal) >= 4 and macd_signal[-4] is not None
            else float("nan")
        )
    else:
        macd_line_pct = macd_hist_pct = macd_hist_slope_3 = float("nan")

    def ema_gap(series: list[float | None]) -> float:
        value = series[last] if last < len(series) else None
        return pct_change(close, float(value)) if value is not None else float("nan")

    def ema_slope(series: list[float | None], lookback: int) -> float:
        if last - lookback < 0:
            return float("nan")
        now = series[last]
        prev = series[last - lookback]
        if now is None or prev is None:
            return float("nan")
        return pct_change(float(now), float(prev))

    def range_pos(lookback: int) -> float:
        start = max(0, last - lookback + 1)
        lo = min(lows[start : last + 1])
        hi = max(highs[start : last + 1])
        return (close - lo) / (hi - lo) if hi > lo else 0.5

    def ret(lookback: int) -> float:
        if last - lookback < 0:
            return float("nan")
        return pct_change(close, closes[last - lookback])

    day_range = high - low
    close_pos_day = (close - low) / day_range if day_range > 0 else 0.5
    body_pct = (close - open_) / close
    upper_wick_pct = (high - max(open_, close)) / close
    lower_wick_pct = (min(open_, close) - low) / close

    lo5 = min(lows[max(0, last - 4) : last + 1])
    hi20 = max(highs[max(0, last - 19) : last + 1])
    liquidity_window = [
        closes[i] * volumes[i] for i in range(max(0, last - 19), last + 1)
    ]

    features: dict[str, Any] = {
        "ret_1d": ret(1),
        "ret_3d": ret(3),
        "ret_5d": ret(5),
        "ret_10d": ret(10),
        "ret_20d": ret(20),
        "ema5_gap": ema_gap(ema5),
        "ema10_gap": ema_gap(ema10),
        "ema25_gap": ema_gap(ema25),
        "ema75_gap": ema_gap(ema75),
        "ema25_slope_5": ema_slope(ema25, 5),
        "ema75_slope_5": ema_slope(ema75, 5),
        "vol_ratio_5": ratio_to_avg(volumes, last, 5),
        "vol_ratio_10": ratio_to_avg(volumes, last, 10),
        "vol_ratio_20": ratio_to_avg(volumes, last, 20),
        "volume_z20": volume_zscore(volumes, last, 20),
        "atr14_pct": atr14 / close if is_finite(atr14) else float("nan"),
        "true_range_pct": true_range_pct(highs, lows, closes, last),
        "realized_vol_10": stddev([x for x in returns[-10:] if is_finite(x)]),
        "body_pct": body_pct,
        "upper_wick_pct": upper_wick_pct,
        "lower_wick_pct": lower_wick_pct,
        "close_pos_day": close_pos_day,
        "rsi14": rsi14,
        "stoch14": stoch14,
        "macd_line_pct": macd_line_pct,
        "macd_hist_pct": macd_hist_pct,
        "macd_hist_slope_3": macd_hist_slope_3 / close if is_finite(macd_hist_slope_3) else float("nan"),
        "bb_pct": max(0.0, min(1.0, bb_pct)),
        "bb_width_pct": bb_width_pct,
        "range_pos_5": range_pos(5),
        "range_pos_20": range_pos(20),
        "drawdown_20": close / hi20 - 1.0 if hi20 > 0 else float("nan"),
        "rebound_5": close / lo5 - 1.0 if lo5 > 0 else float("nan"),
        "liquidity_20": sum(liquidity_window) / len(liquidity_window) if liquidity_window else float("nan"),
        "close": close,
        "signal_bar_date": str(bars[-1]["date"]),
    }
    features.update(existing_logic_flags(features))
    return features


def volume_zscore(values: list[float], last: int, lookback: int) -> float:
    if last <= 0:
        return float("nan")
    window = values[max(0, last - lookback) : last]
    if len(window) < 2:
        return float("nan")
    sd = statistics.pstdev(window)
    if sd <= 0:
        return 0.0
    return (values[last] - (sum(window) / len(window))) / sd


def true_range_pct(highs: list[float], lows: list[float], closes: list[float], last: int) -> float:
    if last <= 0 or closes[last] <= 0:
        return float("nan")
    tr = max(
        highs[last] - lows[last],
        abs(highs[last] - closes[last - 1]),
        abs(lows[last] - closes[last - 1]),
    )
    return tr / closes[last]


def existing_logic_flags(features: dict[str, Any]) -> dict[str, bool]:
    return {
        "ema75": bool(is_finite(features.get("ema75_gap")) and features["ema75_gap"] > 0),
        "ema25": bool(is_finite(features.get("ema25_gap")) and features["ema25_gap"] > 0),
        "vol20": bool(is_finite(features.get("vol_ratio_20")) and features["vol_ratio_20"] >= 2.0),
        "vol15": bool(is_finite(features.get("vol_ratio_20")) and features["vol_ratio_20"] >= 1.5),
        "vol12": bool(is_finite(features.get("vol_ratio_20")) and features["vol_ratio_20"] >= 1.2),
        "sbull": bool(is_finite(features.get("body_pct")) and features["body_pct"] >= 0.005),
        "body1": bool(is_finite(features.get("body_pct")) and features["body_pct"] >= 0.01),
        "macdpos": bool(is_finite(features.get("macd_hist_pct")) and features["macd_hist_pct"] > 0),
        "atr5": bool(is_finite(features.get("atr14_pct")) and features["atr14_pct"] < 0.05),
        "atr3": bool(is_finite(features.get("atr14_pct")) and features["atr14_pct"] < 0.03),
        "atr7": bool(is_finite(features.get("atr14_pct")) and features["atr14_pct"] < 0.07),
        "hb20": bool(is_finite(features.get("range_pos_20")) and features["range_pos_20"] >= 1.0),
        "stoch75": bool(is_finite(features.get("stoch14")) and features["stoch14"] >= 75),
        "stoch60": bool(is_finite(features.get("stoch14")) and features["stoch14"] >= 60),
        "rsi5070": bool(is_finite(features.get("rsi14")) and 50 <= features["rsi14"] < 70),
        "rsi4060": bool(is_finite(features.get("rsi14")) and 40 <= features["rsi14"] < 60),
        "bb80": bool(is_finite(features.get("bb_pct")) and features["bb_pct"] >= 0.80),
        "macdgc": False,
    }


def build_dataset(alerts: list[dict[str, Any]], ohlcv: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], int]:
    dataset: list[dict[str, Any]] = []
    skipped = 0
    for alert in alerts:
        features = compute_features(ohlcv.get(alert["symbol"], []), alert["date"])
        if not features:
            skipped += 1
            continue
        dataset.append({**alert, **features})
    return sorted(dataset, key=lambda r: (r["date"], r["symbol"], r.get("alert_id", ""))), skipped


def split_chronological(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    n = len(rows)
    train_end = int(n * 0.60)
    valid_end = int(n * 0.80)
    return rows[:train_end], rows[train_end:valid_end], rows[valid_end:]


def calc_stats(rows: Iterable[dict[str, Any]]) -> Stats:
    values = [float(r["perf"]) for r in rows if is_finite(r.get("perf"))]
    if not values:
        return Stats()
    return Stats(
        n=len(values),
        win_rate=sum(1 for v in values if v > 0) / len(values),
        avg=sum(values) / len(values),
        median=statistics.median(values),
        win10_rate=sum(1 for v in values if v >= 0.10) / len(values),
        lose10_rate=sum(1 for v in values if v <= -0.10) / len(values),
        min_perf=min(values),
        max_perf=max(values),
    )


def quantiles(values: list[float], qs: list[float]) -> list[float]:
    clean = sorted(v for v in values if is_finite(v))
    if not clean:
        return []
    result = []
    for q in qs:
        pos = (len(clean) - 1) * q
        lo = math.floor(pos)
        hi = math.ceil(pos)
        if lo == hi:
            result.append(clean[int(pos)])
        else:
            result.append(clean[lo] * (hi - pos) + clean[hi] * (pos - lo))
    return result


def unique_thresholds(values: Iterable[float]) -> list[float]:
    result: list[float] = []
    seen: set[float] = set()
    for value in values:
        if not is_finite(value):
            continue
        rounded = round(float(value), 6)
        if rounded not in seen:
            seen.add(rounded)
            result.append(float(value))
    return result


def generate_candidates(train: list[dict[str, Any]]) -> list[Predicate]:
    candidates: list[Predicate] = []
    keys_seen: set[tuple[Any, ...]] = set()

    for feature, family in FEATURE_FAMILIES.items():
        values = [float(r[feature]) for r in train if is_finite(r.get(feature))]
        if len(values) < max(20, len(train) * 0.3):
            continue
        qs = quantiles(values, [0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85])
        anchors = domain_anchors(feature)
        for threshold in unique_thresholds([*qs, *anchors]):
            add_candidate(
                candidates,
                keys_seen,
                Predicate(feature, family, ">=", threshold=threshold, label=FEATURE_LABELS.get(feature, feature)),
            )
            add_candidate(
                candidates,
                keys_seen,
                Predicate(feature, family, "<=", threshold=threshold, label=FEATURE_LABELS.get(feature, feature)),
            )

    for pred in interval_candidates():
        add_candidate(candidates, keys_seen, pred)

    return candidates


def add_candidate(candidates: list[Predicate], seen: set[tuple[Any, ...]], pred: Predicate) -> None:
    key = pred.key()
    if key not in seen:
        seen.add(key)
        candidates.append(pred)


def domain_anchors(feature: str) -> list[float]:
    anchors = {
        "ret_1d": [-0.03, -0.015, 0.0, 0.015, 0.03],
        "ret_3d": [-0.05, -0.025, 0.0, 0.025, 0.05],
        "ret_5d": [-0.08, -0.04, 0.0, 0.04, 0.08],
        "ret_10d": [-0.12, -0.06, 0.0, 0.06, 0.12],
        "ret_20d": [-0.20, -0.10, 0.0, 0.10, 0.20],
        "ema5_gap": [-0.03, -0.015, 0.0, 0.015, 0.03],
        "ema10_gap": [-0.04, -0.02, 0.0, 0.02, 0.04],
        "ema25_gap": [-0.08, -0.03, 0.0, 0.03, 0.08],
        "ema75_gap": [-0.15, -0.05, 0.0, 0.05, 0.15],
        "ema25_slope_5": [-0.03, -0.01, 0.0, 0.01, 0.03],
        "ema75_slope_5": [-0.03, -0.01, 0.0, 0.01, 0.03],
        "vol_ratio_5": [0.8, 1.0, 1.2, 1.5, 2.0, 3.0],
        "vol_ratio_10": [0.8, 1.0, 1.2, 1.5, 2.0, 3.0],
        "vol_ratio_20": [0.8, 1.0, 1.2, 1.5, 2.0, 3.0],
        "volume_z20": [-1.0, 0.0, 1.0, 2.0, 3.0],
        "atr14_pct": [0.03, 0.05, 0.07, 0.10],
        "true_range_pct": [0.03, 0.05, 0.07, 0.10],
        "realized_vol_10": [0.02, 0.035, 0.05, 0.08],
        "body_pct": [-0.03, -0.01, 0.0, 0.005, 0.01, 0.02, 0.04],
        "upper_wick_pct": [0.005, 0.01, 0.02, 0.04],
        "lower_wick_pct": [0.005, 0.01, 0.02, 0.04],
        "close_pos_day": [0.25, 0.5, 0.75, 0.9],
        "rsi14": [35, 40, 45, 50, 55, 60, 65, 70],
        "stoch14": [20, 35, 50, 60, 70, 80],
        "macd_line_pct": [-0.03, -0.01, 0.0, 0.01, 0.03],
        "macd_hist_pct": [-0.02, -0.005, 0.0, 0.005, 0.02],
        "macd_hist_slope_3": [-0.02, -0.005, 0.0, 0.005, 0.02],
        "bb_pct": [0.2, 0.35, 0.5, 0.65, 0.8],
        "bb_width_pct": [0.05, 0.10, 0.20, 0.30],
        "range_pos_5": [0.2, 0.35, 0.5, 0.65, 0.8, 0.95],
        "range_pos_20": [0.2, 0.35, 0.5, 0.65, 0.8, 0.95],
        "drawdown_20": [-0.30, -0.20, -0.10, -0.05, 0.0],
        "rebound_5": [0.0, 0.02, 0.05, 0.10],
    }
    return anchors.get(feature, [])


def interval_candidates() -> list[Predicate]:
    specs = [
        ("rsi14", "oscillator", [(35, 55), (40, 60), (45, 65), (50, 70)]),
        ("stoch14", "oscillator", [(20, 60), (35, 75), (50, 90), (60, 100)]),
        ("bb_pct", "range", [(0.0, 0.45), (0.2, 0.65), (0.35, 0.8), (0.5, 0.95)]),
        ("range_pos_5", "range", [(0.0, 0.5), (0.2, 0.7), (0.35, 0.85), (0.5, 0.95)]),
        ("range_pos_20", "range", [(0.0, 0.5), (0.2, 0.7), (0.35, 0.85), (0.5, 0.95)]),
        ("close_pos_day", "candle", [(0.0, 0.5), (0.35, 0.75), (0.5, 1.0)]),
    ]
    result = []
    for feature, family, intervals in specs:
        for low, high in intervals:
            result.append(
                Predicate(
                    feature,
                    family,
                    "between",
                    low=low,
                    high=high,
                    label=FEATURE_LABELS.get(feature, feature),
                )
            )
    return result


def mask_rows(rows: list[dict[str, Any]], predicates: list[Predicate]) -> list[dict[str, Any]]:
    if not predicates:
        return list(rows)
    return [row for row in rows if all(pred.matches(row) for pred in predicates)]


def candidate_objective(stats: Stats, baseline: Stats, stability: float) -> float:
    if stats.n == 0:
        return -9999.0
    return (
        (stats.win_rate - baseline.win_rate) * 120.0
        + (stats.avg - baseline.avg) * 260.0
        + (stats.win10_rate - baseline.win10_rate) * 90.0
        - max(0.0, stats.lose10_rate - baseline.lose10_rate) * 120.0
        + math.log(stats.n + 1.0) * 2.0
        + stability * 10.0
    )


def stability_score(train: list[dict[str, Any]], predicates: list[Predicate]) -> float:
    if len(train) < 30:
        return 0.0
    fold_size = len(train) // 3
    scores = []
    for i in range(3):
        start = i * fold_size
        end = len(train) if i == 2 else (i + 1) * fold_size
        fold = train[start:end]
        base = calc_stats(fold)
        selected = calc_stats(mask_rows(fold, predicates))
        if selected.n < max(4, len(fold) * 0.02):
            scores.append(-0.5)
        else:
            scores.append(1.0 if selected.win_rate >= base.win_rate and selected.avg >= base.avg else -0.25)
    return sum(scores) / len(scores)


def select_predicates(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    candidates: list[Predicate],
) -> list[SelectionStep]:
    selected: list[SelectionStep] = []
    family_counts: dict[str, int] = {}
    base_valid = calc_stats(validation)

    for _ in range(MAX_CONDITIONS):
        best: SelectionStep | None = None
        current_preds = [step.predicate for step in selected]
        used_keys = {step.predicate.key() for step in selected}
        used_features = {step.predicate.feature for step in selected}

        for pred in candidates:
            if pred.key() in used_keys:
                continue
            if pred.feature in used_features:
                continue
            if family_counts.get(pred.family, 0) >= MAX_PER_FAMILY:
                continue

            trial = [*current_preds, pred]
            validation_rows = mask_rows(validation, trial)
            if len(validation_rows) < min_validation_rows(validation):
                continue
            train_rows = mask_rows(train, trial)
            if len(train_rows) < max(12, len(train) * 0.02):
                continue

            stats = calc_stats(validation_rows)
            stability = stability_score(train, trial)
            score = candidate_objective(stats, base_valid, stability)
            if best is None or score > best.score:
                best = SelectionStep(pred, score, validation_stats=stats)

        if best is None or best.score <= 0:
            break
        selected.append(best)
        family_counts[best.predicate.family] = family_counts.get(best.predicate.family, 0) + 1

    assign_weights(selected)
    return selected


def assign_weights(steps: list[SelectionStep]) -> None:
    if not steps:
        return
    positives = [max(0.1, step.score) for step in steps]
    lo = min(positives)
    hi = max(positives)
    for step, score in zip(steps, positives):
        if hi == lo:
            step.weight = 8
        else:
            step.weight = max(3, min(14, int(round(4 + (score - lo) / (hi - lo) * 10))))


def min_validation_rows(rows: list[dict[str, Any]]) -> int:
    return max(MIN_SELECTED_VALID, int(len(rows) * 0.05))


def score_row(row: dict[str, Any], steps: list[SelectionStep]) -> int:
    total = sum(step.weight for step in steps)
    if total <= 0:
        return 0
    earned = sum(step.weight for step in steps if step.predicate.matches(row))
    return int(round(earned / total * 100))


def add_scores(rows: list[dict[str, Any]], steps: list[SelectionStep]) -> list[dict[str, Any]]:
    return [{**row, "new_score": score_row(row, steps)} for row in rows]


def choose_cutoff(validation_scored: list[dict[str, Any]]) -> tuple[int, Stats, list[dict[str, Any]]]:
    if not validation_scored:
        return 100, Stats(), []
    base = calc_stats(validation_scored)
    unique_scores = sorted({int(r["new_score"]) for r in validation_scored}, reverse=True)
    min_n = min_validation_rows(validation_scored)
    options = []
    for cutoff in unique_scores:
        selected = [r for r in validation_scored if int(r["new_score"]) >= cutoff]
        if len(selected) < min_n:
            continue
        stats = calc_stats(selected)
        quality = candidate_objective(stats, base, 0.0)
        options.append({"cutoff": cutoff, "stats": stats, "quality": quality})
    if not options:
        cutoff = sorted([int(r["new_score"]) for r in validation_scored])[max(0, int(len(validation_scored) * 0.90) - 1)]
        selected = [r for r in validation_scored if int(r["new_score"]) >= cutoff]
        return cutoff, calc_stats(selected), []
    options.sort(key=lambda x: x["quality"], reverse=True)
    best = options[0]
    return int(best["cutoff"]), best["stats"], options[:10]


def bucket_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = [(90, 100), (80, 89), (70, 79), (60, 69), (50, 59), (0, 49)]
    result = []
    for low, high in buckets:
        selected = [r for r in rows if low <= int(r.get("new_score", 0)) <= high]
        stats = calc_stats(selected)
        result.append({"bucket": f"{low}-{high}", **stats.to_json()})
    return result


def top_decile_stats(rows: list[dict[str, Any]]) -> tuple[int, Stats]:
    if not rows:
        return 100, Stats()
    scores = sorted(int(r.get("new_score", 0)) for r in rows)
    cutoff = scores[max(0, int(len(scores) * 0.90) - 1)]
    return cutoff, calc_stats([r for r in rows if int(r.get("new_score", 0)) >= cutoff])


def current_logic_stats(rows: list[dict[str, Any]], logic_path: Path) -> dict[str, Any]:
    if not logic_path.exists():
        return {"available": False, "reason": "current_logic.json not found"}
    try:
        logic = json.loads(logic_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "reason": f"current_logic.json read error: {exc}"}

    method = logic.get("method")
    conditions = logic.get("conditions") or []
    thresholds = logic.get("thresholds") or {}
    selected = []
    for row in rows:
        score = score_current_logic(row, method, conditions, thresholds)
        if score >= 6:
            selected.append(row)
    return {
        "available": True,
        "method": method,
        "conditions": conditions,
        "thresholds": thresholds,
        "star6": calc_stats(selected).to_json(),
    }


def score_current_logic(
    row: dict[str, Any],
    method: Any,
    conditions: list[Any],
    thresholds: dict[str, Any],
) -> int:
    if method == "B":
        score = 0
        for entry in conditions:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            cond, weight = entry[0], int(entry[1])
            if current_condition(row, cond, thresholds):
                score += weight
        return min(score, 6)

    score = 0
    for cond in conditions:
        if current_condition(row, str(cond), thresholds):
            score += 1
    return score


def current_condition(row: dict[str, Any], cond: str, thresholds: dict[str, Any]) -> bool:
    if cond in thresholds:
        th = float(thresholds[cond])
        if cond.startswith("vol"):
            return is_finite(row.get("vol_ratio_20")) and float(row["vol_ratio_20"]) >= th
        if cond in {"sbull", "body1"}:
            return is_finite(row.get("body_pct")) and float(row["body_pct"]) >= th / 100.0
        if cond.startswith("atr"):
            return is_finite(row.get("atr14_pct")) and float(row["atr14_pct"]) < th / 100.0
        if cond.startswith("stoch"):
            return is_finite(row.get("stoch14")) and float(row["stoch14"]) >= th
        if cond == "bb80":
            return is_finite(row.get("bb_pct")) and float(row["bb_pct"]) >= th
    return bool(row.get(cond))


def holdout_recommendation(holdout_stats: Stats, holdout_base: Stats) -> tuple[str, list[str]]:
    reasons = []
    min_n = max(5, int(max(1, holdout_base.n) * 0.03))
    if holdout_stats.n < min_n:
        reasons.append(f"holdout sample {holdout_stats.n} < minimum {min_n}")
    if holdout_stats.win_rate < holdout_base.win_rate:
        reasons.append(
            f"holdout win rate {pct(holdout_stats.win_rate)} below baseline {pct(holdout_base.win_rate)}"
        )
    if holdout_stats.avg < holdout_base.avg:
        reasons.append(f"holdout average {pct(holdout_stats.avg)} below baseline {pct(holdout_base.avg)}")
    if holdout_stats.lose10_rate > holdout_base.lose10_rate * 1.25 and holdout_stats.lose10_rate > 0.05:
        reasons.append(
            f"holdout -10% rate {pct(holdout_stats.lose10_rate)} materially worse than baseline {pct(holdout_base.lose10_rate)}"
        )
    if reasons:
        return "no robust candidate", reasons
    return "candidate is robust enough for deeper paper testing", ["holdout quality gates passed"]


def fetch_sheet_values(spreadsheet_id: str, credentials_path: Path, sheet_name: str) -> list[list[Any]]:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("google-api-python-client and google-auth are required to fetch Sheets data") from exc

    creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
        .execute()
    )
    return response.get("values", [])


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    credentials_path = Path(args.credentials).expanduser().resolve()
    if not credentials_path.exists():
        raise FileNotFoundError(f"credentials file not found: {credentials_path}")

    alerts_rows = fetch_sheet_values(args.spreadsheet_id, credentials_path, ALERTS_SHEET)
    ohlcv_rows = fetch_sheet_values(args.spreadsheet_id, credentials_path, OHLCV_SHEET)
    alerts = parse_alerts(alerts_rows, args.objective)
    ohlcv = parse_ohlcv(ohlcv_rows)
    dataset, skipped = build_dataset(alerts, ohlcv)
    if len(dataset) < 80:
        raise RuntimeError(f"not enough feature-complete rows: {len(dataset)}")

    train, validation, holdout = split_chronological(dataset)
    candidates = generate_candidates(train)
    selected = select_predicates(train, validation, candidates)
    if not selected:
        raise RuntimeError("no positive validation predicates were selected")

    train_scored = add_scores(train, selected)
    valid_scored = add_scores(validation, selected)
    holdout_scored = add_scores(holdout, selected)
    all_scored = add_scores(dataset, selected)
    cutoff, cutoff_valid_stats, cutoff_options = choose_cutoff(valid_scored)

    holdout_selected = [r for r in holdout_scored if int(r["new_score"]) >= cutoff]
    all_selected = [r for r in all_scored if int(r["new_score"]) >= cutoff]
    holdout_stats = calc_stats(holdout_selected)
    all_selected_stats = calc_stats(all_selected)
    holdout_base = calc_stats(holdout)
    recommendation, reasons = holdout_recommendation(holdout_stats, holdout_base)
    top_cutoff, top_stats = top_decile_stats(all_scored)

    repo_root = Path(args.repo_root).resolve()
    current_stats = current_logic_stats(all_scored, repo_root / "current_logic.json")

    result = {
        "objective": args.objective,
        "spreadsheet_id": args.spreadsheet_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "alerts_with_objective": len(alerts),
            "feature_complete": len(dataset),
            "skipped_no_features": skipped,
            "train": len(train),
            "validation": len(validation),
            "holdout": len(holdout),
        },
        "baseline": {
            "train": calc_stats(train).to_json(),
            "validation": calc_stats(validation).to_json(),
            "holdout": holdout_base.to_json(),
            "all": calc_stats(dataset).to_json(),
        },
        "score": {
            "scale": "0-100",
            "cutoff": cutoff,
            "validation_at_cutoff": cutoff_valid_stats.to_json(),
            "holdout_at_cutoff": holdout_stats.to_json(),
            "all_at_cutoff": all_selected_stats.to_json(),
            "top_decile_cutoff_all": top_cutoff,
            "top_decile_all": top_stats.to_json(),
            "buckets_all": bucket_stats(all_scored),
            "cutoff_options_validation": [
                {
                    "cutoff": int(option["cutoff"]),
                    "quality": round(float(option["quality"]), 4),
                    "stats": option["stats"].to_json(),
                }
                for option in cutoff_options
            ],
        },
        "conditions": [
            step.predicate.to_json(step.weight, step.validation_stats) for step in selected
        ],
        "current_logic_reference": current_stats,
        "recommendation": {
            "status": recommendation,
            "reasons": reasons,
        },
    }

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "new_scoring_logic.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "latest_score_report.md").write_text(render_report(result), encoding="utf-8")
    return result


def render_stats_row(name: str, stats: dict[str, Any]) -> str:
    return (
        f"| {name} | {stats.get('n', 0)} | {pct(float(stats.get('win_rate', 0)))} | "
        f"{pct(float(stats.get('avg', 0)))} | {pct(float(stats.get('median', 0)))} | "
        f"{pct(float(stats.get('win10_rate', 0)))} | {pct(float(stats.get('lose10_rate', 0)))} |"
    )


def render_report(result: dict[str, Any]) -> str:
    score = result["score"]
    rec = result["recommendation"]
    lines = [
        "# Experimental 5BD Scoring Logic Report",
        "",
        f"- Generated: `{result['generated_at']}`",
        f"- Objective: `{result['objective']}`",
        f"- Feature-complete rows: `{result['data']['feature_complete']}` "
        f"(skipped no-features: `{result['data']['skipped_no_features']}`)",
        f"- Split: train `{result['data']['train']}`, validation `{result['data']['validation']}`, holdout `{result['data']['holdout']}`",
        f"- Selected cutoff: `score >= {score['cutoff']}`",
        f"- Recommendation: **{rec['status']}**",
        "",
        "## Selected Conditions",
        "",
        "| # | Weight | Condition | Validation n | Validation win | Validation avg |",
        "|---:|---:|---|---:|---:|---:|",
    ]
    for i, cond in enumerate(result["conditions"], 1):
        stats = cond.get("validation_stats", {})
        lines.append(
            f"| {i} | {cond['weight']} | {cond['description']} | "
            f"{stats.get('n', 0)} | {pct(float(stats.get('win_rate', 0)))} | {pct(float(stats.get('avg', 0)))} |"
        )

    lines += [
        "",
        "## Performance",
        "",
        "| Slice | n | Win rate | Avg | Median | +10% | -10% |",
        "|---|---:|---:|---:|---:|---:|---:|",
        render_stats_row("Baseline train", result["baseline"]["train"]),
        render_stats_row("Baseline validation", result["baseline"]["validation"]),
        render_stats_row("Baseline holdout", result["baseline"]["holdout"]),
        render_stats_row("New validation cutoff", score["validation_at_cutoff"]),
        render_stats_row("New holdout cutoff", score["holdout_at_cutoff"]),
        render_stats_row("New all cutoff", score["all_at_cutoff"]),
        render_stats_row("New all top decile", score["top_decile_all"]),
    ]

    current = result.get("current_logic_reference", {})
    if current.get("available"):
        lines.append(render_stats_row("Current logic star6 all", current["star6"]))

    lines += [
        "",
        "## Score Buckets (All Data)",
        "",
        "| Score bucket | n | Win rate | Avg | Median | +10% | -10% |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in score["buckets_all"]:
        lines.append(render_stats_row(bucket["bucket"], bucket))

    lines += [
        "",
        "## Recommendation Notes",
        "",
    ]
    for reason in rec["reasons"]:
        lines.append(f"- {reason}")

    lines += [
        "",
        "This is a paper-test artifact only. It does not update production scoring, pending logic, Discord behavior, or deployment files.",
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_credentials = os.environ.get("GOOGLE_CREDENTIALS_PATH", str(repo_root / "credentials.json"))
    parser = argparse.ArgumentParser(description="Build an experimental interpretable 5BD scoring logic.")
    parser.add_argument("--objective", default="perf_5bd", choices=["perf_5bd"])
    parser.add_argument("--spreadsheet-id", default=SPREADSHEET_ID)
    parser.add_argument("--credentials", default=default_credentials)
    parser.add_argument("--output", default=str(repo_root / "experiments"))
    parser.add_argument("--repo-root", default=str(repo_root))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_experiment(args)
    rec = result["recommendation"]
    print(f"feature_complete={result['data']['feature_complete']}")
    print(f"conditions={len(result['conditions'])}")
    print(f"cutoff={result['score']['cutoff']}")
    print(f"recommendation={rec['status']}")
    print("wrote experiments/new_scoring_logic.json")
    print("wrote experiments/latest_score_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
