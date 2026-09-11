#!/usr/bin/env python3
"""Audit-first EDINET dilution evidence extractor (TEST ONLY).

This module intentionally does NOT convert text-block numbers into an accepted
"remaining warrant shares" figure. It only extracts auditable evidence from
known EDINET disclosure sections and marks every share-count token as a
candidate. A later parser may promote a candidate only after source-table
semantics are proven on real historical filings.

No production writes. No AI. No 2026 tuning.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

import pandas as pd

OUT = Path("tvfree_screener/out")

# Exact, auditable standard-taxonomy text blocks. Company extension elements are
# intentionally NOT guessed here.
EVIDENCE_ELEMENTS = {
    "jpcrp_cor:ParticularsOfNewShareSubscriptionRightsTextBlock": "warrant_particulars",
    "jpcrp_cor:OtherInformationOnShareAcquisitionRightsTextBlock": "other_share_acquisition_rights",
    "jpcrp_cor:ExercisesEtcOfMovingStrikeConvertibleBondsEtcTextBlock": "moving_strike_exercise_status",
}

FULLWIDTH_TRANS = str.maketrans("０１２３４５６７８９，．", "0123456789,.")
SHARE_RE = re.compile(r"(?P<num>[0-9０-９][0-9０-９,，]*)\s*株")
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    s = html.unescape(str(value))
    s = TAG_RE.sub(" ", s)
    return SPACE_RE.sub(" ", s).strip()


def parse_share_count(token: str) -> int | None:
    s = token.translate(FULLWIDTH_TRANS).replace(",", "")
    if not s.isdigit():
        return None
    try:
        return int(s)
    except ValueError:
        return None


def classify_share_mention(text: str, start: int, end: int) -> str:
    """Classify only by nearby source wording; never call it residual dilution."""
    window = text[max(0, start - 140):min(len(text), end + 80)]
    if "目的となる株式" in window or "対象となる株式" in window:
        return "potential_share_candidate"
    if "交付" in window and "株式" in window:
        return "share_delivery_candidate"
    if "行使" in window:
        return "exercise_related_share_candidate"
    return "unclassified_share_count"


def _bracketed_near(text: str, start: int, end: int) -> bool:
    left = text[max(0, start - 2):start]
    right = text[end:min(len(text), end + 3)]
    opens = ("[", "［", "【", "(" , "（")
    closes = ("]", "］", "】", ")", "）")
    return any(x in left for x in opens) or any(x in right for x in closes)


def extract_dilution_evidence(
    facts: pd.DataFrame,
    document: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Extract audit evidence from exact EDINET dilution-related text blocks."""
    required = {"element_id", "context_id", "value"}
    missing = sorted(required - set(facts.columns))
    if missing:
        raise ValueError(f"facts missing required columns: {missing}")

    doc = document or {}
    rows: list[dict[str, object]] = []

    for _, fact in facts.iterrows():
        element_id = str(fact.get("element_id") or "")
        source_kind = EVIDENCE_ELEMENTS.get(element_id)
        if source_kind is None:
            continue

        text = normalize_text(fact.get("value"))
        if not text:
            continue

        ms_evidence = (
            source_kind == "moving_strike_exercise_status"
            or "行使価額修正条項付" in text
            or "行使価格修正条項付" in text
        )
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        mentions = list(SHARE_RE.finditer(text))

        base = {
            "symbol": doc.get("symbol"),
            "doc_id": doc.get("doc_id"),
            "available_at": doc.get("available_at"),
            "available_date": doc.get("available_date"),
            "period_start": doc.get("period_start"),
            "period_end": doc.get("period_end"),
            "element_id": element_id,
            "context_id": str(fact.get("context_id") or ""),
            "source_member": str(fact.get("source_member") or ""),
            "source_kind": source_kind,
            "ms_warrant_evidence": bool(ms_evidence),
            "text_sha256": digest,
            "text_length": len(text),
            "accepted_remaining_potential_shares": False,
        }

        if not mentions:
            rows.append({
                **base,
                "status": "block_no_share_token",
                "candidate_role": None,
                "share_count_raw": None,
                "share_count": None,
                "bracketed_near_token": False,
                "evidence_excerpt": text[:240],
            })
            continue

        for m in mentions:
            raw = m.group("num")
            numeric = parse_share_count(raw)
            excerpt = text[max(0, m.start() - 120):min(len(text), m.end() + 120)]
            rows.append({
                **base,
                "status": "candidate_only_not_accepted",
                "candidate_role": classify_share_mention(text, m.start(), m.end()),
                "share_count_raw": raw,
                "share_count": numeric,
                "bracketed_near_token": _bracketed_near(text, m.start(), m.end()),
                "evidence_excerpt": excerpt,
            })

    columns = [
        "symbol", "doc_id", "available_at", "available_date", "period_start", "period_end",
        "element_id", "context_id", "source_member", "source_kind", "ms_warrant_evidence",
        "status", "candidate_role", "share_count_raw", "share_count",
        "bracketed_near_token", "accepted_remaining_potential_shares",
        "text_sha256", "text_length", "evidence_excerpt",
    ]
    return pd.DataFrame(rows, columns=columns)


def evidence_report(df: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {
            "rows": 0,
            "documents": 0,
            "share_count_candidates": 0,
            "potential_share_candidates": 0,
            "ms_warrant_evidence_rows": 0,
            "accepted_remaining_potential_share_rows": 0,
        }
    return {
        "rows": int(len(df)),
        "documents": int(df["doc_id"].dropna().nunique()) if "doc_id" in df else 0,
        "share_count_candidates": int(df["share_count"].notna().sum()),
        "potential_share_candidates": int((df["candidate_role"] == "potential_share_candidate").sum()),
        "ms_warrant_evidence_rows": int(df["ms_warrant_evidence"].fillna(False).sum()),
        "accepted_remaining_potential_share_rows": int(
            df["accepted_remaining_potential_shares"].fillna(False).sum()
        ),
        "policy": (
            "audit only: no candidate is accepted as residual dilution until real filing "
            "table semantics are validated"
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts-csv", required=True)
    ap.add_argument("--doc-id", default="")
    ap.add_argument("--symbol", default="")
    ap.add_argument("--available-at", default="")
    ap.add_argument("--available-date", default="")
    ap.add_argument("--period-start", default="")
    ap.add_argument("--period-end", default="")
    ap.add_argument("--out", default=str(OUT / "edinet_dilution_evidence.csv"))
    args = ap.parse_args()

    facts = pd.read_csv(args.facts_csv, dtype=str)
    document = {
        "doc_id": args.doc_id or None,
        "symbol": args.symbol or None,
        "available_at": args.available_at or None,
        "available_date": args.available_date or None,
        "period_start": args.period_start or None,
        "period_end": args.period_end or None,
    }
    evidence = extract_dilution_evidence(facts, document)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(out, index=False)
    print(json.dumps(evidence_report(evidence), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
