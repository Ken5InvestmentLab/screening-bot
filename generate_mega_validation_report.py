#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a validation report for mega-return candidate scoring ideas.

This script is intentionally read-only against the production bot. It fetches
the same Google Sheets data used by the optimizer, evaluates fixed candidate
condition sets, and writes human-review reports.
"""

from __future__ import annotations

import argparse
from html import escape
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import optimize_screener as opt


JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MARKDOWN_OUTPUT = os.path.join("reports", "mega_validation_report_latest.md")
DEFAULT_HTML_OUTPUT = os.path.join("reports", "mega_validation_report_latest.html")
CURRENT_LOGIC_PATH = os.path.join(BASE_DIR, "current_logic.json")
SNIPER_LOGIC_PATH = os.path.join(BASE_DIR, "current_logic_sniper.json")
MEGA_LOGIC_PATH = os.path.join(BASE_DIR, "current_logic_mega.json")
REPORT_TITLE = "天底極致 スコアリングBot レポート"
PREMIUM_LOG_SPREADSHEET_ID_DEFAULT = "1GeLT-DUEdsYzT6AR3n1MkhkCeivqgtsMEXMhYfnHm9s"
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_MESSAGE_URL_RE = re.compile(
    r"^https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/channels/([^/]+)/([^/]+)/([^/?#]+)"
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

CONDITION_LABELS = {
    "ema75": "close > EMA75",
    "ema25": "close > EMA25",
    "vol20": "出来高 >= 20日平均x2.0",
    "vol15": "出来高 >= 20日平均x1.5",
    "vol12": "出来高 >= 20日平均x1.2",
    "vol30": "出来高 >= 20日平均x3.0",
    "sbull": "陽線実体 >= 0.5%",
    "body1": "陽線実体 >= 1.0%",
    "body2": "陽線実体 >= 2.0%",
    "macdgc": "MACD GC 3日以内",
    "macdpos": "MACD hist > 0",
    "atr5": "ATR < 5%",
    "atr3": "ATR < 3%",
    "atr7": "ATR < 7%",
    "hb20": "20日高値更新",
    "lower_wick50": "下ヒゲ優位",
    "pre_decline15": "20日高値から-15%以上",
    "stoch75": "Stoch >= 75",
    "stoch60": "Stoch >= 60",
    "rsi5070": "RSI 50-70",
    "rsi4060": "RSI 40-60",
    "bb80": "BB位置 >= 80%",
    "ich_tk": "一目: 転換線 > 基準線",
    "ich_price_tenkan": "一目: close > 転換線",
    "ich_price_kijun": "一目: close > 基準線",
    "ich_cloud_above": "一目: close > 雲上限",
    "ich_cloud_green": "一目: 先行雲が陽転",
    "ich_chikou": "一目: close > 26日前終値",
    "ich_kumo_break": "一目: 雲上抜け",
    "rci9_os": "RCI9 <= -50",
    "rci26_os": "RCI26 <= -50",
    "rci9_up": "RCI9反転上向き",
    "pre_down3": "直近3日連続下落後",
    "gap_up": "ギャップアップ",
    "bb_lower": "BB位置 <= 20%",
    "cci_os": "CCI <= -100",
    "smbull_seq2": "2連小陽線後",
    "smbull_seq3": "3連小陽線後",
}


def load_logic_conditions(path: str, fallback: list[str]) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        conditions = payload.get("conditions")
        if isinstance(conditions, list) and conditions:
            return [str(cond) for cond in conditions]
    except (OSError, json.JSONDecodeError):
        pass
    return fallback


def load_mega_logic_conditions(mode_id: str, fallback: list[str]) -> list[str]:
    try:
        with open(MEGA_LOGIC_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        mode = payload.get("modes", {}).get(mode_id, {})
        conditions = mode.get("conditions")
        if isinstance(conditions, list) and conditions:
            return [str(cond) for cond in conditions]
    except (OSError, AttributeError, json.JSONDecodeError):
        pass
    return fallback


_LOCAL_ENV_CACHE: dict[str, str] | None = None


def local_env() -> dict[str, str]:
    global _LOCAL_ENV_CACHE
    if _LOCAL_ENV_CACHE is not None:
        return _LOCAL_ENV_CACHE
    values: dict[str, str] = {}
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
    _LOCAL_ENV_CACHE = values
    return values


def config_value(names: list[str], default: str = "") -> str:
    env_values = local_env()
    for name in names:
        value = os.environ.get(name) or env_values.get(name)
        if value:
            return str(value).strip()
    return default


STABLE_CONDITIONS = load_logic_conditions(
    CURRENT_LOGIC_PATH,
    ["ema25", "macdpos", "stoch75", "bb80", "pre_down3", "gap_up"],
)
SNIPER_CONDITIONS = load_logic_conditions(
    SNIPER_LOGIC_PATH,
    ["ema25", "sbull", "atr5", "atr7", "hb20", "rsi4060"],
)

CANDIDATES = [
    {
        "id": "stable_s6",
        "label": "Stable ★6",
        "eval_days": 5,
        "target": 0.10,
        "target_label": "+10%",
        "conditions": STABLE_CONDITIONS,
        "intent": "現行Stableロジックの6条件すべてを満たす満点候補。",
    },
    {
        "id": "sniper",
        "label": "Sniper 勝率重視",
        "eval_days": 5,
        "target": 0.0,
        "target_label": "勝ち",
        "conditions": SNIPER_CONDITIONS,
        "intent": "現行Sniperロジックの全条件通過候補。勝率重視で確認する。",
    },
    {
        "id": "mega5_rebound",
        "label": "Mega5 短期リバウンド",
        "eval_days": 5,
        "target": 0.20,
        "target_label": "+20%",
        "conditions": load_mega_logic_conditions(
            "mega5_rebound",
            ["rci9_os", "pre_down3", "body2"],
        ),
        "intent": "売られすぎから強い陽線で反転した短期急騰候補。",
    },
    {
        "id": "mega40_deep_reversal",
        "label": "Mega40 深押し反転",
        "eval_days": 40,
        "target": 0.30,
        "target_label": "+30%",
        "conditions": load_mega_logic_conditions(
            "mega40_deep_reversal",
            ["pre_decline15", "pre_down3", "bb_lower", "body2"],
        ),
        "intent": "深い押し目から強陽線で切り返す40営業日候補。",
    },
    {
        "id": "mega40_wick_recovery",
        "label": "Mega40 下ヒゲ回復",
        "eval_days": 40,
        "target": 0.50,
        "target_label": "+50%",
        "conditions": load_mega_logic_conditions(
            "mega40_wick_recovery",
            ["pre_decline15", "cci_os", "lower_wick50", "ich_chikou"],
        ),
        "intent": "深い調整後の下ヒゲ・遅行線回復を使う少数精鋭候補。",
    },
]

PAID_MODE_IDS = {"mega5_rebound", "mega40_deep_reversal", "mega40_wick_recovery"}
FREE_CONFIRMED_LIMIT = 10
MODE_CONFIRMED_PAGE_SIZE = 10
FREE_REPORT_SUFFIX = "_free"
PURCHASE_PATH = "/purchase"


def is_paid_mode(candidate: dict) -> bool:
    return candidate.get("id") in PAID_MODE_IDS

LIFT_TARGETS = [
    (5, 0.20),
    (10, 0.20),
    (10, 0.30),
    (20, 0.30),
    (20, 0.50),
    (40, 0.30),
    (40, 0.50),
]


def is_finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def pct(value, signed: bool = True) -> str:
    if not is_finite(value):
        return "--"
    prefix = "+" if signed else ""
    return f"{float(value) * 100:{prefix}.1f}%"


def num(value) -> str:
    if not is_finite(value):
        return "--"
    return f"{float(value):.2f}"


def yen(value) -> str:
    if not is_finite(value):
        return "--"
    price = float(value)
    if abs(price - round(price)) < 0.05:
        return f"{price:,.0f}円"
    return f"{price:,.1f}円"


def target_label(candidate: dict) -> str:
    return candidate.get("target_label") or pct(candidate["target"], signed=False)


def horizon_label(days: int) -> str:
    return f"{days}営業日後"


def md(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ").strip()


def normalize_date(value) -> str:
    return str(value or "").replace("/", "-")[:10]


def parse_date(value):
    return pd.to_datetime(normalize_date(value), errors="coerce")


def parse_discord_message_url(value: str) -> tuple[str, str, str] | None:
    match = DISCORD_MESSAGE_URL_RE.match(str(value or "").strip())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def extract_markdown_url(value: str) -> str:
    text = str(value or "").strip()
    match = MARKDOWN_LINK_RE.search(text)
    if match:
        return match.group(2).strip()
    if parse_discord_message_url(text):
        return text
    return ""


def fetch_premium_discord_links(service) -> dict:
    spreadsheet_id = config_value(
        ["PREMIUM_LOG_SPREADSHEET_ID", "PREMIUM_SPREADSHEET_ID"],
        PREMIUM_LOG_SPREADSHEET_ID_DEFAULT,
    )
    sheet_name = config_value(["PREMIUM_LOG_SHEET_NAME", "PREMIUM_SHEET_NAME"], "premium_alert_log")
    result = {"by_alert_id": {}, "row_count": 0, "matched_urls": 0}
    if not spreadsheet_id:
        return result

    try:
        response = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:K")
            .execute()
        )
    except Exception as err:
        print(f"premium log read skipped: {err}")
        return result

    rows = response.get("values", [])
    if len(rows) < 2:
        return result
    header = [str(cell).lower().strip() for cell in rows[0]]

    def col(name: str, fallback: int | None = None) -> int:
        return header.index(name) if name in header else (fallback if fallback is not None else -1)

    columns = {
        "event_at": col("event_at", 0),
        "event_type": col("event_type", 1),
        "alert_id": col("alert_id", 2),
        "signal_type": col("signal_type", 5),
        "reason": col("reason", 10),
    }

    def cell(row: list[str], name: str) -> str:
        index = columns[name]
        return str(row[index]).strip() if 0 <= index < len(row) else ""

    def newer(item: dict, existing: dict | None) -> bool:
        if not existing:
            return True
        return item.get("event_at", "") >= existing.get("event_at", "")

    for row in rows[1:]:
        if not row:
            continue
        result["row_count"] += 1
        if cell(row, "event_type").upper() != "POSTED":
            continue
        if cell(row, "signal_type").upper() not in ("", "BOTTOM"):
            continue
        url = extract_markdown_url(cell(row, "reason"))
        if not url or not parse_discord_message_url(url):
            continue

        alert_id = cell(row, "alert_id")
        item = {
            "alert_id": alert_id,
            "url": url,
            "event_at": cell(row, "event_at"),
        }
        result["matched_urls"] += 1
        if alert_id and newer(item, result["by_alert_id"].get(alert_id)):
            result["by_alert_id"][alert_id] = item
    return result


def discord_api_token() -> str:
    return config_value(["DISCORD_PREMIUM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_TOKEN"], "")


def fetch_discord_message(url: str, token: str) -> dict | None:
    parsed = parse_discord_message_url(url)
    if not parsed or not token:
        return None
    _, channel_id, message_id = parsed
    endpoint = f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "screening-bot-mega-report",
        },
    )
    for _ in range(2):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return simplify_discord_message(payload, url)
        except urllib.error.HTTPError as err:
            if err.code == 429:
                try:
                    body = json.loads(err.read().decode("utf-8"))
                    time.sleep(min(float(body.get("retry_after", 1.0)), 3.0))
                    continue
                except Exception:
                    time.sleep(1.0)
                    continue
            return None
        except Exception:
            return None
    return None


def simplify_discord_message(payload: dict, jump_url: str) -> dict:
    embeds = []
    for embed in payload.get("embeds") or []:
        fields = []
        for field in embed.get("fields") or []:
            fields.append(
                {
                    "name": str(field.get("name") or ""),
                    "value": str(field.get("value") or ""),
                }
            )
        footer = embed.get("footer") or {}
        embeds.append(
            {
                "title": str(embed.get("title") or ""),
                "url": str(embed.get("url") or ""),
                "description": str(embed.get("description") or ""),
                "fields": fields,
                "footer": str(footer.get("text") or ""),
                "timestamp": str(embed.get("timestamp") or payload.get("timestamp") or ""),
            }
        )
    return {
        "content": str(payload.get("content") or ""),
        "embeds": embeds,
        "jump_url": jump_url,
    }


def fetch_discord_messages(urls: list[str]) -> dict[str, dict]:
    enabled = config_value(["MEGA_REPORT_FETCH_DISCORD_MESSAGES"], "").lower() in ("1", "true", "yes", "on")
    if not enabled:
        return {}
    token = discord_api_token()
    if not token:
        return {}
    messages = {}
    for url in sorted(set(urls)):
        message = fetch_discord_message(url, token)
        if message:
            messages[url] = message
    return messages


def premium_link_for_row(row: pd.Series, premium_links: dict) -> str:
    alert_id = str(row.get("alert_id", "") or "").strip()
    item = premium_links.get("by_alert_id", {}).get(alert_id) if alert_id else None
    return str(item.get("url") or "") if item else ""


def attach_fundamental_links(
    frame: pd.DataFrame,
    premium_links: dict,
    discord_messages: dict[str, dict],
) -> pd.DataFrame:
    frame = frame.copy()
    urls = []
    html_blocks = []
    for _, row in frame.iterrows():
        url = premium_link_for_row(row, premium_links)
        urls.append(url)
        html_blocks.append(discord_message_html(discord_messages.get(url)) if url else "")
    frame["fundamental_url"] = urls
    frame["fundamental_html"] = html_blocks
    return frame


def collect_premium_urls(frame: pd.DataFrame, premium_links: dict) -> list[str]:
    urls = []
    for _, row in frame.iterrows():
        url = premium_link_for_row(row, premium_links)
        if url:
            urls.append(url)
    return urls


def business_days_elapsed_for_signal(daily: list[dict], sig_date: str) -> int:
    if not daily:
        return -1
    sig_dt = str(sig_date or "").replace("/", "-")[:10]
    if not sig_dt or daily[-1].get("date", "") < sig_dt:
        return -1
    return sum(1 for bar in daily if sig_dt < str(bar.get("date", ""))[:10])


def close_after_business_days(daily: list[dict], sig_date: str, days: int) -> float:
    if not daily or days <= 0:
        return np.nan
    sig_dt = str(sig_date or "").replace("/", "-")[:10]
    if not sig_dt:
        return np.nan
    future_bars = [bar for bar in daily if sig_dt < str(bar.get("date", ""))[:10]]
    if len(future_bars) < days:
        return np.nan
    close = future_bars[days - 1].get("close", np.nan)
    return float(close) if is_finite(close) else np.nan


def build_alert_frame(include_unconfirmed: bool) -> tuple[pd.DataFrame, dict, dict]:
    svc = opt.get_service()
    alerts_raw_rows = opt.fetch(svc, "alerts_raw")
    archive_rows = opt.fetch(svc, "signals_archive")
    ohlcv_rows = opt.fetch(svc, "ohlcv_4h")

    alerts_raw = opt.parse_alerts(alerts_raw_rows, include_unconfirmed=include_unconfirmed)
    alerts_raw["_from_archive"] = False
    archive = opt.parse_alerts(archive_rows, include_unconfirmed=include_unconfirmed)
    archive["_from_archive"] = True
    alerts = pd.concat([alerts_raw, archive], ignore_index=True)

    if "alert_id" in alerts.columns and not alerts.empty:
        has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat(
            [
                alerts[has_id].drop_duplicates(subset=["alert_id"], keep="first"),
                alerts[~has_id],
            ],
            ignore_index=True,
        )

    ohlcv = opt.parse_ohlcv(ohlcv_rows)
    today = pd.Timestamp(datetime.now(JST).date())
    records = []

    for _, alert in alerts.iterrows():
        daily = ohlcv.get(alert["symbol"], [])
        features = opt.get_features(daily, alert["date"])
        if not features:
            continue

        rec = {**alert.to_dict(), **features}
        latest_close = opt.latest_close_for_signal(daily, alert["date"])
        entry = alert.get("entry", float("nan"))
        rec["latest_close"] = latest_close if is_finite(latest_close) else np.nan
        for days in (5, 10, 20, 40):
            rec[f"price_{days}bd"] = close_after_business_days(daily, alert["date"], days)
        rec["cur_perf"] = (
            latest_close / entry - 1
            if is_finite(latest_close) and is_finite(entry) and float(entry) > 0
            else np.nan
        )
        signal_dt = parse_date(alert["date"])
        rec["signal_dt"] = signal_dt
        rec["days_elapsed"] = int((today - signal_dt).days) if pd.notna(signal_dt) else -1
        rec["business_days_elapsed"] = business_days_elapsed_for_signal(daily, alert["date"])
        records.append(rec)

    frame = pd.DataFrame(records)
    for cond in opt.BOOL_CONDS:
        if cond in frame.columns:
            frame[cond] = frame[cond].astype(bool)

    meta = {
        "alerts_raw_rows": len(alerts_raw_rows),
        "signals_archive_rows": len(archive_rows),
        "ohlcv_rows": len(ohlcv_rows),
        "alerts_after_dedupe": len(alerts),
        "feature_rows": len(frame),
    }
    return frame, ohlcv, meta


def condition_mask(frame: pd.DataFrame, conditions: list[str]) -> pd.Series:
    if frame.empty:
        return pd.Series([], dtype=bool, index=frame.index)
    mask = pd.Series(True, index=frame.index)
    for cond in conditions:
        if cond not in frame.columns:
            return pd.Series(False, index=frame.index)
        mask &= frame[cond].astype(bool)
    return mask


def horizon_frame(frame: pd.DataFrame, eval_days: int) -> pd.DataFrame:
    col = f"perf_{eval_days}bd"
    if col not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame[col].apply(is_finite)].copy()


def win_rate_excluding_ties(perf: pd.Series) -> float:
    values = pd.to_numeric(perf, errors="coerce")
    values = values[np.isfinite(values)]
    decisive = values[values != 0]
    if decisive.empty:
        return np.nan
    return float((decisive > 0).mean())


def recent_calendar_day_frame(frame: pd.DataFrame, calendar_days: int) -> pd.DataFrame:
    if frame.empty or "signal_dt" not in frame.columns:
        return frame.copy()
    today = pd.Timestamp(datetime.now(JST).date())
    cutoff = today - pd.Timedelta(days=max(int(calendar_days), 1) - 1)
    signal_dt = pd.to_datetime(frame["signal_dt"], errors="coerce")
    return frame[signal_dt >= cutoff].copy()


def horizon_summary(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for days in sorted({int(candidate["eval_days"]) for candidate in CANDIDATES}):
        col = f"perf_{days}bd"
        subset = horizon_frame(frame, days)
        perf = subset[col].astype(float) if not subset.empty else pd.Series(dtype=float)
        rows.append(
            {
                "days": days,
                "n": len(subset),
                "avg": perf.mean() if len(perf) else np.nan,
                "win": win_rate_excluding_ties(perf) if len(perf) else np.nan,
                "p10": int((perf >= 0.10).sum()) if len(perf) else 0,
                "p20": int((perf >= 0.20).sum()) if len(perf) else 0,
                "p30": int((perf >= 0.30).sum()) if len(perf) else 0,
                "p50": int((perf >= 0.50).sum()) if len(perf) else 0,
                "p100": int((perf >= 1.00).sum()) if len(perf) else 0,
            }
        )
    return rows


def candidate_stats(frame: pd.DataFrame, candidate: dict) -> dict:
    days = candidate["eval_days"]
    target = candidate["target"]
    perf_col = f"perf_{days}bd"
    subset = horizon_frame(frame, days)
    mask = condition_mask(subset, candidate["conditions"])
    hits = subset[mask].copy()

    total_target = int((subset[perf_col].astype(float) >= target).sum()) if not subset.empty else 0
    base_rate = total_target / len(subset) if len(subset) else 0.0
    if hits.empty:
        return {
            "n": 0,
            "avg": np.nan,
            "median": np.nan,
            "win_rate": np.nan,
            "target_hits": 0,
            "target_rate": 0.0,
            "recall": 0.0,
            "lift": 0.0,
            "p20": 0,
            "p30": 0,
            "p50": 0,
            "p100": 0,
            "m10": 0,
            "max": np.nan,
            "min": np.nan,
            "base_target_rate": base_rate,
        }

    perf = hits[perf_col].astype(float)
    target_hits = int((perf >= target).sum())
    target_rate = target_hits / len(hits)
    return {
        "n": len(hits),
        "avg": float(perf.mean()),
        "median": float(perf.median()),
        "win_rate": win_rate_excluding_ties(perf),
        "target_hits": target_hits,
        "target_rate": target_rate,
        "recall": target_hits / total_target if total_target else 0.0,
        "lift": target_rate / base_rate if base_rate else 0.0,
        "p20": int((perf >= 0.20).sum()),
        "p30": int((perf >= 0.30).sum()),
        "p50": int((perf >= 0.50).sum()),
        "p100": int((perf >= 1.00).sum()),
        "m10": int((perf <= -0.10).sum()),
        "max": float(perf.max()),
        "min": float(perf.min()),
        "base_target_rate": base_rate,
    }


def current_watch_stats(frame: pd.DataFrame, candidate: dict) -> dict:
    days = candidate["eval_days"]
    perf_col = f"perf_{days}bd"
    if perf_col not in frame.columns:
        return {
            "n": 0,
            "with_current": 0,
            "avg": np.nan,
            "median": np.nan,
            "win_rate": np.nan,
            "p10": 0,
            "p20": 0,
            "p50": 0,
            "p100": 0,
            "m10": 0,
            "max": np.nan,
            "min": np.nan,
        }

    mask = condition_mask(frame, candidate["conditions"])
    watch = frame[mask & ~frame[perf_col].apply(is_finite)].copy()
    current = watch[watch["cur_perf"].apply(is_finite)] if "cur_perf" in watch.columns else watch.iloc[0:0]

    if current.empty:
        return {
            "n": len(watch),
            "with_current": 0,
            "avg": np.nan,
            "median": np.nan,
            "win_rate": np.nan,
            "p10": 0,
            "p20": 0,
            "p50": 0,
            "p100": 0,
            "m10": 0,
            "max": np.nan,
            "min": np.nan,
        }

    perf = current["cur_perf"].astype(float)
    return {
        "n": len(watch),
        "with_current": len(current),
        "avg": float(perf.mean()),
        "median": float(perf.median()),
        "win_rate": win_rate_excluding_ties(perf),
        "p10": int((perf >= 0.10).sum()),
        "p20": int((perf >= 0.20).sum()),
        "p50": int((perf >= 0.50).sum()),
        "p100": int((perf >= 1.00).sum()),
        "m10": int((perf <= -0.10).sum()),
        "max": float(perf.max()),
        "min": float(perf.min()),
    }


def compact_stats_text(stats: dict, include_target: bool = False) -> str:
    if stats["n"] == 0:
        return "該当なし"
    if "with_current" in stats and stats["with_current"] == 0:
        return f"n=0/{stats['n']} / 現在値なし"
    count_text = f"n={stats['n']}"
    if "with_current" in stats:
        count_text = f"n={stats['with_current']}"
    parts = [
        count_text,
        f"平均 {pct(stats['avg'])}",
        f"中央値 {pct(stats['median'])}",
        f"勝率 {pct(stats['win_rate'], signed=False)}",
        f"最大 {pct(stats['max'])}",
        f"最小 {pct(stats['min'])}",
        f"<=-10% {stats['m10']}",
    ]
    if include_target:
        parts.insert(4, f"目標Hit {stats['target_hits']}")
    else:
        parts.insert(4, f"+10% {stats['p10']}")
        parts.insert(5, f"+20% {stats['p20']}")
    return " / ".join(parts)


def compact_stats_html(stats: dict, include_target: bool = False) -> str:
    if stats["n"] == 0:
        return '<span class="muted">該当なし</span>'
    if "with_current" in stats and stats["with_current"] == 0:
        empty_count = "n=0"
        return (
            '<div class="stat-stack">'
            f"<span>{html_escape(empty_count)}</span>"
            '<span class="muted">現在値なし</span>'
            "</div>"
        )
    count_text = f"n={stats['n']}"
    if "with_current" in stats:
        count_text = f"n={stats['with_current']}"
    rows = [
        f"<span>{html_escape(count_text)}</span>",
        f"<span>平均 {pct_html(stats['avg'])}</span>",
        f"<span>中央値 {pct_html(stats['median'])}</span>",
        f"<span>勝率 {pct_html(stats['win_rate'], signed=False)}</span>",
        f"<span>最大 {pct_html(stats['max'])}</span>",
        f"<span>最小 {pct_html(stats['min'])}</span>",
        f"<span class=\"neg\">&lt;=-10% {stats['m10']}</span>",
    ]
    if include_target:
        rows.insert(4, f"<span>目標Hit {stats['target_hits']}</span>")
    else:
        rows.insert(4, f"<span>+10% {stats['p10']}</span>")
        rows.insert(5, f"<span>+20% {stats['p20']}</span>")
    return '<div class="stat-stack">' + "".join(rows) + "</div>"


def verdict(stats: dict) -> str:
    if stats["n"] < 5:
        return "保留: 件数不足"
    if is_finite(stats["median"]) and stats["median"] > 0 and stats["avg"] > 0:
        if stats["m10"] / max(stats["n"], 1) <= 0.25:
            return "継続監視"
        return "注意: 下振れ多め"
    if stats["avg"] > 0 and stats["max"] > 0.5:
        return "注意: 外れ値依存"
    return "保留: 優位性弱い"


def top_lift_conditions(frame: pd.DataFrame, days: int, target: float, limit: int = 8) -> list[dict]:
    perf_col = f"perf_{days}bd"
    subset = horizon_frame(frame, days)
    if subset.empty:
        return []
    perf = subset[perf_col].astype(float).to_numpy()
    target_mask = perf >= target
    target_total = int(target_mask.sum())
    base_rate = target_total / len(subset) if len(subset) else 0.0
    rows = []
    for cond in opt.BOOL_CONDS:
        if cond not in subset.columns:
            continue
        cond_mask = subset[cond].astype(bool).to_numpy()
        cond_n = int(cond_mask.sum())
        if cond_n == 0:
            continue
        cond_target = int((cond_mask & target_mask).sum())
        if cond_target == 0:
            continue
        precision = cond_target / cond_n
        rows.append(
            {
                "condition": cond,
                "lift": precision / base_rate if base_rate else 0.0,
                "precision": precision,
                "cover": cond_target / target_total if target_total else 0.0,
                "all_rate": cond_n / len(subset),
                "hits": cond_target,
                "n": cond_n,
            }
        )
    rows.sort(key=lambda item: (-item["lift"], -item["cover"], item["condition"]))
    return rows[:limit]


def candidate_rows(
    frame: pd.DataFrame,
    candidate: dict,
    confirmed: bool,
    limit: int | None,
) -> pd.DataFrame:
    days = candidate["eval_days"]
    perf_col = f"perf_{days}bd"
    if perf_col not in frame.columns:
        return frame.iloc[0:0].copy()
    mask = condition_mask(frame, candidate["conditions"])
    if confirmed:
        rows = frame[mask & frame[perf_col].apply(is_finite)].copy()
        rows = rows.sort_values(perf_col, ascending=False)
        return rows if limit is None else rows.head(limit)
    rows = frame[mask & ~frame[perf_col].apply(is_finite)].copy()
    if rows.empty:
        return rows
    rows = rows.sort_values(["signal_dt", "cur_perf"], ascending=[False, False])
    return rows if limit is None else rows.head(limit)


def conditions_text(conditions: list[str]) -> str:
    return " + ".join(f"`{cond}`" for cond in conditions)


def condition_labels_text(conditions: list[str]) -> str:
    return "<br>".join(f"`{cond}`: {CONDITION_LABELS.get(cond, cond)}" for cond in conditions)


def stats_table_rows(
    frame_confirmed: pd.DataFrame,
    frame_all: pd.DataFrame,
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    stats_by_id = {}
    watch_by_id = {}
    rows = []
    for candidate in CANDIDATES:
        stats = candidate_stats(frame_confirmed, candidate)
        watch_stats = current_watch_stats(frame_all, candidate)
        stats_by_id[candidate["id"]] = stats
        watch_by_id[candidate["id"]] = watch_stats
        rows.append(
            {
                "label": candidate["label"],
                "days": candidate["eval_days"],
                "target": target_label(candidate),
                "conditions": conditions_text(candidate["conditions"]),
                "n": stats["n"],
                "avg": pct(stats["avg"]),
                "median": pct(stats["median"]),
                "win": pct(stats["win_rate"], signed=False),
                "target_hits": f"{stats['target_hits']} ({pct(stats['target_rate'], signed=False)})",
                "recall": pct(stats["recall"], signed=False),
                "lift": num(stats["lift"]),
                "tail": f"+50% {stats['p50']} / +100% {stats['p100']} / <=-10% {stats['m10']}",
                "confirmed_perf": compact_stats_text(stats, include_target=True),
                "watch_perf": compact_stats_text(watch_stats),
                "verdict": verdict(stats),
            }
        )
    return rows, stats_by_id, watch_by_id


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(md(cell) for cell in row) + " |")
    return lines


def signal_table(rows: pd.DataFrame, eval_days: int, confirmed: bool) -> list[str]:
    perf_col = f"perf_{eval_days}bd"
    if rows.empty:
        return ["該当なし"]

    if confirmed:
        headers = ["日付", "銘柄", "社名", "評価値", "5営業日後", "10営業日後", "20営業日後", "40営業日後", "操作"]
        table_rows = []
        for _, row in rows.iterrows():
            symbol = row.get("symbol", "")
            table_rows.append(
                [
                    row.get("date", ""),
                    symbol,
                    row.get("name", ""),
                    pct(row.get(perf_col)),
                    pct(row.get("perf_5bd")),
                    pct(row.get("perf_10bd")),
                    pct(row.get("perf_20bd")),
                    pct(row.get("perf_40bd")),
                    action_links_text(symbol, row),
                ]
            )
        return markdown_table(headers, table_rows)

    headers = ["日付", "銘柄", "社名", "経過営業日", "現在騰落", "5営業日後", "10営業日後", "20営業日後", "操作"]
    table_rows = []
    for _, row in rows.iterrows():
        symbol = row.get("symbol", "")
        table_rows.append(
            [
                row.get("date", ""),
                symbol,
                row.get("name", ""),
                elapsed_business_days_text(row),
                pct(row.get("cur_perf")),
                pct(row.get("perf_5bd")),
                pct(row.get("perf_10bd")),
                pct(row.get("perf_20bd")),
                action_links_text(symbol, row),
            ]
        )
    return markdown_table(headers, table_rows)


def html_escape(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def markdown_text_html(value: str) -> str:
    text = str(value or "")
    parts = []
    last = 0
    for match in MARKDOWN_LINK_RE.finditer(text):
        parts.append(html_escape(text[last : match.start()]))
        label = match.group(1).replace("\\]", "]").replace("\\\\", "\\")
        url = match.group(2)
        parts.append(
            f'<a href="{html_escape(url)}" target="_blank" rel="noopener noreferrer">'
            f"{html_escape(label)}</a>"
        )
        last = match.end()
    parts.append(html_escape(text[last:]))
    return "".join(parts).replace("\n", "<br>")


def discord_message_html(message: dict | None) -> str:
    if not message:
        return ""
    blocks = []
    content = str(message.get("content") or "").strip()
    if content:
        blocks.append(f'<p class="discord-content">{markdown_text_html(content)}</p>')
    for embed in message.get("embeds") or []:
        title = str(embed.get("title") or "").strip()
        title_url = str(embed.get("url") or "").strip()
        description = str(embed.get("description") or "").strip()
        fields = embed.get("fields") or []
        footer = str(embed.get("footer") or "").strip()
        timestamp = str(embed.get("timestamp") or "").strip()
        title_html = ""
        if title:
            if title_url:
                title_html = (
                    f'<h4><a href="{html_escape(title_url)}" target="_blank" '
                    f'rel="noopener noreferrer">{html_escape(title)}</a></h4>'
                )
            else:
                title_html = f"<h4>{html_escape(title)}</h4>"
        field_html = "".join(
            "<div>"
            f"<dt>{html_escape(field.get('name', ''))}</dt>"
            f"<dd>{markdown_text_html(field.get('value', ''))}</dd>"
            "</div>"
            for field in fields
        )
        meta = " / ".join(part for part in [footer, timestamp] if part)
        description_html = f"<p>{markdown_text_html(description)}</p>" if description else ""
        fields_html = f"<dl>{field_html}</dl>" if field_html else ""
        meta_html = f'<p class="discord-meta">{html_escape(meta)}</p>' if meta else ""
        blocks.append(
            '<article class="discord-embed">'
            f"{title_html}"
            f"{description_html}"
            f"{fields_html}"
            f"{meta_html}"
            "</article>"
        )
    if not blocks:
        return ""
    return '<div class="discord-message">' + "".join(blocks) + "</div>"


def clean_symbol_text(value) -> str:
    return str(value or "").replace("TYO:", "").replace("TSE:", "").strip()


def chart_url(symbol: str) -> str:
    return f"https://jp.tradingview.com/chart/?symbol=TSE:{html_escape(clean_symbol_text(symbol))}"


def action_buttons(symbol: str, row: pd.Series) -> str:
    clean = clean_symbol_text(symbol)
    fundamental_url = str(row.get("fundamental_url", "") or "").strip()
    fundamental_html = str(row.get("fundamental_html", "") or "").strip()
    if not clean:
        return '<span class="muted">--</span>'
    fundamental_button = (
        f'<a class="action-btn secondary" href="{html_escape(fundamental_url)}" '
        'target="_blank" rel="noopener noreferrer">ファンダ分析</a>'
        if fundamental_url
        else ""
    )
    fundamental_detail = (
        '<details class="fundamental-detail">'
        '<summary>ファンダ本文</summary>'
        f"{fundamental_html}"
        "</details>"
        if fundamental_html
        else ""
    )
    return (
        '<div class="action-buttons">'
        f"{fundamental_button}"
        f'<a class="action-btn" href="{chart_url(clean)}" target="_blank" rel="noopener noreferrer">チャート</a>'
        "</div>"
        f"{fundamental_detail}"
    )


def volatility_tag(row: pd.Series) -> tuple[str, str, str]:
    atr_pct = row.get("_atr", np.nan)
    if not is_finite(atr_pct):
        return "", "", ""
    atr = float(atr_pct)
    if atr < 3.0:
        return "low", "🟢LOW", "ATR 3%未満。値動きが比較的穏やかな銘柄です。"
    if atr < 6.0:
        return "mid", "🟡MID", "ATR 3%以上6%未満。標準的な変動幅の銘柄です。"
    return "high", "🔴HIGH", "ATR 6%以上。大きく動きやすく、上振れも下振れも大きくなりやすい銘柄です。"


def volatility_tag_html(row: pd.Series) -> str:
    tone, label, description = volatility_tag(row)
    if not label:
        return ""
    atr_pct = float(row.get("_atr"))
    tooltip = f"ATR%: {atr_pct:.1f}% / {description}"
    return (
        f'<span class="vol-tag vol-{tone}" tabindex="0" '
        f'title="{html_escape(tooltip)}" data-tooltip="{html_escape(tooltip)}">'
        f"{html_escape(label)}</span>"
    )


def symbol_with_actions_html(symbol: str, row: pd.Series) -> str:
    name = str(row.get("name", "") or "").strip()
    name_html = (
        '<span class="symbol-separator">/</span>'
        f'<span class="symbol-name">{html_escape(name)}</span>'
        if name
        else ""
    )
    volatility_html = volatility_tag_html(row)
    entry_html = (
        '<span class="symbol-price-meta">'
        '<span><span class="price-label">Entry</span>'
        f'<span class="price-value">{html_escape(yen(row.get("entry")))}</span></span>'
        "</span>"
        if is_finite(row.get("entry"))
        else ""
    )
    meta_html = (
        f'<div class="symbol-meta-row">{volatility_html}{entry_html}</div>'
        if volatility_html or entry_html
        else ""
    )
    return (
        '<div class="symbol-stack">'
        '<div class="symbol-identity">'
        f'<span class="symbol">{html_escape(symbol)}</span>{name_html}'
        "</div>"
        f"{meta_html}"
        f"{action_buttons(symbol, row)}"
        "</div>"
    )


def action_links_text(symbol: str, row: pd.Series) -> str:
    clean = clean_symbol_text(symbol)
    if not clean:
        return "--"
    fundamental_url = str(row.get("fundamental_url", "") or "").strip()
    parts = []
    if fundamental_url:
        parts.append(f"[ファンダ分析]({fundamental_url})")
    parts.append(f"[チャート]({chart_url(clean)})")
    return " / ".join(parts)


def row_condition_truthy(row: pd.Series, condition: str) -> bool:
    value = row.get(condition, False)
    try:
        return bool(value) and not bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def row_condition_count(row: pd.Series, conditions: list[str]) -> int:
    return sum(1 for condition in conditions if row_condition_truthy(row, condition))


def row_true_conditions(row: pd.Series) -> list[str]:
    return [condition for condition in opt.BOOL_CONDS if row_condition_truthy(row, condition)]


def stable_star_score(row: pd.Series) -> int:
    return row_condition_count(row, STABLE_CONDITIONS)


def star_score_badge(row: pd.Series) -> str:
    score = stable_star_score(row)
    tone = "high" if score >= 6 else "mid" if score >= 4 else "low"
    return (
        f'<span class="star-badge {tone}" '
        'title="Stable ★6の判定条件を何個満たしたか">'
        f"★{score}</span>"
    )


def row_matches_candidate(row: pd.Series, candidate: dict) -> bool:
    return all(row_condition_truthy(row, condition) for condition in candidate["conditions"])


def row_mode_matches(row: pd.Series) -> list[dict]:
    return [candidate for candidate in CANDIDATES if row_matches_candidate(row, candidate)]


def mode_match_badges(
    row: pd.Series,
    current_candidate_id: str | None = None,
    include_empty: bool = True,
    link: bool = False,
) -> str:
    matches = [
        candidate
        for candidate in row_mode_matches(row)
        if candidate["id"] != current_candidate_id
    ]
    if not matches:
        return '<span class="muted">なし</span>' if include_empty else ""

    badges = []
    for candidate in matches:
        label = html_escape(candidate["label"])
        if link:
            badges.append(
                f'<a class="mode-badge" href="{html_escape(mode_page_filename(candidate))}">{label}</a>'
            )
        else:
            badges.append(f'<span class="mode-badge">{label}</span>')
    return '<span class="mode-badges">' + "".join(badges) + "</span>"


def search_indicator_options_html() -> str:
    options = []
    for condition in opt.BOOL_CONDS:
        label = CONDITION_LABELS.get(condition, condition)
        options.append(
            '<label class="indicator-option">'
            f'<input type="checkbox" value="{html_escape(condition)}" data-indicator-filter>'
            f'<span><code>{html_escape(condition)}</code><small>{html_escape(label)}</small></span>'
            "</label>"
        )
    return "".join(options)


def search_mode_options_html() -> str:
    options = []
    for candidate in CANDIDATES:
        options.append(
            '<label class="indicator-option">'
            f'<input type="checkbox" value="{html_escape(candidate["id"])}" data-mode-filter>'
            f'<span><strong>{html_escape(candidate["label"])}</strong>'
            f'<small>{horizon_label(candidate["eval_days"])} / {html_escape(target_label(candidate))}</small></span>'
            "</label>"
        )
    return "".join(options)


def pct_html(value, signed: bool = True) -> str:
    text = pct(value, signed=signed)
    css_class = "muted"
    if is_finite(value):
        numeric = float(value)
        if numeric > 0:
            css_class = "pos"
        elif numeric < 0:
            css_class = "neg"
        else:
            css_class = "flat"
    return f'<span class="{css_class}">{html_escape(text)}</span>'


def perf_with_price_html(perf_value, price_value=None) -> str:
    perf_markup = pct_html(perf_value)
    if not is_finite(perf_value) or not is_finite(price_value):
        return perf_markup
    return (
        '<span class="perf-cell">'
        f"{perf_markup}"
        f'<small class="price-sub">{html_escape(yen(price_value))}</small>'
        "</span>"
    )


def elapsed_business_days_text(row: pd.Series) -> str:
    value = row.get("business_days_elapsed", row.get("days_elapsed", ""))
    try:
        days = int(value)
    except (TypeError, ValueError):
        return "--"
    if days < 0:
        return "--"
    return f"{days}営業日"


def verdict_class(value: str) -> str:
    if value.startswith(("有望", "継続監視")):
        return "good"
    if value.startswith("注意"):
        return "warn"
    return "hold"


def condition_chips(conditions: list[str]) -> str:
    chips = []
    for cond in conditions:
        label = CONDITION_LABELS.get(cond, cond)
        chips.append(
            f'<span class="chip" title="{html_escape(label)}">{html_escape(cond)}</span>'
        )
    return "".join(chips)


def anchor_id(candidate: dict, prefix: str = "") -> str:
    return f"{prefix}mode-{candidate['id']}"


def mode_page_filename(candidate: dict) -> str:
    return f"mega_validation_report_{candidate['id']}.html"


def free_report_filename(filename: str) -> str:
    if filename.endswith(f"{FREE_REPORT_SUFFIX}.html"):
        return filename
    return filename.replace(".html", f"{FREE_REPORT_SUFFIX}.html")


def free_mode_page_filename(candidate: dict) -> str:
    return free_report_filename(mode_page_filename(candidate))


def login_path(return_to: str = "/mega_validation_report_latest.html") -> str:
    return f"/auth/login?return_to={urllib.parse.quote(return_to, safe='/')}"


def paywall_cta_html(
    title: str,
    message: str,
    return_to: str = "/mega_validation_report_latest.html",
) -> str:
    return f"""
    <div class="paywall-panel">
      <div class="locked-preview" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
      </div>
      <div class="paywall-copy">
        <span class="premium-badge">有料会員限定</span>
        <h3>{html_escape(title)}</h3>
        <p>{html_escape(message)}</p>
        <div class="access-actions">
          <a class="access-btn primary" href="{PURCHASE_PATH}">アクセス権を購入する</a>
          <a class="access-btn secondary" href="{login_path(return_to)}">Discordでログイン</a>
        </div>
      </div>
    </div>
    """


def navigation_html(current_mode_id: str | None = None, include_mode_sections: bool = False) -> str:
    brand_active = "active" if current_mode_id is None else ""
    mode_links = "".join(
        f'<a class="{ "active" if candidate["id"] == current_mode_id else "" }" '
        f'href="{html_escape(mode_page_filename(candidate))}">{html_escape(candidate["label"])}</a>'
        for candidate in CANDIDATES
    )
    if include_mode_sections:
        section_links = """
        <a href="#summary">成績サマリー</a>
        <a href="#confirmed">確定済み銘柄一覧</a>
        <a href="#watch">未確定ウォッチリスト</a>
        <a href="#guide">使い方</a>
        """
    elif current_mode_id is None:
        section_links = """
        <a href="#performance-summary">全体成績</a>
        <a href="#mode-summary">モード別サマリー</a>
        <a href="#highlights">注目ポイント</a>
        <a href="#daily-detections">銘柄検索</a>
        <a href="#guide">使い方</a>
        """
    else:
        section_links = ""
    return f"""
    <nav class="top-nav" aria-label="ページメニュー">
      <a class="top-nav-brand {brand_active}" href="mega_validation_report_latest.html">天底スコアリング</a>
      <div class="top-nav-links">
        {section_links}
        {mode_links}
      </div>
    </nav>
    """


def guide_section_html() -> str:
    return """
    <section id="guide" class="panel guide-panel">
      <h2>使い方・対象銘柄</h2>
      <p class="note">TradingViewでBOTTOMシグナルが点灯した銘柄について、複数のテクニカル指標をもとに品質スコアを算出し、一覧で表示します。</p>
      <div class="guide-grid">
        <section class="guide-block">
          <h3>監視対象</h3>
          <ul class="guide-list">
            <li>東証個別株</li>
            <li>シグナル点灯前日終値が1,000円以下、かつ出来高10,000株以上</li>
            <li>シグナル点灯時のローソク足の出来高が5,000株以上</li>
            <li>1日あたり最大1,000銘柄。対象が1,001銘柄以上ある場合は、出来高が少ない銘柄から除外されます。</li>
          </ul>
        </section>
        <section class="guide-block">
          <h3>ボラティリティタグ</h3>
          <p class="note">ATR%から、銘柄ごとの値動きの大きさを示します。</p>
          <div class="vol-legend">
            <div><span class="vol-tag vol-low">🟢LOW</span><span>ATR 3%未満。値動きが比較的穏やかな銘柄です。</span></div>
            <div><span class="vol-tag vol-mid">🟡MID</span><span>ATR 3%以上6%未満。標準的な変動幅の銘柄です。</span></div>
            <div><span class="vol-tag vol-high">🔴HIGH</span><span>ATR 6%以上。大きく動きやすく、上振れも下振れも大きくなりやすい銘柄です。</span></div>
          </div>
        </section>
        <section class="guide-block">
          <h3>サイトの見方</h3>
          <ul class="guide-list">
            <li>モード別サマリーから、Stable、Sniper、Mega各モードの詳細ページへ移動できます。</li>
            <li>銘柄検索では、日付、証券コード、★数、株価、テクニカル指標で絞り込めます。</li>
            <li>各銘柄のファンダ分析ボタンは、該当日のDiscord分析がある場合だけ表示されます。</li>
          </ul>
        </section>
      </div>
    </section>
    """


def mode_summary_html(
    candidate: dict,
    stats: dict,
    watch_stats: dict,
    anchor_prefix: str = "",
    href: str | None = None,
    free: bool = False,
) -> str:
    link = href or f"#{anchor_id(candidate, anchor_prefix)}"
    locked = free and is_paid_mode(candidate)
    action_label = "有料会員限定" if locked else "詳細ページを見る" if href else "詳細を見る"
    metrics_html = f"""
        <div class="mode-metrics">
          <span><strong>{stats["n"]}</strong><small>確定</small></span>
          <span><strong>{pct_html(stats["win_rate"], signed=False)}</strong><small>勝率</small></span>
          <span><strong>{pct_html(stats["avg"])}</strong><small>平均</small></span>
          <span><strong>{watch_stats["with_current"]}</strong><small>ウォッチ中</small></span>
        </div>
        """
    return f"""
      <a class="mode-card {verdict_class(verdict(stats))}{" locked" if locked else ""}" href="{html_escape(link)}">
        <div class="mode-card-head">
          <span class="mode-name">{html_escape(candidate["label"])}</span>
          <span class="mode-horizon">{horizon_label(candidate["eval_days"])} / {html_escape(target_label(candidate))}</span>
        </div>
        <p>{html_escape(candidate["intent"])}</p>
        {metrics_html}
        <span class="mode-card-action">{html_escape(action_label)} →</span>
      </a>
    """


def html_table(
    headers: list[str],
    rows: list[list[str]],
    table_class: str = "",
    row_attrs: list[str] | None = None,
) -> str:
    class_attr = f' class="{html_escape(table_class)}"' if table_class else ""
    out = [f"<table{class_attr}>", "<thead><tr>"]
    out.extend(f"<th>{html_escape(header)}</th>" for header in headers)
    out.append("</tr></thead><tbody>")
    for row_index, row in enumerate(rows):
        attr = f" {row_attrs[row_index]}" if row_attrs and row_index < len(row_attrs) else ""
        out.append(f"<tr{attr}>")
        out.extend(
            f'<td data-label="{html_escape(headers[index])}">{cell}</td>'
            for index, cell in enumerate(row)
        )
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def html_signal_table(
    rows: pd.DataFrame,
    eval_days: int,
    confirmed: bool,
    current_candidate: dict | None = None,
    paginate_confirmed: bool = False,
    page_size: int = MODE_CONFIRMED_PAGE_SIZE,
) -> str:
    perf_col = f"perf_{eval_days}bd"
    if rows.empty:
        return '<p class="empty">該当なし</p>'

    show_star = current_candidate is not None and current_candidate.get("id") != "stable_s6"
    show_overlap = current_candidate is not None
    overlap_id = current_candidate.get("id") if current_candidate else None

    if confirmed:
        headers = ["日付"]
        if show_star:
            headers.append("★")
        headers.extend(["銘柄"])
        if show_overlap:
            headers.append("他モード")
        headers.extend(["評価値", "5営業日後", "10営業日後", "20営業日後", "40営業日後"])

        table_rows = []
        row_attrs = []
        for row_index, (_, row) in enumerate(rows.iterrows()):
            symbol = row.get("symbol", "")
            cells = [html_escape(row.get("date", ""))]
            if show_star:
                cells.append(star_score_badge(row))
            cells.extend(
                [
                    symbol_with_actions_html(symbol, row),
                ]
            )
            if show_overlap:
                cells.append(mode_match_badges(row, current_candidate_id=overlap_id))
            cells.extend(
                [
                    perf_with_price_html(row.get(perf_col), row.get(f"price_{eval_days}bd")),
                    perf_with_price_html(row.get("perf_5bd"), row.get("price_5bd")),
                    perf_with_price_html(row.get("perf_10bd"), row.get("price_10bd")),
                    perf_with_price_html(row.get("perf_20bd"), row.get("price_20bd")),
                    perf_with_price_html(row.get("perf_40bd"), row.get("price_40bd")),
                ]
            )
            table_rows.append(cells)
            if paginate_confirmed:
                hidden_class = ' class="is-hidden"' if row_index >= page_size else ""
                row_attrs.append(f'data-confirmed-row data-confirmed-index="{row_index}"{hidden_class}')
        return html_table(headers, table_rows, "signals", row_attrs if paginate_confirmed else None)

    headers = ["日付"]
    if show_star:
        headers.append("★")
    headers.extend(["銘柄"])
    if show_overlap:
        headers.append("他モード")
    headers.extend(["経過", "現在騰落", "5営業日後", "10営業日後", "20営業日後"])

    table_rows = []
    for _, row in rows.iterrows():
        symbol = row.get("symbol", "")
        cells = [html_escape(row.get("date", ""))]
        if show_star:
            cells.append(star_score_badge(row))
        cells.extend(
            [
                symbol_with_actions_html(symbol, row),
            ]
        )
        if show_overlap:
            cells.append(mode_match_badges(row, current_candidate_id=overlap_id))
        cells.extend(
            [
                html_escape(elapsed_business_days_text(row)),
                perf_with_price_html(row.get("cur_perf"), row.get("latest_close")),
                perf_with_price_html(row.get("perf_5bd"), row.get("price_5bd")),
                perf_with_price_html(row.get("perf_10bd"), row.get("price_10bd")),
                perf_with_price_html(row.get("perf_20bd"), row.get("price_20bd")),
            ]
        )
        table_rows.append(cells)
    return html_table(headers, table_rows, "signals")


def build_candidate_detail_sections(
    frame_confirmed: pd.DataFrame,
    frame_all: pd.DataFrame,
    stats_by_id: dict[str, dict],
    watch_by_id: dict[str, dict],
    best_candidates: list[dict],
    anchor_prefix: str = "",
) -> str:
    detail_sections = []
    for index, candidate in enumerate(CANDIDATES):
        stats = stats_by_id[candidate["id"]]
        watch_stats = watch_by_id[candidate["id"]]
        open_attr = " open" if index == 0 or candidate in best_candidates else ""
        confirmed_rows = candidate_rows(frame_confirmed, candidate, confirmed=True, limit=None)
        unconfirmed_rows = candidate_rows(frame_all, candidate, confirmed=False, limit=None)
        detail_sections.append(
            f"""
            <details id="{html_escape(anchor_id(candidate, anchor_prefix))}" class="candidate-detail"{open_attr}>
              <summary>
                <span class="summary-title">
                  <strong>{html_escape(candidate["label"])}</strong>
                  <small>{horizon_label(candidate["eval_days"])} / 目標 {html_escape(target_label(candidate))}</small>
                </span>
                <span class="summary-stats">
                  <span>確定 {stats["n"]}</span>
                  <span>ウォッチ {watch_stats["with_current"]}</span>
                </span>
              </summary>
              <div class="detail-grid">
                <section>
                  <h3>モード概要</h3>
                  <p>{html_escape(candidate["intent"])}</p>
                  <div class="chips">{condition_chips(candidate["conditions"])}</div>
                  <h4>確定済み銘柄の成績</h4>
                  <dl class="metrics">
                    <div><dt>評価軸</dt><dd>{horizon_label(candidate["eval_days"])} / 目標 {html_escape(target_label(candidate))}</dd></div>
                    <div><dt>件数</dt><dd>{stats["n"]}</dd></div>
                    <div><dt>平均</dt><dd>{pct_html(stats["avg"])}</dd></div>
                    <div><dt>中央値</dt><dd>{pct_html(stats["median"])}</dd></div>
                    <div><dt>勝率</dt><dd>{pct_html(stats["win_rate"], signed=False)}</dd></div>
                    <div><dt>Lift</dt><dd>{num(stats["lift"])}</dd></div>
                    <div><dt>最大</dt><dd>{pct_html(stats["max"])}</dd></div>
                    <div><dt>最小</dt><dd>{pct_html(stats["min"])}</dd></div>
                    <div><dt>&lt;=-10%</dt><dd>{stats["m10"]}</dd></div>
                  </dl>
                  <h4>未確定ウォッチリストの現在成績</h4>
                  <dl class="metrics">
                    <div><dt>件数</dt><dd>{watch_stats["with_current"]}</dd></div>
                    <div><dt>平均</dt><dd>{pct_html(watch_stats["avg"])}</dd></div>
                    <div><dt>中央値</dt><dd>{pct_html(watch_stats["median"])}</dd></div>
                    <div><dt>勝率</dt><dd>{pct_html(watch_stats["win_rate"], signed=False)}</dd></div>
                    <div><dt>+10%</dt><dd>{watch_stats["p10"]}</dd></div>
                    <div><dt>+20%</dt><dd>{watch_stats["p20"]}</dd></div>
                    <div><dt>最大</dt><dd>{pct_html(watch_stats["max"])}</dd></div>
                    <div><dt>最小</dt><dd>{pct_html(watch_stats["min"])}</dd></div>
                    <div><dt>&lt;=-10%</dt><dd>{watch_stats["m10"]}</dd></div>
                  </dl>
                </section>
                <section>
                  <h3>判定条件</h3>
                  <ul class="condition-list">
                    {''.join(
                        f'<li><code>{html_escape(cond)}</code><span>{html_escape(CONDITION_LABELS.get(cond, cond))}</span></li>'
                        for cond in candidate["conditions"]
                    )}
                  </ul>
                </section>
              </div>
              <h3>確定済み銘柄一覧</h3>
              {html_signal_table(confirmed_rows, candidate["eval_days"], confirmed=True, current_candidate=candidate)}
              <h3>未確定ウォッチリスト全件</h3>
              {html_signal_table(unconfirmed_rows, candidate["eval_days"], confirmed=False, current_candidate=candidate)}
            </details>
            """
        )
    return "".join(detail_sections)


def build_optional_archive_scope_html(
    frame_confirmed: pd.DataFrame | None,
    frame_all: pd.DataFrame | None,
    meta: dict | None,
) -> str:
    if frame_confirmed is None or frame_all is None or meta is None:
        return ""
    stats_rows, stats_by_id, watch_by_id = stats_table_rows(frame_confirmed, frame_all)
    summary = horizon_summary(frame_confirmed)
    best_candidates = [
        candidate
        for candidate in CANDIDATES
        if verdict(stats_by_id[candidate["id"]]).startswith(("有望", "継続監視"))
    ]
    summary_table = html_table(
        ["評価日", "確定件数", "平均", "勝率", "+10%", "+20%", "+30%", "+50%", "+100%"],
        [
            [
                f"<strong>{horizon_label(row['days'])}</strong>",
                html_escape(row["n"]),
                pct_html(row["avg"]),
                pct_html(row["win"], signed=False),
                html_escape(row["p10"]),
                html_escape(row["p20"]),
                html_escape(row["p30"]),
                html_escape(row["p50"]),
                html_escape(row["p100"]),
            ]
            for row in summary
        ],
        "compact",
    )
    mode_cards = "".join(
        mode_summary_html(
            candidate,
            stats_by_id[candidate["id"]],
            watch_by_id[candidate["id"]],
            anchor_prefix="archive-",
        )
        for candidate in CANDIDATES
    )
    confirmed_total = sum(stats_by_id[candidate["id"]]["n"] for candidate in CANDIDATES)
    watch_total = sum(watch_by_id[candidate["id"]]["with_current"] for candidate in CANDIDATES)
    detail_sections = build_candidate_detail_sections(
        frame_confirmed,
        frame_all,
        stats_by_id,
        watch_by_id,
        best_candidates,
        anchor_prefix="archive-",
    )
    return f"""
    <details class="archive-scope">
      <summary>
        <span>
          <strong>過去1年分の成績と銘柄を表示</strong>
          <small>過去のシグナルも含めて、長めの期間で確認できます。</small>
        </span>
      </summary>
      <section class="cards archive-cards">
        <div class="card"><div class="label">指標計算可能シグナル</div><div class="value">{meta["feature_rows"]}</div></div>
        <div class="card"><div class="label">対象モード</div><div class="value">{len(CANDIDATES)}</div></div>
        <div class="card"><div class="label">確定済み延べ件数</div><div class="value">{confirmed_total}</div></div>
        <div class="card"><div class="label">ウォッチ中延べ件数</div><div class="value">{watch_total}</div></div>
      </section>

      <section class="panel">
        <h2>全体成績（過去1年分）</h2>
        <p class="note">過去1年以内に出たBOTTOMシグナルを、評価日別に集計しています。</p>
        {summary_table}
      </section>

      <section class="panel">
        <h2>モード別サマリー（過去1年分）</h2>
        <div class="mode-grid">
          {mode_cards}
        </div>
      </section>

      <h2>モード別 銘柄一覧（過去1年分）</h2>
      {detail_sections}
    </details>
    """


def daily_detection_section_html(frame_all: pd.DataFrame, free: bool = False) -> str:
    title = "検出された銘柄一覧"
    if frame_all.empty or "signal_dt" not in frame_all.columns:
        return f"""
        <section id="daily-detections" class="panel">
          <h2>{title}</h2>
          <p class="empty">表示できる銘柄がありません。</p>
        </section>
        """

    rows = frame_all.copy()
    rows["_date_key"] = pd.to_datetime(rows["signal_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    rows = rows[rows["_date_key"].notna()].copy()
    if rows.empty:
        return f"""
        <section id="daily-detections" class="panel">
          <h2>{title}</h2>
          <p class="empty">表示できる銘柄がありません。</p>
        </section>
        """

    rows["_stable_score"] = rows.apply(stable_star_score, axis=1)
    rows["_mode_count"] = rows.apply(lambda row: len(row_mode_matches(row)), axis=1)
    rows["_cur_perf_sort"] = (
        pd.to_numeric(rows["cur_perf"], errors="coerce").fillna(-999.0)
        if "cur_perf" in rows.columns
        else -999.0
    )
    rows = rows.sort_values(
        ["_date_key", "_stable_score", "_mode_count", "_cur_perf_sort", "symbol"],
        ascending=[False, False, False, False, True],
    )

    available_dates = sorted(rows["_date_key"].dropna().unique(), reverse=True)
    min_date = available_dates[-1]
    max_date = available_dates[0]
    default_date = max_date
    page_size = 100
    default_total = int((rows["_date_key"] == default_date).sum())
    default_count = min(default_total, page_size)
    note = "初期表示は最新日です。★はStable ★6の判定条件を何個満たしたかです。"

    options = "\n".join(
        ["<option value=\"\">全期間</option>"]
        + [
            f'<option value="{html_escape(date_key)}"{" selected" if date_key == default_date else ""}>{html_escape(date_key)}</option>'
            for date_key in available_dates
        ]
    )

    headers = [
        "日付",
        "★",
        "銘柄",
        "該当モード",
        "現在騰落",
        "5営業日後",
        "10営業日後",
        "20営業日後",
        "40営業日後",
    ]
    table_parts = ['<table class="signals daily-detections">', "<thead><tr>"]
    table_parts.extend(f"<th>{html_escape(header)}</th>" for header in headers)
    table_parts.append("</tr></thead><tbody>")
    default_rendered = 0
    for _, row in rows.iterrows():
        date_key = str(row.get("_date_key", ""))
        symbol = row.get("symbol", "")
        clean_symbol = clean_symbol_text(symbol)
        star_score = stable_star_score(row)
        latest_price = row.get("latest_close", np.nan)
        condition_keys = " ".join(row_true_conditions(row))
        mode_keys = " ".join(candidate["id"] for candidate in row_mode_matches(row))
        mode_html = mode_match_badges(row, include_empty=False, link=True)
        if not mode_html:
            mode_html = '<span class="mode-badge none">モード外</span>'
        is_initial_row = date_key == default_date and default_rendered < page_size
        if date_key == default_date:
            default_rendered += 1
        hidden_class = "" if is_initial_row else ' class="is-hidden"'
        cells = [
            html_escape(date_key),
            star_score_badge(row),
            symbol_with_actions_html(symbol, row),
            mode_html,
            perf_with_price_html(row.get("cur_perf"), row.get("latest_close")),
            perf_with_price_html(row.get("perf_5bd"), row.get("price_5bd")),
            perf_with_price_html(row.get("perf_10bd"), row.get("price_10bd")),
            perf_with_price_html(row.get("perf_20bd"), row.get("price_20bd")),
            perf_with_price_html(row.get("perf_40bd"), row.get("price_40bd")),
        ]
        table_parts.append(
            f'<tr data-detection-row data-date="{html_escape(date_key)}" '
            f'data-symbol="{html_escape(clean_symbol)}" '
            f'data-star="{star_score}" '
            f'data-price="{html_escape(latest_price if is_finite(latest_price) else "")}" '
            f'data-conditions="{html_escape(condition_keys)}" '
            f'data-modes="{html_escape(mode_keys)}"{hidden_class}>'
        )
        table_parts.extend(
            f'<td data-label="{html_escape(headers[index])}">{cell}</td>'
            for index, cell in enumerate(cells)
        )
        table_parts.append("</tr>")
    table_parts.append("</tbody></table>")

    return f"""
    <section id="daily-detections" class="panel">
      <div class="daily-head">
        <div>
          <h2>{title}</h2>
          <p class="note">{html_escape(note)}</p>
        </div>
        <label class="filter-control" for="daily-date-filter">
          <span>表示日</span>
          <select id="daily-date-filter" data-default-date="{html_escape(default_date)}" data-page-size="{page_size}">
            {options}
          </select>
        </label>
      </div>
      <details class="search-panel">
        <summary>銘柄検索モード</summary>
        <div class="search-grid">
          <label>
            <span>開始日</span>
            <input id="search-date-from" type="date" min="{html_escape(min_date)}" max="{html_escape(max_date)}">
          </label>
          <label>
            <span>終了日</span>
            <input id="search-date-to" type="date" min="{html_escape(min_date)}" max="{html_escape(max_date)}">
          </label>
          <label>
            <span>証券コード</span>
            <input id="search-symbol" type="search" inputmode="latin" placeholder="例: 1234">
          </label>
          <label>
            <span>★最小</span>
            <select id="search-star-min">
              <option value="">指定なし</option>
              {''.join(f'<option value="{score}">★{score}以上</option>' for score in range(7))}
            </select>
          </label>
          <label>
            <span>★最大</span>
            <select id="search-star-max">
              <option value="">指定なし</option>
              {''.join(f'<option value="{score}">★{score}以下</option>' for score in range(7))}
            </select>
          </label>
          <label>
            <span>株価下限</span>
            <input id="search-price-min" type="number" min="0" step="1" inputmode="numeric" placeholder="円">
          </label>
          <label>
            <span>株価上限</span>
            <input id="search-price-max" type="number" min="0" step="1" inputmode="numeric" placeholder="円">
          </label>
        </div>
        <div class="indicator-filter">
          <div class="indicator-filter-head">
            <strong>検出モード</strong>
            <small>選択したモードのいずれかに該当する銘柄だけ表示します。</small>
          </div>
          <div class="indicator-options mode-options">
            {search_mode_options_html()}
          </div>
        </div>
        <div class="indicator-filter">
          <div class="indicator-filter-head">
            <strong>テクニカル指標</strong>
            <small>選択した条件をすべて満たす銘柄だけ表示します。</small>
          </div>
          <div class="indicator-options">
            {search_indicator_options_html()}
          </div>
        </div>
        <div class="search-actions">
          <button id="search-reset" type="button">検索条件をリセット</button>
        </div>
      </details>
      {
        paywall_cta_html(
            "検出銘柄一覧と銘柄検索モードは有料会員限定です",
            "アクセス権を購入すると全件を表示できます。",
            "/mega_validation_report_latest.html#daily-detections",
        )
        if free
        else ""
      }
      {
        '<p class="filter-status"><strong>会員限定</strong>/<span>会員限定</span>件を表示中</p>'
        if free
        else f'<p class="filter-status"><strong id="daily-visible-count">{default_count}</strong>/<span id="daily-total-count">{default_total}</span>件を表示中</p>'
      }
      {
        '<p class="empty">銘柄データは有料会員限定です。</p>'
        if free
        else '<p id="daily-empty-message" class="empty" hidden>この条件に一致する銘柄はありません。</p>'
      }
      {"" if free else "".join(table_parts)}
      {
        ""
        if free
        else f'<div class="load-more-row"><button id="daily-load-more" class="load-more" type="button"{" hidden" if default_count >= default_total else ""}>さらに表示</button></div>'
      }
    </section>
    """


def daily_detection_script() -> str:
    return '<script src="report-interactions.js" defer></script>'


def report_interactions_js() -> str:
    return """
(() => {
  const select = document.getElementById("daily-date-filter");
  const rows = Array.from(document.querySelectorAll("[data-detection-row]"));
  const count = document.getElementById("daily-visible-count");
  const total = document.getElementById("daily-total-count");
  const empty = document.getElementById("daily-empty-message");
  const dateFrom = document.getElementById("search-date-from");
  const dateTo = document.getElementById("search-date-to");
  const symbolInput = document.getElementById("search-symbol");
  const starMin = document.getElementById("search-star-min");
  const starMax = document.getElementById("search-star-max");
  const priceMin = document.getElementById("search-price-min");
  const priceMax = document.getElementById("search-price-max");
  const modeInputs = Array.from(document.querySelectorAll("[data-mode-filter]"));
  const indicatorInputs = Array.from(document.querySelectorAll("[data-indicator-filter]"));
  const reset = document.getElementById("search-reset");
  const loadMore = document.getElementById("daily-load-more");
  if (!select || rows.length === 0) return;
  const configuredPageSize = Number(select.dataset.pageSize || 100);
  const pageSize = Number.isFinite(configuredPageSize) ? Math.max(20, configuredPageSize) : 100;
  let visibleLimit = pageSize;

  const normalizeSymbol = (value) => String(value || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  const numericValue = (element) => {
    const value = String(element?.value || "").trim();
    if (value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const applyFilter = (resetLimit = true) => {
    if (resetLimit) visibleLimit = pageSize;
    const selectedDate = String(select.value || "");
    const from = String(dateFrom?.value || "");
    const to = String(dateTo?.value || "");
    const useCustomDateRange = Boolean(from || to);
    const symbol = normalizeSymbol(symbolInput?.value);
    const minStar = numericValue(starMin);
    const maxStar = numericValue(starMax);
    const minPrice = numericValue(priceMin);
    const maxPrice = numericValue(priceMax);
    const selectedModes = modeInputs
      .filter((input) => input.checked)
      .map((input) => input.value);
    const requiredConditions = indicatorInputs
      .filter((input) => input.checked)
      .map((input) => input.value);
    let matched = 0;
    let rendered = 0;
    rows.forEach((row) => {
      const rowDate = row.dataset.date || "";
      const rowSymbol = normalizeSymbol(row.dataset.symbol);
      const rowStar = Number(row.dataset.star);
      const rowPrice = row.dataset.price === "" ? NaN : Number(row.dataset.price);
      const rowConditions = new Set(String(row.dataset.conditions || "").split(/\\s+/).filter(Boolean));
      const rowModes = new Set(String(row.dataset.modes || "").split(/\\s+/).filter(Boolean));
      let shouldShow = true;
      if (useCustomDateRange) {
        if (from && rowDate < from) shouldShow = false;
        if (to && rowDate > to) shouldShow = false;
      } else if (selectedDate && rowDate !== selectedDate) {
        shouldShow = false;
      }
      if (symbol && !rowSymbol.includes(symbol)) shouldShow = false;
      if (minStar !== null && (!Number.isFinite(rowStar) || rowStar < minStar)) shouldShow = false;
      if (maxStar !== null && (!Number.isFinite(rowStar) || rowStar > maxStar)) shouldShow = false;
      if (minPrice !== null && (!Number.isFinite(rowPrice) || rowPrice < minPrice)) shouldShow = false;
      if (maxPrice !== null && (!Number.isFinite(rowPrice) || rowPrice > maxPrice)) shouldShow = false;
      if (selectedModes.length > 0 && !selectedModes.some((mode) => rowModes.has(mode))) shouldShow = false;
      if (requiredConditions.some((condition) => !rowConditions.has(condition))) shouldShow = false;
      const shouldRender = shouldShow && rendered < visibleLimit;
      row.classList.toggle("is-hidden", !shouldRender);
      if (shouldShow) matched += 1;
      if (shouldRender) rendered += 1;
    });
    if (count) count.textContent = String(rendered);
    if (total) total.textContent = String(matched);
    if (empty) empty.hidden = matched !== 0;
    if (loadMore) {
      const remaining = matched - rendered;
      loadMore.hidden = remaining <= 0;
      loadMore.textContent = remaining > 0
        ? `さらに${Math.min(pageSize, remaining)}件表示`
        : "さらに表示";
    }
  };

  const applySelectedDate = () => {
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    applyFilter(true);
  };

  select.addEventListener("change", applySelectedDate);
  select.addEventListener("input", applySelectedDate);
  [dateFrom, dateTo].filter(Boolean).forEach((element) => {
    element.addEventListener("change", () => {
      select.value = "";
      applyFilter(true);
    });
    element.addEventListener("input", () => {
      select.value = "";
      applyFilter(true);
    });
  });
  [
    symbolInput,
    starMin,
    starMax,
    priceMin,
    priceMax,
    ...modeInputs,
    ...indicatorInputs,
  ].filter(Boolean).forEach((element) => {
    element.addEventListener("change", applyFilter);
    element.addEventListener("input", applyFilter);
  });
  loadMore?.addEventListener("click", () => {
    visibleLimit += pageSize;
    applyFilter(false);
  });
  reset?.addEventListener("click", () => {
    const defaultDate = select.dataset.defaultDate || "";
    select.value = defaultDate;
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    if (symbolInput) symbolInput.value = "";
    if (starMin) starMin.value = "";
    if (starMax) starMax.value = "";
    if (priceMin) priceMin.value = "";
    if (priceMax) priceMax.value = "";
    modeInputs.forEach((input) => {
      input.checked = false;
    });
    indicatorInputs.forEach((input) => {
      input.checked = false;
    });
    applyFilter(true);
  });
  applyFilter(true);
})();

(() => {
  const rows = Array.from(document.querySelectorAll("[data-confirmed-row]"));
  const button = document.getElementById("confirmed-load-more");
  const visibleCount = document.getElementById("confirmed-visible-count");
  const totalCount = document.getElementById("confirmed-total-count");
  if (!button || rows.length === 0) return;
  const configuredPageSize = Number(button.dataset.pageSize || 10);
  const pageSize = Number.isFinite(configuredPageSize) ? Math.max(1, configuredPageSize) : 10;
  let visibleLimit = pageSize;

  const render = () => {
    let rendered = 0;
    rows.forEach((row, index) => {
      const shouldShow = index < visibleLimit;
      row.classList.toggle("is-hidden", !shouldShow);
      if (shouldShow) rendered += 1;
    });
    if (visibleCount) visibleCount.textContent = String(rendered);
    if (totalCount) totalCount.textContent = String(rows.length);
    const remaining = rows.length - rendered;
    button.hidden = remaining <= 0;
    button.textContent = remaining > 0
      ? `さらに${Math.min(pageSize, remaining)}件表示`
      : "さらに表示";
  };

  button.addEventListener("click", () => {
    visibleLimit += pageSize;
    render();
  });
  render();
})();
    """


def build_html_report(
    frame_confirmed: pd.DataFrame,
    frame_all: pd.DataFrame,
    meta: dict,
    generated_at: str,
    free: bool = False,
) -> str:
    stats_rows, stats_by_id, watch_by_id = stats_table_rows(frame_confirmed, frame_all)
    summary = horizon_summary(frame_confirmed)
    daily_detection_section = daily_detection_section_html(frame_all, free=free)

    summary_table = html_table(
        ["評価日", "確定件数", "平均", "勝率", "+10%", "+20%", "+30%", "+50%", "+100%"],
        [
            [
                f"<strong>{horizon_label(row['days'])}</strong>",
                html_escape(row["n"]),
                pct_html(row["avg"]),
                pct_html(row["win"], signed=False),
                html_escape(row["p10"]),
                html_escape(row["p20"]),
                html_escape(row["p30"]),
                html_escape(row["p50"]),
                html_escape(row["p100"]),
            ]
            for row in summary
        ],
        "compact",
    )

    mode_cards = "".join(
        mode_summary_html(
            candidate,
            stats_by_id[candidate["id"]],
            watch_by_id[candidate["id"]],
            href=mode_page_filename(candidate),
            free=free,
        )
        for candidate in CANDIDATES
    )
    confirmed_total = sum(stats_by_id[candidate["id"]]["n"] for candidate in CANDIDATES)
    watch_total = sum(watch_by_id[candidate["id"]]["with_current"] for candidate in CANDIDATES)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(REPORT_TITLE)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --text: #182230;
      --muted: #667085;
      --line: #d9e0ea;
      --blue: #2563eb;
      --navy: #102033;
      --green: #16815c;
      --green-bg: #e7f6ef;
      --amber: #a35a00;
      --amber-bg: #fff2d7;
      --red: #b42318;
      --red-bg: #fde7e4;
      --chip: #eef3fb;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-padding-top: 104px; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Yu Gothic", "Meiryo", "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.55;
    }}
    header {{
      background: var(--navy);
      color: white;
      padding: 28px 32px;
      border-bottom: 4px solid #2f80ed;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    header p {{
      margin: 4px 0;
      color: #d7e2f0;
    }}
    .eyebrow {{
      margin: 0 0 6px;
      color: #8fb7ff;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px;
    }}
    .top-nav {{
      position: sticky;
      top: 0;
      z-index: 30;
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 14px;
      background: rgba(16, 32, 51, 0.96);
      border-bottom: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow: 0 8px 24px rgba(16, 24, 40, 0.16);
    }}
    .top-nav-brand {{
      flex: 0 0 auto;
      padding: 7px 10px;
      border-radius: 7px;
      background: rgba(255, 255, 255, 0.08);
      color: white;
      font-weight: 800;
      text-decoration: none;
      white-space: nowrap;
    }}
    .top-nav-links {{
      display: flex;
      flex: 1 1 auto;
      flex-wrap: wrap;
      gap: 6px;
      min-width: 0;
      overflow-x: visible;
      scrollbar-width: thin;
    }}
    .top-nav a {{
      flex: 0 0 auto;
      padding: 7px 10px;
      border-radius: 999px;
      color: #d7e2f0;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.2;
      text-decoration: none;
      white-space: nowrap;
    }}
    .top-nav a:hover,
    .top-nav a.active {{
      background: #eef5ff;
      color: #1849a9;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .card, .panel, .candidate-detail {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
    }}
    .card {{
      padding: 16px;
    }}
    .card .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .card .value {{
      font-size: 24px;
      font-weight: 700;
    }}
    .mode-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .mode-card {{
      display: grid;
      gap: 10px;
      padding: 16px;
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--line);
      border-left: 4px solid var(--muted);
      border-radius: 8px;
      text-decoration: none;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
    }}
    .mode-card.good {{ border-left-color: var(--green); }}
    .mode-card.warn {{ border-left-color: var(--amber); }}
    .mode-card.hold {{ border-left-color: var(--muted); }}
    .mode-card:hover {{
      border-color: #b8c6d9;
      background: #fbfdff;
    }}
    .mode-card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }}
    .mode-name {{
      font-size: 16px;
      font-weight: 700;
    }}
    .mode-horizon {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .mode-card p {{
      margin: 0;
      color: #475467;
    }}
    .mode-card-action {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: fit-content;
      min-height: 30px;
      padding: 5px 10px;
      border-radius: 6px;
      background: #eef5ff;
      color: #1849a9;
      font-size: 12px;
      font-weight: 700;
    }}
    .mode-card:hover .mode-card-action {{
      background: #dceaff;
    }}
    .mode-metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .mode-metrics > span {{
      display: grid;
      gap: 2px;
      min-width: 0;
    }}
    .mode-metrics strong {{
      font-size: 15px;
      line-height: 1.2;
    }}
    .mode-metrics small {{
      color: var(--muted);
      font-size: 11px;
    }}
    .mode-link-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 10px;
    }}
    .mode-link {{
      display: grid;
      gap: 4px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      color: var(--text);
      text-decoration: none;
    }}
    .mode-link:hover {{
      border-color: #b8c6d9;
      background: #eef5ff;
    }}
    .mode-link span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .panel {{
      padding: 18px;
      margin-bottom: 18px;
      overflow-x: auto;
    }}
    .daily-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 10px;
    }}
    .daily-head h2 {{
      margin-top: 0;
    }}
    .filter-control {{
      display: grid;
      gap: 5px;
      min-width: 180px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .filter-control select {{
      min-height: 36px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--text);
      font: inherit;
    }}
    .filter-status {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .load-more {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 7px 14px;
      border: 1px solid #bfd2ee;
      border-radius: 6px;
      background: #eef5ff;
      color: #1849a9;
      font-weight: 700;
      cursor: pointer;
    }}
    .load-more-row {{
      display: flex;
      justify-content: center;
      padding: 12px 0 2px;
    }}
    .search-panel {{
      margin: 8px 0 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      overflow: hidden;
    }}
    .search-panel > summary {{
      cursor: pointer;
      padding: 11px 13px;
      color: #1849a9;
      font-weight: 700;
      list-style-position: inside;
    }}
    .search-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 10px;
      padding: 0 13px 12px;
    }}
    .search-grid label,
    .indicator-filter {{
      display: grid;
      gap: 5px;
      min-width: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .search-grid input,
    .search-grid select {{
      min-height: 34px;
      width: 100%;
      padding: 5px 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--text);
      font: inherit;
    }}
    .search-actions {{
      display: flex;
      justify-content: flex-end;
      padding: 0 13px 13px;
    }}
    .search-actions button {{
      min-height: 34px;
      padding: 6px 12px;
      border: 1px solid #bfd2ee;
      border-radius: 6px;
      background: #eef5ff;
      color: #1849a9;
      font-weight: 700;
      cursor: pointer;
    }}
    .search-actions button:hover {{
      background: #e3efff;
    }}
    .indicator-filter {{
      padding: 0 13px 13px;
    }}
    .indicator-filter-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .indicator-filter-head small {{
      color: var(--muted);
      font-weight: 500;
    }}
    .indicator-options {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 6px;
      max-height: 230px;
      overflow: auto;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
    }}
    .indicator-option {{
      display: flex;
      align-items: flex-start;
      gap: 7px;
      min-width: 0;
      padding: 6px;
      border-radius: 6px;
      color: var(--text);
      font-size: 12px;
      font-weight: 500;
    }}
    .indicator-option:hover {{
      background: #f3f7fc;
    }}
    .indicator-option input {{
      margin-top: 3px;
      flex: 0 0 auto;
    }}
    .indicator-option span {{
      display: grid;
      gap: 1px;
      min-width: 0;
    }}
    .indicator-option small {{
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    h2 {{
      margin: 26px 0 12px;
      font-size: 20px;
    }}
    h3 {{
      margin: 16px 0 10px;
      font-size: 16px;
    }}
    h4 {{
      margin: 14px 0 8px;
      font-size: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 820px;
    }}
    .signals {{
      min-width: 980px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: right;
      vertical-align: top;
      white-space: nowrap;
    }}
    th:first-child, td:first-child,
    .signals th:nth-child(3), .signals td:nth-child(3),
    .signals td[data-label="銘柄"] {{
      text-align: left;
      white-space: normal;
    }}
    .signals td[data-label="操作"] {{
      min-width: 118px;
      max-width: 170px;
      text-align: right;
      white-space: normal;
    }}
    thead th {{
      background: #f0f4f8;
      color: #344054;
      font-size: 12px;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tbody tr:hover {{
      background: #f8fbff;
    }}
    .compact th, .compact td {{
      padding: 8px 9px;
    }}
    .stat-stack {{
      display: grid;
      gap: 3px;
      min-width: 170px;
      text-align: left;
      white-space: normal;
    }}
    .stat-stack span {{
      display: block;
    }}
    .pos {{ color: var(--green); font-weight: 700; }}
    .neg {{ color: var(--red); font-weight: 700; }}
    .flat, .muted {{ color: var(--muted); }}
    .perf-cell {{
      display: inline-grid;
      justify-items: end;
      gap: 1px;
      min-width: 62px;
      line-height: 1.25;
    }}
    .price-sub {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 500;
      white-space: nowrap;
    }}
    .symbol {{
      font-family: "Consolas", "Menlo", monospace;
      font-weight: 700;
    }}
    .symbol-stack {{
      display: grid;
      justify-items: start;
      gap: 4px;
      min-width: 0;
      max-width: 270px;
      text-align: left;
    }}
    .symbol-identity {{
      display: flex;
      align-items: baseline;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
      white-space: nowrap;
    }}
    .symbol-separator {{
      color: var(--text);
      font-weight: 700;
      flex: 0 0 auto;
    }}
    .symbol-name {{
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
      line-height: 1.35;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .symbol-meta-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
    }}
    .symbol-price-meta {{
      display: inline-flex;
      align-items: center;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .symbol-price-meta > span {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .symbol-price-meta .price-value {{
      color: var(--text);
      font-weight: 800;
    }}
    .vol-tag {{
      display: inline-flex;
      align-items: center;
      width: fit-content;
      min-height: 22px;
      padding: 2px 7px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      line-height: 1.2;
      white-space: nowrap;
    }}
    .vol-low {{
      color: #087443;
      background: #e8f7ef;
    }}
    .vol-mid {{
      color: #946300;
      background: #fff4cf;
    }}
    .vol-high {{
      color: #b42318;
      background: #fde7e4;
    }}
    .vol-tag[data-tooltip] {{
      position: relative;
      cursor: help;
      outline-offset: 2px;
    }}
    .vol-tag[data-tooltip]::after {{
      content: attr(data-tooltip);
      display: none;
      position: absolute;
      left: 0;
      top: calc(100% + 6px);
      z-index: 20;
      width: max-content;
      max-width: 260px;
      padding: 8px 10px;
      border: 1px solid #c9d7ea;
      border-radius: 7px;
      background: #102033;
      color: #ffffff;
      box-shadow: 0 10px 26px rgba(16, 24, 40, 0.18);
      font-size: 12px;
      font-weight: 700;
      line-height: 1.45;
      white-space: normal;
    }}
    .vol-tag[data-tooltip]:hover::after,
    .vol-tag[data-tooltip]:focus-visible::after {{
      display: block;
    }}
    .symbol-stack .action-buttons {{
      margin-top: 2px;
      justify-content: flex-start;
      flex-wrap: nowrap;
    }}
    .symbol-stack .action-btn {{
      flex: 0 0 auto;
      min-width: 58px;
    }}
    .chip {{
      display: inline-block;
      margin: 2px 4px 2px 0;
      padding: 3px 7px;
      border-radius: 999px;
      background: var(--chip);
      color: #27415f;
      font-family: "Consolas", "Menlo", monospace;
      font-size: 12px;
      white-space: nowrap;
    }}
    .star-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      min-height: 26px;
      padding: 3px 8px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      white-space: nowrap;
    }}
    .star-badge.high {{
      color: var(--green);
      background: var(--green-bg);
    }}
    .star-badge.mid {{
      color: var(--amber);
      background: var(--amber-bg);
    }}
    .star-badge.low {{
      color: var(--muted);
      background: #eef0f3;
    }}
    .mode-badges {{
      display: inline-flex;
      justify-content: flex-end;
      gap: 4px;
      flex-wrap: wrap;
      max-width: 260px;
    }}
    .mode-badge {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 7px;
      border-radius: 999px;
      background: #eef5ff;
      color: #1849a9;
      font-size: 11px;
      font-weight: 700;
      text-decoration: none;
      white-space: nowrap;
    }}
    .mode-badge.none {{
      background: #eef0f3;
      color: var(--muted);
    }}
    a.mode-badge:hover {{
      background: #dceaff;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-weight: 700;
      font-size: 12px;
      white-space: nowrap;
    }}
    .badge.good {{ color: var(--green); background: var(--green-bg); }}
    .badge.warn {{ color: var(--amber); background: var(--amber-bg); }}
    .badge.hold {{ color: var(--muted); background: #eef0f3; }}
    .tail {{
      display: inline-block;
      margin-right: 6px;
      color: var(--green);
      font-size: 12px;
      font-weight: 700;
    }}
    .tail.danger {{ color: var(--red); }}
    .note {{
      color: var(--muted);
      margin: 0 0 14px;
    }}
    .candidate-detail {{
      margin-bottom: 14px;
      overflow: hidden;
    }}
    .candidate-detail > summary {{
      cursor: pointer;
      list-style: none;
      padding: 15px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      font-weight: 700;
      font-size: 16px;
    }}
    .summary-title {{
      display: grid;
      gap: 2px;
    }}
    .summary-title small {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }}
    .summary-stats {{
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--muted);
    }}
    .action-buttons {{
      display: flex;
      justify-content: flex-end;
      gap: 6px;
      flex-wrap: wrap;
      max-width: 100%;
      white-space: normal;
    }}
    .action-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 1 1 64px;
      min-width: 58px;
      max-width: 100%;
      min-height: 30px;
      padding: 5px 9px;
      border: 1px solid #bfd2ee;
      border-radius: 6px;
      background: #eef5ff;
      color: #1849a9;
      font-size: 12px;
      font-weight: 700;
      text-decoration: none;
      white-space: nowrap;
    }}
    .action-btn.secondary {{
      border-color: #cfd8e6;
      background: #f6f8fb;
      color: #344054;
    }}
    .action-btn.disabled {{
      border-color: #e1e7ef;
      background: #f3f5f8;
      color: #98a2b3;
      cursor: default;
    }}
    .action-btn:hover {{
      background: #dfeeff;
    }}
    .fundamental-detail {{
      margin-top: 8px;
      min-width: 260px;
      max-width: 520px;
      text-align: left;
      white-space: normal;
    }}
    .fundamental-detail summary {{
      cursor: pointer;
      color: #1849a9;
      font-size: 12px;
      font-weight: 700;
    }}
    .discord-message {{
      display: grid;
      gap: 8px;
      margin-top: 8px;
      color: #182230;
    }}
    .discord-embed {{
      border-left: 4px solid #5865f2;
      background: #f8f9ff;
      border-radius: 6px;
      padding: 10px;
    }}
    .discord-embed h4 {{
      margin: 0 0 8px;
      font-size: 13px;
    }}
    .discord-embed dl {{
      display: grid;
      gap: 8px;
      margin: 0;
    }}
    .discord-embed dt {{
      font-weight: 700;
      color: #344054;
      margin-bottom: 2px;
    }}
    .discord-embed dd {{
      margin: 0;
      color: #182230;
    }}
    .discord-meta {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 11px;
    }}
    .candidate-detail > summary::-webkit-details-marker {{ display: none; }}
    .candidate-detail > summary::before {{
      content: "+";
      display: inline-grid;
      place-items: center;
      width: 20px;
      height: 20px;
      margin-right: 8px;
      border-radius: 999px;
      background: #edf2f7;
      color: #344054;
      font-weight: 700;
    }}
    .candidate-detail[open] > summary::before {{
      content: "-";
    }}
    .candidate-detail > h3,
    .candidate-detail > table,
    .candidate-detail > .empty {{
      margin-left: 18px;
      margin-right: 18px;
    }}
    .candidate-detail table {{
      width: calc(100% - 36px);
      margin: 0 18px 16px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(260px, 0.7fr);
      gap: 16px;
      padding: 16px 18px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
      margin: 12px 0 0;
    }}
    .metrics div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfe;
    }}
    .metrics dt {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .metrics dd {{
      margin: 0;
      font-weight: 700;
    }}
    .condition-list {{
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .condition-list li {{
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 8px;
      padding: 6px 0;
      border-bottom: 1px solid #eef2f6;
    }}
    code {{
      font-family: "Consolas", "Menlo", monospace;
      color: #1849a9;
    }}
    .empty {{
      color: var(--muted);
      padding: 0 18px 18px;
    }}
    .gate-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .gate-list li {{
      margin: 8px 0;
    }}
    .guide-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 18px;
    }}
    .guide-block {{
      display: grid;
      align-content: start;
      gap: 8px;
      padding-top: 10px;
      border-top: 2px solid var(--line);
    }}
    .guide-block h3 {{
      margin: 0;
    }}
    .guide-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .guide-list li {{
      margin: 0 0 7px;
    }}
    .vol-legend {{
      display: grid;
      gap: 8px;
    }}
    .vol-legend > div {{
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: start;
      gap: 9px;
    }}
    .notice {{
      color: #475467;
      font-size: 13px;
      border-left: 4px solid var(--amber);
      padding: 10px 12px;
      background: #fffaf0;
      border-radius: 6px;
      margin-top: 12px;
    }}
    .paywall-panel {{
      position: relative;
      display: grid;
      gap: 14px;
      margin: 12px 0;
      padding: 18px;
      border: 1px solid #bfd2ee;
      border-radius: 8px;
      background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
      overflow: hidden;
    }}
    .locked-preview {{
      display: grid;
      gap: 8px;
      opacity: 0.55;
      filter: blur(2px);
      pointer-events: none;
    }}
    .locked-preview span {{
      display: block;
      height: 18px;
      border-radius: 999px;
      background: #d8e4f3;
    }}
    .locked-preview span:nth-child(2) {{ width: 84%; }}
    .locked-preview span:nth-child(3) {{ width: 68%; }}
    .locked-preview span:nth-child(4) {{ width: 76%; }}
    .paywall-copy {{
      position: relative;
      z-index: 1;
      display: grid;
      gap: 8px;
      max-width: 720px;
    }}
    .paywall-copy h3 {{
      margin: 0;
      font-size: 18px;
    }}
    .paywall-copy p {{
      margin: 0;
      color: #475467;
    }}
    .premium-badge {{
      display: inline-flex;
      width: fit-content;
      min-height: 24px;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: #102033;
      color: #ffffff;
      font-size: 12px;
      font-weight: 800;
    }}
    .access-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }}
    .access-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 8px 12px;
      border-radius: 7px;
      font-weight: 800;
      text-decoration: none;
    }}
    .access-btn.primary {{
      background: var(--blue);
      color: #ffffff;
    }}
    .access-btn.secondary {{
      border: 1px solid #bfd2ee;
      background: #eef5ff;
      color: #1849a9;
    }}
    .mode-card.locked {{
      border-left-color: var(--blue);
      background: #fbfdff;
    }}
    .is-hidden,
    [hidden] {{
      display: none !important;
    }}
    @media (max-width: 820px) {{
      .signals {{
        min-width: 0;
        border-collapse: separate;
        border-spacing: 0 10px;
      }}
      .signals thead {{
        display: none;
      }}
      .signals tbody,
      .signals tr,
      .signals td {{
        display: block;
        width: 100%;
      }}
      .signals tr {{
        border: 1px solid var(--line);
        border-radius: 8px;
        background: white;
        overflow: hidden;
      }}
      .signals td {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 8px 10px;
        text-align: right;
        white-space: normal;
      }}
      .signals td > .mode-badges {{
        justify-content: flex-end;
      }}
      .signals td::before {{
        content: attr(data-label);
        color: var(--muted);
        font-size: 12px;
        text-align: left;
      }}
      .signals td:nth-child(2),
      .signals td:nth-child(3) {{
        text-align: right;
      }}
      .signals td[data-label="銘柄"] .symbol-stack {{
        justify-items: end;
        margin-left: auto;
        text-align: right;
      }}
      .signals td[data-label="銘柄"] .symbol-identity,
      .signals td[data-label="銘柄"] .symbol-meta-row,
      .signals td[data-label="銘柄"] .action-buttons {{
        justify-content: flex-end;
      }}
      .signals td[data-label="銘柄"] .vol-tag[data-tooltip]::after {{
        left: auto;
        right: 0;
      }}
      .perf-cell {{
        justify-items: end;
      }}
      .action-buttons {{
        justify-content: flex-end;
        max-width: 100%;
      }}
      .fundamental-detail {{
        min-width: 0;
        max-width: 100%;
      }}
    }}
    @media (max-width: 760px) {{
      .top-nav {{
        align-items: center;
        gap: 7px;
        padding: 7px 10px;
      }}
      .top-nav-brand {{
        max-width: 138px;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .top-nav a {{
        padding: 7px 9px;
      }}
      .top-nav-links {{
        flex-wrap: nowrap;
        overflow-x: auto;
      }}
      header {{ padding: 22px 18px; }}
      main {{ padding: 14px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .card {{ padding: 12px; }}
      .card .value {{ font-size: 20px; }}
      .mode-grid {{ grid-template-columns: 1fr; }}
      .mode-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .daily-head {{
        display: grid;
      }}
      .filter-control {{
        min-width: 0;
      }}
      .search-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .indicator-options {{
        grid-template-columns: 1fr;
        max-height: 280px;
      }}
      .detail-grid {{ grid-template-columns: 1fr; }}
      .candidate-detail > summary {{
        align-items: flex-start;
        display: grid;
        grid-template-columns: auto 1fr;
      }}
      .summary-stats {{
        grid-column: 1 / -1;
        justify-content: flex-start;
        padding-left: 28px;
      }}
      .signals {{
        min-width: 0;
        border-collapse: separate;
        border-spacing: 0 10px;
      }}
      .signals thead {{
        display: none;
      }}
      .signals tbody,
      .signals tr,
      .signals td {{
        display: block;
        width: 100%;
      }}
      .signals tr {{
        border: 1px solid var(--line);
        border-radius: 8px;
        background: white;
        overflow: hidden;
      }}
      .signals td {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 8px 10px;
        text-align: right;
        white-space: normal;
      }}
      .signals td > .mode-badges {{
        justify-content: flex-end;
      }}
      .perf-cell {{
        justify-items: end;
      }}
      .signals td::before {{
        content: attr(data-label);
        color: var(--muted);
        font-size: 12px;
        text-align: left;
      }}
      .signals td:nth-child(2),
      .signals td:nth-child(3) {{
        text-align: right;
      }}
      .action-buttons {{
        justify-content: flex-end;
        max-width: 100%;
      }}
      .fundamental-detail {{
        min-width: 0;
        max-width: 100%;
      }}
      table {{ min-width: 680px; }}
      .signals {{ min-width: 0; }}
    }}
    @media print {{
      body {{ background: white; }}
      header {{ background: white; color: var(--text); border-bottom: 2px solid var(--line); }}
      header p {{ color: var(--muted); }}
      .card, .panel, .candidate-detail {{ box-shadow: none; break-inside: avoid; }}
      .candidate-detail {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  {navigation_html()}
  <header>
    <div class="eyebrow">Bottom Signal Report</div>
    <h1>{html_escape(REPORT_TITLE)}</h1>
    <p>生成日時: {html_escape(generated_at)}</p>
    <p>Stable、Sniper、Mega候補の過去1年分の成績と、ウォッチ中銘柄の現在成績をまとめています。</p>
  </header>
  <main>
    <section id="performance-summary" class="panel">
      <h2>全体成績（過去1年分）</h2>
      <section class="cards">
        <div class="card"><div class="label">指標計算可能シグナル</div><div class="value">{meta["feature_rows"]}</div></div>
        <div class="card"><div class="label">対象モード</div><div class="value">{len(CANDIDATES)}</div></div>
        <div class="card"><div class="label">確定済み延べ件数</div><div class="value">{confirmed_total}</div></div>
        <div class="card"><div class="label">ウォッチ中延べ件数</div><div class="value">{watch_total}</div></div>
      </section>
      <p class="note">過去1年以内に出たBOTTOMシグナルを、評価日別に集計しています。</p>
      {summary_table}
    </section>

    <section id="mode-summary" class="panel">
      <h2>モード別サマリー</h2>
      <div class="mode-grid">
        {mode_cards}
      </div>
      <p class="notice">過去成績は将来の値動きを保証するものではありません。銘柄を確認するときは、最新の開示、出来高、地合い、リスク許容度もあわせて確認してください。</p>
    </section>

    <section id="highlights" class="panel">
      <h2>注目ポイント</h2>
      <ul class="gate-list">
        <li><strong>Stable ★6</strong>は現行Stable満点。短期の安定感と下振れの少なさを見るモードです。</li>
        <li><strong>Sniper 勝率重視</strong>は派手さよりも、条件通過後にプラスで終わる比率を重視します。</li>
        <li><strong>Mega5 短期リバウンド</strong>は短期急騰狙い。5営業日でどこまで反転するかを見ます。</li>
        <li><strong>Mega40</strong>の2モードは中期反転狙い。確定まで時間がかかるため、ウォッチ中の現在成績が特に重要です。</li>
      </ul>
    </section>

    {daily_detection_section}

    {guide_section_html()}
  </main>
  {daily_detection_script()}
</body>
</html>
"""


def mode_page_style() -> str:
    return """
    :root {
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --text: #182230;
      --muted: #667085;
      --line: #d9e0ea;
      --navy: #102033;
      --green: #16815c;
      --green-bg: #e7f6ef;
      --amber: #a35a00;
      --amber-bg: #fff2d7;
      --red: #b42318;
      --chip: #eef3fb;
    }
    * { box-sizing: border-box; }
    html { scroll-padding-top: 104px; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Yu Gothic", "Meiryo", "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.55;
    }
    header {
      background: var(--navy);
      color: white;
      padding: 28px 32px;
      border-bottom: 4px solid #2f80ed;
    }
    header h1 { margin: 0 0 8px; font-size: 26px; letter-spacing: 0; }
    header p { margin: 4px 0; color: #d7e2f0; }
    main { max-width: 1320px; margin: 0 auto; padding: 24px; }
    .top-nav {
      position: sticky;
      top: 0;
      z-index: 30;
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 14px;
      background: rgba(16, 32, 51, 0.96);
      border-bottom: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow: 0 8px 24px rgba(16, 24, 40, 0.16);
    }
    .top-nav-brand {
      flex: 0 0 auto;
      padding: 7px 10px;
      border-radius: 7px;
      background: rgba(255, 255, 255, 0.08);
      color: white;
      font-weight: 800;
      text-decoration: none;
      white-space: nowrap;
    }
    .top-nav-links {
      display: flex;
      flex: 1 1 auto;
      flex-wrap: wrap;
      gap: 6px;
      min-width: 0;
      overflow-x: visible;
      scrollbar-width: thin;
    }
    .top-nav a {
      flex: 0 0 auto;
      padding: 7px 10px;
      border-radius: 999px;
      color: #d7e2f0;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.2;
      text-decoration: none;
      white-space: nowrap;
    }
    .top-nav a:hover, .top-nav a.active {
      background: #eef5ff;
      color: #1849a9;
    }
    .panel, .candidate-detail {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16,24,40,.05); margin-bottom: 18px;
    }
    .panel { padding: 18px; overflow-x: auto; }
    h2 { margin: 0 0 12px; font-size: 20px; }
    h3 { margin: 16px 0 10px; font-size: 16px; }
    h4 { margin: 14px 0 8px; font-size: 14px; }
    .note { color: var(--muted); margin: 0 0 14px; }
    .chips { margin: 8px 0 0; }
    .chip {
      display: inline-block; margin: 2px 4px 2px 0; padding: 3px 7px;
      border-radius: 999px; background: var(--chip); color: #27415f;
      font-family: "Consolas", "Menlo", monospace; font-size: 12px;
    }
    .star-badge {
      display: inline-flex; align-items: center; justify-content: center;
      min-width: 42px; min-height: 26px; padding: 3px 8px;
      border-radius: 999px; font-weight: 700; font-size: 12px; white-space: nowrap;
    }
    .star-badge.high { color: var(--green); background: var(--green-bg); }
    .star-badge.mid { color: var(--amber); background: var(--amber-bg); }
    .star-badge.low { color: var(--muted); background: #eef0f3; }
    .mode-badges {
      display: inline-flex; justify-content: flex-end; gap: 4px;
      flex-wrap: wrap; max-width: 260px;
    }
    .mode-badge {
      display: inline-flex; align-items: center; min-height: 24px; padding: 3px 7px;
      border-radius: 999px; background: #eef5ff; color: #1849a9;
      font-size: 11px; font-weight: 700; text-decoration: none; white-space: nowrap;
    }
    .mode-badge.none { background: #eef0f3; color: var(--muted); }
    .cards, .metrics {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px;
    }
    .metric-groups { display: grid; gap: 10px; }
    .watch-metrics { padding-top: 2px; }
    .metric {
      border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fbfcfe;
    }
    .metric .label { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .metric .value { font-weight: 700; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; min-width: 820px; }
    .signals { min-width: 980px; }
    th, td {
      border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: right;
      vertical-align: top; white-space: nowrap;
    }
    th:first-child, td:first-child, .signals th:nth-child(3), .signals td:nth-child(3),
    .signals td[data-label="銘柄"] {
      text-align: left; white-space: normal;
    }
    .signals td[data-label="操作"] {
      min-width: 118px; max-width: 170px; text-align: right; white-space: normal;
    }
    thead th { background: #f0f4f8; color: #344054; font-size: 12px; position: sticky; top: 0; }
    tbody tr:hover { background: #f8fbff; }
    .pos { color: var(--green); font-weight: 700; }
    .neg { color: var(--red); font-weight: 700; }
    .flat, .muted { color: var(--muted); }
    .perf-cell {
      display: inline-grid; justify-items: end; gap: 1px;
      min-width: 62px; line-height: 1.25;
    }
    .price-sub {
      color: var(--muted); font-size: 11px; font-weight: 500; white-space: nowrap;
    }
    .symbol { font-family: "Consolas", "Menlo", monospace; font-weight: 700; flex: 0 0 auto; }
    .symbol-stack {
      display: grid; justify-items: start; gap: 4px; min-width: 0; max-width: 270px; text-align: left;
    }
    .symbol-identity {
      display: flex; align-items: baseline; gap: 6px; min-width: 0; max-width: 100%; white-space: nowrap;
    }
    .symbol-separator {
      color: var(--text); font-weight: 700; flex: 0 0 auto;
    }
    .symbol-name {
      color: var(--text); font-size: 13px; font-weight: 700; line-height: 1.35;
      min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .symbol-meta-row {
      display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; max-width: 100%;
    }
    .symbol-price-meta {
      display: inline-flex; align-items: center;
      color: var(--muted); font-size: 11px; font-weight: 700; line-height: 1.25;
    }
    .symbol-price-meta > span {
      display: inline-flex; align-items: center; gap: 4px;
    }
    .symbol-price-meta .price-value { color: var(--text); font-weight: 800; }
    .vol-tag {
      display: inline-flex; align-items: center; width: fit-content; min-height: 22px;
      padding: 2px 7px; border-radius: 999px; font-size: 11px; font-weight: 800;
      line-height: 1.2; white-space: nowrap;
    }
    .vol-low { color: #087443; background: #e8f7ef; }
    .vol-mid { color: #946300; background: #fff4cf; }
    .vol-high { color: #b42318; background: #fde7e4; }
    .vol-tag[data-tooltip] {
      position: relative; cursor: help; outline-offset: 2px;
    }
    .vol-tag[data-tooltip]::after {
      content: attr(data-tooltip); display: none; position: absolute; left: 0; top: calc(100% + 6px);
      z-index: 20; width: max-content; max-width: 260px; padding: 8px 10px;
      border: 1px solid #c9d7ea; border-radius: 7px; background: #102033; color: #fff;
      box-shadow: 0 10px 26px rgba(16, 24, 40, .18); font-size: 12px; font-weight: 700;
      line-height: 1.45; white-space: normal;
    }
    .vol-tag[data-tooltip]:hover::after,
    .vol-tag[data-tooltip]:focus-visible::after { display: block; }
    .symbol-stack .action-buttons { margin-top: 2px; justify-content: flex-start; flex-wrap: nowrap; }
    .symbol-stack .action-btn { flex: 0 0 auto; min-width: 58px; }
    .action-buttons {
      display: flex; justify-content: flex-end; gap: 6px; flex-wrap: wrap;
      max-width: 100%; white-space: normal;
    }
    .action-btn {
      display: inline-flex; align-items: center; justify-content: center; min-height: 30px;
      flex: 1 1 64px; min-width: 58px; max-width: 100%;
      padding: 5px 9px; border: 1px solid #bfd2ee; border-radius: 6px;
      background: #eef5ff; color: #1849a9; font-size: 12px; font-weight: 700; text-decoration: none;
      white-space: nowrap;
    }
    .action-btn.secondary { border-color: #cfd8e6; background: #f6f8fb; color: #344054; }
    .fundamental-detail { margin-top: 8px; min-width: 260px; max-width: 520px; text-align: left; white-space: normal; }
    .fundamental-detail summary { cursor: pointer; color: #1849a9; font-size: 12px; font-weight: 700; }
    .discord-message { display: grid; gap: 8px; margin-top: 8px; color: #182230; }
    .discord-embed { border-left: 4px solid #5865f2; background: #f8f9ff; border-radius: 6px; padding: 10px; }
    .discord-embed h4 { margin: 0 0 8px; font-size: 13px; }
    .discord-embed dl { display: grid; gap: 8px; margin: 0; }
    .discord-embed dt { font-weight: 700; color: #344054; margin-bottom: 2px; }
    .discord-embed dd { margin: 0; color: #182230; }
    .discord-meta { margin: 8px 0 0; color: var(--muted); font-size: 11px; }
    .candidate-detail { padding: 18px; }
    .candidate-detail > summary { cursor: pointer; font-weight: 700; color: #1849a9; margin: -18px; padding: 18px; }
    .candidate-detail[open] > summary { border-bottom: 1px solid var(--line); margin-bottom: 16px; }
    .empty { color: var(--muted); padding: 0 0 10px; }
    .is-hidden,
    [hidden] {
      display: none !important;
    }
    .confirmed-list-status {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .load-more {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 7px 14px;
      border: 1px solid #bfd2ee;
      border-radius: 6px;
      background: #eef5ff;
      color: #1849a9;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
    }
    .load-more:hover {
      background: #e3efff;
    }
    .load-more-row {
      display: flex;
      justify-content: center;
      padding: 12px 0 2px;
    }
    .guide-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 18px;
    }
    .guide-block {
      display: grid;
      align-content: start;
      gap: 8px;
      padding-top: 10px;
      border-top: 2px solid var(--line);
    }
    .guide-block h3 { margin: 0; }
    .guide-list {
      margin: 0;
      padding-left: 18px;
    }
    .guide-list li { margin: 0 0 7px; }
    .vol-legend {
      display: grid;
      gap: 8px;
    }
    .vol-legend > div {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: start;
      gap: 9px;
    }
    .paywall-panel {
      position: relative;
      display: grid;
      gap: 14px;
      margin: 12px 0;
      padding: 18px;
      border: 1px solid #bfd2ee;
      border-radius: 8px;
      background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
      overflow: hidden;
    }
    .locked-preview {
      display: grid;
      gap: 8px;
      opacity: 0.55;
      filter: blur(2px);
      pointer-events: none;
    }
    .locked-preview span {
      display: block;
      height: 18px;
      border-radius: 999px;
      background: #d8e4f3;
    }
    .locked-preview span:nth-child(2) { width: 84%; }
    .locked-preview span:nth-child(3) { width: 68%; }
    .locked-preview span:nth-child(4) { width: 76%; }
    .paywall-copy {
      position: relative;
      z-index: 1;
      display: grid;
      gap: 8px;
      max-width: 720px;
    }
    .paywall-copy h3 { margin: 0; font-size: 18px; }
    .paywall-copy p { margin: 0; color: #475467; }
    .premium-badge {
      display: inline-flex;
      width: fit-content;
      min-height: 24px;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: #102033;
      color: #ffffff;
      font-size: 12px;
      font-weight: 800;
    }
    .access-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }
    .access-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      padding: 8px 12px;
      border-radius: 7px;
      font-weight: 800;
      text-decoration: none;
    }
    .access-btn.primary {
      background: #2563eb;
      color: #ffffff;
    }
    .access-btn.secondary {
      border: 1px solid #bfd2ee;
      background: #eef5ff;
      color: #1849a9;
    }
    @media (max-width: 820px) {
      .signals { min-width: 0; border-collapse: separate; border-spacing: 0 10px; }
      .signals thead { display: none; }
      .signals tbody, .signals tr, .signals td { display: block; width: 100%; }
      .signals tr { border: 1px solid var(--line); border-radius: 8px; background: white; overflow: hidden; }
      .signals td {
        display: flex; justify-content: space-between; gap: 12px; padding: 8px 10px;
        text-align: right; white-space: normal;
      }
      .signals td::before { content: attr(data-label); color: var(--muted); font-size: 12px; text-align: left; }
      .signals td > .mode-badges { justify-content: flex-end; }
      .signals td[data-label="銘柄"] .symbol-stack {
        justify-items: end;
        margin-left: auto;
        text-align: right;
      }
      .signals td[data-label="銘柄"] .symbol-identity,
      .signals td[data-label="銘柄"] .symbol-meta-row,
      .signals td[data-label="銘柄"] .action-buttons {
        justify-content: flex-end;
      }
      .signals td[data-label="銘柄"] .vol-tag[data-tooltip]::after {
        left: auto;
        right: 0;
      }
      .perf-cell { justify-items: end; }
      .action-buttons { justify-content: flex-end; flex-wrap: wrap; max-width: 100%; }
      .fundamental-detail { min-width: 0; max-width: 100%; }
    }
    @media (max-width: 760px) {
      .top-nav {
        align-items: center;
        gap: 7px;
        padding: 7px 10px;
      }
      .top-nav-brand {
        max-width: 138px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .top-nav a {
        padding: 7px 9px;
      }
      .top-nav-links {
        flex-wrap: nowrap;
        overflow-x: auto;
      }
      header { padding: 22px 18px; }
      main { padding: 14px; }
      .signals { min-width: 0; border-collapse: separate; border-spacing: 0 10px; }
      .signals thead { display: none; }
      .signals tbody, .signals tr, .signals td { display: block; width: 100%; }
      .signals tr { border: 1px solid var(--line); border-radius: 8px; background: white; overflow: hidden; }
      .signals td {
        display: flex; justify-content: space-between; gap: 12px; padding: 8px 10px;
        text-align: right; white-space: normal;
      }
      .signals td::before { content: attr(data-label); color: var(--muted); font-size: 12px; text-align: left; }
      .signals td > .mode-badges { justify-content: flex-end; }
      .perf-cell { justify-items: end; }
      .action-buttons { justify-content: flex-end; flex-wrap: wrap; }
      .fundamental-detail { min-width: 0; max-width: 100%; }
      table { min-width: 680px; }
      .signals { min-width: 0; }
    }
    """


def stat_metrics_html(stats: dict, watch_stats: dict, include_watch: bool = True) -> str:
    confirmed_items = [
        ("確定件数", stats["n"]),
        ("確定平均", pct_html(stats["avg"])),
        ("確定勝率", pct_html(stats["win_rate"], signed=False)),
        ("目標Hit", stats["target_hits"]),
    ]
    watch_items = [
        ("ウォッチ中", watch_stats["with_current"]),
        ("現在平均", pct_html(watch_stats["avg"])),
        ("現在勝率", pct_html(watch_stats["win_rate"], signed=False)),
        ("現在+10%", watch_stats["p10"]),
    ]

    def row_html(items: list[tuple[str, object]], row_class: str) -> str:
        cards = "".join(
            f'<div class="metric"><div class="label">{html_escape(label)}</div><div class="value">{value}</div></div>'
            for label, value in items
        )
        return f'<div class="metrics {row_class}">{cards}</div>'

    return (
        '<div class="metric-groups">'
        f'{row_html(confirmed_items, "confirmed-metrics")}'
        f'{row_html(watch_items, "watch-metrics") if include_watch else ""}'
        "</div>"
    )


def build_mode_html_page(
    candidate: dict,
    frame_confirmed: pd.DataFrame,
    frame_all: pd.DataFrame,
    generated_at: str,
    free: bool = False,
) -> str:
    free_paid_mode = free and is_paid_mode(candidate)
    stats = candidate_stats(frame_confirmed, candidate)
    watch_stats = current_watch_stats(frame_all, candidate)
    confirmed_limit = FREE_CONFIRMED_LIMIT if free and not free_paid_mode else None
    confirmed_all_rows = candidate_rows(frame_confirmed, candidate, confirmed=True, limit=None)
    confirmed_rows = confirmed_all_rows if confirmed_limit is None else confirmed_all_rows.head(confirmed_limit)
    unconfirmed_rows = candidate_rows(frame_all, candidate, confirmed=False, limit=None)
    confirmed_heading = "確定済み銘柄一覧" if free_paid_mode else f"確定済み上位{FREE_CONFIRMED_LIMIT}件" if free else "確定済み銘柄一覧"
    confirmed_visible_total = int(len(confirmed_rows))
    confirmed_full_total = int(len(confirmed_all_rows))
    confirmed_initial = min(confirmed_visible_total, MODE_CONFIRMED_PAGE_SIZE)
    confirmed_table_html = html_signal_table(
        confirmed_rows,
        candidate["eval_days"],
        confirmed=True,
        current_candidate=candidate,
        paginate_confirmed=not free,
        page_size=MODE_CONFIRMED_PAGE_SIZE,
    )
    if free_paid_mode or confirmed_visible_total == 0:
        confirmed_status_html = ""
    elif free:
        confirmed_status_html = f"""
      <p class="confirmed-list-status"><strong>{confirmed_visible_total}</strong>/<span>{confirmed_full_total}</span>件を表示中</p>
        """
    else:
        confirmed_status_html = f"""
      <p class="confirmed-list-status"><strong id="confirmed-visible-count">{confirmed_initial}</strong>/<span id="confirmed-total-count">{confirmed_visible_total}</span>件を表示中</p>
        """
    confirmed_load_more_html = (
        ""
        if free or confirmed_visible_total == 0
        else f"""
      <div class="load-more-row">
        <button id="confirmed-load-more" class="load-more" type="button" data-page-size="{MODE_CONFIRMED_PAGE_SIZE}"{" hidden" if confirmed_initial >= confirmed_visible_total else ""}>さらに{min(MODE_CONFIRMED_PAGE_SIZE, max(confirmed_visible_total - confirmed_initial, 0))}件表示</button>
      </div>
        """
    )
    confirmed_upgrade_html = (
        f"""
      <div class="load-more-row">
        <a class="load-more" href="{PURCHASE_PATH}">さらに表示するには有料会員へ</a>
      </div>
        """
        if free and not free_paid_mode and confirmed_full_total > confirmed_visible_total
        else ""
    )
    condition_detail_html = "" if free_paid_mode else f'<div class="chips">{condition_chips(candidate["conditions"])}</div>'
    confirmed_html = (
        paywall_cta_html(
            "銘柄一覧は有料会員限定です",
            "アクセス権を購入すると全件を表示できます。",
            f"/{mode_page_filename(candidate)}#confirmed",
        )
        if free_paid_mode
        else f"""
      {('<p class="note">無料表示では、既存の並び順で上位10件だけを表示します。</p>' if free else '')}
      {confirmed_status_html}
      {confirmed_table_html}
      {confirmed_load_more_html}
      {confirmed_upgrade_html}
        """
    )
    watch_html = (
        paywall_cta_html(
            "未確定ウォッチリストは有料会員限定です",
            "アクセス権を購入すると全件を表示できます。",
            f"/{mode_page_filename(candidate)}#watch",
        )
        if free
        else html_signal_table(unconfirmed_rows, candidate["eval_days"], confirmed=False, current_candidate=candidate)
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(candidate["label"])} | {html_escape(REPORT_TITLE)}</title>
  <style>{mode_page_style()}</style>
</head>
<body>
  {navigation_html(candidate["id"], include_mode_sections=True)}
  <header>
    <h1>{html_escape(candidate["label"])}</h1>
    <p>生成日時: {html_escape(generated_at)}</p>
    <p>{html_escape(candidate["intent"])}</p>
  </header>
  <main>
    <section id="summary" class="panel">
      <h2>成績サマリー（過去1年分）</h2>
      <p class="note">{horizon_label(candidate["eval_days"])} / 目標 {html_escape(target_label(candidate))}。過去1年以内に出たBOTTOMシグナルの成績を集計しています。</p>
      {condition_detail_html}
      {stat_metrics_html(stats, watch_stats, include_watch=True)}
    </section>

    <section id="confirmed" class="panel">
      <h2>{confirmed_heading}</h2>
      {confirmed_html}
    </section>

    <section id="watch" class="panel">
      <h2>未確定ウォッチリスト全件</h2>
      {watch_html}
    </section>

    {guide_section_html()}
  </main>
  {"" if free else daily_detection_script()}
</body>
</html>
"""


def build_locked_mode_html_page(candidate: dict, generated_at: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(candidate["label"])} | {html_escape(REPORT_TITLE)}</title>
  <style>{mode_page_style()}</style>
</head>
<body>
  {navigation_html(candidate["id"], include_mode_sections=True)}
  <header>
    <h1>{html_escape(candidate["label"])}</h1>
    <p>生成日時: {html_escape(generated_at)}</p>
    <p>{html_escape(candidate["intent"])}</p>
  </header>
  <main>
    <section id="summary" class="panel">
      <h2>有料会員限定モード</h2>
      {paywall_cta_html(
          "Megaモードの銘柄一覧は有料会員限定です",
          "アクセス権を購入すると表示されます。",
          f"/{mode_page_filename(candidate)}",
      )}
    </section>
    {guide_section_html()}
  </main>
</body>
</html>
"""


def build_report(
    frame_confirmed: pd.DataFrame,
    frame_all: pd.DataFrame,
    meta: dict,
    generated_at: str,
) -> str:
    stats_rows, stats_by_id, watch_by_id = stats_table_rows(frame_confirmed, frame_all)

    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"- 生成日時: {generated_at}",
        "- 対象: 過去1年以内に出たTradingView BOTTOMシグナル",
        "- 注意: 過去成績は将来の値動きを保証するものではありません。",
        "",
        "## 全体成績（過去1年分）",
        "",
        f"- 指標計算可能シグナル: {meta['feature_rows']}",
        f"- 対象モード: {len(CANDIDATES)}",
        f"- 確定済み延べ件数: {sum(stats_by_id[candidate['id']]['n'] for candidate in CANDIDATES)}",
        f"- ウォッチ中延べ件数: {sum(watch_by_id[candidate['id']]['with_current'] for candidate in CANDIDATES)}",
        "",
    ]

    summary_rows = []
    for row in horizon_summary(frame_confirmed):
        summary_rows.append(
            [
                horizon_label(row["days"]),
                str(row["n"]),
                pct(row["avg"]),
                pct(row["win"], signed=False),
                str(row["p10"]),
                str(row["p20"]),
                str(row["p30"]),
                str(row["p50"]),
                str(row["p100"]),
            ]
        )
    lines.extend(
        markdown_table(
            ["評価日", "確定件数", "平均", "勝率", "+10%", "+20%", "+30%", "+50%", "+100%"],
            summary_rows,
        )
    )
    lines += [
        "",
        "## モード別サマリー",
        "",
        "各モードの過去1年分の成績と、ウォッチ中銘柄の現在成績です。",
        "",
    ]

    lines.extend(
        markdown_table(
            ["モード", "評価", "目標", "確定", "平均", "勝率", "ウォッチ中", "現在平均"],
            [
                [
                    row["label"],
                    horizon_label(row["days"]),
                    row["target"],
                    str(row["n"]),
                    row["avg"],
                    row["win"],
                    str(watch_by_id[CANDIDATES[index]["id"]]["with_current"]),
                    pct(watch_by_id[CANDIDATES[index]["id"]]["avg"]),
                ]
                for index, row in enumerate(stats_rows)
            ],
        )
    )

    lines += [
        "",
        "## 注目ポイント",
        "",
        "- `Stable ★6` は現行Stable満点。短期の安定感と下振れの少なさを見るモードです。",
        "- `Sniper 勝率重視` は派手さよりも、条件通過後にプラスで終わる比率を重視します。",
        "- `Mega5 短期リバウンド` は短期急騰狙い。5営業日でどこまで反転するかを見ます。",
        "- `Mega40` の2モードは中期反転狙い。確定まで時間がかかるため、ウォッチ中の現在成績が特に重要です。",
        "",
    ]

    lines += [
        "## 使い方・対象銘柄",
        "",
        "TradingViewでBOTTOMシグナルが点灯した銘柄について、複数のテクニカル指標をもとに品質スコアを算出し、一覧で表示します。",
        "",
        "### 監視対象",
        "",
        "- 東証個別株",
        "- シグナル点灯前日終値が1,000円以下、かつ出来高10,000株以上",
        "- シグナル点灯時のローソク足の出来高が5,000株以上",
        "- 1日あたり最大1,000銘柄。対象が1,001銘柄以上ある場合は、出来高が少ない銘柄から除外されます。",
        "",
        "### ボラティリティタグ",
        "",
        "- 🟢LOW: ATR 3%未満。値動きが比較的穏やかな銘柄です。",
        "- 🟡MID: ATR 3%以上6%未満。標準的な変動幅の銘柄です。",
        "- 🔴HIGH: ATR 6%以上。大きく動きやすく、上振れも下振れも大きくなりやすい銘柄です。",
        "",
    ]

    lines += ["## モード別 銘柄一覧（過去1年分）", ""]

    for candidate in CANDIDATES:
        stats = stats_by_id[candidate["id"]]
        watch_stats = watch_by_id[candidate["id"]]
        lines += [
            f"### {candidate['label']}",
            "",
            f"- 概要: {candidate['intent']}",
            f"- 評価軸: {horizon_label(candidate['eval_days'])} / 目標 {target_label(candidate)}",
            f"- 条件: {conditions_text(candidate['conditions'])}",
            f"- 条件説明:<br>{condition_labels_text(candidate['conditions'])}",
            (
                f"- 成績: 件数 {stats['n']} / 平均 {pct(stats['avg'])} / 中央値 {pct(stats['median'])} / "
                f"勝率 {pct(stats['win_rate'], signed=False)} / 目標Hit {stats['target_hits']} / "
                f"Lift {num(stats['lift'])}"
            ),
            f"- 確定済み銘柄の成績: {compact_stats_text(stats, include_target=True)}",
            f"- 未確定ウォッチリストの現在成績: {compact_stats_text(watch_stats)}",
            "",
            "#### 確定済み銘柄一覧",
            "",
        ]
        confirmed_rows = candidate_rows(frame_confirmed, candidate, confirmed=True, limit=None)
        lines.extend(signal_table(confirmed_rows, candidate["eval_days"], confirmed=True))
        lines += ["", "#### 未確定ウォッチリスト全件", ""]
        unconfirmed_rows = candidate_rows(frame_all, candidate, confirmed=False, limit=None)
        lines.extend(signal_table(unconfirmed_rows, candidate["eval_days"], confirmed=False))
        lines.append("")

    lines += [
        "## 注意事項",
        "",
        "- 本ページは情報提供を目的とした集計であり、投資助言ではありません。",
        "- 最新の開示、出来高、地合い、リスク許容度をあわせて確認してください。",
    ]
    return "\n".join(lines)


def report_meta(base_meta: dict, frame_all: pd.DataFrame, frame_confirmed: pd.DataFrame) -> dict:
    meta = dict(base_meta)
    meta["feature_rows"] = len(frame_all)
    meta["confirmed_feature_rows"] = len(frame_confirmed)
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        dest="markdown_output",
        default=DEFAULT_MARKDOWN_OUTPUT,
        help=(
            "Markdown output path. Kept as --output for compatibility "
            f"(default: {DEFAULT_MARKDOWN_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        dest="markdown_output",
        default=None,
        help=f"Markdown output path (default: {DEFAULT_MARKDOWN_OUTPUT})",
    )
    parser.add_argument(
        "--html-output",
        default=DEFAULT_HTML_OUTPUT,
        help=f"HTML output path (default: {DEFAULT_HTML_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    confirmed_frame, _, confirmed_meta = build_alert_frame(include_unconfirmed=False)
    all_frame, _, all_meta = build_alert_frame(include_unconfirmed=True)
    premium_links = fetch_premium_discord_links(opt.get_service())
    premium_urls = collect_premium_urls(all_frame, premium_links)
    discord_messages = fetch_discord_messages(premium_urls)
    confirmed_frame = attach_fundamental_links(confirmed_frame, premium_links, discord_messages)
    all_frame = attach_fundamental_links(all_frame, premium_links, discord_messages)

    report_confirmed_frame = recent_calendar_day_frame(confirmed_frame, 365)
    report_all_frame = recent_calendar_day_frame(all_frame, 365)
    report_meta_data = report_meta(all_meta, report_all_frame, report_confirmed_frame)
    report_meta_data["premium_log_urls"] = premium_links.get("matched_urls", 0)
    report_meta_data["discord_messages"] = len(discord_messages)
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S %Z")

    markdown_output = args.markdown_output or DEFAULT_MARKDOWN_OUTPUT
    markdown_report = build_report(report_confirmed_frame, report_all_frame, report_meta_data, generated_at)
    markdown_path = os.path.abspath(markdown_output)
    os.makedirs(os.path.dirname(markdown_path), exist_ok=True)
    with open(markdown_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown_report)
        handle.write("\n")

    html_report = build_html_report(
        report_confirmed_frame,
        report_all_frame,
        report_meta_data,
        generated_at,
    )
    html_report = "\n".join(line.rstrip() for line in html_report.rstrip().splitlines())
    html_path = os.path.abspath(args.html_output)
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html_report.rstrip())
        handle.write("\n")

    free_html_report = build_html_report(
        report_confirmed_frame,
        report_all_frame,
        report_meta_data,
        generated_at,
        free=True,
    )
    free_html_report = "\n".join(line.rstrip() for line in free_html_report.rstrip().splitlines())
    free_html_path = os.path.join(
        os.path.dirname(html_path),
        free_report_filename(os.path.basename(html_path)),
    )
    with open(free_html_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(free_html_report.rstrip())
        handle.write("\n")

    html_dir = os.path.dirname(html_path)
    script_path = os.path.join(html_dir, "report-interactions.js")
    with open(script_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report_interactions_js().strip())
        handle.write("\n")

    for candidate in CANDIDATES:
        mode_report = build_mode_html_page(
            candidate,
            report_confirmed_frame,
            report_all_frame,
            generated_at,
        )
        mode_report = "\n".join(line.rstrip() for line in mode_report.rstrip().splitlines())
        mode_path = os.path.join(html_dir, mode_page_filename(candidate))
        with open(mode_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(mode_report.rstrip())
            handle.write("\n")
        print(f"wrote {mode_path}")

        free_mode_report = build_mode_html_page(
            candidate,
            report_confirmed_frame,
            report_all_frame,
            generated_at,
            free=True,
        )
        free_mode_report = "\n".join(line.rstrip() for line in free_mode_report.rstrip().splitlines())
        free_mode_path = os.path.join(html_dir, free_mode_page_filename(candidate))
        with open(free_mode_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(free_mode_report.rstrip())
            handle.write("\n")
        print(f"wrote {free_mode_path}")

    print(f"wrote {script_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {html_path}")
    print(f"wrote {free_html_path}")


if __name__ == "__main__":
    main()
