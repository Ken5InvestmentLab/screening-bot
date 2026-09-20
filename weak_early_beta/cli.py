#!/usr/bin/env python3
"""Command-line entrypoint for the isolated Weak+Early beta."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from .ledger import (
    DEFAULT_LEDGER,
    DEFAULT_QUEUE,
    apply_fundamental_receipts,
    bootstrap_historical,
    merge_detections,
    read_ledger,
    write_fundamental_queue,
    write_ledger,
)
from .report import DEFAULT_METRICS, DEFAULT_REPORT, write_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "weak_early_beta" / "state" / "latest_run_receipt.json"


def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_bootstrap(args: argparse.Namespace) -> None:
    target = Path(args.ledger)
    if target.exists() and not args.force:
        raise RuntimeError(f"ledger already exists: {target}; pass --force to rebuild exact history")
    ledger = bootstrap_historical()
    write_ledger(ledger, target)
    write_fundamental_queue(ledger, Path(args.queue))
    metrics = write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({"rows": len(ledger), "metrics": len(metrics)}, ensure_ascii=False))


def _load_or_bootstrap(path: Path) -> pd.DataFrame:
    return read_ledger(path) if path.exists() else bootstrap_historical()


def command_report(args: argparse.Namespace) -> None:
    ledger = _load_or_bootstrap(Path(args.ledger))
    write_ledger(ledger, Path(args.ledger))
    write_fundamental_queue(ledger, Path(args.queue))
    metrics = write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({"rows": len(ledger), "metrics": len(metrics)}, ensure_ascii=False))


def command_daily(args: argparse.Namespace) -> None:
    # Heavy TV-free runtime dependencies are needed only for the daily scorer;
    # report/bootstrap operations stay lightweight and deterministic.
    from . import model
    from .notify import notify_pending

    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    company_names: dict[str, str] = {}
    daily_path = Path(args.daily_corpus)
    if args.refresh_live:
        universe = model.base.jpx_universe()
        raw = model.base.fetch_daily(universe, args.period)
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(daily_path, index=False, encoding="utf-8", lineterminator="\n", date_format="%Y-%m-%d")
        company_names = universe.set_index("code")["name"].astype(str).to_dict()
    else:
        if not daily_path.exists():
            raise FileNotFoundError(f"daily corpus not found: {daily_path}")
        raw = model.read_daily(daily_path)
        if args.refresh_universe:
            universe = model.base.jpx_universe()
            company_names = universe.set_index("code")["name"].astype(str).to_dict()
    source_hash = model.sha256(daily_path)
    raw = model.read_daily(daily_path)
    ledger = model.refresh_forward_endpoints(ledger, raw)
    if args.from_date:
        tail, selected = model.score_range(raw, args.from_date, args.as_of)
    else:
        tail, selected = model.score_latest(raw, args.as_of)
    incoming = model.attach_forward_rows(selected, raw, company_names, source_hash)
    ledger = merge_detections(ledger, incoming)
    report_url = args.report_url or os.environ.get("WEAK_EARLY_BETA_REPORT_URL", "")
    payloads = []
    if args.notify or args.dry_run_notify:
        ledger, payloads = notify_pending(
            ledger,
            report_url=report_url,
            dry_run=args.dry_run_notify,
        )
    write_ledger(ledger, ledger_path)
    write_fundamental_queue(ledger, Path(args.queue))
    metrics = write_report(ledger, Path(args.report), Path(args.metrics))
    latest = pd.to_datetime(raw["date"]).max()
    receipt = {
        "identity": "WEAK_EARLY_FIVE_LANE_BETA_V1",
        "run_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "daily_corpus": str(daily_path),
        "daily_sha256": source_hash,
        "latest_session": f"{latest:%Y-%m-%d}",
        "score_from": args.from_date or (args.as_of or f"{latest:%Y-%m-%d}"),
        "score_to": args.as_of or f"{latest:%Y-%m-%d}",
        "tail_rows_latest": int(len(tail)),
        "selector_rows_latest": int(len(selected)),
        "new_or_refreshed_rows": int(len(incoming)),
        "notification_payloads": len(payloads),
        "ledger_rows": int(len(ledger)),
        "metrics_rows": int(len(metrics)),
    }
    _write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


def command_notify(args: argparse.Namespace) -> None:
    from .notify import notify_pending

    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    ledger, payloads = notify_pending(
        ledger,
        report_url=args.report_url or os.environ.get("WEAK_EARLY_BETA_REPORT_URL", ""),
        dry_run=args.dry_run,
    )
    if payloads and not args.dry_run:
        write_ledger(ledger, ledger_path)
        write_fundamental_queue(ledger, Path(args.queue))
        write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({"notifications": len(payloads), "dry_run": bool(args.dry_run)}, ensure_ascii=False))


def command_import_fundamentals(args: argparse.Namespace) -> None:
    ledger_path = Path(args.ledger)
    ledger = read_ledger(ledger_path)
    payload = json.loads(Path(args.receipts).read_text(encoding="utf-8"))
    receipts = payload if isinstance(payload, list) else payload.get("receipts", [])
    ledger = apply_fundamental_receipts(ledger, receipts)
    write_ledger(ledger, ledger_path)
    write_fundamental_queue(ledger, Path(args.queue))
    write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({"imported": len(receipts)}, ensure_ascii=False))


def command_prepare_fundamentals(args: argparse.Namespace) -> None:
    from .fundamental import prepare_claim

    claim = prepare_claim(
        queue_path=Path(args.queue),
        ledger_path=Path(args.ledger),
        state_path=Path(args.worker_state),
        claim_path=Path(args.claim),
        max_alerts=args.max_alerts,
    )
    print(json.dumps({
        "claimed": claim["claimedCount"],
        "claim_id": claim["claimId"],
        "claim_path": args.claim,
    }, ensure_ascii=False))


def command_export_fundamentals(args: argparse.Namespace) -> None:
    from .fundamental import export_receipts

    receipts = export_receipts(Path(args.worker_state), Path(args.receipts))
    print(json.dumps({"exported": len(receipts), "receipts": args.receipts}, ensure_ascii=False))


def command_is_business_day(args: argparse.Namespace) -> None:
    from .bank_calendar import is_bank_business_day

    target = pd.Timestamp(args.date or pd.Timestamp.now(tz="Asia/Tokyo").date()).date()
    print(json.dumps({"date": target.isoformat(), "business_day": is_bank_business_day(target)}, ensure_ascii=False))


def command_remind_exits(args: argparse.Namespace) -> None:
    from .bank_calendar import is_bank_business_day
    from .reminders import notify_exit_reminders

    target = pd.Timestamp(args.date or pd.Timestamp.now(tz="Asia/Tokyo").date()).date()
    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    payloads = []
    if is_bank_business_day(target):
        ledger, payloads = notify_exit_reminders(
            ledger,
            target,
            report_url=args.report_url or os.environ.get("WEAK_EARLY_BETA_REPORT_URL", ""),
            dry_run=args.dry_run,
        )
    if payloads and not args.dry_run:
        write_ledger(ledger, ledger_path)
        write_fundamental_queue(ledger, Path(args.queue))
        write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({
        "date": target.isoformat(),
        "business_day": is_bank_business_day(target),
        "reminders": len(payloads),
        "dry_run": bool(args.dry_run),
    }, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ledger", default=str(DEFAULT_LEDGER))
        p.add_argument("--queue", default=str(DEFAULT_QUEUE))
        p.add_argument("--report", default=str(DEFAULT_REPORT))
        p.add_argument("--metrics", default=str(DEFAULT_METRICS))

    bootstrap = sub.add_parser("bootstrap", help="import frozen 2023-2026 exact rows")
    common(bootstrap)
    bootstrap.add_argument("--force", action="store_true")
    bootstrap.set_defaults(func=command_bootstrap)

    report = sub.add_parser("report", help="regenerate metrics and HTML from ledger")
    common(report)
    report.set_defaults(func=command_report)

    daily = sub.add_parser("daily", help="score latest session and update beta artifacts")
    common(daily)
    daily.add_argument("--daily-corpus", default=".cache/weak_early_beta/tse_daily.csv")
    daily.add_argument("--refresh-live", action="store_true")
    daily.add_argument(
        "--refresh-universe",
        action="store_true",
        help="refresh only the JPX code/name mapping while reusing the cached daily corpus",
    )
    daily.add_argument("--period", default="5y")
    daily.add_argument("--as-of")
    daily.add_argument(
        "--from-date",
        help="score every session from this date through --as-of, fitting each month once",
    )
    daily.add_argument("--notify", action="store_true")
    daily.add_argument("--dry-run-notify", action="store_true")
    daily.add_argument("--report-url", default="")
    daily.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    daily.set_defaults(func=command_daily)

    notify = sub.add_parser("notify", help="send queued signal embeds without rescoring")
    common(notify)
    notify.add_argument("--report-url", default="")
    notify.add_argument("--dry-run", action="store_true")
    notify.set_defaults(func=command_notify)

    imports = sub.add_parser("import-fundamentals", help="attach dedicated-channel analysis receipts")
    common(imports)
    imports.add_argument("--receipts", required=True)
    imports.set_defaults(func=command_import_fundamentals)

    prepare = sub.add_parser(
        "prepare-fundamentals", help="create a beta-only Premium Worker claim"
    )
    common(prepare)
    prepare.add_argument(
        "--worker-state",
        default=str(ROOT / "weak_early_beta" / "fundamental_worker" / "state" / "premium_alert_state.json"),
    )
    prepare.add_argument(
        "--claim",
        default=str(ROOT / "weak_early_beta" / "fundamental_worker" / "out" / "latest_claim.json"),
    )
    prepare.add_argument("--max-alerts", type=int, default=0)
    prepare.set_defaults(func=command_prepare_fundamentals)

    export = sub.add_parser(
        "export-fundamentals", help="export dedicated-channel Discord receipts"
    )
    export.add_argument(
        "--worker-state",
        default=str(ROOT / "weak_early_beta" / "fundamental_worker" / "state" / "premium_alert_state.json"),
    )
    export.add_argument(
        "--receipts",
        default=str(ROOT / "weak_early_beta" / "fundamental_worker" / "out" / "fundamental_receipts.json"),
    )
    export.set_defaults(func=command_export_fundamentals)

    business_day = sub.add_parser("is-business-day", help="check the Japanese bank-business-day gate")
    business_day.add_argument("--date")
    business_day.set_defaults(func=command_is_business_day)

    reminders = sub.add_parser("remind-exits", help="notify symbols reaching their fifth session today")
    common(reminders)
    reminders.add_argument("--date")
    reminders.add_argument("--report-url", default="")
    reminders.add_argument("--dry-run", action="store_true")
    reminders.set_defaults(func=command_remind_exits)
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
