from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from ohlcv_supplement import build_missing_inventory


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_receipt(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"input file does not exist: {path}")
    return {
        "name": path.name,
        "size_bytes": int(path.stat().st_size),
        "sha256": _sha256(path),
    }


def run_missing_inventory(expected_path: str | Path, observed_path: str | Path, outdir: str | Path) -> dict:
    """Run the frozen outcome-blind missing-inventory builder on exact input bytes.

    This wrapper deliberately binds both input files and both emitted outputs by SHA-256.
    It does not read OHLC returns, strategy outcomes, ranks, labels, or thresholds.
    """
    expected_path = Path(expected_path)
    observed_path = Path(observed_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    expected_receipt = _file_receipt(expected_path)
    observed_receipt = _file_receipt(observed_path)
    expected = pd.read_csv(expected_path, low_memory=False)
    observed = pd.read_csv(observed_path, low_memory=False)

    inventory, builder_receipt = build_missing_inventory(expected, observed)
    inventory_path = outdir / "missing_inventory.csv"
    inventory.to_csv(inventory_path, index=False)

    bundle = {
        "contract": "CORE24_REAL_MISSING_INVENTORY_V1",
        "expected_input": expected_receipt,
        "observed_input": observed_receipt,
        "builder_receipt": builder_receipt,
        "missing_inventory_output": _file_receipt(inventory_path),
        "outcome_informed": False,
        "performance_opened": False,
    }
    payload = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    bundle["bundle_sha256"] = hashlib.sha256(payload).hexdigest()

    receipt_path = outdir / "missing_inventory_receipt.json"
    receipt_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle


def main() -> None:
    ap = argparse.ArgumentParser(description="Build SHA-bound Core24 missing OHLCV inventory")
    ap.add_argument("--expected", required=True, help="Pinned expected endpoint-key CSV")
    ap.add_argument("--observed", required=True, help="Pinned observed endpoint-key/OHLCV CSV")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    bundle = run_missing_inventory(args.expected, args.observed, args.outdir)
    print(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
