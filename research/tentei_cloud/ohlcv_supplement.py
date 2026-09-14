from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

SUPPLEMENT_CONTRACT_VERSION = 1
REQUIRED_INVENTORY_COLUMNS = (
    "symbol",
    "timestamp",
    "timeframe",
    "decision_ts",
)
REQUIRED_SUPPLEMENT_COLUMNS = (
    "symbol",
    "timestamp",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "acquired_at",
    "latest_market_ts",
    "raw_sha256",
)


@dataclass(frozen=True)
class SourceRule:
    priority: int
    formal_eligible: bool
    allowed_timeframes: tuple[str, ...]


def _iso_utc(series: pd.Series, name: str) -> pd.Series:
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError(f"{name} contains non-parseable timestamps: {int(ts.isna().sum())}")
    return ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_hex(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def canonical_source_policy(policy: Mapping[str, Mapping]) -> dict[str, SourceRule]:
    if not policy:
        raise ValueError("source policy must not be empty")
    out: dict[str, SourceRule] = {}
    priorities: set[int] = set()
    for source, cfg in policy.items():
        source = str(source).strip()
        if not source:
            raise ValueError("source policy contains blank source")
        priority = int(cfg["priority"])
        if priority < 0 or priority in priorities:
            raise ValueError("source priorities must be unique nonnegative integers")
        priorities.add(priority)
        allowed = tuple(str(x).strip().lower() for x in cfg.get("allowed_timeframes", ()))
        if not allowed:
            raise ValueError(f"source {source} has no allowed_timeframes")
        out[source] = SourceRule(
            priority=priority,
            formal_eligible=bool(cfg.get("formal_eligible", False)),
            allowed_timeframes=allowed,
        )
    return out


def canonical_missing_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_INVENTORY_COLUMNS if c not in inventory.columns]
    if missing:
        raise ValueError(f"missing inventory columns: {missing}")
    x = inventory.loc[:, REQUIRED_INVENTORY_COLUMNS].copy()
    x["symbol"] = x["symbol"].astype("string").str.replace(".T", "", regex=False).str.strip()
    x["timestamp"] = _iso_utc(x["timestamp"], "inventory.timestamp")
    x["decision_ts"] = _iso_utc(x["decision_ts"], "inventory.decision_ts")
    x["timeframe"] = x["timeframe"].astype("string").str.strip().str.lower()
    if x["symbol"].isna().any() or (x["symbol"] == "").any():
        raise ValueError("inventory contains blank symbol")
    if (pd.to_datetime(x["timestamp"], utc=True) > pd.to_datetime(x["decision_ts"], utc=True)).any():
        raise ValueError("inventory endpoint timestamp is after decision_ts")
    if x.duplicated(["symbol", "timestamp", "timeframe"]).any():
        raise ValueError("missing inventory contains duplicate symbol/timestamp/timeframe")
    return x.sort_values(["symbol", "timestamp", "timeframe"]).reset_index(drop=True)


