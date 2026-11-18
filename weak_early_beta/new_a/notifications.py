"""Send one New A Discord result through the existing detection webhook."""

import csv
import datetime
import io
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .files import digest, encode, read
from .outbox import ATTEMPTED, Outbox, eligible


SUMMARY = "DAILY_SUMMARY"
DELAYED = "DELAYED_SCHEDULED_OBSERVATION"
FOOTER_PREFIX = "A_BASE | daily batch | "
JST = datetime.timezone(datetime.timedelta(hours=9))
DISCORD_HEADERS = {"User-Agent": "DiscordBot (screening-bot, 1.0)"}


def _counts(rows):
    return {
        "signal_notifications": sum(payload.get("kind") != SUMMARY for _, payload, _ in rows),
        "completion_notifications": sum(payload.get("kind") == SUMMARY for _, payload, _ in rows),
    }


def _attachment(date, chart_links):
    file = io.StringIO(newline="")
    writer = csv.writer(file)
    writer.writerow(["検出日", "証券コード", "TradingView"])
    writer.writerows((date, symbol, url) for symbol, url in chart_links)
    return {"filename": f"cloud-new-a-{date}.csv", "text": "\ufeff" + file.getvalue()}


def _delivery_sha(batch):
    embed = batch["payload"]["embeds"][0]
    return digest({
        **batch, "batch_id": "",
        "payload": {**batch["payload"], "embeds": [{**embed, "footer": None}]},
    })


def _batch(snapshot, rows, report_url):
    from ..notify import chart_components

    date = snapshot["as_of"]
    pending = [row for row in rows if row[2] == "PENDING"]
    counts = _counts(pending)
    symbols = sorted({payload["symbol"] for _, payload, _ in pending if payload.get("kind") != SUMMARY})
    chart_links = [(symbol, chart_components(symbol)[0]["components"][0]["url"]) for symbol in symbols]
    delayed = snapshot["observation_kind"] == DELAYED
    fields = [{"name": "検出日", "value": date, "inline": True}]
    if delayed:
        observed = datetime.datetime.fromisoformat(snapshot["observed_at"]).astimezone(JST)
        fields.append({"name": "実際の観測日時（日本時間）", "value": observed.strftime("%Y-%m-%d %H:%M:%S")})
    if counts["completion_notifications"]:
        total = len({payload["symbol"] for _, payload, _ in rows if payload.get("kind") != SUMMARY})
        fields.extend([
            {"name": "新規検出", "value": f"{total}銘柄", "inline": True},
            {"name": "判定保留", "value": f"{len(snapshot.get('held_symbols', {}))}銘柄", "inline": True},
        ])
    embed = {
        "title": "Cloud 2.0 新A 日次検出" + ("（遅延実行）" if delayed else ""),
        "url": urljoin(report_url, "weak_early_beta_latest.html"),
        "fields": fields,
        "color": 0x5B8DEF,
    }
    attachment = None
    if chart_links:
        lines = [f"[{symbol}]({url})" for symbol, url in chart_links]
        heading = f"**検出一覧（{len(symbols)}銘柄）**\n仕込み候補・監視開始（未約定）\n"
        description = heading + " ・ ".join(lines)
        if len(description) > 4096:
            attachment = _attachment(date, chart_links)
            description = heading + "全銘柄のチャートリンクは添付CSVをご覧ください。\n" + " ・ ".join(lines[:8])
        embed["description"] = description
    payload = {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}}
    if attachment is not None:
        payload["attachments"] = [{"id": 0, "filename": attachment["filename"]}]
    batch = {
        "batch_id": "", "signal_date": date, "event_ids": [event_id for event_id, _, _ in pending],
        "snapshot_sha256": snapshot["payload_sha256"], "source_sha256": snapshot["source_sha256"],
        "observation_kind": snapshot["observation_kind"], "observed_at": snapshot.get("observed_at"),
        "payload": payload, "attachment": attachment, **counts,
    }
    batch["batch_id"] = _delivery_sha(batch)
    embed["footer"] = {"text": FOOTER_PREFIX + batch["batch_id"]}
    return batch


def _signal_webhook():
    from .. import notify

    target = urlparse(os.environ.get(notify.WEBHOOK_ENV, "").strip())
    match = re.fullmatch(r"/api/(?:v\d+/)?webhooks/(\d+)/[A-Za-z0-9_.-]+/?", target.path)
    if (target.scheme != "https" or target.netloc not in {"discord.com", "discordapp.com"}
            or not match or target.query or target.fragment):
        raise RuntimeError("existing_signal_transport_unavailable")
    return target.geturl(), match[1]


