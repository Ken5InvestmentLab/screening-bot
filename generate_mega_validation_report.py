#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a validation report for mega-return candidate scoring ideas.

This script is intentionally read-only against the production bot. It fetches
the same Google Sheets data used by the optimizer, evaluates fixed candidate
condition sets, and writes a Markdown report for human review.
"""

from __future__ import annotations

import argparse
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import optimize_screener as opt


JST = ZoneInfo("Asia/Tokyo")
DEFAULT_OUTPUT = os.path.join("reports", "mega_validation_report_latest.md")

CONDITION_LABELS = {
    "ema75": "close > EMA75",
    "ema25": "close > EMA25",
    "vol20": "出来高 >= 20日平均x2.0",
    "vol15": "出来高 >= 20日平均x1.5",
    "vol12": "出来高 >= 20日平均x1.2",
    "vol30": "出来高 >= 20日平均x3.0",
    "sbull": "陽線実体 >= 0.5%",
    "body1": "陽線実体 >= 1.0%",
    "body2": "陽線実体 >= 2.0%",
    "macdgc": "MACD GC 3日以内",
    "macdpos": "MACD hist > 0",
    "atr5": "ATR < 5%",
    "atr3": "ATR < 3%",
    "atr7": "ATR < 7%",
    "hb20": "20日高値更新",
    "lower_wick50": "下ヒゲ優位",
    "pre_decline15": "20日高値から-15%以上",
    "stoch75": "Stoch >= 75",
    "stoch60": "Stoch >= 60",
    "rsi5070": "RSI 50-70",
    "rsi4060": "RSI 40-60",
    "bb80": "BB位置 >= 80%",
    "ich_tk": "一目: 転換線 > 基準線",
    "ich_price_tenkan": "一目: close > 転換線",
    "ich_price_kijun": "一目: close > 基準線",
    "ich_cloud_above": "一目: close > 雲上限",
    "ich_cloud_green": "一目: 先行雲が陽転",
    "ich_chikou": "一目: close > 26日前終値",
    "ich_kumo_break": "一目: 雲上抜け",
    "rci9_os": "RCI9 <= -50",
    "rci26_os": "RCI26 <= -50",
    "rci9_up": "RCI9反転上向き",
    "pre_down3": "直近3日連続下落後",
    "gap_up": "ギャップアップ",
    "bb_lower": "BB位置 <= 20%",
    "cci_os": "CCI <= -100",
    "smbull_seq2": "2連小陽線後",
    "smbull_seq3": "3連小陽線後",
}

CANDIDATES = [
    {
        "id": "mega5_rebound",
        "label": "Mega5 短期リバウンド",
        "eval_days": 5,
        "target": 0.20,
        "conditions": ["rci9_os", "pre_down3", "body2"],
        "intent": "売られすぎから強い陽線で反転した短期急騰候補。",
    },
    {
        "id": "mega5_trend_break",
        "label": "Mega5 トレンド加速",
        "eval_days": 5,
        "target": 0.20,
        "conditions": ["ich_cloud_above", "ema75", "bb80", "stoch75"],
        "intent": "雲上・EMA75上の高モメンタム短期ブレイク候補。",
    },
    {
        "id": "mega10_breakout",
        "label": "Mega10 初動ブレイク",
        "eval_days": 10,
        "target": 0.20,
        "conditions": ["bb80", "vol30", "macdgc", "pre_down3", "body2", "stoch75"],
        "intent": "出来高急増、MACD反転、強陽線が重なる初動ブレイク候補。",
    },
    {
        "id": "mega20_cloud_momentum",
        "label": "Mega20 雲上モメンタム",
        "eval_days": 20,
        "target": 0.30,
        "conditions": ["ich_cloud_above", "vol20", "stoch75", "rci26_os"],
        "intent": "雲上の強い買い戻しを20営業日で検証する参考候補。",
    },
    {
        "id": "mega20_volume_oversold",
        "label": "Mega20 出来高売られすぎ反転",
        "eval_days": 20,
        "target": 0.50,
        "conditions": ["vol30", "cci_os", "gap_up"],
        "intent": "売られすぎ圏から出来高を伴ってギャップ反転した外れ値狙い。",
    },
    {
        "id": "mega40_deep_reversal",
        "label": "Mega40 深押し反転",
        "eval_days": 40,
        "target": 0.30,
        "conditions": ["pre_decline15", "pre_down3", "bb_lower", "body2"],
        "intent": "深い押し目から強陽線で切り返す40営業日候補。",
    },
    {
        "id": "mega40_wick_recovery",
        "label": "Mega40 下ヒゲ回復",
        "eval_days": 40,
        "target": 0.50,
        "conditions": ["pre_decline15", "cci_os", "lower_wick50", "ich_chikou"],
        "intent": "深い調整後の下ヒゲ・遅行線回復を使う少数精鋭候補。",
    },
]

LIFT_TARGETS = [
    (5, 0.20),
    (10, 0.20),
    (10, 0.30),
    (20, 0.30),
    (20, 0.50),
    (40, 0.30),
    (40, 0.50),
]


def is_finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def pct(value, signed: bool = True) -> str:
    if not is_finite(value):
        return "--"
    prefix = "+" if signed else ""
    return f"{float(value) * 100:{prefix}.1f}%"


def num(value) -> str:
    if not is_finite(value):
        return "--"
    return f"{float(value):.2f}"


def md(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ").strip()


def normalize_date(value) -> str:
    return str(value or "").replace("/", "-")[:10]


def parse_date(value):
    return pd.to_datetime(normalize_date(value), errors="coerce")


def build_alert_frame(include_unconfirmed: bool) -> tuple[pd.DataFrame, dict, dict]:
    svc = opt.get_service()
    alerts_raw_rows = opt.fetch(svc, "alerts_raw")
    archive_rows = opt.fetch(svc, "signals_archive")
    ohlcv_rows = opt.fetch(svc, "ohlcv_4h")

    alerts_raw = opt.parse_alerts(alerts_raw_rows, include_unconfirmed=include_unconfirmed)
    alerts_raw["_from_archive"] = False
    archive = opt.parse_alerts(archive_rows, include_unconfirmed=include_unconfirmed)
    archive["_from_archive"] = True
    alerts = pd.concat([alerts_raw, archive], ignore_index=True)

    if "alert_id" in alerts.columns and not alerts.empty:
        has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat(
            [
                alerts[has_id].drop_duplicates(subset=["alert_id"], keep="first"),
                alerts[~has_id],
            ],
            ignore_index=True,
        )

    ohlcv = opt.parse_ohlcv(ohlcv_rows)
    today = pd.Timestamp(datetime.now(JST).date())
    records = []

    for _, alert in alerts.iterrows():
        daily = ohlcv.get(alert["symbol"], [])
        features = opt.get_features(daily, alert["date"])
        if not features:
            continue

        rec = {**alert.to_dict(), **features}
        latest_close = opt.latest_close_for_signal(daily, alert["date"])
        entry = alert.get("entry", float("nan"))
        rec["latest_close"] = latest_close if is_finite(latest_close) else np.nan
        rec["cur_perf"] = (
            latest_close / entry - 1
            if is_finite(latest_close) and is_finite(entry) and float(entry) > 0
            else np.nan
        )
        signal_dt = parse_date(alert["date"])
        rec["signal_dt"] = signal_dt
        rec["days_elapsed"] = int((today - signal_dt).days) if pd.notna(signal_dt) else -1
        records.append(rec)

    frame = pd.DataFrame(records)
    for cond in opt.BOOL_CONDS:
        if cond in frame.columns:
            frame[cond] = frame[cond].astype(bool)

    meta = {
        "alerts_raw_rows": len(alerts_raw_rows),
        "signals_archive_rows": len(archive_rows),
        "ohlcv_rows": len(ohlcv_rows),
        "alerts_after_dedupe": len(alerts),
        "feature_rows": len(frame),
    }
    return frame, ohlcv, meta


def condition_mask(frame: pd.DataFrame, conditions: list[str]) -> pd.Series:
    if frame.empty:
        return pd.Series([], dtype=bool, index=frame.index)
    mask = pd.Series(True, index=frame.index)
    for cond in conditions:
        if cond not in frame.columns:
            return pd.Series(False, index=frame.index)
        mask &= frame[cond].astype(bool)
    return mask


def horizon_frame(frame: pd.DataFrame, eval_days: int) -> pd.DataFrame:
    col = f"perf_{eval_days}bd"
    if col not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame[col].apply(is_finite)].copy()


def horizon_summary(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for days in (5, 10, 20, 40):
        col = f"perf_{days}bd"
        subset = horizon_frame(frame, days)
        perf = subset[col].astype(float) if not subset.empty else pd.Series(dtype=float)
        rows.append(
            {
                "days": days,
                "n": len(subset),
                "avg": perf.mean() if len(perf) else np.nan,
                "win": (perf > 0).mean() if len(perf) else np.nan,
                "p10": int((perf >= 0.10).sum()) if len(perf) else 0,
                "p20": int((perf >= 0.20).sum()) if len(perf) else 0,
                "p30": int((perf >= 0.30).sum()) if len(perf) else 0,
                "p50": int((perf >= 0.50).sum()) if len(perf) else 0,
                "p100": int((perf >= 1.00).sum()) if len(perf) else 0,
            }
        )
    return rows


def candidate_stats(frame: pd.DataFrame, candidate: dict) -> dict:
    days = candidate["eval_days"]
    target = candidate["target"]
    perf_col = f"perf_{days}bd"
    subset = horizon_frame(frame, days)
    mask = condition_mask(subset, candidate["conditions"])
    hits = subset[mask].copy()

    total_target = int((subset[perf_col].astype(float) >= target).sum()) if not subset.empty else 0
    base_rate = total_target / len(subset) if len(subset) else 0.0
    if hits.empty:
        return {
            "n": 0,
            "avg": np.nan,
            "median": np.nan,
            "win_rate": np.nan,
            "target_hits": 0,
            "target_rate": 0.0,
            "recall": 0.0,
            "lift": 0.0,
            "p20": 0,
            "p30": 0,
            "p50": 0,
            "p100": 0,
            "m10": 0,
            "max": np.nan,
            "min": np.nan,
            "base_target_rate": base_rate,
        }

    perf = hits[perf_col].astype(float)
    target_hits = int((perf >= target).sum())
    target_rate = target_hits / len(hits)
    return {
        "n": len(hits),
        "avg": float(perf.mean()),
        "median": float(perf.median()),
        "win_rate": float((perf > 0).mean()),
        "target_hits": target_hits,
        "target_rate": target_rate,
        "recall": target_hits / total_target if total_target else 0.0,
        "lift": target_rate / base_rate if base_rate else 0.0,
        "p20": int((perf >= 0.20).sum()),
        "p30": int((perf >= 0.30).sum()),
        "p50": int((perf >= 0.50).sum()),
        "p100": int((perf >= 1.00).sum()),
        "m10": int((perf <= -0.10).sum()),
        "max": float(perf.max()),
        "min": float(perf.min()),
        "base_target_rate": base_rate,
    }


def verdict(stats: dict) -> str:
    if stats["n"] < 5:
        return "保留: 件数不足"
    if is_finite(stats["median"]) and stats["median"] > 0 and stats["avg"] > 0:
        if stats["m10"] / max(stats["n"], 1) <= 0.25:
            return "有望: 継続監視"
        return "注意: 下振れ多め"
    if stats["avg"] > 0 and stats["max"] > 0.5:
        return "注意: 外れ値依存"
    return "保留: 優位性弱い"


def top_lift_conditions(frame: pd.DataFrame, days: int, target: float, limit: int = 8) -> list[dict]:
    perf_col = f"perf_{days}bd"
    subset = horizon_frame(frame, days)
    if subset.empty:
        return []
    perf = subset[perf_col].astype(float).to_numpy()
    target_mask = perf >= target
    target_total = int(target_mask.sum())
    base_rate = target_total / len(subset) if len(subset) else 0.0
    rows = []
    for cond in opt.BOOL_CONDS:
        if cond not in subset.columns:
            continue
        cond_mask = subset[cond].astype(bool).to_numpy()
        cond_n = int(cond_mask.sum())
        if cond_n == 0:
            continue
        cond_target = int((cond_mask & target_mask).sum())
        if cond_target == 0:
            continue
        precision = cond_target / cond_n
        rows.append(
            {
                "condition": cond,
                "lift": precision / base_rate if base_rate else 0.0,
                "precision": precision,
                "cover": cond_target / target_total if target_total else 0.0,
                "all_rate": cond_n / len(subset),
                "hits": cond_target,
                "n": cond_n,
            }
        )
    rows.sort(key=lambda item: (-item["lift"], -item["cover"], item["condition"]))
    return rows[:limit]


def candidate_rows(
    frame: pd.DataFrame,
    candidate: dict,
    confirmed: bool,
    limit: int,
) -> pd.DataFrame:
    days = candidate["eval_days"]
    perf_col = f"perf_{days}bd"
    if perf_col not in frame.columns:
        return frame.iloc[0:0].copy()
    mask = condition_mask(frame, candidate["conditions"])
    if confirmed:
        rows = frame[mask & frame[perf_col].apply(is_finite)].copy()
        return rows.sort_values(perf_col, ascending=False).head(limit)
    rows = frame[mask & ~frame[perf_col].apply(is_finite)].copy()
    if rows.empty:
        return rows
    return rows.sort_values(["signal_dt", "cur_perf"], ascending=[False, False]).head(limit)


def conditions_text(conditions: list[str]) -> str:
    return " + ".join(f"`{cond}`" for cond in conditions)


def condition_labels_text(conditions: list[str]) -> str:
    return "<br>".join(f"`{cond}`: {CONDITION_LABELS.get(cond, cond)}" for cond in conditions)


def stats_table_rows(frame: pd.DataFrame) -> tuple[list[dict], dict[str, dict]]:
    stats_by_id = {}
    rows = []
    for candidate in CANDIDATES:
        stats = candidate_stats(frame, candidate)
        stats_by_id[candidate["id"]] = stats
        rows.append(
            {
                "label": candidate["label"],
                "days": candidate["eval_days"],
                "target": pct(candidate["target"], signed=False),
                "conditions": conditions_text(candidate["conditions"]),
                "n": stats["n"],
                "avg": pct(stats["avg"]),
                "median": pct(stats["median"]),
                "win": pct(stats["win_rate"], signed=False),
                "target_hits": f"{stats['target_hits']} ({pct(stats['target_rate'], signed=False)})",
                "recall": pct(stats["recall"], signed=False),
                "lift": num(stats["lift"]),
                "tail": f"+50% {stats['p50']} / +100% {stats['p100']} / <=-10% {stats['m10']}",
                "verdict": verdict(stats),
            }
        )
    return rows, stats_by_id


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(md(cell) for cell in row) + " |")
    return lines


def signal_table(rows: pd.DataFrame, eval_days: int, confirmed: bool) -> list[str]:
    perf_col = f"perf_{eval_days}bd"
    if rows.empty:
        return ["該当なし"]

    if confirmed:
        headers = ["日付", "銘柄", "社名", "評価値", "5BD", "10BD", "20BD", "40BD"]
        table_rows = []
        for _, row in rows.iterrows():
            table_rows.append(
                [
                    row.get("date", ""),
                    row.get("symbol", ""),
                    row.get("name", ""),
                    pct(row.get(perf_col)),
                    pct(row.get("perf_5bd")),
                    pct(row.get("perf_10bd")),
                    pct(row.get("perf_20bd")),
                    pct(row.get("perf_40bd")),
                ]
            )
        return markdown_table(headers, table_rows)

    headers = ["日付", "銘柄", "社名", "経過日数", "現在騰落", "5BD", "10BD", "20BD"]
    table_rows = []
    for _, row in rows.iterrows():
        table_rows.append(
            [
                row.get("date", ""),
                row.get("symbol", ""),
                row.get("name", ""),
                str(row.get("days_elapsed", "")),
                pct(row.get("cur_perf")),
                pct(row.get("perf_5bd")),
                pct(row.get("perf_10bd")),
                pct(row.get("perf_20bd")),
            ]
        )
    return markdown_table(headers, table_rows)


def build_report(frame_confirmed: pd.DataFrame, frame_all: pd.DataFrame, meta: dict) -> str:
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S %Z")
    stats_rows, stats_by_id = stats_table_rows(frame_confirmed)

    lines = [
        "# Mega候補スコアリング検証レポート",
        "",
        f"- 生成日時: {generated_at}",
        "- 対象: TradingView BOTTOM シグナル",
        "- 注意: このレポートは検証専用です。Bot本体、Discordコマンド、Moonshotロック状態は変更しません。",
        "",
        "## データ概要",
        "",
        f"- alerts_raw rows: {meta['alerts_raw_rows']}",
        f"- signals_archive rows: {meta['signals_archive_rows']}",
        f"- ohlcv_4h rows: {meta['ohlcv_rows']}",
        f"- dedupe後シグナル: {meta['alerts_after_dedupe']}",
        f"- 指標計算可能シグナル: {meta['feature_rows']}",
        "",
    ]

    summary_rows = []
    for row in horizon_summary(frame_confirmed):
        summary_rows.append(
            [
                f"{row['days']}BD",
                str(row["n"]),
                pct(row["avg"]),
                pct(row["win"], signed=False),
                str(row["p10"]),
                str(row["p20"]),
                str(row["p30"]),
                str(row["p50"]),
                str(row["p100"]),
            ]
        )
    lines.extend(
        markdown_table(
            ["評価日", "確定件数", "平均", "勝率", "+10%", "+20%", "+30%", "+50%", "+100%"],
            summary_rows,
        )
    )
    lines += [
        "",
        "## 候補スコアカード",
        "",
        "実装判断は `有望` 表示だけではなく、未確定候補の品質と件数増加後の再現性を見て決める前提です。",
        "",
    ]

    lines.extend(
        markdown_table(
            [
                "候補",
                "評価",
                "目標",
                "条件",
                "件数",
                "平均",
                "中央値",
                "勝率",
                "目標Hit",
                "Recall",
                "Lift",
                "Tail",
                "判定",
            ],
            [
                [
                    row["label"],
                    f"{row['days']}BD",
                    row["target"],
                    row["conditions"],
                    str(row["n"]),
                    row["avg"],
                    row["median"],
                    row["win"],
                    row["target_hits"],
                    row["recall"],
                    row["lift"],
                    row["tail"],
                    row["verdict"],
                ]
                for row in stats_rows
            ],
        )
    )

    lines += [
        "",
        "## 読み取り",
        "",
        "- `Mega5 短期リバウンド` は短期検証の主候補。中央値と下振れを最重視して見る。",
        "- `Mega10 初動ブレイク` と `Mega20 出来高売られすぎ反転` は大化けを拾うが外れ値依存になりやすい。",
        "- `Mega40 深押し反転` と `Mega40 下ヒゲ回復` は本命候補。ただし40BD確定まで時間がかかるため未確定監視が重要。",
        "- 20BD単独での実装判断は避け、40BD候補の中間評価として扱う。",
        "",
        "## 条件別 Lift",
        "",
    ]

    for days, target in LIFT_TARGETS:
        rows = top_lift_conditions(frame_confirmed, days, target)
        lines += [f"### {days}BD / 目標 {pct(target, signed=False)}", ""]
        lines.extend(
            markdown_table(
                ["条件", "説明", "Lift", "Precision", "Cover", "全体出現率", "Hit/該当"],
                [
                    [
                        f"`{item['condition']}`",
                        CONDITION_LABELS.get(item["condition"], item["condition"]),
                        num(item["lift"]),
                        pct(item["precision"], signed=False),
                        pct(item["cover"], signed=False),
                        pct(item["all_rate"], signed=False),
                        f"{item['hits']}/{item['n']}",
                    ]
                    for item in rows
                ],
            )
        )
        lines.append("")

    lines += ["## 候補別 詳細", ""]

    for candidate in CANDIDATES:
        stats = stats_by_id[candidate["id"]]
        lines += [
            f"### {candidate['label']}",
            "",
            f"- 意図: {candidate['intent']}",
            f"- 評価軸: {candidate['eval_days']}BD / 目標 {pct(candidate['target'], signed=False)}",
            f"- 条件: {conditions_text(candidate['conditions'])}",
            f"- 条件説明:<br>{condition_labels_text(candidate['conditions'])}",
            (
                f"- 成績: 件数 {stats['n']} / 平均 {pct(stats['avg'])} / 中央値 {pct(stats['median'])} / "
                f"勝率 {pct(stats['win_rate'], signed=False)} / 目標Hit {stats['target_hits']} / "
                f"Lift {num(stats['lift'])} / 判定 {verdict(stats)}"
            ),
            "",
            "#### 確定済み上位",
            "",
        ]
        confirmed_rows = candidate_rows(frame_confirmed, candidate, confirmed=True, limit=10)
        lines.extend(signal_table(confirmed_rows, candidate["eval_days"], confirmed=True))
        lines += ["", "#### 未確定ウォッチ", ""]
        unconfirmed_rows = candidate_rows(frame_all, candidate, confirmed=False, limit=12)
        lines.extend(signal_table(unconfirmed_rows, candidate["eval_days"], confirmed=False))
        lines.append("")

    lines += [
        "## 実装判断ゲート案",
        "",
        "実装前に最低限、以下を満たすか確認する。",
        "",
        "- 確定件数: 主要候補で最低10件以上。少数精鋭候補でも5件未満は不可。",
        "- 中央値: 0%以上。平均だけが高い外れ値依存は不可。",
        "- 下振れ: `<= -10%` が候補内の25%を超える場合は警戒扱い。",
        "- 未確定候補: 直近候補の現在騰落が極端に弱い場合は、確定バックテストが良くても実装しない。",
        "- Moonshotロック: `/scan moonshot` や pending/current moonshot への反映は、別途ユーザー承認があるまで行わない。",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Markdown output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    confirmed_frame, _, confirmed_meta = build_alert_frame(include_unconfirmed=False)
    all_frame, _, all_meta = build_alert_frame(include_unconfirmed=True)
    meta = dict(confirmed_meta)
    meta["alerts_after_dedupe"] = all_meta["alerts_after_dedupe"]
    meta["feature_rows"] = all_meta["feature_rows"]

    report = build_report(confirmed_frame, all_frame, meta)
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)
        handle.write("\n")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
