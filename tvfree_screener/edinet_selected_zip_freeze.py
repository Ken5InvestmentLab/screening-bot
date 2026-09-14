"""Freeze exact selected EDINET ZIP bytes before any parser comparison.

This module is intentionally outcome-blind. It consumes only the frozen sample
receipt produced by ``edinet_oss_sample_selector.py`` and a directory containing
one ZIP per selected doc ID. It validates the exact selected set, verifies ZIP
integrity, and emits immutable SHA256/size metadata. It never invokes a parser or
reads accounting/strategy outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_selected_zips(sample_receipt: dict[str, object], zip_dir: str | Path) -> dict[str, object]:
    ids = sample_receipt.get("selected_doc_ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x.strip() for x in ids):
        raise ValueError("sample receipt must contain non-empty selected_doc_ids strings")
    doc_ids = [x.strip() for x in ids]
    if len(set(doc_ids)) != len(doc_ids):
        raise ValueError("sample receipt contains duplicate selected_doc_ids")
    if sample_receipt.get("strategy_outcomes_opened") is not False:
        raise ValueError("sample receipt must explicitly keep strategy_outcomes_opened=false")
    if sample_receipt.get("no_replacement_rule") is not True:
        raise ValueError("sample receipt must explicitly preserve no_replacement_rule=true")

    root = Path(zip_dir)
    if not root.is_dir():
        raise ValueError("zip_dir must be an existing directory")

    expected_names = {f"{doc_id}.zip" for doc_id in doc_ids}
    actual_names = {p.name for p in root.iterdir() if p.is_file()}
    missing = sorted(expected_names - actual_names)
    extras = sorted(actual_names - expected_names)
    if missing or extras:
        raise ValueError(f"selected ZIP set mismatch: missing={missing}, extras={extras}")

    files: list[dict[str, object]] = []
    for doc_id in doc_ids:
        path = root / f"{doc_id}.zip"
        if not zipfile.is_zipfile(path):
            raise ValueError(f"{doc_id}: not a valid ZIP archive")
        with zipfile.ZipFile(path, "r") as zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                raise ValueError(f"{doc_id}: corrupt ZIP member: {bad_member}")
            member_names = sorted(zf.namelist())
            if not member_names:
                raise ValueError(f"{doc_id}: empty ZIP archive")
        files.append(
            {
                "doc_id": doc_id,
                "filename": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "zip_members": member_names,
            }
        )

    chain = hashlib.sha256()
    for item in files:
        chain.update(f"{item['doc_id']}\0{item['sha256']}\0{item['size_bytes']}\n".encode("utf-8"))

    return {
        "status": "SELECTED_ZIPS_FROZEN_OUTCOME_BLIND",
        "selected_documents": len(doc_ids),
        "selected_doc_ids": doc_ids,
        "files": files,
        "aggregate_sha256_chain": chain.hexdigest(),
        "strategy_outcomes_opened": False,
        "parser_outputs_opened": False,
        "no_replacement_rule": True,
        "next_boundary": "run custom and OSS parsers only against these exact SHA256-frozen ZIP bytes",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sample-receipt", required=True)
    p.add_argument("--zip-dir", required=True)
    p.add_argument("--receipt-output", required=True)
    a = p.parse_args()

    sample_receipt = json.loads(Path(a.sample_receipt).read_text(encoding="utf-8"))
    receipt = freeze_selected_zips(sample_receipt, a.zip_dir)
    out = Path(a.receipt_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
