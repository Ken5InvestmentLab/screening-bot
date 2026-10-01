"""Independent recalculation of saved exit-study prices, quantities and metrics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(left, right, label, tolerance=1e-8):
    if not np.allclose(left, right, rtol=1e-9, atol=tolerance, equal_nan=True):
        raise AssertionError(label)


def recalculate(directory):
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(directory / "trades.csv", parse_dates=["signal_date", "entry_date", "exit_date"], dtype={"symbol": str}, float_precision="round_trip")
    cutoff = pd.Timestamp(metadata["source_cutoff"])
    assert frame.exit_date.le(cutoff).all(), "incomplete/intraday exits"
    assert frame.groupby(["arm", "selector", "identity"]).endpoint.nunique().eq(20).all()
    assert not frame.duplicated(["arm", "selector", "identity", "endpoint"]).any()
    assert frame.entry_shares.eq(100).all()
    assert frame.groupby(["arm", "identity", "endpoint"]).gross_return.nunique().eq(1).all()
    assert sha(metadata["script_snapshot"]) == metadata["script_sha256"]
    for item in metadata["selection_inputs"]:
        assert sha(item["path"]) == item["sha256"]
    assert sha(metadata["actions_path"]) == metadata["actions_sha256"]

    # Read the source separately, without calling the study's loader or helper.
    symbols = set(frame.symbol)
    parts = []
    for chunk in pd.read_csv(metadata["daily_path"], usecols=["date", "symbol", "actual_open", "actual_close", "source_usable"], dtype={"symbol": str}, parse_dates=["date"], chunksize=250_000, float_precision="round_trip"):
        matching = chunk[chunk.symbol.isin(symbols) & chunk.date.le(cutoff)]
        if not matching.empty:
            parts.append(matching)
    source = pd.concat(parts, ignore_index=True).set_index(["symbol", "date"])
    assert not source.index.duplicated().any()
    endpoint_rows = frame.drop_duplicates(["identity", "endpoint"])
    entry_keys = pd.MultiIndex.from_frame(endpoint_rows[["symbol", "entry_date"]])
    exit_keys = pd.MultiIndex.from_frame(endpoint_rows[["symbol", "exit_date"]])
    entries, exits = source.reindex(entry_keys), source.reindex(exit_keys)
    assert entries.source_usable.astype(str).str.lower().isin(["true", "1"]).all()
    assert exits.source_usable.astype(str).str.lower().isin(["true", "1"]).all()
    actual_exit = np.where(endpoint_rows.endpoint.str.endswith("_open"), exits.actual_open, exits.actual_close)
    close(endpoint_rows.entry_open.to_numpy(), entries.actual_open.to_numpy(), "actual entry quotes")
    close(endpoint_rows.exit_price.to_numpy(), actual_exit, "actual exit quotes")

    journal = pd.read_csv(metadata["actions_path"], parse_dates=["effective_date"], dtype={"symbol": str})
    journal = journal[journal.effective_date.le(cutoff)]
    actions = {symbol: list(group.sort_values("effective_date")[["effective_date", "ratio"]].itertuples(index=False, name=None)) for symbol, group in journal.groupby("symbol")}
    quantities = []
    for row in endpoint_rows.itertuples(index=False):
        quantity = 100.
        for effective, ratio in actions.get(row.symbol, []):
            if row.entry_date < effective <= row.exit_date:
                quantity *= ratio
                assert round(quantity) > 0 and math.isclose(quantity, round(quantity), rel_tol=0, abs_tol=1e-8), "fractional lot"
                quantity = float(round(quantity))
        quantities.append(quantity)
    close(endpoint_rows.exit_shares.to_numpy(), quantities, "independent event quantities")
    cost = frame.entry_open * 100
    cash = frame.exit_price * frame.exit_shares - cost
    gross = (cash / cost).mask((cash / cost).abs().lt(1e-12), 0.)
    close(frame.entry_cost_yen, cost, "entry costs", 1e-6)
    close(frame.cash_pl_100_yen, cash, "cash P/L", 1e-6)
    close(frame.gross_return, gross, "share-aware returns")

    computed = []
    for arm, arm_rows in frame.groupby("arm"):
        selectors = sorted(arm_rows.selector.unique()) + ["all_conditions_stacked", "all_conditions_unique"]
        for selector in selectors:
            group = arm_rows if selector == "all_conditions_stacked" else arm_rows.drop_duplicates(["identity", "endpoint"]) if selector == "all_conditions_unique" else arm_rows[arm_rows.selector.eq(selector)]
            period_masks = {"ALL_DESCRIPTIVE": pd.Series(True, index=group.index), "DEV_2023_2024": group.signal_date.dt.year.isin([2023, 2024]), **{str(year): group.signal_date.dt.year.eq(year) for year in sorted(group.signal_date.dt.year.unique())}}
            for period, mask in period_masks.items():
                for endpoint, values in group[mask].groupby("endpoint"):
                    returns = values.gross_return.to_numpy()
                    sorted_returns = np.sort(returns)
                    computed.append(dict(arm=arm, selector=selector, period=period, endpoint=endpoint, n=len(values), mean_pct=np.mean(returns)*100, median_pct=np.median(returns)*100, win_pct=np.count_nonzero(returns>0)/len(values)*100, loss10_pct=np.count_nonzero(returns<=-.1)/len(values)*100, loss10_count=np.count_nonzero(returns<=-.1), max_down_pct=np.min(returns)*100, top3_ex_mean_pct=np.mean(sorted_returns[:-3])*100 if len(values)>3 else np.nan, cash_pl_100_yen=values.cash_pl_100_yen.sum(), entry_capital_sum_yen=values.entry_cost_yen.sum()))
    recalculated = pd.DataFrame(computed)
    stored = pd.read_csv(directory / "metrics.csv", dtype={"period": str}, float_precision="round_trip")
    keys = ["arm", "selector", "period", "endpoint"]
    merged = recalculated.merge(stored, on=keys, suffixes=("_audit", "_saved"), validate="one_to_one")
    assert len(merged) == len(stored) == len(recalculated)
    for name in set(recalculated.columns) - set(keys):
        close(merged[f"{name}_audit"], merged[f"{name}_saved"], f"metric {name}", 1e-6)
    assert stored.groupby(["arm", "selector", "period"]).n.nunique().eq(1).all()

    def order(row, joint):
        cap = int(row.arm[3:]) if row.arm.startswith("cap") else 0
        day = int(row.endpoint.split("_")[0][1:])
        return (-row.mean_pct, cap if cap > 0 else float("inf") if joint else 0, day, row.endpoint.endswith("_close"), row.arm)

    cap_fixed = pd.read_csv(directory / "dev_fixed_vs_posthoc.csv", dtype={"period": str})
    for (arm, selector), group in recalculated.groupby(["arm", "selector"]):
        dev = group[group.period.eq("DEV_2023_2024")]
        selected = min(dev.itertuples(index=False), key=lambda row: order(row, False))
        receipts = cap_fixed[cap_fixed.arm.eq(arm) & cap_fixed.selector.eq(selector)]
        assert receipts.dev_fixed_endpoint.eq(selected.endpoint).all(), "per-cap DEV leakage"
    joint = pd.read_csv(directory / "joint_cap_exit_dev_fixed.csv", dtype={"period": str})
    for selector, group in recalculated.groupby("selector"):
        dev = group[group.period.eq("DEV_2023_2024")]
        assert len(dev) == 120, "incomplete cap-by-exit DEV grid"
        selected = min(dev.itertuples(index=False), key=lambda row: order(row, True))
        receipts = joint[joint.selector.eq(selector)]
        assert receipts.dev_fixed_arm.eq(selected.arm).all() and receipts.dev_fixed_endpoint.eq(selected.endpoint).all(), "joint DEV leakage"
        for row in receipts.itertuples(index=False):
            fixed = group[group.period.eq(row.period) & group.arm.eq(selected.arm) & group.endpoint.eq(selected.endpoint)].iloc[0]
            for name in ["mean_pct", "win_pct", "median_pct", "loss10_pct", "top3_ex_mean_pct"]:
                close(getattr(row, f"fixed_{name}"), fixed[name], f"joint fixed {name}")
    result = dict(status="PASS", trade_rows=len(frame), metrics_rows=len(stored), endpoint_price_rows=len(endpoint_rows), unique_identities=int(frame.identity.nunique()), joint_groups=int(joint.selector.nunique()), checks=["immutable input/script SHA", "source actual quotes and source usability", "entry-exclusive/exit-inclusive event quantities and whole intermediate lots", "cash and returns from original 100 shares", "all saved metrics independently recalculated", "equal twenty-endpoint cohorts", "DEV-only per-cap and 120-pair joint selection"], no_production_mutations=True)
    (directory / "independent_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(recalculate(args.directory), ensure_ascii=False))
