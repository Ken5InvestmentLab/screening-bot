#!/usr/bin/env python3
"""Generate frozen Weak+Early candidate identities without reading outcomes.

Research-only shadow entrypoint. The input must already be a causally generated
V7 Tail pool. Only signal-time columns are read, so target/return columns in a
historical artifact cannot influence selection.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


RET10_MAX = 0.5735294117647058
G3_MED_RET1_MIN = -0.01
HISTORICAL_TAIL_SHA256 = (
    "0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d"
)
USECOLS = [
    "date",
    "symbol",
    "model_period",
    "med_ret5",
    "med_ret1",
    "ret10",
    "volr20",
    "body_pct",
    "tail_cdf",
    "tail_p",
]
EXPECTED_HISTORICAL_COUNTS = {
    "volr20_low": 172,
    "body_pct_low": 172,
    "mean_rank_volr20_body_pct": 172,
    "dual_top1_agreement": 140,
    "dual_top1_agreement_g3_no_acute_selloff": 117,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_one(pool: pd.DataFrame, key: str) -> pd.DataFrame:
    ordered = pool.sort_values(
        ["date", key, "tail_cdf"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    for date, day in ordered.groupby("date", sort=True):
        best = day.iloc[0]
        tied = day[(day[key] == best[key]) & (day["tail_cdf"] == best["tail_cdf"])]
        if len(tied) != 1:
            raise RuntimeError(f"unresolved winning tie: {date:%Y-%m-%d} / {key}")
    return ordered.groupby("date", sort=True, as_index=False).head(1).copy()


def add_identity(frame: pd.DataFrame, selector: str) -> pd.DataFrame:
    result = frame.copy()
    result["selector"] = selector
    result["candidate_id"] = (
        result["date"].dt.strftime("%Y-%m-%d")
        + "|"
        + result["symbol"].astype(str)
        + "|"
        + selector
    )
    return result


def select_candidates(tail: pd.DataFrame) -> pd.DataFrame:
    pool = tail[
        (tail["med_ret5"] <= 0)
        & (tail["ret10"] <= RET10_MAX)
    ].copy()
    pool["rank_volr20"] = pool.groupby("date")["volr20"].rank(
        pct=True, method="average", ascending=True
    )
    pool["rank_body_pct"] = pool.groupby("date")["body_pct"].rank(
        pct=True, method="average", ascending=True
    )
    pool["mean_rank"] = pool[["rank_volr20", "rank_body_pct"]].mean(axis=1)

    selected = {
        "volr20_low": choose_one(pool, "volr20"),
        "body_pct_low": choose_one(pool, "body_pct"),
        "mean_rank_volr20_body_pct": choose_one(pool, "mean_rank"),
    }
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
    selected["dual_top1_agreement"] = dual
    selected["dual_top1_agreement_g3_no_acute_selloff"] = dual[
        dual["med_ret1"] >= G3_MED_RET1_MIN
    ].copy()

    safe_columns = [
        "date",
        "symbol",
        "model_period",
        "med_ret5",
        "med_ret1",
        "ret10",
        "volr20",
        "body_pct",
        "rank_volr20",
        "rank_body_pct",
        "mean_rank",
        "tail_cdf",
        "tail_p",
        "selector",
        "candidate_id",
    ]
    return pd.concat(
        [add_identity(frame, name) for name, frame in selected.items()],
        ignore_index=True,
    )[safe_columns].sort_values(["date", "selector", "symbol"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail-pool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument(
        "--assert-historical-2023-2025",
        action="store_true",
        help="Require the pinned artifact SHA and five frozen selector counts.",
    )
    args = parser.parse_args()

    if args.assert_historical_2023_2025:
        actual_sha = sha256(args.tail_pool)
        if actual_sha != HISTORICAL_TAIL_SHA256:
            raise RuntimeError(
                f"historical Tail SHA drift: {actual_sha} != {HISTORICAL_TAIL_SHA256}"
            )

    tail = pd.read_csv(
        args.tail_pool,
        usecols=USECOLS,
        dtype={"symbol": str},
        parse_dates=["date"],
    )
    if args.start:
        tail = tail[tail["date"] >= pd.Timestamp(args.start)]
    if args.end:
        tail = tail[tail["date"] <= pd.Timestamp(args.end)]

    output = select_candidates(tail)
    if args.assert_historical_2023_2025:
        counts = output.groupby("selector").size().to_dict()
        if counts != EXPECTED_HISTORICAL_COUNTS:
            raise RuntimeError(
                f"historical selector count drift: {counts} != {EXPECTED_HISTORICAL_COUNTS}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(
        args.output,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        date_format="%Y-%m-%d",
        float_format="%.12g",
    )
    print(output.groupby("selector").size().to_json())


if __name__ == "__main__":
    main()
