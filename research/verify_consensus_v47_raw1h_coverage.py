from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PAIR_MIN = 0.995
MONTH_MIN = 0.990
SYMBOL_MIN = 0.950
RESTORED_PAIR_MIN = 0.990
MIN_SYMBOL_DAYS_FOR_RATE = 20


def load_available_pairs(raw_dir: Path) -> pd.DataFrame:
    parts = []
    files = sorted(raw_dir.glob("**/v47_raw1h_shard_*.csv.gz"))
    if not files:
        raise RuntimeError("no raw1h shard files found")
    for p in files:
        try:
            chunks = pd.read_csv(
                p,
                usecols=["symbol", "date"],
                dtype={"symbol": str, "date": str},
                chunksize=500_000,
            )
            for chunk in chunks:
                chunk["symbol"] = (
                    chunk["symbol"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                )
                chunk["date"] = chunk["date"].astype(str).str[:10]
                parts.append(chunk.drop_duplicates(["symbol", "date"]))
        except pd.errors.EmptyDataError:
            # An empty shard is transport/data-coverage evidence, not a verifier crash.
            # Treat it as contributing zero available pairs so the frozen coverage
            # thresholds fail closed and the missing-pair artifacts can be emitted.
            continue
    if not parts:
        return pd.DataFrame(columns=["symbol", "date"])
    out = (
        pd.concat(parts, ignore_index=True)
        .drop_duplicates(["symbol", "date"])
        .reset_index(drop=True)
    )
    return out


def arm_required(candidates: pd.DataFrame, col: str) -> pd.DataFrame:
    q = candidates[candidates[col].astype(bool)][["symbol", "date_s"]].copy()
    q = q.rename(columns={"date_s": "date"})
    q["symbol"] = (
        q["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    q["date"] = q["date"].astype(str).str[:10]
    return q.drop_duplicates(["symbol", "date"]).reset_index(drop=True)


def evaluate_arm(
    required: pd.DataFrame,
    available: pd.DataFrame,
    restored: set[str],
) -> tuple[dict, pd.DataFrame]:
    x = required.merge(
        available.assign(raw_present=True),
        on=["symbol", "date"],
        how="left",
        validate="one_to_one",
    )
    x["raw_present"] = x["raw_present"].fillna(False).astype(bool)
    missing = x[~x["raw_present"]][["symbol", "date"]].copy()

    pair_cov = float(x["raw_present"].mean()) if len(x) else 1.0

    by_month = x.assign(month=x["date"].str[:7]).groupby("month").agg(
        required_pairs=("raw_present", "size"),
        present_pairs=("raw_present", "sum"),
    )
    by_month["coverage"] = by_month["present_pairs"] / by_month["required_pairs"]

    by_symbol = x.groupby("symbol").agg(
        required_days=("raw_present", "size"),
        present_days=("raw_present", "sum"),
    )
    by_symbol["coverage"] = by_symbol["present_days"] / by_symbol["required_days"]

    zero_symbols = sorted(
        by_symbol.index[by_symbol["present_days"] == 0].astype(str).tolist()
    )
    long_symbols = by_symbol[
        by_symbol["required_days"] >= MIN_SYMBOL_DAYS_FOR_RATE
    ]
    low_symbol_cov = long_symbols[long_symbols["coverage"] < SYMBOL_MIN]

    rx = x[x["symbol"].isin(restored)]
    restored_pair_cov = (
        float(rx["raw_present"].mean()) if len(rx) else 1.0
    )

    checks = {
        "pair_coverage_gte_99p5": pair_cov >= PAIR_MIN,
        "monthly_min_coverage_gte_99p0": (
            float(by_month["coverage"].min()) >= MONTH_MIN
            if len(by_month) else True
        ),
        "zero_completely_missing_required_symbols": len(zero_symbols) == 0,
        "per_symbol_coverage_gte_95_for_symbols_with_20plus_days": (
            len(low_symbol_cov) == 0
        ),
        "restored_pair_coverage_gte_99p0": restored_pair_cov >= RESTORED_PAIR_MIN,
    }

    result = {
        "required_pairs": int(len(x)),
        "present_pairs": int(x["raw_present"].sum()),
        "missing_pairs": int((~x["raw_present"]).sum()),
        "pair_coverage": pair_cov,
        "required_symbols": int(by_symbol.shape[0]),
        "completely_missing_required_symbols": zero_symbols,
        "monthly_min_coverage": (
            float(by_month["coverage"].min()) if len(by_month) else 1.0
        ),
        "months_below_99pct": [
            {
                "month": str(idx),
                "coverage": float(row["coverage"]),
                "required_pairs": int(row["required_pairs"]),
                "present_pairs": int(row["present_pairs"]),
            }
            for idx, row in by_month[by_month["coverage"] < MONTH_MIN].iterrows()
        ],
        "symbols_below_95pct_with_20plus_required_days": [
            {
                "symbol": str(idx),
                "coverage": float(row["coverage"]),
                "required_days": int(row["required_days"]),
                "present_days": int(row["present_days"]),
            }
            for idx, row in low_symbol_cov.sort_values("coverage").head(200).iterrows()
        ],
        "restored_required_pairs": int(len(rx)),
        "restored_pair_coverage": restored_pair_cov,
        "checks": checks,
        "accepted": bool(all(checks.values())),
    }
    return result, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-candidates", required=True, type=Path)
    ap.add_argument("--restored-daily", required=True, type=Path)
    ap.add_argument("--daily-receipt", required=True, type=Path)
    ap.add_argument("--raw-dir", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    daily_receipt = json.loads(a.daily_receipt.read_text(encoding="utf-8"))
    if not daily_receipt.get("daily_coverage_pass"):
        raise RuntimeError("daily coverage receipt is not accepted")
    if daily_receipt.get("strategy_returns_opened") or daily_receipt.get("model_scores_opened"):
        raise RuntimeError("daily isolation contract violated")

    candidates = pd.read_csv(
        a.daily_candidates,
        dtype={"symbol": str, "date_s": str},
        low_memory=False,
    )
    restored_daily = pd.read_csv(
        a.restored_daily,
        dtype={"symbol": str},
        usecols=["symbol"],
    )
    restored = set(
        restored_daily["symbol"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .unique()
    )
    available = load_available_pairs(a.raw_dir)

    nocap_req = arm_required(candidates, "eligible_nocap_daily")
    cap_req = arm_required(candidates, "eligible_cap1000_daily")

    nocap, missing_nocap = evaluate_arm(nocap_req, available, restored)
    cap, missing_cap = evaluate_arm(cap_req, available, restored)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    missing_nocap.to_csv(out / "v47_raw1h_missing_pairs_nocap.csv", index=False)
    missing_cap.to_csv(out / "v47_raw1h_missing_pairs_cap1000.csv", index=False)

    report = {
        "scope": "outcome-blind V47 raw1h candidate-date coverage acceptance",
        "thresholds_frozen_before_strategy_outcomes": {
            "pair_coverage_min": PAIR_MIN,
            "monthly_coverage_min": MONTH_MIN,
            "per_symbol_coverage_min_for_20plus_days": SYMBOL_MIN,
            "restored_pair_coverage_min": RESTORED_PAIR_MIN,
        },
        "raw_unique_symbol_dates": int(len(available)),
        "NOCAP": nocap,
        "CAP1000_PIT": cap,
        "accepted": bool(nocap["accepted"] and cap["accepted"]),
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "next_action": (
            "If accepted=false, targeted-refetch the emitted missing symbol/date "
            "pairs and re-run this exact acceptance contract. If accepted=true, "
            "freeze raw hashes and only then materialize model features."
        ),
    }
    (out / "v47_raw1h_coverage_receipt.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
