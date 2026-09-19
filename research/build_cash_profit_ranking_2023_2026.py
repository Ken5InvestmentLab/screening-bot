"""Rank fixed candidates by exact 100-share cash profit for 2023-2026."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WEAK = ROOT / "research/repro_packs/weak_early_exact_v1/output"
CLOUD = ROOT / "research/repro_packs/cloud_monster_legacy_exact_v1/output/canonical_next_open_fifth_close/canonical_trade_rows_next_open_fifth_close.csv"
OUT = ROOT / "research/comparisons/cash_profit_ranking_2023_2026"
SELECTORS = [
    "volr20_low",
    "body_pct_low",
    "mean_rank_volr20_body_pct",
    "dual_top1_agreement",
    "dual_top1_agreement_g3_no_acute_selloff",
]
LABELS = {
    "volr20_low": "volr20 LOW",
    "body_pct_low": "body_pct LOW",
    "mean_rank_volr20_body_pct": "mean-rank(volr20, body_pct)",
    "dual_top1_agreement": "DUAL_TOP1_AGREEMENT",
    "dual_top1_agreement_g3_no_acute_selloff": "DUAL + G3",
    "cloud_monster_canonical": "Cloud Monster canonical",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows() -> dict[str, pd.DataFrame]:
    rows = {}
    for selector in SELECTORS:
        historical_path = WEAK / f"canonical_trade_rows_{selector}.csv"
        current_path = WEAK / "full_period_2026" / f"canonical_trade_rows_{selector}_2026.csv"
        historical = pd.read_csv(historical_path, dtype={"symbol": str})
        current = pd.read_csv(
            current_path,
            dtype={"symbol": str},
        )
        historical_years = set(pd.to_datetime(historical["signal_date"]).dt.year)
        current_years = set(pd.to_datetime(current["signal_date"]).dt.year)
        if historical_years != {2023, 2024, 2025} or current_years != {2026}:
            raise ValueError(
                f"Unexpected year coverage for {selector}: historical={historical_years}, current={current_years}"
            )
        frame = pd.concat([historical, current], ignore_index=True)
        frame = frame.rename(columns={"fifth_xtks_exit_date": "exit_date", "fifth_xtks_exit_close": "exit_close"})
        rows[selector] = frame[["signal_date", "symbol", "entry_date", "entry_open", "exit_date", "exit_close", "gross_return"]].copy()
    cloud = pd.read_csv(CLOUD, dtype={"symbol": str})
    if set(pd.to_datetime(cloud["signal_date"]).dt.year) != {2026}:
        raise ValueError("Cloud Monster canonical rows must remain 2026-only")
    rows["cloud_monster_canonical"] = cloud[["signal_date", "symbol", "entry_date", "entry_open", "exit_date", "exit_close", "gross_return"]].copy()
    for selector, frame in rows.items():
        if frame.isna().any().any():
            raise ValueError(f"Missing canonical trade field for {selector}")
        recomputed = frame["exit_close"] / frame["entry_open"] - 1.0
        # Historical canonical CSVs preserve source prices with a maximum
        # floating-point serialization delta below 1e-11 in gross_return.
        if (recomputed - frame["gross_return"]).abs().max() > 1e-11:
            raise ValueError(f"Canonical return mismatch for {selector}")
    return rows


def input_receipts() -> list[dict[str, str]]:
    paths = []
    for selector in SELECTORS:
        paths.extend(
            [
                WEAK / f"canonical_trade_rows_{selector}.csv",
                WEAK / "full_period_2026" / f"canonical_trade_rows_{selector}_2026.csv",
            ]
        )
    paths.append(CLOUD)
    return [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
        for path in paths
    ]


def cash_metrics(frame: pd.DataFrame, selector: str, period: str) -> dict:
    data = frame.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"])
    data["exit_date"] = pd.to_datetime(data["exit_date"])
    data["entry_cost"] = data["entry_open"] * 100
    data["exit_proceeds"] = data["exit_close"] * 100
    data["cash_profit"] = data["exit_proceeds"] - data["entry_cost"]
    events = pd.concat(
        [
            pd.DataFrame({"date": data["entry_date"], "order": 0, "cash_flow": -data["entry_cost"]}),
            pd.DataFrame({"date": data["exit_date"], "order": 1, "cash_flow": data["exit_proceeds"]}),
        ],
        ignore_index=True,
    ).sort_values(["date", "order"], kind="mergesort")
    cumulative = events["cash_flow"].cumsum()
    starting_cash = float(-min(0.0, cumulative.min()))
    profit = float(data["cash_profit"].sum())
    gross_deployed = float(data["entry_cost"].sum())
    return {
        "selector": selector,
        "candidate": LABELS[selector],
        "period": period,
        "coverage": "2026-only" if selector == "cloud_monster_canonical" else "2023-2026",
        "n": int(len(data)),
        "minimum_starting_cash_yen": starting_cash,
        "ending_cash_yen": starting_cash + profit,
        "cash_profit_yen": profit,
        "increase_on_starting_cash_pct": profit / starting_cash * 100 if starting_cash else 0.0,
        "gross_deployed_capital_yen": gross_deployed,
        "profit_on_gross_deployed_pct": profit / gross_deployed * 100 if gross_deployed else 0.0,
        "mean_trade_return_pct": float(data["gross_return"].mean() * 100),
    }


def yen(value: float) -> str:
    return f"¥{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def render_table(frame: pd.DataFrame) -> list[str]:
    lines = [
        "| Rank | Candidate | Coverage | n | 必要元資金 | 最終資金 | 稼いだ金額 | 元資金増加率 | 延べ投入額 | 延べ投入利益率 | Mean |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in frame.to_dict(orient="records"):
        lines.append(
            f"| {int(row['cash_rank'])} | {row['candidate']} | {row['coverage']} | {int(row['n'])} | "
            f"{yen(row['minimum_starting_cash_yen'])} | {yen(row['ending_cash_yen'])} | "
            f"{yen(row['cash_profit_yen'])} | {pct(row['increase_on_starting_cash_pct'])} | "
            f"{yen(row['gross_deployed_capital_yen'])} | {pct(row['profit_on_gross_deployed_pct'])} | "
            f"{pct(row['mean_trade_return_pct'])} |"
        )
    return lines


def main() -> None:
    rows = load_rows()
    yearly = []
    totals = []
    for selector, frame in rows.items():
        frame["signal_date"] = pd.to_datetime(frame["signal_date"])
        for year, group in frame.groupby(frame["signal_date"].dt.year):
            yearly.append(cash_metrics(group, selector, str(year)))
        totals.append(cash_metrics(frame, selector, "TOTAL"))
    yearly_frame = pd.DataFrame(yearly)
    yearly_frame["cash_rank"] = yearly_frame.groupby("period")["cash_profit_yen"].rank(
        method="min", ascending=False
    ).astype(int)
    total_frame = pd.DataFrame(totals)
    total_frame["cash_rank"] = total_frame["cash_profit_yen"].rank(method="min", ascending=False).astype(int)
    comparable = total_frame[total_frame["coverage"].eq("2023-2026")].copy()
    comparable["cash_rank"] = comparable["cash_profit_yen"].rank(method="min", ascending=False).astype(int)

    OUT.mkdir(parents=True, exist_ok=True)
    yearly_path = OUT / "yearly_cash_profit_ranking.csv"
    total_path = OUT / "total_cash_profit_ranking_with_cloud_reference.csv"
    comparable_path = OUT / "comparable_2023_2026_cash_profit_ranking.csv"
    yearly_frame.sort_values(["period", "cash_rank"]).to_csv(yearly_path, index=False, lineterminator="\n", float_format="%.17g")
    total_frame.sort_values("cash_rank").to_csv(total_path, index=False, lineterminator="\n", float_format="%.17g")
    comparable.sort_values("cash_rank").to_csv(comparable_path, index=False, lineterminator="\n", float_format="%.17g")

    receipt = {
        "identity": "CASH_PROFIT_RANKING_2023_2026_V1",
        "status": "EXACT_CANONICAL_ROWS",
        "selection_policy": "No candidate, feature, gate, or threshold was selected from these outcomes.",
        "contract": {
            "shares_per_signal": 100,
            "entry": "next official XTKS session open",
            "exit": "fifth official XTKS session close",
            "cost_pct": 0,
            "tax_pct": 0,
            "position_sizing": "fixed 100 shares; no compounding",
            "same_day_cash_event_order": "all entries at open before all exits at close",
            "minimum_starting_cash": "negative of the minimum cumulative cash flow, floored at zero",
            "ranking_key": "cash_profit_yen descending",
            "2022": "excluded because exact trade rows and entry prices are unavailable",
            "cloud_monster": "2026-only reference; excluded from comparable 2023-2026 ranking",
        },
        "inputs": input_receipts(),
        "outputs": {
            comparable_path.relative_to(ROOT).as_posix(): sha256(comparable_path),
            total_path.relative_to(ROOT).as_posix(): sha256(total_path),
            yearly_path.relative_to(ROOT).as_posix(): sha256(yearly_path),
        },
    }
    receipt_path = OUT / "cash_profit_ranking_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 2023–2026 実価格・100株キャッシュ利益ランキング",
        "",
        "Status: **EXACT CANONICAL ROWS / COST 0% / 100 SHARES PER SIGNAL**",
        "",
        "必要元資金は、各signalを100株ずつ売買し、entry日の寄付きで資金を支出、exit日の引けで売却代金を回収すると仮定したとき、口座残高を一度もマイナスにしない最小初期現金。延べ投入額は全entry costの合計。固定100株なので複利・position sizing・手数料・税金は含めない。",
        "",
        "## 比較可能な2023–2026トータル順位",
        "",
    ]
    lines += render_table(comparable.sort_values("cash_rank"))
    lines += [
        "",
        "## Cloud Monsterを参考表示した利用可能全期間順位",
        "",
        "Cloud Monsterは2026-03〜08だけなので、金額順位には表示するが2023–2026の同期間勝敗とは扱わない。",
        "",
    ]
    lines += render_table(total_frame.sort_values("cash_rank"))
    lines += ["", "## 年別順位", ""]
    for period in ["2023", "2024", "2025", "2026"]:
        lines += [f"### {period}", ""]
        lines += render_table(yearly_frame[yearly_frame["period"].eq(period)].sort_values("cash_rank"))
        lines.append("")
    lines += [
        "## Receipts",
        "",
        f"- Comparable total CSV SHA-256: `{sha256(comparable_path)}`",
        f"- All available total CSV SHA-256: `{sha256(total_path)}`",
        f"- Yearly CSV SHA-256: `{sha256(yearly_path)}`",
        f"- Machine receipt SHA-256: `{sha256(receipt_path)}`",
    ]
    report_path = OUT / "CASH_PROFIT_RANKING_2023_2026.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(comparable.sort_values("cash_rank")[["cash_rank", "candidate", "n", "minimum_starting_cash_yen", "cash_profit_yen", "increase_on_starting_cash_pct", "gross_deployed_capital_yen", "profit_on_gross_deployed_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
