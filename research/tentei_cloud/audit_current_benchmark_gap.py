#!/usr/bin/env python3
"""Current-system benchmark gap audit for fixed reconstructed Core.

Research-only. No production writes and no rule changes.

This audit compares:
1) current Stable★6 confirmed 5BD returns parsed from the saved production-style
   validation report; and
2) fixed reconstructed Core over the same confirmed-date window, using both the
   standard signal-session close label and the first executable next-1H-open entry.

It also snapshots headline summaries for Sniper / Mega modes, preserving each
mode's own official horizon/target rather than forcing unlike modes into one score.

Important:
- This is a retrospective benchmark-gap audit, not a clean validation.
- Stable and Core have different signal-generation architectures and entry
  conventions. The comparison is product-level descriptive evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from reconstruct_4h_from_1h import load, aggregate, enrich_session, add_daily_context, cooldown

MODE_REPORTS = {
    "Stable_S6": ("reports/mega_validation_report_stable_s6.html", "5BD", "+10%"),
    "Sniper": ("reports/mega_validation_report_sniper.html", "5BD", "WIN"),
    "Mega5": ("reports/mega_validation_report_mega5_rebound.html", "5BD", "+20%"),
    "Mega40_Deep": ("reports/mega_validation_report_mega40_deep_reversal.html", "40BD", "+30%"),
    "Mega40_Wick": ("reports/mega_validation_report_mega40_wick_recovery.html", "40BD", "+50%"),
}

def parse_pct(s: str):
    s=(s or "").replace("＋","+").replace("−","-").replace("％","%").strip()
    m=re.search(r"([+-]?\d+(?:\.\d+)?)\s*%",s)
    return float(m.group(1))/100.0 if m else np.nan

def clean_text(node):
    return " ".join(node.stripped_strings) if node is not None else ""

def parse_report_summary(path: Path, horizon: str, target: str):
    soup=BeautifulSoup(path.read_text(encoding="utf-8"),"html.parser")
    header=soup.find("header")
    generated=None
    if header:
        for p in header.find_all("p"):
            t=clean_text(p)
            if t.startswith("生成日時:"):
                generated=t.split(":",1)[1].strip()
                break

    summary=soup.find("section",id="summary")
    labels={}
    if summary:
        for metric in summary.select(".metric"):
            label=metric.select_one(".label")
            value=metric.select_one(".value")
            if label and value:
                labels[clean_text(label)]=clean_text(value)

    rows=[]
    confirmed=soup.find("section",id="confirmed")
    if confirmed:
        for tr in confirmed.select("tr[data-confirmed-row]"):
            cells={td.get("data-label"): clean_text(td) for td in tr.find_all("td") if td.get("data-label")}
            date=cells.get("日付")
            symtxt=cells.get("銘柄","")
            sm=re.search(r"\b([0-9A-Z]{4})\b",symtxt)
            metric_text=cells.get("5営業日後" if horizon=="5BD" else "40営業日後","")
            ret=parse_pct(metric_text)
            if date and sm and pd.notna(ret):
                rows.append({
                    "date":date.replace("/","-"),
                    "symbol":sm.group(1),
                    "return":ret,
                })

    return {
        "generated":generated,
        "horizon":horizon,
        "target":target,
        "confirmed_n_headline":int(labels.get("確定件数","0") or 0),
        "confirmed_mean_headline":parse_pct(labels.get("確定平均","")),
        "confirmed_win_headline":parse_pct(labels.get("確定勝率","")),
        "target_hit_headline":int(labels.get("目標Hit","0") or 0),
        "parsed_rows":rows,
    }

def make_core(raw):
    s=aggregate(raw,780)
    s=enrich_session(s)
    s,dates=add_daily_context(s,raw)
    e=s[
        (s["prev_daily_close"]<=1000)
        & (s["prev_daily_volume"]>=10000)
        & (s["volume"]>=5000)
    ].copy()
    g=(
        (e["rsi12"]<45)
        & e["pre_down3"].fillna(False)
        & (e["close"]>e["bb_mid"])
        & (e["atr14_pct"]<0.05)
    )
    q=cooldown(e[g].copy(),dates,5)
    q=q[q["ret5bd"].notna()].copy()
    q["date_dt"]=pd.to_datetime(q["date"],errors="coerce")
    return q

def attach_next_open(core,raw):
    by_symbol={}
    for sym,g in raw.sort_values("timestamp").groupby("symbol",sort=False):
        by_symbol[str(sym)]=g[["timestamp","open"]].reset_index(drop=True)
    vals=[]
    for _,r in core.iterrows():
        g=by_symbol.get(str(r["symbol"]))
        if g is None or g.empty or pd.isna(r["last_ts"]):
            vals.append(np.nan); continue
        needle=pd.Timestamp(r["last_ts"])
        j=int(g["timestamp"].searchsorted(needle,side="right"))
        vals.append(float(g.iloc[j]["open"]) if j<len(g) else np.nan)
    x=core.copy()
    x["next_open"]=vals
    x["ret5bd_next_open"]=x["target_close"]/x["next_open"]-1
    return x

def ret_metrics(r):
    r=pd.Series(r).dropna().astype(float)
    if r.empty: return {"n":0}
    rs=r.sort_values(ascending=False).reset_index(drop=True)
    return {
        "n":int(len(r)),
        "mean":float(r.mean()),
        "median":float(r.median()),
        "win":float((r>0).mean()),
        "ge10":float((r>=0.10).mean()),
        "ge20":float((r>=0.20).mean()),
        "le10":float((r<=-0.10).mean()),
        "max":float(r.max()),
        "min":float(r.min()),
        "top1_removed":float(rs.iloc[1:].mean()) if len(rs)>1 else None,
        "top3_removed":float(rs.iloc[3:].mean()) if len(rs)>3 else None,
        "top5_removed":float(rs.iloc[5:].mean()) if len(rs)>5 else None,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",action="append",required=True)
    ap.add_argument("--repo-root",default=".")
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    root=Path(a.repo_root)
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    snapshots=[]
    parsed={}
    for mode,(rel,horizon,target) in MODE_REPORTS.items():
        info=parse_report_summary(root/rel,horizon,target)
        parsed[mode]=info
        rows=info["parsed_rows"]
        dates=[r["date"] for r in rows]
        snapshots.append({
            "mode":mode,
            "generated":info["generated"],
            "official_horizon":horizon,
            "official_target":target,
            "confirmed_n":info["confirmed_n_headline"],
            "confirmed_mean":info["confirmed_mean_headline"],
            "confirmed_win":info["confirmed_win_headline"],
            "target_hit":info["target_hit_headline"],
            "target_hit_rate":info["target_hit_headline"]/info["confirmed_n_headline"] if info["confirmed_n_headline"] else None,
            "parsed_confirmed_rows":len(rows),
            "min_confirmed_date":min(dates) if dates else None,
            "max_confirmed_date":max(dates) if dates else None,
        })
    pd.DataFrame(snapshots).to_csv(out/"current_mode_benchmark_snapshot.csv",index=False)

    stable=pd.DataFrame(parsed["Stable_S6"]["parsed_rows"])
    if stable.empty:
        raise RuntimeError("no Stable rows parsed")
    stable["date_dt"]=pd.to_datetime(stable["date"])
    stable_start=stable["date_dt"].min()
    stable_end=stable["date_dt"].max()

    raw=load(a.inputs)
    core=attach_next_open(make_core(raw),raw)
    c=core[(core["date_dt"]>=stable_start)&(core["date_dt"]<=stable_end)].copy()

    rows=[]
    rows.append({"system":"Current_Stable_S6","entry":"official_report","window_start":str(stable_start.date()),"window_end":str(stable_end.date()),**ret_metrics(stable["return"])})
    rows.append({"system":"Cloud_Core","entry":"signal_session_close","window_start":str(stable_start.date()),"window_end":str(stable_end.date()),**ret_metrics(c["ret5bd"])})
    rows.append({"system":"Cloud_Core","entry":"first_executable_next_1h_open","window_start":str(stable_start.date()),"window_end":str(stable_end.date()),**ret_metrics(c["ret5bd_next_open"])})
    compare=pd.DataFrame(rows)
    compare.to_csv(out/"stable_vs_core_common_window.csv",index=False)

    # Stable row export for auditability.
    stable.to_csv(out/"stable_s6_parsed_confirmed_rows.csv",index=False)

    meta={
        "stable_report_generated":parsed["Stable_S6"]["generated"],
        "stable_common_window_start":str(stable_start.date()),
        "stable_common_window_end":str(stable_end.date()),
        "stable_headline_n":parsed["Stable_S6"]["confirmed_n_headline"],
        "stable_parsed_rows":int(len(stable)),
        "note":"product-level retrospective comparison; does not imply identical signal universe or entry semantics",
        "production_writes":False,
    }
    (out/"benchmark_gap_meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

    print(json.dumps(meta,ensure_ascii=False,indent=2))
    print("\nMODE SNAPSHOT")
    print(pd.DataFrame(snapshots).to_string(index=False))
    print("\nSTABLE VS CORE COMMON WINDOW")
    print(compare.to_string(index=False))

if __name__=="__main__":
    main()
