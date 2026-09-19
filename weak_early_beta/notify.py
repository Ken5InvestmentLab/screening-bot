"""Dedicated, idempotent Discord notification adapter for beta detections."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests


WEBHOOK_ENV = "WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL"
CHANNEL_ID = "1550876104917520505"


def _discord_url(response: dict[str, Any]) -> str:
    guild_id = response.get("guild_id") or "@me"
    channel_id = response.get("channel_id")
    message_id = response.get("id")
    if not channel_id or not message_id:
        return ""
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def _message(group: pd.DataFrame, report_url: str) -> dict[str, Any]:
    first = group.iloc[0]
    names = " / ".join(sorted(group["selector_name"].astype(str).unique()))
    units = int(group["selector_id"].nunique())
    company = str(first.get("company_name", "") or "").strip()
    symbol_label = f"{first['symbol']} {company}".strip()
    marker = f"WEAK_EARLY_BETA:{pd.Timestamp(first['signal_date']):%Y-%m-%d}|{first['symbol']}"
    content = (
        f"**Weak+Early ベータ検出**\n"
        f"銘柄: **{symbol_label}**\n"
        f"シグナル日: {pd.Timestamp(first['signal_date']):%Y-%m-%d}\n"
        f"該当条件: {names}\n"
        f"条件別積上げ換算: {units}ユニット / {units * 100}株\n"
        "売買評価: 翌営業日寄付 → 5営業日目終値（100株・コスト0%）\n"
        f"||{marker}||"
    )
    if report_url:
        content += f"\n履歴と成績: {report_url}"
    return {"content": content, "allowed_mentions": {"parse": []}}


def _existing_message(marker: str, bot_token: str) -> dict[str, Any] | None:
    if not bot_token:
        return None
    response = requests.get(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=100",
        headers={"authorization": f"Bot {bot_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return next((message for message in response.json() if marker in str(message.get("content", ""))), None)


def notify_pending(
    ledger: pd.DataFrame,
    report_url: str = "",
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    webhook_url = (webhook_url or os.environ.get(WEBHOOK_ENV, "")).strip()
    bot_token = (
        os.environ.get("WEAK_EARLY_BETA_DISCORD_BOT_TOKEN")
        or ""
    ).strip()
    pending = ledger[
        ledger["source_scope"].eq("FORWARD_CAUSAL")
        & ledger["notified_at"].fillna("").astype(str).str.strip().eq("")
    ].copy()
    payloads: list[dict[str, Any]] = []
    result = ledger.copy()
    if pending.empty:
        return result, payloads
    if not dry_run and not webhook_url:
        raise RuntimeError(f"{WEBHOOK_ENV} is required for live beta notifications")
    for (signal_date, symbol), group in pending.groupby(["signal_date", "symbol"], sort=True):
        payload = _message(group, report_url)
        payloads.append(payload)
        if dry_run:
            continue
        marker = f"WEAK_EARLY_BETA:{pd.Timestamp(signal_date):%Y-%m-%d}|{symbol}"
        existing_message = _existing_message(marker, bot_token)
        if existing_message:
            receipt = existing_message
        else:
            response = requests.post(
                webhook_url + ("&" if "?" in webhook_url else "?") + "wait=true",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            receipt = response.json()
        url = _discord_url(receipt)
        mask = (
            pd.to_datetime(result["signal_date"]).eq(pd.Timestamp(signal_date))
            & result["symbol"].astype(str).eq(str(symbol))
            & result["source_scope"].eq("FORWARD_CAUSAL")
        )
        now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
        result.loc[mask, "signal_discord_url"] = url
        result.loc[mask, "notified_at"] = now
        result.loc[mask, "updated_at"] = now
    return result, payloads
