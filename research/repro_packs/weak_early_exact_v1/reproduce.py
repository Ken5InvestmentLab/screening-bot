#!/usr/bin/env python3
"""Reproduce the preserved Weak+Early legacy rank comparison exactly.

This is research-only.  It never reads 2026 outcomes and never mutates production.
The replay starts from the contemporaneous preserved causal V7 Tail artifact so
that XGBoost/runtime drift cannot change the historical candidate identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


IDENTITY = "WEAK_EARLY_EXACT_V1"
TAIL_SHA256 = "0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d"
DAILY_SHA256 = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
RET10_MAX = 0.5735294117647058
START = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2025-12-31")

RANKERS = {
    "volr20_low": "volr20",
    "body_pct_low": "body_pct",
    "mean_rank_volr20_body_pct": "mean_rank",
}

DUAL_NAME = "dual_top1_agreement"
DUAL_G3_NAME = "dual_top1_agreement_g3_no_acute_selloff"
G3_MED_RET1_MIN = -0.01

EXPECTED_DEV = {
    "volr20_low": {"n": 128, "mean_pct": 6.239403543533105, "median_pct": 1.064960900249695},
    "body_pct_low": {"n": 128, "mean_pct": 6.461068512693746, "median_pct": 1.25435483964363},
    "mean_rank_volr20_body_pct": {"n": 128, "mean_pct": 7.1635478562729835, "median_pct": 1.808791736728315},
}
EXPECTED_2025_MEAN_PCT = {
    "volr20_low": 6.58,
    "body_pct_low": 6.78,
    "mean_rank_volr20_body_pct": 6.09,
}

EXPECTED_STRUCTURAL = {
    DUAL_NAME: {
        "development_2023_2024": {
            "n": 103,
            "mean_pct": 6.88,
            "median_pct": 1.39,
            "win_pct": 53.40,
            "top3_ex_mean_pct": 3.86,
        },
        "year_2025": {
            "n": 37,
            "mean_pct": 7.97,
            "median_pct": -2.40,
            "win_pct": 48.65,
            "top3_ex_mean_pct": -0.06,
        },
        "aggregate_2023_2025": {
            "n": 140,
            "mean_pct": 7.17,
            "median_pct": 1.25,
            "win_pct": 52.14,
            "top3_ex_mean_pct": 4.79,
        },
    },
    DUAL_G3_NAME: {
        "development_2023_2024": {
            "n": 83,
            "mean_pct": 7.38,
            "median_pct": 1.74,
            "win_pct": 55.42,
            "top3_ex_mean_pct": 3.62,
        },
        "year_2025": {
            "n": 34,
            "mean_pct": 9.43,
            "median_pct": 0.37,
            "win_pct": 50.00,
            "top3_ex_mean_pct": 0.77,
        },
        "aggregate_2023_2025": {
            "n": 117,
            "mean_pct": 7.98,
            "median_pct": 1.74,
            "win_pct": 53.85,
            "top3_ex_mean_pct": 5.14,
        },
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"input SHA mismatch: {path}: {actual} != {expected}")


def metrics(frame: pd.DataFrame) -> dict[str, Any]:
    returns = pd.to_numeric(frame["gross_return"], errors="raise")
    ranked = returns.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n": int(len(frame)),
        "mean_pct": float(returns.mean() * 100),
        "median_pct": float(returns.median() * 100),
        "win_pct": float((returns > 0).mean() * 100),
        "plus10_pct": float((returns >= 0.10).mean() * 100),
        "plus20_pct": float((returns >= 0.20).mean() * 100),
        "plus50_pct": float((returns >= 0.50).mean() * 100),
        "minus10_pct": float((returns <= -0.10).mean() * 100),
        "minus20_pct": float((returns <= -0.20).mean() * 100),
        "max_up_pct": float(returns.max() * 100),
        "max_down_pct": float(returns.min() * 100),
        "top1_ex_mean_pct": float(ranked.iloc[1:].mean() * 100) if len(ranked) > 1 else None,
        "top3_ex_mean_pct": float(ranked.iloc[3:].mean() * 100) if len(ranked) > 3 else None,
        "one_hundred_shares_pl_yen": float(frame["one_hundred_shares_pl_yen"].sum()),
    }


def choose_one_per_day(pool: pd.DataFrame, key: str) -> pd.DataFrame:
    ordered = pool.sort_values(
        ["date", key, "tail_cdf"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    unresolved = 0
    for _, day in ordered.groupby("date", sort=True):
        best = day.iloc[0]
        unresolved += int(
            ((day[key] == best[key]) & (day["tail_cdf"] == best["tail_cdf"])).sum() > 1
        )
    if unresolved:
        raise RuntimeError(f"{key}: {unresolved} top ties remain after exact Tail-CDF tie-break")
    return ordered.groupby("date", sort=True, as_index=False).head(1).copy()


def load_required_daily_rows(daily_path: Path, symbols: set[str]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        daily_path,
        dtype={"symbol": str},
        parse_dates=["date"],
        usecols=["date", "symbol", "open", "close"],
        chunksize=250_000,
    ):
        keep = chunk[
            chunk["symbol"].isin(symbols)
            & chunk["date"].between("2022-12-01", "2026-01-31")
        ]
        if not keep.empty:
            parts.append(keep)
    if not parts:
        raise RuntimeError("no endpoint rows found in daily corpus")
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"])


def load_xtks_calendar(daily_path: Path) -> pd.DatetimeIndex:
    sessions: set[pd.Timestamp] = set()
    for chunk in pd.read_csv(
        daily_path,
        parse_dates=["date"],
        usecols=["date"],
        chunksize=500_000,
    ):
        sessions.update(pd.Timestamp(value) for value in chunk["date"].dropna().unique())
    if not sessions:
        raise RuntimeError("XTKS session calendar is empty")
    return pd.DatetimeIndex(sorted(sessions))


def attach_canonical_endpoint(
    picks: pd.DataFrame,
    daily: pd.DataFrame,
    xtks_calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = {symbol: frame for symbol, frame in daily.groupby("symbol", sort=False)}
    for row in picks.itertuples(index=False):
        symbol = str(row.symbol)
        future = grouped[symbol].loc[grouped[symbol]["date"] > row.date].sort_values("date")
        if len(future) < 5:
            raise RuntimeError(f"endpoint missing for {row.date:%Y-%m-%d}|{symbol}")
        entry = future.iloc[0]
        exit_row = future.iloc[4]
        gross = float(exit_row["close"] / entry["open"] - 1.0)
        official_future = xtks_calendar[xtks_calendar > row.date]
        if len(official_future) < 5:
            raise RuntimeError(f"official XTKS endpoint missing for {row.date:%Y-%m-%d}|{symbol}")
        if pd.Timestamp(entry["date"]) != official_future[0]:
            raise RuntimeError(f"next XTKS session mismatch for {row.date:%Y-%m-%d}|{symbol}")
        if pd.Timestamp(exit_row["date"]) != official_future[4]:
            raise RuntimeError(f"fifth XTKS session mismatch for {row.date:%Y-%m-%d}|{symbol}")
        if pd.Timestamp(exit_row["date"]) != pd.Timestamp(row.target_end_date):
            raise RuntimeError(f"target_end_date mismatch for {row.date:%Y-%m-%d}|{symbol}")
        if not np.isclose(float(entry["open"]), float(row.next_open), rtol=0, atol=1e-10):
            raise RuntimeError(f"entry open mismatch for {row.date:%Y-%m-%d}|{symbol}")
        if not np.isclose(gross, float(row.target5_no), rtol=0, atol=1e-10):
            raise RuntimeError(f"gross return mismatch for {row.date:%Y-%m-%d}|{symbol}")
        item = row._asdict()
        item.update(
            {
                "candidate_id": f"{row.date:%Y-%m-%d}|{symbol}|{row.model_period}",
                "signal_date": row.date,
                "entry_date": pd.Timestamp(entry["date"]),
                "entry_open": float(entry["open"]),
                "fifth_xtks_exit_date": pd.Timestamp(exit_row["date"]),
                "fifth_xtks_exit_close": float(exit_row["close"]),
                "gross_return": gross,
                "one_hundred_shares_pl_yen": float((exit_row["close"] - entry["open"]) * 100),
            }
        )
        rows.append(item)
    output = pd.DataFrame(rows)
    columns = [
        "signal_date",
        "symbol",
        "candidate_id",
        "model_period",
        "entry_date",
        "entry_open",
        "fifth_xtks_exit_date",
        "fifth_xtks_exit_close",
        "gross_return",
        "one_hundred_shares_pl_yen",
        "med_ret5",
        "ret10",
        "volr20",
        "body_pct",
        "rank_volr20",
        "rank_body_pct",
        "mean_rank",
        "tail_cdf",
        "tail_p",
    ]
    return output[columns].sort_values(["signal_date", "symbol"]).reset_index(drop=True)


def assert_historical_identity(name: str, rows: pd.DataFrame) -> None:
    development = rows[rows["signal_date"] < "2025-01-01"]
    expected = EXPECTED_DEV[name]
    if len(development) != expected["n"]:
        raise RuntimeError(f"{name}: development n drift")
    for field in ("mean_pct", "median_pct"):
        actual = metrics(development)[field]
        if not np.isclose(actual, expected[field], rtol=0, atol=1e-12):
            raise RuntimeError(f"{name}: {field} drift: {actual} != {expected[field]}")
    year_2025 = rows[rows["signal_date"].dt.year == 2025]
    if len(year_2025) != 44:
        raise RuntimeError(f"{name}: 2025 n drift")
    if round(metrics(year_2025)["mean_pct"], 2) != EXPECTED_2025_MEAN_PCT[name]:
        raise RuntimeError(f"{name}: 2025 mean drift")


def assert_structural_identity(name: str, rows: pd.DataFrame) -> None:
    frames = {
        "development_2023_2024": rows[rows["signal_date"] < "2025-01-01"],
        "year_2025": rows[rows["signal_date"].dt.year == 2025],
        "aggregate_2023_2025": rows,
    }
    for period, frame in frames.items():
        actual = metrics(frame)
        for field, expected in EXPECTED_STRUCTURAL[name][period].items():
            if field == "n":
                if actual[field] != expected:
                    raise RuntimeError(f"{name}: {period} {field} drift")
            elif round(actual[field], 2) != expected:
                raise RuntimeError(
                    f"{name}: {period} {field} drift: {actual[field]} != {expected}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail-cache", type=Path, required=True)
    parser.add_argument("--daily-corpus", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    require_sha(args.tail_cache, TAIL_SHA256)
    require_sha(args.daily_corpus, DAILY_SHA256)

    tail = pd.read_csv(
        args.tail_cache,
        dtype={"symbol": str},
        parse_dates=["date", "target_end_date"],
    )
    if len(tail) != 1306:
        raise RuntimeError(f"preserved Tail row-count drift: {len(tail)} != 1306")
    pool = tail[
        tail["date"].between(START, END)
        & (tail["med_ret5"] <= 0)
        & (tail["ret10"] <= RET10_MAX)
    ].copy()
    pool["rank_volr20"] = pool.groupby("date")["volr20"].rank(
        pct=True, method="average", ascending=True
    )
    pool["rank_body_pct"] = pool.groupby("date")["body_pct"].rank(
        pct=True, method="average", ascending=True
    )
    pool["mean_rank"] = pool[["rank_volr20", "rank_body_pct"]].mean(axis=1)

    selected = {name: choose_one_per_day(pool, key) for name, key in RANKERS.items()}
    agreement_ids = selected["volr20_low"][["date", "symbol"]].merge(
        selected["body_pct_low"][["date", "symbol"]],
        on=["date", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    dual = pool.merge(
        agreement_ids,
        on=["date", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    selected[DUAL_NAME] = dual
    selected[DUAL_G3_NAME] = dual[dual["med_ret1"] >= G3_MED_RET1_MIN].copy()
    symbols = set(pd.concat(selected.values(), ignore_index=True)["symbol"].astype(str))
    daily = load_required_daily_rows(args.daily_corpus, symbols)
    xtks_calendar = load_xtks_calendar(args.daily_corpus)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metric_report: dict[str, Any] = {
        "identity": IDENTITY,
        "cost_pct": 0,
        "win_definition": "gross_return > 0",
        "endpoint": "signal T -> next available official XTKS session open -> fifth official XTKS session close",
        "selectors": {},
    }
    output_hashes: dict[str, str] = {}

    for name, picks in selected.items():
        rows = attach_canonical_endpoint(picks, daily, xtks_calendar)
        if name in RANKERS:
            assert_historical_identity(name, rows)
        else:
            assert_structural_identity(name, rows)
        csv_path = args.output_dir / f"canonical_trade_rows_{name}.csv"
        rows.to_csv(
            csv_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            date_format="%Y-%m-%d",
            float_format="%.12g",
        )
        output_hashes[csv_path.name] = sha256(csv_path)
        metric_report["selectors"][name] = {
            "by_year": {
                str(year): metrics(rows[rows["signal_date"].dt.year == year])
                for year in (2023, 2024, 2025)
            },
            "development_2023_2024": metrics(rows[rows["signal_date"] < "2025-01-01"]),
            "aggregate_2023_2025": metrics(rows),
        }

    metrics_path = args.output_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metric_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_hashes[metrics_path.name] = sha256(metrics_path)

    manifest = {
        "identity": IDENTITY,
        "status": "EXACT_REPRODUCED_FROM_PRESERVED_CAUSAL_TAIL_ARTIFACT",
        "inputs": {
            "tail_cache": {
                "artifact_id": 10264251140,
                "source_run": 34600083474,
                "sha256": TAIL_SHA256,
            },
            "daily_corpus": {
                "artifact_id": 10264205130,
                "source_run": 34599959356,
                "original_source_run": 34545440155,
                "sha256": DAILY_SHA256,
            },
        },
        "rules": {
            "population": "preserved causal V7 Tail; tail_cdf >= 0.999 already materialized",
            "gate": f"med_ret5 <= 0 AND ret10 <= {RET10_MAX}",
            "selection": "one candidate per signal date",
            "rankers": RANKERS,
            "dual_top1_agreement": "select only dates where volr20 LOW Top1 and body_pct LOW Top1 are the same symbol; otherwise NO TRADE",
            "g3_no_acute_selloff": f"previous-session med_ret1 >= {G3_MED_RET1_MIN}",
            "tie_break": "tail_cdf descending",
            "cooldown": "none in the legacy n=128/n=44 rank comparison",
            "causal_training": "monthly; labels require target_end_date < month_start; minimum 30000 training rows",
            "universe": "fixed run-80 TSE daily corpus",
        },
        "rule_sources": {
            "dual_top1_agreement": {
                "commit": "4b37f18d7601f8fd6ff42155879faff5b7d1e9e3",
                "path": "research/WEAK_EARLY_PHASE2_20260914.md",
            },
            "g3_preregistration": {
                "commit": "bb7e9dcddcf1ff9e931f0e2f92925d6f761cf7e5",
                "path": "research/WEAK_EARLY_PHASE2_REGIME_PREREG_20260914.md",
            },
            "g3_frozen_selection": {
                "commit": "aed2690c5972edff99b0b06a26f8cb37b86165c1",
                "path": "research/WEAK_EARLY_PHASE2_REGIME_SELECTION_20260914.md",
            },
        },
        "outputs": output_hashes,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
