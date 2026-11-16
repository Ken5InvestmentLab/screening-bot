"""Cloud-only split-aware daily prices and auditable share-unit reconstruction.

Yahoo daily OHLC and share volume are already split-adjusted, even when
``auto_adjust=False``.  Keep that series for relative technical features, and
reconstruct the trading day's actual units using declared Stock Splits events.
Dividend adjustment factors and price-jump guesses are deliberately not used.
"""

from __future__ import annotations

import json
import time
from typing import Any, TYPE_CHECKING

import numpy as np
import pandas as pd

from .network import permanent_network_error, transient_network_error

if TYPE_CHECKING:
    from .acquisition import AcquisitionArchive


VERSION = "CLOUD_SPLIT_BASIS_V1"
PRICE_BASIS = "yahoo_daily_split_adjusted"
ACTION_SOURCE = "Yahoo Finance Stock Splits"
OHLC = ("open", "high", "low", "close")
ACTUAL_COLUMNS = tuple(f"actual_{name}" for name in (*OHLC, "volume"))
BASIS_COLUMNS = (
    "split_ratio", "split_factor", "basis_asof", "price_basis",
    "corporate_actions_version", "corporate_actions_source",
    "off_session_actions",
    "source_usable", "source_issue", "provider_repaired",
)
ACTION_COLUMNS = ("symbol", "effective_date", "ratio", "source", "basis_asof")
REVISION_EVIDENCE = "source_revision_evidence"
REVISION_ISSUE = "unstable_historical_repaired_volume"


class CorporateActionError(RuntimeError):
    """An unknown or inconsistent share basis must not enter Cloud scoring."""


