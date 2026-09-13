from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(payload: Mapping) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def build_authorization_receipt(
    authorization_result: Mapping,
    observed_heads: Mapping[str, str],
    supervisor_contract_sha256: str,
    created_at: str,
) -> dict:
    decision = str(authorization_result.get("decision", ""))
    if decision not in {"AUTHORIZE_PROSPECTIVE_SHADOW_START", "BLOCK_PROSPECTIVE_SHADOW_START"}:
        raise ValueError("authorization_result has unsupported decision")
    if not observed_heads:
        raise ValueError("observed_heads must be nonempty")
    for branch, sha in observed_heads.items():
        if not str(branch).strip() or len(str(sha)) != 40:
            raise ValueError("invalid observed branch HEAD")
    if len(supervisor_contract_sha256) != 64:
        raise ValueError("invalid supervisor_contract_sha256")
    if not str(created_at).strip():
        raise ValueError("created_at is required")

    authorization_sha256 = sha256_bytes(canonical_json_bytes(dict(authorization_result)))
    source_heads = dict(sorted((str(k), str(v)) for k, v in observed_heads.items()))
    core = {
        "receipt_type": "PROSPECTIVE_SHADOW_AUTHORIZATION_RECEIPT",
        "created_at": created_at,
        "decision": decision,
        "authorization_result_sha256": authorization_sha256,
        "supervisor_contract_sha256": supervisor_contract_sha256,
        "source_branch_heads": source_heads,
        "production_authorized": False,
        "note": "This receipt pins the evidence-collection authorization event only. It never authorizes production promotion.",
    }
    core["receipt_sha256"] = sha256_bytes(canonical_json_bytes(core))
    return core


def verify_authorization_receipt(
    receipt: Mapping,
    authorization_result: Mapping,
    observed_heads: Mapping[str, str],
    supervisor_contract_sha256: str,
) -> dict:
    errors: list[str] = []
    expected_auth_sha = sha256_bytes(canonical_json_bytes(dict(authorization_result)))
    if receipt.get("authorization_result_sha256") != expected_auth_sha:
        errors.append("authorization_result_sha256_mismatch")
    if receipt.get("supervisor_contract_sha256") != supervisor_contract_sha256:
        errors.append("supervisor_contract_sha256_mismatch")
    expected_heads = dict(sorted((str(k), str(v)) for k, v in observed_heads.items()))
    if receipt.get("source_branch_heads") != expected_heads:
        errors.append("source_branch_heads_mismatch")

    body = dict(receipt)
    stated_receipt_sha = body.pop("receipt_sha256", None)
    actual_receipt_sha = sha256_bytes(canonical_json_bytes(body))
    if stated_receipt_sha != actual_receipt_sha:
        errors.append("receipt_sha256_mismatch")

    valid = not errors
    return {
        "valid": valid,
        "decision": "RECEIPT_VERIFIED" if valid else "RECEIPT_INVALID",
        "errors": errors,
    }


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Create or verify prospective-shadow authorization receipts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--authorization-json", type=Path, required=True)
    c.add_argument("--heads-json", type=Path, required=True)
    c.add_argument("--supervisor-contract-sha256", required=True)
    c.add_argument("--created-at", required=True)
    c.add_argument("--output", type=Path, required=True)

    v = sub.add_parser("verify")
    v.add_argument("--receipt-json", type=Path, required=True)
    v.add_argument("--authorization-json", type=Path, required=True)
    v.add_argument("--heads-json", type=Path, required=True)
    v.add_argument("--supervisor-contract-sha256", required=True)

    args = ap.parse_args()
    auth = _load_json(args.authorization_json)
    heads = _load_json(args.heads_json)

    if args.cmd == "create":
        receipt = build_authorization_receipt(auth, heads, args.supervisor_contract_sha256, args.created_at)
        raw = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print(raw, end="")
    else:
        receipt = _load_json(args.receipt_json)
        result = verify_authorization_receipt(receipt, auth, heads, args.supervisor_contract_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0 if result["valid"] else 2)


if __name__ == "__main__":
    main()
