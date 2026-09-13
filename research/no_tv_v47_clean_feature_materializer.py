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



def load_events(path: Path) -> pd.DataFrame:
    e=pd.read_csv(path,dtype={"code":str})
    e["code"]=e["code"].map(clean_symbol)
    e["event_date"]=pd.to_datetime(e["event_date"],errors="coerce").dt.strftime("%Y-%m-%d")
    e=e.dropna(subset=["code","event_date","event"])
    return e


def listing_map(events: pd.DataFrame) -> dict[str,list[str]]:
    out={}
    q=events[events["event"]=="listing"].copy()
    for code,g in q.groupby("code",sort=False):
        out[str(code)]=sorted(g["event_date"].astype(str).tolist())
    return out


def identity_epoch_for_date(
    listing_dates: dict[str,list[str]],
    symbol: str,
    date_s: str,
) -> int:
    return sum(1 for dt in listing_dates.get(str(symbol),[]) if dt <= str(date_s))


def add_identity_epoch(
    df: pd.DataFrame,
    listing_dates: dict[str,list[str]],
) -> pd.DataFrame:
    x=df.copy()
    x["identity_epoch"]=[
        identity_epoch_for_date(listing_dates,str(s),str(d))
        for s,d in zip(x["symbol"],x["date"])
    ]
    return x


