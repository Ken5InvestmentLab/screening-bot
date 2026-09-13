"""Frozen discovery audit for CORE-TREND-COMPRESSION-20260913-01."""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

BATCH_DIR=Path(__file__).resolve().parent
WORKTREE=BATCH_DIR.parents[1]
sys.path.insert(0,str(WORKTREE))
from tvfree_screener.batch01.evaluation import cohort_summary,daily_cohorts,label_summary,return_metrics
from tvfree_screener.batch01.selection import PolicySpec,apply_selection_policy,rank_candidate_pool

B1=BATCH_DIR.parent/"batch01"
SPEC=BATCH_DIR/"FAMILY_SPEC.json"
SPEC_SHA=BATCH_DIR/"FAMILY_SPEC.sha256"
FEATURE=B1/".cache/core_moderate_features_through_2023.parquet"
LABEL=B1/".cache/core_moderate_ridge_discovery_labels.parquet"
CALENDAR=B1/"reference/xtks_sessions.csv"
CACHE=BATCH_DIR/".cache"
REPORTS=BATCH_DIR/"reports"
PREP=CACHE/"core_trend_compression_prepare_receipt.json"
RECOVERY=CACHE/"core_trend_compression_recovery_receipt.json"
POOL=CACHE/"core_trend_compression_candidate_pool.parquet"
RANKED=CACHE/"core_trend_compression_ranked_pool.parquet"
SELECTED=CACHE/"core_trend_compression_selections.parquet"
REPORT=REPORTS/"core_trend_compression_discovery.json"
REPORT_MD=REPORTS/"core_trend_compression_discovery.md"
EXPECTED={"feature_sha256":"f66bf52ab73a4764c9b4c55857877970f536a6d96485d70282b00b6ee6a4bec4",
"label_artifact_sha256":"abf9c3181dfa1f86f78b75528eafaa27ba9bb9250db17b5b14e8970d60ad2732",
"calendar_sha256":"74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68"}
LABEL_FAMILY="core_moderate_capped_return_ridge_v1"
LABEL_SPEC="6f56fc4c0f914f6faec0285e915a393044003505bc5d71cabb52e4d7778dcfa7"
EXPERIMENT="CORE-TREND-COMPRESSION-20260913-01"
START=pd.Timestamp("2022-07-01")
YEAR_END=pd.Timestamp("2023-12-31")
COST=0.005
TOP_NS=(1,2,3,5)
FEATURE_COLUMNS=["rv_ratio_5_20","ret20"]
OUTCOME_COLUMNS={"gross_return","label_status","label_resolved","entry_date","exit_date","entry_price","exit_price","label_available_at"}

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1<<20),b""): h.update(block)
 return h.hexdigest()

def digest_frame(frame,columns):
 work=frame.loc[:,[c for c in columns if c in frame]].copy()
 if "date" in work: work["date"]=pd.to_datetime(work["date"]).dt.strftime("%Y-%m-%d")
 if "symbol" in work: work["symbol"]=work["symbol"].astype("string")
 h=hashlib.sha256()
 for i in range(0,len(work),100_000):
  values=pd.util.hash_pandas_object(work.iloc[i:i+100_000],index=False,categorize=True).to_numpy(dtype="uint64")
  h.update(values.tobytes())
 return h.hexdigest()

def verify_inputs():
 spec_bytes=SPEC.read_bytes()
 spec=json.loads(spec_bytes)
 spec_hash=hashlib.sha256(spec_bytes).hexdigest()
 if spec_hash!=SPEC_SHA.read_text(encoding="utf-8").split()[0]: raise ValueError("frozen family spec hash mismatch")
 if spec.get("experiment_id")!=EXPERIMENT: raise ValueError("unexpected experiment ID")
 hashes={"spec_sha256":spec_hash,"feature_sha256":sha(FEATURE),"label_artifact_sha256":sha(LABEL),"calendar_sha256":sha(CALENDAR)}
 if {k:hashes[k] for k in EXPECTED}!=EXPECTED: raise ValueError("frozen input hash mismatch")
 cal=pd.read_csv(CALENDAR,parse_dates=["date"])
 cal["date"]=pd.to_datetime(cal["date"],errors="raise").dt.normalize()
 if cal["date"].duplicated().any() or cal["session_index"].duplicated().any() or not cal["date"].is_monotonic_increasing:
  raise ValueError("official calendar is invalid")
 return spec,cal,hashes

