from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tvfree_screener.batch02 import eval_tentei_inspired_4h_v14_fast_replay as base

EXPECTED_DAILY_SHA = "6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0"
TOP_NS = [1, 2, 3, 5]
PRIMARY_COST = 0.005
COSTS = [0.0, 0.005, 0.01]
H1_START, H1_END = "2025-03-01", "2025-06-30"
H2_START, H2_END = "2025-07-01", "2025-12-31"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_daily(path: Path) -> pd.DataFrame:
    actual = sha256_file(path)
    if actual != EXPECTED_DAILY_SHA:
        raise RuntimeError(f"daily SHA mismatch {actual}")
    d = pd.read_csv(
        path,
        usecols=["date", "symbol", "open", "close", "volume"],
        dtype={"date":"string", "symbol":"string"},
        low_memory=False,
    )
    d["date"] = d["date"].astype(str).str[:10]
    d["symbol"] = d["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for c in ["open", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.sort_values(["symbol", "date"]).reset_index(drop=True)
    return d


def add_history_features(bins: pd.DataFrame) -> pd.DataFrame:
    x = bins.sort_values(["symbol", "date", "bin_ord"], kind="stable").copy()
    x["session_return"] = np.where(x["open"] > 0, x["close"] / x["open"] - 1.0, np.nan)
    span = x["high"] - x["low"]
    x["close_location"] = np.where(span > 0, (x["close"] - x["low"]) / span, 0.5)
    x["true_range_pct"] = np.where(x["close"] > 0, span / x["close"], np.nan)

    g = x.groupby("symbol", sort=False)
    x["prev20_tr_median"] = g["true_range_pct"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=20).median()
    )
    x["prev20_ret_q75"] = g["session_return"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=20).quantile(0.75)
    )
    x["prev20_volume_median"] = g["volume"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=20).median()
    )
    x["volume_ratio20"] = np.where(
        x["prev20_volume_median"] > 0,
        x["volume"] / x["prev20_volume_median"],
        np.nan,
    )
    return x


def attach_prior_daily(bins: pd.DataFrame, daily: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict[str,int]]:
    sessions = sorted(daily["date"].dropna().unique().tolist())
    idx = {d:i for i,d in enumerate(sessions)}
    prior = {sessions[i]: sessions[i-1] for i in range(1, len(sessions))}
    x = bins.copy()
    x["prior_date"] = x["date"].map(prior)
    p = daily[["symbol", "date", "close", "volume"]].rename(
        columns={
            "date":"prior_date",
            "close":"prior_daily_close",
            "volume":"prior_daily_volume",
        }
    )
    x = x.merge(p, on=["symbol", "prior_date"], how="left", validate="many_to_one")
    return x, sessions, idx


def build_candidates(raw_glob: str, daily: pd.DataFrame, max_date: str) -> tuple[pd.DataFrame, list[str], dict[str,int]]:
    bins = base.build_bins_fast(raw_glob, max_date)
    bins = add_history_features(bins)
    bins, sessions, session_idx = attach_prior_daily(bins, daily)

    finite = np.isfinite(
        bins[[
            "session_return", "close_location", "true_range_pct",
            "prev20_tr_median", "prev20_ret_q75", "volume_ratio20",
            "prior_daily_close", "prior_daily_volume", "volume",
        ]]
    ).all(axis=1)

    eligible = bins.loc[
        finite
        & (bins["prior_daily_close"] <= 1000)
        & (bins["prior_daily_volume"] >= 10000)
        & (bins["volume"] >= 5000)
        & (bins["session_return"] > 0)
        & (bins["close_location"] >= 0.75)
        & (bins["true_range_pct"] >= bins["prev20_tr_median"])
        & (bins["session_return"] >= bins["prev20_ret_q75"])
        & (bins["volume_ratio20"] >= 1.0)
    ].copy()

    if eligible.empty:
        return eligible, sessions, session_idx

    for src, dst in [
        ("session_return","rank_session_return"),
        ("close_location","rank_close_location"),
        ("true_range_pct","rank_true_range_pct"),
        ("volume_ratio20","rank_volume_ratio20"),
    ]:
        eligible[dst] = eligible.groupby(["date","bin_name"], sort=False)[src].rank(
            method="average", pct=True, ascending=True
        )
    eligible["score"] = eligible[[
        "rank_session_return","rank_close_location","rank_true_range_pct","rank_volume_ratio20"
    ]].mean(axis=1)

    eligible = eligible.sort_values(
        ["date","bin_ord","score","symbol"],
        ascending=[True,True,False,True],
        kind="stable",
    ).reset_index(drop=True)
    eligible["cohort_rank"] = (
        eligible.groupby(["date","bin_name"], sort=False).cumcount() + 1
    )
    return eligible, sessions, session_idx