def _off_session_events(group: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if "off_session_actions" not in group:
        return events
    symbol = str(group.iloc[0]["symbol"])
    for value in group["off_session_actions"]:
        if pd.isna(value) or not str(value).strip():
            continue
        try:
            parsed = json.loads(str(value))
            if not isinstance(parsed, list):
                raise ValueError("action journal must be a list")
            for event in parsed:
                date = _dates([event["effective_date"]])[0]
                ratio = float(event["ratio"])
                source = str(event["source"])
                if not np.isfinite(ratio) or ratio <= 0 or source != ACTION_SOURCE:
                    raise ValueError("invalid off-session action")
                events.append({"symbol": symbol, "effective_date": date, "ratio": ratio, "source": source})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CorporateActionError(f"invalid off-session action journal for {symbol}") from exc
    dates = [event["effective_date"] for event in events]
    regular_dates = set(group.loc[group["split_ratio"].ne(0), "date"])
    if len(dates) != len(set(dates)) or regular_dates.intersection(dates):
        raise CorporateActionError(f"duplicate regular/off-session action for {symbol}")
    if set(group["date"]).intersection(dates):
        raise CorporateActionError(f"off-session action has an existing price row for {symbol}")
    return sorted(events, key=lambda event: event["effective_date"])


def _dates(values: Any) -> pd.DatetimeIndex:
    try:
        dates = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
        if dates.tz is not None:
            dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
        dates = dates.normalize()
    except (TypeError, ValueError) as exc:
        raise CorporateActionError("invalid corporate-action session date") from exc
    if dates.isna().any():
        raise CorporateActionError("missing corporate-action session date")
    return dates


def _historical_actions(group: pd.DataFrame, basis: pd.Timestamp) -> list[dict[str, Any]]:
    events = [
        {"effective_date": f"{row.date:%Y-%m-%d}", "ratio": float(row.split_ratio)}
        for row in group[group["split_ratio"].ne(0)].itertuples()
        if row.date <= basis
    ]
    events.extend(
        {"effective_date": f"{event['effective_date']:%Y-%m-%d}", "ratio": event["ratio"]}
        for event in _off_session_events(group) if event["effective_date"] <= basis
    )
    return sorted(events, key=lambda event: event["effective_date"])


def _numeric(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise CorporateActionError(f"non-finite {column} in corporate-action source")


def _validate_adjusted_boundary(group: pd.DataFrame, external: list[dict[str, Any]] | None = None) -> None:
    """Reject a known action whose source appears to retain the nominal jump.

    A price move cannot prove its cause.  This check therefore stops an ambiguous
    source; it never invents an action or silently rescales a genuine price move.
    Small-ratio actions are still handled by their declared factors.
    """
    events = [
        {"effective_date": row.date, "ratio": row.split_ratio}
        for row in group[group["split_ratio"].ne(0)].itertuples()
    ] + list(external or [])
    for event in events:
        ratio = float(event["ratio"])
        date = pd.Timestamp(event["effective_date"])
        previous = group[group["date"].lt(date)]
        following = group[group["date"].ge(date)]
        if previous.empty or following.empty or 0.8 < ratio < 1.25:
            continue
        if "source_usable" in group and (
            not bool(previous.iloc[-1]["source_usable"])
            or not bool(following.iloc[0]["source_usable"])
        ):
            continue
        observed = float(following.iloc[0]["open"]) / float(previous.iloc[-1]["close"])
        if min(abs(observed * ratio - 1.0), abs(observed / ratio - 1.0)) <= 0.08 and abs(observed - 1.0) > 0.12:
            raise CorporateActionError(
                "ambiguous/unadjusted split boundary: "
                f"{group.iloc[0]['symbol']} {date:%Y-%m-%d}; "
                "review declared action and provider OHLC before scoring"
            )


def _ambiguous_repair_boundary(group: pd.DataFrame, events: list[dict[str, Any]]) -> bool:
    """A marked repair must not introduce a split-sized discontinuity.

    Both action boundaries and transitions into/out of a repaired segment are
    checked against declared events. This is evidence for quarantine only, never
    an inferred multiplier with which to repair prices.
    """
    good = group[group["source_usable"]]
    if len(good) < 2 or not good["provider_repaired"].any():
        return False
    declared = [float(event["ratio"]) for event in events if event["ratio"] <= 0.8 or event["ratio"] >= 1.25]
    flags = good["provider_repaired"].to_numpy(dtype=bool)
    positions = set((np.flatnonzero(flags[1:] != flags[:-1]) + 1).tolist())
    dates = pd.DatetimeIndex(good["date"])
    positions.update(int(dates.searchsorted(event["effective_date"])) for event in events)
    for position in sorted(positions):
        if position <= 0 or position >= len(good):
            continue
        left, right = good.iloc[position - 1], good.iloc[position]
        observed = float(right["open"]) / float(left["close"])
        if abs(observed - 1.0) <= 0.12:
            continue
        if any(min(abs(observed * ratio - 1), abs(observed / ratio - 1)) <= 0.08 for ratio in declared):
            return True
    return False


from .progress import recorded_phase


@recorded_phase('corporate-action-normalization')
def normalize_daily(
    frame: pd.DataFrame,
    *,
    basis_asof: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Validate Yahoo split-adjusted rows and add contemporaneous OHLCV units.

    ``split_ratio`` is new shares per old share, with zero meaning no event.
    Its effective date is the row's exchange session. ``split_factor`` multiplies
    only events strictly AFTER a row, so an event-day row is already in its new
    units.  Reapplying this function verifies existing derived columns instead of
    adjusting them again.  A legacy corpus with no action metadata must be fetched
    again with actions enabled; a zero-event assumption is not a safe migration.
    """
    required = {"symbol", "date", *OHLC, "volume", "split_ratio"}
    missing = required.difference(frame.columns)
    if missing:
        raise CorporateActionError(
            f"missing split-aware daily columns {sorted(missing)}; use --refresh-live"
        )
    result = frame.copy()
    if result.empty:
        for column in (*ACTUAL_COLUMNS, *BASIS_COLUMNS):
            if column not in result:
                result[column] = pd.Series(dtype="object")
        return result
    result["symbol"] = result["symbol"].astype(str).str.strip()
    valid_symbols = result["symbol"].str.fullmatch(r"[0-9A-Z]{4}")
    if not valid_symbols.all():
        invalid_symbols = result.loc[~valid_symbols, "symbol"]
        samples = [
            {"code": code} if len(code) <= 12 else {"length": len(code), "type": type(code).__name__}
            for code in invalid_symbols.head(5)
        ]
        raise CorporateActionError(
            f"invalid symbol in corporate-action source: invalid_count={len(invalid_symbols)}; "
            f"samples={json.dumps(samples, ensure_ascii=True)}"
        )
    result["date"] = _dates(result["date"])
    if result.duplicated(["symbol", "date"]).any():
        raise CorporateActionError("duplicate symbol/session in corporate-action source")
    result = result.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    if "provider_repaired" not in result:
        result["provider_repaired"] = False
    repaired = result["provider_repaired"].astype(str).str.lower().map({"true": True, "false": False})
    if repaired.isna().any():
        raise CorporateActionError("invalid provider repair flag")
    result["provider_repaired"] = repaired
    _numeric(result, (*OHLC, "volume", "split_ratio"))
    if (result[list(OHLC)] <= 0).any().any() or (result["volume"] < 0).any():
        raise CorporateActionError("non-positive price or negative share volume")
    if (result["split_ratio"] < 0).any():
        raise CorporateActionError("split ratio must be positive, or zero for no event")
    tolerance = result["high"].abs() * 1e-6
    invalid_ohlc = (
        (result["low"] > result["high"] + tolerance)
        | (result["open"] < result["low"] - tolerance)
        | (result["open"] > result["high"] + tolerance)
        | (result["close"] < result["low"] - tolerance)
        | (result["close"] > result["high"] + tolerance)
    )
    # Preserve the vendor bar and its action instead of inventing a repaired
    # range or deleting a session. Downstream scoring masks these untrusted bars
    # and the affected lookback/outcome windows; other symbols can continue.
    source_usable = ~invalid_ohlc
    source_issue = pd.Series("", index=result.index, dtype="object")
    source_issue.loc[invalid_ohlc] = "inconsistent_ohlc"

    existing_derived = set(ACTUAL_COLUMNS).intersection(result.columns)
    existing_basis = set(BASIS_COLUMNS).difference({"split_ratio", "off_session_actions", "provider_repaired"}).intersection(result.columns)
    enriched = bool(existing_derived or existing_basis)
    if enriched:
        expected = set(ACTUAL_COLUMNS).union(BASIS_COLUMNS)
        missing = expected.difference(result.columns)
        if missing:
            raise CorporateActionError(f"incomplete corporate-action basis metadata: {sorted(missing)}")
        for column, value in (
            ("price_basis", PRICE_BASIS),
            ("corporate_actions_version", VERSION),
            ("corporate_actions_source", ACTION_SOURCE),
        ):
            matches = result[column].eq(value).fillna(False)
            if not matches.all():
                sample = result.iloc[np.flatnonzero(~matches.to_numpy())[:5]][["symbol", "date", column]].astype(str).to_dict("records")
                raise CorporateActionError(
                    f"unsupported {column}; refusing double adjustment; "
                    f"invalid_rows={int((~matches).sum())}, expected={value!r}, sample={json.dumps(sample)}"
                )
        _numeric(result, (*ACTUAL_COLUMNS, "split_factor"))
        result["basis_asof"] = _dates(result["basis_asof"])
        saved_quality = result["source_usable"].astype(str).str.lower().map({"true": True, "false": False})
        saved_issue = result["source_issue"].fillna("").copy()

    explicit_basis = _dates([basis_asof])[0] if basis_asof is not None else None
    factors = np.empty(len(result), dtype=float)
    snapshot_dates = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns]")
    off_session_values = pd.Series("", index=result.index, dtype="object")
    for symbol, group in result.groupby("symbol", sort=False):
        external = _off_session_events(group)
        last_event = max((event["effective_date"] for event in external), default=group["date"].max())
        snapshot = explicit_basis or max(group["date"].max(), last_event)
        if enriched:
            snapshots = group["basis_asof"].unique()
            if len(snapshots) != 1:
                raise CorporateActionError(f"mixed snapshot bases for {symbol}")
            snapshot = pd.Timestamp(snapshots[0])
            if explicit_basis is not None and explicit_basis != snapshot:
                raise CorporateActionError(f"cannot change existing snapshot basis for {symbol}")
        if max(group["date"].max(), last_event) > snapshot:
            raise CorporateActionError(f"OHLCV/action after declared snapshot for {symbol}")
        all_events = [
            {"effective_date": row.date, "ratio": row.split_ratio}
            for row in group[group["split_ratio"].ne(0)].itertuples()
        ] + external
        for event in all_events:
            if event["ratio"] >= 1e-4:
                continue
            before_event = group.loc[group["date"].lt(event["effective_date"]), "date"]
            after_event = group.loc[group["date"].ge(event["effective_date"]), "date"]
            if not before_event.empty and not after_event.empty and (
                after_event.iloc[0] - before_event.iloc[-1]
            ).days >= 180:
                # A squeeze-out followed by a long absence and resumed quotes
                # cannot establish the same security identity from ticker alone.
                source_usable.loc[group.index] = False
                source_issue.loc[group.index] = "ambiguous_security_identity_after_consolidation"
        group = group.copy()
        group["source_usable"] = source_usable.loc[group.index]
        if _ambiguous_repair_boundary(group, all_events):
            source_usable.loc[group.index] = False
            source_issue.loc[group.index] = "ambiguous_provider_repair_basis"
            group["source_usable"] = False
        _validate_adjusted_boundary(group, external)
        ratios = group["split_ratio"].mask(group["split_ratio"].eq(0), 1.0).to_numpy(dtype=float)
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            future = np.cumprod(ratios[::-1])[::-1] / ratios
            for event in external:
                future[group["date"].lt(event["effective_date"]).to_numpy()] *= event["ratio"]
        if not np.isfinite(future).all() or (future <= 0).any():
            raise CorporateActionError(f"invalid cumulative split factor for {symbol}")
        factors[group.index] = future
        snapshot_dates.loc[group.index] = snapshot
        if external:
            off_session_values.at[group.index[-1]] = json.dumps([
                {"effective_date": f"{event['effective_date']:%Y-%m-%d}", "ratio": event["ratio"], "source": event["source"]}
                for event in external
            ], separators=(",", ":"))
    if enriched and not np.allclose(result["split_factor"], factors, rtol=1e-12, atol=1e-12):
        raise CorporateActionError("stored split factor disagrees with declared events")
    ambiguous_volume = repaired & (factors < 1e-4) & source_usable
    source_usable.loc[ambiguous_volume] = False
    source_issue.loc[ambiguous_volume] = "ambiguous_repaired_volume_basis"
    # A cross-snapshot repair discrepancy is evidence of uncertainty, not a new
    # volume estimate. Verify the retained evidence on every cache read before
    # masking the original vendor bar from features and outcomes.
    if REVISION_EVIDENCE in result:
        evidence_values = result[REVISION_EVIDENCE].fillna("").astype(str)
        groups = {symbol: group for symbol, group in result.groupby("symbol", sort=False)}
        for position in evidence_values.index[evidence_values.ne("")]:
            row = result.loc[position]
            try:
                evidence = json.loads(evidence_values.at[position])
                prior_basis = _dates([evidence["previousBasis"]])[0]
                current_volume = float(row.volume) / factors[position]
                previous_volume = float(evidence["previousActualVolume"])
                previous_prices = np.array([evidence["previousActualOHLC"][name] for name in OHLC], dtype=float)
                current_prices = row[list(OHLC)].to_numpy(dtype=float) * factors[position]
                valid = (
                    evidence["identity"] == "CLOUD_REPAIRED_VOLUME_QUARANTINE_V1"
                    and evidence["symbol"] == row.symbol
                    and evidence["date"] == f"{row.date:%Y-%m-%d}"
                    and row.date < prior_basis <= snapshot_dates.at[position]
                    and bool(row.provider_repaired) and evidence["previousProviderRepaired"] is True
                    and np.isfinite(previous_volume) and previous_volume >= 0
                    and np.isfinite(previous_prices).all()
                    and np.isclose(previous_prices, current_prices, rtol=0, atol=1e-8).all()
                    and not np.isclose(previous_volume, current_volume, rtol=0.05, atol=1e-6)
                    and np.isclose(evidence["currentActualVolume"], current_volume, rtol=1e-9, atol=1e-6)
                    and evidence["historicalActions"] == _historical_actions(groups[row.symbol], prior_basis)
                )
                if not valid:
                    raise ValueError("evidence does not match the provider bar")
            except (KeyError, TypeError, ValueError) as exc:
                raise CorporateActionError(f"invalid repaired-volume revision evidence: {row.symbol} {row.date:%Y-%m-%d}") from exc
            if source_usable.at[position]:
                source_usable.at[position] = False
                source_issue.at[position] = REVISION_ISSUE
        result[REVISION_EVIDENCE] = evidence_values
    # JPX hold integration: verify full original symbol rows before
    # deriving usability. A stored boolean alone never authorizes quarantine.
    from .jpx_holds import COLUMN as JPX_HOLD, ISSUE as JPX_ISSUE, verify as verify_jpx_hold
    if JPX_HOLD in result:
        for symbol, group in result.groupby("symbol", sort=False):
            try:
                hold = verify_jpx_hold(group)
            except (ValueError, KeyError, TypeError) as exc:
                raise CorporateActionError(f"invalid JPX symbol hold evidence: {symbol}") from exc
            if hold:
                source_issue.loc[group.index[source_usable.loc[group.index]]] = JPX_ISSUE
                source_usable.loc[group.index] = False
    from .endpoint_holds import COLUMN as ENDPOINT_HOLD, ISSUE as ENDPOINT_ISSUE, verify as verify_endpoint_hold
    if ENDPOINT_HOLD in result:
        for symbol, group in result.groupby("symbol", sort=False):
            try:
                hold = verify_endpoint_hold(group)
            except (ValueError, KeyError, TypeError) as exc:
                raise CorporateActionError(f"invalid endpoint symbol hold evidence: {symbol}") from exc
            if hold:
                source_issue.loc[group.index[source_usable.loc[group.index]]] = ENDPOINT_ISSUE
                source_usable.loc[group.index] = False
    if enriched:
        if saved_quality.isna().any() or not saved_quality.eq(source_usable).all():
            raise CorporateActionError("stored source_usable disagrees with provider evidence")
        if not saved_issue.eq(source_issue).all():
            raise CorporateActionError("stored source_issue disagrees with provider evidence")
    for column in OHLC:
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            values = result[column] * factors
        if not np.isfinite(values.to_numpy(dtype=float)).all() or (values <= 0).any():
            raise CorporateActionError(f"invalid reconstructed actual_{column}")
        if enriched and not np.allclose(result[f"actual_{column}"], values, rtol=1e-9, atol=1e-8):
            raise CorporateActionError(f"stored actual_{column} has already been adjusted or changed")
        result[f"actual_{column}"] = values
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        actual_volume = result["volume"] / factors
    if not np.isfinite(actual_volume.to_numpy(dtype=float)).all():
        raise CorporateActionError("invalid reconstructed actual_volume")
    if enriched and not np.allclose(result["actual_volume"], actual_volume, rtol=1e-9, atol=1e-6):
        raise CorporateActionError("stored actual_volume disagrees with declared events")
    result["actual_volume"] = actual_volume
    result["split_factor"] = factors
    result["basis_asof"] = snapshot_dates
    result["price_basis"] = PRICE_BASIS
    result["corporate_actions_version"] = VERSION
    result["corporate_actions_source"] = ACTION_SOURCE
    result["off_session_actions"] = off_session_values
    result["source_usable"] = source_usable
    result["source_issue"] = source_issue
    return result


def source_quality_audit(frame: pd.DataFrame) -> pd.DataFrame:
    """Explain locally quarantined source bars without correcting their values."""
    verified = normalize_daily(frame)
    rejected = verified[~verified["source_usable"]].copy()
    columns = ["symbol", "date", "source_issue", *OHLC, "volume", "split_ratio", "split_factor", "provider_repaired"]
    if REVISION_EVIDENCE in verified:
        columns.append(REVISION_EVIDENCE)
    if rejected.empty:
        return rejected.reindex(columns=[*columns, "error_yen", "error_ratio"])
    rejected["error_yen"] = pd.concat([
        rejected[["open", "close"]].max(axis=1) - rejected["high"],
        rejected["low"] - rejected[["open", "close"]].min(axis=1),
        rejected["low"] - rejected["high"],
    ], axis=1).max(axis=1).clip(lower=0)
    rejected["error_ratio"] = rejected["error_yen"] / rejected["high"].abs()
    return rejected.reindex(columns=[*columns, "error_yen", "error_ratio"])


def source_quality_receipt(frame: pd.DataFrame) -> dict[str, Any]:
    """JSON-safe explanation of retained but unusable provider bars."""
    audit = source_quality_audit(frame)
    audit["date"] = pd.to_datetime(audit["date"]).dt.strftime("%Y-%m-%d")
    return {
        "identity": "CLOUD_SOURCE_QUALITY_V1",
        "sourceRows": int(len(frame)),
        "quarantinedRows": int(len(audit)),
        "quarantinedSymbols": sorted(audit["symbol"].astype(str).unique().tolist()),
        "quarantinedDates": {str(date): int(count) for date, count in audit.groupby("date").size().items()},
        "issues": audit.to_dict(orient="records"),
    }


def action_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the verified daily action journal, including reverse splits."""
    verified = normalize_daily(frame)
    events = verified[verified["split_ratio"].ne(0)].copy()
    events = events.rename(columns={"date": "effective_date", "split_ratio": "ratio"})
    events["source"] = ACTION_SOURCE
    parts = [events.reindex(columns=ACTION_COLUMNS)]
    for _, group in verified.groupby("symbol", sort=False):
        external = _off_session_events(group)
        if external:
            detached = pd.DataFrame(external)
            detached["basis_asof"] = group["basis_asof"].iloc[0]
            parts.append(detached.reindex(columns=ACTION_COLUMNS))
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "effective_date"]).reset_index(drop=True)


@recorded_phase('corporate-action-volume-revision')
def quarantine_repaired_volume_revisions(
    previous: pd.DataFrame, current: pd.DataFrame, *, previous_source_sha256: str | None = None,
) -> pd.DataFrame:
    """Retain, audit and exclude unstable historical reconstructed volumes.

    Only two provider-marked repairs with identical actual OHLC and an unchanged
    historical action journal qualify. The ordinary revision validator remains
    strict. Never select either volume as the corrected historical value.
    One separately reviewed, byte-pinned transition may bypass carried handling
    after all of its original/new endpoints and provenance have been verified.
    """
    from .reviewed_repair_releases import reviewed_repair_release_keys

    if previous_source_sha256 is None:
        previous_source_sha256 = previous.attrs.get("source_sha256")
    if previous.empty or "corporate_actions_version" not in previous:
        # A matching identity must not opt out through missing old metadata.
        reviewed_repair_release_keys(previous, current, previous_source_sha256=previous_source_sha256)
        return current
    original_previous, original_current = previous, current
    previous = normalize_daily(previous)
    result = normalize_daily(current)
    released_keys, release_audit = reviewed_repair_release_keys(
        previous, result, previous_source_sha256=previous_source_sha256,
    )
    if released_keys:
        # normalize_daily deliberately allows tiny reconstruction differences.
        # This reviewed fingerprint does not: check the original inputs too.
        for original, normalized in ((original_previous, previous), (original_current, result)):
            numeric_fields = (*OHLC, "volume", *ACTUAL_COLUMNS, "split_factor", "split_ratio")
            if not set(numeric_fields).issubset(original.columns):
                raise CorporateActionError("reviewed repair release mismatch: missing original numeric metadata")
            original_rows = original.loc[original.symbol.astype(str).str.strip().eq("523A")].copy()
            for field, expected in (
                ("price_basis", PRICE_BASIS), ("corporate_actions_source", ACTION_SOURCE),
                ("corporate_actions_version", VERSION),
            ):
                if original_rows[field].isna().any() or not original_rows[field].eq(expected).all():
                    raise CorporateActionError(f"reviewed repair release mismatch: original {field}")
            original_rows["date"] = _dates(original_rows.date)
            original_rows = original_rows.set_index("date")
            normalized_rows = normalized.loc[normalized.symbol.eq("523A")].set_index("date")
            for symbol, date in released_keys:
                before, after = original_rows.loc[date], normalized_rows.loc[date]
                for field in numeric_fields:
                    if isinstance(before[field], (bool, np.bool_)) or before[field] != after[field]:
                        raise CorporateActionError(f"reviewed repair release mismatch: original {symbol} {date:%Y-%m-%d} {field}")
    if REVISION_EVIDENCE not in result:
        result[REVISION_EVIDENCE] = ""
    old_groups = {symbol: group for symbol, group in previous.groupby("symbol", sort=False)}
    for symbol, group in result.groupby("symbol", sort=False):
        old = old_groups.get(symbol)
        if old is None:
            continue
        prior_basis = old.basis_asof.max()
        old_rows = old.set_index("date")
        prior_volume = group.date.map(old_rows.actual_volume)
        changed_volume = ~np.isclose(prior_volume, group.actual_volume, rtol=0.05, atol=1e-6)
        carried_dates = old.loc[
            old.get(REVISION_EVIDENCE, pd.Series("", index=old.index)).fillna("").ne(""), "date"
        ]
        candidates = (group.provider_repaired & changed_volume) | group.date.isin(carried_dates)
        for position in group.index[candidates]:
            row = result.loc[position]
            if (str(symbol), row.date) in released_keys:
                continue
            if row.date not in old_rows.index or row.date >= prior_basis:
                continue
            before = old_rows.loc[row.date]
            saved = before.get(REVISION_EVIDENCE, "")
            carried = bool(pd.notna(saved) and str(saved).strip())
            if not bool(before.provider_repaired) or (not bool(before.source_usable) and not carried):
                continue
            evidence = json.loads(saved) if carried else {
                "identity": "CLOUD_REPAIRED_VOLUME_QUARANTINE_V1", "symbol": str(symbol),
                "date": f"{row.date:%Y-%m-%d}", "previousBasis": f"{prior_basis:%Y-%m-%d}",
                "previousProviderRepaired": True, "previousActualVolume": float(before.actual_volume),
                "previousActualOHLC": {name: float(before[f"actual_{name}"]) for name in OHLC},
                "historicalActions": _historical_actions(old, prior_basis),
            }
            basis = pd.Timestamp(evidence["previousBasis"])
            same_prices = all(np.isclose(evidence["previousActualOHLC"][name], row[f"actual_{name}"], rtol=0, atol=1e-8) for name in OHLC)
            same_actions = evidence["historicalActions"] == _historical_actions(group, basis)
            if carried and (not same_prices or not same_actions):
                raise CorporateActionError(f"quarantined repair changed price/action evidence: {symbol} {row.date:%Y-%m-%d}")
            if not bool(row.provider_repaired) or not same_prices or not same_actions or not bool(row.source_usable):
                continue
            if np.isclose(evidence["previousActualVolume"], row.actual_volume, rtol=0.05, atol=1e-6):
                continue
            evidence["currentActualVolume"] = float(row.actual_volume)
            result.at[position, REVISION_EVIDENCE] = json.dumps(evidence, separators=(",", ":"))
            result.at[position, "source_usable"] = False
            result.at[position, "source_issue"] = REVISION_ISSUE
    result = normalize_daily(result)
    # Do not rely on pandas propagating attrs through final normalization.
    result.attrs["reviewedRepairReleases"] = release_audit
    return result


@recorded_phase('corporate-action-source-revision')
def validate_source_revision(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    *,
    previous_source_sha256: str | None = None,
    source_corrections_manifest: dict[str, Any] | None = None,
    collect_unexplained: bool = False,
    confirmed_new: dict | None = None,
) -> dict[str, Any]:
    """Reject missing actions and unexplained historical share-unit revisions.

    For a legacy snapshot, only declared actions newly effective AFTER its last
    session can explain a provider-wide rebase.  For a verified snapshot, actual
    historical OHLCV must remain stable. Small provider corrections are tolerated.
    A repaired bar on the previous snapshot's final session can
    settle to an unrepaired positive-volume bar in a later snapshot only when its
    actual OHLC meets the existing price tolerance and its historical action
    journal is unchanged. Audit that narrow
    completion separately; larger unexplained changes still require review.
    """
    receipt: dict[str, Any] = {
        "identity": "CLOUD_SOURCE_REVISION_V1", "previousBasis": "none",
        "comparedRows": 0, "quarantinedComparisonRows": 0,
        "acceptedRepairColumnValues": 0, "acceptedRepairs": [],
        "quarantinedComparisons": [],
        "sourceCorrectionAudit": [],
    }
    # Capture file identity before copies/normalization can discard attrs.
    if previous_source_sha256 is None:
        previous_source_sha256 = previous.attrs.get("source_sha256")
    if previous.empty:
        return receipt
    current = normalize_daily(current)
    required = {"symbol", "date", *OHLC, "volume"}
    if not required.issubset(previous.columns):
        raise CorporateActionError("previous daily corpus cannot verify a source revision")
    previous = previous.copy()
    previous["symbol"] = previous["symbol"].astype(str)
    previous["date"] = _dates(previous["date"])
    if previous.duplicated(["symbol", "date"]).any():
        raise CorporateActionError("duplicate rows in previous corporate-action snapshot")
    _numeric(previous, (*OHLC, "volume"))
    legacy_tolerance = previous["high"].abs() * 1e-6
    previous_usable = (
        (previous["low"] <= previous["high"] + legacy_tolerance)
        & (previous["open"] >= previous["low"] - legacy_tolerance)
        & (previous["open"] <= previous["high"] + legacy_tolerance)
        & (previous["close"] >= previous["low"] - legacy_tolerance)
        & (previous["close"] <= previous["high"] + legacy_tolerance)
    )
    previous["_revision_source_usable"] = previous_usable
    enriched = "corporate_actions_version" in previous
    receipt["previousBasis"] = "verified" if enriched else "legacy_unverified"
    legacy_snapshot = previous["date"].max()
    current_events = action_table(current)
    if enriched:
        previous = normalize_daily(previous)
        old_events = action_table(previous).set_index(["symbol", "effective_date"])
        new_events = current_events.set_index(["symbol", "effective_date"])
        for identity, event in old_events.iterrows():
            symbol, effective = identity
            now = current[current["symbol"].eq(symbol)]
            if now.empty or not now["date"].min() <= effective <= now["basis_asof"].max():
                continue
            if identity not in new_events.index or not np.isclose(
                event["ratio"], new_events.at[identity, "ratio"], rtol=1e-12, atol=0
            ):
                raise CorporateActionError(f"previously recorded split event was removed/revised: {identity}")

    from .source_corrections import reviewed_comparison_overrides

    comparison_overrides, correction_audit = reviewed_comparison_overrides(
        previous, current,
        previous_source_sha256=previous_source_sha256,
        manifest=source_corrections_manifest,
    )
    receipt["sourceCorrectionAudit"] = correction_audit
    old_groups = {symbol: group for symbol, group in previous.groupby("symbol", sort=False)}
    for symbol, now in current.groupby("symbol", sort=False):
        old = old_groups.get(symbol)
        if old is None:
            continue
        # A stale/delisted ticker can have no quotes after a corporate action.
        # The legacy download still already reflects actions through the corpus
        # snapshot, not merely through that ticker's last trading session.
        old_basis = old["basis_asof"].max() if enriched else legacy_snapshot
        if now["basis_asof"].max() < old_basis:
            raise CorporateActionError(f"source snapshot moved backwards for {symbol}")
        common = old.set_index("date").index.intersection(now.set_index("date").index)
        if common.empty:
            continue
        left = old.set_index("date").loc[common]
        right = now.set_index("date").loc[common]
        # Quarantined bars are retained for the audit and calendar but cannot
        # substantiate a price-basis revision or an execution price.
        good = right["source_usable"].to_numpy(dtype=bool)
        if enriched:
            good &= left["source_usable"].to_numpy(dtype=bool)
        else:
            good &= left["_revision_source_usable"].to_numpy(dtype=bool)
        receipt["comparedRows"] += int(good.sum())
        receipt["quarantinedComparisonRows"] += int((~good).sum())
        if not good.all():
            receipt["quarantinedComparisons"].append({
                "symbol": str(symbol), "rows": int((~good).sum()),
                "currentIssues": right.iloc[np.flatnonzero(~good)]["source_issue"].value_counts().to_dict(),
                "firstDate": f"{common[~good].min():%Y-%m-%d}",
                "lastDate": f"{common[~good].max():%Y-%m-%d}",
            })
        left = left.iloc[np.flatnonzero(good)]
        right = right.iloc[np.flatnonzero(good)]
        if left.empty:
            continue
        new_ratios = current_events.loc[
            current_events["symbol"].eq(symbol) & current_events["effective_date"].gt(old_basis), "ratio"
        ]
        additional_factor = float(new_ratios.prod())
        # Only legacy downloads used repair=False. A single migration can admit
        # a provider-marked repair whose exact price multiplier is a declared
        # event or its reciprocal. Verified snapshots retain strict comparison.
        repair_price_scale = np.ones(len(right), dtype=float)
        repair_eligible = np.zeros(len(right), dtype=bool)
        symbol_events = current_events[current_events["symbol"].eq(symbol)]
        if not enriched:
            expected_prices = left[list(OHLC)].to_numpy(dtype=float) / additional_factor
            scale = right[list(OHLC)].to_numpy(dtype=float) / expected_prices
            repair_price_scale = scale[:, 0]
            coherent = np.isclose(scale, repair_price_scale[:, None], rtol=1e-6, atol=1e-9).all(axis=1)
            declared = symbol_events.loc[symbol_events["effective_date"].le(old_basis), "ratio"].to_numpy(dtype=float)
            matching = np.zeros(len(right), dtype=bool)
            for ratio in declared:
                matching |= np.isclose(repair_price_scale, ratio, rtol=1e-6, atol=1e-9)
                matching |= np.isclose(repair_price_scale, 1.0 / ratio, rtol=1e-6, atol=1e-9)
            repair_eligible = coherent & matching & right["provider_repaired"].to_numpy(dtype=bool)
        for column in (*OHLC, "volume"):
            if enriched:
                # Overrides exist only in this private comparison array. The
                # normalized frames retain their original, consistent bases.
                before = left[f"actual_{column}"].to_numpy(dtype=float, copy=True)
                for (reviewed_symbol, session), correction in comparison_overrides.items():
                    if reviewed_symbol == str(symbol) and session in left.index:
                        before[left.index.get_loc(session)] = correction[f"actual_{column}"]
                after = right[f"actual_{column}"].to_numpy(dtype=float)
            else:
                before = left[column].to_numpy(dtype=float)
                expected_scale = additional_factor if column == "volume" else 1.0 / additional_factor
                before = before * expected_scale
                after = right[column].to_numpy(dtype=float)
            relative_tolerance = 0.05 if column == "volume" else 0.03
            different = ~np.isclose(before, after, rtol=relative_tolerance, atol=1e-6)
            accepted = different & repair_eligible
            if column == "volume":
                accepted &= np.isclose(after, before / repair_price_scale, rtol=1e-6, atol=1e-6)
            settled = np.zeros(len(right), dtype=bool)
            if enriched and column == "volume":
                old_prices = left[[f"actual_{name}" for name in OHLC]].to_numpy(dtype=float)
                new_prices = right[[f"actual_{name}" for name in OHLC]].to_numpy(dtype=float)
                historical_actions_unchanged = all(
                    (symbol, event.effective_date) in old_events.index
                    for event in symbol_events.itertuples()
                    if event.effective_date <= old_basis
                )
                settled = (
                    different & historical_actions_unchanged
                    & (right.index == old_basis)
                    & right["basis_asof"].gt(old_basis).to_numpy(dtype=bool)
                    & left["provider_repaired"].to_numpy(dtype=bool)
                    & ~right["provider_repaired"].to_numpy(dtype=bool)
                    & (after > 0)
                    & np.isclose(old_prices, new_prices, rtol=0.03, atol=1e-6).all(axis=1)
                )
            unexplained = different & ~(accepted | settled)
            if unexplained.any():
                for position in np.flatnonzero(unexplained):
                    key = (str(symbol), f"{right.index[position]:%Y-%m-%d}", column)
                    confirmation = (confirmed_new or {}).get(key)
                    if confirmation is not None:
                        # Internal resolver's official byte-verified decision. Never a
                        # boolean override. Endpoint mismatches fail closed.
                        from .jpx_decisions import decide
                        decision = decide(*key, before[position], after[position], confirmation)
                        if decision["decision"] != "accept_new":
                            raise CorporateActionError("JPX new confirmation endpoint mismatch")
                        receipt.setdefault("jpxConfirmedNew", []).append(decision)
                        continue
                    if collect_unexplained:
                        receipt.setdefault("unexplainedCells", []).append({
                            "symbol": key[0], "session": key[1], "field": column,
                            "old": float(before[position]), "new": float(after[position]),
                        })
                    else:
                        raise CorporateActionError(
                            f"unexplained historical {column} revision for {symbol} "
                            f"{right.index[position]:%Y-%m-%d}: {before[position]} -> {after[position]}; "
                            "missing/corrected action or provider repair requires review"
                        )
            if accepted.any():
                receipt["acceptedRepairColumnValues"] += int(accepted.sum())
                receipt["acceptedRepairs"].append({
                    "symbol": str(symbol), "column": column, "rows": int(accepted.sum()),
                    "reason": "legacy_provider_repair_matching_declared_split",
                    "firstDate": f"{right.index[accepted].min():%Y-%m-%d}",
                    "lastDate": f"{right.index[accepted].max():%Y-%m-%d}",
                    "priceMultipliers": sorted(set(repair_price_scale[accepted].round(9).tolist())),
                    "declaredEvents": [
                        {"effective_date": f"{event.effective_date:%Y-%m-%d}", "ratio": float(event.ratio)}
                        for event in symbol_events.itertuples()
                    ],
                    "differences": [
                        {"date": f"{right.index[i]:%Y-%m-%d}", "previousExpected": float(before[i]), "current": float(after[i])}
                        for i in np.flatnonzero(accepted)
                    ],
                })
            if settled.any():
                receipt["acceptedRepairColumnValues"] += int(settled.sum())
                receipt["acceptedRepairs"].append({
                    "symbol": str(symbol), "column": "volume", "rows": int(settled.sum()),
                    "reason": "latest_repaired_bar_settled_by_unrepaired_bar",
                    "firstDate": f"{right.index[settled].min():%Y-%m-%d}",
                    "lastDate": f"{right.index[settled].max():%Y-%m-%d}",
                    "previousBasis": f"{old_basis:%Y-%m-%d}",
                    "currentBasis": f"{right['basis_asof'].max():%Y-%m-%d}",
                    "differences": [{
                        "date": f"{right.index[i]:%Y-%m-%d}",
                        "previousExpected": float(before[i]), "current": float(after[i]),
                        "previousProviderRepaired": True, "currentProviderRepaired": False,
                        "previousActualOHLC": dict(zip(OHLC, old_prices[i].tolist())),
                        "currentActualOHLC": dict(zip(OHLC, new_prices[i].tolist())),
                    } for i in np.flatnonzero(settled)],
                })
    return receipt


def _ticker_source(data: pd.DataFrame | None, ticker: str, *, single: bool) -> pd.DataFrame:
    """Keep ticker identity when unpacking a possibly partial batch response."""
    if data is None:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0):
            source = data[ticker].copy()
        elif ticker in data.columns.get_level_values(1):
            source = data.xs(ticker, axis=1, level=1).copy()
        else:
            return pd.DataFrame()
    elif single or data.empty:
        source = data.copy()
    else:
        raise CorporateActionError("Yahoo multi-symbol response lost ticker identity")
    return source.rename(columns={column: str(column).strip().lower().replace(" ", "_") for column in source})