def canonical_supplement_rows(rows: pd.DataFrame, source_policy: Mapping[str, Mapping]) -> pd.DataFrame:
    policy = canonical_source_policy(source_policy)
    missing = [c for c in REQUIRED_SUPPLEMENT_COLUMNS if c not in rows.columns]
    if missing:
        raise ValueError(f"supplement rows missing columns: {missing}")

    x = rows.loc[:, REQUIRED_SUPPLEMENT_COLUMNS].copy()
    x["symbol"] = x["symbol"].astype("string").str.replace(".T", "", regex=False).str.strip()
    x["timestamp"] = _iso_utc(x["timestamp"], "supplement.timestamp")
    x["acquired_at"] = _iso_utc(x["acquired_at"], "supplement.acquired_at")
    x["latest_market_ts"] = _iso_utc(x["latest_market_ts"], "supplement.latest_market_ts")
    x["timeframe"] = x["timeframe"].astype("string").str.strip().str.lower()
    x["source"] = x["source"].astype("string").str.strip()

    for c in ("open", "high", "low", "close", "volume"):
        x[c] = pd.to_numeric(x[c], errors="coerce")
    if x[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError("supplement OHLCV contains non-finite/non-numeric values")
    if (x[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("supplement OHLC prices must be positive")
    if (x["volume"] < 0).any():
        raise ValueError("supplement volume must be nonnegative")
    if (x["high"] < x[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("supplement high violates OHLC consistency")
    if (x["low"] > x[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("supplement low violates OHLC consistency")
    if (pd.to_datetime(x["latest_market_ts"], utc=True) > pd.to_datetime(x["timestamp"], utc=True)).any():
        raise ValueError("latest_market_ts is after represented endpoint timestamp")
    if (pd.to_datetime(x["acquired_at"], utc=True) < pd.to_datetime(x["latest_market_ts"], utc=True)).any():
        raise ValueError("acquired_at precedes latest_market_ts")
    if not x["raw_sha256"].map(_sha256_hex).all():
        raise ValueError("supplement raw_sha256 must be a 64-character hex digest")

    unknown = sorted(set(x["source"].tolist()) - set(policy))
    if unknown:
        raise ValueError(f"supplement contains unregistered sources: {unknown}")

    def source_ok(row: pd.Series) -> bool:
        rule = policy[str(row["source"])]
        return rule.formal_eligible and str(row["timeframe"]) in rule.allowed_timeframes

    x["source_formal_eligible"] = x.apply(source_ok, axis=1)
    x["source_priority"] = x["source"].map(lambda s: policy[str(s)].priority)
    return x.sort_values(["symbol", "timestamp", "timeframe", "source_priority", "source"]).reset_index(drop=True)


def _row_value_tuple(row: pd.Series) -> tuple[float, float, float, float, float]:
    return tuple(float(row[c]) for c in ("open", "high", "low", "close", "volume"))


def verify_and_select_supplements(
    inventory: pd.DataFrame,
    supplement_rows: pd.DataFrame,
    source_policy: Mapping[str, Mapping],
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Select only deterministic, provenance-complete supplements for predeclared missing pairs.

    This is deliberately outcome-blind. Rows that were not in the pre-supplement missing
    inventory are rejected. Multiple eligible sources for one pair must agree exactly on
    OHLCV; otherwise the pair is conflicted and excluded rather than averaged or selected
    by source priority.
    """
    inv = canonical_missing_inventory(inventory)
    supp = canonical_supplement_rows(supplement_rows, source_policy)
    policy = canonical_source_policy(source_policy)

    key_cols = ["symbol", "timestamp", "timeframe"]
    inv_keys = set(map(tuple, inv[key_cols].itertuples(index=False, name=None)))
    decision_by_key = {
        tuple(r[c] for c in key_cols): r["decision_ts"]
        for _, r in inv.iterrows()
    }

    audit_rows: list[dict] = []
    selected_rows: list[dict] = []

    for key, group in supp.groupby(key_cols, sort=True, dropna=False):
        key = tuple(key) if isinstance(key, tuple) else (key,)
        if key not in inv_keys:
            for _, row in group.iterrows():
                audit_rows.append({**row.to_dict(), "acceptance": "REJECT_NOT_IN_MISSING_INVENTORY"})
            continue

        decision_ts = pd.Timestamp(decision_by_key[key])
        eligible = group[group["source_formal_eligible"]].copy()
        if eligible.empty:
            for _, row in group.iterrows():
                audit_rows.append({**row.to_dict(), "acceptance": "REJECT_SOURCE_NOT_FORMAL_ELIGIBLE"})
            continue

        # Historical repair may be acquired later, but the market interval represented by
        # the row must itself not extend past the original decision timestamp.
        eligible = eligible[
            pd.to_datetime(eligible["latest_market_ts"], utc=True) <= decision_ts
        ].copy()
        if eligible.empty:
            for _, row in group.iterrows():
                audit_rows.append({**row.to_dict(), "acceptance": "REJECT_CAUSALITY"})
            continue

        distinct_values = {_row_value_tuple(row) for _, row in eligible.iterrows()}
        if len(distinct_values) > 1:
            for _, row in group.iterrows():
                audit_rows.append({**row.to_dict(), "acceptance": "CONFLICT_FAIL_CLOSED"})
            continue

        winner = eligible.sort_values(["source_priority", "source"]).iloc[0]
        selected = winner.to_dict()
        selected["provenance"] = "supplemented"
        selected["acceptance"] = "ACCEPT"
        selected_rows.append(selected)
        winner_source = str(winner["source"])
        for _, row in group.iterrows():
            status = "ACCEPT" if str(row["source"]) == winner_source else "AGREEING_ALTERNATE_NOT_SELECTED"
            if not bool(row["source_formal_eligible"]):
                status = "REJECT_SOURCE_NOT_FORMAL_ELIGIBLE"
            audit_rows.append({**row.to_dict(), "acceptance": status})

    selected = pd.DataFrame(selected_rows)
    audit = pd.DataFrame(audit_rows)
    accepted_keys = set(map(tuple, selected[key_cols].itertuples(index=False, name=None))) if not selected.empty else set()
    unresolved = len(inv_keys - accepted_keys)
    conflict_n = 0 if audit.empty else int(
        audit.loc[audit["acceptance"] == "CONFLICT_FAIL_CLOSED", key_cols].drop_duplicates().shape[0]
    )

    receipt_payload = {
        "contract_version": SUPPLEMENT_CONTRACT_VERSION,
        "status": "PASS" if unresolved == 0 else "FAIL_CLOSED",
        "inventory_n": int(len(inv)),
        "accepted_n": int(len(accepted_keys)),
        "unresolved_n": int(unresolved),
        "conflicted_pair_n": conflict_n,
        "source_hierarchy": [
            {
                "source": source,
                "priority": rule.priority,
                "formal_eligible": rule.formal_eligible,
                "allowed_timeframes": list(rule.allowed_timeframes),
            }
            for source, rule in sorted(policy.items(), key=lambda kv: kv[1].priority)
        ],
        "interpolation": False,
        "forward_fill_back_fill": False,
        "daily_to_intraday_synthesis": False,
        "outcome_informed_selection": False,
        "performance_opened": False,
    }
    encoded = json.dumps(receipt_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt_payload["receipt_sha256"] = hashlib.sha256(encoded).hexdigest()
    return selected, audit, receipt_payload


def source_file_receipt(path: str | Path, *, source: str, acquired_at: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"source file does not exist: {p}")
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    acquired = pd.to_datetime(pd.Series([acquired_at]), utc=True, errors="coerce")
    if acquired.isna().any():
        raise ValueError("acquired_at is invalid")
    payload = {
        "source": str(source),
        "name": p.name,
        "size_bytes": int(p.stat().st_size),
        "sha256": h,
        "acquired_at": acquired.dt.strftime("%Y-%m-%dT%H:%M:%SZ").iloc[0],
    }
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload
