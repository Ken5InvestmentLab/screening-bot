"""Explicit read-only research-artifact reconciliation and endpoint backfill.

Run with ``python -B -m weak_early_beta.research_endpoint_backfill --help``.
Only new output files outside production state are permitted.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .endpoint_receipts import (
    ENDPOINT_COLUMNS, ENDPOINT_DATE_COLUMNS, ENDPOINT_NUMBER_COLUMNS, ENDPOINT_TEXT_COLUMNS,
    preserve_verified_endpoints, signal_actual_close_verified, sixth_endpoint_verified, sixth_economics_verified,
    endpoint_csv_frame,
)
from .research_price_receipts import (
    PRICE_PACKAGE_SHA256, MODE_PACKAGE_SHA256, PRICE_INPUT_SHA256, MODE_INPUT_SHA256,
    build_research_receipts, verify_research_trade, VERIFICATION_SCOPE,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_zip(path: Path, expected_sha256: str, manifest_name: str) -> tuple[dict[str, bytes], dict]:
    data = path.read_bytes()
    if digest(data) != expected_sha256:
        raise ValueError(f"research package SHA-256 mismatch: {path}")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or sum(info.file_size for info in archive.infolist()) > 25_000_000:
            raise ValueError("duplicate ZIP member or research archive exceeds the expected size limit")
        members = {name: archive.read(name) for name in names}
    manifest = json.loads(members[manifest_name].decode("utf-8-sig"))
    if set(manifest) != set(members).difference({manifest_name}):
        raise ValueError("research ZIP manifest/member set mismatch")
    for name, expected in manifest.items():
        if len(members[name]) != expected["bytes"] or digest(members[name]) != expected["sha256"]:
            raise ValueError(f"research member checksum mismatch: {name}")
    return members, {"path": str(path), "bytes": len(data), "sha256": digest(data),
                     "manifest_sha256": digest(members[manifest_name]), "members_verified": len(manifest)}


def _identity(record: dict) -> str:
    return f"{record['signal_date']}|{record['symbol']}"


def _indexed(records: list[dict]) -> dict[str, tuple[int, dict]]:
    result = {}
    for index, record in enumerate(records):
        key = _identity(record)
        if key in result:
            raise ValueError(f"duplicate research identity: {key}")
        result[key] = (index, record)
    return result


def validate_research_inputs(prices: dict, compact: dict, results: dict) -> dict:
    """Reconcile both artifacts and repeat the economic checks without executing their scripts."""
    quotes = _indexed(prices["prices"])
    if len(quotes) != 253 or set(compact["signal_prices"]) != set(quotes):
        raise ValueError("pinned research signal universe is not the expected 253 identities")
    for key, (_, record) in quotes.items():
        if record["signal_usable"] is not True or not math.isfinite(float(record["signal_close"])) or record["signal_close"] <= 0:
            raise ValueError(f"unusable research signal quote: {key}")
        if record["signal_close"] != compact["signal_prices"][key]:
            raise ValueError(f"research nominal signal close mismatch: {key}")
    all_trades = {}
    peer_counts = {}
    for endpoint in ("BASE5", "OPEN6"):
        merged = {}
        for stage in ("DEV", "EVAL"):
            for key, (index, record) in _indexed(prices["controls"][stage][endpoint]).items():
                if key in merged or stage != ("DEV" if int(record["signal_year"]) <= 2025 else "EVAL"):
                    raise ValueError(f"duplicate or misclassified research trade: {key}")
                verify_research_trade(record, endpoint=endpoint)
                merged[key] = (index, record)
        if set(merged) != set(quotes):
            raise ValueError(f"{endpoint} records do not cover the price evidence universe")
        peers = _indexed(compact["baseline_ledgers"][endpoint])
        expected_peers = {key for key, (_, record) in quotes.items() if record["signal_close"] <= 1000}
        if set(peers) != expected_peers:
            raise ValueError("the mode-study overlap is not exactly its documented signal-price cap")
        for key, (_, record) in peers.items():
            if record != merged[key][1]:
                raise ValueError(f"cross-package {endpoint} trade mismatch: {key}")
        peer_counts[endpoint] = len(peers)
        all_trades[endpoint] = merged
    for key in quotes:
        fifth = all_trades["BASE5"][key][1]
        sixth = all_trades["OPEN6"][key][1]
        if any(fifth[field] != sixth[field] for field in ("entry_date", "entry_price", "entry_shares", "entry_cost_yen")):
            raise ValueError(f"entry basis differs between research endpoints: {key}")
        if [action for action in sixth["applied_actions"] if action["effective_date"] <= fifth["exit_date"]] != fifth["applied_actions"]:
            raise ValueError(f"D5/D6 research holding-action prefix mismatch: {key}")
    metric_checks = 0
    for metric in results["metrics"]:
        trades = prices["controls"][metric["stage"]][metric["exit"]]
        selected = []
        for trade in trades:
            if metric["group"] not in ("DEV", "EVAL") and str(trade["signal_year"]) != metric["group"]:
                continue
            quote = quotes[_identity(trade)][1]
            signal = quote["signal_usable"] and 0 < quote["signal_close"] <= 1000
            previous = quote["previous_usable"] and 0 < quote["previous_close"] <= 1000
            if {"none": True, "signal": signal, "previous": previous, "both": signal and previous}[metric["policy"]]:
                selected.append(trade)
        events, profits = {}, []
        for trade in selected:
            cost = Decimal(str(trade["entry_price"])) * Decimal(str(trade["entry_shares"]))
            sale = Decimal(str(trade["exit_price"])) * Decimal(str(trade["exit_shares"]))
            profits.append(sale - cost)
            for key, amount in (((trade["entry_date"], 0), -cost), ((trade["exit_date"], 1), sale)):
                events[key] = events.get(key, Decimal(0)) + amount
        cash = required = Decimal(0)
        for _, amount in sorted(events.items()):
            cash += amount
            required = max(required, -cash)
        calculated = {"price_pl_yen": sum(profits, Decimal(0)), "min_cash_yen": required,
                      "losing_sum_yen": sum((amount for amount in profits if amount < 0), Decimal(0))}
        if len(selected) != metric["intents"] or any(abs(float(value) - metric[key]) > 1e-6 for key, value in calculated.items()):
            raise ValueError("independent research metric replay failed")
        metric_checks += 1
    if metric_checks != 48:
        raise ValueError("research metric replay did not cover all 48 published groups")
    return {"quotes": quotes, "trades": all_trades, "peer_counts": peer_counts, "metric_checks": metric_checks}


def reconcile_and_backfill(frame: pd.DataFrame, prices: dict, compact: dict, results: dict, *, observed_at: str) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    evidence = validate_research_inputs(prices, compact, results)
    if frame["detection_id"].duplicated().any():
        raise ValueError("input ledger has duplicate detection identities")
    mode_columns = ["signal_date", "symbol", "selector_id", "source_scope", "status"]
    reference_modes = {tuple(str(record[column]) for column in mode_columns) for record in compact["mode_rows"]}
    if len(reference_modes) != len(compact["mode_rows"]):
        raise ValueError("research mode records contain duplicate identities")
    ledger_keys = {f"{pd.Timestamp(row.signal_date):%Y-%m-%d}|{row.symbol}" for row in frame.itertuples()}
    result = frame.copy(deep=True)
    for column in ENDPOINT_COLUMNS:
        if column not in result:
            result[column] = pd.NaT if column in ENDPOINT_DATE_COLUMNS else (float("nan") if column in ENDPOINT_NUMBER_COLUMNS else "")
        elif column in ENDPOINT_TEXT_COLUMNS:
            result[column] = result[column].astype(object)
    coverage, changes = [], []
    for index, row in result.iterrows():
        key = f"{pd.Timestamp(row['signal_date']):%Y-%m-%d}|{row['symbol']}"
        row_key = tuple(str(row[column]) if column != "signal_date" else f"{pd.Timestamp(row[column]):%Y-%m-%d}" for column in mode_columns)
        record = {"detection_id": row["detection_id"], "signal_date": f"{pd.Timestamp(row['signal_date']):%Y-%m-%d}",
                  "symbol": str(row["symbol"]), "selector_id": row["selector_id"], "source_scope": row["source_scope"],
                  "research_identity_present": key in evidence["quotes"], "research_mode_matches": row_key in reference_modes,
                  "coverage": "missing_research_price", "endpoint_peer_scope": ""}
        if key in evidence["quotes"] and row_key in reference_modes and str(row["source_scope"]).startswith("EXACT_CANONICAL"):
            price_index, quote = evidence["quotes"][key]
            trade_index, trade = evidence["trades"]["OPEN6"][key]
            new = build_research_receipts(row, quote, trade, price_index=price_index, trade_index=trade_index,
                                         peer_close=compact["signal_prices"][key], observed_at=observed_at)
            preserved = preserve_verified_endpoints(row, {**dict(row), **new})
            changed = []
            for column in ENDPOINT_COLUMNS:
                prior, value = row.get(column), preserved.get(column)
                same = (pd.isna(prior) and pd.isna(value)) or (pd.notna(prior) and pd.notna(value) and prior == value)
                if not same:
                    result.at[index, column] = value
                    changed.append(column)
            if changed:
                changes.append({"detection_id": str(row["detection_id"]), "columns": changed})
            record.update({"coverage": "verified_research_receipts" if sixth_economics_verified(preserved) else "review_required",
                           "endpoint_peer_scope": "two_artifacts_exact_trade_match" if quote["signal_close"] <= 1000 else "comparison_nocap_record_and_independent_replay",
                           "verified_signal_close": float(quote["signal_close"]), "verified_d6_open": float(trade["exit_price"]),
                           "holding_action_count": len(trade["applied_actions"])})
        elif key in evidence["quotes"]:
            record["coverage"] = "mode_or_source_scope_mismatch"
        coverage.append(record)
    old_columns = [column for column in frame.columns if column not in ENDPOINT_COLUMNS]
    pd.testing.assert_frame_equal(result[old_columns], frame[old_columns])
    rows = pd.DataFrame(coverage)
    audit = {
        "schema": "CLOUD_PINNED_RESEARCH_ENDPOINT_BACKFILL_V1", "observed_at": observed_at,
        "verification_scope": VERIFICATION_SCOPE, "raw_market_refetched": False,
        "ledger_rows": len(frame), "ledger_unique_signals": len(ledger_keys),
        "research_mode_rows": len(compact["mode_rows"]), "research_unique_prices": len(evidence["quotes"]),
        "identity_overlap": len(ledger_keys & set(evidence["quotes"])),
        "ledger_only_identities": sorted(ledger_keys - set(evidence["quotes"])),
        "research_only_identities": sorted(set(evidence["quotes"]) - ledger_keys),
        "coverage_rows": dict(Counter(rows.coverage)),
        "peer_endpoint_records": evidence["peer_counts"], "decimal_metric_groups_replayed": evidence["metric_checks"],
        "individual_trade_records_replayed": sum(len(records) for records in evidence["trades"].values()),
        "research_date_range": [min(record[1]["signal_date"] for record in evidence["quotes"].values()), max(record[1]["signal_date"] for record in evidence["quotes"].values())],
        "ledger_date_range": [str(frame.signal_date.min()), str(frame.signal_date.max())],
        "known_2026_is_historical_reuse": True, "changed_rows": len(changes), "changes": changes,
        "non_endpoint_columns_unchanged": True, "canonical_upsert_protection_changed": False,
        "d5_economics_modified": False, "production_state_modified": False, "notifications_sent": 0,
        "verified_signal_rows": int(result.apply(signal_actual_close_verified, axis=1).sum()),
        "verified_d6_price_rows": int(result.apply(sixth_endpoint_verified, axis=1).sum()),
        "verified_d6_economics_rows": int(result.apply(sixth_economics_verified, axis=1).sum()),
    }
    return result, audit, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("ledger", "price-comparison-zip", "mode-research-zip", "output", "audit", "coverage"):
        parser.add_argument(f"--{flag}", required=True)
    args = parser.parse_args()
    inputs = [Path(value).resolve(strict=True) for value in (args.ledger, args.price_comparison_zip, args.mode_research_zip)]
    outputs = [Path(value).resolve() for value in (args.output, args.audit, args.coverage)]
    if len(set(inputs + outputs)) != 6:
        raise ValueError("all input and output paths must be distinct")
    for target in outputs:
        if target.exists() or target.is_relative_to((ROOT / "weak_early_beta" / "state").resolve()):
            raise ValueError(f"existing output or production-state write refused: {target}")
    comparison, comparison_receipt = verified_zip(inputs[1], PRICE_PACKAGE_SHA256, "manifest.json")
    mode, mode_receipt = verified_zip(inputs[2], MODE_PACKAGE_SHA256, "MANIFEST.json")
    compact_bytes = mode["legacy_mode_sizing_v1/compact_inputs.json"]
    if digest(comparison["inputs.json"]) != PRICE_INPUT_SHA256 or digest(compact_bytes) != MODE_INPUT_SHA256:
        raise ValueError("pinned research input member changed")
    ledger_bytes = inputs[0].read_bytes()
    frame = pd.read_csv(io.BytesIO(ledger_bytes), dtype={"symbol": str})
    revised, audit, coverage = reconcile_and_backfill(
        frame, json.loads(comparison["inputs.json"]), json.loads(compact_bytes), json.loads(comparison["results.json"]),
        observed_at=pd.Timestamp.now(tz="UTC").isoformat(),
    )
    csv_bytes = endpoint_csv_frame(revised).to_csv(index=False, lineterminator="\n", date_format="%Y-%m-%d", float_format="%.12g").encode("utf-8")
    restored = pd.read_csv(io.BytesIO(csv_bytes), dtype={"symbol": str})
    for label, verifier in (("signal", signal_actual_close_verified), ("d6_price", sixth_endpoint_verified),
                            ("d6_economics", sixth_economics_verified)):
        expected = revised.apply(verifier, axis=1).tolist()
        actual = restored.apply(verifier, axis=1).tolist()
        if actual != expected:
            raise ValueError(f"CSV serialization changed {label} verification; outputs were not written")
    audit["csv_readback_all_receipts_verified"] = True
    audit.update({"input_ledger": str(inputs[0]), "input_ledger_sha256": digest(ledger_bytes),
                  "source_packages": [comparison_receipt, mode_receipt],
                  "output_ledger": str(outputs[0]), "output_ledger_sha256": digest(csv_bytes)})
    contents = [csv_bytes, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), coverage.to_csv(index=False, lineterminator="\n").encode("utf-8")]
    created = []
    try:
        for target, data in zip(outputs, contents):
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                created.append(target)
                handle.write(data)
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    if inputs[0].read_bytes() != ledger_bytes:
        raise RuntimeError("input ledger changed concurrently; do not adopt these outputs")
    print(json.dumps({key: audit[key] for key in ("ledger_rows", "ledger_unique_signals", "research_unique_prices", "identity_overlap", "coverage_rows", "changed_rows", "verified_d6_price_rows", "output_ledger", "output_ledger_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