def _source_problem(source: pd.DataFrame) -> str | None:
    if "stock_splits" not in source:
        return "did not return split actions"
    missing = set([*OHLC, "volume"]).difference(source.columns)
    if missing:
        return f"incomplete daily bars: {sorted(missing)}"
    priced = source[list(OHLC)].notna().any(axis=1)
    if source.loc[priced, "stock_splits"].isna().any():
        return "did not return split actions for priced sessions"
    if source.empty or (
        source[list(OHLC)].isna().all().all()
        and not source["stock_splits"].fillna(0).ne(0).any()
    ):
        return "returned no usable daily bars"
    return None


def _provider_errors(yf: Any) -> dict:
    # yfinance 0.2.66 swallows transport exceptions in download/history and
    # stores their original representation here. Keep this diagnostic only;
    # success still requires the actual bars and explicit action evidence.
    errors = getattr(getattr(yf, "shared", None), "_ERRORS", None)
    return errors if isinstance(errors, dict) else {}


def _retry_ticker(yf: Any, ticker: str, period: str, *, archive: AcquisitionArchive | None = None) -> pd.DataFrame:
    """Retry only failed tickers, retaining repaired daily bars and split evidence.

    yfinance.download forces raise_errors=True. A missing intraday series used
    by its repair routine can therefore discard otherwise valid daily history.
    history(raise_errors=False) retains those daily rows; empty or incomplete
    responses still fail here, and normal source-quality/revision gates follow.
    """
    problem = "returned no usable daily bars"
    last_error = None
    for attempt in range(3):
        last_error = None
        _provider_errors(yf).pop(ticker.upper(), None)
        try:
            kwargs = dict(period=period, interval="1d", auto_adjust=False,
                          actions=True, repair=True, raise_errors=False, timeout=30)
            operation = lambda: yf.Ticker(ticker).history(**kwargs)
            response = (archive.request({"kind": "history", "ticker": ticker, "kwargs": kwargs},
                                        operation, lambda: _provider_errors(yf)) if archive else operation())
            source = _ticker_source(response, ticker, single=True)
            problem = _source_problem(source)
            if problem is None:
                return source
        except Exception as exc:
            if not transient_network_error(exc):
                raise CorporateActionError(f"Yahoo daily history request failed for {ticker}: {exc}") from exc
            last_error = exc
        else:
            provider_error = _provider_errors(yf).get(ticker.upper())
            if provider_error:
                last_error = provider_error
                if permanent_network_error(provider_error):
                    raise CorporateActionError(
                        f"Yahoo daily history request failed for {ticker}: {provider_error}"
                    ) from RuntimeError(str(provider_error))
        if attempt < 2 and not (archive and archive.replay):
            time.sleep(2 ** attempt)
    if last_error is not None and transient_network_error(last_error):
        cause = last_error if isinstance(last_error, BaseException) else RuntimeError(str(last_error))
        raise CorporateActionError(
            f"Yahoo daily transport request failed for {ticker} after 3 individual attempts: {last_error}; "
            f"last response: {problem}"
        ) from cause
    if last_error is not None:
        cause = last_error if isinstance(last_error, BaseException) else RuntimeError(str(last_error))
        raise CorporateActionError(
            f"Yahoo {problem} for {ticker} after 3 individual attempts: {last_error}"
        ) from cause
    raise CorporateActionError(f"Yahoo {problem} for {ticker} after 3 individual attempts")


