"""One-time diagnostic of the four already-frozen CORE-TREND-COMPRESSION policies.

This user-directed deviation is exploratory only. It cannot promote a policy or
open any period beyond the original 2022H2-2023 discovery window.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from tvfree_screener.batch02 import core_trend_compression_audit as audit

BATCH=Path(__file__).resolve().parent
SPEC=BATCH/"reports/core_trend_compression_fixed_policy_diagnostic_spec.json"
SPEC_SHA=BATCH/"reports/core_trend_compression_fixed_policy_diagnostic_spec.sha256"
REPORT=BATCH/"reports/core_trend_compression_fixed_policy_diagnostic.json"
REPORT_MD=BATCH/"reports/core_trend_compression_fixed_policy_diagnostic.md"
TOP_NS=(1,2,3,5)

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1<<20),b""): h.update(block)
 return h.hexdigest()

def verify_freeze():
 raw=SPEC.read_bytes()
 actual=hashlib.sha256(raw).hexdigest()
 expected=SPEC_SHA.read_text(encoding="utf-8").split()[0]
 if actual!=expected: raise ValueError("diagnostic spec hash mismatch")
 spec=json.loads(raw)
 if spec["diagnostic_runner_sha256"]!=sha(Path(__file__)): raise ValueError("diagnostic runner changed after freeze")
 prep=audit.read_prepared()
 if prep["spec_sha256"]!=spec["family_spec_sha256"]: raise ValueError("family spec hash mismatch")
 if prep["decision_hashes"]!=spec["prepared_decision_hashes"]: raise ValueError("frozen selection hashes differ")
 expected_files=spec["prepared_file_hashes"]
 for key,path in (("pool",audit.POOL),("ranked",audit.RANKED),("selected",audit.SELECTED)):
  if sha(path)!=expected_files[key]: raise ValueError("prepared decision artifact changed: "+key)
 return spec,prep

def run():
 if REPORT.exists() or REPORT_MD.exists(): raise FileExistsError("diagnostic report already exists")
 spec,prep=verify_freeze()
 family,cal,_=audit.verify_inputs()
 pool=pd.read_parquet(audit.POOL)
 selected=pd.read_parquet(audit.SELECTED)
 cal_dates=cal["date"].to_numpy()
 pool_labels=audit.join_labels(pool,cal_dates)
 pool_summary=audit.label_summary(pool_labels,costs=(0.0,audit.COST,0.01))
 pool_segments=audit.segment_metrics(pool_labels)
 year_idx=int(cal.loc[cal["date"].le(audit.YEAR_END),"session_index"].max())
 active=pd.DatetimeIndex(cal.loc[(cal["date"]>=audit.START)&(cal["session_index"]<=year_idx-5),"date"])
 pool_cohorts,pool_daily=audit.cohort(pool,pool_labels,active)
 policies={}
 for n in TOP_NS:
  rows=selected.loc[selected["top_n"].eq(n)].copy()
  joined=audit.join_labels(rows,cal_dates)
  signal=audit.label_summary(joined,costs=(0.0,audit.COST,0.01))
  segments=audit.segment_metrics(joined)
  cohorts,daily=audit.cohort(rows,joined,active)
  common=daily.loc[daily["cohort_status"].eq("COMPLETE"),["date","cohort_return"]].merge(
   pool_daily.loc[pool_daily["cohort_status"].eq("COMPLETE"),["date","cohort_return"]],
   on="date",suffixes=("_policy","_pool"),validate="one_to_one")
  counts=rows.groupby("date",sort=True).size()
  net=signal["round_trip_cost_scenarios"][f"{audit.COST:g}"]
  policies[str(n)]={
   "frozen_policy_sha256":prep["policy_hashes"][str(n)]["policy_sha256"],
   "selection_sha256":prep["policy_hashes"][str(n)]["selection_sha256"],
   "selected_rows":int(len(rows)),
   "active_days":int(counts.size),
   "selected_names_per_active_day":{"mean":float(counts.mean()),"median":float(counts.median()),
    "max":int(counts.max()),"distribution":{str(k):int(v) for k,v in counts.value_counts().sort_index().items()}},
   "signal_metrics":signal,
   "signal_segments_and_concentration":segments,
   "daily_cohort_metrics_net_0_5pct":cohorts,
   "daily_cohort_coverage":{"active_days":int(daily["selected_count"].gt(0).sum()),
    "complete_days":int(daily["cohort_status"].eq("COMPLETE").sum()),
    "partial_days":int(daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum()),
    "abstain_days":int(daily["cohort_status"].eq("ABSTAIN").sum())},
   "resolved_only_signal_mean_lift_vs_resolved_full_pool":(
    float(net["mean"]-pool_summary["round_trip_cost_scenarios"][f"{audit.COST:g}"]["mean"])
    if net["mean"] is not None else None),
   "common_complete_days_vs_full_pool":int(len(common)),
   "paired_daily_value_add_vs_full_pool":(
    float((common["cohort_return_policy"]-common["cohort_return_pool"]).mean()) if len(common) else None),
   "promotion_status":"DIAGNOSTIC_ONLY_NO_PROMOTION",
  }
 result={
  "schema_version":1,
  "diagnostic_id":spec["diagnostic_id"],
  "evidence_level":"RETROSPECTIVE_EXPLORATORY",
  "diagnostic_spec_sha256":hashlib.sha256(SPEC.read_bytes()).hexdigest(),
  "diagnostic_runner_sha256":sha(Path(__file__)),
  "family_spec_sha256":prep["spec_sha256"],
  "preparation_receipt_sha256":sha(audit.PREP),
  "recovery_receipt_sha256":sha(audit.RECOVERY),
  "selection_hashes_unchanged":True,
  "prior_full_pool_result_seen":True,
  "period":"2022-07-01 through 2023-12-22; all exits no later than last 2023 official session",
  "current_system_benchmark_context":spec["current_system_benchmark_context"],
  "full_pool_reference":{"signal_metrics":pool_summary,"segments":pool_segments,
   "daily_cohort_metrics_net_0_5pct":pool_cohorts,
   "complete_days":int(pool_daily["cohort_status"].eq("COMPLETE").sum()),
   "partial_days":int(pool_daily["cohort_status"].eq("PARTIAL_UNRESOLVED").sum())},
  "all_frozen_top_n_policies":policies,
  "decision":"EXPLORATORY_DIAGNOSTIC_COMPLETE; NO_POLICY_PROMOTED; 2024+ CLOSED",
  "deviation":"All four Top-N outcome summaries are exposed together because the previously frozen full-pool gate was incomplete on every active date. No N, threshold, ranking, feature, or cooldown was changed. This readout is not a gate pass or independent validation.",
  "unresolved_rows_retained_in_requested_counts":True,
  "round_trip_cost_assumption":0.005,
  "2024_2025_2026_outcomes_opened":False,
  "production_modified":False,
 }
 REPORT.parent.mkdir(parents=True,exist_ok=True)
 REPORT.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
 summary=result["full_pool_reference"]["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]
 lines=["# Frozen Top-N policy diagnostic","",
  "- Status: exploratory only; no policy promotion.",
  "- All four pre-outcome Top-N selections were evaluated together; no parameter search or threshold change.",
  "- The original full-pool gate was inconclusive because every active day had unresolved candidates.",
  "- Unresolved selected rows remain in requested counts; resolved-return summaries are explicitly conditional on resolved labels.",
  "- 2024, 2025, and 2026 outcomes remain closed.",
  f"- Full-pool net mean / median / win: {summary.get('mean')} / {summary.get('median')} / {summary.get('win_rate')}.",
  "",
  "| Top-N | n | resolved | net mean | median | win | +10% | -10% | complete policy days | unresolved |",
  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
 for n,v in policies.items():
  m=v["signal_metrics"]; net=m["round_trip_cost_scenarios"][f"{audit.COST:g}"]
  lines.append(f"| {n} | {m['selected_count']} | {m['resolved_count']} | {net.get('mean')} | {net.get('median')} | {net.get('win_rate')} | {net.get('plus10_rate')} | {net.get('minus10_rate')} | {v['daily_cohort_coverage']['complete_days']} | {m['unresolved_count']} |")
 lines += ["","The local current Bot benchmark report (generated 2026-09-09) lists Stable ★6 at n=55, mean +6.6%, median +1.5%, win 56.4%. This is context only: its BOTTOM-signal population and signal-close target differ from this all-TSE, next-session-open experiment, so the figures are not directly comparable."]
 REPORT_MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
 return result

if __name__=="__main__":
 r=run()
 print(json.dumps({"decision":r["decision"],"top_n":{
  n:{"n":v["signal_metrics"]["selected_count"],
   "resolved":v["signal_metrics"]["resolved_count"],
   "net_mean":v["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["mean"],
   "median":v["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["median"],
   "win_rate":v["signal_metrics"]["round_trip_cost_scenarios"][f"{audit.COST:g}"]["win_rate"],
   "unresolved":v["signal_metrics"]["unresolved_count"],
   "complete_days":v["daily_cohort_coverage"]["complete_days"]}
  for n,v in r["all_frozen_top_n_policies"].items()}},ensure_ascii=False,indent=2))
