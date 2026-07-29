#!/usr/bin/env python3
"""Send the report-ready Discord notice with message-level deduplication."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


NOTICE_TITLE = "✅ OHLCVデータ同期完了"
NOTICE_FIELD_NAME = "🤖 スコアリングレポート"
NOTICE_FIELD_VALUE = (
    "最新の分析結果は `/scan` または "
    "[ブラウザ](https://scoring-bot-report.ipo-ken5-5489.workers.dev/) "
    "にてご確認いただけます。"
)
NOTICE_FOOTER = "天底極致 OHLCV同期"
DEFAULT_DEDUP_SECONDS = 15 * 60
DISCORD_API_BASE = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (screening-bot, 1.0)"


class DiscordRequestError(RuntimeError):
    """Raised when Discord does not return an expected success response."""


RequestJson = Callable[[str, str, dict[str, str], dict[str, Any] | None], Any]


def build_notice_embed(now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "title": NOTICE_TITLE,
        "color": 0x2ECC71,
        "fields": [
            {
                "name": NOTICE_FIELD_NAME,
                "value": NOTICE_FIELD_VALUE,
                "inline": False,
            }
        ],
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "footer": {"text": NOTICE_FOOTER},
    }


def _normalized_webhook_url(webhook_url: str) -> str:
    parsed = urllib.parse.urlsplit(webhook_url.strip())
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _with_wait(webhook_url: str) -> str:
    parsed = urllib.parse.urlsplit(webhook_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "wait"]
    query.append(("wait", "true"))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _message_matches_notice(message: dict[str, Any]) -> bool:
    embeds = message.get("embeds")
    if not isinstance(embeds, list) or not embeds:
        return False
    embed = embeds[0] if isinstance(embeds[0], dict) else {}
    fields = embed.get("fields")
    field = fields[0] if isinstance(fields, list) and fields and isinstance(fields[0], dict) else {}
    footer = embed.get("footer") if isinstance(embed.get("footer"), dict) else {}
    return (
        embed.get("title") == NOTICE_TITLE
        and field.get("name") == NOTICE_FIELD_NAME
        and field.get("value") == NOTICE_FIELD_VALUE
        and footer.get("text") == NOTICE_FOOTER
    )


def recent_matching_notices(
    messages: list[dict[str, Any]],
    *,
    now: datetime,
    dedup_seconds: int,
) -> list[dict[str, Any]]:
    current = now.astimezone(timezone.utc)
    cutoff = current - timedelta(seconds=dedup_seconds)
    clock_skew_ceiling = current + timedelta(seconds=60)
    matches: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict) or not _message_matches_notice(message):
            continue
        created_at = _parse_timestamp(message.get("timestamp"))
        if created_at is None or created_at < cutoff or created_at > clock_skew_ceiling:
            continue
        matches.append(message)
    return sorted(matches, key=lambda item: str(item.get("timestamp") or ""))


def _http_json(
    url: str,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"User-Agent": USER_AGENT, **headers}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_body = response.read()
            if response.status not in (200, 201, 204):
                raise DiscordRequestError(f"Discord returned HTTP {response.status}")
            return json.loads(response_body.decode("utf-8")) if response_body else None
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise DiscordRequestError(f"Discord returned HTTP {exc.code}: {response_body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise DiscordRequestError(f"Discord request failed: {exc.reason}") from exc
    except OSError as exc:
        raise DiscordRequestError(f"Discord request failed: {exc}") from exc


def send_report_ready_notice(
    webhook_url: str,
    bot_token: str,
    *,
    dedup_seconds: int = DEFAULT_DEDUP_SECONDS,
    now: datetime | None = None,
    request_json: RequestJson = _http_json,
) -> str:
    """Send once, returning ``sent``, ``skipped_duplicate``, or ``removed_duplicate``."""

    if not webhook_url.strip():
        raise ValueError("Discord report webhook URL is required")
    if not bot_token.strip():
        raise ValueError("Discord bot token is required for duplicate-safe report notices")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    base_webhook_url = _normalized_webhook_url(webhook_url)
    webhook = request_json(base_webhook_url, "GET", {}, None)
    if not isinstance(webhook, dict) or not webhook.get("id") or not webhook.get("channel_id"):
        raise DiscordRequestError("Discord webhook metadata did not include id and channel_id")

    auth_headers = {"Authorization": f"Bot {bot_token}"}
    messages_url = f"{DISCORD_API_BASE}/channels/{webhook['channel_id']}/messages?limit=50"
    before = request_json(messages_url, "GET", auth_headers, None)
    if not isinstance(before, list):
        raise DiscordRequestError("Discord recent-message response was not a list")
    if recent_matching_notices(before, now=current, dedup_seconds=dedup_seconds):
        return "skipped_duplicate"

    sent = request_json(
        _with_wait(base_webhook_url),
        "POST",
        {},
        {"embeds": [build_notice_embed(current)]},
    )
    if not isinstance(sent, dict) or not sent.get("id"):
        raise DiscordRequestError("Discord did not return the sent message id")

    after = request_json(messages_url, "GET", auth_headers, None)
    if not isinstance(after, list):
        raise DiscordRequestError("Discord post-send recent-message response was not a list")
    matches = recent_matching_notices(after, now=current, dedup_seconds=dedup_seconds)
    if len(matches) <= 1:
        return "sent"

    oldest_id = str(matches[0].get("id") or "")
    sent_id = str(sent["id"])
    if sent_id != oldest_id:
        request_json(f"{base_webhook_url}/messages/{sent_id}", "DELETE", {}, None)
        return "removed_duplicate"

    own_webhook_id = str(webhook["id"])
    for duplicate in matches[1:]:
        duplicate_id = str(duplicate.get("id") or "")
        if duplicate_id and str(duplicate.get("webhook_id") or "") == own_webhook_id:
            request_json(f"{base_webhook_url}/messages/{duplicate_id}", "DELETE", {}, None)
    return "sent"


def main() -> int:
    webhook_url = (
        os.environ.get("DISCORD_REPORT_WEBHOOK_URL")
        or os.environ.get("DISCORD_WEBHOOK_URL")
        or os.environ.get("DISCORD_WEBHOOK")
        or ""
    ).strip()
    bot_token = (os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or "").strip()
    if not webhook_url:
        print("DISCORD_REPORT_WEBHOOK_URL is not set; skipping report-ready Discord notice")
        return 0
    dedup_seconds = int(os.environ.get("REPORT_READY_NOTICE_DEDUP_SECONDS", DEFAULT_DEDUP_SECONDS))
    try:
        result = send_report_ready_notice(
            webhook_url,
            bot_token,
            dedup_seconds=max(1, dedup_seconds),
        )
    except (DiscordRequestError, ValueError) as exc:
        print(f"::warning::Report-ready Discord notice was not sent safely: {exc}")
        return 0
    if result == "skipped_duplicate":
        print("Skipped duplicate report-ready Discord notice")
    elif result == "removed_duplicate":
        print("Removed the duplicate report-ready Discord notice sent by this run")
    else:
        print("Sent report-ready Discord notice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
