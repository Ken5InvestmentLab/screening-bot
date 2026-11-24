"""New A forward analysis over the admitted snapshot. Never writes legacy state."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from ..historical_fundamentals import FIELD_ORDER, _fields, validate_forward_reports
from .files import atomic_write, digest, encode, file_sha, private_root, read
from .publication import validate_for_owner_read
from .publisher import descriptors, validate_manifest

JST = dt.timezone(dt.timedelta(hours=9))
HEX = re.compile(r"[0-9a-f]{64}")
MODEL = "gpt-6.1-sol"
EFFORT = "xhigh"
RECEIPT_SCHEMA = "NEW_A_FORWARD_FUNDAMENTAL_RECEIPT_V1"
HISTORICAL_SCHEMA = "NEW_A_LOCAL_HISTORICAL_OWNER_LEDGER_V1"
MAX_HISTORICAL_LEDGER_BYTES = 128 * 1024 * 1024
CODE = re.compile(r"[0-9A-Z]{4}")


def _check(value, message):
    if not value:
        raise ValueError(message)


def _instant(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    _check(parsed.tzinfo is not None, "fundamental timestamp requires timezone")
    return parsed


def _part(folder, descriptor):
    filename = descriptor["name"]
    path = (folder / filename).resolve()
    _check(path.parent == folder, "fundamental bundle part escapes owner bundle")
    raw = path.read_bytes()
    _check(hashlib.sha256(raw).hexdigest() == descriptor["sha256"]
           and len(raw) == descriptor["bytes"], "fundamental base part changed")
    rows = json.loads(raw)
    _check(isinstance(rows, list) and len(rows) == descriptor["rows"],
           "fundamental base row count changed")
    return rows


def _manifest(folder):
    path = folder / "manifest.json"
    manifest = validate_manifest(read(path), prepared=True)
    receipt = read(folder / "receipt.json")
    _check(file_sha(path) == receipt["manifest_sha256"]
           and receipt["as_of"] == manifest["as_of"]
           and receipt["daily_snapshot_sha256"] == manifest["daily_snapshot_sha256"]
           and receipt["source_version"] == manifest["source_version"],
           "fundamental bundle provenance changed")
    return manifest, receipt


def _context(repo, runtime, day, started_at):
    root = private_root(repo)
    _check(dt.date.fromisoformat(day).isoformat() == day, "fundamental date must be canonical")
    runtime = Path(runtime).resolve()
    lock = runtime / "daily.lock"
    _check(runtime.is_relative_to(repo) and lock.read_text(encoding="utf-8").strip() == started_at,
           "fundamental stage requires the exact daily lock owner")
    owner = read(runtime / "daily-latest.json")
    _check(owner.get("startedAt") == started_at and owner.get("date") == day
           and owner.get("stage") == "fundamental" and not owner.get("completedAt"),
           "fundamental stage differs from the active daily runner")
    latest = root / "latest-run.json"
    run = read(latest)
    _check(run.get("identity") == "NEW_A_CLOUD_DAILY_V1" and run.get("strategy") == "A_BASE"
           and run.get("dry_run") is False and run.get("detection_executed") is True
           and run.get("latest_session") == day and not run.get("delayed_recovery")
           and HEX.fullmatch(run.get("source_sha256", "")),
           "fundamental stage requires same-day ordinary New A detection")
    publication = root / "latest-publication.json"
    if publication.exists():
        _check(read(publication).get("as_of", "") < day, "target day already published; do not rerun analysis")
    target = (root / "runs" / day / run["source_sha256"] / "live").resolve()
    _check(target.is_relative_to(root) and Path(run["snapshot_file"]).resolve() == target / "snapshot.json",
           "fundamental snapshot outside exact owner run")
    snapshot = validate_for_owner_read(read(target / "snapshot.json"),
                                       {"owner": True, "role_authorized": True, "current": True})
    _check(snapshot["payload_sha256"] == run["snapshot_sha256"] and snapshot["as_of"] == day
           and snapshot["source_sha256"] == run["source_sha256"]
           and snapshot["observation_kind"] == "LIVE_OBSERVATION"
           and _instant(snapshot["observed_at"]).astimezone(JST).date().isoformat() == day,
           "fundamental live snapshot provenance changed")
    base = target / "bundle"
    _check(base.resolve() == base, "fundamental base dataset escaped its immutable directory")
    manifest, receipt = _manifest(base)
    _check(manifest["daily_snapshot_sha256"] == snapshot["payload_sha256"], "base dataset differs from detection")
    _check(lock.read_text(encoding="utf-8").strip() == started_at, "fundamental daily lock owner changed")
    return root, target, latest, run, snapshot, base, manifest, receipt


def make_claim(snapshot, presentation, analysis_started):
    """A model alert retains its exact episode and same-day event identity."""
    day = snapshot["as_of"]
    _check(_instant(analysis_started) >= _instant(snapshot["observed_at"]), "analysis precedes detection")
    lookup = {row["identity"]: row for row in presentation}
    _check(len(lookup) == len(presentation), "duplicate source presentation identity")
    alerts = []
    for event in snapshot["events"]:
        if event.get("is_new_live_signal") is not True:
            continue
        _check(event.get("kind") == "WATCH_STARTED" and event.get("session") == day
               and event.get("candidate_date") == day and event.get("observation_kind") == "LIVE_OBSERVATION"
               and HEX.fullmatch(event.get("event_id", "")), "live fundamental candidate identity changed")
        symbol = event["symbol"]
        _check(re.fullmatch(r"[0-9A-Z]{4}", symbol), "unexpected fundamental candidate symbol")
        episode = f'{symbol}|{day}|{event["episode_id"]}'
        row = lookup.get(episode, {})
        _check(row.get("symbol") == symbol and row.get("signalDate") == day,
               "fundamental candidate has no exact presentation row")
        alerts.append({
            "alertId": "new-a:" + event["event_id"],
            "eventId": event["event_id"],
            "episodeIdentity": episode,
            "receivedAt": snapshot["observed_at"],
            "analysisCutoff": analysis_started,
            "signalDate": day,
            "signalType": "WEAK_EARLY_BETA",  # Existing Cloud report validation contract, not the legacy ledger.
            "symbolCode": symbol,
            "symbolName": row["companyName"] if row["nameStatus"] != "NAME_UNVERIFIED" else "",
            "entryPrice": None,
            "tradingViewUrl": f"https://jp.tradingview.com/chart/?symbol=TSE%3A{symbol}",
            "betaSelectors": ["A_BASE"],
        })
    _check(len(alerts) == snapshot["new_live_signals"]
           and len({alert["alertId"] for alert in alerts}) == len(alerts)
           and len({alert["episodeIdentity"] for alert in alerts}) == len(alerts)
           and len({alert["symbolCode"] for alert in alerts}) == len(alerts),
           "fundamental queue does not match all new same-day detections")
    alerts.sort(key=lambda alert: alert["symbolCode"])
    return {
        "claimId": digest([snapshot["payload_sha256"], analysis_started, alerts]),
        "generatedAt": analysis_started,
        "analysisStartedAt": analysis_started,
        "claimedCount": len(alerts),
        "snapshotSha256": snapshot["payload_sha256"],
        "alerts": alerts,
        "rules": {"destination": "html", "model": MODEL, "reasoningEffort": EFFORT,
                  "workflow": "premium-legacy-1fa6d89"},
    }


def _immutable(path, value):
    if path.exists():
        _check(read(path) == value, "retained fundamental evidence differs")
    else:
        atomic_write(path, value)


def _rows(folder, manifest):
    return [row for part in manifest["collections"]["presentation"] for row in _part(folder, part)]


def _project(claim, reports):
    validate_forward_reports(claim, reports, html_only=True)
    by_alert = {report["alertId"]: report for report in reports}
    result = {}
    for alert in claim["alerts"]:
        report = by_alert[alert["alertId"]]
        fields = _fields(report)
        result[alert["episodeIdentity"]] = {
            "identity": f'{alert["signalDate"]}|{alert["symbolCode"]}',
            "symbol": alert["symbolCode"],
            "signalDate": alert["signalDate"],
            "analysisCutoff": alert["analysisCutoff"],
            "auditStatus": "pass",
            "fields": [{"label": name, "text": fields[name]} for name in FIELD_ORDER],
        }
    return result


def _receipt(day, snapshot, claim, reports):
    result = {
        "schema": RECEIPT_SCHEMA, "day": day, "snapshotSha256": snapshot["payload_sha256"],
        "model": MODEL, "reasoningEffort": EFFORT, "claim": claim, "reports": reports,
        "presentation": _project(claim, reports),
    }
    result["sha256"] = digest(result)
    return result


def _history(root, day):
    records = {}
    for path in sorted((root / "fundamentals" / "verified").glob("*.json")):
        report_day = path.stem
        _check(dt.date.fromisoformat(report_day).isoformat() == report_day and report_day <= day
               and path.resolve().parent == path.parent, "unexpected fundamental history receipt")
        saved = read(path)
        evidence = {key: value for key, value in saved.items() if key != "sha256"}
        _check(saved.get("schema") == RECEIPT_SCHEMA and saved.get("day") == report_day
               and saved.get("sha256") == digest(evidence)
               and saved.get("model") == MODEL and saved.get("reasoningEffort") == EFFORT
               and saved["claim"]["snapshotSha256"] == saved["snapshotSha256"],
               "fundamental history evidence changed")
        _check(all(alert["signalDate"] == report_day for alert in saved["claim"]["alerts"])
               and saved["presentation"] == _project(saved["claim"], saved["reports"]),
               "fundamental history contract changed")
        for key, row in saved["presentation"].items():
            _check(key not in records, "fundamental episode occurs in multiple receipts")
            records[key] = row
    return records


def _historical_sha(pointer):
    if not pointer.exists():
        return None
    _check(pointer.resolve() == pointer and pointer.stat().st_size <= 1024,
           "invalid historical fundamental pointer")
    value = read(pointer)
    _check(isinstance(value, dict) and set(value) == {"sha256"}
           and isinstance(value["sha256"], str) and HEX.fullmatch(value["sha256"]),
           "invalid historical fundamental digest")
    return value["sha256"]


def _historical_history(root, sha, rows, forward, day):
    if sha is None:
        return {}, None
    path = root / "fundamentals" / "historical" / (sha + ".json")
    _check(path.resolve() == path, "historical fundamental ledger escaped private history")
    with path.open("rb") as source:
        raw = source.read(MAX_HISTORICAL_LEDGER_BYTES + 1)
    _check(len(raw) <= MAX_HISTORICAL_LEDGER_BYTES and hashlib.sha256(raw).hexdigest() == sha,
           "historical fundamental ledger changed")
    ledger = json.loads(raw)
    del raw
    _check(isinstance(ledger, dict) and ledger.get("schema") == HISTORICAL_SCHEMA and ledger.get("scope") == "owner-presentation"
           and isinstance(ledger.get("profiles"), dict), "invalid historical fundamental ledger")
    for key in ("frozen_snapshot_sha256", "frozen_archive_index_sha256",
                "frozen_owner_manifest_sha256", "inventory_sha256"):
        _check(isinstance(ledger.get(key), str) and HEX.fullmatch(ledger[key]),
               "missing historical fundamental ledger provenance")
    lookup = {row["identity"]: row for row in rows}
    _check(len(lookup) == len(rows), "duplicate owner presentation identity")
    matched = {}
    overlap = 0
    seen = set()
    for key, profile in ledger["profiles"].items():
        report = profile["presentation"]
        date = report["signalDate"]
        symbol = report["symbol"]
        company = profile["company_name"]
        _check(CODE.fullmatch(symbol) and dt.date.fromisoformat(date).isoformat() == date
               and re.fullmatch(re.escape(f"{symbol}|{date}|") + r"[1-9][0-9]*", key)
               and report["identity"] == f"{date}|{symbol}" and report["identity"] not in seen
               and profile["cutoff"] == report["analysisCutoff"] == f"{date}T16:15:00+09:00"
               and isinstance(company, str) and company.strip()
               and report["auditStatus"] == "pass", "historical fundamental episode differs")
        seen.add(report["identity"])
        fields = report["fields"]
        _check(set(report) == {"identity", "symbol", "signalDate", "analysisCutoff", "auditStatus", "fields"}
               and isinstance(fields, list) and len(fields) == len(FIELD_ORDER)
               and all(isinstance(field, dict) and set(field) == {"label", "text"}
                       and field["label"] == label and isinstance(field["text"], str) and field["text"].strip()
                       for label, field in zip(FIELD_ORDER, fields)), "invalid historical fundamental fields")
        for name in ("report_sha256", "validation_sha256", "validator_sha256"):
            _check(isinstance(profile.get(name), str) and HEX.fullmatch(profile[name]),
                   "missing historical fundamental review evidence")
        row = lookup.get(key)
        if (row is None or date > day or row["symbol"] != symbol or row["signalDate"] != date
                or row.get("companyName") != company or row.get("chartAllowed") is False
                or row.get("identityStatus") == "PRELISTING_HISTORY_MAPPING_UNVERIFIED"):
            continue
        if key in forward or row.get("fundamental") is not None:
            overlap += 1
            continue
        matched[key] = report
    counts = {"ledgerSha256": sha, "available": len(seen), "attached": len(matched),
              "alreadyVerified": overlap, "unmatched": len(seen) - len(matched) - overlap}
    return matched, counts


def _bundle(base, manifest, receipt, target, rows, analyses):
    matched = set()
    changed = False
    for row in rows:
        value = analyses.get(row["identity"])
        if value is None:
            continue
        _check(row["symbol"] == value["symbol"] and row["signalDate"] == value["signalDate"],
               "analysis would overwrite other presentation evidence")
        if row.get("fundamental") is not None:
            _check(row["fundamental"] == value and row.get("analysisCutoff") == value["analysisCutoff"],
                   "analysis would overwrite other presentation evidence")
            matched.add(row["identity"])
            continue
        row.update(analysisCutoff=value["analysisCutoff"], fundamental=value)
        matched.add(row["identity"])
        changed = True
    _check(matched == set(analyses), "analysis receipt no longer matches an exact owner presentation row")
    if not changed:
        return base, manifest["source_version"]
    source_version = digest([manifest["source_version"], analyses])
    output = target / ("bundle-fundamental-" + source_version)
    # Rebuild via a staging directory. Never rewrite the detection bundle or its snapshot.
    with tempfile.TemporaryDirectory(prefix="fundamental-bundle-", dir=target) as workspace:
        staged = Path(workspace) / "bundle"
        staged.mkdir()
        for descriptor in descriptors(manifest):
            _part(base, descriptor)
            if not descriptor["name"].startswith("presentation-"):
                shutil.copyfile(base / descriptor["name"], staged / descriptor["name"])
                _check(file_sha(staged / descriptor["name"]) == descriptor["sha256"],
                       "non-presentation part changed during staging")
        parts = []
        batch = []
        size = 2

        def flush():
            if batch:
                raw = encode(batch).encode()
                name = f"presentation-{len(parts):03d}.json"
                (staged / name).write_bytes(raw)
                parts.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(),
                              "rows": len(batch), "bytes": len(raw)})

        for row in rows:
            row_size = len(encode(row).encode()) + 1
            _check(row_size + 2 <= 65536, "oversized fundamental presentation row")
            if size + row_size > 65536:
                flush()
                batch = []
                size = 2
            batch.append(row)
            size += row_size
        flush()
        manifest["collections"]["presentation"] = parts
        manifest["source_version"] = manifest["input_header"]["source_version"] = source_version
        validate_manifest(manifest, prepared=True)
        raw = encode(manifest).encode()
        (staged / "manifest.json").write_bytes(raw)
        manifest_sha = hashlib.sha256(raw).hexdigest()
        receipt.update(manifest_sha256=manifest_sha, dataset_id="a-" + manifest_sha[:24],
                       source_version=source_version, bytes=len(raw) + sum(x["bytes"] for x in descriptors(manifest)),
                       parts=len(descriptors(manifest)))
        atomic_write(staged / "receipt.json", receipt)
        if output.exists():
            existing, existing_receipt = _manifest(output)
            _check(existing == manifest and existing_receipt == receipt, "saved analysis bundle differs")
            for descriptor in descriptors(existing):
                _part(output, descriptor)
        else:
            os.rename(staged, output)
    return output, source_version


def retain_verified_for_publication(root, run):
    """Attach proven earlier analyses even when today's research was held.

    This is a presentation-only publication step. It never reads a pending
    claim, creates an analysis receipt, runs detection, or sends notifications.
    """
    root = Path(root).resolve()
    historical_sha = _historical_sha(root / "fundamentals" / "historical" / "latest.json")
    if historical_sha is None and not any((root / "fundamentals" / "verified").glob("*.json")):
        return run
    forward = _history(root, run["latest_session"])
    if historical_sha is None and not forward:
        return run
    day = run["latest_session"]
    _check(run.get("identity") == "NEW_A_CLOUD_DAILY_V1" and run.get("strategy") == "A_BASE"
           and run.get("detection_executed") is True and run.get("dry_run") is False
           and not run.get("delayed_recovery") and dt.date.fromisoformat(day).isoformat() == day
           and HEX.fullmatch(run.get("source_sha256", "")),
           "cached analyses require the exact completed ordinary detection")
    target = root / "runs" / day / run["source_sha256"] / "live"
    base = Path(run["bundle_directory"])
    _check(root.name == "new-a-private" and target.resolve() == target and base.resolve() == base
           and base.parent == target and (base.name == "bundle"
               or re.fullmatch(r"bundle-fundamental-[0-9a-f]{64}", base.name))
           and Path(run["snapshot_file"]) == target / "snapshot.json",
           "cached analysis source escaped its immutable daily workspace")
    snapshot = validate_for_owner_read(read(target / "snapshot.json"),
                                       {"owner": True, "role_authorized": True, "current": True})
    manifest, receipt = _manifest(base)
    _check(snapshot["payload_sha256"] == run["snapshot_sha256"]
           and snapshot["source_sha256"] == run["source_sha256"] and snapshot["as_of"] == day
           and manifest["daily_snapshot_sha256"] == snapshot["payload_sha256"]
           and manifest["source_version"] == run["source_version"] and manifest["as_of"] == day,
           "cached analysis publication differs from the frozen detection")
    rows = _rows(base, manifest)
    historical, counts = _historical_history(root, historical_sha, rows, forward, day)
    output, source = _bundle(base, manifest, receipt, target, rows, {**historical, **forward})
    retained = {
        "historicalLedgerSha256": historical_sha,
        "historicalAvailable": counts["available"] if counts else 0,
        "forwardVerified": len(forward), "verifiedForwardSha256": digest(forward),
        "visible": sum(row.get("fundamental") is not None for row in rows),
        "newResearch": False,
    }
    latest = root / "latest-run.json"
    _check(read(latest) == run, "detection changed during cached analysis publication")
    result = {**run, "source_version": source, "bundle_directory": str(output),
              "retained_fundamentals": retained}
    if result != run:
        atomic_write(latest, result)
    return result


def stage(repo, runtime, day, started_at, action, analysis_started=None, reports_sha256=None):
    root, target, latest, run, snapshot, base, manifest, receipt = _context(repo, runtime, day, started_at)
    rows = _rows(base, manifest)
    stage_path = target / "fundamental-analysis"
    claim_path = stage_path / "claim.json"
    historical_pin = stage_path / "historical-source.json"
    reports_path = stage_path / "reports.json"
    _check(stage_path.resolve() == stage_path and claim_path.resolve() == claim_path,
           "fundamental claim location escaped its immutable directory")
    found = read(claim_path) if claim_path.exists() else None
    cutoff = found["analysisStartedAt"] if found else analysis_started
    _check(cutoff is not None, "missing analysis-start timestamp")
    claim = make_claim(snapshot, rows, cutoff)
    if action == "prepare":
        if not historical_pin.exists():
            sha = _historical_sha(root / "fundamentals" / "historical" / "latest.json")
            _immutable(historical_pin, {"sha256": sha})
        _immutable(claim_path, claim)
        return {"claimed": claim["claimedCount"], "claimPath": str(claim_path), "reportsPath": str(reports_path)}
    _check(found == claim, "fundamental claim changed before publication")
    reports = []
    if claim["claimedCount"]:
        _check(reports_path.resolve().parent == stage_path and HEX.fullmatch(reports_sha256 or ""),
               "fundamental report requires bounded reviewed bytes")
        raw = reports_path.read_bytes()
        _check(len(raw) <= 8 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == reports_sha256,
               "fundamental reports changed after Node evidence validation")
        reports = json.loads(raw.decode("utf-8-sig"))["reports"]
    else:
        _check(reports_sha256 is None, "unexpected model report for clean zero")
    saved = _receipt(day, snapshot, claim, reports)
    positive = root / "fundamentals" / "verified" / (day + ".json")
    _check(positive.resolve() == positive, "fundamental receipt escaped private history")
    if claim["claimedCount"]:
        _immutable(positive, saved)
    elif positive.exists():
        raise ValueError("zero detections conflict with a retained fundamental receipt")
    _check(historical_pin.resolve() == historical_pin, "historical pin escaped private run")
    historical_sha = read(historical_pin)["sha256"] if historical_pin.exists() else None
    _check(historical_sha is None or isinstance(historical_sha, str) and HEX.fullmatch(historical_sha),
           "invalid saved historical fundamental digest")
    forward = _history(root, day)
    historical, counts = _historical_history(root, historical_sha, rows, forward, day)
    output, source = _bundle(base, manifest, receipt, target, rows, {**historical, **forward})
    _check(read(latest) == run and (Path(runtime) / "daily.lock").read_text(encoding="utf-8").strip() == started_at,
           "detection or owner changed before final bundle handoff")
    result = {"ok": True, "status": "COMPLETE" if claim["claimedCount"] else "NO_NEW_SIGNALS",
              "imported": claim["claimedCount"], "posted": 0, "receiptSha256": saved["sha256"]}
    if counts is not None:
        result["historical"] = counts
    atomic_write(latest, {**run, "source_version": source, "bundle_directory": str(output), "fundamentals": result})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "finish"))
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--owner-start", required=True)
    parser.add_argument("--analysis-start")
    parser.add_argument("--reports-sha256")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    print(json.dumps(stage(repo, args.runtime, args.date, args.owner_start, args.action, args.analysis_start, args.reports_sha256)))


if __name__ == "__main__":
    main()
