#!/usr/bin/env python3
"""Point-in-time EDINET fundamental collector (TEST ONLY).

This module never writes to production systems. It uses EDINET API v2 and
requires EDINET_API_KEY from the environment. The API key is never included in
logs or output files.

The collector intentionally starts with accounting facts that can be extracted
deterministically from EDINET's XBRL-to-CSV ZIP. Every output row retains the
source document id and market-availability timestamp/date. Ambiguous or missing
facts remain missing; they are never guessed or treated as healthy.

Dilution-related text blocks are passed to an audit-first evidence extractor.
Candidate share counts are retained for validation, but none is automatically
accepted as residual dilution until real filing table semantics are proven.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
import argparse
import io
import json
import os
from pathlib import Path
import time
from typing import Iterable
import zipfile

import pandas as pd
import requests

import edinet_dilution_audit as dilution_audit

API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
DEFAULT_OUT = Path("tvfree_screener/out/edinet")
ORDINANCE_COMPANY_DISCLOSURE = "010"

CSV_COLUMN_ALIASES = {
    "element_id": ("要素ID", "Element ID", "ElementID"),
    "item_name": ("項目名", "Item Name", "ItemName"),
    "context_id": ("コンテキストID", "Context ID", "ContextID"),
    "relative_year": ("相対年度", "Relative Year", "RelativeYear"),
    "consolidated": ("連結・個別", "Consolidated/NonConsolidated", "Consolidated"),
    "period_type": ("期間・時点", "Period/Instant", "DurationOrPoint"),
    "unit_id": ("ユニットID", "Unit ID", "UnitID"),
    "unit": ("単位", "Unit"),
    "value": ("値", "Value"),
}

# Deliberately small, auditable alias set. Coverage is measured before aliases
# are expanded. Exact element ids win over item-name heuristics; there are no
# heuristics here.
FACT_SPECS = {
    "shares_outstanding": {
        "kind": "instant",
        "prefer_nonconsolidated": True,
        # Prefer the current-year summary-table fact when present. Real EDINET
        # annual filings also commonly expose the issued-share count only at
        # FilingDateInstant, so that context is an explicit audited fallback.
        "elements": (
            "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
            "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
            "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfShares",
        ),
        "context_prefixes": ("CurrentYear", "FilingDateInstant"),
        "element_priority_first": True,
    },
    "assets": {
        "kind": "instant",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:Assets",
            "ifrs-full:Assets",
        ),
    },
    "equity": {
        "kind": "instant",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:NetAssets",
            "jppfs_cor:Equity",
            "ifrs-full:Equity",
            "jpcrp_cor:NetAssetsSummaryOfBusinessResults",
        ),
    },
    "revenue": {
        "kind": "duration",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:NetSales",
            "jppfs_cor:Revenue",
            "ifrs-full:Revenue",
            "jpcrp_cor:NetSalesSummaryOfBusinessResults",
            "jpcrp_cor:RevenueSummaryOfBusinessResults",
        ),
    },
    "operating_income": {
        "kind": "duration",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:OperatingIncome",
            "jppfs_cor:OperatingProfitLoss",
            "ifrs-full:ProfitLossFromOperatingActivities",
            "jpcrp_cor:OperatingIncomeLossSummaryOfBusinessResults",
        ),
    },
    "net_income": {
        "kind": "duration",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:ProfitLossAttributableToOwnersOfParent",
            "ifrs-full:ProfitLossAttributableToOwnersOfParent",
            "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
            "jppfs_cor:ProfitLoss",
        ),
    },
    "operating_cf": {
        "kind": "duration",
        "prefer_nonconsolidated": False,
        "elements": (
            "jppfs_cor:NetCashProvidedByUsedInOperatingActivities",
            "ifrs-full:CashFlowsFromUsedInOperatingActivities",
            "jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
        ),
    },
}


def require_api_key(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    key = str(source.get("EDINET_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("EDINET_API_KEY is required")
    return key


def sec_code_to_symbol(sec_code: object) -> str | None:
    """Convert EDINET five-character security code to JPX four-char symbol.

    Fail closed if the expected trailing zero is absent.
    """
    if sec_code is None or pd.isna(sec_code):
        return None
    s = str(sec_code).strip().upper()
    if len(s) == 5 and s[-1] == "0" and s[:4].isalnum():
        return s[:4]
    return None


def parse_submit_datetime(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Tokyo").tz_localize(None)
    return ts


def normalize_document(raw: dict, source_file_date: str) -> dict | None:
    doc_id = str(raw.get("docID") or "").strip()
    symbol = sec_code_to_symbol(raw.get("secCode"))
    submitted = parse_submit_datetime(raw.get("submitDateTime"))
    if not doc_id or symbol is None or submitted is None:
        return None
    return {
        "symbol": symbol,
        "sec_code": str(raw.get("secCode") or "").strip(),
        "doc_id": doc_id,
        "edinet_code": str(raw.get("edinetCode") or "").strip(),
        "filer_name": str(raw.get("filerName") or "").strip(),
        "ordinance_code": str(raw.get("ordinanceCode") or "").strip(),
        "form_code": str(raw.get("formCode") or "").strip(),
        "doc_type_code": str(raw.get("docTypeCode") or "").strip(),
        "doc_description": str(raw.get("docDescription") or "").strip(),
        "period_start": str(raw.get("periodStart") or "").strip(),
        "period_end": str(raw.get("periodEnd") or "").strip(),
        "submit_datetime": submitted.strftime("%Y-%m-%d %H:%M:%S"),
        "available_at": submitted.strftime("%Y-%m-%d %H:%M:%S"),
        "available_date": submitted.strftime("%Y-%m-%d"),
        "source_file_date": str(source_file_date),
        "xbrl_flag": str(raw.get("xbrlFlag") or "").strip(),
        "csv_flag": str(raw.get("csvFlag") or "").strip(),
        "withdrawal_status": str(raw.get("withdrawalStatus") or "").strip(),
    }


@dataclass
class EdinetClient:
    api_key: str
    timeout: int = 60
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key must not be blank")
        if self.session is None:
            self.session = requests.Session()

    def __repr__(self) -> str:
        return f"EdinetClient(api_key=<redacted>, timeout={self.timeout})"

    def _get(self, path: str, params: dict[str, object]) -> requests.Response:
        assert self.session is not None
        safe_params = dict(params)
        safe_params["Subscription-Key"] = self.api_key
        response = self.session.get(
            f"{API_BASE}/{path.lstrip('/')}",
            params=safe_params,
            timeout=self.timeout,
            headers={"User-Agent": "screening-bot-tvfree-research/1.0"},
        )
        response.raise_for_status()
        return response

    def list_documents(self, day: str) -> list[dict]:
        response = self._get("documents.json", {"date": day, "type": 2})
        payload = response.json()
        metadata = payload.get("metadata") or {}
        status = str(metadata.get("status") or "")
        if status and status != "200":
            raise RuntimeError(f"EDINET list API status={status}")
        results = payload.get("results")
        if not isinstance(results, list):
            raise RuntimeError("EDINET list API returned no results array")
        return results

    def download_csv_zip(self, doc_id: str) -> bytes:
        response = self._get(f"documents/{doc_id}", {"type": 5})
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "json" in content_type:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            metadata = payload.get("metadata") if isinstance(payload, dict) else None
            status = metadata.get("status") if isinstance(metadata, dict) else None
            raise RuntimeError(f"EDINET document API returned JSON error status={status or 'unknown'}")
        if "octet-stream" not in content_type and "zip" not in content_type:
            raise RuntimeError(f"unexpected EDINET document content-type: {content_type or 'missing'}")
        return response.content


def iter_days(start: str, end: str) -> Iterable[str]:
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    if b < a:
        raise ValueError("end-date must be on or after start-date")
    cur = a
    while cur <= b:
        yield cur.isoformat()
        cur += timedelta(days=1)


def canonicalize_csv_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    for canonical, aliases in CSV_COLUMN_ALIASES.items():
        hit = next((a for a in aliases if a in df.columns), None)
        if hit is not None:
            rename[hit] = canonical
    z = df.rename(columns=rename).copy()
    required = ["element_id", "context_id", "value"]
    missing = [c for c in required if c not in z.columns]
    if missing:
        raise ValueError(f"EDINET CSV missing required columns: {missing}")
    for c in CSV_COLUMN_ALIASES:
        if c not in z.columns:
            z[c] = pd.NA
    return z[list(CSV_COLUMN_ALIASES.keys())]


def read_xbrl_csv_zip(payload: bytes, max_member_bytes: int = 50_000_000) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir() or not name.lower().endswith(".csv"):
                continue
            if "/xbrl_to_csv/" not in f"/{name.lower()}":
                continue
            if info.file_size > max_member_bytes:
                raise ValueError(f"EDINET CSV member too large: {name}")
            with zf.open(info) as fh:
                raw = fh.read(max_member_bytes + 1)
            if len(raw) > max_member_bytes:
                raise ValueError(f"EDINET CSV member too large after read: {name}")
            df = pd.read_csv(io.BytesIO(raw), sep="\t", encoding="utf-16", dtype=str)
            df = canonicalize_csv_columns(df)
            df["source_member"] = name
            frames.append(df)
    if not frames:
        raise ValueError("EDINET ZIP contained no XBRL_TO_CSV/*.csv files")
    return pd.concat(frames, ignore_index=True)


def parse_numeric(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip().replace(",", "").replace("，", "")
    if not s or s in {"-", "－", "—", "―", "N/A", "n/a"}:
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1].strip()
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if negative else x


def _context_rank(
    context_id: str,
    prefer_nonconsolidated: bool,
    prefixes: tuple[str, ...] = ("CurrentYear",),
) -> tuple[int, int, int] | None:
    ctx = str(context_id or "")
    prefix_rank = next(
        (index for index, prefix in enumerate(prefixes) if ctx.startswith(prefix)),
        None,
    )
    if prefix_rank is None:
        return None
    noncon = "NonConsolidatedMember" in ctx
    if prefer_nonconsolidated:
        ownership_rank = 0 if noncon else 1
    else:
        ownership_rank = 1 if noncon else 0
    return (prefix_rank, ownership_rank, len(ctx))


def extract_fact(df: pd.DataFrame, field: str) -> dict:
    spec = FACT_SPECS[field]
    cand = df[df["element_id"].isin(spec["elements"])].copy()
    if cand.empty:
        return {"value": None, "status": "missing", "element_id": None, "context_id": None, "source_member": None}

    ranked = []
    prefixes = tuple(spec.get("context_prefixes", ("CurrentYear",)))
    element_priority_first = bool(spec.get("element_priority_first", False))
    for idx, row in cand.iterrows():
        rank = _context_rank(
            str(row["context_id"]),
            bool(spec["prefer_nonconsolidated"]),
            prefixes=prefixes,
        )
        if rank is None:
            continue
        numeric = parse_numeric(row["value"])
        if numeric is None:
            continue
        element_rank = spec["elements"].index(row["element_id"])
        key = (element_rank, *rank) if element_priority_first else (*rank, element_rank)
        ranked.append((key, idx, numeric))
    if not ranked:
        return {"value": None, "status": "missing_eligible_context", "element_id": None, "context_id": None, "source_member": None}

    ranked.sort(key=lambda x: (x[0], x[1]))
    best_key = ranked[0][0]
    best = [r for r in ranked if r[0] == best_key]
    unique_values = {r[2] for r in best}
    if len(unique_values) != 1:
        return {"value": None, "status": "ambiguous", "element_id": None, "context_id": None, "source_member": None}
    chosen = cand.loc[best[0][1]]
    return {
        "value": best[0][2],
        "status": "ok",
        "element_id": str(chosen["element_id"]),
        "context_id": str(chosen["context_id"]),
        "source_member": str(chosen.get("source_member") or ""),
    }


def extract_standard_facts(df: pd.DataFrame) -> dict:
    out: dict[str, object] = {}
    for field in FACT_SPECS:
        fact = extract_fact(df, field)
        out[field] = fact["value"]
        out[f"{field}_status"] = fact["status"]
        out[f"{field}_element_id"] = fact["element_id"]
        out[f"{field}_context_id"] = fact["context_id"]
        out[f"{field}_source_member"] = fact["source_member"]
    return out


def collect(
    client: EdinetClient,
    start_date: str,
    end_date: str,
    symbols: set[str] | None = None,
    request_interval: float = 1.0,
    max_docs: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    documents: list[dict] = []
    for day in iter_days(start_date, end_date):
        raw_rows = client.list_documents(day)
        for raw in raw_rows:
            doc = normalize_document(raw, day)
            if doc is None:
                continue
            if doc["ordinance_code"] != ORDINANCE_COMPANY_DISCLOSURE:
                continue
            if symbols is not None and doc["symbol"] not in symbols:
                continue
            documents.append(doc)
        if request_interval > 0:
            time.sleep(request_interval)

    docs_df = pd.DataFrame(documents)
    if docs_df.empty:
        report = {
            "start_date": start_date,
            "end_date": end_date,
            "documents": 0,
            "csv_candidates": 0,
            "downloaded": 0,
            "parse_errors": 0,
            "field_coverage": {field: {"ok": 0, "missing_or_ambiguous": 0} for field in FACT_SPECS},
        }
        return docs_df, pd.DataFrame(), pd.DataFrame(), report

    docs_df = docs_df.sort_values(["available_at", "symbol", "doc_id"], kind="mergesort").drop_duplicates("doc_id")
    candidates = docs_df[docs_df["csv_flag"] == "1"].copy()
    if max_docs is not None:
        candidates = candidates.head(max_docs)

    snapshots: list[dict] = []
    dilution_frames: list[pd.DataFrame] = []
    errors: list[dict] = []
    for _, doc in candidates.iterrows():
        try:
            payload = client.download_csv_zip(str(doc["doc_id"]))
            facts_df = read_xbrl_csv_zip(payload)
            facts = extract_standard_facts(facts_df)
            doc_dict = doc.to_dict()
            snapshots.append({**doc_dict, **facts})
            dilution = dilution_audit.extract_dilution_evidence(facts_df, doc_dict)
            if not dilution.empty:
                dilution_frames.append(dilution)
        except Exception as exc:
            errors.append({"doc_id": str(doc["doc_id"]), "error": type(exc).__name__})
        if request_interval > 0:
            time.sleep(request_interval)

    snap_df = pd.DataFrame(snapshots)
    dilution_df = (
        pd.concat(dilution_frames, ignore_index=True)
        if dilution_frames
        else dilution_audit.extract_dilution_evidence(
            pd.DataFrame(columns=["element_id", "context_id", "value"])
        )
    )
    coverage = {}
    for field in FACT_SPECS:
        status_col = f"{field}_status"
        counts = Counter(snap_df[status_col].tolist()) if status_col in snap_df.columns else Counter()
        coverage[field] = {
            "ok": int(counts.get("ok", 0)),
            "missing_or_ambiguous": int(len(snap_df) - counts.get("ok", 0)),
            "status_counts": dict(sorted(counts.items())),
        }

    report = {
        "start_date": start_date,
        "end_date": end_date,
        "documents": int(len(docs_df)),
        "csv_candidates": int(len(candidates)),
        "downloaded": int(len(snap_df)),
        "parse_errors": int(len(errors)),
        "errors": errors,
        "field_coverage": coverage,
        "dilution_evidence": dilution_audit.evidence_report(dilution_df),
        "note": (
            "Missing or ambiguous facts remain unknown. Dilution output is audit evidence only; "
            "no candidate share count is accepted as residual dilution automatically."
        ),
    }
    return (
        docs_df.reset_index(drop=True),
        snap_df.reset_index(drop=True),
        dilution_df.reset_index(drop=True),
        report,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--symbols", default="", help="comma-separated four-character JPX symbols")
    ap.add_argument("--request-interval", type=float, default=1.0)
    ap.add_argument("--max-docs", type=int)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    key = require_api_key()
    symbols = {s.strip().upper() for s in args.symbols.split(",") if s.strip()} or None
    client = EdinetClient(key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    docs, snapshots, dilution_evidence, report = collect(
        client,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=symbols,
        request_interval=max(0.0, args.request_interval),
        max_docs=args.max_docs,
    )
    docs.to_csv(out_dir / "edinet_documents.csv", index=False)
    snapshots.to_csv(out_dir / "edinet_fundamental_snapshots.csv", index=False)
    dilution_evidence.to_csv(out_dir / "edinet_dilution_evidence.csv", index=False)
    with open(out_dir / "edinet_coverage.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
