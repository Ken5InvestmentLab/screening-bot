"""Dedicated, idempotent Discord notification adapter for beta detections."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

from .config import SELECTOR_ORDER


WEBHOOK_ENV = "WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL"
CHANNEL_ID = "1550876104917520505"


def _discord_url(response: dict[str, Any]) -> str:
    guild_id = response.get("guild_id") or "@me"
    channel_id = response.get("channel_id")
    message_id = response.get("id")
    if not channel_id or not message_id:
        return ""
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


EMBED_COLORS = {
    1: 0x5B8DEF,
    2: 0x27B7C7,
    3: 0x2ECC71,
    4: 0xF39C12,
    5: 0x9B59B6,
}


def _number(value: Any, suffix: str = "") -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "—" if pd.isna(numeric) else f"{float(numeric):,.0f}{suffix}"


def _message(group: pd.DataFrame, report_url: str) -> dict[str, Any]:
    first = group.iloc[0]
    order = {selector_id: index for index, selector_id in enumerate(SELECTOR_ORDER)}
    modes = (
        group[["selector_id", "selector_name"]]
        .drop_duplicates("selector_id")
        .assign(_order=lambda frame: frame["selector_id"].map(order).fillna(len(order)))
        .sort_values("_order", kind="mergesort")
    )
    names = " / ".join(modes["selector_name"].astype(str))
    units = int(group["selector_id"].nunique())
    company = str(first.get("company_name", "") or "").strip()
    symbol_label = f"{first['symbol']} {company}".strip()
    embed: dict[str, Any] = {
        "title": symbol_label,
        "color": EMBED_COLORS.get(min(max(units, 1), 5), EMBED_COLORS[5]),
        "fields": [
            {
                "name": "検出日",
                "value": f"{pd.Timestamp(first['signal_date']):%Y-%m-%d}",
                "inline": True,
            },
            {
                "name": "検出時点の終値",
                "value": _number(first.get("signal_close"), "円"),
                "inline": True,
            },
            {
                "name": "当日の出来高",
                "value": _number(first.get("signal_volume"), "株"),
                "inline": True,
            },
            {"name": "該当モード数", "value": f"{units}モード", "inline": True},
            {"name": "該当モード", "value": names, "inline": False},
        ],
        "footer": {"text": "色は該当モード数を表します"},
    }
    if report_url:
        embed["url"] = report_url
    # Discord PATCH keeps omitted fields, so an explicit empty content value is
    # required when upgrading an older text notification to an embed.
    return {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}}


def _existing_message(signal_date: Any, symbol: str, bot_token: str) -> dict[str, Any] | None:
    if not bot_token:
        return None
    response = requests.get(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=100",
        headers={"authorization": f"Bot {bot_token}"},
        timeout=30,
    )
    response.raise_for_status()
    expected_date = f"{pd.Timestamp(signal_date):%Y-%m-%d}"
    for message in response.json():
        for embed in message.get("embeds", []):
            title = str(embed.get("title", ""))
            fields = {str(field.get("name", "")): str(field.get("value", "")) for field in embed.get("fields", [])}
            if title.startswith(str(symbol)) and fields.get("検出日") == expected_date:
                return message
    return None


def edit_webhook_message(webhook_url: str, message_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Replace a beta webhook message without creating a duplicate."""
    response = requests.patch(
        f"{webhook_url.rstrip('/')}/messages/{message_id}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


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
        existing_message = _existing_message(signal_date, str(symbol), bot_token)
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