def rolling_stats(ix,returns):
 ix=np.asarray(ix,dtype=np.int64); ret=np.asarray(returns,dtype=np.float64)
 if len(ix)!=len(ret): raise ValueError("rolling inputs are misaligned")
 rv5=pd.Series(ret).rolling(5,min_periods=5).std(ddof=0).to_numpy()
 rv20=pd.Series(ret).rolling(20,min_periods=20).std(ddof=0).to_numpy()
 steps=np.zeros(len(ix),dtype=np.int8)
 if len(ix)>1: steps[1:]=(np.diff(ix)==1).astype(np.int8)
 consecutive=pd.Series(steps).rolling(19,min_periods=19).sum().eq(19).to_numpy()
 return rv5,rv20,consecutive

def build_pool(cal):
 cols=["date","symbol","open","high","low","close","volume","ret1","ret5","ret20"]
 f=pd.read_parquet(FEATURE,columns=cols)
 f["date"]=pd.to_datetime(f["date"],errors="raise").dt.normalize()
 if f.duplicated(["date","symbol"]).any(): raise ValueError("duplicate signal feature rows")
 if not f.groupby("symbol",sort=False,observed=True)["date"].apply(lambda x:x.is_monotonic_increasing).all():
  raise ValueError("dates not monotonic within symbol")
 session_map=dict(zip(cal["date"],cal["session_index"]))
 f["session_index"]=f["date"].map(session_map)
 if f["session_index"].isna().any(): raise ValueError("feature date missing from calendar")
 f["session_index"]=f["session_index"].astype("int32")
 year_idx=int(cal.loc[cal["date"].le(YEAR_END),"session_index"].max())
 start_idx=int(cal.loc[cal["date"].ge(START),"session_index"].iloc[0])
 last_idx=year_idx-5
 last_date=pd.Timestamp(cal.loc[cal["session_index"].eq(last_idx),"date"].iloc[0])
 chunks=[]; eligible=0; n_pool=0
 for _,g in f.groupby("symbol",sort=False,observed=True):
  ix=g["session_index"].to_numpy(dtype=np.int64)
  ret1=pd.to_numeric(g["ret1"],errors="coerce").to_numpy(dtype=np.float64)
  rv5,rv20,consecutive=rolling_stats(ix,ret1)
  ratio=np.divide(rv5,rv20,out=np.full(len(g),np.nan),where=np.isfinite(rv20)&(rv20>0))
  bars=g[["open","high","low","close","volume"]].to_numpy(dtype=np.float64)
  op,hi,lo,close,vol=bars.T
  quality=np.isfinite(bars).all(axis=1)&(bars[:,:4]>0).all(axis=1)&(vol>0)
  quality &= (hi>=np.maximum(op,close))&(lo<=np.minimum(op,close))&(hi>=lo)
  ret5=pd.to_numeric(g["ret5"],errors="coerce").to_numpy(dtype=np.float64)
  ret20=pd.to_numeric(g["ret20"],errors="coerce").to_numpy(dtype=np.float64)
  base=(ix>=start_idx)&(ix<=last_idx)&quality&np.isfinite(ret5)&np.isfinite(ret20)&(ret20>0)&(ret5>=0)
  eligible+=int(base.sum())
  keep=base&consecutive&np.isfinite(ratio)&(ratio<1.0)
  if keep.any():
   part=g.loc[keep,["date","symbol","ret20"]].copy()
   part["rv5"]=rv5[keep]; part["rv20"]=rv20[keep]; part["rv_ratio_5_20"]=ratio[keep]
   part["symbol"]=part["symbol"].astype("string")
   chunks.append(part); n_pool+=int(keep.sum())
 del f
 if chunks: pool=pd.concat(chunks,ignore_index=True)
 else: pool=pd.DataFrame(columns=["date","symbol","ret20","rv5","rv20","rv_ratio_5_20"])
 spec_hash=hashlib.sha256(SPEC.read_bytes()).hexdigest()
 pool["date"]=pd.to_datetime(pool["date"]).dt.normalize()
 pool["family"]="core_trend_compression"; pool["spec_hash"]=spec_hash
 pool["identity_key"]=pool["symbol"].astype("string")
 pool=pool.sort_values(["date","rv_ratio_5_20","ret20","symbol"],ascending=[True,True,False,True],kind="mergesort").reset_index(drop=True)
 active=cal.loc[cal["session_index"].between(start_idx,last_idx),"date"]
 counts={"source_feature_rows":int(pd.read_parquet(FEATURE,columns=["date"]).shape[0]),
 "signal_rows_passing_price_quality_and_ret5_ret20":eligible,"candidate_pool_rows":n_pool,
 "candidate_bearing_days":int(pool["date"].nunique()),"candidate_symbols":int(pool["symbol"].nunique()),
 "max_candidates_per_day":int(pool.groupby("date").size().max()) if len(pool) else 0,
 "last_signal_date_within_2023_exit_horizon":last_date.date().isoformat(),
 "warmup_begins":"2022-01-04"}
 return pool,pd.DatetimeIndex(active),counts

