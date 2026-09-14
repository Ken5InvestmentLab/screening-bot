from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_verified_resolve import verified_resolve_shadow_file
from tvfree_screener.batch02.prospective_shadow_session_calendar_guard import validate_xtks_calendar
from tvfree_screener.batch02.prospective_shadow_daily_endpoint_guard import validate_daily_endpoint_dataset
from tvfree_screener.batch02.prospective_shadow_admission_gate import evaluate_shadow_admission
from tvfree_screener.batch02.prospective_shadow_verified_append import verified_append


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_freeze_manifest(path: Path, expected_sha256: str | None = None) -> dict:
    actual = sha256_file(path)
    if expected_sha256 and actual.lower() != expected_sha256.lower():
        raise RuntimeError(f"freeze manifest SHA mismatch: {actual}")
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"experiment_id", "model_freeze_id", "frozen_at", "model_spec_sha256"}
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"freeze manifest missing fields: {missing}")
    data["freeze_manifest_sha256"] = actual
    return data


def _receipt_manifest(freeze: dict) -> dict:
    data = dict(freeze)
    data.pop("freeze_manifest_sha256", None)
    return data


def _default_xtks_calendar_paths() -> tuple[Path, Path]:
    tvfree_root = Path(__file__).resolve().parents[1]
    reference = tvfree_root / "batch01" / "reference"
    return reference / "xtks_sessions.csv", reference / "xtks_sessions.manifest.json"


def _shadow_signal_dates(path: Path) -> list[str]:
    dates: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            dates.append(str(row["signal_date"])[:10])
    return sorted(set(dates))


def load_candidate_rows(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    raise ValueError("candidate input must be .csv or .jsonl")


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "true":
            return True
        if text == "false":
            return False
    return value


def normalize_candidate_row(row: dict, freeze: dict) -> dict:
    if row.get("experiment_id") and row["experiment_id"] != freeze["experiment_id"]:
        raise ValueError("candidate experiment_id does not match freeze manifest")
    if row.get("model_freeze_id") and row["model_freeze_id"] != freeze["model_freeze_id"]:
        raise ValueError("candidate model_freeze_id does not match freeze manifest")
    out = dict(row)
    out["experiment_id"] = freeze["experiment_id"]
    out["model_freeze_id"] = freeze["model_freeze_id"]
    out["symbol"] = str(row["symbol"]).replace(".0", "").upper()
    out["signal_date"] = str(row["signal_date"])[:10]
    out["bin_name"] = str(row["bin_name"])
    out["feature_cutoff"] = str(row["feature_cutoff"])
    out["source_tag"] = str(row["source_tag"])
    if row.get("rank") not in (None, ""):
        out["rank"] = int(row["rank"])
    if row.get("score") not in (None, ""):
        out["score"] = float(row["score"])
    if "data_sufficient" in out:
        out["data_sufficient"] = _parse_bool(out["data_sufficient"])
    if isinstance(out.get("missing_fields"), str):
        text = out["missing_fields"].strip()
        if text == "":
            out["missing_fields"] = ""
        else:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
            out["missing_fields"] = parsed
    return out


def candidate_from_row(row: dict, freeze: dict):
    """Backward-compatible normalization helper; returns a normalized candidate mapping."""
    return normalize_candidate_row(row, freeze)


def read_daily_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    sessions = sorted({str(r["date"])[:10] for r in rows if r.get("date")})
    normalized = []
    for r in rows:
        normalized.append({
            "symbol": str(r["symbol"]).replace(".0", "").upper(),
            "date": str(r["date"])[:10],
            "open": r.get("open"),
            "close": r.get("close"),
        })
    return normalized, sessions


def write_summary(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def cmd_ingest(args: argparse.Namespace) -> None:
    freeze = load_freeze_manifest(Path(args.freeze_manifest), args.freeze_sha256)
    manifest = _receipt_manifest(freeze)
    raw_rows = load_candidate_rows(Path(args.candidates))
    rows = [normalize_candidate_row(row, manifest) for row in raw_rows]
    admission = json.loads(Path(args.admission).read_text(encoding="utf-8"))
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))

    live_admission = evaluate_shadow_admission(manifest, rows)
    if live_admission != admission:
        out = {
            "operation": "ingest",
            "appended": False,
            "decision": "BLOCK_CLI_ADMISSION_REPLAY_MISMATCH",
            "experiment_id": manifest["experiment_id"],
            "model_freeze_id": manifest["model_freeze_id"],
            "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
            "candidate_input_sha256": sha256_file(Path(args.candidates)),
        }
        write_summary(Path(args.summary), out)
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(2)

    result = verified_append(Path(args.shadow), manifest, rows, admission, receipt)
    out = {
        "operation": "ingest",
        "experiment_id": manifest["experiment_id"],
        "model_freeze_id": manifest["model_freeze_id"],
        "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
        "candidate_input_sha256": sha256_file(Path(args.candidates)),
        **result,
    }
    write_summary(Path(args.summary), out)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    if not result.get("appended", False):
        raise SystemExit(2)


