#!/usr/bin/env python3
"""Outcome-blind audit of candidate EDINET CSV contexts for Class-B documents.

Reads only the already-frozen pre-parser type=5 ZIP bytes. It does not choose a
fact, mutate parser aliases, or inspect strategy returns/performance.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import zipfile

import pandas as pd

from edinet_fundamental_collector import CSV_COLUMN_ALIASES, FACT_SPECS

CLASS_B_DOCS = ("S100QF0X", "S100RWZI", "S100UXL5")
FIELDS = ("assets", "equity", "operating_income", "net_income")


def _col(df: pd.DataFrame, logical: str) -> str | None:
    for name in CSV_COLUMN_ALIASES[logical]:
        if name in df.columns:
            return name
    return None


def _read_csvs(zip_bytes: bytes) -> list[tuple[str, pd.DataFrame]]:
    out = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith(".csv"):
                continue
            raw = zf.read(name)
            df = None
            for enc in ("utf-16", "utf-8-sig", "cp932"):
                try:
                    df = pd.read_csv(io.BytesIO(raw), encoding=enc, dtype=str, keep_default_na=False)
                    break
                except Exception:
                    pass
            if df is not None:
                out.append((name, df))
    return out


def audit_doc(path: Path, doc_id: str) -> dict:
    records = []
    for filename, df in _read_csvs(path.read_bytes()):
        element_col = _col(df, "element_id")
        if element_col is None:
            continue
        context_col = _col(df, "context_id")
        rel_col = _col(df, "relative_year")
        cons_col = _col(df, "consolidated")
        period_col = _col(df, "period_type")
        value_col = _col(df, "value")
        for field in FIELDS:
            spec = FACT_SPECS[field]
            hit = df[df[element_col].isin(spec["elements"])]
            for _, row in hit.iterrows():
                records.append({
                    "field": field,
                    "kind": spec["kind"],
                    "element_id": str(row.get(element_col, "")),
                    "context_id": str(row.get(context_col, "")) if context_col else "",
                    "relative_year": str(row.get(rel_col, "")) if rel_col else "",
                    "consolidated": str(row.get(cons_col, "")) if cons_col else "",
                    "period_type": str(row.get(period_col, "")) if period_col else "",
                    "value_present": bool(str(row.get(value_col, "")).strip()) if value_col else False,
                    "source_csv": filename,
                })
    # Preserve candidates, but never emit values: context audit is semantic only.
    records.sort(key=lambda x: (x["field"], x["element_id"], x["context_id"], x["source_csv"]))
    by_field = {f: [r for r in records if r["field"] == f] for f in FIELDS}
    return {
        "doc_id": doc_id,
        "status": "CONTEXT_CANDIDATES_ENUMERATED" if records else "NO_MAPPED_CANDIDATES_FAIL_CLOSED",
        "strategy_outcomes_opened": False,
        "performance_opened": False,
        "fact_values_emitted": False,
        "candidate_count_by_field": {f: len(by_field[f]) for f in FIELDS},
        "candidate_contexts": by_field,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root, out = Path(args.zip_root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    for doc_id in CLASS_B_DOCS:
        p = root / f"{doc_id}.zip"
        if not p.is_file():
            raise SystemExit(f"FAIL_CLOSED missing frozen ZIP: {doc_id}")
        rec = audit_doc(p, doc_id)
        (out / f"{doc_id}_contexts.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        docs.append(rec)
    summary = {
        "status": "CLASS_B_CONTEXT_AUDIT_COMPLETE" if all(d["status"] == "CONTEXT_CANDIDATES_ENUMERATED" for d in docs) else "FAIL_CLOSED",
        "documents": len(docs),
        "doc_ids": list(CLASS_B_DOCS),
        "strategy_outcomes_opened": False,
        "performance_opened": False,
        "fact_values_emitted": False,
        "rule": "Enumerate frozen candidate contexts only; do not select facts or alter parser semantics.",
    }
    (out / "class_b_context_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if summary["status"] != "CLASS_B_CONTEXT_AUDIT_COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
