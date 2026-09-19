"""Build coverage-aware yearly/total comparison for the fixed research candidates."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WEAK_PATH = ROOT / "research/repro_packs/weak_early_exact_v1/output/full_period_2026/normalized_yearly_and_total_metrics.csv"
CLOUD_PATH = ROOT / "research/repro_packs/cloud_monster_legacy_exact_v1/output/canonical_next_open_fifth_close/canonical_metrics_by_year_and_total.csv"
OUT_DIR = ROOT / "research/comparisons/cloud_weak_early_20260919"
EXPECTED = {
    WEAK_PATH: "c40067044e2dd69fa40031f49548ae3b76e3511e594fd24613d74b4a11091ce6",
    CLOUD_PATH: "8df1b9481eca98494b9ebb06b30c70faa469c95a760aadd1c2a88dd91c27923f",
}
LABELS = {
    "volr20_low": "volr20 LOW",
    "body_pct_low": "body_pct LOW",
    "mean_rank_volr20_body_pct": "mean-rank(volr20, body_pct)",
    "dual_top1_agreement": "DUAL_TOP1_AGREEMENT",
    "dual_top1_agreement_g3_no_acute_selloff": "DUAL + G3",
    "cloud_monster_canonical": "Cloud Monster legacy signals (canonical endpoint)",
}
RANK_HIGH = ["mean_pct", "median_pct", "win_pct", "top3_ex_mean_pct", "max_down_pct"]
RANK_LOW = ["minus10_pct", "minus20_pct"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rank(frame: pd.DataFrame) -> pd.DataFrame:
    ranked = frame.copy()
    ordinal = []
    for field in RANK_HIGH:
        column = f"rank__{field}"
        ranked[column] = ranked[field].rank(method="average", ascending=False)
        ordinal.append(column)
    for field in RANK_LOW:
        column = f"rank__{field}"
        ranked[column] = ranked[field].rank(method="average", ascending=True)
        ordinal.append(column)
    ranked["ordinal_score"] = ranked[ordinal].mean(axis=1)
    ranked = ranked.sort_values(
        ["ordinal_score", "top3_ex_mean_pct", "mean_pct", "median_pct", "win_pct", "n"],
        ascending=[True, False, False, False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    return ranked


def pct(value: float) -> str:
    return f"{float(value):+.2f}%"


def cash(value: float) -> str:
    return f"¥{float(value):,.0f}"


def table(frame: pd.DataFrame, include_rank: bool = True) -> list[str]:
    rank_head = "Rank | " if include_rank else ""
    rank_div = "---:|" if include_rank else ""
    lines = [
        f"| {rank_head}Candidate | n | Mean | Median | Win | +10 | +20 | -10 | -20 | Max up | Max down | Top3-ex | 100株P/L |",
        f"|{rank_div}---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in frame.to_dict(orient="records"):
        rank_cell = f"{int(row['rank'])} | " if include_rank else ""
        lines.append(
            f"| {rank_cell}{LABELS[row['selector']]} | {int(row['n'])} | {pct(row['mean_pct'])} | "
            f"{pct(row['median_pct'])} | {pct(row['win_pct'])} | {pct(row['plus10_pct'])} | "
            f"{pct(row['plus20_pct'])} | {pct(row['minus10_pct'])} | {pct(row['minus20_pct'])} | "
            f"{pct(row['max_up_pct'])} | {pct(row['max_down_pct'])} | "
            f"{pct(row['top3_ex_mean_pct'])} | {cash(row['one_hundred_shares_pl_yen'])} |"
        )
    return lines


def main() -> None:
    for path, expected in EXPECTED.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"input hash drift: {path} {actual}")

    weak = pd.read_csv(WEAK_PATH, dtype={"selector": str, "period": str})
    weak = weak[weak["source_status"].eq("EXACT_CANONICAL_ROWS")].copy()
    cloud_raw = pd.read_csv(CLOUD_PATH, dtype={"period": str})
    cloud = pd.DataFrame(
        {
            "selector": "cloud_monster_canonical",
            "period": cloud_raw["period"].replace({"TOTAL": "2026-only-total"}),
            "source_status": "EXACT_CANONICAL_ROWS",
            "n": cloud_raw["n"],
            "mean_pct": cloud_raw["mean"] * 100,
            "median_pct": cloud_raw["median"] * 100,
            "win_pct": cloud_raw["win"] * 100,
            "plus10_pct": cloud_raw["plus10"] * 100,
            "plus20_pct": cloud_raw["plus20"] * 100,
            "minus10_pct": cloud_raw["minus10"] * 100,
            "minus20_pct": cloud_raw["minus20"] * 100,
            "max_up_pct": cloud_raw["max_up"] * 100,
            "max_down_pct": cloud_raw["max_down"] * 100,
            "top3_ex_mean_pct": cloud_raw["top3_excluded_mean"] * 100,
            "one_hundred_shares_pl_yen": cloud_raw["pl_100_shares_yen"],
        }
    )
    annual = pd.concat([weak[weak["period"].isin(["2023", "2024", "2025", "2026"])], cloud[cloud["period"].eq("2026")]], ignore_index=True)
    annual_ranked = pd.concat(
        [rank(group).assign(period=period) for period, group in annual.groupby("period", sort=True)],
        ignore_index=True,
    )
    weak_total = rank(weak[weak["period"].eq("2023-2026")].copy()).assign(period="2023-2026")
    cloud_total = cloud[cloud["period"].eq("2026-only-total")].copy()
    cloud_total["rank"] = np.nan
    cloud_total["ordinal_score"] = np.nan

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    annual_path = OUT_DIR / "yearly_ranked_metrics.csv"
    total_path = OUT_DIR / "coverage_aware_total_metrics.csv"
    annual_ranked.to_csv(annual_path, index=False, lineterminator="\n", float_format="%.17g")
    pd.concat([weak_total, cloud_total], ignore_index=True).to_csv(
        total_path, index=False, lineterminator="\n", float_format="%.17g"
    )

    lines = [
        "# Cloud Monster + Weak+Early 固定候補比較 — 2026-09-19",
        "",
        "Status: **REPORTING-ONLY / FIXED IDENTITIES / NO RETUNE / PRODUCTION NO-GO**",
        "",
        "全候補の共通endpointは signal T → next official XTKS session open → fifth official XTKS session close、cost 0%、win=gross>0。Cloud Monsterは歴史的63 signal identityを変えずendpointだけcanonical化した。順位は既存Weak+Early契約と同じ7指標（Mean、Median、Win、Top3-ex、Max down、-10、-20）の等重みordinal平均で、2026の記述比較にのみ使う。なおCloudは3〜8月、Weak+Earlyは1〜9月初旬までで、観測月は完全一致しない。",
        "",
        "## 年別成績と順位",
    ]
    for period in ["2023", "2024", "2025", "2026"]:
        lines += ["", f"### {period}", ""]
        rows = annual_ranked[annual_ranked["period"].eq(period)].sort_values("rank")
        lines += table(rows)
        if period != "2026":
            lines += ["", "Cloud Monster legacyは2026-03-01以降の固定研究で、この年の行は存在しないため順位対象外。"]

    lines += [
        "",
        "## 全期間トータル（coverage-aware）",
        "",
        "Weak+Early 5候補のexact totalは2023-2026。Cloud Monster exactは2026-03-01〜2026-08-31だけなので、同じ全期間順位へ混ぜない。Cloudの比較順位は上の共通2026表を正とする。",
        "",
        "### Weak+Early 2023-2026 total",
        "",
    ]
    lines += table(weak_total.sort_values("rank"))
    lines += ["", "### Cloud Monster 2026-only total", ""]
    lines += table(cloud_total, include_rank=False)
    lines += [
        "",
        "## 判定",
        "",
        "- 2026年内の記述比較ではCloud Monsterを含む6候補を同一endpoint・同一7指標で順位付けしたが、観測月差があるため完全なapples-to-apples比較ではない。",
        "- 2023-2026総合順位は、同じ4年間を持つWeak+Early 5候補だけの比較であり、Cloud Monsterを不当に混ぜていない。",
        "- この順位はreporting-only。2026成績を閾値、feature、gate、候補identityの選択やretuneには使用しない。",
        "- 2022はhistorical row identity未回収のため、このexact rankingから除外した。",
        "",
        "## Receipts",
        "",
        f"- Weak normalized metrics SHA-256: `{sha256(WEAK_PATH)}`",
        f"- Cloud canonical metrics SHA-256: `{sha256(CLOUD_PATH)}`",
        f"- Yearly ranked output SHA-256: `{sha256(annual_path)}`",
        f"- Coverage-aware total output SHA-256: `{sha256(total_path)}`",
    ]
    report_path = OUT_DIR / "CLOUD_WEAK_EARLY_COMPARISON_20260919.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path)
    print(annual_ranked[annual_ranked["period"].eq("2026")][["rank", "selector", "ordinal_score", "mean_pct", "median_pct", "win_pct", "top3_ex_mean_pct"]].sort_values("rank").to_string(index=False))


if __name__ == "__main__":
    main()
