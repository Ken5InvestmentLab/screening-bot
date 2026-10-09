#!/usr/bin/env python3
"""Command-line entrypoint for the isolated Weak+Early beta."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
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
    normalize_historical_material_impacts,
    select_batch as select_historical_batch,
    validate_historical_report,
    validate_forward_reports,
)
from .report import DEFAULT_METRICS, DEFAULT_REPORT, write_report
from .progress import daily_phase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "weak_early_beta" / "state" / "latest_run_receipt.json"


def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_daily_cache(frame: pd.DataFrame, path: Path) -> None:
    """Keep the prior price/action evidence intact if a large CSV write fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8", lineterminator="\n", date_format="%Y-%m-%d")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    source_revision = {}
    if args.refresh_live:
        from .corporate_actions import fetch_daily

        with daily_phase("live-acquisition"):
            universe = model.base.jpx_universe()
            # The old cache is evidence for detecting unannounced source rebases;
            # it must not be treated as action-aware input merely because it exists.
            previous = (
                pd.read_csv(daily_path, parse_dates=["date"], dtype={"symbol": str})
                if daily_path.exists() else None
            )
            if previous is not None:
                previous.attrs["source_sha256"] = model.sha256(daily_path)
            raw = fetch_daily(universe, args.period, previous=previous)
            source_revision = raw.attrs.get("source_revision_receipt", {})
            del previous
        with daily_phase("source-cache-write"):
            _write_daily_cache(raw, daily_path)
        del raw
        company_names = universe.set_index("code")["name"].astype(str).to_dict()
    else:
        if not daily_path.exists():
            raise FileNotFoundError(f"daily corpus not found: {daily_path}")
        if args.refresh_universe:
            universe = model.base.jpx_universe()
            company_names = universe.set_index("code")["name"].astype(str).to_dict()
    source_hash = model.sha256(daily_path)
    with daily_phase("cache-read-and-validation"):
        raw = model.read_daily(daily_path)
    from .corporate_actions import source_quality_receipt

    with daily_phase("source-quality"):
        source_quality = source_quality_receipt(raw)
    quality_path = daily_path.with_suffix(".source-quality.json")
    if not args.refresh_live and quality_path.exists():
        previous_quality = json.loads(quality_path.read_text(encoding="utf-8"))
        if previous_quality.get("daily_sha256") == source_hash:
            source_revision = previous_quality.get("source_revision", {})
    _write_receipt(quality_path, {**source_quality, "daily_sha256": source_hash, "source_revision": source_revision})
    quality_dates = sorted(source_quality["quarantinedDates"])
    source_quality = {key: value for key, value in source_quality.items() if key not in {"issues", "quarantinedDates"}}
    source_quality.update(
        quarantinedDateCount=len(quality_dates),
        firstQuarantinedDate=quality_dates[0] if quality_dates else None,
        lastQuarantinedDate=quality_dates[-1] if quality_dates else None,
    )
    source_quality.update(audit_path=str(quality_path), audit_sha256=model.sha256(quality_path))
    source_revision = {
        **{key: value for key, value in source_revision.items() if key not in {"acceptedRepairs", "quarantinedComparisons"}},
        "acceptedRepairs": [
            {key: value for key, value in repair.items() if key != "differences"}
            for repair in source_revision.get("acceptedRepairs", [])
        ],
        "quarantinedComparisonSymbolCount": len(source_revision.get("quarantinedComparisons", [])),
    }
    with daily_phase("forward-endpoints"):
        ledger = model.refresh_forward_endpoints(ledger, raw, source_sha256=source_hash)
    with daily_phase("scoring"):
        if args.from_date:
            tail, selected = model.score_range(raw, args.from_date, args.as_of)
        else:
            tail, selected = model.score_latest(raw, args.as_of)
    latest = pd.to_datetime(raw["date"]).max()
    with daily_phase("jpx-tradability"):
        restrictions = fetch_jpx_restricted_symbols(
            args.as_of or latest,
            Path(args.restriction_snapshot),
        )
    selected_restriction_mask = restricted_mask(selected, restrictions)
    restricted_selected = selected[selected_restriction_mask].copy()
    selected = selected[~selected_restriction_mask].copy()
    with daily_phase("attach-forward-rows"):
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
    with daily_phase("report"):
        metrics = write_report(ledger, Path(args.report), Path(args.metrics))
    receipt = {
        "identity": "WEAK_EARLY_FIVE_LANE_BETA_V1",
        "run_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "daily_corpus": str(daily_path),
        "daily_sha256": source_hash,
        "source_quality": source_quality,
        "source_revision": source_revision,
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


def command_system_log(args: argparse.Namespace) -> None:
    from .system_log import post_event

    result = post_event(
        date.fromisoformat(args.date), args.event, args.run_id,
        stage=args.stage, detail=args.detail, count=args.count,
    )
    print(json.dumps(result, ensure_ascii=False))


def command_watch_cloud_start(args: argparse.Namespace) -> None:
    from .system_log import watch_missed

    print(json.dumps(watch_missed(), ensure_ascii=False))


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
        analysis_cutoff=getattr(args, "analysis_cutoff", None),
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


def command_validate_forward_fundamentals(args: argparse.Namespace) -> None:
    claim = json.loads(Path(args.claim).read_text(encoding="utf-8-sig"))
    payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    reports = payload if isinstance(payload, list) else payload.get("reports", [])
    identities = validate_forward_reports(claim, reports)
    print(json.dumps({"ok": True, "validated": len(identities), "identities": identities}, ensure_ascii=False))


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


def command_normalize_historical_material_impacts(args: argparse.Namespace) -> None:
    """Persist the Premium-compatible impact label on existing historical reports."""
    ledger_path = Path(args.ledger)
    receipts_path = Path(args.receipts)
    manifest_path = Path(args.manifest)
    audit_path = Path(args.audit)
    ledger = read_ledger(ledger_path)
    receipts = json.loads(receipts_path.read_text(encoding="utf-8-sig"))
    updated_ledger, updated_reports, audit_rows = normalize_historical_material_impacts(
        ledger, receipts.get("reports", [])
    )
    now = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
    updated_receipts = dict(receipts)
    updated_receipts["updated_at"] = now
    updated_receipts["reports"] = updated_reports
    updated_manifest = build_historical_manifest(updated_ledger, updated_reports)
    audit = {
        "identity": "WEAK_EARLY_MATERIAL_IMPACT_NORMALIZATION_V1",
        "updated_at": now,
        "rule": "premium_impact_labels_v1; existing as-of snapshot text only; no new facts",
        "reports_reviewed": len(updated_reports),
        "reports_changed": len(audit_rows),
        "changes": audit_rows,
    }
    receipts_path.write_text(
        json.dumps(updated_receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_ledger(updated_ledger, ledger_path)
    manifest_path.write_text(
        json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = write_report(updated_ledger, Path(args.report), Path(args.metrics))
    labels = {}
    for report in updated_reports:
        impact = next(
            (field["value"] for field in report.get("fields", []) if field.get("name") == "材料インパクト"),
            "",
        )
        label = impact.split("：", 1)[0]
        labels[label] = labels.get(label, 0) + 1
    print(json.dumps({
        "reports_reviewed": len(updated_reports),
        "reports_changed": len(audit_rows),
        "labels": labels,
        "metrics_rows": len(metrics),
        "discord_posts": 0,
        "audit": str(audit_path),
    }, ensure_ascii=False))


def command_is_business_day(args: argparse.Namespace) -> None:
    from .bank_calendar import is_bank_business_day

    target = pd.Timestamp(args.date or pd.Timestamp.now(tz="Asia/Tokyo").date()).date()
    print(json.dumps({"date": target.isoformat(), "business_day": is_bank_business_day(target)}, ensure_ascii=False))


def command_backfill_endpoints(args: argparse.Namespace) -> None:
    """Write a reviewed, isolated endpoint migration and its audit, never in place."""
    import hashlib
    import io
    from .ledger import backfill_verified_endpoints

    inputs = [Path(value).resolve(strict=True) for value in (args.ledger, args.daily_corpus, args.identities)]
    ledger_path, source_path, identities_path = inputs
    output = Path(args.output).resolve()
    audit_path = Path(args.audit).resolve()
    protected_state = (ROOT / "weak_early_beta" / "state").resolve()
    if len(set(inputs + [output, audit_path])) != 5:
        raise ValueError("ledger, source, identities, output and audit must be distinct paths")
    for target in (output, audit_path):
        if target.is_relative_to(protected_state):
            raise ValueError("endpoint backfill cannot write into the production state directory")
        if target.exists():
            raise ValueError(f"endpoint backfill output already exists: {target}")
    # Read each input only once: the checked digest and parsed bytes are identical.
    source_bytes = source_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != args.source_sha256:
        raise ValueError("reviewed daily source SHA-256 does not match the input file")
    ledger_bytes = ledger_path.read_bytes()
    identity_bytes = identities_path.read_bytes()
    identities = json.loads(identity_bytes.decode("utf-8-sig"))
    if not isinstance(identities, list) or not all(isinstance(value, str) and value.strip() for value in identities):
        raise ValueError("identities JSON must be an explicit array of nonempty detection_id strings")
    observed = pd.Timestamp(args.observed_at)
    if pd.isna(observed) or observed.tzinfo is None or observed > pd.Timestamp.now(tz="UTC"):
        raise ValueError("observed-at must be a timezone-aware, non-future actual ingestion time")
    # Do not apply company-name or D5 migrations while reading a backfill input.
    ledger = pd.read_csv(io.BytesIO(ledger_bytes), dtype={"symbol": str})
    raw = pd.read_csv(io.BytesIO(source_bytes), parse_dates=["date"], dtype={"symbol": str})
    revised, audit = backfill_verified_endpoints(
        ledger, raw, source_sha256=source_hash, observed_at=observed.isoformat(), identities=identities,
    )
    csv_bytes = revised.to_csv(index=False, lineterminator="\n", date_format="%Y-%m-%d", float_format="%.12g").encode("utf-8")
    audit.update({
        "input_ledger": str(ledger_path), "input_ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "source_file": str(source_path), "identities_file": str(identities_path),
        "identities_sha256": hashlib.sha256(identity_bytes).hexdigest(),
        "output_ledger": str(output), "output_ledger_sha256": hashlib.sha256(csv_bytes).hexdigest(),
    })
    audit_bytes = (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for target in (output, audit_path):
        target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents racing another review output. If writing the
    # audit fails, remove only the output created by this invocation.
    created = []
    try:
        for target, contents in ((output, csv_bytes), (audit_path, audit_bytes)):
            with target.open("xb") as handle:
                created.append(target)
                handle.write(contents)
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    print(json.dumps({"output": str(output), "audit": str(audit_path),
                      "changed_count": audit["changed_count"], "notifications_sent": 0}, ensure_ascii=False))


def command_remind_exits(args: argparse.Namespace) -> None:
    from .bank_calendar import is_bank_business_day
    from .reminders import notify_exit_reminders, save_reminder_receipts

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
            on_delivery=lambda delivered: save_reminder_receipts(delivered, ledger_path),
        )
    # Morning delivery changes only receipts. The daily job rebuilds HTML and
    # queues; doing that here delayed completion after an already sent message.
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

    endpoints = sub.add_parser("backfill-endpoints", help="write a reviewed actual-price/D6 migration to a separate ledger")
    endpoints.add_argument("--ledger", required=True, help="read-only input ledger; no default")
    endpoints.add_argument("--daily-corpus", required=True, help="reviewed action-aware daily CSV")
    endpoints.add_argument("--source-sha256", required=True, help="reviewed daily CSV SHA-256")
    endpoints.add_argument("--identities", required=True, help="JSON array of detection_id strings to migrate")
    endpoints.add_argument("--observed-at", required=True, help="actual ingestion time with a timezone offset")
    endpoints.add_argument("--output", required=True, help="new isolated output ledger; input and production state forbidden")
    endpoints.add_argument("--audit", required=True, help="new JSON audit receipt path")
    endpoints.set_defaults(func=command_backfill_endpoints)

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

    system_log = sub.add_parser("system-log", help="post one Cloud event to the admin channel")
    system_log.add_argument("--date", required=True)
    system_log.add_argument("--event", required=True, choices=("started", "detected", "error"))
    system_log.add_argument("--run-id", required=True)
    system_log.add_argument("--stage", default="")
    system_log.add_argument("--detail", default="")
    system_log.add_argument("--count", type=int)
    system_log.set_defaults(func=command_system_log)

    watch_cloud = sub.add_parser("watch-cloud-start", help="alert if the scheduled Cloud start was not observed")
    watch_cloud.set_defaults(func=command_watch_cloud_start)

    notify_exclusions = sub.add_parser("notify-exclusions", help="patch already-posted JPX-excluded signals")
    notify_exclusions.add_argument(
        "--excluded-ledger",
        default=str(ROOT / "weak_early_beta" / "state" / "excluded_detections.csv"),
    )
    notify_exclusions.add_argument("--dry-run", action="store_true")
    notify_exclusions.set_defaults(func=command_notify_exclusions)

    imports = sub.add_parser("import-fundamentals", help="attach saved analysis snapshots to HTML")
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
    prepare.add_argument(
        "--analysis-cutoff",
        help="exact fundamental analysis-start ISO timestamp; runner stamps the final value immediately before analysis",
    )
    prepare.set_defaults(func=command_prepare_fundamentals)

    validate_forward = sub.add_parser(
        "validate-forward-fundamentals", help="validate audited reports against the actual analysis-start claim cutoff"
    )
    validate_forward.add_argument("--claim", required=True)
    validate_forward.add_argument("--input", required=True)
    validate_forward.set_defaults(func=command_validate_forward_fundamentals)

    export = sub.add_parser(
        "export-fundamentals", help="export saved HTML snapshots and legacy Discord receipts"
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

    impact_normalize = sub.add_parser(
        "normalize-historical-material-impacts",
        help="persist Premium labels/colors on existing as-of reports and regenerate the beta HTML",
    )
    impact_normalize.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    impact_normalize.add_argument("--receipts", default=str(DEFAULT_HISTORICAL_RECEIPTS))
    impact_normalize.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    impact_normalize.add_argument("--report", default=str(DEFAULT_REPORT))
    impact_normalize.add_argument("--metrics", default=str(DEFAULT_METRICS))
    impact_normalize.add_argument(
        "--audit",
        default=str(ROOT / "weak_early_beta" / "fundamental_worker" / "out" / "historical_material_impact_normalization_receipt.json"),
    )
    impact_normalize.set_defaults(func=command_normalize_historical_material_impacts)

    business_day = sub.add_parser("is-business-day", help="check the Japanese bank-business-day gate")
    business_day.add_argument("--date")
    business_day.set_defaults(func=command_is_business_day)

    reminders = sub.add_parser("remind-exits", help="notify D5-close and D6-open evaluation days")
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
