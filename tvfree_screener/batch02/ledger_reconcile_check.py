from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ENTRY_RE = re.compile(r"^##\s+([^\n]+?)\s*$", re.MULTILINE)


def entry_ids(text: str) -> list[str]:
    ids: list[str] = []
    for heading in ENTRY_RE.findall(text):
        entry_id = heading.split(" — ", 1)[0].strip()
        if entry_id and entry_id not in ids:
            ids.append(entry_id)
    return ids


def compare_ledger(ledger_text: str, pending_text: str) -> dict:
    ledger = set(entry_ids(ledger_text))
    pending = entry_ids(pending_text)
    present = [x for x in pending if x in ledger]
    missing = [x for x in pending if x not in ledger]
    return {
        "pending_entries": len(pending),
        "present_entries": len(present),
        "missing_entries": len(missing),
        "present": present,
        "missing": missing,
        "safe_to_delete_pending_file": bool(pending) and not missing,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only ledger reconciliation checker")
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--pending", type=Path, required=True)
    ap.add_argument("--json-output", type=Path)
    args = ap.parse_args()

    result = compare_ledger(
        args.ledger.read_text(encoding="utf-8"),
        args.pending.read_text(encoding="utf-8"),
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(raw)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
