#!/usr/bin/env python3
"""Fail-closed verifier for recovered legacy Cloud Monster evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TEACHER_SHA256 = "f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2"
REQUIRED_IDENTITY_FILES = (
    "cloud_two_lane_union_jpx.csv",
    "cloud_priorityA_monsters_compare_teacher.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()

    teacher = args.artifact_dir / "teacher_ohlcv_4h_raw.csv"
    teacher_hash = sha256(teacher) if teacher.is_file() else None
    missing = [name for name in REQUIRED_IDENTITY_FILES if not (args.artifact_dir / name).is_file()]
    result = {
        "identity": "CLOUD_MONSTER_LEGACY_EXACT_V1",
        "teacher_input": {
            "path": str(teacher),
            "sha256": teacher_hash,
            "verified": teacher_hash == TEACHER_SHA256,
        },
        "missing_identity_files": missing,
        "score_generator_or_model_verified": False,
        "status": "EXACT_NOT_YET_RECOVERED",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["teacher_input"]["verified"] or missing or not result["score_generator_or_model_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