def select_topn_no_backfill(candidates: pd.DataFrame, session_idx: dict[str,int], n: int) -> pd.DataFrame:
    top = candidates[candidates["cohort_rank"] <= n].copy()
    blocked_until: dict[str,int] = {}
    keep: list[int] = []

    for i, row in top.iterrows():
        di = session_idx.get(str(row["date"]))
        if di is None:
            continue
        sym = str(row["symbol"])
        # A selection on signal index d may be selected again at d+5:
        # the prior position exits at d+5 close and the new one enters d+6 open.
        if blocked_until.get(sym, -999999) > di:
            continue
        keep.append(i)
        blocked_until[sym] = di + 5

    return top.loc[keep].copy().reset_index(drop=True)


def attach_labels(selected: pd.DataFrame, daily: pd.DataFrame, sessions: list[str]) -> pd.DataFrame:
    entry = {sessions[i]: sessions[i+1] for i in range(len(sessions)-5)}
    exit_ = {sessions[i]: sessions[i+5] for i in range(len(sessions)-5)}

    x = selected.copy()
    x["entry_date"] = x["date"].map(entry)
    x["exit_date"] = x["date"].map(exit_)

    en = daily[["symbol","date","open"]].rename(columns={"date":"entry_date","open":"entry_open"})
    ex = daily[["symbol","date","close"]].rename(columns={"date":"exit_date","close":"exit_close"})
    x = x.merge(en, on=["symbol","entry_date"], how="left", validate="many_to_one")
    x = x.merge(ex, on=["symbol","exit_date"], how="left", validate="many_to_one")

    ok = (
        np.isfinite(x["entry_open"]) & (x["entry_open"] > 0)
        & np.isfinite(x["exit_close"]) & (x["exit_close"] > 0)
    )
    x["endpoint_status"] = np.where(ok, "RESOLVED", "UNRESOLVED_ENDPOINT")
    x["ret5bd_gross"] = np.where(ok, x["exit_close"] / x["entry_open"] - 1.0, np.nan)
    return x


def metrics(rows: pd.DataFrame, cost: float) -> dict:
    r = rows[rows["endpoint_status"]=="RESOLVED"].copy()
    out = {
        "requested": int(len(rows)),
        "resolved": int(len(r)),
        "unresolved": int(len(rows)-len(r)),
    }
    if r.empty:
        return out

    gross = r["ret5bd_gross"].to_numpy(float)
    net = gross - cost
    best = np.sort(net)[::-1]

    z = r.assign(
        net=net,
        month=pd.to_datetime(r["date"]).dt.to_period("M").astype(str),
        week=pd.to_datetime(r["date"]).dt.to_period("W").astype(str),
    )
    month_means = z.groupby("month")["net"].mean()
    week_means = z.groupby("week")["net"].mean()
    sym_share = r["symbol"].astype(str).value_counts(normalize=True)

    out.update({
        "net_mean": float(np.mean(net)),
        "net_median": float(np.median(net)),
        "net_win_rate": float(np.mean(net > 0)),
        "gross_ge10_rate": float(np.mean(gross >= 0.10)),
        "gross_ge20_rate": float(np.mean(gross >= 0.20)),
        "gross_ge50_rate": float(np.mean(gross >= 0.50)),
        "gross_le10_rate": float(np.mean(gross <= -0.10)),
        "gross_le20_rate": float(np.mean(gross <= -0.20)),
        "top1_removed_net_mean": float(best[1:].mean()) if len(best)>1 else None,
        "top3_removed_net_mean": float(best[3:].mean()) if len(best)>3 else None,
        "top5_removed_net_mean": float(best[5:].mean()) if len(best)>5 else None,
        "positive_month_fraction": float((month_means>0).mean()) if len(month_means) else None,
        "positive_week_fraction": float((week_means>0).mean()) if len(week_means) else None,
        "unique_symbols": int(r["symbol"].nunique()),
        "max_symbol_share": float(sym_share.iloc[0]) if len(sym_share) else None,
        "top5_symbol_share": float(sym_share.iloc[:5].sum()) if len(sym_share) else None,
    })
    return out