def rank_select(pool,sessions):
 ranked=rank_candidate_pool(pool,sessions=sessions,feature_columns=FEATURE_COLUMNS,
  ranking_terms=[("rv_ratio_5_20",True),("ret20",False)])
 frames=[]; ph={}
 for n in TOP_NS:
  result=apply_selection_policy(ranked,sessions=sessions,policy=PolicySpec("core",n,f"{EXPERIMENT}:TOP{n}"))
  selected=result.selected.copy(); selected["top_n"]=n; frames.append(selected)
  ph[str(n)]={"policy_sha256":result.policy_sha256,"selection_sha256":result.selection_sha256}
 selected=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
 for name in list(pool.columns)+list(ranked.columns)+list(selected.columns):
  if name.lower() in OUTCOME_COLUMNS or name.lower().startswith(("future_","target","label_","realized_","exit_")):
   raise ValueError("outcome column leaked into decision artifact")
 return ranked,selected,ph

def prep(verify=False):
 spec,cal,hashes=verify_inputs()
 if verify:
  receipt=json.loads(PREP.read_text(encoding="utf-8"))
  if receipt["input_hashes"]!=hashes or receipt["runner_sha256"]!=sha(Path(__file__)):
   raise ValueError("preparation freeze/code/input changed")
  pool,sessions,_=build_pool(cal); ranked,selected,_=rank_select(pool,sessions)
  got={"pool":digest_frame(pool,["date","symbol","ret20","rv5","rv20","rv_ratio_5_20"]),
       "ranked":digest_frame(ranked,["date","symbol","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"]),
       "selected":digest_frame(selected,["date","symbol","top_n","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"])}
  if got!=receipt["decision_hashes"]: raise ValueError("feature-only reproduction hash mismatch")
  return {"status":"PREPARE_REPRODUCED","decision_hashes":got}
 if PREP.exists(): raise FileExistsError("prepare receipt exists; use verify-prepare")
 pool,sessions,counts=build_pool(cal); ranked,selected,policies=rank_select(pool,sessions)
 CACHE.mkdir(parents=True,exist_ok=True)
 pool.to_parquet(POOL,index=False,compression="zstd")
 ranked.to_parquet(RANKED,index=False,compression="zstd")
 selected.to_parquet(SELECTED,index=False,compression="zstd")
 decision_hashes={"pool":digest_frame(pool,["date","symbol","ret20","rv5","rv20","rv_ratio_5_20"]),
  "ranked":digest_frame(ranked,["date","symbol","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"]),
  "selected":digest_frame(selected,["date","symbol","top_n","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"])}
 receipt={"schema_version":1,"experiment_id":EXPERIMENT,"prepared_at_utc":datetime.now(timezone.utc).isoformat(),
  "spec_sha256":hashes["spec_sha256"],"runner_sha256":sha(Path(__file__)),
  "selection_helper_sha256":sha(B1/"selection.py"),"evaluation_helper_sha256":sha(B1/"evaluation.py"),
  "input_hashes":hashes,"label_metadata":{"family":LABEL_FAMILY,"spec_hash":LABEL_SPEC,"numeric_outcome_values_opened":False},
  "counts":counts,"candidate_pool_spec":spec["candidate_pool"],"ranking_spec":spec["ranking"],"selection_spec":spec["selection"],
  "decision_hashes":decision_hashes,"policy_hashes":policies,"pool_file_sha256":sha(POOL),
  "ranked_file_sha256":sha(RANKED),"selected_file_sha256":sha(SELECTED),"outcome_values_opened":False}
 PREP.write_text(json.dumps(receipt,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
 return {"status":"PREPARED_BEFORE_OUTCOME_ACCESS","counts":counts,"decision_hashes":decision_hashes}

def read_prepared():
 if not PREP.exists(): raise FileNotFoundError("prepare must precede outcome access")
 receipt=json.loads(PREP.read_text(encoding="utf-8"))
 _,_,hashes=verify_inputs()
 if receipt["input_hashes"]!=hashes: raise ValueError("frozen prepare input hashes changed")
 if receipt["runner_sha256"]!=sha(Path(__file__)):
  if not RECOVERY.exists(): raise ValueError("runner changed after outcomes opened; explicit engineering recovery receipt required")
  recovery=json.loads(RECOVERY.read_text(encoding="utf-8"))
  if recovery.get("previous_runner_sha256")!=receipt["runner_sha256"] or recovery.get("current_runner_sha256")!=sha(Path(__file__)):
   raise ValueError("engineering recovery receipt does not match current runner")
  if recovery.get("decision_hashes")!=receipt.get("decision_hashes") or not recovery.get("selection_reproduced"):
   raise ValueError("recovery did not preserve frozen decision artifacts")
 for key,path in [("pool_file_sha256",POOL),("ranked_file_sha256",RANKED),("selected_file_sha256",SELECTED)]:
  if receipt[key]!=sha(path): raise ValueError("prepared artifact hash mismatch: "+path.name)
 return receipt

def recover_prepare():
 receipt=json.loads(PREP.read_text(encoding="utf-8"))
 _,cal,hashes=verify_inputs()
 if receipt["input_hashes"]!=hashes: raise ValueError("frozen prepare inputs changed")
 file_hashes={"pool":sha(POOL),"ranked":sha(RANKED),"selected":sha(SELECTED)}
 expected_files={"pool":receipt["pool_file_sha256"],"ranked":receipt["ranked_file_sha256"],"selected":receipt["selected_file_sha256"]}
 if file_hashes!=expected_files: raise ValueError("prepared Parquet artifacts changed")
 pool,sessions,_=build_pool(cal); ranked,selected,_=rank_select(pool,sessions)
 got={"pool":digest_frame(pool,["date","symbol","ret20","rv5","rv20","rv_ratio_5_20"]),
  "ranked":digest_frame(ranked,["date","symbol","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"]),
  "selected":digest_frame(selected,["date","symbol","top_n","raw_rank","daily_candidate_count","rv_ratio_5_20","ret20"])}
 if got!=receipt["decision_hashes"]: raise ValueError("engineering recovery changed frozen membership or selection")
 recovery={"schema_version":1,"experiment_id":EXPERIMENT,"recovery_kind":"EVALUATION_JOIN_KEY_FIX",
  "created_at_utc":datetime.now(timezone.utc).isoformat(),"previous_runner_sha256":receipt["runner_sha256"],
  "current_runner_sha256":sha(Path(__file__)),"input_hashes":hashes,"prepared_file_hashes":file_hashes,
  "decision_hashes":got,"selection_reproduced":True,
  "prior_evaluation_attempt":{"status":"ABORTED_ENGINEERING_AFTER_POOL_LABEL_SUMMARY_IN_MEMORY",
   "numeric_outcomes_accessed":True,"summary_emitted_or_persisted":False,
   "failure":"daily_cohorts required explicit date/symbol join_columns"},
  "recovery_scope":"Evaluation plumbing only; no candidate, rank, threshold, cooldown, or period changes.",
  "future_periods_opened":False}
 RECOVERY.write_text(json.dumps(recovery,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
 return {"status":"ENGINEERING_RECOVERY_FROZEN","decision_hashes":got,"runner_sha256":recovery["current_runner_sha256"]}

def join_labels(decisions,sessions):
 columns=["date","symbol","family","spec_hash","entry_date","exit_date","entry_price","exit_price",
  "gross_return","label_status","label_resolved","label_available_at","session_index"]
 labels=pd.read_parquet(LABEL,columns=columns)
 labels["date"]=pd.to_datetime(labels["date"],errors="raise").dt.normalize()
 labels["symbol"]=labels["symbol"].astype("string")
 if labels.duplicated(["date","symbol"]).any(): raise ValueError("outcome keys are not unique")
 if set(labels["family"].dropna().unique())!={LABEL_FAMILY} or set(labels["spec_hash"].dropna().unique())!={LABEL_SPEC}:
  raise ValueError("outcome source family/spec differs from pinned metadata")
 if not labels["label_resolved"].equals(labels["label_status"].eq("RESOLVED")): raise ValueError("label status/resolution mismatch")
 decisions=decisions.loc[:,["date","symbol"]].copy()
 decisions["date"]=pd.to_datetime(decisions["date"],errors="raise").dt.normalize()
 decisions["symbol"]=decisions["symbol"].astype("string")
 if decisions.duplicated(["date","symbol"]).any(): raise ValueError("duplicate decisions")
 out=decisions.merge(labels,on=["date","symbol"],how="left",validate="one_to_one",indicator=True)
 missing=out["_merge"].eq("left_only")
 out.loc[missing,"label_status"]="LABEL_ROW_MISSING"; out.loc[missing,"label_resolved"]=False
 ix={pd.Timestamp(d):i for i,d in enumerate(sessions)}
 positions=out["date"].map(ix)
 valid=~missing
 if positions.loc[valid].isna().any(): raise ValueError("decision date not in calendar")
 pos=positions.loc[valid].to_numpy(dtype=int)
 if (pos+5>=len(sessions)).any(): raise ValueError("decision date has no fifth-session exit")
 expected_entry=pd.Series(sessions[pos+1],index=out.index[valid])
 expected_exit=pd.Series(sessions[pos+5],index=out.index[valid])
 if not pd.to_datetime(out.loc[valid,"entry_date"]).dt.normalize().equals(expected_entry) or not pd.to_datetime(out.loc[valid,"exit_date"]).dt.normalize().equals(expected_exit):
  raise ValueError("outcome label entry/exit timing mismatch")
 resolved=out["label_resolved"].fillna(False).astype(bool)
 numeric=out.loc[resolved,["gross_return","entry_price","exit_price"]].apply(pd.to_numeric,errors="coerce")
 if not np.isfinite(numeric.to_numpy()).all() or (numeric["entry_price"]<=0).any(): raise ValueError("invalid resolved target price")
 check=numeric["exit_price"]/numeric["entry_price"]-1
 if not np.allclose(check.to_numpy(),numeric["gross_return"].to_numpy(),rtol=1e-8,atol=1e-10): raise ValueError("gross return/price mismatch")
 out["label_resolved"]=resolved; out["gross_return"]=pd.to_numeric(out["gross_return"],errors="coerce")
 return out.drop(columns="_merge")

def concentration(joined):
 x=joined.loc[joined["label_resolved"].astype(bool)]
 if x.empty: return {"resolved_rows":0,"distinct_symbols":0,"top1_share":None,"top5_share":None,"hhi":None}
 counts=x.groupby("symbol",observed=True).size().sort_values(ascending=False); n=int(counts.sum()); shares=counts/n
 return {"resolved_rows":n,"distinct_symbols":int(len(counts)),"top1_share":float(shares.iloc[0]),
  "top5_share":float(shares.head(5).sum()),"hhi":float(np.square(shares.to_numpy()).sum())}

def segment_metrics(joined):
 x=joined.loc[joined["label_resolved"].astype(bool)].copy()
 x["net"]=pd.to_numeric(x["gross_return"],errors="coerce")-COST
 x["month"]=x["date"].dt.to_period("M").astype(str); x["week"]=x["date"].dt.strftime("%G-W%V")
 def groups(col): return {str(k):return_metrics(g["net"],requested_count=len(g)) for k,g in x.groupby(col,sort=True)}
 return {"monthly":groups("month"),"weekly":groups("week"),"symbol_concentration":concentration(joined)}

def cohort(keys,joined,active_sessions):
 daily=daily_cohorts(keys.loc[:,["date","symbol"]],joined,sessions=active_sessions,join_columns=("date","symbol"))
 complete=daily["cohort_status"].eq("COMPLETE")
 daily.loc[complete,"cohort_return"]=daily.loc[complete,"cohort_return"]-COST
 return cohort_summary(daily),daily

def positive(m):
 return all(m.get(k) is not None and float(m[k])>0 for k in ("mean","median","mean_excluding_top3_winners"))

def evaluate():
 receipt=read_prepared()
 spec,cal,hashes=verify_inputs()
 pool=pd.read_parquet(POOL); selected=pd.read_parquet(SELECTED)
 year_idx=int(cal.loc[cal["date"].le(YEAR_END),"session_index"].max())
 active=pd.DatetimeIndex(cal.loc[(cal["date"]>=START)&(cal["session_index"]<=year_idx-5),"date"])
 joined=join_labels(pool,cal["date"].to_numpy())
 pool_stats=label_summary(joined,costs=(0.0,COST,0.01))
 pool_seg=segment_metrics(joined)
 pool_cohort,pd_pool=cohort(pool,joined,active)
 active_days=int(pd_pool["selected_count"].gt(0).sum())
 partial=int(pd_pool["cohort_status"].eq("PARTIAL_UNRESOLVED").sum())
 net=pool_stats["round_trip_cost_scenarios"][f"{COST:g}"]
 sig_ok=positive(net); coh_ok=positive(pool_cohort)
 decision=("INCONCLUSIVE_INCOMPLETE_FULL_POOL_COHORTS" if partial or pool_cohort["n"]==0
  else "KEEP" if sig_ok and coh_ok else "REJECT_POOL_GATE")
 result={"schema_version":1,"experiment_id":EXPERIMENT,"evidence_level":"RETROSPECTIVE_PROVISIONAL",
  "spec_sha256":receipt["spec_sha256"],"runner_sha256":receipt["runner_sha256"],
  "input_hashes":hashes,"prepare_receipt_sha256":sha(PREP),"engineering_recovery":json.loads(RECOVERY.read_text(encoding="utf-8")) if RECOVERY.exists() else None,
  "outcome_values_opened_at_utc":datetime.now(timezone.utc).isoformat(),"pool":{"counts":receipt["counts"],
   "signal_metrics":pool_stats,"segments":pool_seg,"complete_daily_cohorts_net_0_5pct":pool_cohort,
   "daily_coverage":{"active_days":active_days,"complete_days":int(pd_pool["cohort_status"].eq("COMPLETE").sum()),
    "partial_days":partial,"abstain_days":int(pd_pool["cohort_status"].eq("ABSTAIN").sum())},
   "family_gate":{"signal_metrics_all_positive":sig_ok,"complete_cohort_metrics_all_positive":coh_ok,"decision":decision}},
  "top_n_policies":{},"decision":decision,"parameter_changes_after_freeze":False,
  "2024_2025_2026_outcomes_opened":False,"cost_assumption":"0.5% round trip primary; 0%/1% sensitivities; not measured execution costs."}
 if decision=="KEEP":
  pd_pool_by_date=pd_pool.set_index("date")
  for n in TOP_NS:
   chosen=selected.loc[selected["top_n"].eq(n)].copy()
   j=join_labels(chosen,cal["date"].to_numpy())
   metrics=label_summary(j,costs=(0.0,COST,0.01))
   segments=segment_metrics(j); cm,dc=cohort(chosen,j,active)
   common=dc.loc[dc["cohort_status"].eq("COMPLETE"),["date","cohort_return"]].merge(
    pd_pool.loc[pd_pool["cohort_status"].eq("COMPLETE"),["date","cohort_return"]],
    on="date",suffixes=("_policy","_pool"),validate="one_to_one")
   add=float((common["cohort_return_policy"]-common["cohort_return_pool"]).mean()) if len(common) else None
   nm=metrics["round_trip_cost_scenarios"][f"{COST:g}"]
   tail=all(nm.get(k) is not None and net.get(k) is not None and nm[k]<=net[k] for k in ("minus10_rate","minus20_rate"))
   pass_policy=positive(nm) and positive(cm) and len(common)>=20 and add is not None and add>0 and tail
   result["top_n_policies"][str(n)]={"selected_rows":len(chosen),"metrics":metrics,"segments":segments,
    "complete_daily_cohorts_net_0_5pct":cm,"common_complete_days":len(common),"paired_cohort_mean_value_add":add,
    "signal_gate":positive(nm),"cohort_gate":positive(cm),"tail_risk_not_worse_than_pool":tail,
    "decision":"PASS_RETROSPECTIVE_CONFIRMATION_GATE" if pass_policy else "NO_POLICY_PASSED"}
  passed=[(int(n),v["complete_daily_cohorts_net_0_5pct"].get("mean")) for n,v in result["top_n_policies"].items()
   if v["decision"]=="PASS_RETROSPECTIVE_CONFIRMATION_GATE"]
  result["decision"]="KEEP_TOP"+str(sorted(passed,key=lambda x:(-float(x[1]),x[0]))[0][0]) if passed else "NO_POLICY_PASSED"
 REPORTS.mkdir(parents=True,exist_ok=True)
 REPORT.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
 md=["# Core Trend Compression discovery","",f"- Decision: {result['decision']}",
  "- Evidence: RETROSPECTIVE_PROVISIONAL; historical data was previously exposed.",
  "- Window: 2022-07-01 through final 2023 signal with fifth-session exit within 2023.",
  "- Candidate membership and Top-N were frozen before numeric outcomes were read.",
  "- 2024/2025/2026 outcomes were not opened.",
  "- Evaluation used a documented join-key recovery; the first attempt emitted no metrics.",
  f"- Candidates: {len(joined):,}; resolved {pool_stats['resolved_count']:,}; unresolved {pool_stats['unresolved_count']:,}.",
  f"- Net mean / median / win: {net.get('mean')} / {net.get('median')} / {net.get('win_rate')}.",
  f"- Complete pool cohorts: {pool_cohort['n']}; partial active days: {partial}.",
  f"- Family gate: {decision}."]
 REPORT_MD.write_text("\n".join(md)+"\n",encoding="utf-8")
 return result

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("phase",choices=("prepare","verify-prepare","recover-prepare","evaluate"))
 phase=parser.parse_args().phase
 if phase=="prepare": output=prep()
 elif phase=="verify-prepare": output=prep(verify=True)
 elif phase=="recover-prepare": output=recover_prepare()
 else:
  r=evaluate()
  output={"decision":r["decision"],"candidates":len(pd.read_parquet(POOL)),
   "resolved":r["pool"]["signal_metrics"]["resolved_count"],
   "net_mean":r["pool"]["signal_metrics"]["round_trip_cost_scenarios"][f"{COST:g}"]["mean"],
   "net_median":r["pool"]["signal_metrics"]["round_trip_cost_scenarios"][f"{COST:g}"]["median"],
   "win_rate":r["pool"]["signal_metrics"]["round_trip_cost_scenarios"][f"{COST:g}"]["win_rate"],
   "complete_cohort_days":r["pool"]["daily_coverage"]["complete_days"],
   "partial_days":r["pool"]["daily_coverage"]["partial_days"]}
 print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=="__main__": main()


