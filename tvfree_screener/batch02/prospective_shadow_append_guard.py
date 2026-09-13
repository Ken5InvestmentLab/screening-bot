from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(lines: list[str]) -> str:
    raw = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compare_append_only_snapshots(old_lines: list[str], new_lines: list[str]) -> dict:
    old = [line for line in old_lines if line.strip()]
    new = [line for line in new_lines if line.strip()]

    errors: list[str] = []
    if len(new) < len(old):
        errors.append("new snapshot has fewer non-empty rows than old snapshot")

    shared = min(len(old), len(new))
    first_mismatch = None
    for i in range(shared):
        if old[i] != new[i]:
            first_mismatch = i + 1
            errors.append(f"historical row mismatch at non-empty line {first_mismatch}")
            break

    valid = not errors
    appended = max(0, len(new) - len(old)) if valid else 0
    return {
        "append_only_valid": valid,
        "decision": "APPEND_ONLY_OK" if valid else "BLOCK_AND_INVESTIGATE_SHADOW_MUTATION",
        "old_rows": len(old),
        "new_rows": len(new),
        "appended_rows": appended,
        "first_mismatch_row": first_mismatch,
        "errors": errors,
        "old_content_sha256": _digest(old),
        "new_content_sha256": _digest(new),
        "integrity": {
            "permits_historical_rewrite": False,
            "permits_truncation": False,
            "permits_reordering": False,
            "changes_model_or_thresholds": False,
            "uses_strategy_returns": False,
        },
    }


def compare_files(old_path: Path, new_path: Path) -> dict:
    return compare_append_only_snapshots(
        old_path.read_text(encoding="utf-8").splitlines(),
        new_path.read_text(encoding="utf-8").splitlines(),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify that a prospective shadow JSONL snapshot only appended rows")
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--new", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    result = compare_files(args.old, args.new)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    if not result["append_only_valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
