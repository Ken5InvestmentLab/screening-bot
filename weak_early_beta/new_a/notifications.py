"""Send one New A Discord result through the existing detection webhook."""

import csv
import datetime
import io
import json
import math
import os
import re
import subprocess
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


def _attachment(date, chart_links, entries=None, openings=None):
    file = io.StringIO(newline="")
    writer = csv.writer(file)
    if entries is None and openings is None:
        writer.writerow(["検出日", "証券コード", "TradingView"])
        writer.writerows((date, symbol, url) for symbol, url in chart_links)
    else:
        columns = ["通知種別", "対象日", "証券コード", "TradingView"]
        rows = [("監視開始", date, symbol, url) for symbol, url in chart_links]
        if entries is not None:
            label = "仮想保有開始候補" if "shared_order" in entries else "買付候補（未約定）"
            rows.extend((label, entries["session"], symbol, "") for symbol in entries["symbols"])
        if openings is not None:
            writer.writerow([*columns, "日足始値（円）"])
            writer.writerows((*row, "") for row in rows)
            writer.writerows(_opening_csv_row(date, row) for row in openings["rows"])
        else:
            writer.writerow(columns)
            writer.writerows(rows)
    return {"filename": f"cloud-new-a-{date}.csv", "text": "\ufeff" + file.getvalue()}


def _opening_csv_row(date, row):
    symbol, price = row
    if price is None:
        return ("始値保留", date, symbol, "", "")
    return ("終了後に確認した始値", date, symbol, "", _format_opening_price(price))


def _fresh_ordinary_result(run, snapshot, publication):
    date = snapshot["as_of"]
    return (snapshot["observation_kind"] == "LIVE_OBSERVATION"
            and run.get("identity") == "NEW_A_CLOUD_DAILY_V1"
            and run.get("latest_session") == date and run.get("dry_run") is False
            and run.get("detection_executed") is True and run.get("same_run_replay") is False
            and "delayed_recovery" not in run
            and publication.get("schema") == "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1"
            and publication.get("as_of") == date and publication.get("same_dataset_replay") is False
            and publication.get("existing_owner_gate_verified") is True
            and publication.get("local_d1_emulation") is False
            and publication.get("operational_gate_continuity_verified") in (None, False)
            and "delayed_recovery" not in publication)


def _episode(row):
    symbol, candidate_date, episode = (row.get(key) for key in ("symbol", "candidate_date", "episode_id"))
    if (not isinstance(symbol, str) or not re.fullmatch(r"[0-9A-Z]{4}", symbol)
            or not isinstance(candidate_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate_date)
            or type(episode) is not int or episode <= 0):
        raise ValueError("closing opening episode identity differs")
    datetime.date.fromisoformat(candidate_date)
    return symbol, candidate_date, episode


def _closing_openings(snapshot, events, pending, index, previous_day):
    date = snapshot["as_of"]
    due = {}
    for row in pending:
        identity = _episode(row)
        if (identity in due or row.get("entry_index") != index or row.get("trigger_date") != previous_day
                or identity[1] > previous_day or row.get("execution_status") != "NOT_EXECUTED"):
            raise ValueError("closing opening does not match its preceding market-session episode")
        due[identity] = row

    results = {}
    for event in events:
        identity = _episode(event)
        row = due.pop(identity, None)
        if row is None or event.get("execution_status") != "NOT_EXECUTED":
            raise ValueError("closing opening event lacks a matching pending episode")
        price = event.get("reference_open")
        status = event.get("price_status")
        if status == "HISTORICAL_REFERENCE_ONLY":
            if (type(price) not in (int, float) or not math.isfinite(price) or price <= 0
                    or price != row.get("reference_open") or status != row.get("price_status")):
                raise ValueError("closing opening price differs from the monitor receipt")
        elif status != "UNRESOLVED_OPEN" or price is not None or status != row.get("price_status"):
            raise ValueError("closing opening hold differs from the monitor receipt")
        symbol = identity[0]
        if symbol in results and results[symbol] != price:
            raise ValueError("closing opening price differs between episodes")
        results[symbol] = price

    for (symbol, _, _), row in due.items():
        hold = snapshot.get("held_symbols", {}).get(symbol, {})
        held_day = hold.get("day")
        if (row.get("price_status") == "UNCONFIRMED_NEXT_OPEN" and isinstance(held_day, str)
                and held_day <= date):
            if symbol in results and results[symbol] is not None:
                raise ValueError("closing opening price conflicts with an unresolved episode")
            results[symbol] = None
    if results:
        return {"rows": sorted([symbol, price] for symbol, price in results.items()),
                "snapshot_sha256": snapshot["payload_sha256"]}
    return None


