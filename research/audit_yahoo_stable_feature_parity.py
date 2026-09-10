from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base

BITS = {
    "ema25": "stable_ema25",
    "macdpos": "stable_macdpos",
    "stoch75": "stable_stoch75",
    "bb80": "stable_bb80",
    "pre_down3": "stable_pre_down3",
    "gap_up": "stable_gap_up",
}


def to_bool(s):
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(["true", "1", "yes"])


def load_teacher(path, start, end):
    t = pd.read_csv(path, dtype={"symbol": str})
    t["date_norm"] = pd.to_datetime(t.date, errors="coerce").dt.strftime("%Y-%m-%d")
    rec = pd.to_datetime(t.received_at, errors="coerce")
    t["session"] = np.where(rec.dt.hour < 14, 9, 13)
    t["symbol"] = t.symbol.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    t = t[t.date_norm.between(start, end)].copy()
    for c in BITS:
        t[c] = to_bool(t[c])
    t["teacher_score_calc"] = sum(t[c].astype(int) for c in BITS)
    t["teacher_stable6_calc"] = t.teacher_score_calc == 6
    t["key"] = t.symbol + "|" + t.date_norm + "|" + t.session.astype(str)
    return t.sort_values("received_at").drop_duplicates("key", keep="last")


def bit_metrics(m, teacher_col, yahoo_col):
    a = m[teacher_col].astype(bool).to_numpy(); b = m[yahoo_col].astype(bool).to_numpy()
    tp = int(np.sum(a & b)); tn = int(np.sum(~a & ~b)); fp = int(np.sum(~a & b)); fn = int(np.sum(a & ~b))
    return {
        "n": int(len(a)), "accuracy": float(np.mean(a == b)), "teacher_true": int(a.sum()), "yahoo_true": int(b.sum()),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "true_recall": float(tp / max(1, tp + fn)), "true_precision": float(tp / max(1, tp + fp)),
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--teacher", required=True); ap.add_argument("--start", default="2026-07-01"); ap.add_argument("--end", default="2026-08-31")
    ap.add_argument("--max-symbols", type=int, default=200); ap.add_argument("--max-workers", type=int, default=20); ap.add_argument("--output-dir", default="research_artifacts/stable_feature_parity")
    a = ap.parse_args(); t = load_teacher(a.teacher, a.start, a.end)
    stable_syms = set(t.loc[t.teacher_stable6_calc, "symbol"])
    freq = t.groupby("symbol").size().sort_values(ascending=False)
    ordered = list(stable_syms) + [s for s in freq.index if s not in stable_syms]
    codes = ordered[:a.max_symbols]
    t = t[t.symbol.isin(codes)].copy()

    frames=[]; errors={}
    with ThreadPoolExecutor(max_workers=a.max_workers) as ex:
        fut={ex.submit(base.fetch_one,c,a.start,a.end):c for c in codes}
        for i,f in enumerate(as_completed(fut),1):
            try: fr,err=f.result()
            except Exception as e: fr,err=None,type(e).__name__
            if fr is not None and not fr.empty: frames.append(fr)
            elif err: errors[err]=errors.get(err,0)+1
            if i%50==0: print(f"progress {i}/{len(codes)}",flush=True)
    if not frames: raise RuntimeError("no Yahoo candidate rows")
    y=pd.concat(frames,ignore_index=True); y["key"]=y.symbol.astype(str)+"|"+y.date.astype(str)+"|"+y.session.astype(int).astype(str)
    keep=["key","stable_score","stoch14","bb_pct"]+list(BITS.values())
    m=t.merge(y[keep],on="key",how="left",indicator=True)
    matched=m[m._merge=="both"].copy()
    result={"teacher_rows":int(len(t)),"teacher_stable6":int(t.teacher_stable6_calc.sum()),"symbols":len(codes),"matched":int(len(matched)),"unmatched":int((m._merge!="both").sum()),"errors":errors,"bits":{}}
    for tc,yc in BITS.items(): result["bits"][tc]=bit_metrics(matched,tc,yc)
    if len(matched):
        result["score_exact"] = float(np.mean(matched.teacher_score_calc.to_numpy(int)==matched.stable_score.to_numpy(int)))
        result["score_mae"] = float(np.mean(np.abs(matched.teacher_score_calc.to_numpy(int)-matched.stable_score.to_numpy(int))))
        teacher_s6=matched.teacher_stable6_calc.to_numpy(bool); yahoo_s6=matched.stable_score.to_numpy(int)==6
        result["stable6"]={"teacher":int(teacher_s6.sum()),"yahoo":int(yahoo_s6.sum()),"overlap":int(np.sum(teacher_s6&yahoo_s6)),"recall":float(np.sum(teacher_s6&yahoo_s6)/max(1,teacher_s6.sum()))}
        ss=pd.to_numeric(matched._stoch,errors="coerce"); bb=pd.to_numeric(matched._bbpct,errors="coerce")
        result["numeric"]={
          "stoch_mae":float(np.nanmean(np.abs(ss-matched.stoch14))),"stoch_corr":float(np.corrcoef(ss.fillna(ss.median()),matched.stoch14.fillna(matched.stoch14.median()))[0,1]),
          "bbpct_mae":float(np.nanmean(np.abs(bb-matched.bb_pct))),"bbpct_corr":float(np.corrcoef(bb.fillna(bb.median()),matched.bb_pct.fillna(matched.bb_pct.median()))[0,1]),
        }
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/"stable_feature_parity.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
