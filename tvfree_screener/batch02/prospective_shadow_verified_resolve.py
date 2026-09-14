from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Mapping, Sequence

from prospective_shadow import resolve_shadow_file
from prospective_shadow_resolution_continuity_guard import compare_resolution_snapshots


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("each resolved JSONL row must be an object")
            rows.append(item)
    return rows


def verified_resolve_shadow_file(
    input_path: Path,
    output_path: Path,
    daily_rows: Iterable[Mapping],
    sessions: Sequence[str],
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    before_sha = _sha256(output_path)

    with TemporaryDirectory(dir=output_path.parent) as tmp:
        staged = Path(tmp) / "resolved.jsonl"
        resolution = resolve_shadow_file(input_path, staged, daily_rows, sessions)
        previous_rows = _load_jsonl(output_path)
        current_rows = _load_jsonl(staged)
        continuity = compare_resolution_snapshots(previous_rows, current_rows)

        if not continuity.get("resolution_continuity_valid", False):
            return {
                "resolved_written": False,
                "decision": "BLOCK_RESOLUTION_CONTINUITY_FAILURE",
                "resolution": resolution,
                "continuity": continuity,
                "output_sha256_before": before_sha,
                "output_sha256_after": _sha256(output_path),
                "integrity": {
                    "staged_before_replace": True,
                    "resolved_history_preserved_on_failure": True,
                    "production_modified": False,
                },
            }

        staged.replace(output_path)

    after_sha = _sha256(output_path)
    return {
        "resolved_written": True,
        "decision": "VERIFIED_RESOLUTION_WRITE_COMPLETE",
        "resolution": resolution,
        "continuity": continuity,
        "output_sha256_before": before_sha,
        "output_sha256_after": after_sha,
        "integrity": {
            "staged_before_replace": True,
            "continuity_required_before_replace": True,
            "resolved_rows_immutable_after_first_resolution": True,
            "production_modified": False,
        },
    }