def _verify_destination(url, webhook_id):
    from .. import notify

    try:
        response = notify.requests.get(
            url, headers=DISCORD_HEADERS, allow_redirects=False, timeout=30,
        )
        metadata = response.json() if response.status_code == 200 else {}
        if (str(metadata.get("id")) == webhook_id
                and str(metadata.get("guild_id")) == notify.GUILD_ID
                and str(metadata.get("channel_id")) == notify.CHANNEL_ID):
            return
    except Exception:
        pass
    raise RuntimeError("existing_signal_destination_unverified")

def _field_values(embed):
    return [(f.get("name"), f.get("value"), bool(f.get("inline"))) for f in embed.get("fields", [])]


def _matches_discord(message, batch, *, webhook_id, channel_id):
    if (not isinstance(message, dict) or not re.fullmatch(r"\d+", str(message.get("id", "")))
            or str(message.get("channel_id")) != channel_id
            or str(message.get("webhook_id")) != webhook_id
            or message.get("content") != batch["payload"]["content"]):
        return False
    embeds = message.get("embeds", [])
    if len(embeds) != 1:
        return False
    expected = batch["payload"]["embeds"][0]
    actual = embeds[0]
    if (any(actual.get(key) != expected.get(key) for key in ("title", "url", "description", "color"))
            or actual.get("footer", {}).get("text") != FOOTER_PREFIX + batch["batch_id"]
            or _field_values(actual) != _field_values(expected)):
        return False
    attachments = [(file.get("filename"), file.get("size")) for file in message.get("attachments", [])]
    file = batch["attachment"]
    return attachments == ([(file["filename"], len(file["text"].encode("utf-8")))] if file else [])


def default_transport():
    from .. import notify

    url, webhook_id = _signal_webhook()
    _verify_destination(url, webhook_id)

    def send(batch):
        try:
            file = batch["attachment"]
            body = {"json": batch["payload"]}
            if file is not None:
                body = {
                    "data": {"payload_json": encode(batch["payload"])},
                    "files": {"files[0]": (file["filename"], file["text"].encode("utf-8"), "text/csv")},
                }
            response = notify.requests.post(
                url, params={"wait": "true", "with_components": "true"}, headers=DISCORD_HEADERS,
                allow_redirects=False, timeout=30, **body,
            )
            message = response.json() if response.status_code == 200 else None
            if _matches_discord(message, batch, webhook_id=webhook_id, channel_id=notify.CHANNEL_ID):
                return {"confirmed": True, "message_id": str(message["id"])}
        except Exception:
            raise RuntimeError("existing_notification_transport_failed_reconcile_before_retry") from None
        return {"confirmed": False}

    return send

