"""Dedicated, idempotent Discord notification adapter for beta detections."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from .config import SELECTOR_ORDER, selector_info


WEBHOOK_ENV = "WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL"
CHANNEL_ID = "1550876104917520505"
SUMMARY_CHANNEL_ID = "1552256658678218852"
GUILD_ID = "1479418833352785944"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DAILY_NOTIFICATION_STATE = ROOT / "weak_early_beta" / "state" / "daily_notifications.json"


def _discord_url(response: dict[str, Any]) -> str:
    guild_id = response.get("guild_id") or GUILD_ID
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


def _message(group: pd.DataFrame, report_url: str = "") -> dict[str, Any]:
    first = group.iloc[0]
    order = {selector_id: index for index, selector_id in enumerate(SELECTOR_ORDER)}
    modes = (
        group[["selector_id", "selector_name"]]
        .drop_duplicates("selector_id")
        .assign(_order=lambda frame: frame["selector_id"].map(order).fillna(len(order)))
        .sort_values("_order", kind="mergesort")
    )
    names = " / ".join(selector_info(selector_id).display_name for selector_id in modes["selector_id"])
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
    embed["url"] = f"https://jp.tradingview.com/chart/?symbol=TSE%3A{first['symbol']}"
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


def _post_webhook(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        webhook_url + ("&" if "?" in webhook_url else "?") + "wait=true",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _post_bot(channel_id: str, bot_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers={"authorization": f"Bot {bot_token}"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _message_id_from_url(value: Any) -> str:
    return str(value or "").rstrip("/").rsplit("/", 1)[-1]


def notify_pending(
    ledger: pd.DataFrame,
    report_url: str = "",
    webhook_url: str | None = None,
    dry_run: bool = False,
    signal_date: Any | None = None,
    refresh_existing: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    webhook_url = (webhook_url or os.environ.get(WEBHOOK_ENV, "")).strip()
    bot_token = (
        os.environ.get("WEAK_EARLY_BETA_DISCORD_BOT_TOKEN")
        or ""
    ).strip()
    eligible = ledger["source_scope"].eq("FORWARD_CAUSAL")
    if signal_date is not None:
        eligible &= pd.to_datetime(ledger["signal_date"]).eq(pd.Timestamp(signal_date))
    if not refresh_existing:
        eligible &= ledger["notified_at"].fillna("").astype(str).str.strip().eq("")
    pending = ledger[eligible].copy()
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
        stored_urls = group["signal_discord_url"].fillna("").astype(str).str.strip()
        stored_url = next((value for value in stored_urls if value), "")
        existing_message = (
            None if refresh_existing and stored_url
            else _existing_message(signal_date, str(symbol), bot_token)
        )
        if refresh_existing and stored_url:
            receipt = edit_webhook_message(webhook_url, _message_id_from_url(stored_url), payload)
        elif existing_message:
            receipt = edit_webhook_message(webhook_url, str(existing_message["id"]), payload)
        else:
            receipt = _post_webhook(webhook_url, payload)
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


def daily_summary_payload(
    ledger: pd.DataFrame,
    target_date: Any,
    report_url: str,
    source_scope: str = "FORWARD_CAUSAL",
) -> dict[str, Any]:
    """Build the dated, per-mode result and HTML links for the summary channel."""
    if not report_url:
        raise ValueError("WEAK_EARLY_BETA_REPORT_URL is required for the Cloud summary")
    date_key = f"{pd.Timestamp(target_date):%Y-%m-%d}"
    dated = ledger[
        ledger["source_scope"].eq(source_scope)
        & pd.to_datetime(ledger["signal_date"]).eq(pd.Timestamp(target_date))
    ]
    unique_count = int(dated["symbol"].astype(str).nunique())
    fields = [{"name": "重複を除いた検出銘柄", "value": f"{unique_count}件", "inline": False}]
    modes_by_count: dict[int, list[str]] = {}
    for selector_id in SELECTOR_ORDER:
        count = int(dated.loc[dated["selector_id"].eq(selector_id), "symbol"].astype(str).nunique())
        modes_by_count.setdefault(count, []).append(selector_info(selector_id).display_name)
    breakdown = "全モード0件" if unique_count == 0 else "\n".join(
        f"**{count}件**｜{'・'.join(modes_by_count[count])}"
        for count in sorted(modes_by_count, reverse=True)
    )
    fields.extend([
        {"name": "モード別内訳", "value": breakdown, "inline": False},
        {"name": "検出銘柄一覧", "value": f"[最新情報をチェック]({urljoin(report_url, 'weak_early_beta_latest.html')})", "inline": False},
    ])
    return {
        "content": "",
        "embeds": [{
            "title": f"天底極致 -Cloud- | {date_key} 検出結果",
            "description": "5モードの件数です。同じ銘柄が複数モードに該当する場合があります。",
            "url": urljoin(report_url, "weak_early_beta_latest.html"),
            "color": 0x4169E1,
            "fields": fields,
        }],
        "allowed_mentions": {"parse": []},
    }


def notify_daily_completion(
    ledger: pd.DataFrame,
    target_date: Any,
    report_url: str,
    state_path: Path = DEFAULT_DAILY_NOTIFICATION_STATE,
    bot_token: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Post one idempotent summary Embed to the dedicated update channel."""
    token = (bot_token or os.environ.get("WEAK_EARLY_BETA_DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or "").strip()
    if not dry_run and not token:
        raise RuntimeError("a Discord bot token is required for the Cloud summary channel")
    date_key = f"{pd.Timestamp(target_date):%Y-%m-%d}"
    state = {"version": 1, "days": {}}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    day_state = state.setdefault("days", {}).setdefault(date_key, {})
    if day_state.get("summary_url"):
        return []
    payload = daily_summary_payload(ledger, target_date, report_url)
    if dry_run:
        return [payload]
    receipt = _post_bot(SUMMARY_CHANNEL_ID, token, payload)
    day_state["summary_url"] = _discord_url(receipt) or str(receipt.get("id", ""))
    day_state["updated_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [payload]


def notify_exclusion_corrections(
    excluded: pd.DataFrame,
    webhook_url: str | None = None,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Patch an already-posted signal into a clear JPX exclusion correction."""
    webhook_url = (webhook_url or os.environ.get(WEBHOOK_ENV, "")).strip()
    if not dry_run and not webhook_url:
        raise RuntimeError(f"{WEBHOOK_ENV} is required for live beta notifications")
    result = excluded.copy()
    for column in ("exclusion_correction_notified_at", "exclusion_correction_discord_url"):
        if column not in result:
            result[column] = ""
    payloads: list[dict[str, Any]] = []
    for (signal_date, symbol), group in result.groupby(["signal_date", "symbol"], sort=True):
        if group["exclusion_correction_notified_at"].fillna("").astype(str).str.strip().ne("").any():
            continue
        first = group.iloc[0]
        message_url = next(
            (str(value).strip() for value in group["signal_discord_url"] if pd.notna(value) and str(value).strip()),
            "",
        )
        if not message_url:
            continue
        company = str(first.get("company_name", "") or "").strip()
        designated = str(first.get("restriction_designation_date", "") or "")
        source_url = str(first.get("restriction_source_url", "") or "")
        payload = {
            "content": "",
            "embeds": [{
                "title": f"{symbol} {company}（Cloud対象外）".strip(),
                "description": "JPXで上場廃止が決定し、整理銘柄に指定されていたため、Cloudの検出対象から除外しました。",
                "url": source_url,
                "color": 0xF04438,
                "fields": [
                    {"name": "当初の検出日", "value": f"{pd.Timestamp(signal_date):%Y-%m-%d}", "inline": True},
                    {"name": "整理銘柄指定日", "value": designated, "inline": True},
                ],
                "footer": {"text": "検出履歴・売却リマインダーから除外済みです"},
            }],
            "allowed_mentions": {"parse": []},
        }
        payloads.append(payload)
        if dry_run:
            continue
        receipt = edit_webhook_message(webhook_url, _message_id_from_url(message_url), payload)
        mask = (
            pd.to_datetime(result["signal_date"]).eq(pd.Timestamp(signal_date))
            & result["symbol"].astype(str).eq(str(symbol))
        )
        result.loc[mask, "exclusion_correction_notified_at"] = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
        result.loc[mask, "exclusion_correction_discord_url"] = _discord_url(receipt) or message_url
    return result, payloads
