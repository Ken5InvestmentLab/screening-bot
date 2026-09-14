from __future__ import annotations

import hashlib
import json

import pandas as pd

REQUIRED_CALENDAR_COLUMNS = (
    "date",
    "calendar_name",
    "calendar_version",
    "open_bar_ts",
    "close_bar_ts",
)
REQUIRED_RAW_COLUMNS = ("symbol", "timestamp", "open", "close")


def _iso_utc(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError(f"non-parseable timestamp rows: {int(ts.isna().sum())}")
    return ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_calendar_manifest(calendar: pd.DataFrame) -> pd.DataFrame:
    """Validate and canonicalize a vendor-specific pinned XTKS endpoint manifest."""
    missing = [c for c in REQUIRED_CALENDAR_COLUMNS if c not in calendar.columns]
    if missing:
        raise ValueError(f"calendar manifest missing columns: {missing}")

    x = calendar.loc[:, REQUIRED_CALENDAR_COLUMNS].copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if x["date"].isna().any():
        raise ValueError("calendar manifest contains invalid date")

    for c in ("calendar_name", "calendar_version"):
        x[c] = x[c].astype("string").str.strip()
        if x[c].isna().any() or (x[c] == "").any():
            raise ValueError(f"calendar manifest contains blank {c}")

    if x["calendar_name"].nunique(dropna=False) != 1:
        raise ValueError("calendar_name must be constant")
    if x["calendar_version"].nunique(dropna=False) != 1:
        raise ValueError("calendar_version must be constant")
    if x["calendar_name"].iloc[0] != "XTKS":
        raise ValueError("calendar_name must equal XTKS")

    x["open_bar_ts"] = _iso_utc(x["open_bar_ts"])
    x["close_bar_ts"] = _iso_utc(x["close_bar_ts"])
    if (pd.to_datetime(x["close_bar_ts"], utc=True) < pd.to_datetime(x["open_bar_ts"], utc=True)).any():
        raise ValueError("close_bar_ts precedes open_bar_ts")

    if x["date"].duplicated().any():
        dup = x.loc[x["date"].duplicated(), "date"].tolist()
        raise ValueError(f"duplicate calendar dates: {dup[:5]}")

    if x["date"].tolist() != sorted(x["date"].tolist()):
        raise ValueError("calendar manifest must be strictly sorted by date")

    return x.reset_index(drop=True)


def calendar_manifest_sha256(calendar: pd.DataFrame) -> str:
    x = canonical_calendar_manifest(calendar)
    encoded = json.dumps(
        x.to_dict(orient="records"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_calendar_manifest(calendar: pd.DataFrame, expected_sha256: str) -> pd.DataFrame:
    x = canonical_calendar_manifest(calendar)
    actual = calendar_manifest_sha256(x)
    if actual != expected_sha256:
        raise ValueError(f"calendar SHA-256 mismatch: expected={expected_sha256} actual={actual}")
    return x


def _normalize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"raw endpoint data missing columns: {missing}")

    x = raw.loc[:, REQUIRED_RAW_COLUMNS].copy()
    x["symbol"] = x["symbol"].astype("string").str.replace(".T", "", regex=False)
    x["timestamp"] = _iso_utc(x["timestamp"])
    x["open"] = pd.to_numeric(x["open"], errors="coerce")
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    if x.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("duplicate symbol/timestamp endpoint rows")
    return x


def resolve_canonical_endpoints(
    candidates: pd.DataFrame,
    raw: pd.DataFrame,
    calendar: pd.DataFrame,
    expected_calendar_sha256: str,
) -> tuple[pd.DataFrame, dict]:
    """Resolve next-XTKS-open -> fifth-XTKS-close using exact pinned raw bar timestamps.

    The calendar manifest must explicitly provide the raw-vendor timestamps that
    represent each XTKS session's opening bar and closing bar. Missing endpoint
    rows never fall back to another observed date or to first/last available rows.
    """
    cal = verify_calendar_manifest(calendar, expected_calendar_sha256)
    rr = _normalize_raw(raw)

    if "symbol" not in candidates.columns or "date" not in candidates.columns:
        raise ValueError("candidates require symbol and date columns")
    c = candidates.copy()
    c["symbol"] = c["symbol"].astype("string").str.replace(".T", "", regex=False)
    c["date"] = pd.to_datetime(c["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if c["date"].isna().any():
        raise ValueError("candidates contain invalid signal date")

    dates = cal["date"].tolist()
    pos = {d: i for i, d in enumerate(dates)}
    c["entry_date"] = c["date"].map(
        lambda d: dates[pos[d] + 1] if d in pos and pos[d] + 1 < len(dates) else None
    )
    c["exit_date"] = c["date"].map(
        lambda d: dates[pos[d] + 5] if d in pos and pos[d] + 5 < len(dates) else None
    )

    c = c.merge(
        cal[["date", "open_bar_ts"]].rename(columns={"date": "entry_date"}),
        on="entry_date",
        how="left",
    )
    c = c.merge(
        cal[["date", "close_bar_ts"]].rename(columns={"date": "exit_date"}),
        on="exit_date",
        how="left",
    )

    c = c.merge(
        rr[["symbol", "timestamp", "open"]].rename(
            columns={"timestamp": "open_bar_ts", "open": "entry_open"}
        ),
        on=["symbol", "open_bar_ts"],
        how="left",
    )
    c = c.merge(
        rr[["symbol", "timestamp", "close"]].rename(
            columns={"timestamp": "close_bar_ts", "close": "exit_close"}
        ),
        on=["symbol", "close_bar_ts"],
        how="left",
    )

    valid = (
        c["entry_date"].notna()
        & c["exit_date"].notna()
        & c["entry_open"].notna()
        & c["exit_close"].notna()
        & (c["entry_open"] > 0)
        & (c["exit_close"] > 0)
    )
    c["endpoint_complete"] = valid
    c["canonical_ret5bd"] = pd.NA
    c.loc[valid, "canonical_ret5bd"] = c.loc[valid, "exit_close"] / c.loc[valid, "entry_open"] - 1.0

    receipt = {
        "status": "PASS" if bool(valid.all()) else "FAIL_CLOSED",
        "calendar_name": cal["calendar_name"].iloc[0],
        "calendar_version": cal["calendar_version"].iloc[0],
        "calendar_sha256": expected_calendar_sha256,
        "candidate_n": int(len(c)),
        "resolved_n": int(valid.sum()),
        "unresolved_n": int((~valid).sum()),
        "cost_pct_points": 0.0,
        "win_definition": "gross return > 0",
        "endpoint": "next XTKS open -> fifth XTKS close",
        "fallback_to_observed_date_or_row": False,
    }
    return c, receipt