def _shared_trial_order_rule():
    repo = Path(__file__).resolve().parents[2]
    config = repo / ".cache/weak_early_beta/daily-runner.config.json"
    preferences = repo / "weak-early-beta-gate/src/new-a-preferences.ts"
    engine = repo / "weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs"
    script = """
const { SHARED_TRIAL_DEFAULTS, validateTrial } = require(process.argv[1]);
const { trialTerms } = require(process.argv[2]);
const { base_shares, per_order_cap_yen, max_positions } = validateTrial(SHARED_TRIAL_DEFAULTS);
const { daily_fill_cap: profit_daily_fill_cap } = trialTerms("profit");
process.stdout.write(JSON.stringify({ base_shares, per_order_cap_yen, max_positions, profit_daily_fill_cap }));
"""
    try:
        node = read(config)["nodePath"] if config.is_file() else "node"
        if not isinstance(node, str) or not node:
            raise ValueError("existing runner Node runtime unavailable")
        result = subprocess.run(
            [node, "--input-type=commonjs", "-e", script, str(preferences), str(engine)],
            cwd=repo, check=True, capture_output=True, encoding="utf-8", timeout=15,
        )
        order = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise ValueError("shared trial order rule unavailable") from None
    positive_keys = ("base_shares", "per_order_cap_yen", "max_positions")
    if (not isinstance(order, dict) or set(order) != {*positive_keys, "profit_daily_fill_cap"}
            or any(type(order[key]) is not int or order[key] <= 0 for key in positive_keys)):
        raise ValueError("invalid shared trial order rule")
    daily_cap = order["profit_daily_fill_cap"]
    if daily_cap is not None and (type(daily_cap) is not int or daily_cap <= 0):
        raise ValueError("invalid shared trial order rule")
    return order


def _summary_details(root, snapshot):
    from .owner_notice_producer import _verified_calendar

    date = snapshot["as_of"]
    same_observation = [
        event for event in snapshot["events"]
        if event["session"] == date and event.get("observation_kind") == "LIVE_OBSERVATION"
        and event.get("observed_at") == snapshot["observed_at"]
    ]
    candidates = [
        event for event in same_observation if event["kind"] == "ENTRY_CANDIDATE"
        and event.get("trigger_date") == date
        and event.get("execution_status") == "NOT_EXECUTED"
        and event.get("price_status") == "UNCONFIRMED_NEXT_OPEN"
    ]
    openings = [event for event in same_observation if event["kind"] == "REFERENCE_OPEN"]
    state = snapshot.get("monitor_state", {})
    pending = [row for row in state.get("pending_references", []) if row.get("reference_entry_date") == date]
    if not (candidates or openings or pending):
        return {}
    observed = datetime.datetime.fromisoformat(snapshot["observed_at"])
    day = datetime.date.fromisoformat(date)
    close = datetime.datetime.combine(day, datetime.time(15, 30), tzinfo=JST)
    if observed.tzinfo is None or observed < close or observed.astimezone(JST).date() != day:
        raise ValueError("daily notification details require a same-session live observation after close")
    calendar = _verified_calendar(root.parents[2])
    if day not in calendar:
        raise ValueError("verified current market session required")
    index = calendar.index(day)
    details = {}
    if openings or pending:
        if (not index or state.get("schema") != "NEW_A_CURRENT_MONITOR_STATE_V1"
                or state.get("strategy") != "A_BASE" or state.get("actual_fills") is not False):
            raise ValueError("verified closing monitor state required")
        result = _closing_openings(snapshot, openings, pending, index, calendar[index - 1].isoformat())
        if result is not None:
            details["closing_openings"] = result
    if candidates:
        if index + 1 >= len(calendar):
            raise ValueError("verified next market session required for entry candidates")
        next_date = calendar[index + 1].isoformat()
        if any(event.get("reference_entry_date") != next_date
               or not re.fullmatch(r"[0-9A-Z]{4}", event["symbol"]) for event in candidates):
            raise ValueError("entry candidate differs from the verified next market session")
        details["next_session_entries"] = {
            "session": next_date,
            "symbols": sorted({event["symbol"] for event in candidates}),
            "snapshot_sha256": snapshot["payload_sha256"],
            "shared_order": _shared_trial_order_rule(),
            "fixed_zero_cost": True,
        }
    return details


def _format_opening_price(price):
    return f"{price:,.2f}".rstrip("0").rstrip(".")


def _opening_field(openings, attached):
    rows = openings["rows"]
    lines = [
        f"{symbol}　{_format_opening_price(price)}円" if price is not None else f"{symbol}　始値保留"
        for symbol, price in (rows[:10] if attached else rows)
    ]
    if attached:
        lines.append(f"全{len(rows)}銘柄は添付CSV")
    return {"name": "終了後に確認した始値（日足始値）", "value": "\n".join(lines)}

