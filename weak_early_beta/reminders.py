"""Independent D5-close and D6-open morning reminders for forward detections."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from .bank_calendar import (
    fifth_session_from_entry, is_bank_business_day, sixth_session_from_entry,
)
from .ledger import EXIT_REMINDER_COLUMNS, write_ledger
from .notify import WEBHOOK_ENV, _discord_url, _number, chart_components


REMINDER_COLOR = 0xF39C12
REMINDER_ENDPOINTS = (
    (5, "終値", fifth_session_from_entry, "exit_reminder_discord_url", "exit_reminded_at"),
    (6, "始値", sixth_session_from_entry, "d6_exit_reminder_discord_url", "d6_exit_reminded_at"),
)


def save_reminder_receipts(ledger: pd.DataFrame, path: Path) -> None:
    """Replace the ledger atomically before proceeding to another delivery."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        write_ledger(ledger, temporary_path)
        with temporary_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _payload(
    group: pd.DataFrame, target: date, report_url: str, session: int, price_label: str,
) -> dict[str, Any]:
    first = group.iloc[0]
    company = str(first.get("company_name", "") or "").strip()
    symbol = str(first["symbol"])
    embed: dict[str, Any] = {
        "title": f"{session}営業日目の確認：{symbol} {company}".strip(),
        "description": f"本日の{price_label}で、Cloudの{session}営業日目が確定します。運用ルールの確認用リマインダーです。",
        "color": REMINDER_COLOR,
        "fields": [
            {"name": "確認日", "value": target.isoformat(), "inline": True},
            {"name": "評価タイミング", "value": f"{session}営業日目の{price_label}", "inline": True},
            {"name": "エントリー日", "value": f"{pd.Timestamp(first['entry_date']):%Y-%m-%d}", "inline": True},
            {"name": "エントリー価格", "value": _number(first.get("entry_open"), "円"), "inline": True},
            {"name": "該当モード数", "value": f"{group['selector_id'].nunique()}モード", "inline": True},
        ],
        "footer": {"text": "売買推奨ではなく、設定済み評価日の確認通知です"},
    }
    if report_url:
        embed["url"] = report_url
    return {"content": "", "embeds": [embed], "components": chart_components(symbol), "allowed_mentions": {"parse": []}}


def notify_exit_reminders(
    ledger: pd.DataFrame,
    target: date,
    report_url: str = "",
    webhook_url: str | None = None,
    dry_run: bool = False,
    on_delivery: Callable[[pd.DataFrame], None] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    webhook_url = (webhook_url or os.environ.get(WEBHOOK_ENV, "")).strip()
    result = ledger.copy()
    # CSVs written before D6 reminders have only the original D5 columns.
    for column in (*EXIT_REMINDER_COLUMNS, "updated_at"):
        result[column] = result.get(column, pd.Series("", index=result.index)).fillna("").astype(object)
    if not is_bank_business_day(target):
        return result, []
    candidates = result[
        result["source_scope"].eq("FORWARD_CAUSAL")
        & pd.to_datetime(result["entry_date"], errors="coerce").notna()
    ].copy()
    payloads: list[dict[str, Any]] = []
    for (signal_date, symbol), group in candidates.groupby(["signal_date", "symbol"], sort=True):
        entry = pd.Timestamp(group.iloc[0]["entry_date"]).date()
        for session, price_label, session_date, url_column, at_column in REMINDER_ENDPOINTS:
            if session_date(entry) != target:
                continue
            # One receipt on any matched mode suppresses the whole symbol group.
            if any(group[column].astype(str).str.strip().ne("").any() for column in (url_column, at_column)):
                continue
            payload = _payload(group, target, report_url, session, price_label)
            payloads.append(payload)
            if dry_run:
                continue
            if not webhook_url:
                raise RuntimeError(f"{WEBHOOK_ENV} is required for live exit reminders")
            try:
                response = requests.post(
                    webhook_url + ("&" if "?" in webhook_url else "?") + "wait=true&with_components=true",
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException:
                # Request exception text can contain the secret webhook URL.
                raise RuntimeError("Cloud reminder delivery failed; reconcile Discord receipts before retrying") from None
            receipt = response.json()
            mask = (
                pd.to_datetime(result["signal_date"]).eq(pd.Timestamp(signal_date))
                & result["symbol"].astype(str).eq(str(symbol))
                & result["source_scope"].eq("FORWARD_CAUSAL")
            )
            now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
            result.loc[mask, url_column] = _discord_url(receipt)
            result.loc[mask, at_column] = now
            result.loc[mask, "updated_at"] = now
            if on_delivery is not None:
                on_delivery(result.copy())
    return result, payloads
