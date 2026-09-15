from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from no_tv_v47_clean_feature_materializer import clean_symbol, future_factor, load_split_map


PRICE_COLS = ("open", "high", "low", "close")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_frame(
    df: pd.DataFrame,
    split_map: dict[str, list[tuple[str, float]]],
) -> pd.DataFrame:
    required = {"symbol", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")

    x = df.copy()
    x["symbol"] = x["symbol"].map(clean_symbol)

    ts_col = (
        "ts_jst"
        if "ts_jst" in x.columns
        else "timestamp"
        if "timestamp" in x.columns
        else None
    )
    if ts_col is None:
        raise ValueError("missing timestamp/ts_jst column")

    ts = pd.to_datetime(x[ts_col], errors="coerce", utc=True)
    if ts.isna().any():
        raise ValueError("unparseable timestamps present")
    ts = ts.dt.tz_convert("Asia/Tokyo")
    x["ts_jst"] = ts.map(lambda z: z.isoformat())
    x["date"] = ts.dt.strftime("%Y-%m-%d")

    for col in (*PRICE_COLS, "volume"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    if x[list(PRICE_COLS)].isna().any().any() or x["volume"].isna().any():
        raise ValueError("non-numeric OHLCV present")
    if (x[list(PRICE_COLS)] <= 0).any().any() or (x["volume"] < 0).any():
        raise ValueError("invalid OHLCV values")

    factors = np.array(
        [
            future_factor(split_map, symbol, date_s)
            for symbol, date_s in zip(x["symbol"], x["date"])
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(factors)) or np.any(factors <= 0):
        raise ValueError("invalid future split factor")

    source_volume = x["volume"].to_numpy(float).copy()
    for col in PRICE_COLS:
        x[col] = x[col].to_numpy(float) / factors

    if not np.array_equal(source_volume, x["volume"].to_numpy(float)):
        raise RuntimeError("raw 1H volume changed during normalization")

    x["core24_future_split_factor"] = factors
    x["core24_price_basis_normalized"] = factors != 1.0

    return x[
        [
            "symbol",
            "ts_jst",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "core24_future_split_factor",
            "core24_price_basis_normalized",
        ]
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path)
    ap.add_argument("--all-splits", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()

    files = sorted(args.input_dir.glob("**/ohlcv_1h_shard_*.csv"))
    if not files:
        raise SystemExit("no Core24 raw shard CSVs")

    split_map = load_split_map(args.all_splits)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    receipts = []
    for i, src in enumerate(files):
        df = pd.read_csv(src, dtype={"symbol": str}, low_memory=False)
        out_df = normalize_frame(df, split_map)
        dst = args.output_dir / f"v47_raw1h_shard_{i:02d}.csv.gz"
        out_df.to_csv(dst, index=False, compression="gzip")

        receipts.append(
            {
                "source_file": src.name,
                "source_sha256": sha256_file(src),
                "output_file": dst.name,
                "output_sha256": sha256_file(dst),
                "rows": int(len(out_df)),
                "symbols": int(out_df["symbol"].nunique()),
                "price_basis_rows_transformed": int(
                    out_df["core24_price_basis_normalized"].sum()
                ),
                "source_price_semantics": "Yahoo explicit-period PIT nominal",
                "target_price_semantics": "V47 split-normalized adjusted basis",
                "volume_semantics": "raw Yahoo 1H unchanged",
            }
        )

    payload = {
        "contract": "CONSENSUS_V47_CORE24_RAW_PRICE_BASIS_NORMALIZATION_V1",
        "scope": "OUTCOME_BLIND_PROVENANCE_COMPATIBLE_REUSE",
        "source_run_id": 34592896202,
        "rule": (
            "OHLC_out = OHLC_core24_nominal / "
            "cumulative_future_split_factor(symbol,date); volume unchanged"
        ),
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "files": receipts,
    }
    (args.output_dir / "core24_v47_normalization_receipt.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