def cmd_resolve(args: argparse.Namespace) -> None:
    freeze = load_freeze_manifest(Path(args.freeze_manifest), args.freeze_sha256)
    daily_manifest_path = Path(args.daily_manifest)
    daily_manifest = json.loads(daily_manifest_path.read_text(encoding="utf-8"))
    daily_provenance = validate_daily_endpoint_dataset(Path(args.daily), daily_manifest)
    if not daily_provenance.get("endpoint_dataset_valid", False):
        out = {
            "operation": "resolve",
            "resolved_written": False,
            "decision": "BLOCK_CLI_DAILY_ENDPOINT_DATASET",
            "experiment_id": freeze["experiment_id"],
            "model_freeze_id": freeze["model_freeze_id"],
            "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
            "shadow_input_sha256": sha256_file(Path(args.shadow)),
            "daily_input_sha256": sha256_file(Path(args.daily)),
            "daily_manifest_sha256": sha256_file(daily_manifest_path),
            "daily_endpoint_provenance": daily_provenance,
        }
        write_summary(Path(args.summary), out)
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(2)

    daily_rows, _ = read_daily_csv(Path(args.daily))
    default_sessions_csv, default_sessions_manifest = _default_xtks_calendar_paths()
    sessions_csv = Path(getattr(args, "sessions_csv", None) or default_sessions_csv)
    sessions_manifest = Path(getattr(args, "sessions_manifest", None) or default_sessions_manifest)
    sessions, calendar = validate_xtks_calendar(
        sessions_csv,
        sessions_manifest,
        _shadow_signal_dates(Path(args.shadow)),
    )
    if not calendar.get("calendar_valid", False):
        out = {
            "operation": "resolve",
            "resolved_written": False,
            "decision": "BLOCK_CLI_SESSION_CALENDAR",
            "experiment_id": freeze["experiment_id"],
            "model_freeze_id": freeze["model_freeze_id"],
            "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
            "shadow_input_sha256": sha256_file(Path(args.shadow)),
            "daily_input_sha256": sha256_file(Path(args.daily)),
            "daily_manifest_sha256": sha256_file(daily_manifest_path),
            "daily_endpoint_provenance": daily_provenance,
            "session_calendar": calendar,
        }
        write_summary(Path(args.summary), out)
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(2)

    result = verified_resolve_shadow_file(Path(args.shadow), Path(args.resolved), daily_rows, sessions)
    out = {
        "operation": "resolve",
        "experiment_id": freeze["experiment_id"],
        "model_freeze_id": freeze["model_freeze_id"],
        "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
        "shadow_input_sha256": sha256_file(Path(args.shadow)),
        "daily_input_sha256": sha256_file(Path(args.daily)),
        "daily_manifest_sha256": sha256_file(daily_manifest_path),
        "daily_endpoint_provenance": daily_provenance,
        "session_calendar": calendar,
        **result,
    }
    write_summary(Path(args.summary), out)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    if not result.get("resolved_written", False):
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local-only prospective shadow evidence helper")
    sub = p.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Verified ingest only; admission and receipt are mandatory")
    ingest.add_argument("--freeze-manifest", required=True)
    ingest.add_argument("--freeze-sha256")
    ingest.add_argument("--candidates", required=True)
    ingest.add_argument("--admission", required=True)
    ingest.add_argument("--receipt", required=True)
    ingest.add_argument("--shadow", required=True)
    ingest.add_argument("--summary", required=True)
    ingest.set_defaults(func=cmd_ingest)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--freeze-manifest", required=True)
    resolve.add_argument("--freeze-sha256")
    resolve.add_argument("--shadow", required=True)
    resolve.add_argument("--daily", required=True)
    resolve.add_argument("--daily-manifest", required=True)
    resolve.add_argument("--resolved", required=True)
    resolve.add_argument("--sessions-csv")
    resolve.add_argument("--sessions-manifest")
    resolve.add_argument("--summary", required=True)
    resolve.set_defaults(func=cmd_resolve)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
