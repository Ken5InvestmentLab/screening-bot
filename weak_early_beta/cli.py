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
from .historical_fundamentals import (
    DEFAULT_BATCH,
    DEFAULT_BATCH_REPORTS,
    DEFAULT_MANIFEST,
    DEFAULT_RECEIPTS as DEFAULT_HISTORICAL_RECEIPTS,
    build_manifest as build_historical_manifest,
    import_historical_reports,
    merge_receipts as merge_historical_receipts,
    select_batch as select_historical_batch,
    validate_historical_report,
)
from .report import DEFAULT_METRICS, DEFAULT_REPORT, write_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "weak_early_beta" / "state" / "latest_run_receipt.json"


def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_historical_audit_pass(reports: list[dict]) -> None:
    for report in reports:
        if report.get("auditStatus") != "pass":
            identity = f"{report.get('signalDate', '?')}|{report.get('symbolCode', '?')}"
            status = report.get("auditStatus", "missing")
            raise ValueError(
                f"historical report {identity} is not importable: auditStatus={status!r}"
            )


def _validate_historical_import_targets(
    manifest_status: dict[str, str],
    identities: list[str],
    *,
    replace_existing: bool = False,
) -> None:
    for row_id in identities:
        if row_id not in manifest_status:
            raise ValueError(f"historical identity is not in the canonical ledger: {row_id}")
    complete = [row_id for row_id in identities if manifest_status[row_id] == "complete"]
    if replace_existing:
        if len(complete) != len(identities):
            raise ValueError("--replace-existing may only replace already complete identities")
    elif complete:
        raise ValueError(f"historical identity is already complete: {complete[0]}")


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
    from .restrictions import fetch_jpx_restricted_symbols, quarantine_restricted_detections, restricted_mask

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
    latest = pd.to_datetime(raw["date"]).max()
    restrictions = fetch_jpx_restricted_symbols(
        args.as_of or latest,
        Path(args.restriction_snapshot),
    )
    selected_restriction_mask = restricted_mask(selected, restrictions)
    restricted_selected = selected[selected_restriction_mask].copy()
    selected = selected[~selected_restriction_mask].copy()
    incoming = model.attach_forward_rows(selected, raw, company_names, source_hash)
    ledger = merge_detections(ledger, incoming)
    ledger, quarantined = quarantine_restricted_detections(
        ledger,
        restrictions,
        Path(args.excluded_ledger),
    )
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
        "restricted_selector_rows_latest": int(len(restricted_selected)),
        "quarantined_ledger_rows": int(len(quarantined)),
        "jpx_restricted_symbols": int(len(restrictions)),
        "new_or_refreshed_rows": int(len(incoming)),
        "notification_payloads": len(payloads),
        "ledger_rows": int(len(ledger)),
        "metrics_rows": int(len(metrics)),
    }
    _write_receipt(Path(args.receipt), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


def command_refresh_restrictions(args: argparse.Namespace) -> None:
    from .restrictions import fetch_jpx_restricted_symbols, quarantine_restricted_detections

    target = args.as_of or pd.Timestamp.now(tz="Asia/Tokyo").date()
    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    restrictions = fetch_jpx_restricted_symbols(target, Path(args.restriction_snapshot))
    ledger, excluded = quarantine_restricted_detections(
        ledger,
        restrictions,
        Path(args.excluded_ledger),
    )
    write_ledger(ledger, ledger_path)
    write_fundamental_queue(ledger, Path(args.queue))
    metrics = write_report(ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({
        "as_of": f"{pd.Timestamp(target):%Y-%m-%d}",
        "restricted_symbols": len(restrictions),
        "excluded_rows": len(excluded),
        "ledger_rows": len(ledger),
        "metrics_rows": len(metrics),
    }, ensure_ascii=False))


def command_notify(args: argparse.Namespace) -> None:
    from .notify import notify_pending

    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    ledger, payloads = notify_pending(
        ledger,
        report_url=args.report_url or os.environ.get("WEAK_EARLY_BETA_REPORT_URL", ""),
        dry_run=args.dry_run,
        signal_date=args.date,
        refresh_existing=args.refresh_existing,
    )
    if payloads and not args.dry_run:
        write_ledger(ledger, ledger_path)
        write_fundamental_queue(ledger, Path(args.queue))
    print(json.dumps({"notifications": len(payloads), "dry_run": bool(args.dry_run)}, ensure_ascii=False))


def command_notify_day(args: argparse.Namespace) -> None:
    from .notify import notify_daily_completion, notify_pending

    target = pd.Timestamp(args.date or pd.Timestamp.now(tz="Asia/Tokyo").date()).date()
    ledger_path = Path(args.ledger)
    ledger = _load_or_bootstrap(ledger_path)
    report_url = args.report_url or os.environ.get("WEAK_EARLY_BETA_REPORT_URL", "")
    ledger, signal_payloads = notify_pending(
        ledger,
        report_url=report_url,
        dry_run=args.dry_run,
        signal_date=target,
    )
    completion_payloads = notify_daily_completion(
        ledger,
        target,
        report_url,
        state_path=Path(args.daily_notification_state),
        dry_run=args.dry_run,
    )
    if signal_payloads and not args.dry_run:
        write_ledger(ledger, ledger_path)
        write_fundamental_queue(ledger, Path(args.queue))
    print(json.dumps({
        "date": target.isoformat(),
        "signal_notifications": len(signal_payloads),
        "completion_notifications": len(completion_payloads),
        "dry_run": bool(args.dry_run),
    }, ensure_ascii=False))


def command_notify_exclusions(args: argparse.Namespace) -> None:
    from .notify import notify_exclusion_corrections

    excluded_path = Path(args.excluded_ledger)
    if not excluded_path.exists():
        print(json.dumps({"corrections": 0, "dry_run": bool(args.dry_run)}, ensure_ascii=False))
        return
    excluded = pd.read_csv(excluded_path, dtype={"symbol": str})
    excluded, payloads = notify_exclusion_corrections(excluded, dry_run=args.dry_run)
    if payloads and not args.dry_run:
        excluded.to_csv(excluded_path, index=False, encoding="utf-8", lineterminator="\n")
    print(json.dumps({"corrections": len(payloads), "dry_run": bool(args.dry_run)}, ensure_ascii=False))


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

    alert_ids = None
    if args.claim:
        claim = json.loads(Path(args.claim).read_text(encoding="utf-8-sig"))
        alert_ids = {str(alert["alertId"]) for alert in claim.get("alerts", [])}
    receipts = export_receipts(
        Path(args.worker_state),
        Path(args.receipts),
        alert_ids=alert_ids,
    )
    print(json.dumps({"exported": len(receipts), "receipts": args.receipts}, ensure_ascii=False))


def _historical_payload(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    reports = payload if isinstance(payload, list) else payload.get("reports", [])
    if not isinstance(reports, list):
        raise ValueError("historical reports must be a list")
    return reports


def command_historical_fundamentals_manifest(args: argparse.Namespace) -> None:
    ledger = read_ledger(Path(args.ledger))
    receipts_payload = json.loads(Path(args.receipts).read_text(encoding="utf-8-sig")) if Path(args.receipts).exists() else {}
    manifest = build_historical_manifest(ledger, receipts_payload.get("reports", []))
    target = Path(args.manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "identity": manifest["identity"],
        "total_identities": manifest["total_identities"],
        "status_counts": manifest["status_counts"],
        "manifest": args.manifest,
    }, ensure_ascii=False))


