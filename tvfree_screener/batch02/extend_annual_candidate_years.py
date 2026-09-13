"""Report-only causal V7 score reconstruction for the requested 2022/2026 years."""
from __future__ import annotations
import argparse, gc, hashlib, json, sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

B2 = Path(__file__).resolve().parent
ROOT = B2.parents[1]
TV = B2.parents[0]
B1 = ROOT / "tvfree_screener" / "batch01"
REPORTS = B2 / "reports"
CACHE = B2 / ".cache"
SPEC = B2 / "ANNUAL_CANDIDATE_2022_2026_EXTENSION_SPEC_V3.json"
SPEC_SHA = B2 / "ANNUAL_CANDIDATE_2022_2026_EXTENSION_SPEC_V3.sha256"
OUT_JSON = REPORTS / "annual_candidate_evaluation_2022_2026_extended.json"
OUT_MD = REPORTS / "annual_candidate_evaluation_2022_2026_extended.md"
OUT_DETECTIONS = REPORTS / "annual_candidate_detections_2022_2026.csv"
OUT_POOL = REPORTS / "annual_candidate_pool_2022_2026.csv"
sys.path.insert(0, str(TV))

from tvfree_screener.batch02 import annual_candidate_audit as annual
from tvfree_screener.batch01 import audit_monster_canonical as monster
from tvfree_screener.batch01.session_calendar import SessionCalendar
from tvfree_screener.batch01.selection import rank_candidate_pool
from tvfree_screener.batch01.evaluation import build_five_session_labels
import run as base
import v7_full_tail_research as v7

TARGET_YEARS = (2022, 2026)
CHECK_MONTH = "2024-06"
MIN_TRAIN = 30_000
TAIL_GATE = 0.999
SIGNAL_COLUMNS = ["date", "symbol", "ret1", "ret10", "volr20", "tail_cdf", "tail_p", "range_pct"]
DETECTION_COLUMNS = [
    "year", "signal_date", "symbol", "detection_status", "volr20_first_daily_rank",
    "raw_pool_count_that_day", "post_cooldown_count", "cooldown_blocked_count",
    "ret1_signal_time", "ret10_signal_time", "volr20_signal_time", "tail_cdf_signal_time",
    "tail_p_signal_time", "previous_session_market_median_ret5", "entry_date", "exit_date",
    "entry_price", "exit_price", "gross_5bd_return_pct", "net_5bd_return_0pct",
    "net_5bd_return_0_5pct", "net_5bd_return_1pct", "label_status",
    "entry_fill_quality", "label_definition",
]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def paths() -> dict[str, Path]:
    return {
        "daily": B1 / ".cache/artifacts/tse_daily.csv",
        "calendar": B1 / "reference/xtks_sessions.csv",
        "market": B1 / ".cache/market_returns.parquet",
        "tail_cache": B1 / ".cache/artifacts/v7_causal_tail_cache_2023_2025.csv",
        "parent_spec": B2 / "ANNUAL_CANDIDATE_AUDIT_SPEC.json",
        "monster_spec": B1 / "reports/monster_canonical_spec.json",
        "run_py": TV / "run.py",
        "v7_py": TV / "v7_full_tail_research.py",
        "v9_py": TV / "v9_conditional_quality_research.py",
        "label_helpers": B1 / "evaluation.py",
        "candidate_helpers": B1 / "audit_monster_canonical.py",
        "annual_helpers": B2 / "annual_candidate_audit.py",
        "extension_script": Path(__file__).resolve(),
    }


