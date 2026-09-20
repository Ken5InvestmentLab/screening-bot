"""Isolated claim/state adapter for the existing Premium fundamental worker."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

from .ledger import DEFAULT_LEDGER, DEFAULT_QUEUE, read_ledger


ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = ROOT / "weak_early_beta" / "fundamental_worker"
DEFAULT_WORKER_STATE = WORKER_ROOT / "state" / "premium_alert_state.json"
DEFAULT_WORKER_OUT = WORKER_ROOT / "out"
DEFAULT_CLAIM = DEFAULT_WORKER_OUT / "latest_claim.json"
DEFAULT_RECEIPTS = DEFAULT_WORKER_OUT / "fundamental_receipts.json"
DEFAULT_REPORTS = DEFAULT_WORKER_OUT / "premium_reports.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def alert_id(signal_date: str, symbol: str) -> str:
    return f"weak-early-beta:{signal_date}:{symbol}"


def empty_worker_state() -> dict:
    return {
        "version": 1,
        "posted": {},
        "failed": {},
        "claims": {},
        "pendingLogEvents": [],
    }


def prepare_claim(
    queue_path: Path = DEFAULT_QUEUE,
    ledger_path: Path = DEFAULT_LEDGER,
    state_path: Path = DEFAULT_WORKER_STATE,
    claim_path: Path = DEFAULT_CLAIM,
    max_alerts: int = 0,
) -> dict:
    """Create one immutable beta batch without reading production Sheets/state."""
    queue = _read_json(queue_path, [])
    state = _read_json(state_path, empty_worker_state())
    for key, default in empty_worker_state().items():
        state.setdefault(key, default.copy() if isinstance(default, dict) else list(default) if isinstance(default, list) else default)
    if state["claims"]:
        raise RuntimeError(
            "beta fundamental claims already exist; reconcile the existing batch before preparing another"
        )

    ledger = read_ledger(ledger_path)
    lookup = {}
    if not ledger.empty:
        for (date, symbol), group in ledger.groupby(["signal_date", "symbol"], sort=False):
            lookup[(f"{pd.Timestamp(date):%Y-%m-%d}", str(symbol))] = group

    pending = []
    for item in queue:
        signal_date = str(item["signal_date"])
        symbol = str(item["symbol"])
        identity = alert_id(signal_date, symbol)
        if identity in state["posted"]:
            continue
        group = lookup.get((signal_date, symbol))
        entry_price = None
        if group is not None:
            prices = pd.to_numeric(group["entry_open"], errors="coerce").dropna()
            if not prices.empty:
                entry_price = float(prices.iloc[0])
        alert = {
            "alertId": identity,
            "receivedAt": f"{signal_date}T15:30:00+09:00",
            "signalDate": signal_date,
            "signalType": "WEAK_EARLY_BETA",
            "symbolCode": symbol,
            "symbolName": str(item.get("company_name", "")),
            "entryPrice": entry_price,
            "tradingViewUrl": f"https://jp.tradingview.com/chart/?symbol=TSE%3A{symbol}",
            "betaSelectors": list(item.get("selector_names", [])),
        }
        pending.append(alert)
    if max_alerts > 0:
        pending = pending[:max_alerts]

    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    claim_id = str(uuid.uuid4())
    for alert in pending:
        state["claims"][alert["alertId"]] = {
            "claimId": claim_id,
            "claimedAt": now,
            "receivedAt": alert["receivedAt"],
            "signalDate": alert["signalDate"],
            "signalType": alert["signalType"],
            "symbolCode": alert["symbolCode"],
            "symbolName": alert["symbolName"],
            "tradingViewUrl": alert["tradingViewUrl"],
        }
    claim = {
        "ok": True,
        "claimId": claim_id,
        "generatedAt": now,
        "claimedCount": len(pending),
        "alerts": pending,
        "outputReportPath": str(DEFAULT_WORKER_OUT / "premium_reports.json"),
        "rules": {
            "requiredFields": [
                "alertId", "symbolCode", "symbolName", "summary",
                "materialImpact", "fields", "sources",
            ],
            "disclosureFallback": "開示リンク未確認",
            "prohibited": [
                "buy/sell recommendations", "target prices", "additional scores"
            ],
            "destinationChannelId": "1550876675884060702",
            "model": "gpt-5.6-luna",
            "reasoningEffort": "xhigh",
        },
    }
    _write_json(state_path, state)
    _write_json(claim_path, claim)
    return claim


def export_receipts(
    state_path: Path = DEFAULT_WORKER_STATE,
    receipt_path: Path = DEFAULT_RECEIPTS,
    reports_path: Path = DEFAULT_REPORTS,
) -> list[dict]:
    """Convert worker Discord receipts into the beta ledger import contract."""
    state = _read_json(state_path, empty_worker_state())
    reports_payload = _read_json(reports_path, {"reports": []})
    report_lookup = {
        str(report.get("alertId", "")): report
        for report in reports_payload.get("reports", [])
        if isinstance(report, dict)
    }
    receipts = []
    for identity, posted in sorted(state.get("posted", {}).items()):
        if not identity.startswith("weak-early-beta:"):
            continue
        signal_date, symbol = identity.removeprefix("weak-early-beta:").split(":", 1)
        report = report_lookup.get(identity, {})
        analysis_lines = []
        for field in report.get("fields", []):
            name = str(field.get("name", "")).strip()
            value = str(field.get("value", "")).strip()
            if name and value:
                analysis_lines.extend([name, value, ""])
        receipts.append({
            "signal_date": signal_date,
            "symbol": symbol,
            "status": "complete",
            "discord_url": str(posted.get("discordMessageUrl", "")),
            "html": "\n".join(analysis_lines).strip(),
        })
    _write_json(receipt_path, {"receipts": receipts})
    return receipts
