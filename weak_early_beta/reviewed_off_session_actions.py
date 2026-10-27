"""Retain one reviewed provider journal entry, without repairing security prices.

The provider date is the delisting date, not the legal consolidation date.
Later private-company actions do not establish continuity across the relisting.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re

import pandas as pd


SEED_SHA256 = "0c4643bb6ea521dc99d9e0a7cab3624bc0e9706ea9796bc26f710af48b278a03"
PRIOR_AUDIT_ATTR = "verified_retained_off_session_actions"
ISSUE = "ambiguous_security_identity_after_consolidation"
EVENT = {"effective_date": "2023-09-28", "ratio": 5e-8, "source": "Yahoo Finance Stock Splits"}
SEED_BOUNDS = {"firstDate": "2021-10-26", "lastDate": "2026-10-26", "basisAsOf": "2026-10-26", "rows": 689}
CATALOG = {
    "identity": "CLOUD_REVIEWED_OFF_SESSION_ACTION_V1", "symbol": "8303",
    "providerEvent": EVENT, "legalEffectiveDate": "2023-10-02",
    "primarySourceURLs": [
        "https://www.jpx.co.jp/news/1023/20230901-11.html",
        "https://corp.sbishinseibank.co.jp/ja/news/news/auto_20230831549172/pdfFile.pdf",
        "https://corp.sbishinseibank.co.jp/ja/news/news/20251113c.html",
    ],
    "seedSourceSha256": SEED_SHA256, "seedBounds": SEED_BOUNDS,
    "policy": "provider-journal-only; identity remains quarantined; no later actions inferred",
}
CATALOG_SHA256 = hashlib.sha256(json.dumps(CATALOG, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bounds(group: pd.DataFrame) -> dict:
    return {"firstDate": f"{group.date.min():%Y-%m-%d}", "lastDate": f"{group.date.max():%Y-%m-%d}",
            "basisAsOf": f"{group.basis_asof.iloc[0]:%Y-%m-%d}", "rows": len(group)}


def _raw_fingerprint(group: pd.DataFrame) -> str:
    """Exact sorted raw numeric values, independent of DataFrame dtypes/index."""
    fields = ("open", "high", "low", "close", "volume", "split_ratio")
    rows = [[str(row.symbol), f"{row.date:%Y-%m-%d}",
             *[float(getattr(row, field)).hex() for field in fields]]
            for row in group.sort_values("date").itertuples()]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def retain_reviewed_off_session_actions(previous: pd.DataFrame | None, current: pd.DataFrame,
                                        *, basis_asof: pd.Timestamp) -> tuple[pd.DataFrame, list[dict]]:
    """Authorize only the pinned seed or its source-quality-verified descendants.

    Inputs are never mutated. Only the raw off-session journal can change;
    ordinary normalization and source-revision validation still run afterwards.
    """
    from .corporate_actions import (
        ACTION_SOURCE, ACTUAL_COLUMNS, BASIS_COLUMNS, OHLC, PRICE_BASIS, VERSION,
        CorporateActionError, _dates, _off_session_events, normalize_daily,
    )

    if previous is None or "symbol" not in previous or "symbol" not in current:
        return current, []
    old = previous.loc[previous.symbol.eq("8303")].copy()
    now = current.loc[current.symbol.eq("8303")].copy()
    if old.empty or now.empty:
        return current, []
    # An unauthenticated provider declaration belongs to ordinary validation.
    # Established lineage also survives a day on which the provider reappears.
    current_events = _off_session_events(now)
    expected = {"symbol": "8303", **EVENT, "effective_date": pd.Timestamp(EVENT["effective_date"])}
    declared = current_events == [expected]
    if declared and previous.attrs.get("source_sha256") != SEED_SHA256 and PRIOR_AUDIT_ATTR not in previous.attrs:
        return current, []
    if "off_session_actions" not in old or not old.off_session_actions.fillna("").astype(str).str.strip().ne("").any():
        return current, []

    def reject(reason: str) -> None:
        raise CorporateActionError(f"reviewed off-session retention rejected for 8303: {reason}")

    required = {"symbol", "date", *OHLC, "volume", *ACTUAL_COLUMNS, *BASIS_COLUMNS}
    if not required.issubset(old.columns):
        reject("incomplete previous basis metadata")
    for field, value in (("price_basis", PRICE_BASIS), ("corporate_actions_version", VERSION),
                         ("corporate_actions_source", ACTION_SOURCE), ("source_issue", ISSUE)):
        if not old[field].eq(value).fillna(False).all():
            reject(f"unexpected previous {field}")
    if not old.source_usable.astype(str).str.lower().eq("false").all():
        reject("previous identity is not fully quarantined")
    old["date"] = _dates(old.date)
    old["basis_asof"] = _dates(old.basis_asof)
    if old.basis_asof.nunique() != 1 or not old.split_ratio.eq(0).all():
        reject("previous regular actions or mixed basis")
    journal = old.off_session_actions.fillna("").astype(str).str.strip()
    nonempty = journal[journal.ne("")]
    try:
        if (len(nonempty) != 1 or nonempty.index[0] != old.date.idxmax()
                or json.loads(nonempty.iloc[0]) != [EVENT]):
            reject("previous journal is not the exact reviewed provider event")
    except (ValueError, TypeError) as exc:
        raise CorporateActionError("invalid reviewed off-session journal") from exc
    old = normalize_daily(old)
    old_bounds = _bounds(old)
    source_sha = previous.attrs.get("source_sha256")
    if source_sha == SEED_SHA256:
        if old_bounds != SEED_BOUNDS:
            reject("seed symbol bounds differ")
    else:
        lineage = previous.attrs.get(PRIOR_AUDIT_ATTR)
        if (not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha)
                or not isinstance(lineage, dict) or lineage.get("dailySha256") != source_sha):
            reject("no matching source-quality lineage")
        audits = lineage.get("actions")
        if not isinstance(audits, list) or len(audits) != 1 or not isinstance(audits[0], dict):
            reject("invalid retention lineage")
        audit = audits[0]
        fixed = {"identity": CATALOG["identity"], "catalogSha256": CATALOG_SHA256,
                 "symbol": "8303", "seedSourceSha256": SEED_SHA256, "seedBounds": SEED_BOUNDS,
                 "providerEvent": EVENT, "legalEffectiveDate": CATALOG["legalEffectiveDate"],
                 "primarySourceURLs": CATALOG["primarySourceURLs"], "originalJournal": [EVENT],
                 "noPriceEdits": True, "currentBounds": old_bounds}
        if any(audit.get(key) != value for key, value in fixed.items()) or audit.get("noPriceEdits") is not True:
            reject("retention catalog/seed/bounds lineage mismatch")
        if audit.get("actionStatus") not in ("retained", "provider-declared"):
            reject("invalid prior action status")
        # The matching full CSV hash authenticates persisted input. These
        # digests prove the prior in-memory operation did not edit numbers;
        # reparsing CSV need not reproduce its pre-serialization float bits.
        proof = audit.get("rawOHLCVBeforeSha256")
        if (not isinstance(proof, str) or not re.fullmatch(r"[0-9a-f]{64}", proof)
                or audit.get("rawOHLCVAfterSha256") != proof):
            reject("invalid prior no-price-edit proof")
        prior_sha = audit.get("previousSourceSha256")
        prior_bounds = audit.get("previousBounds")
        if (not isinstance(prior_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", prior_sha)
                or not isinstance(prior_bounds, dict) or set(prior_bounds) != set(SEED_BOUNDS)):
            reject("invalid previous source linkage")
        try:
            prior_dates = _dates([prior_bounds[key] for key in ("firstDate", "lastDate", "basisAsOf")])
            if (not prior_dates[0] < pd.Timestamp(EVENT["effective_date"]) < prior_dates[1] <= prior_dates[2]
                    or prior_dates[0] > old.date.min() or prior_dates[2] > old.basis_asof.iloc[0]
                    or type(prior_bounds["rows"]) is not int or prior_bounds["rows"] <= 0
                    or (prior_sha == SEED_SHA256 and prior_bounds != SEED_BOUNDS)):
                reject("invalid prior bounds linkage")
        except (TypeError, ValueError) as exc:
            raise CorporateActionError("invalid reviewed retention bounds") from exc

    if (current_events and not declared) or not now.split_ratio.eq(0).all():
        reject("current action journal conflicts")
    now["date"] = _dates(now.date)
    provider_date = pd.Timestamp(EVENT["effective_date"])
    for group in (old, now):
        if not group.date.min() < provider_date < group.date.max() or group.date.eq(provider_date).any():
            reject("event is not bracketed by unpriced history")
    if (now.date.min() < old.date.min() or now.date.max() < old.date.max()
            or _dates([basis_asof])[0] < old.basis_asof.iloc[0]):
        reject("current history moved backwards")
    result = current.copy()
    if not declared:
        result.loc[now.date.idxmax(), "off_session_actions"] = json.dumps([EVENT], separators=(",", ":"))
    before_hash = _raw_fingerprint(now)
    after_hash = _raw_fingerprint(result.loc[result.symbol.eq("8303")])
    if before_hash != after_hash:
        reject("raw price/volume/action values changed")
    verified = normalize_daily(result.loc[result.symbol.eq("8303")], basis_asof=basis_asof)
    if verified.source_usable.any() or not verified.source_issue.eq(ISSUE).all():
        reject("retained identity must remain wholly quarantined")
    audit = {"identity": CATALOG["identity"], "catalogSha256": CATALOG_SHA256, "symbol": "8303",
             "seedSourceSha256": SEED_SHA256, "seedBounds": SEED_BOUNDS,
             "previousSourceSha256": source_sha, "previousBounds": old_bounds,
             "currentBounds": _bounds(verified), "providerEvent": EVENT,
             "legalEffectiveDate": CATALOG["legalEffectiveDate"],
             "primarySourceURLs": CATALOG["primarySourceURLs"], "originalJournal": [EVENT],
             "noPriceEdits": True, "actionStatus": "provider-declared" if declared else "retained",
             "rawOHLCVBeforeSha256": before_hash,
             "rawOHLCVAfterSha256": after_hash}
    return result, [copy.deepcopy(audit)]