def _lookup_discord(batch):
    from .. import notify

    _, webhook_id = _signal_webhook()
    token = (os.environ.get("WEAK_EARLY_BETA_DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or "").strip()
    if not token:
        raise ValueError("notification outcome unconfirmed; existing Discord history access required")
    try:
        response = notify.requests.get(
            f"https://discord.com/api/v10/channels/{notify.CHANNEL_ID}/messages",
            params={"limit": 100}, headers={**DISCORD_HEADERS, "authorization": f"Bot {token}"},
            allow_redirects=False, timeout=30,
        )
        if response.status_code != 200:
            raise ValueError("unexpected Discord history status")
        matches = [
            message for message in response.json()
            if _matches_discord(message, batch, webhook_id=webhook_id, channel_id=notify.CHANNEL_ID)
        ]
    except Exception:
        raise ValueError("notification outcome unconfirmed; Discord history lookup failed") from None
    if len(matches) == 1:
        return str(matches[0]["id"])
    raise ValueError("notification outcome unconfirmed; expected one exact Discord message")


def notify_day(root, *, date, dry_run, report_url, transport=None, reconcile_only=False):
    if dry_run and reconcile_only:
        raise ValueError("choose either dry run or Discord reconciliation")
    root = Path(root).resolve()
    run = read(root / "latest-run.json")
    snapshot = read(run["snapshot_file"])
    publication = read(root / "latest-publication.json")
    from .operational_admission import action_context, publication_gate_verified

    def verify_finite_admission():
        if publication.get("operational_gate_continuity_verified") is True:
            action_context(
                root.parents[2], date=date, run=run, snapshot=snapshot, publication=publication, required=True,
            )

    verify_finite_admission()
    if (date != snapshot["as_of"] or run["strategy"] != "A_BASE"
            or run["snapshot_sha256"] != snapshot["payload_sha256"]):
        raise ValueError("matching New A daily snapshot required")
    if (digest({k: v for k, v in snapshot.items() if k != "payload_sha256"}) != snapshot["payload_sha256"]
            or run["source_sha256"] != snapshot["source_sha256"]
            or run["source_version"] != publication.get("source_version")):
        raise ValueError("private notification source bytes changed")
    kind = snapshot["observation_kind"]
    local_historical_preview = (
        dry_run and kind == "DRY_RUN_HISTORICAL" and publication.get("local_d1_emulation") is True
    )
    if (publication.get("snapshot_sha256") != snapshot["payload_sha256"]
            or publication.get("active_readback_verified") is not True
            or (not local_historical_preview
                and (not publication_gate_verified(publication) or publication.get("published") is not True))):
        raise ValueError("verified private publication required")
    if kind == DELAYED:
        from .delayed_recovery import delivery_context
        delivery_context(root.parents[2], snapshot, publication)
    if not dry_run and kind not in {"LIVE_OBSERVATION", DELAYED}:
        raise ValueError("historical/catchup notifications prohibited")
    summary = None
    signals = eligible(snapshot)
    if kind in {"LIVE_OBSERVATION", DELAYED}:
        count_field = "delayed_scheduled_signals" if kind == DELAYED else "new_live_signals"
        if (snapshot.get("data_status") not in {"COMPLETED", "COMPLETED_WITH_HELD_SYMBOLS"}
                or snapshot.get(count_field) != len(signals)):
            raise ValueError("completed New A detection result required")
    if signals:
        summary = {
            "kind": SUMMARY, "event_id": digest(["A_BASE", date, SUMMARY]), "signal_date": date,
            "count": len({event["symbol"] for event in signals}), "strategy": "A_BASE",
            "signal_phase": "WATCH_STARTED", "execution_status": "NOT_EXECUTED",
        }
        if kind == DELAYED:
            summary.update(
                observation_kind=kind, observed_at=snapshot["observed_at"],
                delayed_recovery=snapshot["delayed_recovery"],
            )

    outbox = Outbox(root / "notification-outbox.sqlite")
    try:
        if not reconcile_only:
            # An empty verified result preserves the previous silent completion behavior.
            outbox.stage(snapshot, publication, existing_notifications_enabled=True, summary=summary)
        rows = outbox.day_rows(date)
        reconciled = False
        if any(status == ATTEMPTED for _, _, status in rows):
            if not reconcile_only:
                raise ValueError("notification outcome unconfirmed; use --reconcile-only before retry")
            batch = outbox.unconfirmed_batch(date)
            if (batch["signal_date"] != date or batch["snapshot_sha256"] != snapshot["payload_sha256"]
                    or _delivery_sha(batch) != batch["batch_id"]):
                raise ValueError("notification batch differs from verified snapshot")
            verify_finite_admission()
            outbox.confirm_batch(batch, _lookup_discord(batch))
            reconciled = True
            rows = outbox.day_rows(date)
            if any(status == ATTEMPTED for _, _, status in rows):
                raise ValueError("other notification outcomes remain unconfirmed")
        counts = _counts([row for row in rows if row[2] == "PENDING"])
        sent = 0
        if not dry_run and not reconcile_only and any(counts.values()):
            target = urlparse(report_url)
            if target.scheme != "https" or not target.netloc:
                raise ValueError("existing Cloud report URL is required before send")
            send = transport or default_transport()
            verify_finite_admission()
            batch = outbox.claim_batch(date, lambda current: _batch(snapshot, current, report_url))
            if batch is not None:
                receipt = send(batch)
                if (not isinstance(receipt, dict) or receipt.get("confirmed") is not True
                        or not isinstance(receipt.get("message_id"), str) or not receipt["message_id"].strip()):
                    raise RuntimeError("notification_unconfirmed_reconcile_before_retry")
                outbox.confirm_batch(batch, receipt["message_id"])
                counts = {name: batch[name] for name in counts}
                sent = 1
            else:
                counts = _counts([])
        result = {
            "date": date, "dry_run": dry_run, **counts, "strategy": "A_BASE",
            "source_sha256": snapshot["source_sha256"], "snapshot_sha256": snapshot["payload_sha256"],
            "old_ledger_written": False, "external_sends": sent,
            "pending_discord_messages": int((dry_run or reconcile_only) and any(counts.values())),
        }
        if reconcile_only:
            result["reconciled_batch"] = reconciled
        return result
    finally:
        outbox.close()
