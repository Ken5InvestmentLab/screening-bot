"""Build a standalone local preview without writing ledger or production state."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from weak_early_beta.ledger import DEFAULT_LEDGER, read_ledger
from weak_early_beta.report import write_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger_path, destination = args.ledger.resolve(), args.output.resolve()
    protected = (ROOT / "weak_early_beta" / "state").resolve()
    if destination == protected or protected in destination.parents:
        raise ValueError("preview output must be outside production state")
    if destination == ledger_path or destination in ledger_path.parents:
        raise ValueError("preview output must not contain the source ledger")
    before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    frame = read_ledger(ledger_path)
    destination.mkdir(parents=True, exist_ok=True)
    write_report(frame, destination / "weak_early_beta_latest.html",
                 destination / "review_metrics.csv", destination / "review_monthly_metrics.csv")
    for filename in ("weak-early-beta-interactions.js", "weak-early-beta-theme-init.js"):
        target = destination / filename
        source = ROOT / "reports" / filename
        if target.resolve() != source.resolve():
            shutil.copyfile(source, target)
    assets = destination / "report-assets"
    assets.mkdir(exist_ok=True)
    for filename in ("discord-light.png", "discord-dark.png", "coconala-light.png", "coconala-dark.png",
                     "x-light.png", "x-dark.png", "cloud-logo-light.png", "cloud-logo-dark.png"):
        source, target = ROOT / "reports" / "report-assets" / filename, assets / filename
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
    after = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("source ledger changed during preview generation")
    receipt = {"source_sha256": before, "source_rows": len(frame), "source_unchanged": True,
               "notifications_sent": 0, "deployment": False,
               "note": "Local preview only. Missing verified prices remain unavailable."}
    (destination / "review_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
