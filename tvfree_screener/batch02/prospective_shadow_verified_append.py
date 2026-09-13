from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from prospective_shadow import ShadowCandidate, append_candidates
from prospective_shadow_admission_gate import evaluate_shadow_admission
from prospective_shadow_admission_receipt import verify_admission_receipt


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return _sha256_bytes(path.read_bytes())


def _normalize_rows(rows: Iterable[Mapping]) -> list[dict]:
    return [dict(r) for r in rows]


def _to_candidate(row: Mapping) -> ShadowCandidate:
    return ShadowCandidate(
        experiment_id=str(row["experiment_id"]),
        model_freeze_id=str(row["model_freeze_id"]),
        symbol=str(row["symbol"]),
        signal_date=str(row["signal_date"]),
        bin_name=str(row["bin_name"]),
        feature_cutoff=str(row["feature_cutoff"]),
        source_tag=str(row["source_tag"]),
        score=None if row.get("score") in (None, "") else float(row["score"]),
        rank=None if row.get("rank") in (None, "") else int(row["rank"]),
        payload_sha256=None if row.get("payload_sha256") in (None, "") else str(row["payload_sha256"]),
    )


def verified_append(
    output_path: Path,
    manifest: Mapping,
    rows: Iterable[Mapping],
    admission_result: Mapping,
    receipt: Mapping,
) -> dict:
    rows_n = _normalize_rows(rows)

    live_admission = evaluate_shadow_admission(manifest, rows_n)
    if live_admission != dict(admission_result):
        return {
            "appended": False,
            "decision": "BLOCK_APPEND_ADMISSION_REPLAY_MISMATCH",
            "errors": ["admission_result_does_not_match_live_replay"],
            "output_sha256_before": _file_sha256(output_path),
            "output_sha256_after": _file_sha256(output_path),
            "production_modified": False,
        }

    receipt_check = verify_admission_receipt(receipt, manifest, rows_n, admission_result)
    if not receipt_check.get("valid", False):
        return {
            "appended": False,
            "decision": "BLOCK_APPEND_RECEIPT_INVALID",
            "errors": list(receipt_check.get("errors", [])),
            "receipt_check": receipt_check,
            "output_sha256_before": _file_sha256(output_path),
            "output_sha256_after": _file_sha256(output_path),
            "production_modified": False,
        }

    before = _file_sha256(output_path)
    candidates = [_to_candidate(row) for row in rows_n]
    append_result = append_candidates(output_path, candidates)
    after = _file_sha256(output_path)

    return {
        "appended": True,
        "decision": "VERIFIED_APPEND_COMPLETE",
        "receipt_check": receipt_check,
        "append_result": append_result,
        "output_sha256_before": before,
        "output_sha256_after": after,
        "integrity": {
            "live_admission_replayed": True,
            "receipt_required": True,
            "exact_batch_pinned": True,
            "direct_production_write": False,
            "opens_strategy_returns": False,
            "changes_model": False,
            "changes_thresholds": False,
        },
    }


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = _load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ValueError("rows must be a JSON array or JSONL of objects")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Verified prospective-shadow append requiring live admission replay and exact receipt verification")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--admission", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--shadow-jsonl", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = verified_append(
        args.shadow_jsonl,
        _load_json(args.manifest),
        _load_rows(args.rows),
        _load_json(args.admission),
        _load_json(args.receipt),
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    raise SystemExit(0 if result["appended"] else 2)


if __name__ == "__main__":
    main()
