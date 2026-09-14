"""Outcome-blind selector for the preregistered EDINET OSS real sample.

Selection uses document metadata only. Parser outputs, accounting values,
strategy candidates, scores, labels, returns, and 2026 market outcomes are not
accepted inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

SAMPLE_START = pd.Timestamp("2023-01-01T00:00:00+09:00")
SAMPLE_END = pd.Timestamp("2025-12-31T23:59:59+09:00")
ELIGIBLE_DOC_TYPES = {"120", "130"}
PER_STRATUM = 2


def _normalize_jst(value: object, *, name: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return ts.tz_convert("Asia/Tokyo")


def select_real_sample(
    metadata: pd.DataFrame,
    *,
    source_coverage_start: object,
    source_coverage_end: object,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select the frozen quarter x doc-type sample from complete metadata."""
    required = {"doc_id", "doc_type_code", "submit_datetime"}
    missing = sorted(required.difference(metadata.columns))
    if missing:
        raise ValueError(f"missing metadata columns: {missing}")

    coverage_start = _normalize_jst(source_coverage_start, name="source_coverage_start")
    coverage_end = _normalize_jst(source_coverage_end, name="source_coverage_end")
    if coverage_start > SAMPLE_START or coverage_end < SAMPLE_END:
        raise ValueError(
            "metadata source does not cover the full preregistered 2023-01-01..2025-12-31 interval"
        )

    z = metadata.loc[:, ["doc_id", "doc_type_code", "submit_datetime"]].copy()
    z["doc_id"] = z["doc_id"].astype("string").str.strip()
    z["doc_type_code"] = z["doc_type_code"].astype("string").str.strip()
    z["submit_datetime"] = pd.to_datetime(z["submit_datetime"], errors="raise", utc=True).dt.tz_convert(
        "Asia/Tokyo"
    )
    if z[["doc_id", "doc_type_code", "submit_datetime"]].isna().any().any():
        raise ValueError("metadata contains missing required values")
    if z["doc_id"].eq("").any():
        raise ValueError("metadata contains blank doc_id")

    eligible = z.loc[
        z["doc_type_code"].isin(ELIGIBLE_DOC_TYPES)
        & z["submit_datetime"].between(SAMPLE_START, SAMPLE_END, inclusive="both")
    ].copy()
    eligible = eligible.sort_values(
        ["submit_datetime", "doc_id", "doc_type_code"], kind="stable"
    ).drop_duplicates(subset=["doc_id"], keep="first")
    if eligible.empty:
        raise ValueError("no eligible EDINET documents in preregistered interval")

    naive = eligible["submit_datetime"].dt.tz_localize(None)
    eligible["calendar_quarter"] = naive.dt.to_period("Q").astype(str)
    selected = (
        eligible.sort_values(
            ["calendar_quarter", "doc_type_code", "submit_datetime", "doc_id"], kind="stable"
        )
        .groupby(["calendar_quarter", "doc_type_code"], sort=True, group_keys=False)
        .head(PER_STRATUM)
        .reset_index(drop=True)
    )

    strata = (
        eligible.groupby(["calendar_quarter", "doc_type_code"], sort=True)
        .size()
        .rename("eligible_count")
        .reset_index()
    )
    selected_counts = (
        selected.groupby(["calendar_quarter", "doc_type_code"], sort=True)
        .size()
        .rename("selected_count")
        .reset_index()
    )
    strata = strata.merge(selected_counts, on=["calendar_quarter", "doc_type_code"], how="left")
    strata["selected_count"] = strata["selected_count"].fillna(0).astype(int)

    receipt = {
        "status": "SAMPLE_FROZEN_OUTCOME_BLIND",
        "selection_period": {
            "start": SAMPLE_START.isoformat(),
            "end": SAMPLE_END.isoformat(),
        },
        "source_coverage": {
            "start": coverage_start.isoformat(),
            "end": coverage_end.isoformat(),
            "full_period_pass": True,
        },
        "eligible_doc_type_codes": sorted(ELIGIBLE_DOC_TYPES),
        "sampling_unit": "calendar quarter x doc_type_code",
        "per_stratum": PER_STRATUM,
        "eligible_rows_after_doc_id_dedup": int(len(eligible)),
        "selected_documents": int(len(selected)),
        "selected_doc_ids": selected["doc_id"].astype(str).tolist(),
        "strata": strata.to_dict(orient="records"),
        "strategy_outcomes_opened": False,
        "selection_inputs": ["doc_id", "doc_type_code", "submit_datetime", "source coverage bounds"],
        "no_replacement_rule": True,
    }
    return selected, receipt


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--metadata", required=True)
    p.add_argument("--source-coverage-start", required=True)
    p.add_argument("--source-coverage-end", required=True)
    p.add_argument("--sample-output", required=True)
    p.add_argument("--receipt-output", required=True)
    a = p.parse_args()

    metadata = pd.read_csv(a.metadata)
    selected, receipt = select_real_sample(
        metadata,
        source_coverage_start=a.source_coverage_start,
        source_coverage_end=a.source_coverage_end,
    )
    receipt["metadata_input"] = {
        "path": str(a.metadata),
        "sha256": _sha256(a.metadata),
    }

    sample_path = Path(a.sample_output)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(sample_path, index=False)
    receipt["sample_csv_sha256"] = _sha256(sample_path)

    receipt_path = Path(a.receipt_output)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