def fetch_daily(
    universe: pd.DataFrame,
    period: str,
    batch: int = 80,
    *,
    previous: pd.DataFrame | None = None,
    archive: AcquisitionArchive | None = None,
) -> pd.DataFrame:
    """Fetch Cloud daily bars with actions, without changing legacy research IO."""
    import yfinance as yf

    if batch <= 0:
        raise ValueError("batch must be positive")
    previous_source_sha256 = (
        previous.attrs.get("source_sha256") if previous is not None else None
    )
    tickers = universe["ticker"].astype(str).tolist()
    rows: list[pd.DataFrame] = []
    provider_snapshot = pd.NaT
    for offset in range(0, len(tickers), batch):
        part = tickers[offset:offset + batch]
        data = None
        batch_error = None
        for attempt in range(3):
            batch_error = None
            for ticker in part:
                _provider_errors(yf).pop(ticker.upper(), None)
            try:
                kwargs = dict(period=period, interval="1d", group_by="ticker", auto_adjust=False,
                              actions=True, repair=True, threads=True, progress=False, timeout=30)
                operation = lambda: yf.download(part, **kwargs)
                data = (archive.request({"kind": "batch", "tickers": part, "kwargs": kwargs},
                                        operation, lambda: _provider_errors(yf)) if archive else operation())
                errors = _provider_errors(yf)
                failures = [errors.get(ticker.upper()) for ticker in part]
                for failure in failures:
                    if failure and permanent_network_error(failure):
                        raise CorporateActionError(f"Yahoo batch daily request failed: {failure}") from RuntimeError(str(failure))
                if data is not None and not data.empty:
                    break
                if failures and all(failure and transient_network_error(failure) for failure in failures):
                    batch_error = RuntimeError("; ".join(dict.fromkeys(str(failure) for failure in failures)))
            except Exception as exc:
                if not transient_network_error(exc):
                    raise CorporateActionError(f"Yahoo batch daily request failed: {exc}") from exc
                batch_error = exc
                data = None
            if attempt < 2 and not (archive and archive.replay):
                time.sleep(2 ** attempt)
        if (data is None or data.empty) and batch_error is not None:
            raise CorporateActionError(
                f"Yahoo batch daily transport request failed after 3 attempts: {batch_error}"
            ) from batch_error
        for ticker in part:
            source = _ticker_source(data, ticker, single=len(part) == 1)
            if _source_problem(source) is not None:
                source = _retry_ticker(yf, ticker, period, archive=archive)
            required = [*OHLC, "volume", "stock_splits"]
            if "repaired?" in source:
                source["provider_repaired"] = source["repaired?"].fillna(False)
            else:
                source["provider_repaired"] = False
            no_prices = source[list(OHLC)].isna().all(axis=1)
            dates = _dates(source.index)
            provider_snapshot = max(provider_snapshot, dates.max()) if pd.notna(provider_snapshot) else dates.max()
            detached_events = []
            for position in np.flatnonzero((no_prices & source["stock_splits"].fillna(0).ne(0)).to_numpy()):
                detached_events.append({"effective_date": f"{dates[position]:%Y-%m-%d}", "ratio": float(source.iloc[position]["stock_splits"]), "source": ACTION_SOURCE})
            source = source.loc[~no_prices, [*required, "provider_repaired"]].copy()
            if source.empty:
                if detached_events:
                    raise CorporateActionError(f"action-only ticker has no price history to establish a basis: {ticker}")
                continue
            source["date"] = _dates(source.index)
            source["symbol"] = ticker.removesuffix(".T")
            source = source.rename(columns={"stock_splits": "split_ratio"})
            source["off_session_actions"] = ""
            if detached_events:
                source.at[source.index[-1], "off_session_actions"] = json.dumps(detached_events, separators=(",", ":"))
            rows.append(source.reset_index(drop=True))
    if not rows:
        raise CorporateActionError("Yahoo returned no split-aware daily rows")
    from .reviewed_off_session_actions import retain_reviewed_off_session_actions

    raw, retained_actions = retain_reviewed_off_session_actions(
        previous, pd.concat(rows, ignore_index=True), basis_asof=provider_snapshot,
    )
    from .reviewed_provider_restorations import (
        restore_reviewed_november_quotes,
        restore_reviewed_provider_values,
    )

    raw, provider_restorations = restore_reviewed_provider_values(
        previous, raw, basis_asof=provider_snapshot, archive=archive,
    )
    raw, november_restorations = restore_reviewed_november_quotes(
        previous, raw, basis_asof=provider_snapshot, archive=archive,
    )
    normalized = normalize_daily(raw, basis_asof=provider_snapshot)
    if previous is not None:
        normalized = quarantine_repaired_volume_revisions(
            previous, normalized, previous_source_sha256=previous_source_sha256,
        )
        release_audit = normalized.attrs.get("reviewedRepairReleases", [])
        from .jpx_holds import carry as carry_jpx_holds, audit as audit_jpx_holds
        try:
            normalized = carry_jpx_holds(previous, normalized, archive=archive)
        except ValueError as exc:
            raise CorporateActionError(str(exc)) from exc
        try:
            revision = validate_source_revision(
                previous, normalized, previous_source_sha256=previous_source_sha256,
            )
        except CorporateActionError as exc:
            # Only the established historical numeric-revision failure qualifies.
            # Missing/changed actions, invalid identities, or corrupt data remain
            # systemic hard failures. No daily runner retry or notification here.
            if not str(exc).startswith("unexplained historical ") or archive is None:
                raise
            from .jpx_reports import load as load_jpx_reports
            from .jpx_resolver import resolve as resolve_jpx_revisions
            pending = validate_source_revision(
                previous, normalized, previous_source_sha256=previous_source_sha256,
                collect_unexplained=True,
            )
            evidence, failures = load_jpx_reports(pending.get("unexplainedCells", []), archive)
            normalized, revision = resolve_jpx_revisions(
                previous, normalized, evidence=evidence,
                previous_source_sha256=previous_source_sha256, archive=archive,
            )
            revision["jpxEvidenceFailures"] = failures
        normalized.attrs["source_revision_receipt"] = revision
        normalized.attrs["source_revision_receipt"]["jpxHolds"] = audit_jpx_holds(normalized)
        normalized.attrs["source_revision_receipt"]["reviewedRepairReleases"] = release_audit
        normalized.attrs["source_revision_receipt"]["retainedOffSessionActions"] = retained_actions
        normalized.attrs["source_revision_receipt"]["reviewedProviderRestorations"] = provider_restorations
        if november_restorations:
            normalized.attrs["source_revision_receipt"]["reviewedNovember9Restorations"] = november_restorations
    return normalized




