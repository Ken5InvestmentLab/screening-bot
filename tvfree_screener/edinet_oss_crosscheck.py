"""Outcome-blind cross-check between the custom EDINET extractor and edinet-tools.

The same XBRL-to-CSV ZIP bytes are parsed independently by both implementations.
This module compares source facts only. It never reads strategy returns and never
changes point-in-time availability; submit/available timestamps remain governed
by the repository's existing EDINET collector contract.

A disagreement is evidence to inspect, not permission to choose the value that
improves a backtest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from edinet_tools.parsers.extraction import extract_csv_from_zip
from edinet_tools.parsers.securities import parse_securities_report

try:
    from tvfree_screener import edinet_fundamental_collector as custom
except ImportError:  # direct script execution
    import edinet_fundamental_collector as custom


FIELD_MAP = {
    "assets": "total_assets",
    "equity": "net_assets_total",
    "revenue": "net_sales",
    "operating_income": "operating_income",
    "net_income": "net_income_owners",
    "operating_cf": "operating_cash_flow",
}

SHARE_ELEMENTS = (
    "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
    "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
    "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares",
)

SHARE_PRIORITY_GROUPS = (
    (
        ("jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults", "CurrentYear"),
    ),
    (
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc", "CurrentYear"),
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares", "CurrentYear"),
    ),
    (
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc", "FilingDateInstant"),
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares", "FilingDateInstant"),
    ),
)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _values_match(left: float | None, right: float | None) -> bool | None:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return bool(np.isclose(left, right, rtol=1e-9, atol=0.5))


def _oss_issued_shares(raw_facts: list[Any]) -> dict[str, object]:
    """Select issued shares from edinet-tools raw facts using the frozen semantic priority.

    Priority:
    1) summary-table issued shares at CurrentYear;
    2) fiscal-year-end issued shares at CurrentYear;
    3) fiscal-year-end issued shares at FilingDateInstant.

    Conflicting values inside one priority group fail closed.
    """
    facts = []
    for fact in raw_facts:
        element_id = str(getattr(fact, "element_id", "") or "")
        if element_id not in SHARE_ELEMENTS:
            continue
        context_id = str(getattr(fact, "context_id", "") or "")
        numeric = custom.parse_numeric(getattr(fact, "value", None))
        if numeric is None:
            continue
        facts.append((fact, element_id, context_id, float(numeric)))

    for group in SHARE_PRIORITY_GROUPS:
        eligible = [
            item
            for item in facts
            if any(
                item[1] == allowed_element and item[2].startswith(context_prefix)
                for allowed_element, context_prefix in group
            )
        ]
        if not eligible:
            continue
        values = {item[3] for item in eligible}
        if len(values) != 1:
            return {
                "value": None,
                "status": "ambiguous",
                "element_id": None,
                "context_id": None,
            }
        chosen = eligible[0]
        return {
            "value": chosen[3],
            "status": "ok",
            "element_id": chosen[1],
            "context_id": chosen[2],
        }

    return {
        "value": None,
        "status": "missing",
        "element_id": None,
        "context_id": None,
    }


def crosscheck_zip(
    payload: bytes,
    *,
    doc_id: str = "OSS-CROSSCHECK",
    doc_type_code: str = "120",
) -> dict[str, object]:
    """Parse one ZIP twice and compare financial/source facts."""
    if str(doc_type_code) not in {"120", "130"}:
        raise ValueError("initial cross-check is restricted to securities reports 120/130")

    custom_frame = custom.read_xbrl_csv_zip(payload)
    custom_facts = custom.extract_standard_facts(custom_frame)

    oss_csv_files = extract_csv_from_zip(payload)
    if not oss_csv_files:
        raise ValueError("edinet-tools extracted no CSV files from ZIP")
    report = parse_securities_report(
        csv_files=oss_csv_files,
        doc_id=str(doc_id),
        doc_type_code=str(doc_type_code),
    )

    comparisons: dict[str, dict[str, object]] = {}
    for custom_name, oss_name in FIELD_MAP.items():
        left = _number(custom_facts.get(custom_name))
        right = _number(getattr(report, oss_name, None))
        match = _values_match(left, right)
        if match:
            status = "MATCH" if left is not None else "BOTH_MISSING"
        elif left is None:
            status = "CUSTOM_MISSING_OSS_VALUE"
        elif right is None:
            status = "OSS_MISSING_CUSTOM_VALUE"
        else:
            status = "VALUE_MISMATCH"
        comparisons[custom_name] = {
            "custom_value": left,
            "custom_status": custom_facts.get(f"{custom_name}_status"),
            "custom_element_id": custom_facts.get(f"{custom_name}_element_id"),
            "custom_context_id": custom_facts.get(f"{custom_name}_context_id"),
            "oss_field": oss_name,
            "oss_value": right,
            "status": status,
        }

    custom_shares = {
        "value": _number(custom_facts.get("shares_outstanding")),
        "status": custom_facts.get("shares_outstanding_status"),
        "element_id": custom_facts.get("shares_outstanding_element_id"),
        "context_id": custom_facts.get("shares_outstanding_context_id"),
    }
    oss_shares = _oss_issued_shares(report.raw_facts)
    shares_match = _values_match(
        _number(custom_shares["value"]),
        _number(oss_shares["value"]),
    )
    if shares_match:
        share_status = "MATCH" if custom_shares["value"] is not None else "BOTH_MISSING"
    elif custom_shares["value"] is None:
        share_status = "CUSTOM_MISSING_OSS_VALUE"
    elif oss_shares["value"] is None:
        share_status = "OSS_MISSING_CUSTOM_VALUE"
    else:
        share_status = "VALUE_MISMATCH"
    comparisons["shares_outstanding"] = {
        "custom_value": custom_shares["value"],
        "custom_status": custom_shares["status"],
        "custom_element_id": custom_shares["element_id"],
        "custom_context_id": custom_shares["context_id"],
        "oss_value": oss_shares["value"],
        "oss_status": oss_shares["status"],
        "oss_element_id": oss_shares["element_id"],
        "oss_context_id": oss_shares["context_id"],
        "status": share_status,
    }

    mismatch_fields = [
        name
        for name, comparison in comparisons.items()
        if comparison["status"] not in {"MATCH", "BOTH_MISSING"}
    ]
    oss_flags = [
        flag.to_dict() if hasattr(flag, "to_dict") else str(flag)
        for flag in getattr(report, "extraction_flags", [])
    ]
    return {
        "doc_id": str(doc_id),
        "doc_type_code": str(doc_type_code),
        "custom_parser": "screening-bot edinet_fundamental_collector",
        "oss_parser": "edinet-tools",
        "comparisons": comparisons,
        "mismatch_fields": mismatch_fields,
        "all_compared_fields_agree": not mismatch_fields,
        "oss_extraction_flags": oss_flags,
        "outcome_data_opened": False,
        "availability_policy_changed": False,
        "decision_rule": (
            "Parser disagreement is an audit finding only. Never choose a value "
            "because it improves strategy performance."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, help="EDINET XBRL-to-CSV ZIP")
    p.add_argument("--doc-id", default="OSS-CROSSCHECK")
    p.add_argument("--doc-type-code", default="120")
    p.add_argument("--output", required=True)
    a = p.parse_args()

    payload = Path(a.zip).read_bytes()
    result = crosscheck_zip(payload, doc_id=a.doc_id, doc_type_code=a.doc_type_code)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
