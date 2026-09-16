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
import io
import json
from pathlib import Path
from typing import Any
import zipfile

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
    "operating_cf": "operating_cash_flow",
}

NET_INCOME_OSS_FIELD_BY_ELEMENT = {
    "jppfs_cor:ProfitLoss": "net_income_total",
    "jppfs_cor:ProfitLossAttributableToOwnersOfParent": "net_income_owners",
}
OWNERS_NET_INCOME_ELEMENT_SUFFIXES = (
    "ProfitLossAttributableToOwnersOfParent",
    "ProfitLossAttributableToOwnersOfParentIFRS",
    "ProfitLossAttributableToOwnersOfParentUSGAAP",
)

SHARE_ELEMENTS = (
    "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
    "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
    "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares",
)

SHARE_PRIORITY_GROUPS = (
    (("jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults", "CurrentYear"),),
    (
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc", "CurrentYear"),
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares", "CurrentYear"),
    ),
    (
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc", "FilingDateInstant"),
        ("jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares", "FilingDateInstant"),
    ),
)


def _corporate_domain_disposition(payload: bytes) -> dict[str, object]:
    """Fail-close investment-fund filings before listed-company comparison.

    jpsps070000 is source taxonomy identity for investment-fund securities
    reports. The corporate-fundamental adapter must not collapse either a
    single-fund or multi-fund jpsps filing into one listed-company row. This
    classification uses no accounting values, parser agreement, or outcomes.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        basenames = [Path(name).name.lower() for name in csv_names]
        jpsps = [name for name in basenames if "jpsps070000" in name]
        if not jpsps:
            return {"status": "CORPORATE_DOMAIN", "reason": None, "source_csv_count": len(csv_names)}
        numbered_components = [
            name for name in jpsps
            if any(f"-{i:03d}_" in name for i in range(1, 1000))
        ]
        return {
            "status": "OUT_OF_DOMAIN_INVESTMENT_FUND_FILING",
            "reason": "jpsps070000 investment-fund securities-report taxonomy is outside listed-company fundamental domain",
            "source_csv_count": len(csv_names),
            "jpsps070000_csv_count": len(jpsps),
            "numbered_component_count": len(numbered_components),
            "multi_component": len(numbered_components) > 1,
        }


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


def _net_income_oss_field(element_id: Any) -> str | None:
    element = str(element_id or "")
    if element in NET_INCOME_OSS_FIELD_BY_ELEMENT:
        return NET_INCOME_OSS_FIELD_BY_ELEMENT[element]
    local_name = element.split(":", 1)[-1]
    if any(local_name.endswith(suffix) for suffix in OWNERS_NET_INCOME_ELEMENT_SUFFIXES):
        return "net_income_owners"
    return None


def _comparison(left: float | None, right: float | None) -> str:
    match = _values_match(left, right)
    if match:
        return "MATCH" if left is not None else "BOTH_MISSING"
    if left is None:
        return "CUSTOM_MISSING_OSS_VALUE"
    if right is None:
        return "OSS_MISSING_CUSTOM_VALUE"
    return "VALUE_MISMATCH"


def _oss_issued_shares(raw_facts: list[Any]) -> dict[str, object]:
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
            item for item in facts
            if any(item[1] == allowed_element and item[2].startswith(context_prefix)
                   for allowed_element, context_prefix in group)
        ]
        if not eligible:
            continue
        values = {item[3] for item in eligible}
        if len(values) != 1:
            return {"value": None, "status": "ambiguous", "element_id": None, "context_id": None}
        chosen = eligible[0]
        return {"value": chosen[3], "status": "ok", "element_id": chosen[1], "context_id": chosen[2]}

    return {"value": None, "status": "missing", "element_id": None, "context_id": None}


def crosscheck_zip(payload: bytes, *, doc_id: str = "OSS-CROSSCHECK", doc_type_code: str = "120") -> dict[str, object]:
    if str(doc_type_code) not in {"120", "130"}:
        raise ValueError("initial cross-check is restricted to securities reports 120/130")

    domain = _corporate_domain_disposition(payload)
    if domain["status"] != "CORPORATE_DOMAIN":
        return {
            "doc_id": str(doc_id),
            "doc_type_code": str(doc_type_code),
            "domain_status": domain["status"],
            "domain_reason": domain["reason"],
            "domain_evidence": domain,
            "comparisons": {},
            "mismatch_fields": [],
            "all_compared_fields_agree": False,
            "excluded_from_corporate_comparability": True,
            "outcome_data_opened": False,
            "availability_policy_changed": False,
            "decision_rule": "Investment-fund filings are explicit domain exclusions, not parser mismatches, and are never collapsed into a listed-company fundamental row.",
        }

    custom_frame = custom.read_xbrl_csv_zip(payload)
    custom_facts = custom.extract_standard_facts(custom_frame)
    oss_csv_files = extract_csv_from_zip(payload)
    if not oss_csv_files:
        raise ValueError("edinet-tools extracted no CSV files from ZIP")
    report = parse_securities_report(csv_files=oss_csv_files, doc_id=str(doc_id), doc_type_code=str(doc_type_code))

    comparisons: dict[str, dict[str, object]] = {}
    for custom_name, oss_name in FIELD_MAP.items():
        left = _number(custom_facts.get(custom_name))
        right = _number(getattr(report, oss_name, None))
        comparisons[custom_name] = {
            "custom_value": left,
            "custom_status": custom_facts.get(f"{custom_name}_status"),
            "custom_element_id": custom_facts.get(f"{custom_name}_element_id"),
            "custom_context_id": custom_facts.get(f"{custom_name}_context_id"),
            "oss_field": oss_name,
            "oss_value": right,
            "status": _comparison(left, right),
        }

    net_element = custom_facts.get("net_income_element_id")
    net_oss_name = _net_income_oss_field(net_element)
    net_left = _number(custom_facts.get("net_income"))
    if net_oss_name is None and net_left is not None:
        net_right = None
        net_status = "UNCLASSIFIED_NET_INCOME_BASIS"
    else:
        net_right = _number(getattr(report, net_oss_name, None)) if net_oss_name else None
        net_status = _comparison(net_left, net_right)
    comparisons["net_income"] = {
        "custom_value": net_left,
        "custom_status": custom_facts.get("net_income_status"),
        "custom_element_id": net_element,
        "custom_context_id": custom_facts.get("net_income_context_id"),
        "oss_field": net_oss_name,
        "oss_value": net_right,
        "status": net_status,
    }

    custom_shares = {
        "value": _number(custom_facts.get("shares_outstanding")),
        "status": custom_facts.get("shares_outstanding_status"),
        "element_id": custom_facts.get("shares_outstanding_element_id"),
        "context_id": custom_facts.get("shares_outstanding_context_id"),
    }
    oss_shares = _oss_issued_shares(report.raw_facts)
    comparisons["shares_outstanding"] = {
        "custom_value": custom_shares["value"],
        "custom_status": custom_shares["status"],
        "custom_element_id": custom_shares["element_id"],
        "custom_context_id": custom_shares["context_id"],
        "oss_value": oss_shares["value"],
        "oss_status": oss_shares["status"],
        "oss_element_id": oss_shares["element_id"],
        "oss_context_id": oss_shares["context_id"],
        "status": _comparison(_number(custom_shares["value"]), _number(oss_shares["value"])),
    }

    mismatch_fields = [name for name, comparison in comparisons.items()
                       if comparison["status"] not in {"MATCH", "BOTH_MISSING"}]
    oss_flags = [flag.to_dict() if hasattr(flag, "to_dict") else str(flag)
                 for flag in getattr(report, "extraction_flags", [])]
    return {
        "doc_id": str(doc_id),
        "doc_type_code": str(doc_type_code),
        "domain_status": "CORPORATE_DOMAIN",
        "custom_parser": "screening-bot edinet_fundamental_collector",
        "oss_parser": "edinet-tools",
        "comparisons": comparisons,
        "mismatch_fields": mismatch_fields,
        "all_compared_fields_agree": not mismatch_fields,
        "excluded_from_corporate_comparability": False,
        "oss_extraction_flags": oss_flags,
        "outcome_data_opened": False,
        "availability_policy_changed": False,
        "decision_rule": "Parser disagreement is an audit finding only. Never choose a value because it improves strategy performance.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, help="EDINET XBRL-to-CSV ZIP")
    p.add_argument("--doc-id", default="OSS-CROSSCHECK")
    p.add_argument("--doc-type-code", default="120")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = crosscheck_zip(Path(a.zip).read_bytes(), doc_id=a.doc_id, doc_type_code=a.doc_type_code)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
