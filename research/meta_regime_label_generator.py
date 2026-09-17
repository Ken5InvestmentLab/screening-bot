"""Causal Meta regime label generator (research-only).

Implements META_REGIME_SWITCHING_PREREG_20260917.md only.
No outcome/return columns are read. 2026 rows are rejected.
"""
from __future__ import annotations
import pandas as pd

HISTORY = 120
Q_LOW = 0.33
Q_HIGH = 0.67
ALLOWED_YEARS = {2023, 2024, 2025}


def _causal_band(history: pd.Series, value: float) -> str | None:
    h = pd.to_numeric(history, errors="coerce").dropna()
    if len(h) < HISTORY or pd.isna(value):
        return None
    h = h.iloc[-HISTORY:]
    lo, hi = h.quantile([Q_LOW, Q_HIGH]).tolist()
    if value <= lo:
        return "LOW"
    if value >= hi:
        return "HIGH"
    return "MID"


def label_rows(rows: pd.DataFrame, daily_regime: pd.DataFrame) -> pd.DataFrame:
    """Attach causal breadth/range/scarcity labels to pinned candidate rows.

    Required rows: signal_date, candidate_count_pre_rank.
    Required daily_regime: session, breadth_ma20, range_pct.
    Percentiles use exactly the 120 XTKS sessions strictly before signal T.
    """
    r = rows.copy()
    d = daily_regime.copy()
    r["signal_date"] = pd.to_datetime(r["signal_date"]).dt.normalize()
    d["session"] = pd.to_datetime(d["session"]).dt.normalize()
    if not set(r["signal_date"].dt.year.unique()).issubset(ALLOWED_YEARS):
        raise ValueError("fail-closed: only 2023-2025 rows are allowed; 2026 is sealed")
    d = d.sort_values("session").drop_duplicates("session", keep="last")
    by_session = d.set_index("session")
    breadth_labels, range_labels, reasons = [], [], []
    for t in r["signal_date"]:
        prior = d.loc[d["session"] < t].tail(HISTORY)
        cur = by_session.loc[t] if t in by_session.index else None
        if cur is None or len(prior) < HISTORY:
            breadth_labels.append(None); range_labels.append(None)
            reasons.append("MISSING_SIGNAL_SESSION" if cur is None else "INSUFFICIENT_120_PRIOR_XTKS")
            continue
        b = _causal_band(prior["breadth_ma20"], cur["breadth_ma20"])
        g = _causal_band(prior["range_pct"], cur["range_pct"])
        breadth_labels.append(b); range_labels.append(g)
        reasons.append(None if b is not None and g is not None else "MISSING_REGIME_VALUE")
    r["breadth_regime"] = breadth_labels
    r["range_regime"] = range_labels
    cnt = pd.to_numeric(r["candidate_count_pre_rank"], errors="coerce")
    r["scarcity_regime"] = cnt.map(lambda x: "SCARCE" if x == 1 else ("MULTI" if x >= 2 else None))
    r["meta_label_fail_reason"] = reasons
    bad_scarcity = r["scarcity_regime"].isna() & r["meta_label_fail_reason"].isna()
    r.loc[bad_scarcity, "meta_label_fail_reason"] = "MISSING_CANDIDATE_COUNT_PRE_RANK"
    r["meta_label_covered"] = r[["breadth_regime", "range_regime", "scarcity_regime"]].notna().all(axis=1)
    return r