def command_historical_fundamentals_batch(args: argparse.Namespace) -> None:
    ledger = read_ledger(Path(args.ledger))
    receipts_path = Path(args.receipts)
    receipts_payload = json.loads(receipts_path.read_text(encoding="utf-8-sig")) if receipts_path.exists() else {}
    manifest = build_historical_manifest(ledger, receipts_payload.get("reports", []))
    batch = select_historical_batch(manifest, args.limit)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "identity": "WEAK_EARLY_HISTORICAL_FUNDAMENTALS_BATCH_V1",
        "created_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "limit": args.limit,
        "records": batch,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batch_size": len(batch), "output": args.output}, ensure_ascii=False))


def command_import_historical_fundamentals(args: argparse.Namespace) -> None:
    ledger_path = Path(args.ledger)
    receipts_path = Path(args.receipts)
    manifest_path = Path(args.manifest)
    input_reports = _historical_payload(Path(args.input))
    _require_historical_audit_pass(input_reports)
    identities = [validate_historical_report(report) for report in input_reports]
    if len(identities) != len(set(identities)):
        raise ValueError("input contains duplicate historical identities")

    ledger = read_ledger(ledger_path)
    previous = json.loads(receipts_path.read_text(encoding="utf-8-sig")) if receipts_path.exists() else {}
    manifest = build_historical_manifest(ledger, previous.get("reports", []))
    manifest_status = {record["identity"]: record["status"] for record in manifest["records"]}
    _validate_historical_import_targets(
        manifest_status,
        identities,
        replace_existing=bool(getattr(args, "replace_existing", False)),
    )

    updated_ledger, accepted = import_historical_reports(ledger, input_reports)
    merged_receipts = merge_historical_receipts(previous, accepted)
    updated_manifest = build_historical_manifest(updated_ledger, merged_receipts["reports"])

    receipts_path.parent.mkdir(parents=True, exist_ok=True)
    receipts_path.write_text(json.dumps(merged_receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    write_ledger(updated_ledger, ledger_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = write_report(updated_ledger, Path(args.report), Path(args.metrics))
    print(json.dumps({
        "imported": len(accepted),
        "total_identities": updated_manifest["total_identities"],
        "status_counts": updated_manifest["status_counts"],
        "metrics_rows": len(metrics),
        "discord_posts": 0,
    }, ensure_ascii=False))


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
    daily.add_argument(
        "--restriction-snapshot",
        default=str(ROOT / "weak_early_beta" / "state" / "jpx_restricted_symbols_latest.json"),
    )
    daily.add_argument(
        "--excluded-ledger",
        default=str(ROOT / "weak_early_beta" / "state" / "excluded_detections.csv"),
    )
    daily.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    daily.set_defaults(func=command_daily)

    restrictions = sub.add_parser("refresh-restrictions", help="apply the causal JPX delisting gate")
    common(restrictions)
    restrictions.add_argument("--as-of")
    restrictions.add_argument(
        "--restriction-snapshot",
        default=str(ROOT / "weak_early_beta" / "state" / "jpx_restricted_symbols_latest.json"),
    )
    restrictions.add_argument(
        "--excluded-ledger",
        default=str(ROOT / "weak_early_beta" / "state" / "excluded_detections.csv"),
    )
    restrictions.set_defaults(func=command_refresh_restrictions)

    notify = sub.add_parser("notify", help="send queued signal embeds without rescoring")
    common(notify)
    notify.add_argument("--report-url", default="")
    notify.add_argument("--dry-run", action="store_true")
    notify.add_argument("--date")
    notify.add_argument("--refresh-existing", action="store_true")
    notify.set_defaults(func=command_notify)

    notify_day = sub.add_parser("notify-day", help="send one business day's signals and completion embeds")
    common(notify_day)
    notify_day.add_argument("--date")
    notify_day.add_argument("--report-url", default="")
    notify_day.add_argument("--dry-run", action="store_true")
    notify_day.add_argument(
        "--daily-notification-state",
        default=str(ROOT / "weak_early_beta" / "state" / "daily_notifications.json"),
    )
    notify_day.set_defaults(func=command_notify_day)

    notify_exclusions = sub.add_parser("notify-exclusions", help="patch already-posted JPX-excluded signals")
    notify_exclusions.add_argument(
        "--excluded-ledger",
        default=str(ROOT / "weak_early_beta" / "state" / "excluded_detections.csv"),
    )
    notify_exclusions.add_argument("--dry-run", action="store_true")
    notify_exclusions.set_defaults(func=command_notify_exclusions)

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
    export.add_argument("--claim", help="limit receipts to alert IDs in this claim JSON")
    export.set_defaults(func=command_export_fundamentals)

    historical_manifest = sub.add_parser(
        "historical-fundamentals-manifest",
        help="build the as-of historical fundamental backfill manifest",
    )
    historical_manifest.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    historical_manifest.add_argument("--receipts", default=str(DEFAULT_HISTORICAL_RECEIPTS))
    historical_manifest.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    historical_manifest.set_defaults(func=command_historical_fundamentals_manifest)

    historical_batch = sub.add_parser(
        "historical-fundamentals-batch",
        help="export the next bounded batch of historical detections to analyze",
    )
    historical_batch.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    historical_batch.add_argument("--receipts", default=str(DEFAULT_HISTORICAL_RECEIPTS))
    historical_batch.add_argument("--limit", type=int, default=4)
    historical_batch.add_argument("--output", default=str(DEFAULT_BATCH))
    historical_batch.set_defaults(func=command_historical_fundamentals_batch)

    historical_import = sub.add_parser(
        "import-historical-fundamentals",
        help="validate and attach as-of historical analysis without Discord posting",
    )
    historical_import.add_argument("--input", default=str(DEFAULT_BATCH_REPORTS))
    historical_import.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    historical_import.add_argument("--receipts", default=str(DEFAULT_HISTORICAL_RECEIPTS))
    historical_import.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    historical_import.add_argument("--report", default=str(DEFAULT_REPORT))
    historical_import.add_argument("--metrics", default=str(DEFAULT_METRICS))
    historical_import.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace complete historical receipts only after auditStatus=pass",
    )
    historical_import.set_defaults(func=command_import_historical_fundamentals)

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