def h1_gate(m: dict) -> dict:
    checks = {
        "min_resolved_n": m.get("resolved",0) >= 30,
        "net_mean_gt_0": m.get("net_mean",-999.0) > 0,
        "net_median_gte_0": m.get("net_median",-999.0) >= 0,
        "net_win_rate_gt_0_5": m.get("net_win_rate",-999.0) > 0.5,
        "top3_removed_net_mean_gt_0": (
            m.get("top3_removed_net_mean") is not None
            and m["top3_removed_net_mean"] > 0
        ),
        "gross_ge10_rate_gte_0_1": m.get("gross_ge10_rate",-1.0) >= 0.10,
        "gross_le10_rate_lte_0_2": m.get("gross_le10_rate",999.0) <= 0.20,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-glob", required=True)
    ap.add_argument("--daily", required=True, type=Path)
    ap.add_argument("--period", choices=["h1","h2"], default="h1")
    ap.add_argument("--passing-topn", action="append", type=int, default=[])
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--rows-dir", type=Path)
    a = ap.parse_args()

    daily = load_daily(a.daily)
    max_date = H1_END if a.period=="h1" else H2_END
    candidates, sessions, session_idx = build_candidates(a.raw_glob, daily, max_date)

    if a.period=="h1":
        start, end = H1_START, H1_END
        policies = TOP_NS
    else:
        start, end = H2_START, H2_END
        policies = sorted(set(a.passing_topn))
        if not policies:
            raise RuntimeError("H2 requires explicit frozen --passing-topn from H1")
        if any(n not in TOP_NS for n in policies):
            raise RuntimeError(f"invalid H2 TopN policy {policies}")

    period_candidates = candidates[
        (candidates["date"] >= start) & (candidates["date"] <= end)
    ].copy()

    result = {
        "experiment_id":"TENTEI-4H-V20-SESSION-IMPULSE-CONTINUATION-20260914",
        "period":a.period,
        "start":start,
        "end":end,
        "daily_sha256":EXPECTED_DAILY_SHA,
        "candidate_rows":int(len(period_candidates)),
        "candidate_symbols":int(period_candidates["symbol"].nunique()) if len(period_candidates) else 0,
        "candidate_groups":int(period_candidates.groupby(["date","bin_name"]).ngroups) if len(period_candidates) else 0,
        "policies":{},
        "year_2026_outcomes_opened":False,
        "production_modified":False,
    }

    if a.rows_dir:
        a.rows_dir.mkdir(parents=True, exist_ok=True)
        period_candidates.to_csv(a.rows_dir/f"v20_{a.period}_candidates.csv", index=False)

    passing = []
    for n in policies:
        sel = select_topn_no_backfill(period_candidates, session_idx, n)
        labeled = attach_labels(sel, daily, sessions)
        primary = metrics(labeled, PRIMARY_COST)
        block = {
            "top_n":n,
            "selected_rows":int(len(labeled)),
            "cost0":metrics(labeled,0.0),
            "cost0_5pct":primary,
            "cost1pct":metrics(labeled,0.01),
        }
        if a.period=="h1":
            block["h1_gate"] = h1_gate(primary)
            if block["h1_gate"]["all_pass"]:
                passing.append(n)
        result["policies"][str(n)] = block
        if a.rows_dir:
            labeled.to_csv(a.rows_dir/f"v20_{a.period}_top{n}.csv", index=False)

    if a.period=="h1":
        result["passing_topn"] = passing
        result["decision"] = (
            "OPEN_H2_FOR_UNCHANGED_PASSING_POLICIES" if passing
            else "REJECT_V20_WITHOUT_H2"
        )
    else:
        result["decision"] = "H2_RETROSPECTIVE_REFUTATION_REPORTED"

    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
