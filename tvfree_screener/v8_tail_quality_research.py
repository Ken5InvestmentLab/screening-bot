#!/usr/bin/env python3
"""V8 downstream Quality/Meta filtering for the V7 full-feature Tail detector.

TEST ONLY. No production writes.

V7 established a useful but noisy component: full 45-feature monthly
cross-sectional top-0.25% ranking concentrated future +20/+50/+100 winners, but
raw -10% false positives were about 40%.

V8 deliberately leaves that Tail score untouched. It adds independent causal
quality heads and optional regime/confirmed-outcome gates AFTER the Tail gate.

Protocol:
  * 2023 is warm-up only for confirmed-outcome Meta state.
  * 2024 develops/ranks a small predeclared filter family.
  * only top 2 qualifying 2024 variants may expose 2025.
  * at most one variant is locked from 2025.
  * 2026 is scored/reported only after the 2025 gate passes.
  * 2026 never selects a feature, threshold, model, or filter.

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

OUT = Path("tvfree_screener/out")
TAIL_GATE = 0.999

DEV = {
    "2024H1": ("2024-01-01", "2024-06-30"),
    "2024H2": ("2024-07-01", "2024-12-31"),
}
VAL = {
    "2025H1": ("2025-01-01", "2025-06-30"),
    "2025H2": ("2025-07-01", "2025-12-31"),
}

# Fixed before V8 is run. Tail ranking itself is identical for every variant.
# Quality CDFs are calibrated from each month's causal training distribution.
VARIANTS = {
    "win50_loss60": {
        "win_min": 0.50, "loss_max": 0.60,
        "market": False, "meta20": False,
    },
    "win60_loss60": {
        "win_min": 0.60, "loss_max": 0.60,
        "market": False, "meta20": False,
    },
    "win55_loss50": {
        "win_min": 0.55, "loss_max": 0.50,
        "market": False, "meta20": False,
    },
    "win65_loss50": {
        "win_min": 0.65, "loss_max": 0.50,
        "market": False, "meta20": False,
    },
    "win55_loss55_market": {
        "win_min": 0.55, "loss_max": 0.55,
        "market": True, "meta20": False,
    },
    "win55_loss55_meta20": {
        "win_min": 0.55, "loss_max": 0.55,
        "market": False, "meta20": True,
    },
    "win55_loss55_market_meta20": {
        "win_min": 0.55, "loss_max": 0.55,
        "market": True, "meta20": True,
    },
}


def classifier(y: pd.Series) -> XGBClassifier:
    pos = max(int(y.sum()), 1)
    neg = max(int(len(y) - pos), 1)
    return XGBClassifier(
        n_estimators=160,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        min_child_weight=18,
        reg_lambda=6,
        reg_alpha=0.3,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=min(neg / pos, 30.0),
        n_jobs=4,
        random_state=42,
    )


def empirical_cdf(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    ref = np.asarray(reference, dtype=float)
    ref = ref[np.isfinite(ref)]
    ref.sort()
    if len(ref) == 0:
        raise RuntimeError("empty training CDF")
    return np.searchsorted(
        ref, np.asarray(values, dtype=float), side="right"
    ) / len(ref)


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    f = base.build_features(raw)
    q = base.eligible_rows(f, price_cap=1000.0).copy()
    q = q.dropna(subset=base.FEATURES + ["target5_no", "target_end_date"])
    q["date"] = pd.to_datetime(q["date"])
    q["target_end_date"] = pd.to_datetime(q["target_end_date"])

    # Tail label remains the V7 concept: future same-day cross-sectional top .25%.
    q["future_rank"] = q.groupby("date")["target5_no"].rank(
        pct=True, method="average"
    )
    q["y_top025"] = (q["future_rank"] >= 0.9975).astype(int)
    q["y_win"] = (q["target5_no"] > 0).astype(int)
    q["y_loss10"] = (q["target5_no"] <= -0.10).astype(int)
    return q


def fit_month(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    for target in ["y_top025", "y_win", "y_loss10"]:
        y = train[target].astype(int)
        if y.nunique() < 2:
            raise RuntimeError(f"degenerate V8 target: {target}")
        m = classifier(y)
        m.fit(train[base.FEATURES], y, verbose=False)
        tr = m.predict_proba(train[base.FEATURES])[:, 1]
        pr = m.predict_proba(pred[base.FEATURES])[:, 1]
        out[f"p_{target}"] = pr
        out[f"cdf_{target}"] = empirical_cdf(tr, pr)
    return out


def score_months(q: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    parts = []
    for period in pd.period_range(
        pd.Timestamp(start).to_period("M"),
        pd.Timestamp(end).to_period("M"),
        freq="M",
    ):
        a = period.start_time
        b = period.end_time.normalize()
        train = q[q["target_end_date"] < a].copy()
        pred = q[(q["date"] >= a) & (q["date"] <= b)].copy()
        if len(train) < 30_000 or pred.empty:
            print(f"skip {period}: train={len(train)} pred={len(pred)}")
            continue
        print(f"fit {period}: train={len(train)} pred={len(pred)}")
        s = fit_month(train, pred)
        s["model_period"] = str(period)
        parts.append(s)
    if not parts:
        raise RuntimeError("no V8 scored periods")
    return pd.concat(parts, ignore_index=True)


def one_per_day(
    z: pd.DataFrame,
    trading_dates: pd.Index,
    score_col: str = "cdf_y_top025",
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
        ["date", score_col], ascending=[True, False]
    ).groupby("date", sort=True):
        idx = date_idx[pd.Timestamp(date)]
        chosen = None
        for _, row in day.sort_values(score_col, ascending=False).iterrows():
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


def baseline_tail(scored: pd.DataFrame, trading_dates: pd.Index) -> pd.DataFrame:
    return one_per_day(
        scored[scored["cdf_y_top025"] >= TAIL_GATE].copy(),
        trading_dates,
    )


def confirmed_meta20(
    baseline: pd.DataFrame,
    dates: pd.Index,
) -> pd.DataFrame:
    baseline = baseline.sort_values("date").copy()
    rows = []
    for date in pd.Index(pd.to_datetime(dates)).sort_values():
        hist = baseline[
            (baseline["date"] < date)
            & (baseline["target_end_date"] < date)
            & baseline["target5_no"].notna()
        ].tail(20)
        rows.append({
            "date": pd.Timestamp(date),
            "recent20_n": int(len(hist)),
            "recent20_mean": (
                float(hist["target5_no"].mean()) if len(hist) else np.nan
            ),
            "recent20_win": (
                float((hist["target5_no"] > 0).mean()) if len(hist) else np.nan
            ),
            "recent20_loss10": (
                float((hist["target5_no"] <= -0.10).mean())
                if len(hist) else np.nan
            ),
        })
    return pd.DataFrame(rows)


def select_variant(
    scored: pd.DataFrame,
    spec: dict,
    trading_dates: pd.Index,
) -> pd.DataFrame:
    base_tail = baseline_tail(scored, trading_dates)
    meta = confirmed_meta20(base_tail, pd.Index(scored["date"].unique()))

    z = scored[scored["cdf_y_top025"] >= TAIL_GATE].copy()
    z = z[
        (z["cdf_y_win"] >= spec["win_min"])
        & (z["cdf_y_loss10"] <= spec["loss_max"])
    ].copy()

    if spec["market"]:
        z = z[
            (z["med_ret5"] >= -0.01)
            & (z["breadth_ma20"] >= 0.40)
        ].copy()

    if spec["meta20"]:
        z = z.merge(meta, on="date", how="left", validate="many_to_one")
        z = z[
            (z["recent20_n"] >= 12)
            & (z["recent20_win"] >= 0.45)
            & (z["recent20_loss10"] <= 0.35)
        ].copy()

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
            picks[(picks["date"] >= a) & (picks["date"] <= b)]["target5_no"]
        )
        for name, (a, b) in periods.items()
    }


def development_utility(ps: dict, pooled: dict) -> float | None:
    h1, h2 = ps["2024H1"], ps["2024H2"]
    if h1.get("n", 0) < 10 or h2.get("n", 0) < 10:
        return None
    if h1["mean"] <= 0 or h2["mean"] <= 0:
        return None
    if pooled["mean"] < 0.02:
        return None
    if pooled["hit20_rate"] < 0.10:
        return None
    if pooled["hit50_rate"] < 0.02:
        return None
    if pooled["loss10_rate"] > 0.25:
        return None
    if max(h1["loss10_rate"], h2["loss10_rate"]) > 0.30:
        return None
    return float(
        min(h1["mean"], h2["mean"])
        + 0.50 * pooled["mean"]
        + 0.08 * pooled["hit20_rate"]
        + 0.12 * pooled["hit50_rate"]
        - 0.10 * max(h1["loss10_rate"], h2["loss10_rate"])
    )


def validation_pass(ps: dict, pooled: dict) -> bool:
    h1, h2 = ps["2025H1"], ps["2025H2"]
    return bool(
        h1.get("n", 0) >= 10
        and h2.get("n", 0) >= 10
        and h1["mean"] > 0
        and h2["mean"] > 0
        and pooled["mean"] >= 0.02
        and pooled["hit20_rate"] >= 0.10
        and pooled["hit50_rate"] >= 0.02
        and pooled["loss10_rate"] <= 0.25
        and max(h1["loss10_rate"], h2["loss10_rate"]) <= 0.30
    )


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
    trading_dates = pd.Index(pd.to_datetime(raw["date"].unique())).sort_values()

    q = prepare(raw)

    # Warm-up 2023 is scored only so 2024 recent-confirmed Meta can be causal.
    dev_scored = score_months(q, "2023-01-01", "2024-12-31")
    candidates = {}
    for name, spec in VARIANTS.items():
        picks = select_variant(dev_scored, spec, trading_dates)
        dev = period_stats(picks, DEV)
        pool = summarize(
            picks[
                (picks["date"] >= "2024-01-01")
                & (picks["date"] <= "2024-12-31")
            ]["target5_no"]
        )
        candidates[name] = {
            "spec": spec,
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
    if opened:
        val_scored = score_months(q, "2025-01-01", "2025-12-31")
        pre2026_scored = pd.concat(
            [dev_scored, val_scored], ignore_index=True
        )
        for name in opened:
            picks = select_variant(
                pre2026_scored, VARIANTS[name], trading_dates
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
    fixed_monthly = None

    if locked is not None:
        future_scored = score_months(q, "2026-01-01", "2026-08-31")
        all_scored = pd.concat(
            [pre2026_scored, future_scored], ignore_index=True
        )
        picks = select_variant(
            all_scored, VARIANTS[locked], trading_dates
        )
        z = picks[
            (picks["date"] >= "2026-03-01")
            & (picks["date"] <= "2026-08-31")
        ].copy()
        fixed = summarize(z["target5_no"])
        fixed_monthly = {
            str(month): summarize(group["target5_no"])
            for month, group in z.groupby(z["date"].dt.to_period("M"))
        }
        z.to_csv(OUT / "v8_tail_quality_locked_2026.csv", index=False)

    report = {
        "status": "research_only_no_production_writes",
        "component": "V7 full-feature top-0.25% Tail detector + downstream V8 Quality/Meta",
        "tail_gate": TAIL_GATE,
        "entry": "next_session_open_to_5BD_close",
        "protocol": (
            "2023 warmup only -> 2024 development -> top2 -> "
            "2025 validation -> lock -> 2026 only after pass"
        ),
        "eligible_rows": int(len(q)),
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
            item["validation_2025"] = v["validation_2025"]
            item["validation_2025_pooled"] = v["validation_2025_pooled"]
            item["validation_pass"] = v["validation_pass"]
        if name == locked:
            item["fixed_2026_MarAug"] = fixed
            item["fixed_2026_monthly"] = fixed_monthly
        report["candidates"][name] = item

    OUT.mkdir(parents=True, exist_ok=True)
    with open(
        OUT / "v8_tail_quality_report.json", "w", encoding="utf-8"
    ) as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