def freeze() -> dict:
    if SPEC.exists() or SPEC_SHA.exists():
        raise FileExistsError("extension specification already exists; never overwrite it")
    parent, _, _ = annual.verify_frozen_inputs()
    manifest = {k: sha(v) for k, v in paths().items()}
    body = {
        "schema_version": 1,
        "extension_id": "TVFREE-ANNUAL-CANDIDATE-2022-2026-EXT-20260913-03",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_2022_2026_EXTENSION_REPLAY",
        "purpose": "User-requested descriptive extension of the frozen Monster candidate; no model, feature, threshold, or selection tuning.",
        "known_calibration_mismatch": "2024-06 generated 30 tail rows versus 37 frozen-cache rows; tail_p maximum absolute difference 0.03175835206146238. Keep XGBoost 3.4.1, do not search versions or alter gates to force a match, and label 2022/2026 as runtime-sensitive source reconstruction.",
        "parent_audit_id": parent["audit_id"],
        "parent_spec_sha256": sha(B2 / "ANNUAL_CANDIDATE_AUDIT_SPEC.json"),
        "monster_spec_sha256": parent["monster"]["existing_spec_sha256"],
        "years": {
            "2022": "Full calendar-year retrospective diagnostic; later-derived fixed gates mean this is not OOS.",
            "2026": "Partial year from 2026-01-01 through the last frozen daily-data date; forward outcomes unavailable after that date remain unresolved. Report only, no tuning.",
        },
        "reconstruction": {
            "algorithm": "Same v9.score_tail_month recipe: v7.model, y_top025, base.FEATURES, v7.cdf, monthly retraining.",
            "train_purge": "target_end_date strictly earlier than model-month start.",
            "minimum_train_rows": MIN_TRAIN,
            "eligible_universe": "base.eligible_rows with price_cap=1000; prev_volume>=10000, volume>=5000, close>=20, prev_close<=1000 and all base.FEATURES present.",
            "prediction_rows": "All eligible feature rows in the month, including recent rows with immature forward labels; those labels are excluded from scoring and used only for post-score evaluation.",
            "model_parameters": {"n_estimators":160,"max_depth":3,"learning_rate":0.04,"subsample":0.8,"colsample_bytree":0.8,"min_child_weight":18,"reg_lambda":6,"reg_alpha":0.3,"scale_pos_weight":"min(negative/positive,80)","random_state":42,"n_jobs":4},
            "tail_gate": TAIL_GATE,
            "xgboost_version": version("xgboost"),
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
        },
        "candidate_policy": {
            "pool": "tail_cdf>=0.999 AND previous official XTKS-session market median ret5<=0 AND signal-date ret10<=0.5735294117647058.",
            "rank": ["volr20 ascending","tail_cdf descending","tail_p descending","symbol ascending"],
            "daily_limit": "None; emit all qualifying non-cooldown candidates.",
            "cooldown": "Same symbol detected on immediately previous official XTKS session; 2026 year boundary seeded from the frozen 2025-12-30 candidate cache.",
            "target": "Next official XTKS open through fifth official XTKS close including entry, canonical daily-OHLCV labels.",
            "costs": [0.0,0.005,0.01],
        },
        "predeclared_check": {
            "month": CHECK_MONTH,
            "rule": "Compare generated tail-gate date/symbol set to frozen cache; tail_cdf exact and tail_p absolute difference <=1e-9.",
            "drift": "If mismatch, retain results only as same-source reconstruction with runtime sensitivity disclosed; do not tune to force a match.",
        },
        "use_of_results": "Report only. Do not promote/reject/tune any candidate using these annual results. Original frozen spec and report remain unchanged.",
        "source_sha256": manifest,
    }
    raw = (json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    SPEC.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    SPEC_SHA.write_text(digest + "\n", encoding="ascii")
    return {"status":"EXTENSION_SPEC_FROZEN","sha256":digest,"sources":manifest}


def verify() -> tuple[dict, dict[str, str]]:
    annual.verify_frozen_inputs()
    raw = SPEC.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SPEC_SHA.read_text(encoding="ascii").strip().split()[0].lower():
        raise ValueError("extension spec SHA mismatch")
    spec = json.loads(raw.decode("utf-8-sig"))
    if spec.get("status") != "FROZEN_BEFORE_2022_2026_EXTENSION_REPLAY":
        raise ValueError("extension spec is not frozen")
    actual = {k:sha(v) for k,v in paths().items()}
    changed = [k for k in actual if actual[k] != spec["source_sha256"].get(k)]
    if changed:
        raise ValueError(f"frozen extension input hash mismatch: {changed}")
    if version("xgboost") != spec["reconstruction"]["xgboost_version"]:
        raise ValueError("xgboost version differs from preregistered runtime")
    return spec, actual


def features_from_raw(raw: pd.DataFrame) -> pd.DataFrame:
    e = base.eligible_rows(base.build_features(raw), price_cap=1000.0).copy()
    e["date"] = pd.to_datetime(e["date"], errors="raise").dt.normalize()
    e["target_end_date"] = pd.to_datetime(e["target_end_date"], errors="coerce").dt.normalize()
    labeled = e["target5_no"].notna() & e["target_end_date"].notna()
    rank = e.loc[labeled].groupby("date", sort=False)["target5_no"].rank(pct=True, method="average")
    e["y_top025"] = np.nan
    e.loc[labeled, "y_top025"] = (rank >= 0.9975).astype("int8").to_numpy()
    return e


def score_month(e: pd.DataFrame, month: pd.Period) -> tuple[pd.DataFrame, dict]:
    start, end = month.start_time, month.end_time.normalize()
    train_mask = e["target_end_date"].notna() & e["target_end_date"].lt(start)
    pred_mask = e["date"].between(start, end, inclusive="both")
    ntrain, npred = int(train_mask.sum()), int(pred_mask.sum())
    meta = {"month":str(month),"train_rows":ntrain,"pred_rows":npred}
    empty_cols = SIGNAL_COLUMNS + ["model_period","model_train_rows"]
    if ntrain < MIN_TRAIN:
        return pd.DataFrame(columns=empty_cols), {**meta,"status":"SKIPPED_MIN_TRAIN"}
    if npred == 0:
        return pd.DataFrame(columns=empty_cols), {**meta,"status":"SKIPPED_NO_PRED_ROWS"}
    train = e.loc[train_mask]
    y = train["y_top025"].astype("int8")
    if y.nunique() < 2:
        return pd.DataFrame(columns=empty_cols), {**meta,"status":"SKIPPED_DEGENERATE_LABEL"}
    pred = e.loc[pred_mask]
    model = v7.model(y)
    model.fit(train[base.FEATURES], y, verbose=False)
    p_train = model.predict_proba(train[base.FEATURES])[:,1]
    p_pred = model.predict_proba(pred[base.FEATURES])[:,1]
    scored = pred.loc[:,["date","symbol","ret1","ret10","volr20","range_pct"]].copy()
    scored["tail_p"] = p_pred
    scored["tail_cdf"] = v7.cdf(p_train,p_pred)
    scored["model_period"] = str(month)
    scored["model_train_rows"] = ntrain
    out = scored.loc[scored["tail_cdf"].ge(TAIL_GATE)].copy()
    status = {**meta,"status":"SCORED","tail_gate_rows":int(len(out))}
    del model, train, pred, y, p_train, p_pred, scored
    gc.collect()
    return out,status


def calibration_check(e: pd.DataFrame) -> dict:
    period = pd.Period(CHECK_MONTH,freq="M")
    current,status = score_month(e,period)
    cached = pd.read_csv(paths()["tail_cache"],usecols=["date","symbol","tail_cdf","tail_p"],
                         parse_dates=["date"],dtype={"symbol":"string"})
    cached = cached.loc[cached["date"].dt.to_period("M").eq(period)]
    a = set(zip(current["date"].dt.strftime("%Y-%m-%d"),current["symbol"].astype(str)))
    b = set(zip(cached["date"].dt.strftime("%Y-%m-%d"),cached["symbol"].astype(str)))
    same = a == b
    joined = current.merge(cached,on=["date","symbol"],how="inner",suffixes=("_new","_cache"),validate="one_to_one")
    cdf_equal = bool(np.allclose(joined["tail_cdf_new"],joined["tail_cdf_cache"],rtol=0,atol=0)) if len(joined) else same
    p_diff = float((joined["tail_p_new"]-joined["tail_p_cache"]).abs().max()) if len(joined) else 0.0
    match = same and cdf_equal and p_diff <= 1e-9 and status["status"] == "SCORED"
    return {
        "month":CHECK_MONTH,
        "generated_rows":len(current),
        "cached_rows":len(cached),
        "same_date_symbol_set":bool(same),
        "tail_cdf_exact":cdf_equal,
        "tail_p_max_abs_difference":p_diff,
        "status":"MATCHED_FROZEN_CACHE" if match else "SOURCE_RECONSTRUCTION_DRIFT",
        "interpretation":"Generated scores reproduce the frozen cache in the predeclared month." if match else "Same source scoring recipe was reconstructed, but the frozen cache differs; extended results are runtime-sensitive.",
    }


def csv_rows(x: pd.DataFrame) -> pd.DataFrame:
    if x.empty: return pd.DataFrame(columns=DETECTION_COLUMNS)
    z=x.copy()
    z["year"]=pd.to_datetime(z["date"]).dt.year
    gross=pd.to_numeric(z["gross_return"],errors="coerce")
    z["gross_5bd_return_pct"]=gross*100
    z["net_5bd_return_0pct"]=gross*100
    z["net_5bd_return_0_5pct"]=(gross-0.005)*100
    z["net_5bd_return_1pct"]=(gross-0.01)*100
    z=z.rename(columns={
        "date":"signal_date","ret1":"ret1_signal_time","ret10":"ret10_signal_time",
        "volr20":"volr20_signal_time","tail_cdf":"tail_cdf_signal_time","tail_p":"tail_p_signal_time",
        "market_median_ret5_lag1":"previous_session_market_median_ret5",
        "raw_rank":"volr20_first_daily_rank","daily_candidate_count":"raw_pool_count_that_day",
        "cooldown_status":"detection_status",
    })
    return z.loc[:,[c for c in DETECTION_COLUMNS if c in z.columns]]


def pct(x):
    return annual.pct(x)


def render(report: dict) -> str:
    lines=[
        "# Monster / Core候補の年別検出・評価（2022・2026拡張）","",
        f"- 拡張ID: {report['extension_id']}",
        f"- 拡張仕様SHA-256: {report['extension_spec_sha256']}",
        f"- 親監査仕様SHA-256: {report['parent_spec_sha256']}",
        f"- Git SHA: {report.get('git_sha')}",
        f"- V7再構成確認: {report['reconstruction_check']['status']} — {report['reconstruction_check']['interpretation']}",
        "- 2022は後年に確定した固定条件の遡及診断で、OOSではありません。2026はデータ最終日までの部分年で、条件調整に使いません。",
        "- 日次上限なし。全候補を出し、前の東証営業日に検出した同一銘柄だけ1営業日cooldownで除外します。",
        "- 成績は次の東証営業日始値から5営業日目終値。主指標は0.5%のコスト仮定控除後です。","",
        "## Monster 年別成績","",
        "| 年 | スコア期間 | 予測対象行 | 生pool | 検出 | 銘柄数 | 稼働日 | 解決/未解決 | 平均 | 中央値 | 勝率 | +10 | +20 | +50 | -10 | -20 | Top1除外 | Top3除外 | 月プラス | 週プラス |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in report["monster_annual"]:
        y=r["year"]
        if r["status"] not in ("REPLAYED_RETROSPECTIVE","PARTIAL_YTD_SOURCE_RECONSTRUCTION"):
            lines.append(f"| {y} | {r['status']} | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        m=r["primary_net_0_5pct"]; mo=r["month_dependence_net_0_5pct"]; we=r["week_dependence_net_0_5pct"]
        source="保存V7 cache" if y in (2023,2024,2025) else ("ソース再構成" if report["reconstruction_check"]["status"]=="MATCHED_FROZEN_CACHE" else "ソース再構成・runtime差")
        if y==2026: source += " / " + str(r.get("data_through"))
        unresolved=m["requested_count"]-m["resolved_count"]
        lines.append(
            f"| {y} | {source} | {r.get('scored_universe_rows','—')} | {r['raw_pool_rows']} | {r['detected_rows']} | {r['unique_symbols']} | {r['active_dates']} | {m['resolved_count']}/{unresolved} | "
            f"{pct(m.get('mean'))} | {pct(m.get('median'))} | {pct(m.get('win_rate'))} | {pct(m.get('plus10_rate'))} | {pct(m.get('plus20_rate'))} | {pct(m.get('plus50_rate'))} | "
            f"{pct(m.get('minus10_rate'))} | {pct(m.get('minus20_rate'))} | {pct(r['top1_top3_winner_exclusion'].get('mean_excluding_best_one_resolved_return'))} | "
            f"{pct(r['top1_top3_winner_exclusion'].get('mean_excluding_best_three_resolved_returns'))} | {mo['positive_periods']}/{mo['periods']} | {we['positive_periods']}/{we['periods']} |"
        )
    lines += ["","検出銘柄一覧CSV: annual_candidate_detections_2022_2026.csv","cooldown前poolを含む一覧: annual_candidate_pool_2022_2026.csv","","## 採点範囲","",
              "| 年 | 初回スコア日 | 最終スコア日 | 採点済み月 | 学習不足で未採点の月 | データ最終日 |",
              "|---:|---|---|---:|---:|---|"]
    for y in TARGET_YEARS:
        c=report["coverage"][str(y)]
        lines.append(f"| {y} | {c['first_scored_date'] or '—'} | {c['last_scored_date'] or '—'} | {c['scored_months']} | {c['skipped_months']} | {c['data_through']} |")
    lines += ["","## Core V29","","V29 fixed_min98_bothの年別再現用の生教師行、日付付き350銘柄watchlist、当時のYahoo時間足が保存されていないため、2022/2026を含む年別銘柄一覧は復元できません。日足で代替していません。既存の非年次参考値は n=35、平均+4.86%、中央値+2.90%、勝率55.88%、+10率31.43%。Monsterとは対象母集団・エントリー/ターゲット定義が異なり、直接比較できません。","","## 制限","","- 2022は2023以降に由来する固定候補条件を遡及適用した診断です。採点可能な期間より前はゼロ成績ではなく未採点です。",
                "- 2026は部分年です。末尾の5営業日OHLCVがないシグナルは消さず、未解決としてCSVに残しています。",
                "- 再構成確認がruntime差の場合、2022/2026は元cacheの完全再現ではありません。同じV7ソースと設定による参考再構成として扱ってください。",
                "- 日足集合に生存銘柄バイアスがあり、この表は東証全銘柄の完全再現・真のOOS・本番稼働性を示しません。",""]
    return "\n".join(lines)


def run() -> dict:
    spec, manifest = verify()
    print("Loading frozen daily OHLCV and calculating causal features...",flush=True)
    raw=pd.read_csv(paths()["daily"],parse_dates=["date"],dtype={"symbol":"string"})
    for c in ["open","high","low","close","volume"]: raw[c]=pd.to_numeric(raw[c],errors="coerce")
    raw=raw.dropna(subset=["date","symbol","open","high","low","close","volume"])
    data_last=pd.to_datetime(raw["date"]).max().normalize()
    e=features_from_raw(raw)
    del raw
    gc.collect()

    print("Running preregistered cache comparison...",flush=True)
    check=calibration_check(e)
    print(json.dumps(check,ensure_ascii=False),flush=True)
    scored=[]; month_status={y:[] for y in TARGET_YEARS}
    for year in TARGET_YEARS:
        end=data_last if year==2026 else pd.Timestamp(f"{year}-12-31")
        for month in pd.period_range(f"{year}-01",f"{end:%Y-%m}",freq="M"):
            z,s=score_month(e,month); month_status[year].append(s)
            print(f"{month}: {s['status']} train={s.get('train_rows')} pred={s.get('pred_rows')} tails={s.get('tail_gate_rows',0)}",flush=True)
            if len(z): scored.append(z)
    if not scored: raise RuntimeError("no V7 source-reconstructed scores in requested years")
    tail=pd.concat(scored,ignore_index=True)
    tail["date"]=pd.to_datetime(tail["date"]).dt.normalize()
    tail["symbol"]=tail["symbol"].astype("string")
    tail=annual.attach_lagged_market_feature(tail)
    mspec=json.loads((B1/"reports/monster_canonical_spec.json").read_text(encoding="utf-8-sig"))
    _,pool,_=monster._split_pool(tail,mspec)
    pool=pool.loc[pd.to_datetime(pool["date"]).dt.year.isin(TARGET_YEARS)].copy()

    cache=pd.read_csv(paths()["tail_cache"],usecols=SIGNAL_COLUMNS,parse_dates=["date"],dtype={"symbol":"string"})
    cache["date"]=pd.to_datetime(cache["date"]).dt.normalize()
    cache["symbol"]=cache["symbol"].astype("string")
    seed=cache.loc[cache["date"].eq(pd.Timestamp("2025-12-30"))].copy()
    seed=annual.attach_lagged_market_feature(seed)
    _,seed_pool,_=monster._split_pool(seed,mspec)
    all_candidates=pd.concat([seed_pool,pool],ignore_index=True,sort=False)
    calendar=SessionCalendar.from_csv(B1/"reference/xtks_sessions.csv",expected_sha256=spec["source_sha256"]["calendar"])
    ranked=rank_candidate_pool(all_candidates,sessions=calendar.sessions,
        feature_columns=["ret1","ret10","volr20","tail_cdf","tail_p","market_median_ret5_lag1"],
        ranking_terms=[("volr20_rank_value",True),("tail_cdf",False),("tail_p",False)])
    trace_all=annual.apply_all_candidates_cooldown(ranked,calendar.sessions)
    trace=trace_all.loc[pd.to_datetime(trace_all["date"]).dt.year.isin(TARGET_YEARS)].copy()
    detected=trace.loc[trace["cooldown_status"].eq("DETECTED")].copy()

    summaries=[]; eval_parts=[]; coverage={}
    for year in TARGET_YEARS:
        py=trace.loc[pd.to_datetime(trace["date"]).dt.year.eq(year)].copy()
        dy=detected.loc[pd.to_datetime(detected["date"]).dt.year.eq(year)].copy()
        sessions=calendar.sessions[calendar.sessions.year==year]
        cutoff=pd.Timestamp(sessions[-1]) if year==2022 else data_last
        prices=monster._price_subset(dy,calendar,cutoff.strftime("%Y-%m-%d")) if len(dy) else pd.DataFrame(columns=monster.PRICE_COLUMNS)
        labels=build_five_session_labels(prices,dy,calendar)
        if year==2022: labels=monster._periodized(labels,year,cutoff.strftime("%Y-%m-%d"))
        row=annual.summarize_year(year,py,dy,labels,calendar,cutoff)
        statuses=month_status[year]; sm=[s for s in statuses if s["status"]=="SCORED"]
        dates=tail.loc[pd.to_datetime(tail["date"]).dt.year.eq(year),"date"]
        row.update({"scored_universe_rows":int(sum(s["pred_rows"] for s in sm)),
                    "scored_month_count":len(sm),"data_through":data_last.strftime("%Y-%m-%d") if year==2026 else f"{year}-12-30",
                    "status":"PARTIAL_YTD_SOURCE_RECONSTRUCTION" if year==2026 else "REPLAYED_RETROSPECTIVE",
                    "score_source":"V7 monthly source reconstruction","calibration_status":check["status"]})
        summaries.append(row)
        coverage[str(year)]={"first_scored_date":pd.Timestamp(dates.min()).date().isoformat() if len(dates) else None,
            "last_scored_date":pd.Timestamp(dates.max()).date().isoformat() if len(dates) else None,
            "scored_months":len(sm),"skipped_months":sum(s["status"].startswith("SKIPPED") for s in statuses),
            "data_through":row["data_through"],"month_status":statuses}
        if len(dy):
            cols=["date","symbol","family","spec_hash","entry_date","exit_date","entry_price","exit_price","gross_return",
                  "label_status","label_resolved","entry_fill_quality","label_definition"]
            eval_parts.append(dy.merge(labels[cols],on=["date","symbol","family","spec_hash"],how="left",validate="one_to_one"))

    old=json.loads((REPORTS/"annual_candidate_evaluation.json").read_text(encoding="utf-8-sig"))
    existing={r["year"]:r for r in old["monster"]["annual"]}
    annual_rows=[]
    for y in range(2022,2027):
        ext=next((r for r in summaries if r["year"]==y),None)
        if ext is not None: annual_rows.append(ext)
        elif y in existing: annual_rows.append(existing[y])
    new_eval=pd.concat(eval_parts,ignore_index=True) if eval_parts else detected.iloc[0:0].copy()
    new_csv=csv_rows(new_eval)
    old_csv=pd.read_csv(CACHE/"annual_candidate_detections.csv",dtype={"symbol":"string"})
    combined=pd.concat([old_csv,new_csv],ignore_index=True,sort=False)
    combined=combined.sort_values(["year","signal_date","volr20_first_daily_rank","symbol"],kind="mergesort",na_position="last")
    OUT_DETECTIONS.parent.mkdir(parents=True,exist_ok=True)
    combined.to_csv(OUT_DETECTIONS,index=False,encoding="utf-8-sig",na_rep="")
    old_pool=pd.read_csv(CACHE/"annual_candidate_all_pool.csv",dtype={"symbol":"string"})
    pexport=trace.copy(); pexport["year"]=pd.to_datetime(pexport["date"]).dt.year
    combined_pool=pd.concat([old_pool,pexport],ignore_index=True,sort=False)
    combined_pool=combined_pool.sort_values(["year","date","raw_rank","symbol"],kind="mergesort",na_position="last")
    combined_pool.to_csv(OUT_POOL,index=False,encoding="utf-8-sig",na_rep="")

    report={"schema_version":1,"extension_id":spec["extension_id"],"generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "status":"COMPLETE_REPORT_ONLY","extension_spec_sha256":sha(SPEC),"parent_spec_sha256":spec["parent_spec_sha256"],
        "source_sha256":manifest,"git_sha":annual.git_sha(),"production_modified":False,"reconstruction_check":check,
        "data_through":data_last.strftime("%Y-%m-%d"),"generated_tail_gate_rows":len(tail),"coverage":coverage,
        "monster_annual":annual_rows,"core_annual":old["core"]["annual"],"core_reference":old["core"]["prior_aggregate_reference"],
        "outputs":{"detections_csv":str(OUT_DETECTIONS.relative_to(ROOT).as_posix()),"candidate_pool_csv":str(OUT_POOL.relative_to(ROOT).as_posix())},
        "interpretation":{"2022":"fixed later-derived policy, retrospective diagnostic; not OOS",
            "2026":"partial year through frozen daily data maximum; report only; no tuning",
            "xgboost":version("xgboost"),"daily_to_intraday_synthesis":False}}
    clean=annual.safe_json(report)
    OUT_JSON.write_text(json.dumps(clean,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    OUT_MD.write_text(render(clean),encoding="utf-8")
    return clean


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--freeze-spec",action="store_true")
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.freeze_spec:
        print(json.dumps(freeze(),ensure_ascii=False,indent=2)); return
    spec,manifest=verify()
    if a.verify_only:
        print(json.dumps({"status":"EXTENSION_INPUTS_VERIFIED","id":spec["extension_id"],"spec_sha256":sha(SPEC),"source_count":len(manifest),"xgboost":version("xgboost")},ensure_ascii=False,indent=2)); return
    r=run()
    print(json.dumps({"status":r["status"],"reconstruction_check":r["reconstruction_check"],
        "data_through":r["data_through"],"years":[{"year":x["year"],"status":x["status"],"n":x.get("detected_rows"),
        "mean":x.get("primary_net_0_5pct",{}).get("mean"),"median":x.get("primary_net_0_5pct",{}).get("median")} for x in r["monster_annual"]],
        "detections_csv":r["outputs"]["detections_csv"],"summary_markdown":str(OUT_MD.relative_to(ROOT).as_posix())},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()




