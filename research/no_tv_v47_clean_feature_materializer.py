from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import no_tv_v10_standalone as base
import no_tv_v11_independent_selector as v11
import no_tv_v13_official_daily as v13

WINDOW_START = "2024-10-01"
WINDOW_END = "2025-12-30"


def clean_symbol(x: object) -> str:
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def load_daily(frozen: Path, restored: Path) -> pd.DataFrame:
    cols = ["date","open","high","low","close","volume","symbol"]
    d = pd.read_csv(frozen, usecols=cols, dtype={"symbol":str}, low_memory=False)
    r = pd.read_csv(restored, usecols=cols, dtype={"symbol":str}, low_memory=False)
    x = pd.concat([d,r], ignore_index=True, sort=False)
    x["symbol"] = x["symbol"].map(clean_symbol)
    x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for c in ["open","high","low","close","volume"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x = (
        x.dropna(subset=["date","symbol","close","volume"])
        .sort_values(["symbol","date"])
        .drop_duplicates(["symbol","date"], keep="last")
        .reset_index(drop=True)
    )
    g = x.groupby("symbol", sort=False)
    x["next_open"] = g["open"].shift(-1)
    x["d5_close"] = g["close"].shift(-5)
    return x


def load_split_map(path: Path) -> dict[str,list[tuple[str,float]]]:
    s = pd.read_csv(path,dtype={"symbol":str})
    s["symbol"] = s["symbol"].map(clean_symbol)
    s["event_date"] = pd.to_datetime(s["event_date"]).dt.strftime("%Y-%m-%d")
    s["split_ratio"] = pd.to_numeric(s["split_ratio"], errors="coerce")
    out={}
    for sym,g in s.groupby("symbol",sort=False):
        out[str(sym)] = [
            (str(r.event_date),float(r.split_ratio))
            for r in g.sort_values("event_date").itertuples(index=False)
        ]
    return out


def future_factor(split_map, symbol: str, date_s: str) -> float:
    f=1.0
    for event_date,ratio in split_map.get(symbol,[]):
        if event_date > date_s:
            f *= ratio
    return float(f)


def load_candidate_sets(path: Path) -> tuple[set[tuple[str,str]],set[tuple[str,str]]]:
    d = pd.read_csv(
        path,
        usecols=[
            "date_s","symbol",
            "eligible_nocap_daily","eligible_cap1000_daily",
        ],
        dtype={"date_s":str,"symbol":str},
        low_memory=False,
    )
    d["symbol"]=d["symbol"].map(clean_symbol)
    nocap=set(
        zip(
            d.loc[d["eligible_nocap_daily"].astype(bool),"symbol"],
            d.loc[d["eligible_nocap_daily"].astype(bool),"date_s"],
        )
    )
    cap=set(
        zip(
            d.loc[d["eligible_cap1000_daily"].astype(bool),"symbol"],
            d.loc[d["eligible_cap1000_daily"].astype(bool),"date_s"],
        )
    )
    if not cap.issubset(nocap):
        raise RuntimeError("CAP1000 daily set is not subset of NOCAP")
    return nocap,cap


def read_raw_symbol_groups(raw_dir: Path):
    files=sorted(raw_dir.glob("**/v47_raw1h_shard_*.csv.gz"))
    if not files:
        raise RuntimeError("no raw1h shards")
    for p in files:
        d=pd.read_csv(p,dtype={"symbol":str,"date":str},low_memory=False)
        d["symbol"]=d["symbol"].map(clean_symbol)
        d["ts"]=pd.to_datetime(d["ts_jst"],utc=True).dt.tz_convert("Asia/Tokyo")
        for sym,g in d.groupby("symbol",sort=False):
            yield str(sym),g[["ts","date","open","high","low","close","volume"]].copy()


def build_symbol_rows(
    symbol: str,
    raw: pd.DataFrame,
    daily: pd.DataFrame,
    nocap_dates: set[str],
    split_map: dict[str,list[tuple[str,float]]],
) -> pd.DataFrame:
    if not nocap_dates or daily.empty or raw.empty:
        return pd.DataFrame()
    sessions=base.synthetic_sessions(raw).reset_index(drop=True)
    if sessions.empty:
        return pd.DataFrame()
    svolume=sessions["volume"].to_numpy(float)
    daymap=daily.set_index("date")
    rows=[]
    for i,row in sessions.iterrows():
        dt=str(row.date)
        if dt not in nocap_dates or dt not in daymap.index:
            continue
        if float(row.volume) < 5000:
            continue
        asof=v13.build_asof_official(daily,sessions,i)
        if asof is None:
            continue
        tf=base.technical_features(asof)
        if tf is None:
            continue
        prev20=svolume[max(0,i-20):i]
        svr=(
            float(row.volume/np.mean(prev20))
            if len(prev20)>=5 and np.mean(prev20)>0
            else np.nan
        )
        rng=float(row.high-row.low)
        factor=future_factor(split_map,symbol,dt)
        entry_adjusted=float(row.close)
        entry_pit=entry_adjusted*factor

        nx=daymap.loc[dt,"next_open"]
        d5=daymap.loc[dt,"d5_close"]
        canonical=(
            float(d5/nx-1)
            if pd.notna(nx) and pd.notna(d5) and float(nx)>0
            else np.nan
        )
        legacy=(
            float(d5/entry_adjusted-1)
            if pd.notna(d5) and entry_adjusted>0
            else np.nan
        )
        rec={
            "date":dt,
            "session":int(row.session),
            "symbol":symbol,
            "entry_adjusted":entry_adjusted,
            "entry_pit":entry_pit,
            "future_split_factor":factor,
            "session_volume":float(row.volume),
            "session13":int(row.session==13),
            "log_price":float(np.log(max(entry_pit,1e-9))),
            "session_ret":float(row.close/row.open-1) if row.open else np.nan,
            "session_range_pct":float(rng/row.open) if row.open else np.nan,
            "session_body_pct":float((row.close-row.open)/row.open) if row.open else np.nan,
            "session_close_loc":float((row.close-row.low)/rng) if rng>0 else .5,
            "session_vol_ratio20":svr,
            "canonical_ret_5bd":canonical,
            "legacy_ret_5bd":legacy,
            **tf,
        }
        rows.append(rec)
    return pd.DataFrame(rows)


def enrich_arm(base_rows: pd.DataFrame, eligible_pairs: set[tuple[str,str]]) -> pd.DataFrame:
    if base_rows.empty:
        return base_rows
    mask=[
        (str(s),str(d)) in eligible_pairs
        for s,d in zip(base_rows["symbol"],base_rows["date"])
    ]
    x=base_rows.loc[mask].copy()
    if x.empty:
        return x
    x=v11.enrich_cross_sectional(x)
    return x


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--frozen-daily",required=True,type=Path)
    ap.add_argument("--restored-daily",required=True,type=Path)
    ap.add_argument("--all-splits",required=True,type=Path)
    ap.add_argument("--daily-candidates",required=True,type=Path)
    ap.add_argument("--raw-dir",required=True,type=Path)
    ap.add_argument("--raw-coverage-receipt",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    cov=json.loads(a.raw_coverage_receipt.read_text(encoding="utf-8"))
    if not cov.get("accepted"):
        raise RuntimeError("raw1h coverage not accepted")
    if cov.get("strategy_returns_opened") or cov.get("model_scores_opened"):
        raise RuntimeError("coverage isolation contract violated")

    daily=load_daily(a.frozen_daily,a.restored_daily)
    split_map=load_split_map(a.all_splits)
    nocap_pairs,cap_pairs=load_candidate_sets(a.daily_candidates)

    daily_by_symbol={
        str(sym):g[["date","open","high","low","close","volume","next_open","d5_close"]]
        .sort_values("date")
        .reset_index(drop=True)
        for sym,g in daily.groupby("symbol",sort=False)
    }
    nocap_dates_by_symbol={}
    for sym,dt in nocap_pairs:
        nocap_dates_by_symbol.setdefault(sym,set()).add(dt)

    frames=[]
    raw_symbols=set()
    for n,(sym,raw) in enumerate(read_raw_symbol_groups(a.raw_dir),1):
        raw_symbols.add(sym)
        fr=build_symbol_rows(
            sym,
            raw,
            daily_by_symbol.get(sym,pd.DataFrame()),
            nocap_dates_by_symbol.get(sym,set()),
            split_map,
        )
        if not fr.empty:
            frames.append(fr)
        if n%250==0:
            print(f"features symbols={n} frames={len(frames)}",flush=True)

    if not frames:
        raise RuntimeError("no clean base candidate rows")
    base_rows=pd.concat(frames,ignore_index=True)

    nocap=enrich_arm(base_rows,nocap_pairs)
    cap=enrich_arm(base_rows,cap_pairs)

    feature_cols=v11.features()
    mandatory=[
        "date","session","symbol","entry_adjusted","entry_pit",
        "future_split_factor","session_volume",
        "canonical_ret_5bd","legacy_ret_5bd",
        *feature_cols,
    ]
    missing=[x for x in mandatory if x not in nocap.columns]
    if missing:
        raise RuntimeError(f"missing NOCAP columns {missing}")

    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)
    nocap[mandatory].to_parquet(out/"v47_nocap_features.parquet",index=False)
    cap[mandatory].to_parquet(out/"v47_cap1000_features.parquet",index=False)

    def stats(x):
        return {
            "rows":int(len(x)),
            "symbols":int(x["symbol"].nunique()) if len(x) else 0,
            "dates":int(x["date"].nunique()) if len(x) else 0,
            "date_sessions":int(x.groupby(["date","session"]).ngroups) if len(x) else 0,
            "rows_with_canonical_label":int(x["canonical_ret_5bd"].notna().sum()) if len(x) else 0,
        }

    report={
        "scope":"clean PIT V47 feature materialization after raw coverage acceptance",
        "NOCAP":stats(nocap),
        "CAP1000_PIT":stats(cap),
        "cap_is_subset_at_daily_policy_level":True,
        "feature_columns":feature_cols,
        "absolute_price_semantics":"log_price uses point-in-time nominal entry_pit",
        "relative_technical_semantics":"split-normalized Yahoo price path",
        "target_columns_materialized":[
            "canonical_ret_5bd",
            "legacy_ret_5bd",
        ],
        "strategy_selection_performed":False,
        "model_fit_performed":False,
        "2026_rows_included":False,
        "production_writes":False,
    }
    (out/"v47_clean_feature_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
