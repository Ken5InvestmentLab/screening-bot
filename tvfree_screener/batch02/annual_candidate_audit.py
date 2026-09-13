"""Frozen, retrospective annual report for the leading TV-Free Monster/Core references."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd

from tvfree_screener.batch01 import audit_monster_canonical as monster
from tvfree_screener.batch01.evaluation import daily_cohorts, label_summary, return_metrics
from tvfree_screener.batch01.selection import rank_candidate_pool
from tvfree_screener.batch01.session_calendar import SessionCalendar

BATCH2_DIR = Path(__file__).resolve().parent
REPO_ROOT = BATCH2_DIR.parents[1]
BATCH1_DIR = REPO_ROOT / "tvfree_screener" / "batch01"
AUDIT_SPEC_PATH = BATCH2_DIR / "ANNUAL_CANDIDATE_AUDIT_SPEC.json"
AUDIT_SPEC_SHA_PATH = BATCH2_DIR / "ANNUAL_CANDIDATE_AUDIT_SPEC.sha256"
FAMILY_SPEC_PATH = BATCH2_DIR / "FAMILY_SPEC.json"
FAMILY_SPEC_SHA_PATH = BATCH2_DIR / "FAMILY_SPEC.sha256"
REPORT_DIR = BATCH2_DIR / "reports"
CACHE_DIR = BATCH2_DIR / ".cache"
SUMMARY_JSON_PATH = REPORT_DIR / "annual_candidate_evaluation.json"
SUMMARY_MD_PATH = REPORT_DIR / "annual_candidate_evaluation.md"
POOL_CSV_PATH = CACHE_DIR / "annual_candidate_all_pool.csv"
DETECTIONS_CSV_PATH = CACHE_DIR / "annual_candidate_detections.csv"
TAIL_SIGNAL_COLUMNS = ("date", "symbol", "ret1", "ret10", "volr20", "tail_cdf", "tail_p", "range_pct")
YEAR_RANGE = (2022, 2026)
COSTS = (0.0, 0.005, 0.01)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_paths() -> dict[str, Path]:
    return {
        "daily_ohlcv": BATCH1_DIR / ".cache" / "artifacts" / "tse_daily.csv",
        "monster_tail_features": BATCH1_DIR / ".cache" / "artifacts" / "v7_causal_tail_cache_2023_2025.csv",
        "monster_tail_metadata": BATCH1_DIR / ".cache" / "artifacts" / "v7_causal_tail_cache_meta.json",
        "monster_prior_audit": BATCH1_DIR / "reports" / "monster_canonical_audit.json",
        "monster_prior_frozen_spec_file": BATCH1_DIR / "reports" / "monster_canonical_spec.json",
        "v29_summary_artifact": BATCH1_DIR / ".cache" / "artifacts" / "v29_purged_rolling.json",
        "v29_prior_audit": BATCH1_DIR / "reports" / "v29_canonical_audit.json",
        "xtks_calendar": BATCH1_DIR / "reference" / "xtks_sessions.csv",
        "market_returns": BATCH1_DIR / ".cache" / "market_returns.parquet",
    }


def verify_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    raw = AUDIT_SPEC_PATH.read_bytes()
    actual_spec_sha = hashlib.sha256(raw).hexdigest()
    sidecar = AUDIT_SPEC_SHA_PATH.read_text(encoding="utf-8-sig").strip().split()[0].lower()
    if actual_spec_sha != sidecar:
        raise ValueError("annual audit spec hash differs from sidecar")
    audit_spec = json.loads(raw.decode("utf-8-sig"))
    if audit_spec.get("audit_id") != "TVFREE-ANNUAL-CANDIDATE-AUDIT-20260913-01":
        raise ValueError("unexpected audit ID")
    if audit_spec.get("status") != "FROZEN_BEFORE_2025_ANNUAL_REPLAY":
        raise ValueError("annual audit spec is not frozen")
    if audit_spec.get("evidence_level") != "RETROSPECTIVE_PROVISIONAL":
        raise ValueError("unexpected evidence level")

    family_raw = FAMILY_SPEC_PATH.read_bytes()
    family_sha = hashlib.sha256(family_raw).hexdigest()
    family_sidecar = FAMILY_SPEC_SHA_PATH.read_text(encoding="utf-8-sig").strip().split()[0].lower()
    if family_sha != family_sidecar:
        raise ValueError("independent Core family spec hash differs from sidecar")
    family_spec = json.loads(family_raw.decode("utf-8-sig"))

    frozen_path = source_paths()["monster_prior_frozen_spec_file"]
    monster_spec = json.loads(frozen_path.read_text(encoding="utf-8-sig"))
    monster_core = {key: value for key, value in monster_spec.items() if key != "spec_sha256"}
    if canonical_json_sha256(monster_core) != monster_spec.get("spec_sha256"):
        raise ValueError("canonical Monster spec content hash mismatch")
    if monster_spec.get("spec_sha256") != audit_spec["monster"]["existing_spec_sha256"]:
        raise ValueError("annual audit points to a different Monster spec")

    paths = source_paths()
    expected = audit_spec["source_sha256"]
    if set(paths) != set(expected):
        raise ValueError("source path map differs from frozen hash manifest")
    actual: dict[str, str] = {}
    for key, path in paths.items():
        digest = sha256_file(path)
        if digest != expected[key]:
            raise ValueError(f"frozen source hash mismatch for {key}: {digest}")
        actual[key] = digest

    metadata = json.loads(paths["monster_tail_metadata"].read_text(encoding="utf-8-sig"))
    if set(metadata.get("period_counts", {})) != {"2023", "2024", "2025"}:
        raise ValueError("unexpected V7 cache period coverage")
    if not audit_spec["core"]["exact_annual_replay"].startswith("NOT_REPLAYABLE"):
        raise ValueError("Core annual replay limitation has changed")
    return audit_spec, family_spec, actual


def read_v7_signal_features(path: Path | None = None) -> pd.DataFrame:
    """Read only signal-time columns, excluding all cached target/label fields."""
    frame = pd.read_csv(
        path or monster.TAIL_PATH,
        usecols=list(TAIL_SIGNAL_COLUMNS),
        parse_dates=["date"],
        dtype={"symbol": "string"},
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype("string")
    if frame[["date", "symbol"]].isna().any().any():
        raise ValueError("V7 feature cache has a missing date or symbol")
    return frame


def attach_lagged_market_feature(tail: pd.DataFrame) -> pd.DataFrame:
    market = pd.read_parquet(
        BATCH1_DIR / ".cache" / "market_returns.parquet",
        columns=["date", "market_median_ret5_lag1"],
    )
    market["date"] = pd.to_datetime(market["date"], errors="raise").dt.normalize()
    if market["date"].duplicated().any():
        raise ValueError("lagged market table has duplicate sessions")
    result = tail.merge(market, on="date", how="left", validate="many_to_one")
    for column in ("ret1", "ret10", "volr20", "tail_cdf", "tail_p", "range_pct", "market_median_ret5_lag1"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def apply_all_candidates_cooldown(ranked_pool: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Emit every passing candidate; only prior official-session detections are blocked."""
    required = {"date", "symbol", "identity_key", "raw_rank"}
    missing = sorted(required.difference(ranked_pool.columns))
    if missing:
        raise ValueError(f"ranked pool missing cooldown fields: {missing}")
    if ranked_pool.duplicated(["date", "symbol"]).any():
        raise ValueError("duplicate candidate symbol/date")
    work = ranked_pool.copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
    if not set(pd.DatetimeIndex(work["date"].unique())).issubset(set(sessions)):
        raise ValueError("candidate date is not an official session")
    by_date = {pd.Timestamp(day): frame for day, frame in work.groupby("date", sort=False)}
    previous_detected: set[str] = set()
    traces: list[pd.DataFrame] = []
    for session in sessions:
        day = pd.Timestamp(session)
        current = by_date.get(day)
        if current is None or current.empty:
            previous_detected = set()
            continue
        current = current.copy()
        blocked = current["identity_key"].astype(str).isin(previous_detected)
        current["cooldown_status"] = np.where(blocked, "COOLDOWN_BLOCKED", "DETECTED")
        current["cooldown_blocked"] = blocked.astype(bool)
        current["post_cooldown_count"] = int((~blocked).sum())
        current["cooldown_blocked_count"] = int(blocked.sum())
        traces.append(current)
        previous_detected = set(current.loc[~blocked, "identity_key"].astype(str))
    if not traces:
        empty = work.iloc[0:0].copy()
        empty["cooldown_status"] = pd.Series(dtype="string")
        empty["cooldown_blocked"] = pd.Series(dtype="bool")
        empty["post_cooldown_count"] = pd.Series(dtype="int64")
        empty["cooldown_blocked_count"] = pd.Series(dtype="int64")
        return empty
    return pd.concat(traces, ignore_index=True).sort_values(
        ["date", "raw_rank", "symbol"], kind="mergesort",
    ).reset_index(drop=True)


