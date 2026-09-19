"""Run the recovered Cloud Monster lineage from the pinned raw artifact.

The historical sources are preserved byte-for-byte apart from the repository's
line-ending policy.  This runner changes only their hard-coded work directory
in memory, then executes the original stages in order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xc
import sklearn


INPUTS = (
    "teacher_ohlcv_4h_raw.csv",
    "teacher_bottom_confirmed.csv",
    "teacher_stable6_confirmed.csv",
)
STAGES = (
    ("build_cloud4h_dedup_sep.py", "BASE=Path('/mnt/data/v3r')"),
    ("build_mtf_fast.py", "B=Path('/mnt/data/v3r')"),
    ("relabel_jpx_5bd.py", "B=Path('/mnt/data/v3r')"),
    ("../recovered_selector.py", "B = Path('/mnt/data/v3r')"),
)
EXPECTED_RAW_SHA256 = (
    "f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def adapt_source(source: str, marker: str, work_dir: Path) -> str:
    if source.count(marker) != 1:
        raise RuntimeError(f"expected one work-directory marker, found {source.count(marker)}")
    variable = marker.split("=", 1)[0].rstrip()
    replacement = f"{variable}=Path({str(work_dir)!r})"
    if " = " in marker:
        replacement = f"{variable} = Path({str(work_dir)!r})"
    return source.replace(marker, replacement, 1)


def run_stage(pack_dir: Path, work_dir: Path, relative: str, marker: str) -> dict:
    source_path = (pack_dir / "source" / relative).resolve()
    if relative.startswith("../"):
        source_path = (pack_dir / "source" / relative).resolve()
    source = source_path.read_text(encoding="utf-8")
    adapted = adapt_source(source, marker, work_dir.resolve())
    completed = subprocess.run(
        [sys.executable, "-c", adapted],
        cwd=work_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    log_path = work_dir / f"{source_path.stem}.log"
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"{source_path.name} failed; see {log_path}")
    return {
        "source": str(source_path.relative_to(pack_dir)),
        "source_sha256": sha256(source_path),
        "log": log_path.name,
        "returncode": completed.returncode,
    }


def metrics(values: pd.Series) -> dict:
    x = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    ranked = np.sort(x)[::-1]
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "win": float(np.mean(x > 0)),
        "plus10": float(np.mean(x >= 0.10)),
        "plus20": float(np.mean(x >= 0.20)),
        "plus30": float(np.mean(x >= 0.30)),
        "minus10": float(np.mean(x <= -0.10)),
        "minus20": float(np.mean(x <= -0.20)),
        "max_up": float(np.max(x)),
        "max_down": float(np.min(x)),
        "top3_excluded_mean": float(np.mean(ranked[3:])),
        "top5_excluded_mean": float(np.mean(ranked[5:])),
    }


def compare_rows(pack_dir: Path, work_dir: Path) -> tuple[pd.DataFrame, dict]:
    expected = pd.read_csv(pack_dir / "artifacts" / "cloud_two_lane_union_jpx.csv")
    expected = expected[expected["lane"].eq("Monster")].copy()
    actual = pd.read_csv(work_dir / "cloud_monster_priority_jpx.csv")
    columns = ["symbol", "timestamp", "date", "close", "ret5"]
    for frame in (expected, actual):
        frame["symbol"] = frame["symbol"].astype(str)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame.sort_values(["symbol", "date", "timestamp"], inplace=True)
        frame.reset_index(drop=True, inplace=True)
    identity_columns_equal = expected[columns[:3]].equals(actual[columns[:3]])
    close_equal = bool(np.array_equal(expected["close"].to_numpy(), actual["close"].to_numpy()))
    ret5_max_abs_diff = float(
        np.max(np.abs(expected["ret5"].to_numpy() - actual["ret5"].to_numpy()))
    )
    exact = bool(
        len(expected) == len(actual)
        and identity_columns_equal
        and close_equal
        and ret5_max_abs_diff <= 1e-15
    )
    result = {
        "expected_n": int(len(expected)),
        "actual_n": int(len(actual)),
        "identity_columns_equal": identity_columns_equal,
        "close_bitwise_equal": close_equal,
        "ret5_max_abs_diff": ret5_max_abs_diff,
        "exact_rows_reproduced": exact,
        "metrics": metrics(actual["ret5"]),
    }
    return actual, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    pack_dir = Path(__file__).resolve().parent
    input_dir = args.input_dir.resolve()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    input_receipts = {}
    for name in INPUTS:
        source = input_dir / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = work_dir / name
        shutil.copy2(source, target)
        input_receipts[name] = {"sha256": sha256(source), "bytes": source.stat().st_size}
    if input_receipts["teacher_ohlcv_4h_raw.csv"]["sha256"] != EXPECTED_RAW_SHA256:
        raise RuntimeError("raw OHLCV SHA-256 does not match artifact 10266329903")

    stage_receipts = [run_stage(pack_dir, work_dir, *stage) for stage in STAGES]
    rows, comparison = compare_rows(pack_dir, work_dir)
    reproduced_path = work_dir / "cloud_monster_legacy_reproduced.csv"
    rows.to_csv(reproduced_path, index=False)

    receipt = {
        "identity": "CLOUD_MONSTER_LEGACY_EXACT_V1",
        "status": "EXACT_REPRODUCED" if comparison["exact_rows_reproduced"] else "MISMATCH",
        "input_artifact_id": "10266329903",
        "inputs": input_receipts,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "exchange_calendars": xc.__version__,
        },
        "stages": stage_receipts,
        "comparison": comparison,
        "reproduced_rows": {
            "path": reproduced_path.name,
            "sha256": sha256(reproduced_path),
        },
    }
    receipt_path = args.receipt.resolve() if args.receipt else work_dir / "raw_reproduction_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not comparison["exact_rows_reproduced"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