def _entry_field(entries, attached):
    symbols = entries["symbols"]
    shown = "・".join(symbols[:12] if attached else symbols)
    if attached:
        shown += f"（全{len(symbols)}銘柄は添付CSV）"
    if "shared_order" in entries:
        shares = entries["shared_order"]["base_shares"]
        cap = entries["shared_order"]["per_order_cap_yen"]
        max_positions = entries["shared_order"]["max_positions"]
        scaled_limit, remainder = divmod(cap * 100, shares)
        cap_text = f"{cap // 10_000:,}万円" if cap % 10_000 == 0 else f"{cap:,}円"
        if remainder:
            # Retain the exact ratio rather than rounding a nonterminating cap up.
            limit = f"（{cap_text}÷{shares:,}株）以下"
        else:
            limit = f"{scaled_limit // 100:,}.{scaled_limit % 100:02d}".rstrip("0").rstrip(".") + "円以下"
        # Older pending entries keep the exact wording they were staged with.
        cash_rule = "残資金内" if entries.get("fixed_zero_cost") is True else "手数料込みで残資金内"
        daily_cap = entries["shared_order"]["profit_daily_fill_cap"]
        priority = (f"利益優先：優先順で1日最大{daily_cap}件" if daily_cap is not None
                    else "利益優先：候補の優先順で判定")
        return {
            "name": f"翌取引日の仮想保有開始候補（{entries['session']}）",
            "value": (f"{shown}\n"
                      f"注文額の条件：始値{limit}（{shares:,}株・1注文{cap_text}）\n"
                      f"{cash_rule}、同時保有枠（最大{max_positions:,}銘柄）に空きがあり、"
                      "同じ銘柄を仮想保有中でないこと\n"
                      "当日の有効な日足と正の出来高があり、高値と安値が異なること\n"
                      f"{priority}"),
        }
    # Pending entries staged before the order rule retained their original text.
    return {
        "name": f"翌営業日の買付候補（{entries['session']}）",
        "value": (f"{shown}\n"
                  "支持線付近で終値の反発条件を満たした銘柄です。"
                  "翌営業日の取引終了後に日足始値を確認し、確認できない場合は保留します。"
                  "始値×設定株数が注文上限以内で、手数料込みの資金と保有枠が足りる場合が対象です。"
                  "保有の確定には当日の値幅と出来高の確認も必要です。"
                  "現時点では買付候補（未約定）です。"),
    }


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
    summary = next((payload for _, payload, _ in pending if payload.get("kind") == SUMMARY), {})
    entries = summary.get("next_session_entries")
    openings = summary.get("closing_openings")
    attach_details = False
    for details, field_builder in ((openings, _opening_field), (entries, _entry_field)):
        if details is not None:
            if delayed or details["snapshot_sha256"] != snapshot["payload_sha256"]:
                raise ValueError("daily notification details differ from the verified live snapshot")
            field = field_builder(details, attached=False)
            if len(field["value"]) > 1024:
                field = field_builder(details, attached=True)
                attach_details = True
            fields.append(field)
    attachment = _attachment(date, chart_links, entries, openings) if attach_details else None
    if chart_links:
        lines = [f"[{symbol}]({url})" for symbol, url in chart_links]
        heading = f"**検出一覧（{len(symbols)}銘柄）**\n仕込み候補・監視開始（未約定）\n"
        description = heading + " ・ ".join(lines)
        other_chars = len(embed["title"]) + len(FOOTER_PREFIX) + 64 + sum(
            len(field["name"]) + len(field["value"]) for field in fields
        )
        if len(description) > min(4096, 6000 - other_chars):
            attachment = attachment or _attachment(date, chart_links, entries, openings)
            description = heading + "全銘柄のチャートリンクは添付CSVをご覧ください。\n" + " ・ ".join(lines[:8])
        embed["description"] = description
    payload = {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}}
    if openings is not None:
        payload["components"] = [{"type": 1, "components": [{
            "type": 2, "style": 5, "label": "Cloudダッシュボードで試算を確認", "url": embed["url"],
        }]}]
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
    if "components" in batch["payload"]:
        rows = message.get("components")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get("type") != 1:
            return False
        buttons = rows[0].get("components")
        expected = batch["payload"]["components"][0]["components"][0]
        if (not isinstance(buttons, list) or len(buttons) != 1 or not isinstance(buttons[0], dict)
                or buttons[0].get("disabled") is True
                or any(buttons[0].get(key) != value for key, value in expected.items())):
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
    build_summary_details = None
    if _fresh_ordinary_result(run, snapshot, publication):
        build_summary_details = lambda: _summary_details(root, snapshot)
    if signals or build_summary_details is not None:
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
            # Only a fresh session can add the optional evening summary; a
            # verified day without signals or entry candidates stays silent.
            outbox.stage(snapshot, publication, existing_notifications_enabled=True, summary=summary,
                         build_summary_details=build_summary_details)
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
