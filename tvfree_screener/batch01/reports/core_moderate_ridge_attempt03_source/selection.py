"""Leakage-resistant candidate ranking and independent Top-N policies."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from collections.abc import Sequence

import pandas as pd


ALLOWED_TOP_N = (1, 2, 3, 5)
POLICY_VERSION = "canonical-selection-v1"
FUTURE_COLUMN_PREFIXES = ("future_", "target", "label_", "realized_", "exit_")
FUTURE_COLUMN_NAMES = {
    "return_5bd", "target_end_date", "target5_cc", "target5_no",
    "five_day_return", "label_available_at",
}


@dataclass(frozen=True)
class PolicySpec:
    """One independently evaluated lane and selection count."""

    lane: str
    top_n: int
    policy_id: str
    cooldown_sessions: int = 1

    def __post_init__(self) -> None:
        if self.top_n not in ALLOWED_TOP_N:
            raise ValueError(f"top_n must be one of {ALLOWED_TOP_N}")
        if not self.lane.strip() or not self.policy_id.strip():
            raise ValueError("lane and policy_id must be non-empty")
        if self.cooldown_sessions != 1:
            raise ValueError("canonical policy uses exactly one prior TSE session")


@dataclass(frozen=True)
class SelectionResult:
    selected: pd.DataFrame
    candidate_trace: pd.DataFrame
    daily: pd.DataFrame
    policy_sha256: str
    selection_sha256: str


def _iso(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _frame_digest(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    """Hash only declared decision-time fields; arbitrary input columns are ignored."""
    rows = frame.loc[:, list(columns)].copy()
    if "date" in rows.columns:
        rows["date"] = pd.to_datetime(rows["date"]).map(_iso)
    records = rows.astype(object).where(pd.notna(rows), None).to_dict(orient="records")
    return _canonical_digest(records)


def _is_future_column(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in FUTURE_COLUMN_NAMES or lowered.startswith(FUTURE_COLUMN_PREFIXES)


def rank_candidate_pool(
    pool: pd.DataFrame,
    *,
    sessions: Sequence[object],
    feature_columns: Sequence[str],
    ranking_terms: Sequence[tuple[str, bool]],
    date_col: str = "date",
    symbol_col: str = "symbol",
    family_col: str = "family",
    spec_hash_col: str = "spec_hash",
    identity_col: str = "identity_key",
) -> pd.DataFrame:
    """Rank the full preregistered pool before cooldown, retaining no labels.

    ranking_terms is an ordered list of (column, ascending) pairs. The symbol
    is always the final ascending deterministic tie-break. Only required
    metadata, declared signal-time features, and ranking terms are returned,
    so a future-label column supplied by mistake cannot leak into the saved
    pool or its selection hash.
    """
    if not ranking_terms:
        raise ValueError("at least one preregistered ranking term is required")
    term_columns = [column for column, _ in ranking_terms]
    declared_features = list(feature_columns)
    if len(declared_features) != len(set(declared_features)):
        raise ValueError("feature_columns contains duplicates")
    if any(_is_future_column(column) for column in declared_features + term_columns):
        raise ValueError("future outcome columns cannot enter the candidate pool")

    required = {date_col, symbol_col, family_col, spec_hash_col, *term_columns}
    missing = sorted(required.difference(pool.columns))
    if missing:
        raise ValueError(f"missing candidate-pool columns: {missing}")
    absent_features = sorted(set(declared_features).difference(pool.columns))
    if absent_features:
        raise ValueError(f"missing declared signal-time features: {absent_features}")
    if pool.empty:
        return pd.DataFrame(columns=[
            "date", "symbol", "family", "spec_hash", "identity_key",
            "score", "raw_rank", "daily_candidate_count", *declared_features,
        ])

    work = pool.copy()
    work["date"] = pd.to_datetime(work[date_col], errors="raise").dt.normalize()
    work["symbol"] = work[symbol_col].astype("string")
    work["family"] = work[family_col].astype("string")
    work["spec_hash"] = work[spec_hash_col].astype("string")
    if identity_col in work.columns:
        work["identity_key"] = work[identity_col].astype("string")
    else:
        # Legacy datasets without a PIT issuer key are symbol-keyed and must
        # carry the separate identity-reuse limitation in their manifest.
        work["identity_key"] = work["symbol"]
    if work[["date", "symbol", "family", "spec_hash", "identity_key"]].isna().any().any():
        raise ValueError("date, symbol, family, spec hash and identity key cannot be missing")
    if work.duplicated(["date", "family", "spec_hash", "symbol"]).any():
        raise ValueError("duplicate family/spec/symbol candidate on a date")
    if work.duplicated(["date", "family", "spec_hash", "identity_key"]).any():
        raise ValueError("duplicate instrument identity in one daily candidate pool")

    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    if not set(pd.DatetimeIndex(work["date"].unique())).issubset(set(calendar)):
        raise ValueError("candidate date is missing from the official session calendar")

    for column, _ascending in ranking_terms:
        work[column] = pd.to_numeric(work[column], errors="coerce")
        if work[column].isna().any():
            raise ValueError(f"ranking term {column!r} contains missing or non-numeric values")

    terms = [column for column, _ascending in ranking_terms]
    ascending = [direction for _column, direction in ranking_terms]
    sort_columns = ["date", "family", "spec_hash", *terms, "symbol"]
    sort_ascending = [True, True, True, *ascending, True]
    work = work.sort_values(sort_columns, ascending=sort_ascending, kind="mergesort")
    group_cols = ["date", "family", "spec_hash"]
    work["raw_rank"] = work.groupby(group_cols, sort=False).cumcount().add(1).astype("int64")
    work["daily_candidate_count"] = work.groupby(group_cols, sort=False)["symbol"].transform("size").astype("int64")
    work["score"] = work[terms[0]]
    work["tie_break_json"] = work.apply(
        lambda row: json.dumps(
            {name: row[name].item() if hasattr(row[name], "item") else row[name] for name in terms[1:]},
            sort_keys=True, separators=(",", ":"), default=str,
        ),
        axis=1,
    )
    keep = [
        "date", "symbol", "family", "spec_hash", "identity_key",
        "score", "raw_rank", "daily_candidate_count", "tie_break_json",
        *terms, *declared_features,
    ]
    if "candidate_id" in work.columns:
        keep.insert(4, "candidate_id")
    for name in ("decision_timestamp", "feature_timestamp", "inclusion_reason"):
        if name in work.columns:
            keep.append(name)
    keep = list(dict.fromkeys(keep))
    return work.loc[:, keep].reset_index(drop=True)


def policy_digest(spec: PolicySpec) -> str:
    return _canonical_digest({"version": POLICY_VERSION, **asdict(spec)})


def apply_selection_policy(
    ranked_pool: pd.DataFrame,
    *,
    sessions: Sequence[object],
    policy: PolicySpec,
) -> SelectionResult:
    """Apply one Top-N policy with selected-symbol-only, one-session cooldown.

    Call separately for each lane and Top-N. Its cooldown state is therefore
    independent. The empty official session between two signal dates clears
    the previous-session block. Cooldown is carried across year and fold edges.
    """
    required = {
        "date", "symbol", "family", "spec_hash", "identity_key",
        "score", "raw_rank", "daily_candidate_count",
    }
    missing = sorted(required.difference(ranked_pool.columns))
    if missing:
        raise ValueError(f"missing ranked-pool columns: {missing}")
    if not ranked_pool.empty:
        if ranked_pool["family"].nunique(dropna=False) != 1 or ranked_pool["spec_hash"].nunique(dropna=False) != 1:
            raise ValueError("one policy run must contain exactly one family and spec hash")
        if ranked_pool.duplicated(["date", "symbol"]).any():
            raise ValueError("ranked pool contains duplicate symbol/date rows")

    calendar = pd.DatetimeIndex(pd.to_datetime(list(sessions), errors="raise")).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    work = ranked_pool.copy()
    if not work.empty:
        work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
        if not set(pd.DatetimeIndex(work["date"].unique())).issubset(set(calendar)):
            raise ValueError("candidate date is missing from the official session calendar")

    groups = {pd.Timestamp(day): group for day, group in work.groupby("date", sort=False)}
    previous_selected: set[str] = set()
    selected_frames: list[pd.DataFrame] = []
    trace_frames: list[pd.DataFrame] = []
    daily_rows: list[dict[str, object]] = []

    for session in calendar:
        day = pd.Timestamp(session)
        candidates = groups.get(day)
        if candidates is None or candidates.empty:
            previous_selected = set()
            daily_rows.append({
                "date": day, "policy_id": policy.policy_id, "lane": policy.lane,
                "top_n": policy.top_n, "candidate_count": 0,
                "cooldown_blocked_count": 0, "post_cooldown_count": 0,
                "selected_count": 0, "selected_symbols": [],
                "abstain_reason": "NO_CANDIDATES",
            })
            continue

        day_rows = candidates.copy()
        identity = day_rows["identity_key"].astype(str)
        blocked_mask = identity.isin(previous_selected)
        post = day_rows.loc[~blocked_mask].sort_values(
            ["raw_rank", "symbol"], ascending=[True, True], kind="mergesort"
        ).copy()
        post["policy_rank"] = range(1, len(post) + 1)
        chosen = post.head(policy.top_n).copy()
        chosen["policy_id"] = policy.policy_id
        chosen["lane"] = policy.lane
        chosen["top_n"] = policy.top_n
        chosen["selection_status"] = "SELECTED"
        selected_frames.append(chosen)

        trace = day_rows.copy()
        trace["policy_id"] = policy.policy_id
        trace["lane"] = policy.lane
        trace["top_n"] = policy.top_n
        rank_map = post.set_index("symbol")["policy_rank"]
        trace["policy_rank"] = trace["symbol"].map(rank_map).astype("Int64")
        selected_symbols = set(chosen["symbol"].astype(str))
        trace["selection_status"] = "COOLDOWN_BLOCKED"
        trace.loc[
            (~blocked_mask) & (~trace["symbol"].astype(str).isin(selected_symbols)),
            "selection_status",
        ] = "ABOVE_TOP_N"
        trace.loc[trace["symbol"].astype(str).isin(selected_symbols), "selection_status"] = "SELECTED"
        trace_frames.append(trace)

        previous_selected = set(chosen["identity_key"].astype(str))
        daily_rows.append({
            "date": day, "policy_id": policy.policy_id, "lane": policy.lane,
            "top_n": policy.top_n, "candidate_count": int(len(day_rows)),
            "cooldown_blocked_count": int(blocked_mask.sum()),
            "post_cooldown_count": int(len(post)),
            "selected_count": int(len(chosen)),
            "selected_symbols": sorted(selected_symbols),
            "abstain_reason": "ALL_BLOCKED_BY_COOLDOWN" if len(chosen) == 0 else None,
        })

    empty = work.iloc[0:0].copy()
    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else empty.copy()
    trace = pd.concat(trace_frames, ignore_index=True) if trace_frames else empty.assign(
        policy_id=pd.Series(dtype="string"),
        lane=pd.Series(dtype="string"),
        top_n=pd.Series(dtype="int64"),
        policy_rank=pd.Series(dtype="Int64"),
        selection_status=pd.Series(dtype="string"),
    )
    daily = pd.DataFrame(daily_rows)
    digest_columns = [
        column for column in (
            "date", "symbol", "family", "spec_hash", "identity_key",
            "score", "raw_rank", "daily_candidate_count", "policy_id",
            "lane", "top_n", "policy_rank", "selection_status",
        ) if column in trace.columns
    ]
    policy_hash = policy_digest(policy)
    selection_hash = _canonical_digest({
        "policy_sha256": policy_hash,
        "selected_sha256": _frame_digest(selected, [
            column for column in digest_columns if column in selected.columns
        ]),
    })
    return SelectionResult(
        selected=selected,
        candidate_trace=trace,
        daily=daily,
        policy_sha256=policy_hash,
        selection_sha256=selection_hash,
    )
