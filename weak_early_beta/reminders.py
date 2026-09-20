"""Idempotent fifth-session morning reminder for forward Cloud detections."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
import requests

from .bank_calendar import fifth_session_from_entry
from .notify import WEBHOOK_ENV, _discord_url, _number


REMINDER_COLOR = 0xF39C12


def _payload(group: pd.DataFrame, target: date, report_url: str) -> dict[str, Any]:
    first = group.iloc[0]
    company = str(first.get("company_name", "") or "").strip()
    symbol = str(first["symbol"])
    embed: dict[str, Any] = {
        "title": f"5営業日目の確認：{symbol} {company}".strip(),
        "description": "本日の終値で、Cloudの5営業日目が確定します。運用ルールの確認用リマインダーです。",
        "color": REMINDER_COLOR,
        "fields": [
            {"name": "確認日", "value": target.isoformat(), "inline": True},
            {"name": "エントリー日", "value": f"{pd.Timestamp(first['entry_date']):%Y-%m-%d}", "inline": True},
            {"name": "エントリー価格", "value": _number(first.get("entry_open"), "円"), "inline": True},
            {"name": "該当モード数", "value": f"{group['selector_id'].nunique()}モード", "inline": True},
        ],
        "footer": {"text": "売買推奨ではなく、設定済み評価日の確認通知です"},
    }
    if report_url:
        embed["url"] = report_url
    return {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}}


def notify_exit_reminders(
    ledger: pd.DataFrame,
    target: date,
    report_url: str = "",
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    webhook_url = (webhook_url or os.environ.get(WEBHOOK_ENV, "")).strip()
    result = ledger.copy()
    candidates = result[
        result["source_scope"].eq("FORWARD_CAUSAL")
        & pd.to_datetime(result["entry_date"], errors="coerce").notna()
        & result["exit_reminded_at"].fillna("").astype(str).str.strip().eq("")
    ].copy()
    payloads: list[dict[str, Any]] = []
    for (signal_date, symbol), group in candidates.groupby(["signal_date", "symbol"], sort=True):
        entry = pd.Timestamp(group.iloc[0]["entry_date"]).date()
        if fifth_session_from_entry(entry) != target:
            continue
        payload = _payload(group, target, report_url)
        payloads.append(payload)
        if dry_run:
            continue
        if not webhook_url:
            raise RuntimeError(f"{WEBHOOK_ENV} is required for live exit reminders")
        response = requests.post(
            webhook_url + ("&" if "?" in webhook_url else "?") + "wait=true",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        receipt = response.json()
        mask = (
            pd.to_datetime(result["signal_date"]).eq(pd.Timestamp(signal_date))
            & result["symbol"].astype(str).eq(str(symbol))
            & result["source_scope"].eq("FORWARD_CAUSAL")
        )
        now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
        result.loc[mask, "exit_reminder_discord_url"] = _discord_url(receipt)
        result.loc[mask, "exit_reminded_at"] = now
        result.loc[mask, "updated_at"] = now
    return result, payloads