def safe_json(value: Any) -> Any:
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(key): safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def period_dependence(labels: pd.DataFrame, date_format: str, cost: float) -> dict[str, Any]:
    resolved = labels.loc[labels["label_resolved"].astype(bool), ["date", "gross_return"]].copy()
    if resolved.empty:
        return {
            "periods": 0, "positive_periods": 0, "negative_periods": 0,
            "best_period": None, "best_period_mean_net": None,
            "worst_period": None, "worst_period_mean_net": None, "by_period": {},
        }
    resolved["net"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - cost
    resolved["period"] = pd.to_datetime(resolved["date"]).dt.strftime(date_format)
    by_period: dict[str, Any] = {}
    means: dict[str, float] = {}
    for name, group in resolved.groupby("period", sort=True):
        by_period[str(name)] = return_metrics(group["net"])
        means[str(name)] = float(group["net"].mean())
    best, worst = max(means, key=means.get), min(means, key=means.get)
    return {
        "periods": len(means),
        "positive_periods": sum(value > 0 for value in means.values()),
        "negative_periods": sum(value < 0 for value in means.values()),
        "best_period": best,
        "best_period_mean_net": means[best],
        "worst_period": worst,
        "worst_period_mean_net": means[worst],
        "by_period": by_period,
    }


def symbol_concentration(detections: pd.DataFrame, labels: pd.DataFrame, cost: float) -> dict[str, Any]:
    if detections.empty:
        return {
            "unique_symbols_detected": 0, "top1_frequency_share": None, "top3_frequency_share": None,
            "mean_net_excluding_most_frequent_top1_symbol": None,
            "mean_net_excluding_most_frequent_top3_symbols": None, "top_symbols_by_detection_count": [],
        }
    counts = detections.groupby("symbol", dropna=False).size().sort_values(ascending=False, kind="mergesort")
    top1, top3 = set(counts.head(1).index.astype(str)), set(counts.head(3).index.astype(str))
    resolved = labels.loc[labels["label_resolved"].astype(bool), ["symbol", "gross_return"]].copy()
    resolved["net"] = pd.to_numeric(resolved["gross_return"], errors="coerce") - cost
    rest1 = resolved.loc[~resolved["symbol"].astype(str).isin(top1), "net"]
    rest3 = resolved.loc[~resolved["symbol"].astype(str).isin(top3), "net"]
    return {
        "unique_symbols_detected": int(counts.size),
        "top1_frequency_share": float(counts.head(1).sum() / len(detections)),
        "top3_frequency_share": float(counts.head(3).sum() / len(detections)),
        "mean_net_excluding_most_frequent_top1_symbol": float(rest1.mean()) if len(rest1) else None,
        "mean_net_excluding_most_frequent_top3_symbols": float(rest3.mean()) if len(rest3) else None,
        "top_symbols_by_detection_count": [
            {"symbol": str(symbol), "detections": int(count)}
            for symbol, count in counts.head(10).items()
        ],
    }


def summarize_year(year: int, pool: pd.DataFrame, detections: pd.DataFrame, labels: pd.DataFrame,
                   calendar: SessionCalendar, cutoff: pd.Timestamp) -> dict[str, Any]:
    metrics = label_summary(labels, costs=COSTS)
    primary = metrics["round_trip_cost_scenarios"]["0.005"]
    cohorts = daily_cohorts(detections, labels, sessions=calendar.slice(f"{year}-01-01", cutoff))
    active = cohorts.loc[cohorts["selected_count"].gt(0)].copy()
    complete = active.loc[active["cohort_status"].eq("COMPLETE") & active["cohort_return"].notna()].copy()
    complete["net_return"] = pd.to_numeric(complete["cohort_return"], errors="coerce") - 0.005
    daily = return_metrics(complete["net_return"], requested_count=len(active))
    return {
        "year": year,
        "status": "REPLAYED_RETROSPECTIVE",
        "evidence_level": "RETROSPECTIVE_PROVISIONAL",
        "year_end_purge_cutoff": cutoff.date().isoformat(),
        "raw_pool_rows": int(len(pool)),
        "cooldown_blocked_rows": int(pool["cooldown_blocked"].sum()) if len(pool) else 0,
        "detected_rows": int(len(detections)),
        "unique_symbols": int(detections["symbol"].nunique()) if len(detections) else 0,
        "active_dates": int(detections["date"].nunique()) if len(detections) else 0,
        "maximum_detected_symbols_per_day": int(detections.groupby("date").size().max()) if len(detections) else 0,
        "signal_level": metrics,
        "primary_net_0_5pct": primary,
        "top1_top3_winner_exclusion": {
            "mean_excluding_best_one_resolved_return": primary.get("mean_excluding_top1_winner"),
            "mean_excluding_best_three_resolved_returns": primary.get("mean_excluding_top3_winners"),
            "definition": "0.5 percentage-point cost; remove the largest one or three resolved signal returns.",
        },
        "equal_weight_daily_cohort_net_0_5pct": {
            **daily,
            "active_dates": int(len(active)),
            "complete_dates": int(len(complete)),
            "partial_unresolved_dates": int(active["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
            "abstain_dates": int(cohorts["cohort_status"].eq("ABSTAIN").sum()),
            "definition": "Equal-weight all detections per date; complete daily cohorts only; 0.5 percentage-point assumed cost.",
        },
        "month_dependence_net_0_5pct": period_dependence(labels, "%Y-%m", 0.005),
        "week_dependence_net_0_5pct": period_dependence(labels, "%G-W%V", 0.005),
        "symbol_concentration_net_0_5pct": symbol_concentration(detections, labels, 0.005),
    }


def pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{100 * number:.2f}%" if math.isfinite(number) else "—"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Monster / Core候補の年別検出・評価",
        "",
        f"- 監査ID: {report['audit_id']}",
        f"- 凍結仕様SHA-256: {report['audit_spec_sha256']}",
        f"- Git SHA: {report['git_sha']}",
        "- 全結果は回顧再計算です。以前に候補・結果を閲覧済みのため、OOS成績ではありません。",
        "- MonsterのV7キャッシュはTail上位候補行のみで、東証全銘柄・全日のスコア履歴ではありません。",
        "- 日次上限なしで全候補を検出。前の東証営業日に検出した同一銘柄だけを1営業日cooldownで除外します。",
        "- 5BDは次の東証営業日の始値から5営業日目の終値まで。年末をまたぐ結果はpurgeし未解決扱いです。",
        "- 主指標は0.5%の往復コスト仮定を差し引いた値。0%/1%感度はJSONと銘柄別CSVに記載。",
        "",
        "## Monster 年次サマリー",
        "",
        "| 年 | 状態 | 生pool | 検出 | 銘柄数 | 稼働日 | 解決/未解決 | 平均 | 中央値 | 勝率 | +10% | +20% | +50% | -10% | -20% | 最大1件除外 | 最大3件除外 | 日次等ウェイト平均 | 月プラス/対象 | 週プラス/対象 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["monster"]["annual"]:
        if row["status"] != "REPLAYED_RETROSPECTIVE":
            lines.append(f"| {row['year']} | {row['status']} | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        m, month, week, daily = (
            row["primary_net_0_5pct"], row["month_dependence_net_0_5pct"],
            row["week_dependence_net_0_5pct"], row["equal_weight_daily_cohort_net_0_5pct"],
        )
        unresolved = m["requested_count"] - m["resolved_count"]
        lines.append(
            f"| {row['year']} | 回顧再計算 | {row['raw_pool_rows']} | {row['detected_rows']} | {row['unique_symbols']} | {row['active_dates']} | {m['resolved_count']}/{unresolved} | "
            f"{pct(m.get('mean'))} | {pct(m.get('median'))} | {pct(m.get('win_rate'))} | {pct(m.get('plus10_rate'))} | {pct(m.get('plus20_rate'))} | {pct(m.get('plus50_rate'))} | "
            f"{pct(m.get('minus10_rate'))} | {pct(m.get('minus20_rate'))} | "
            f"{pct(row['top1_top3_winner_exclusion'].get('mean_excluding_best_one_resolved_return'))} | "
            f"{pct(row['top1_top3_winner_exclusion'].get('mean_excluding_best_three_resolved_returns'))} | "
            f"{pct(daily.get('mean'))} ({daily['complete_dates']}/{daily['active_dates']}日完了) | {month['positive_periods']}/{month['periods']} | {week['positive_periods']}/{week['periods']} |"
        )
    lines.extend([
        "",
        "日付・銘柄・順位・特徴量・個別5BD評価はローカルCSVに全件あります: tvfree_screener/batch02/.cache/annual_candidate_detections.csv",
        "cooldown除外も含む適格候補pool: tvfree_screener/batch02/.cache/annual_candidate_all_pool.csv",
        "",
        "- 平均/中央値/到達率は個別シグナル単位。Top1/Top3除外は最良リターンの1件/3件を外す診断。",
        "- 日次等ウェイトはその日の全検出銘柄を等ウェイト化し、全銘柄のラベルが解決した日だけを集計。",
        "- 月/週欄はコスト控除後にプラスだった期間数/対象期間数。JSONには期間別成績と銘柄集中度を収録。",
        "",
        "## Core V29 fixed_min98_both",
        "",
        "年別の個別銘柄再現は NOT_REPLAYABLE_FROM_PRESERVED_INPUTS です。V29の生教師行、日付付き350銘柄watchlist、当時のYahoo取得行がありません。日足から当時の時間足を合成して代替することもしません。",
    ])
    ref = report["core"]["prior_aggregate_reference"]
    lines.append(
        f"過去に保存された非年次の参考集計: n={ref['n']}, mean {pct(ref['mean'])}, median {pct(ref['median'])}, "
        f"win {pct(ref['win_rate'])}, +10% {pct(ref['plus10_rate'])}。"
    )
    lines.extend([
        "これは350銘柄のwatchlist頻度サンプル、signal close→5営業日目closeの別ターゲットです。Monsterとの直接比較や年別への割り振りはできず、個別銘柄一覧も復元できません。",
        "",
        "## 年別の利用可能性",
        "",
        "| 系統 | 年 | 状態 |",
        "|---|---:|---|",
    ])
    for row in report["monster"]["annual"]:
        lines.append(f"| Monster | {row['year']} | {row['status']} |")
    for row in report["core"]["annual"]:
        lines.append(f"| Core V29 | {row['year']} | {row['status']} |")
    lines.extend([
        "",
        "V7の2022/2026スコアは保存されていないため日足から再現していません。全入力ハッシュと凍結仕様を実行前に検証し、V7の結果列を読み込まず日足OHLCVからラベルを再計算しています。",
        "この結果は説明的な過去評価で、全市場スコア再現、Walk-Forward/OOS昇格、Codexなしの本番実行性は証明しません。",
        "",
    ])
    return "\n".join(lines)


def git_sha() -> str | None:
    root = REPO_ROOT.as_posix()
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", root, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_csv(pool: pd.DataFrame, evaluated: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pool_export = pool.copy()
    if len(pool_export):
        pool_export["year"] = pd.to_datetime(pool_export["date"]).dt.year
    pool_export.to_csv(POOL_CSV_PATH, index=False, encoding="utf-8-sig", na_rep="")

    output = evaluated.copy()
    if len(output):
        output["year"] = pd.to_datetime(output["date"]).dt.year
        gross = pd.to_numeric(output["gross_return"], errors="coerce")
        output["gross_5bd_return_pct"] = gross * 100
        output["net_5bd_return_0pct"] = gross * 100
        output["net_5bd_return_0_5pct"] = (gross - 0.005) * 100
        output["net_5bd_return_1pct"] = (gross - 0.01) * 100
        output = output.rename(columns={
            "date": "signal_date", "ret1": "ret1_signal_time", "ret10": "ret10_signal_time",
            "volr20": "volr20_signal_time", "tail_cdf": "tail_cdf_signal_time",
            "tail_p": "tail_p_signal_time", "market_median_ret5_lag1": "previous_session_market_median_ret5",
            "raw_rank": "volr20_first_daily_rank", "daily_candidate_count": "raw_pool_count_that_day",
            "cooldown_status": "detection_status",
        })
    columns = [
        "year", "signal_date", "symbol", "detection_status", "volr20_first_daily_rank",
        "raw_pool_count_that_day", "post_cooldown_count", "cooldown_blocked_count",
        "ret1_signal_time", "ret10_signal_time", "volr20_signal_time",
        "tail_cdf_signal_time", "tail_p_signal_time", "previous_session_market_median_ret5",
        "entry_date", "exit_date", "entry_price", "exit_price", "gross_5bd_return_pct",
        "net_5bd_return_0pct", "net_5bd_return_0_5pct", "net_5bd_return_1pct",
        "label_status", "entry_fill_quality", "label_definition",
    ]
    output.loc[:, [column for column in columns if column in output.columns]].to_csv(
        DETECTIONS_CSV_PATH, index=False, encoding="utf-8-sig", na_rep="",
    )


def run_audit() -> dict[str, Any]:
    audit_spec, family_spec, verified_hashes = verify_frozen_inputs()
    sources = source_paths()
    monster_spec = json.loads(sources["monster_prior_frozen_spec_file"].read_text(encoding="utf-8-sig"))
    calendar = SessionCalendar.from_csv(
        BATCH1_DIR / "reference" / "xtks_sessions.csv",
        expected_sha256=audit_spec["source_sha256"]["xtks_calendar"],
    )
    metadata = json.loads(sources["monster_tail_metadata"].read_text(encoding="utf-8-sig"))

    tail = read_v7_signal_features()
    tail = tail.loc[tail["date"].between("2023-01-01", "2025-12-31")].copy()
    tail = attach_lagged_market_feature(tail)
    _weak, pool, pool_counts = monster._split_pool(tail, monster_spec)
    pool = pool.loc[pool["date"].dt.year.isin([2023, 2024, 2025])].copy() if len(pool) else pool
    ranked = rank_candidate_pool(
        pool,
        sessions=calendar.sessions,
        feature_columns=["ret1", "ret10", "volr20", "tail_cdf", "tail_p", "market_median_ret5_lag1"],
        ranking_terms=[("volr20_rank_value", True), ("tail_cdf", False), ("tail_p", False)],
    )
    trace = apply_all_candidates_cooldown(ranked, calendar.sessions)
    detected = trace.loc[trace["cooldown_status"].eq("DETECTED")].copy() if len(trace) else trace.copy()

    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": audit_spec["audit_id"],
        "status": "COMPLETE_RETROSPECTIVE_REPORT_ONLY",
        "evidence_level": audit_spec["evidence_level"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_spec_sha256": sha256_file(AUDIT_SPEC_PATH),
        "family_spec_id": family_spec.get("experiment_id"),
        "family_spec_sha256": sha256_file(FAMILY_SPEC_PATH),
        "git_sha": git_sha(),
        "production_modified": False,
        "data_policy": {
            "v7_cache_rows": int(metadata["rows"]),
            "v7_period_counts": metadata["period_counts"],
            "v7_signal_columns_read": list(TAIL_SIGNAL_COLUMNS),
            "v7_outcome_columns_not_loaded": list(metadata.get("contains_outcomes", [])),
            "candidate_cache_population": "V7 monthly causal top-0.25% Tail score rows; not the full TSE daily universe.",
            "daily_output_cap": None,
            "multiple_symbols_per_day_allowed": True,
            "cooldown": "One immediately prior official XTKS session; emit every non-blocked candidate.",
            "target": "Next official XTKS session open to fifth-session close including entry; rebuilt from preserved daily OHLCV.",
            "year_end_policy": "Targets ending after that year's final official XTKS session remain unresolved PURGED_SPLIT_BOUNDARY.",
            "cost_scenarios": {"0.0": "gross reference", "0.005": "primary assumed round-trip cost", "0.01": "sensitivity"},
            "verified_source_hashes": verified_hashes,
            "pool_counts_total": pool_counts,
            "pool_counts_by_year": {
                str(year): int((pool["date"].dt.year == year).sum()) if len(pool) else 0
                for year in [2023, 2024, 2025]
            },
        },
        "monster": {
            "spec_id": monster_spec["spec_id"],
            "spec_sha256": monster_spec["spec_sha256"],
            "detection_rule": audit_spec["monster"]["candidate_pool"],
            "annual": [],
        },
        "core": {
            "annual": [{"year": year, "status": "NOT_REPLAYABLE_FROM_PRESERVED_INPUTS"} for year in YEAR_RANGE],
            "prior_aggregate_reference": {},
            "no_symbol_list_reason": "V29 artifacts contain aggregate/fold metrics only; no dated symbol rows, source watchlist/teacher rows or original Yahoo OHLCV.",
        },
        "interpretation": {
            "selection_or_tuning_from_annual_replay": False,
            "2025": "User-requested retrospective reporting only; previously exposed and not OOS.",
            "direct_core_monster_ranking": False,
            "production_decision": "NO_GO: this descriptive cached-subset replay does not prove full-universe or Codex-free operation.",
        },
    }
    v29_audit = json.loads(sources["v29_prior_audit"].read_text(encoding="utf-8-sig"))
    ref = v29_audit["v29_fixed_min98_both"]
    report["core"]["prior_aggregate_reference"] = {
        "source": "previous V29 audit; not recalculated and not annual",
        "population": ref["population"], "n": ref["n"], "mean": ref["mean"],
        "median": ref["median"], "robust_mean": ref["robust_mean"],
        "win_rate": ref["win_rate"], "plus10_rate": ref["plus10_rate"],
        "target_definition": v29_audit["target_mismatch"]["v29"],
        "individual_symbols_available": False,
    }

    evaluated_parts: list[pd.DataFrame] = []
    for year in [2023, 2024, 2025]:
        pool_year = trace.loc[pd.to_datetime(trace["date"]).dt.year.eq(year)].copy() if len(trace) else trace.copy()
        detected_year = detected.loc[pd.to_datetime(detected["date"]).dt.year.eq(year)].copy() if len(detected) else detected.copy()
        year_sessions = calendar.sessions[calendar.sessions.year == year]
        if len(year_sessions) == 0:
            raise ValueError(f"official calendar missing {year}")
        cutoff = pd.Timestamp(year_sessions[-1])
        prices = (
            monster._price_subset(detected_year, calendar, cutoff.strftime("%Y-%m-%d"))
            if len(detected_year)
            else pd.DataFrame(columns=monster.PRICE_COLUMNS)
        )
        labels = monster.build_five_session_labels(prices, detected_year, calendar)
        labels = monster._periodized(labels, year, cutoff.strftime("%Y-%m-%d"))
        report["monster"]["annual"].append(
            summarize_year(year, pool_year, detected_year, labels, calendar, cutoff)
        )
        if len(detected_year):
            label_columns = [
                "date", "symbol", "family", "spec_hash", "entry_date", "exit_date",
                "entry_price", "exit_price", "gross_return", "label_status", "label_resolved",
                "entry_fill_quality", "label_definition",
            ]
            joined = detected_year.merge(
                labels.loc[:, label_columns],
                on=["date", "symbol", "family", "spec_hash"],
                how="left", validate="one_to_one",
            )
            joined["year"] = year
            evaluated_parts.append(joined)
    report["monster"]["annual"].extend([
        {"year": 2022, "status": "NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS"},
        {"year": 2026, "status": "NOT_AVAILABLE_NO_PRESERVED_V7_SCORE_ROWS"},
    ])
    report["monster"]["annual"].sort(key=lambda row: row["year"])
    evaluated = pd.concat(evaluated_parts, ignore_index=True) if evaluated_parts else detected.iloc[0:0].copy()
    for cost, name in ((0.0, "net_return_0pct"), (0.005, "net_return_0_5pct"), (0.01, "net_return_1pct")):
        if len(evaluated):
            evaluated[name] = pd.to_numeric(evaluated["gross_return"], errors="coerce") - cost

    hashes = dict(verified_hashes)
    hashes["annual_audit_script"] = sha256_file(Path(__file__).resolve())
    hashes["monster_audit_helper"] = sha256_file(Path(monster.__file__).resolve())
    report["data_policy"]["implementation_hashes"] = hashes
    write_csv(trace, evaluated)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    clean = safe_json(report)
    SUMMARY_JSON_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    SUMMARY_MD_PATH.write_text(render_markdown(clean), encoding="utf-8")
    return clean


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="verify frozen manifests and hashes without loading score/outcome rows")
    args = parser.parse_args()
    spec, family, hashes = verify_frozen_inputs()
    if args.verify_only:
        print(json.dumps({
            "status": "FROZEN_INPUTS_VERIFIED",
            "audit_id": spec["audit_id"],
            "audit_spec_sha256": sha256_file(AUDIT_SPEC_PATH),
            "family_spec_id": family.get("experiment_id"),
            "verified_source_hash_count": len(hashes),
        }, ensure_ascii=False, indent=2))
        return
    report = run_audit()
    print(json.dumps({
        "status": report["status"],
        "summary_json": str(SUMMARY_JSON_PATH),
        "summary_markdown": str(SUMMARY_MD_PATH),
        "detections_csv": str(DETECTIONS_CSV_PATH),
        "all_pool_csv": str(POOL_CSV_PATH),
        "monster_years": [{
            "year": row["year"], "status": row["status"], "pool": row.get("raw_pool_rows"),
            "detected": row.get("detected_rows"),
            "mean_net_0_5pct": row.get("primary_net_0_5pct", {}).get("mean")
            if row.get("primary_net_0_5pct") else None,
        } for row in report["monster"]["annual"]],
        "core_v29_reference_n": report["core"]["prior_aggregate_reference"]["n"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

