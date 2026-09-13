from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_receipt(inputs: dict[str, Path], audit_result: dict) -> dict:
    files = {}
    for name, path in sorted(inputs.items()):
        files[name] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    payload = {
        "receipt_type": "PROSPECTIVE_SHADOW_EVIDENCE_CHAIN_RECEIPT",
        "experiment_id": audit_result.get("experiment_id"),
        "model_freeze_id": audit_result.get("model_freeze_id"),
        "audit_decision": audit_result.get("decision"),
        "audit_ok": audit_result.get("ok") is True,
        "inputs": files,
        "integrity": {
            "read_only": True,
            "model_changes": False,
            "selection_changes": False,
            "production_changes": False,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Create immutable input receipt for prospective shadow evidence-chain audit")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--continuity", type=Path, required=True)
    ap.add_argument("--append-guard", type=Path, required=True)
    ap.add_argument("--maturity", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--audit-result", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    audit_result = json.loads(args.audit_result.read_text(encoding="utf-8"))
    receipt = build_receipt(
        {
            "manifest": args.manifest,
            "continuity": args.continuity,
            "append_guard": args.append_guard,
            "maturity": args.maturity,
            "report": args.report,
            "audit_result": args.audit_result,
        },
        audit_result,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    args.output.write_text(raw + "\n", encoding="utf-8")
    print(raw)


if __name__ == "__main__":
    main()
