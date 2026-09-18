#!/usr/bin/env python3
"""V9 conditional Quality model for the V7 Tail detector (TEST ONLY).

V8 trained quality heads on the whole eligible universe, then applied them after
an extreme Tail gate. That produced zero 2024 picks. V9 changes the population:

1. Generate the V7 top-0.25% Tail score causally each month.
2. Keep the raw extreme Tail pool (cdf >= 0.999) BEFORE one-per-day selection.
3. Train Quality only on previously completed historical Tail candidates.
4. Quality predicts two conditional outcomes:
   - future 5BD return >= +20% (monster hit)
   - future 5BD return <= -10% (large loss)
5. Score current Tail candidates by monster-vs-loss probability ratio.
6. Tail score itself is never penalized or retrained by Quality.

Protocol:
- 2023 = causal meta-training warmup only.
- 2024 = development only.
- Only top 2 qualifying fixed variants may expose 2025.
- At most one variant is locked on 2025.
- 2026 is scored only after a 2025 pass.
- No production writes.

Entry/evaluation: next-session open -> 5BD close.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

import run as base
import v7_full_tail_research as v7

OUT = Path("tvfree_screener/out")
TAIL_GATE = 0.999
MIN_META_N = 120
MIN_META_CLASS = 12

DEV = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}

# Fixed before opening 2024 outcomes for V9.
# rank_only never vetoes a Tail day; the ratio variants progressively remove
# candidates whose conditional monster-vs-loss profile is weak.
VARIANTS = {
    "rank_only": {"ratio_min": None},
    "ratio30": {"ratio_min": 0.30},
    "ratio40": {"ratio_min": 0.40},
    "ratio50": {"ratio_min": 0.50},
}

# Keep the conditional model deliberately smaller than the 45-feature Tail
# detector. These are signal-time price/volume/structure + market-context fields.
QUALITY_FEATURES = [
    "ret1", "ret3", "ret5", "ret10", "ret20",
    "ma5_gap", "ma20_gap",
    "volr5", "volr20",
    "rsi14", "atr14p",
    "body_pct", "lower_wick", "upper_wick", "range_pct", "gap",
    "pos20", "dd20", "bounce20",
    "bbpct", "bbwidth", "volz20", "log_dv",
    "down3", "down5",
    "breadth_ret1_pos", "med_ret5", "breadth_ma20",
    "tail_p", "tail_cdf",
]


def quality_model(y: pd.Series, seed: int = 42) -> XGBClassifier:
    pos = max(int(y.sum()), 1)
    neg = max(int(len(y) - pos), 1)
    return XGBClassifier(
        n_estimators=140,
        max_depth=2,
        learning_rate=0.035,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=8,
        reg_lambda=8,
        reg_alpha=0.5,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=min(neg / pos, 20.0),
        n_jobs=4,
        random_state=seed,
    )


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    q = v7.prepare(raw)
    q["y_hit20"] = (q["target5_no"] >= 0.20).astype(int)
    q["y_loss10"] = (q["target5_no"] <= -0.10).astype(int)
    return q


def score_tail_month(
    q: pd.DataFrame,
    month: pd.Period,
) -> pd.DataFrame:
    a = month.start_time
    b = month.end_time.normalize()
    train = q[q["target_end_date"] < a].copy()
    pred = q[(q["date"] >= a) & (q["date"] <= b)].copy()
    if len(train) < 30_000 or pred.empty:
        return pd.DataFrame()

    y = train["y_top025"].astype(int)
    if y.nunique() < 2:
        return pd.DataFrame()

    m = v7.model(y)
    m.fit(train[base.FEATURES], y, verbose=False)
    tr = m.predict_proba(train[base.FEATURES])[:, 1]
    pr = m.predict_proba(pred[base.FEATURES])[:, 1]

    pred = pred.copy()
    pred["tail_p"] = pr
    pred["tail_cdf"] = v7.cdf(tr, pr)
    pred["model_period"] = str(month)
    return pred[pred["tail_cdf"] >= TAIL_GATE].copy()


def generate_tail_pool(
    q: pd.DataFrame,
    start: str,
    end: str,
) -> pd.DataFrame:
    parts = []
    for month in pd.period_range(
        pd.Timestamp(start).to_period("M"),
        pd.Timestamp(end).to_period("M"),
        freq="M",
    ):
        z = score_tail_month(q, month)
        print(f"tail {month}: n={len(z)}")
        if not z.empty:
            parts.append(z)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def attach_quality_scores(
    current: pd.DataFrame,
    history: pd.DataFrame,
    month_start: pd.Timestamp,
) -> pd.DataFrame:
    hist = history[
        (history["target_end_date"] < month_start)
        & history["target5_no"].notna()
    ].copy()
    hist = hist.dropna(subset=QUALITY_FEATURES)
    cur = current.dropna(subset=QUALITY_FEATURES).copy()

    if len(hist) < MIN_META_N or cur.empty:
        return pd.DataFrame()

    hit_n = int(hist["y_hit20"].sum())
    loss_n = int(hist["y_loss10"].sum())
    non_hit = len(hist) - hit_n
    non_loss = len(hist) - loss_n
    if min(hit_n, loss_n, non_hit, non_loss) < MIN_META_CLASS:
        print(
            f"skip quality {month_start:%Y-%m}: hist={len(hist)} "
            f"hit20={hit_n} loss10={loss_n}"
        )
        return pd.DataFrame()

    out = cur.copy()
    for target in ["y_hit20", "y_loss10"]:
        y = hist[target].astype(int)
        model = quality_model(y)
        model.fit(hist[QUALITY_FEATURES], y, verbose=False)
        out[f"qprob_{target}"] = model.predict_proba(
            out[QUALITY_FEATURES]
        )[:, 1]

    denom = out["qprob_y_hit20"] + out["qprob_y_loss10"]
    out["quality_ratio"] = np.where(
        denom > 0,
        out["qprob_y_hit20"] / denom,
        0.0,
    )
    out["quality_edge"] = (
        out["qprob_y_hit20"] - out["qprob_y_loss10"]
    )
    out["meta_hist_n"] = len(hist)
    out["meta_hist_hit20"] = hit_n
    out["meta_hist_loss10"] = loss_n
    return out


def one_per_day(
    z: pd.DataFrame,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    if z.empty:
        return z.copy()

    date_idx = {
        pd.Timestamp(d): i
        for i, d in enumerate(pd.Index(trading_dates).sort_values())
    }
    rows = []
    last_symbol = None
    last_idx = None

    for date, day in z.sort_values(
        ["date", "quality_ratio", "tail_cdf", "tail_p"],
        ascending=[True, False, False, False],
    ).groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        chosen = None
        for _, row in day.sort_values(
            ["quality_ratio", "tail_cdf", "tail_p"],
            ascending=False,
        ).iterrows():
            if (
                last_idx is not None
                and idx == last_idx + 1
                and str(row["symbol"]) == last_symbol
            ):
                continue
            chosen = row
            break
        if chosen is not None:
            rows.append(chosen)
            last_symbol = str(chosen["symbol"])
            last_idx = idx

    return pd.DataFrame(rows).reset_index(drop=True)


def select_variant(
    scored: pd.DataFrame,
    name: str,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    spec = VARIANTS[name]
    z = scored.copy()
    if spec["ratio_min"] is not None:
        z = z[z["quality_ratio"] >= spec["ratio_min"]].copy()
    return one_per_day(z, trading_dates)


def summarize(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "win_rate": float((x > 0).mean()),
        "hit10_rate": float((x >= 0.10).mean()),
        "hit20_rate": float((x >= 0.20).mean()),
        "hit50_rate": float((x >= 0.50).mean()),
        "hit100_rate": float((x >= 1.00).mean()),
        "loss10_rate": float((x <= -0.10).mean()),
        "max": float(x.max()),
        "min": float(x.min()),
    }


def period_stats(
    picks: pd.DataFrame,
    periods: dict[str, tuple[str, str]],
) -> dict:
    return {
        name: summarize(
            picks[
                (picks["date"] >= a) & (picks["date"] <= b)
            ]["target5_no"]
        )
        for name, (a, b) in periods.items()
    }


def development_utility(ps: dict, pooled: dict) -> float | None:
    h1, h2 = ps["2024H1"], ps["2024H2"]
    if h1.get("n", 0) < 8 or h2.get("n", 0) < 8:
        return None
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return None
    if pooled["mean"] < 0.02:
        return None
    if pooled["hit20_rate"] < 0.10:
        return None
    if pooled["hit50_rate"] < 0.02:
        return None
    if pooled["loss10_rate"] > 0.30:
        return None
    return float(
        min(h1["mean"], h2["mean"])
        + 0.50 * pooled["mean"]
        + 0.10 * pooled["hit20_rate"]
        + 0.15 * pooled["hit50_rate"]
        - 0.08 * pooled["loss10_rate"]
    )


def validation_pass(ps: dict, pooled: dict) -> bool:
    h1, h2 = ps["2025H1"], ps["2025H2"]
    return bool(
        h1.get("n", 0) >= 8
        and h2.get("n", 0) >= 8
        and h1["mean"] > 0
        and h2["mean"] > 0
        and pooled["mean"] >= 0.02
        and pooled["hit20_rate"] >= 0.08
        and pooled["hit50_rate"] >= 0.02
        and pooled["loss10_rate"] <= 0.30
    )


def score_period_with_quality(
    q: pd.DataFrame,
    history_tail: pd.DataFrame,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_parts = []
    hist = history_tail.copy()

    for month in pd.period_range(
        pd.Timestamp(start).to_period("M"),
        pd.Timestamp(end).to_period("M"),
        freq="M",
    ):
        cur = score_tail_month(q, month)
        if cur.empty:
            continue
        qcur = attach_quality_scores(cur, hist, month.start_time)
        print(
            f"quality {month}: tail={len(cur)} scored={len(qcur)} "
            f"hist={len(hist)}"
        )
        if not qcur.empty:
            scored_parts.append(qcur)
        hist = pd.concat([hist, cur], ignore_index=True)

    scored = (
        pd.concat(scored_parts, ignore_index=True)
        if scored_parts else pd.DataFrame()
    )
    return scored, hist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(OUT / "tse_daily.csv"))
    args = ap.parse_args()

    raw = pd.read_csv(args.cache, parse_dates=["date"], dtype={"symbol": str})
    for c in ["open", "high", "low", "close", "volume"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.dropna(
        subset=["date", "symbol", "open", "high", "low", "close", "volume"]
    ).sort_values(["symbol", "date"]).reset_index(drop=True)

    trading_dates = pd.Index(
        pd.to_datetime(raw["date"].unique())
    ).sort_values()
    q = prepare(raw)

    # 2023 tail candidates are warmup only. They provide the first completed
    # conditional-Tail examples for the 2024 meta model.
    warm_tail = generate_tail_pool(q, "2023-01-01", "2023-12-31")
    if warm_tail.empty:
        raise RuntimeError("V9 warmup tail pool is empty")

    dev_scored, tail_through_2024 = score_period_with_quality(
        q, warm_tail, "2024-01-01", "2024-12-31"
    )
    if dev_scored.empty:
        raise RuntimeError("V9 generated no 2024 quality scores")

    candidates = {}
    for name in VARIANTS:
        picks = select_variant(dev_scored, name, trading_dates)
        dev = period_stats(picks, DEV)
        pool = summarize(
            picks[
                (picks["date"] >= "2024-01-01")
                & (picks["date"] <= "2024-12-31")
            ]["target5_no"]
        )
        candidates[name] = {
            "spec": VARIANTS[name],
            "development_2024": dev,
            "development_2024_pooled": pool,
            "development_utility": development_utility(dev, pool),
        }

    ranked = sorted(
        [
            (v["development_utility"], name)
            for name, v in candidates.items()
            if v["development_utility"] is not None
        ],
        reverse=True,
    )
    opened = [name for _, name in ranked[:2]]

    accepted = []
    pre2026_scored = None
    tail_through_2025 = None

    if opened:
        val_scored, tail_through_2025 = score_period_with_quality(
            q, tail_through_2024, "2025-01-01", "2025-12-31"
        )
        pre2026_scored = pd.concat(
            [dev_scored, val_scored], ignore_index=True
        )

        for name in opened:
            picks = select_variant(
                pre2026_scored, name, trading_dates
            )
            val = period_stats(picks, VAL)
            pool = summarize(
                picks[
                    (picks["date"] >= "2025-01-01")
                    & (picks["date"] <= "2025-12-31")
                ]["target5_no"]
            )
            candidates[name]["validation_2025"] = val
            candidates[name]["validation_2025_pooled"] = pool
            candidates[name]["validation_pass"] = validation_pass(val, pool)
            if candidates[name]["validation_pass"]:
                accepted.append((
                    min(val["2025H1"]["mean"], val["2025H2"]["mean"]),
                    pool["mean"],
                    name,
                ))

    locked = sorted(accepted, reverse=True)[0][2] if accepted else None
    fixed = None
    monthly = None

    if locked is not None:
        future_scored, _ = score_period_with_quality(
            q, tail_through_2025, "2026-01-01", "2026-08-31"
        )
        all_scored = pd.concat(
            [pre2026_scored, future_scored], ignore_index=True
        )
        picks = select_variant(
            all_scored, locked, trading_dates
        )
        z = picks[
            (picks["date"] >= "2026-03-01")
            & (picks["date"] <= "2026-08-31")
        ].copy()
        fixed = summarize(z["target5_no"])
        monthly = {
            str(month): summarize(group["target5_no"])
            for month, group in z.groupby(z["date"].dt.to_period("M"))
        }
        z.to_csv(
            OUT / "v9_conditional_quality_locked_2026.csv",
            index=False,
        )

    report = {
        "status": "research_only_no_production_writes",
        "component": (
            "V7 top-0.25% Tail detector + V9 conditional-on-Tail Quality"
        ),
        "tail_gate": TAIL_GATE,
        "quality_targets": ["5BD >= +20%", "5BD <= -10%"],
        "quality_population": (
            "historical causal V7 extreme-Tail candidates only"
        ),
        "quality_features": QUALITY_FEATURES,
        "entry": "next_session_open_to_5BD_close",
        "protocol": (
            "2023 Tail warmup -> 2024 development -> top2 -> "
            "2025 validation -> lock -> 2026 only after pass"
        ),
        "eligible_rows": int(len(q)),
        "warmup_tail_candidates_2023": int(len(warm_tail)),
        "development_ranked": [
            {"name": name, "utility": float(score)}
            for score, name in ranked
        ],
        "validation_opened": opened,
        "locked_candidate": locked,
        "candidates": {},
    }

    for name, v in candidates.items():
        item = {
            "spec": v["spec"],
            "development_2024": v["development_2024"],
            "development_2024_pooled": v["development_2024_pooled"],
            "development_utility": v["development_utility"],
        }
        if name in opened:
            item.update({
                "validation_2025": v["validation_2025"],
                "validation_2025_pooled": v["validation_2025_pooled"],
                "validation_pass": v["validation_pass"],
            })
        if name == locked:
            item.update({
                "fixed_2026_MarAug": fixed,
                "fixed_2026_monthly": monthly,
            })
        report["candidates"][name] = item

    OUT.mkdir(parents=True, exist_ok=True)
    with open(
        OUT / "v9_conditional_quality_report.json",
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
