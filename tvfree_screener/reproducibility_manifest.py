#!/usr/bin/env python3
"""Create a test-only reproducibility manifest for fixed-start TV-free research.

The manifest records dataset coverage, current JPX universe, historical OHLCV
and model-output fingerprints, plus a research-code/configuration fingerprint.
Later append-only runs can compare these values and distinguish source/universe
drift from semantic changes.

This tool does not write to production systems.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

OUT = Path("tvfree_screener/out")
CUTOFF = pd.Timestamp("2026-08-31")
FILES = [
    "v3_short_reconstruction_core.csv",
    "v3_short_reconstruction_defensive.csv",
    "v3_swing_v2_s_picks.csv",
    "v3_short_2024_extension_core.csv",
    "v3_short_2024_extension_defensive.csv",
    "v3_swing_2024_extension_s.csv",
    "v4_event_quality_locked_pre2026.csv",
]
CODE_FILES = [
    "tvfree_screener/run.py",
    "tvfree_screener/bootstrap.py",
    "tvfree_screener/v3_short_reconstruction.py",
    "tvfree_screener/v3_swing_v2.py",
    "tvfree_screener/v3_pre2026_extension.py",
    "tvfree_screener/v4_event_quality_research.py",
    "tvfree_screener/v4_event_quality_selftest.py",
    "tvfree_screener/unified_comparison.py",
    "tvfree_screener/reproducibility_manifest.py",
    "tvfree_screener/reproducibility_selftest.py",
    "tvfree_screener/fixed_baseline_run80.json",
    "tvfree_screener/fixed_baseline_guard.py",
    "tvfree_screener/fixed_baseline_guard_selftest.py",
    "tvfree_screener/causality_selftest.py",
    "tvfree_screener/point_in_time_universe.py",
    "tvfree_screener/point_in_time_universe_selftest.py",
    "tvfree_screener/delisted_price_coverage.py",
    "tvfree_screener/delisted_price_coverage_selftest.py",
    "tvfree_screener/fundamental_overlay.py",
    "tvfree_screener/fundamental_overlay_selftest.py",
    "tvfree_screener/fundamental_overlay_evaluator.py",
    "tvfree_screener/fundamental_overlay_evaluator_selftest.py",
    "tvfree_screener/edinet_fundamental_collector.py",
    "tvfree_screener/edinet_fundamental_collector_selftest.py",
    "tvfree_screener/edinet_dilution_audit.py",
    "tvfree_screener/edinet_dilution_audit_selftest.py",
    "tvfree_screener/requirements.txt",
    ".github/workflows/tvfree-screener-test.yml",
]
CONFIG_ENV = [
    "TVFREE_PERIOD",
    "TVFREE_START_DATE",
    "TVFREE_PRICE_CAP",
    "TVFREE_LOSS_PENALTY",
    "TVFREE_TOPK",
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(path: Path, cutoff: pd.Timestamp) -> dict:
    if not path.exists():
        return {"exists": False}
    df = pd.read_csv(path, dtype={"symbol": str})
    if "date" not in df.columns:
        return {"exists": True, "rows": int(len(df)), "historical_hash": None, "note": "no date column"}
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    hist = df[df["date"] <= cutoff].copy()
    sort_cols = [c for c in ["date", "symbol", "model_period"] if c in hist.columns]
    if sort_cols:
        hist = hist.sort_values(sort_cols, kind="mergesort")
    payload = hist.to_csv(index=False, lineterminator="\n", float_format="%.12g").encode("utf-8")
    return {
        "exists": True,
        "rows": int(len(df)),
        "historical_rows": int(len(hist)),
        "historical_cutoff": cutoff.strftime("%Y-%m-%d"),
        "historical_sha256": sha256_bytes(payload),
        "min_date": None if df["date"].dropna().empty else df["date"].min().strftime("%Y-%m-%d"),
        "max_date": None if df["date"].dropna().empty else df["date"].max().strftime("%Y-%m-%d"),
    }


def universe_manifest(path: Path) -> dict:
    """Fingerprint the exact current-listed JPX universe used by this run."""
    if not path.exists():
        return {"exists": False}
    cols = ["code", "name", "market", "ticker"]
    df = pd.read_csv(path, dtype=str)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return {"exists": True, "rows": int(len(df)), "sha256": None, "missing_columns": missing}
    z = df[cols].fillna("").sort_values(["code", "ticker"], kind="mergesort").reset_index(drop=True)
    payload = z.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return {
        "exists": True,
        "rows": int(len(z)),
        "sha256": sha256_bytes(payload),
        "policy": "run-date JPX domestic common-stock universe",
        "warning": (
            "Historical research currently uses the run-date listed universe. "
            "Listings/delistings can therefore change historical backtest membership; "
            "a universe-hash mismatch must not be treated as pure append-only market-data drift."
        ),
    }


def cache_manifest(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    cols = ["date", "symbol", "open", "high", "low", "close", "volume"]
    df = pd.read_csv(path, usecols=cols, dtype={"symbol": str})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    valid = df.dropna(subset=["date"])
    hist = valid[valid["date"] <= CUTOFF].sort_values(["date", "symbol"], kind="mergesort")
    coverage_payload = hist[["date", "symbol"]].to_csv(index=False, lineterminator="\n").encode("utf-8")
    ohlcv_payload = hist[cols].to_csv(index=False, lineterminator="\n", float_format="%.12g").encode("utf-8")
    return {
        "exists": True,
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "min_date": None if valid.empty else valid["date"].min().strftime("%Y-%m-%d"),
        "max_date": None if valid.empty else valid["date"].max().strftime("%Y-%m-%d"),
        "historical_cutoff": CUTOFF.strftime("%Y-%m-%d"),
        "historical_rows": int(len(hist)),
        "historical_date_symbol_sha256": sha256_bytes(coverage_payload),
        "historical_ohlcv_sha256": sha256_bytes(ohlcv_payload),
        "fixed_start_contract": "2022-01-01 -> current; symbols listed later naturally start later",
    }


def research_contract_manifest() -> dict:
    """Fingerprint test research semantics without reading or exposing secrets."""
    file_hashes = {}
    aggregate = hashlib.sha256()
    for name in CODE_FILES:
        path = Path(name)
        if not path.exists():
            file_hashes[name] = None
            aggregate.update(f"{name}\0MISSING\n".encode("utf-8"))
            continue
        payload = path.read_bytes()
        digest = sha256_bytes(payload)
        file_hashes[name] = digest
        aggregate.update(f"{name}\0{digest}\n".encode("utf-8"))

    config = {name: os.environ.get(name) for name in CONFIG_ENV}
    config_payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    config_sha = sha256_bytes(config_payload)
    aggregate.update(b"CONFIG\0" + config_sha.encode("ascii") + b"\n")

    return {
        "code_files_sha256": file_hashes,
        "safe_config": config,
        "safe_config_sha256": config_sha,
        "research_contract_sha256": aggregate.hexdigest(),
        "note": "Only explicit non-secret TVFREE_* research inputs are captured; code hashes cover frozen model semantics and reproducibility/causality/universe/fundamental-overlay/EDINET-ingestion/dilution-audit checks.",
    }


def main() -> None:
    report = {
        "manifest_version": 3,
        "status": "research_only_no_production_writes",
        "purpose": "append-only reproducibility fingerprint with universe-drift detection",
        "universe": universe_manifest(OUT / "jpx_universe_snapshot.csv"),
        "cache": cache_manifest(OUT / "tse_daily.csv"),
        "outputs": {name: canonical_hash(OUT / name, CUTOFF) for name in FILES},
        "research_contract": research_contract_manifest(),
        "interpretation": (
            "For append-only verification, first require the research_contract_sha256 and universe sha256 to match. "
            "Then historical date/symbol coverage, OHLCV, and output hashes should remain unchanged. "
            "A contract mismatch means code/config changed; a universe mismatch means current-listed membership changed; "
            "an OHLCV-only mismatch with matching contract/universe/coverage can indicate Yahoo historical revision."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "reproducibility_manifest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
