"""Offline fixed-selection exit comparison. No network or production writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "weak_early_beta" / "bank_calendar.py").is_file())
sys.path.insert(0, str(ROOT))
from weak_early_beta.bank_calendar import add_bank_business_days
from weak_early_beta.entry_feasibility import performance_eligible
from weak_early_beta.restrictions import restricted_mask
from weak_early_beta.trade_basis import build_trade_economics

ENDPOINTS = [(day, price) for day in range(1, 11) for price in ("open", "close")]
BASELINE = "d5_close"
SELECTOR_LABELS = {"volr20_low": "Silence", "body_pct_low": "Dive", "mean_rank_volr20_body_pct": "Shadow", "dual_top1_agreement": "Fusion", "dual_top1_agreement_g3_no_acute_selloff": "Balance", "all_conditions_stacked": "Stacked", "all_conditions_unique": "Unique"}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verified_cap_summary(path):
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary.get("identity") != "CLOUD_CAP_CORRECTED_COMPARISON_V2" or summary.get("status") != "complete":
        raise ValueError("only the completed corrected V2 cap comparison may feed the final exit study")
    counts = summary["counts"]
    expected_caps = {0, 1000, 1500, 2000, 3000, 5000}
    if {item["cap"] for item in counts} != expected_caps or any(item["completed_months"] != 45 for item in counts):
        raise ValueError("six arms and all 270 model fits are required")
    receipts = sorted(path.parent.glob("receipt_cap*_*.json"))
    expected = {(cap, str(month)) for cap in expected_caps for month in pd.period_range("2023-01", "2026-09", freq="M")}
    observed = set()
    source_hashes = None
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        identity = (receipt["cap"], receipt["month"])
        if identity in observed:
            raise ValueError("duplicate model receipt")
        observed.add(identity)
        selected = path.parent / f"selected_cap{identity[0]}_{identity[1]}.csv"
        if digest(selected) != receipt["selected_sha256"]:
            raise ValueError(f"changed monthly selected file: {selected}")
        if source_hashes is None:
            source_hashes = receipt["source_hashes"]
        elif source_hashes != receipt["source_hashes"]:
            raise ValueError("mixed monthly code/input versions")
    if observed != expected or len(receipts) != 270:
        raise ValueError("270 unique monthly model receipts are required")
    for component, expected_hash in source_hashes.items():
        if digest(ROOT / component) != expected_hash:
            raise ValueError(f"changed model component: {component}")
    return summary, len(receipts)


def sessions(signal):
    return [pd.Timestamp(add_bank_business_days(signal.date(), day)) for day in range(1, 11)]


def load_prices(path, symbols, bad_bars_path=None):
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    keep = [name for name in (
        "date", "symbol", "open", "high", "low", "close", "volume",
        "actual_open", "actual_close", "split_factor", "source_usable",
        "price_basis", "corporate_actions_version",
    ) if name in columns]
    parts = []
    for chunk in pd.read_csv(path, usecols=keep, parse_dates=["date"], dtype={"symbol": str}, chunksize=250_000):
        selected = chunk[chunk.symbol.isin(symbols)]
        if not selected.empty:
            parts.append(selected.copy())
    if not parts:
        raise ValueError("no selected-symbol source prices")
    result = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"])
    if result.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate source prices")
    tolerance = result.high.abs() * 1e-6
    result["endpoint_usable"] = (
        np.isfinite(result[["open", "high", "low", "close"]]).all(axis=1)
        & (result[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (result.low <= result.high + tolerance)
        & (result.open >= result.low - tolerance) & (result.open <= result.high + tolerance)
        & (result.close >= result.low - tolerance) & (result.close <= result.high + tolerance)
    )
    if "source_usable" in result:
        result["endpoint_usable"] &= result.source_usable.astype(str).str.lower().isin(["true", "1"])
    if bad_bars_path:
        audit = pd.read_csv(bad_bars_path, usecols=["date", "symbol"], parse_dates=["date"], dtype={"symbol": str})
        audited = pd.MultiIndex.from_frame(audit[["symbol", "date"]])
        result["endpoint_usable"] &= ~pd.MultiIndex.from_frame(result[["symbol", "date"]]).isin(audited)
    return result


def load_actions(path, source_cutoff):
    if path is None:
        return {}
    actions = pd.read_csv(path, parse_dates=["effective_date"], dtype={"symbol": str})
    actions = actions[actions.effective_date.le(source_cutoff)].copy()
    if actions.duplicated(["symbol", "effective_date"]).any():
        raise ValueError("duplicate action journal identities")
    if not np.isfinite(actions.ratio).all() or actions.ratio.le(0).any():
        raise ValueError("invalid action journal ratio")
    return {
        symbol: group.sort_values("effective_date")[["effective_date", "ratio"]].to_dict("records")
        for symbol, group in actions.groupby("symbol")
    }


def factor(events, session):
    return math.prod(float(event["ratio"]) for event in events if event["effective_date"] > session)


def evaluate(selected, raw, actions, share_aware):
    prices = raw.set_index(["symbol", "date"])
    output, rejected = [], []
    completed_cache, rejection_cache, action_frames = {}, {}, {}
    for row in selected.itertuples(index=False):
        identity = f"{row.date:%Y-%m-%d}|{row.symbol}"
        current = {"selector": row.selector, "arm": getattr(row, "arm", "cap1000")}
        if identity in completed_cache:
            output.extend([{**endpoint, **current} for endpoint in completed_cache[identity]])
            continue
        if identity in rejection_cache:
            rejected.append({"identity": identity, "symbol": row.symbol, "signal_date": row.date, **current, "reason": rejection_cache[identity]})
            continue
        dates = sessions(row.date)
        events = actions.get(row.symbol, [])
        if row.symbol not in action_frames:
            action_frames[row.symbol] = pd.DataFrame(events, columns=["effective_date", "ratio"])
        try:
            endpoints = []
            for session in dates:
                if (row.symbol, session) not in prices.index:
                    raise ValueError(f"missing_session:{session:%Y-%m-%d}")
                endpoint = prices.loc[(row.symbol, session)]
                if not bool(endpoint.endpoint_usable):
                    raise ValueError(f"unusable_ohlc:{session:%Y-%m-%d}")
                endpoints.append(endpoint)
            entry_adjusted = float(endpoints[0].open)
            if share_aware:
                # The journal is clipped to the OLD price corpus snapshot;
                # later splits must not be applied a second time to old prices.
                entry_factor = factor(events, dates[0])
                entry_actual = float(endpoints[0].get("actual_open", entry_adjusted * entry_factor))
            else:
                entry_factor, entry_actual = 1.0, entry_adjusted
            if not math.isfinite(entry_actual) or entry_actual <= 0:
                raise ValueError("nonpositive_or_nonfinite_actual_entry")
            identity_rows = []
            for day, quote in ENDPOINTS:
                endpoint = endpoints[day - 1]
                adjusted_exit = float(endpoint[quote])
                if share_aware:
                    actual_exit = float(endpoint.get(f"actual_{quote}", adjusted_exit * factor(events, dates[day - 1])))
                    economics = build_trade_economics(dates[0], dates[day - 1], entry_actual, actual_exit, action_frames[row.symbol])
                    shares = economics["exit_shares"]
                    gross, cash = economics["gross_return"], economics["one_hundred_shares_pl_yen"]
                else:
                    shares, actual_exit = 100.0, adjusted_exit
                    gross, cash = adjusted_exit / entry_adjusted - 1, (adjusted_exit - entry_adjusted) * 100
                if not math.isfinite(actual_exit) or actual_exit <= 0 or not math.isfinite(gross):
                    raise ValueError("nonpositive_or_nonfinite_actual_exit")
                if abs(gross) < 1e-12:
                    gross, cash = 0.0, 0.0
                identity_rows.append({
                    "signal_date": row.date, "symbol": row.symbol,
                    **current, "identity": identity,
                    "endpoint": f"d{day}_{quote}", "holding_sessions": day,
                    "entry_date": dates[0], "exit_date": dates[day - 1],
                    "entry_open": entry_actual, "exit_price": actual_exit,
                    "entry_shares": 100, "exit_shares": shares,
                    "entry_cost_yen": entry_actual * 100,
                    "gross_return": gross, "cash_pl_100_yen": cash,
                    "cash_basis": "actual_session_journal_reconstructed" if share_aware else "legacy_adjusted_reference",
                })
            output.extend(identity_rows)
            completed_cache[identity] = identity_rows
        except ValueError as exc:
            rejection_cache[identity] = str(exc)
            rejected.append({"identity": identity, "symbol": row.symbol, "signal_date": row.date, **current, "reason": str(exc)})
    return pd.DataFrame(output), pd.DataFrame(rejected)


def periods(frame):
    yield "ALL_DESCRIPTIVE", frame
    yield "DEV_2023_2024", frame[frame.signal_date.dt.year.isin([2023, 2024])]
    for year, yearly in frame.groupby(frame.signal_date.dt.year):
        yield str(year), yearly


def stats(frame):
    returns = frame.gross_return
    return {
        "n": len(frame), "mean_pct": returns.mean() * 100,
        "median_pct": returns.median() * 100,
        "win_pct": (returns > 0).mean() * 100,
        "flat_count": int(returns.eq(0).sum()),
        "nonflat_win_pct": (returns[returns.ne(0)] > 0).mean() * 100,
        "loss10_pct": (returns <= -.1).mean() * 100,
        "loss10_count": int((returns <= -.1).sum()),
        "max_down_pct": returns.min() * 100,
        "top3_ex_mean_pct": returns.sort_values().iloc[:-3].mean() * 100 if len(returns) > 3 else np.nan,
        "cash_pl_100_yen": frame.cash_pl_100_yen.sum(),
        "entry_capital_sum_yen": frame.entry_cost_yen.sum(),
    }


def summarize(trades):
    metrics = []
    for arm, arm_trades in trades.groupby("arm"):
        groups = {name: arm_trades[arm_trades.selector.eq(name)] for name in sorted(arm_trades.selector.unique())}
        groups["all_conditions_stacked"] = arm_trades
        groups["all_conditions_unique"] = arm_trades.drop_duplicates(["identity", "endpoint"])
        for name, group in groups.items():
            for period, subset in periods(group):
                for endpoint, values in subset.groupby("endpoint"):
                    metrics.append({"arm": arm, "selector": name, "period": period, "endpoint": endpoint, **stats(values)})
    return pd.DataFrame(metrics)


def comparisons(metrics):
    records = []
    for (arm, selector), group in metrics.groupby(["arm", "selector"]):
        group = group.copy()
        group["day"] = group.endpoint.str.extract(r"d(\d+)_")[0].astype(int)
        group["quote_order"] = group.endpoint.str.endswith("_close").astype(int)
        dev = group[group.period.eq("DEV_2023_2024")].sort_values(["mean_pct", "day", "quote_order"], ascending=[False, True, True])
        fixed = dev.iloc[0].endpoint
        for period, subset in group.groupby("period"):
            retrospective = subset.sort_values(["mean_pct", "day", "quote_order"], ascending=[False, True, True]).iloc[0]
            chosen = subset[subset.endpoint.eq(fixed)].iloc[0]
            baseline = subset[subset.endpoint.eq(BASELINE)].iloc[0]
            records.append({
                "arm": arm, "selector": selector, "period": period,
                "dev_fixed_endpoint": fixed, "posthoc_best_endpoint": retrospective.endpoint,
                "baseline_n": int(baseline.n), "baseline_mean_pct": baseline.mean_pct,
                "baseline_win_pct": baseline.win_pct, "baseline_median_pct": baseline.median_pct,
                "fixed_mean_pct": chosen.mean_pct, "fixed_win_pct": chosen.win_pct,
                "fixed_median_pct": chosen.median_pct, "fixed_loss10_pct": chosen.loss10_pct,
                "fixed_top3_ex_mean_pct": chosen.top3_ex_mean_pct,
                "fixed_minus_baseline_mean_pt": chosen.mean_pct - baseline.mean_pct,
                "posthoc_best_mean_pct": retrospective.mean_pct,
                "posthoc_best_win_pct": retrospective.win_pct,
                "posthoc_best_median_pct": retrospective.median_pct,
                "posthoc_best_loss10_pct": retrospective.loss10_pct,
                "posthoc_best_top3_ex_mean_pct": retrospective.top3_ex_mean_pct,
                "posthoc_advantage_over_dev_fixed_pt": retrospective.mean_pct - chosen.mean_pct,
            })
    return pd.DataFrame(records)


def joint_cap_exit_comparisons(metrics):
    """Select one cap/exit pair on DEV, then evaluate that fixed policy.

    Each selector gets its own DEV choice. Across caps, selections and trade
    counts can differ; the comparison shares evaluation dates, not identities.
    Exact mean ties prefer the tighter positive cap, earlier day, then open.
    """
    records = []
    for selector, group in metrics.groupby("selector"):
        group = group.copy()
        group["day"] = group.endpoint.str.extract(r"d(\d+)_")[0].astype(int)
        group["quote_order"] = group.endpoint.str.endswith("_close").astype(int)
        cap_number = pd.to_numeric(group.arm.str.extract(r"(\d+)$")[0], errors="coerce")
        group["cap_order"] = cap_number.where(cap_number.gt(0), np.inf)
        sort_columns = ["mean_pct", "cap_order", "day", "quote_order", "arm"]
        ascending = [False, True, True, True, True]
        dev = group[group.period.eq("DEV_2023_2024")].sort_values(sort_columns, ascending=ascending)
        if dev.empty:
            raise ValueError(f"no DEV observations for joint policy selection: {selector}")
        choice = dev.iloc[0]
        tied_dev = dev[dev.mean_pct.eq(choice.mean_pct)]
        for period, subset in group.groupby("period"):
            fixed = subset[subset.arm.eq(choice.arm) & subset.endpoint.eq(choice.endpoint)]
            if fixed.empty:
                raise ValueError(f"DEV-selected cap/exit has no {period} observations: {selector}")
            chosen = fixed.iloc[0]
            retrospective = subset.sort_values(sort_columns, ascending=ascending).iloc[0]
            baseline = subset[subset.arm.eq("cap1000") & subset.endpoint.eq(BASELINE)]
            baseline_mean = baseline.iloc[0].mean_pct if not baseline.empty else np.nan
            records.append({
                "selector": selector, "period": period,
                "dev_grid_count": len(dev), "dev_fixed_arm": choice.arm,
                "dev_fixed_endpoint": choice.endpoint, "dev_selection_n": int(choice.n),
                "dev_tied_pairs": ",".join(f"{row.arm}:{row.endpoint}" for row in tied_dev.itertuples(index=False)),
                "fixed_n": int(chosen.n), "fixed_mean_pct": chosen.mean_pct,
                "fixed_win_pct": chosen.win_pct, "fixed_median_pct": chosen.median_pct,
                "fixed_loss10_pct": chosen.loss10_pct,
                "fixed_top3_ex_mean_pct": chosen.top3_ex_mean_pct,
                "fixed_max_down_pct": chosen.max_down_pct,
                "fixed_cash_pl_100_yen": chosen.cash_pl_100_yen,
                "cap1000_d5_close_mean_pct": baseline_mean,
                "fixed_minus_cap1000_d5_close_mean_pt": chosen.mean_pct - baseline_mean,
                "posthoc_best_arm": retrospective.arm,
                "posthoc_best_endpoint": retrospective.endpoint,
                "posthoc_best_mean_pct": retrospective.mean_pct,
                "posthoc_advantage_over_dev_fixed_pt": retrospective.mean_pct - chosen.mean_pct,
            })
    return pd.DataFrame(records)


def objective_leaders(metrics):
    records = []
    for (arm, selector, period), group in metrics.groupby(["arm", "selector", "period"]):
        for objective, column, ascending in (
            ("max_mean", "mean_pct", False), ("max_win", "win_pct", False),
            ("max_median", "median_pct", False), ("min_loss10", "loss10_pct", True),
            ("max_top3_ex_mean", "top3_ex_mean_pct", False),
        ):
            # Every endpoint has identical sample size. Ties use the earliest
            # exit, then open before close, to avoid claiming a unique optimum.
            ordered = group.copy()
            ordered["day"] = ordered.endpoint.str.extract(r"d(\d+)_")[0].astype(int)
            ordered["quote_order"] = ordered.endpoint.str.endswith("_close").astype(int)
            best = ordered.sort_values([column, "day", "quote_order"], ascending=[ascending, True, True]).iloc[0]
            tied = group[group[column].eq(best[column])].endpoint.tolist()
            records.append({"arm": arm, "selector": selector, "period": period, "objective": objective,
                "endpoint": best.endpoint, "tied_endpoints": ",".join(tied),
                **{name: best[name] for name in ("n", "mean_pct", "win_pct", "median_pct", "loss10_pct", "max_down_pct", "top3_ex_mean_pct", "cash_pl_100_yen")}})
    return pd.DataFrame(records)


def write_report(path, metrics, comparison, metadata, joint=None):
    name_map = {"volr20_low": "Silence", "body_pct_low": "Dive", "mean_rank_volr20_body_pct": "Shadow", "dual_top1_agreement": "Fusion", "dual_top1_agreement_g3_no_acute_selloff": "Balance", "all_conditions_stacked": "モード別積上げ", "all_conditions_unique": "銘柄均等"}
    lines = ["# Cloud 売却時点の固定選定比較", "", "既存の5営業日学習targetと選定銘柄を固定し、翌営業日寄付で入った同じ取引について売却時点だけを比較した。コストは0。全20時点の株価が揃う共通集合に限定した。", "", "2023–2024で平均騰落率が最大の売却時点を選び、同じ時点を2025と2026でも評価する。既に開いた履歴を使う時系列検証であり、未使用データによる独立OOSではない。全期間や各年の事後最高値は選択による楽観差を含む。", "", f"価格・選定基準: {metadata['basis_note']}", "", "|条件|期間|件数|5日終値平均|DEV固定売却|固定平均|平均差pt|固定勝率|固定中央値|−10%以下|Top3除外平均|事後best|事後best平均|楽観差pt|", "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for row in comparison.itertuples(index=False):
        lines.append(f"|{row.arm} {name_map.get(row.selector,row.selector)}|{row.period}|{row.baseline_n}|{row.baseline_mean_pct:.2f}%|{row.dev_fixed_endpoint}|{row.fixed_mean_pct:.2f}%|{row.fixed_minus_baseline_mean_pt:+.2f}|{row.fixed_win_pct:.2f}%|{row.fixed_median_pct:.2f}%|{row.fixed_loss10_pct:.2f}%|{row.fixed_top3_ex_mean_pct:.2f}%|{row.posthoc_best_endpoint}|{row.posthoc_best_mean_pct:.2f}%|{row.posthoc_advantage_over_dev_fixed_pt:.2f}|")
    if joint is not None and not joint.empty:
        joint_unique = joint[joint.selector.eq("all_conditions_unique") & joint.period.isin(["DEV_2023_2024", "2025", "2026", "ALL_DESCRIPTIVE"])].copy()
        period_order = {"DEV_2023_2024": 0, "2025": 1, "2026": 2, "ALL_DESCRIPTIVE": 3}
        joint_unique["period_order"] = joint_unique.period.map(period_order)
        joint_unique = joint_unique.sort_values("period_order")
        grid_count = int(joint_unique.dev_grid_count.iloc[0])
        lines += ["", f"価格上限と出口を同時に選ぶ比較では、銘柄均等のDEV=2023–2024にある{grid_count}組から平均が最大の1組を選び、その上限・出口の両方を2025と2026にも固定した。DEVも全期間も採用候補の選択を含む記述値であり、全期間最高値をOOS成績とは呼ばない。各モードの同様の比較は joint_cap_exit_dev_fixed.csv に保存した。", "", "|期間|DEV固定上限・出口|DEV選択件数|評価件数|固定平均|固定勝率|固定中央値|−10%以下|Top3除外平均|1000円・5日終値比pt|同期間事後best|事後平均|楽観差pt|", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
        for row in joint_unique.itertuples(index=False):
            lines.append(f"|{row.period}|{row.dev_fixed_arm}/{row.dev_fixed_endpoint}|{row.dev_selection_n}|{row.fixed_n}|{row.fixed_mean_pct:.2f}%|{row.fixed_win_pct:.2f}%|{row.fixed_median_pct:.2f}%|{row.fixed_loss10_pct:.2f}%|{row.fixed_top3_ex_mean_pct:.2f}%|{row.fixed_minus_cap1000_d5_close_mean_pt:+.2f}|{row.posthoc_best_arm}/{row.posthoc_best_endpoint}|{row.posthoc_best_mean_pct:.2f}%|{row.posthoc_advantage_over_dev_fixed_pt:.2f}|")
        lines += ["", "これは時間順に選択・評価する手順の再現である。上限変更は学習母集団と選定銘柄も変えるため、上限間の件数・銘柄は同一ではない。各上限内の20出口比較は同一銘柄、上限間比較は共通の評価日で行い、価格上限そのものの因果効果を識別した実験とは区別する。既に開いた履歴による時系列検証であり、完全に未使用の独立OOSではない。同平均なら厳しい正の上限、早い売却日、寄付を優先し、同率組もCSVに残した。"]
    lines += ["", "20売却時点すべての平均・中央値・勝率・損失率・100株損益は metrics.csv、取引単位は trades.csv、共通集合からの除外は excluded.csv と policy_excluded.csv に保存した。objective_leaders.csv は最大平均・最大勝率・最大中央値・最小−10%以下率・Top3除外後最大平均の時点を比較する。同率では早い売却時点を先に表示し、同率時点も列挙する。Top3除外平均は各条件・期間・売却時点内の最大騰落率3件を除いた感度分析である。勝率の0%取引は現行Cloudと同じく分母に含め、分母から除く参考値も保存した。", "", "翌営業日寄付で買って同じ寄付で売るd1_openは、コスト0なら損益0となる対照値である。最小損失率の候補に出ても実際の別注文で無コストの同時約定が可能という意味ではない。最悪値は売却時点の単一取引で最大の損失を指し、保有途中の最大下落ではない。", "", "売買手数料・スプレッド・滑りは0、配当は含めない。100株損益は検証済みイベント履歴を価格snapshot日までに絞って当時株単位を復元した。端株の現金化を要する取引は推測せず共通集合から除外した。", "", "本研究は売却ルール採用や公開レポートの更新を行わない。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(directory, metrics):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    for (arm, period), subset in metrics[metrics.period.isin(("ALL_DESCRIPTIVE", "DEV_2023_2024", "2025", "2026"))].groupby(["arm", "period"]):
        fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=True)
        for axis, (selector, group) in zip(axes.flat, subset.groupby("selector")):
            for quote in ("open", "close"):
                series = group[group.endpoint.str.endswith(f"_{quote}")].copy()
                series["day"] = series.endpoint.str.extract(r"d(\d+)_")[0].astype(int)
                series = series.sort_values("day")
                axis.plot(series.day, series.mean_pct, marker="o", label=quote)
            axis.axvline(5, color="gray", ls="--", alpha=.5)
            axis.axhline(0, color="gray", lw=.5)
            axis.set_title(SELECTOR_LABELS.get(selector, selector))
            axis.set_ylabel("Mean return (%)")
            axis.set_xlabel("Sessions after signal")
            axis.set_xticks(range(1, 11))
            axis.grid(alpha=.25)
            axis.legend()
        for axis in axes.flat[len(subset.selector.unique()):]:
            axis.set_visible(False)
        fig.suptitle(f"{arm}: fixed selections, entry next-session open / {period}")
        fig.tight_layout()
        fig.savefig(directory / f"mean_curve_{arm}_{period.lower()}.png", dpi=180)
        fig.savefig(directory / f"mean_curve_{arm}_{period.lower()}.svg")
        plt.close(fig)
    if metrics.arm.nunique() > 1:
        for period in ("ALL_DESCRIPTIVE", "DEV_2023_2024", "2025", "2026"):
            fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
            unique = metrics[metrics.period.eq(period) & metrics.selector.eq("all_conditions_unique")]
            for axis, quote in zip(axes, ("open", "close")):
                for arm, group in unique[unique.endpoint.str.endswith(f"_{quote}")].groupby("arm"):
                    group = group.copy()
                    group["day"] = group.endpoint.str.extract(r"d(\d+)_")[0].astype(int)
                    group = group.sort_values("day")
                    axis.plot(group.day, group.mean_pct, marker="o", label=arm)
                axis.set_title(f"Exit {quote} / unique trades")
                axis.set_xlabel("Sessions after signal")
                axis.set_ylabel("Mean return (%)")
                axis.set_xticks(range(1, 11))
                axis.axvline(5, color="gray", ls="--", alpha=.5)
                axis.axhline(0, color="gray", lw=.5)
                axis.grid(alpha=.25)
                axis.legend()
            fig.suptitle(f"Cap and exit interaction on common dates / {period}")
            fig.tight_layout()
            fig.savefig(directory / f"cap_exit_mean_unique_{period.lower()}.png", dpi=180)
            fig.savefig(directory / f"cap_exit_mean_unique_{period.lower()}.svg")
            plt.close(fig)
    return True


def main():
    run_script = Path(__file__).resolve()
    run_script_bytes = run_script.read_bytes()
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path)
    parser.add_argument("--selection-arm", action="append", default=[], help="ARM=CSV; repeat for cap-by-exit grid")
    parser.add_argument("--daily", type=Path, required=True)
    parser.add_argument("--source-cutoff", required=True)
    parser.add_argument("--actions", type=Path)
    parser.add_argument("--quarantined-dates", type=Path)
    parser.add_argument("--bad-bars", type=Path)
    parser.add_argument("--cap-summary", type=Path, help="Final V2 completion gate and common tie-date union")
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--stage", default="preliminary_legacy_selection")
    args = parser.parse_args()
    cap_summary, receipt_count = verified_cap_summary(args.cap_summary) if args.cap_summary else (None, None)
    if args.stage.startswith("corrected") and cap_summary is None:
        raise ValueError("a corrected final run requires --cap-summary")
    args.out.mkdir(parents=True, exist_ok=True)
    script_snapshot = args.out / "compare_exits_executed.py"
    script_snapshot.write_bytes(run_script_bytes)
    if cap_summary is not None:
        if len(args.selection_arm) != 6 or args.selected:
            raise ValueError("the final study requires all six completed selection arms")
        args.quarantined_dates = args.out / "quarantined_dates_from_cap_summary.json"
        args.quarantined_dates.write_text(json.dumps(cap_summary["quarantined_dates"], ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    inputs = [("cap1000", args.selected)] if args.selected else []
    for value in args.selection_arm:
        arm, path = value.split("=", 1)
        inputs.append((arm, Path(path)))
    if not inputs or len({arm for arm, _ in inputs}) != len(inputs):
        raise ValueError("provide unique --selected or --selection-arm inputs")
    parts, common_day_flags = [], set()
    for arm, path in inputs:
        frame = pd.read_csv(path, parse_dates=["date"], dtype={"symbol": str})
        if "comparison_common_day_excluded" in frame:
            flag = frame.comparison_common_day_excluded.astype(str).str.lower().isin(["true", "1"])
            common_day_flags.update(frame.loc[flag, "date"].tolist())
        parts.append(frame[["date", "symbol", "selector"]].drop_duplicates().assign(arm=arm))
    selected = pd.concat(parts, ignore_index=True)
    selected["entry_date"] = selected.date.map(lambda date: pd.Timestamp(add_bank_business_days(date.date(), 1)))
    count_before = len(selected)
    policy_excluded = []
    eligible = performance_eligible(selected)
    policy_excluded.append(selected[~selected.index.isin(eligible.index)].assign(reason="reviewed_entry_feasibility_reference_only"))
    selected = eligible
    restrictions_path = ROOT / "weak_early_beta/state/jpx_restricted_symbols_latest.json"
    restriction_snapshot = json.loads(restrictions_path.read_text(encoding="utf-8"))
    restricted = restricted_mask(selected.rename(columns={"date": "signal_date"}), restriction_snapshot["symbols"])
    policy_excluded.append(selected[restricted].assign(reason="causal_jpx_delisting_decision"))
    selected = selected[~restricted].copy()
    policy_excluded.append(selected[selected.date.isin(common_day_flags)].assign(reason="cap_comparison_common_day_flag"))
    selected = selected[~selected.date.isin(common_day_flags)].copy()
    if args.quarantined_dates:
        quarantined = {record["date"] for record in json.loads(args.quarantined_dates.read_text(encoding="utf-8"))}
        policy_excluded.append(selected[selected.date.dt.strftime("%Y-%m-%d").isin(quarantined)].assign(reason="unresolved_cap_selection_tie_date_union"))
        selected = selected[~selected.date.dt.strftime("%Y-%m-%d").isin(quarantined)]
    source_cutoff = pd.Timestamp(args.source_cutoff)
    raw = load_prices(args.daily, set(selected.symbol), args.bad_bars)
    raw = raw[raw.date.le(source_cutoff)].copy()
    actions = load_actions(args.actions, source_cutoff)
    trades, excluded = evaluate(selected, raw, actions, args.actions is not None)
    per_arm_metrics = summarize(trades) if not trades.empty else pd.DataFrame()
    if len(inputs) > 1 and not excluded.empty:
        bad_dates = set(excluded.signal_date)
        additional = trades[trades.signal_date.isin(bad_dates)].drop_duplicates(["arm", "identity", "selector"])
        if not additional.empty:
            additional = additional[["identity", "symbol", "signal_date", "selector", "arm"]].assign(reason="common_date_quarantine_from_another_arm")
            excluded = pd.concat([excluded, additional], ignore_index=True)
        trades = trades[~trades.signal_date.isin(bad_dates)].copy()
    if trades.empty:
        raise ValueError("no common complete endpoint cohort")
    metrics = summarize(trades)
    comparison = comparisons(metrics)
    joint = joint_cap_exit_comparisons(metrics)
    leaders = objective_leaders(metrics)
    metadata = {
        "stage": args.stage, "selection_inputs": [{"arm": arm, "path": str(path), "sha256": digest(path)} for arm, path in inputs],
        "cap_summary_path": str(args.cap_summary) if args.cap_summary else None,
        "cap_summary_sha256": digest(args.cap_summary) if args.cap_summary else None,
        "verified_monthly_model_receipts": receipt_count,
        "script_path": str(run_script), "script_snapshot": str(script_snapshot), "script_sha256": hashlib.sha256(run_script_bytes).hexdigest(),
        "daily_path": str(args.daily), "daily_sha256": digest(args.daily), "source_cutoff": args.source_cutoff,
        "actions_path": str(args.actions) if args.actions else None,
        "actions_sha256": digest(args.actions) if args.actions else None,
        "bad_bars_path": str(args.bad_bars) if args.bad_bars else None,
        "bad_bars_sha256": digest(args.bad_bars) if args.bad_bars else None,
        "quarantined_dates_sha256": digest(args.quarantined_dates) if args.quarantined_dates else None,
        "entry_registry_sha256": digest(ROOT / "weak_early_beta/state/entry_feasibility_exclusions.csv"),
        "jpx_restriction_sha256": digest(restrictions_path),
        "selection_rows_before_policy": count_before, "selection_rows_after_policy": len(selected),
        "common_day_flag_count": len(common_day_flags),
        "endpoint_bad_date_union_applied_to_all_arms": len(inputs) > 1,
        "common_selector_rows": int(len(trades) / 20),
        "common_unique_trades": int(trades.identity.nunique()), "excluded_selector_rows": len(excluded),
        "selection_target": "Original fixed 5-session next-open-to-close learning target; no retraining or re-selection for exit endpoints.",
        "entry": "signal+1 official bank business session open", "exits": [f"d{day}_{quote}" for day, quote in ENDPOINTS],
        "cost_pct": 0, "win": "gross_return>0; flat trades in denominator",
        "dividends_included": False,
        "max_down_pct": "Worst completed trade return at an endpoint; not intraholding drawdown.",
        "cohort": "All twenty endpoints available and usable for every retained identity; fractional corporate-action lots rejected.",
        "holdout": "Endpoint chosen on 2023-2024 only; 2025 temporal validation and 2026 reporting; already-opened retrospective data, not untouched OOS.",
        "joint_cap_exit_selection": "One arm/endpoint pair per selector chosen by DEV 2023-2024 mean; cap and exit both fixed for 2025/2026. Exact ties: tighter positive cap, earlier day, open. Whole-period maxima descriptive only.",
        "joint_dev_grid_counts": {str(selector): int(count) for selector, count in joint.groupby("selector").dev_grid_count.first().items()},
        "basis_note": "予備の旧調整価格・旧選定。最新sourceに大幅revisionが見つかっているため当時株単位の価格上限で再選定する前の参考値。" if args.stage.startswith("preliminary") else "分割併合確認後の当時株単位による価格上限・固定選定。ベンダーの最新取得履歴を使い、過去時点の原本そのものを復元したデータではない。価格元データの制約は別途source監査参照。",
        "cash_basis": "journal reconstructed actual entry100shares" if args.actions else "adjusted reference only; actual cash not yet verified",
        "no_production_mutations": True,
    }
    if cap_summary is not None and (metadata["daily_sha256"] != cap_summary["metadata"]["source_sha256"] or metadata["actions_sha256"] != cap_summary["metadata"]["actions_sha256"]):
        raise ValueError("exit source/actions differ from the completed cap-model snapshot")
    trades.to_csv(args.out / "trades.csv", index=False, date_format="%Y-%m-%d", float_format="%.17g")
    excluded.to_csv(args.out / "excluded.csv", index=False, date_format="%Y-%m-%d")
    pd.concat(policy_excluded, ignore_index=True).to_csv(args.out / "policy_excluded.csv", index=False, date_format="%Y-%m-%d")
    metrics.to_csv(args.out / "metrics.csv", index=False, float_format="%.12g")
    if len(inputs) > 1:
        per_arm_metrics.to_csv(args.out / "per_arm_before_date_union_metrics.csv", index=False, float_format="%.12g")
    comparison.to_csv(args.out / "dev_fixed_vs_posthoc.csv", index=False, float_format="%.12g")
    joint.to_csv(args.out / "joint_cap_exit_dev_fixed.csv", index=False, float_format="%.12g")
    leaders.to_csv(args.out / "objective_leaders.csv", index=False, float_format="%.12g")
    metadata["standard_matplotlib_plots_written"] = write_plots(args.out, metrics)
    (args.out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(args.out / "report.md", metrics, comparison, metadata, joint)
    print(json.dumps({"stage": args.stage, "common_selector_rows": metadata["common_selector_rows"], "common_unique_trades": metadata["common_unique_trades"], "excluded": len(excluded), "metrics_rows": len(metrics)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