def load_daily(
    frozen: Path,
    restored: Path,
    listing_dates: dict[str,list[str]],
    split_map: dict[str,list[tuple[str,float]]],
) -> pd.DataFrame:
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
    x["volume_adjusted"]=x["volume"].astype(float)
    x["future_split_factor_daily"]=[
        future_factor(split_map,str(s),str(d))
        for s,d in zip(x["symbol"],x["date"])
    ]
    # Preserve provider-adjusted daily volume here. At each signal timestamp,
    # prior daily volumes are causally rebased to the signal-date share basis
    # by removing only splits that are still in the future at that signal.
    x["volume"]=x["volume_adjusted"]
    x=add_identity_epoch(x,listing_dates)
    x=x.sort_values(["symbol","identity_epoch","date"]).reset_index(drop=True)
    g = x.groupby(["symbol","identity_epoch"], sort=False)
    x["next_open"] = g["open"].shift(-1)
    x["d5_close"] = g["close"].shift(-5)
    x["exit_date_5bd"] = g["date"].shift(-5)
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
    listing_dates: dict[str,list[str]],
) -> pd.DataFrame:
    if not nocap_dates or daily.empty or raw.empty:
        return pd.DataFrame()
    sessions=base.synthetic_sessions(raw).reset_index(drop=True)
    if sessions.empty:
        return pd.DataFrame()
    sessions["identity_epoch"]=[
        identity_epoch_for_date(listing_dates,symbol,str(dt))
        for dt in sessions["date"].astype(str)
    ]
    rows=[]
    for epoch,sessions_epoch in sessions.groupby("identity_epoch",sort=True):
        s=sessions_epoch.reset_index(drop=True)
        d=daily[daily["identity_epoch"]==int(epoch)].copy()
        if d.empty or s.empty:
            continue
        daymap=d.set_index("date")
        for i,row in s.iterrows():
            dt=str(row.date)
            if dt not in nocap_dates or dt not in daymap.index:
                continue
            if float(row.volume) < 5000:
                continue

            factor=future_factor(split_map,symbol,dt)

            # Daily provider volume is on anchor/present share basis. Remove
            # splits that are still future as of this signal date; splits that
            # already happened remain, so past daily volumes are on the current
            # signal-date share basis and comparable to raw current-session volume.
            d_asof=d.copy()
            d_asof["volume"]=d_asof["volume_adjusted"].astype(float)/factor
            asof=v13.build_asof_official(d_asof,s,i)
            if asof is None:
                continue
            tf=base.technical_features(asof)
            if tf is None:
                continue

            # Raw 1H source volume is stored unchanged. For the ratio only,
            # causally rebase prior sessions to today's share basis. The quotient
            # future_factor(prev)/future_factor(today) contains only splits that
            # occurred between the prior session and today; splits after today
            # cancel and therefore cannot leak future information.
            prev=s.iloc[max(0,i-20):i]
            prev_norm=[]
            for pr in prev.itertuples(index=False):
                pf=future_factor(split_map,symbol,str(pr.date))
                prev_norm.append(float(pr.volume)*pf/factor)
            svr=(
                float(row.volume/np.mean(prev_norm))
                if len(prev_norm)>=5 and np.mean(prev_norm)>0
                else np.nan
            )
            rng=float(row.high-row.low)
            entry_adjusted=float(row.close)
            entry_pit=entry_adjusted*factor

            nx=daymap.loc[dt,"next_open"]
            d5=daymap.loc[dt,"d5_close"]
            exit_date=daymap.loc[dt,"exit_date_5bd"]
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
                "identity_epoch":int(epoch),
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
                "exit_date_5bd":str(exit_date) if pd.notna(exit_date) else "",
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
    ap.add_argument("--membership-events",required=True,type=Path)
    ap.add_argument("--raw-dir",required=True,type=Path)
    ap.add_argument("--raw-coverage-receipt",required=True,type=Path)
    ap.add_argument("--output-dir",required=True,type=Path)
    a=ap.parse_args()

    cov=json.loads(a.raw_coverage_receipt.read_text(encoding="utf-8"))
    if not cov.get("accepted"):
        raise RuntimeError("raw1h coverage not accepted")
    if cov.get("strategy_returns_opened") or cov.get("model_scores_opened"):
        raise RuntimeError("coverage isolation contract violated")

    events=load_events(a.membership_events)
    lmap=listing_map(events)
    split_map=load_split_map(a.all_splits)
    daily=load_daily(a.frozen_daily,a.restored_daily,lmap,split_map)
    nocap_pairs,cap_pairs=load_candidate_sets(a.daily_candidates)

    daily_by_symbol={
        str(sym):g[["date","open","high","low","close","volume","volume_adjusted","future_split_factor_daily","identity_epoch","next_open","d5_close","exit_date_5bd"]]
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
            lmap,
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
    feature_base_cols=[
        "date","session","symbol","identity_epoch","entry_adjusted","entry_pit",
        "future_split_factor","session_volume","exit_date_5bd",
        *feature_cols,
    ]
    dev_cols=[
        *feature_base_cols,
        "canonical_ret_5bd","legacy_ret_5bd",
    ]
    missing=[x for x in dev_cols if x not in nocap.columns]
    if missing:
        raise RuntimeError(f"missing NOCAP columns {missing}")

    out=a.output_dir
    out.mkdir(parents=True,exist_ok=True)

    def write_arm(name: str, x: pd.DataFrame):
        dates=pd.to_datetime(x["date"])
        dev=x[dates <= pd.Timestamp("2025-06-30")].copy()
        h2=x[dates >= pd.Timestamp("2025-07-01")].copy()
        dev[dev_cols].to_parquet(
            out/f"v47_{name}_dev_features.parquet",index=False
        )
        # Locked validation artifact deliberately omits both return targets.
        h2[feature_base_cols].to_parquet(
            out/f"v47_{name}_validation_blind.parquet",index=False
        )
        return dev,h2

    nocap_dev,nocap_h2=write_arm("nocap",nocap)
    cap_dev,cap_h2=write_arm("cap1000",cap)

    def stats(dev,h2):
        return {
            "dev_rows":int(len(dev)),
            "dev_symbols":int(dev["symbol"].nunique()) if len(dev) else 0,
            "dev_dates":int(dev["date"].nunique()) if len(dev) else 0,
            "dev_rows_with_canonical_label":int(dev["canonical_ret_5bd"].notna().sum()) if len(dev) else 0,
            "validation_blind_rows":int(len(h2)),
            "validation_blind_symbols":int(h2["symbol"].nunique()) if len(h2) else 0,
            "validation_blind_dates":int(h2["date"].nunique()) if len(h2) else 0,
        }

    report={
        "scope":"clean PIT V47 feature materialization after raw coverage acceptance",
        "NOCAP":stats(nocap_dev,nocap_h2),
        "CAP1000_PIT":stats(cap_dev,cap_h2),
        "cap_is_subset_at_daily_policy_level":True,
        "feature_columns":feature_cols,
        "absolute_price_semantics":"log_price uses point-in-time nominal entry_pit",
        "relative_technical_semantics":"split-normalized Yahoo price path; daily volume ratios causally rebase provider daily volume to each signal-date share basis",
        "raw_1h_volume_semantics":"raw Yahoo 1H volume stored unchanged; session gate uses raw current shares; session_vol_ratio20 causally rebases only prior sessions to current signal-date share basis",
        "target_columns_materialized_in_development_only":[
            "canonical_ret_5bd",
            "legacy_ret_5bd",
        ],
        "locked_validation_target_columns_emitted":False,
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
