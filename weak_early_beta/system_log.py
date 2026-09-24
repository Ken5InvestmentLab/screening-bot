"""Admin-only Discord events for the Cloud daily runner and its watchdog."""

from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .bank_calendar import is_bank_business_day


CHANNEL_ID = "1480210812457975839"
API = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
IDENTITY = "WEAK_EARLY_CLOUD_DAILY_V1"
JST = ZoneInfo("Asia/Tokyo")
SCHEDULED_START = time(17, 0)
WATCH_TIME = time(17, 30)


def _token(value: str | None = None) -> str:
    result = (value or os.environ.get("WEAK_EARLY_BETA_DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or "").strip()
    if not result:
        raise RuntimeError("Cloud system log requires a Discord bot token")
    return result


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bot {token}"}


def _marker(day: date, event: str, run_id: str) -> str:
    return f"{IDENTITY}|{day.isoformat()}|{event}|{run_id}"


def _recent(day: date, token: str) -> list[dict[str, Any]]:
    """Read a bounded slice of the admin channel, including all recent daily events."""
    cutoff = datetime.combine(day, time.min, tzinfo=JST)
    before = ""
    messages: list[dict[str, Any]] = []
    for _ in range(5):
        params: dict[str, str | int] = {"limit": 100}
        if before:
            params["before"] = before
        response = requests.get(API, headers=_headers(token), params=params, timeout=30)
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        messages.extend(page)
        oldest = page[-1]
        stamp = oldest.get("timestamp")
        if stamp and datetime.fromisoformat(stamp.replace("Z", "+00:00")) < cutoff:
            break
        before = str(oldest["id"])
    return messages


def _has_marker(messages: list[dict[str, Any]], marker: str) -> bool:
    return any(
        embed.get("footer", {}).get("text") == marker
        for message in messages
        for embed in message.get("embeds", [])
    )


def _payload(day: date, event: str, run_id: str, *, stage: str = "", detail: str = "", count: int | None = None) -> dict[str, Any]:
    titles = {
        "started": "Cloud 起動",
        "detected": "Cloud 検出終了",
        "error": "Cloud エラー停止",
        "missed": "Cloud 定時起動を確認できません",
    }
    if event not in titles:
        raise ValueError(f"unsupported Cloud event: {event}")
    if event == "started":
        description = "Cloudの日次処理を開始しました。"
    elif event == "detected":
        description = f"検出処理が終了しました。該当モードの延べ検出件数: {count if count is not None else '不明'}件。"
    elif event == "error":
        description = f"処理を停止しました。\n停止段階: {stage or '不明'}\n原因: {detail[:500] or '不明'}"
    else:
        description = (
            f"{SCHEDULED_START:%H:%M}の定時起動の記録が"
            f"{WATCH_TIME:%H:%M}時点で確認できません。起動状況を確認してください。"
        )
    return {
        "content": "",
        "embeds": [{
            "title": f"{titles[event]} | {day.isoformat()}",
            "description": description,
            "color": 0xF04438 if event in {"error", "missed"} else 0x4169E1,
            "footer": {"text": _marker(day, event, run_id)},
        }],
        "allowed_mentions": {"parse": []},
    }


def post_event(
    day: date, event: str, run_id: str, *, stage: str = "", detail: str = "",
    count: int | None = None, token: str | None = None,
) -> dict[str, Any]:
    bot_token = _token(token)
    marker = _marker(day, event, run_id)
    if _has_marker(_recent(day, bot_token), marker):
        return {"posted": False, "duplicate": True}
    response = requests.post(
        API, headers=_headers(bot_token),
        json=_payload(day, event, run_id, stage=stage, detail=detail, count=count),
        timeout=30,
    )
    response.raise_for_status()
    message_id = str(response.json()["id"])
    verified = requests.get(f"{API}/{message_id}", headers=_headers(bot_token), timeout=30)
    verified.raise_for_status()
    if not _has_marker([verified.json()], marker):
        raise RuntimeError("Cloud system log post could not be verified")
    return {"posted": True, "duplicate": False, "message_id": message_id}


def watch_missed(now: datetime | None = None, *, token: str | None = None) -> dict[str, Any]:
    current = (now or datetime.now(JST)).astimezone(JST)
    day = current.date()
    if not is_bank_business_day(day):
        return {"posted": False, "skipped": "bank_holiday"}
    if (current.hour, current.minute) < (WATCH_TIME.hour, WATCH_TIME.minute):
        return {"posted": False, "skipped": "before_watch_time"}
    bot_token = _token(token)
    start_prefix = f"{IDENTITY}|{day.isoformat()}|started|"
    messages = _recent(day, bot_token)
    if any(
        str(embed.get("footer", {}).get("text", "")).startswith(start_prefix)
        for message in messages for embed in message.get("embeds", [])
    ):
        return {"posted": False, "skipped": "started"}
    return post_event(day, "missed", "schedule-1700", token=bot_token)
