from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow import (
    ShadowCandidate,
    append_candidates,
    resolve_shadow_file,
)


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


def load_candidate_rows(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    raise ValueError("candidate input must be .csv or .jsonl")


def candidate_from_row(row: dict, freeze: dict) -> ShadowCandidate:
    if row.get("experiment_id") and row["experiment_id"] != freeze["experiment_id"]:
        raise ValueError("candidate experiment_id does not match freeze manifest")
    if row.get("model_freeze_id") and row["model_freeze_id"] != freeze["model_freeze_id"]:
        raise ValueError("candidate model_freeze_id does not match freeze manifest")
    payload_sha = row.get("payload_sha256") or None
    return ShadowCandidate(
        experiment_id=freeze["experiment_id"],
        model_freeze_id=freeze["model_freeze_id"],
        symbol=str(row["symbol"]).replace(".0", "").upper(),
        signal_date=str(row["signal_date"])[:10],
        bin_name=str(row["bin_name"]),
        feature_cutoff=str(row["feature_cutoff"]),
        source_tag=str(row["source_tag"]),
        score=float(row["score"]) if row.get("score") not in (None, "") else None,
        rank=int(row["rank"]) if row.get("rank") not in (None, "") else None,
        payload_sha256=payload_sha,
    )


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
    rows = load_candidate_rows(Path(args.candidates))
    candidates = [candidate_from_row(row, freeze) for row in rows]
    summary = append_candidates(Path(args.shadow), candidates)
    out = {
        "operation": "ingest",
        "experiment_id": freeze["experiment_id"],
        "model_freeze_id": freeze["model_freeze_id"],
        "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
        "candidate_input_sha256": sha256_file(Path(args.candidates)),
        **summary,
    }
    write_summary(Path(args.summary), out)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_resolve(args: argparse.Namespace) -> None:
    freeze = load_freeze_manifest(Path(args.freeze_manifest), args.freeze_sha256)
    daily_rows, sessions = read_daily_csv(Path(args.daily))
    summary = resolve_shadow_file(Path(args.shadow), Path(args.resolved), daily_rows, sessions)
    out = {
        "operation": "resolve",
        "experiment_id": freeze["experiment_id"],
        "model_freeze_id": freeze["model_freeze_id"],
        "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
        "shadow_input_sha256": sha256_file(Path(args.shadow)),
        "daily_input_sha256": sha256_file(Path(args.daily)),
        **summary,
    }
    write_summary(Path(args.summary), out)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local-only prospective shadow evidence helper")
    sub = p.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--freeze-manifest", required=True)
    ingest.add_argument("--freeze-sha256")
    ingest.add_argument("--candidates", required=True)
    ingest.add_argument("--shadow", required=True)
    ingest.add_argument("--summary", required=True)
    ingest.set_defaults(func=cmd_ingest)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--freeze-manifest", required=True)
    resolve.add_argument("--freeze-sha256")
    resolve.add_argument("--shadow", required=True)
    resolve.add_argument("--daily", required=True)
    resolve.add_argument("--resolved", required=True)
    resolve.add_argument("--summary", required=True)
    resolve.set_defaults(func=cmd_resolve)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
