"""Check a model-verified historical batch before the import CLI changes state.

This checks provenance and manifest alignment. It cannot replace reading the
primary disclosures and independently checking the candidate's claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weak_early_beta.historical_fundamentals import FIELD_ORDER, validate_historical_report  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_candidate(path: Path, manifest: dict, receipt_paths: list[Path]) -> list[str]:
    errors: list[str] = []
    payload = load_json(path)
    reports = payload.get("reports", [])
    if not reports:
        return [f"{path.name}: no reports"]
    records = {row["identity"]: row for row in manifest["records"]}
    candidate_sha = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    receipts = [load_json(item) for item in receipt_paths]
    seen: set[str] = set()
    for report in reports:
        row_id = report.get("identity", "")
        prefix = f"{path.name}:{row_id}"
        if row_id in seen:
            errors.append(f"{prefix}: duplicate identity in candidate")
        seen.add(row_id)
        try:
            validated_id = validate_historical_report(report)
            if validated_id != row_id:
                errors.append(f"{prefix}: declared identity differs from validated identity")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: {exc}")
        manifest_row = records.get(row_id)
        if manifest_row is None:
            errors.append(f"{prefix}: identity missing from manifest")
        else:
            for key, actual in (
                ("company_name", report.get("companyName")),
                ("analysis_cutoff", report.get("analysisCutoff")),
            ):
                if actual != manifest_row[key]:
                    errors.append(f"{prefix}: {key} does not match manifest")
            if sorted(report.get("selectorNames", [])) != sorted(manifest_row["selector_names"]):
                errors.append(f"{prefix}: selectorNames do not match manifest")
        if report.get("auditStatus") != "pass":
            errors.append(f"{prefix}: auditStatus is not pass")
        if [item.get("name") for item in report.get("fields", [])] != list(FIELD_ORDER):
            errors.append(f"{prefix}: seven fields are missing, duplicated, or out of order")
        for field in report.get("fields", []):
            value = field.get("value")
            if field.get("name") in ("開示リンク", "Sources") and isinstance(value, str) and "\\n" in value:
                errors.append(f"{prefix}: {field['name']} contains escaped newline text")
        matching = [
            item
            for item in receipts
            if item.get("identity") == row_id
            and str(item.get("sha256", "")).lower() == candidate_sha
            and (ROOT / str(item.get("candidate_path", ""))).resolve() == path.resolve()
        ]
        if len(matching) != 1:
            errors.append(f"{prefix}: exactly one matching generation receipt is required")
            continue
        receipt = matching[0]
        if receipt.get("model") != "gpt-6-luna" or receipt.get("reasoning_effort") != "xhigh":
            errors.append(f"{prefix}: generation model/effort differs from the backfill contract")
        if receipt.get("generated_at") != report.get("generatedAt"):
            errors.append(f"{prefix}: generatedAt and generation receipt time differ")
        try:
            generated_at = datetime.fromisoformat(report["generatedAt"])
            if generated_at.tzinfo is None:
                raise ValueError("timezone missing")
            if generated_at.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=1):
                errors.append(f"{prefix}: generatedAt is in the future")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: invalid generatedAt: {exc}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--manifest", type=Path, default=ROOT / "weak_early_beta/fundamental_worker/out/historical_backfill_manifest.json")
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    receipt_paths = sorted((ROOT / "weak_early_beta/fundamental_worker/out").glob("*_generation_receipt.json"))
    failures: list[str] = []
    for candidate in args.candidates:
        path = candidate.resolve()
        candidate_failures = check_candidate(path, manifest, receipt_paths)
        failures.extend(candidate_failures)
        if not candidate_failures:
            print(f"PASS {path.name}")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
