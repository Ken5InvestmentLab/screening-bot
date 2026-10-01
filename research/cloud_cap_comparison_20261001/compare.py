"""Reproducible offline Cloud cap ablation. No notifications or runtime state IO."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "frozen"))
sys.path.insert(0, str(ROOT))
import run as base
import v7_full_tail_research as v7
import select_shadow_candidates as shadow
from weak_early_beta.bank_calendar import add_bank_business_days
from weak_early_beta.entry_feasibility import performance_eligible
from weak_early_beta.restrictions import restricted_mask
from weak_early_beta.trade_basis import PRICE_BASIS_VERSION, UnsupportedFractionalShares, build_trade_economics
from weak_early_beta.metrics import required_capital

CAPS = (1000, 1500, 2000, 3000, 5000, 0)
DEFAULT_OUT = ROOT / ".cache/cloud_cap_corrected_v2_20261001"
SELECTED_COLUMNS = ["date", "symbol", "model_period", "med_ret5", "med_ret1", "ret10", "volr20", "body_pct", "rank_volr20", "rank_body_pct", "mean_rank", "tail_cdf", "tail_p", "selector", "candidate_id"]
META_COLUMNS = ["symbol", "date", "target_end_date", "target5_no", "actual_close", "actual_volume", "source_usable", "med_ret5", "med_ret1", "ret10", "volr20", "body_pct"]
PRICE_COLUMNS = ["symbol", "date", "open", "close", "actual_open", "actual_close", "split_factor", "source_usable"]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def save_json(path: Path, value) -> None:
    def clean(item):
        if isinstance(item, dict):
            return {key:clean(value) for key,value in item.items()}
        if isinstance(item, (tuple,list)):
            return [clean(value) for value in item]
        if isinstance(item, (float,np.floating)) and not np.isfinite(item):
            return 'NaN' if np.isnan(item) else str(item)
        return item
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def output_lock(path: Path):
    """OS lock is released on process exit; stale text cannot block a restart."""
    import msvcrt
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    if path.stat().st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise RuntimeError(f'output is already active: {path}') from exc
    try:
        yield
    finally:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


def component_hashes() -> dict[str,str]:
    paths = [*sorted((HERE/'frozen').glob('*.py')), Path(__file__),
        *[ROOT/'weak_early_beta'/name for name in ('bank_calendar.py','trade_basis.py','metrics.py','entry_feasibility.py','restrictions.py')],
        ROOT/'weak_early_beta/state/entry_feasibility_exclusions.csv',
        ROOT/'weak_early_beta/state/jpx_restricted_symbols_latest.json']
    return {str(p.relative_to(ROOT)):sha256(p) for p in paths}


def verify_frozen(info: dict) -> None:
    if info['source_hashes'] != component_hashes():
        raise RuntimeError('a frozen runner/component changed; restore it or use a new output directory')


def prepare(daily: Path, output: Path, start: str, end: str, quote_cutoff: str, actions_path: Path | None = None) -> None:
    """Prepare immutable shared features once, with bad quotes masked, dates kept."""
    output.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(daily)
    actions_path = actions_path or daily.parent / 'actions.csv'
    if not actions_path.exists():
        raise ValueError('split action journal is required')
    if (output / "prepared.json").exists():
        old = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
        if (old["source_sha256"], old["start"], old["end"], old["quote_cutoff"]) != (source_hash, start, end, quote_cutoff):
            raise RuntimeError("prepared source or period changed; use a new output directory")
        if old['actions_sha256'] != sha256(actions_path):
            raise RuntimeError('prepared action journal changed')
        verify_frozen(old)
        return
    began = time.time()
    raw = pd.read_csv(daily, parse_dates=["date"], dtype={"symbol": str}, low_memory=False)
    required = {*PRICE_COLUMNS, "high", "low", "volume", "actual_volume", "basis_asof"}
    if not required.issubset(raw.columns):
        raise ValueError(f"normalized source missing columns: {sorted(required-set(raw.columns))}")
    if raw.source_usable.dtype != bool:
        lookup = {"True": True, "False": False, "true": True, "false": False}
        usable = raw.source_usable.astype(str).map(lookup)
        if usable.isna().any():
            raise ValueError("invalid source_usable value")
        raw["source_usable"] = usable.astype(bool)
    source_rows = len(raw)
    source_basis = sorted(raw.basis_asof.astype(str).unique().tolist())
    raw = raw[raw.date.le(pd.Timestamp(quote_cutoff))].sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    if raw.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate symbol/session")
    bad = ~raw.source_usable
    excluded_columns=[c for c in ['symbol','date','source_issue','open','high','low','close','volume'] if c in raw]
    raw.loc[bad,excluded_columns].to_csv(output/'source_quality_excluded_quotes.csv',index=False,date_format='%Y-%m-%d')
    prices = raw[PRICE_COLUMNS].copy()
    prices.loc[bad, ["open", "close", "actual_open", "actual_close"]] = np.nan
    prices.to_pickle(output / "prices.pkl")
    # Do not drop a bad row: rolling lookbacks and symbol-shift(-5) teacher timing
    # must retain the original session slot. Relative features keep adjusted units.
    raw.loc[bad, ["open", "high", "low", "close", "volume"]] = np.nan
    keep = list(dict.fromkeys(base.FEATURES + META_COLUMNS))
    symbols = sorted(raw.symbol.unique())
    parts = []
    for at in range(0, len(symbols), 400):
        z = base.build_features(raw[raw.symbol.isin(symbols[at:at+400])])
        parts.append(z[keep])
        print(f"feature symbols {min(at+400,len(symbols))}/{len(symbols)}", flush=True)
    f = pd.concat(parts, ignore_index=True)
    del parts
    gc.collect()
    groups = f.groupby("date")
    breadth = pd.DataFrame({
        "breadth_ret1_pos": groups.ret1.apply(lambda s: s.dropna().gt(0).mean()),
        "med_ret1": groups.ret1.median(),
        "med_ret5": groups.ret5.median(),
        "breadth_ma20": groups.ma20_gap.apply(lambda s: s.dropna().gt(0).mean()),
    })
    for column in breadth:
        f[column] = f.date.map(breadth[column])
    f = f.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    f["previous_actual_close"] = f.groupby("symbol").actual_close.shift(1)
    f["previous_actual_volume"] = f.groupby("symbol").actual_volume.shift(1)
    f["previous_source_usable"] = f.groupby("symbol").source_usable.shift(1).eq(True)
    f["feature_complete"] = f[base.FEATURES].notna().all(axis=1)
    np.save(output / "features.npy", f[base.FEATURES].to_numpy(dtype=np.float32))
    f[[*META_COLUMNS, "previous_actual_close", "previous_actual_volume", "previous_source_usable", "feature_complete"]].to_pickle(output / "rows.pkl")
    # Every invariant feature uses a constant unit multiplier within a historical
    # signal lookback. Explicitly test the only absolute feature, price*volume.
    check = raw[raw.source_usable & raw.volume.notna() & raw.actual_volume.notna()]
    invariant_error = float(np.max(np.abs(np.log1p(check.close*check.volume)-np.log1p(check.actual_close*check.actual_volume))))
    if invariant_error > 1e-10:
        raise RuntimeError(f"log_dv basis is not invariant: {invariant_error}")
    import xgboost
    metadata = {
        "identity": "CLOUD_CAP_CORRECTED_COMPARISON_V2", "source_path": str(daily),
        "source_sha256": source_hash, "source_basis_asof": source_basis,
        "actions_sha256":sha256(actions_path),
        "source_rows": source_rows, "used_quote_rows": len(raw), "symbols": len(symbols),
        "quote_start": str(raw.date.min().date()), "quote_cutoff": quote_cutoff,
        "start": start, "end": end, "caps": CAPS, "tail_gate": .999,
        "unusable_quote_rows": int(bad.sum()), "feature_count": len(base.FEATURES),
        "complete_feature_rows": int(f.feature_complete.sum()),
        "log_dv_basis_invariance_max_abs_error": invariant_error,
        "source_hashes": component_hashes(),
        "versions": {"python":sys.version,"pandas":pd.__version__,"numpy":np.__version__,"xgboost":xgboost.__version__},
        "model_parameters":v7.model(pd.Series([0,1])).get_params(),
        "contract": {
            "market_breadth":"ret1 and ma20_gap positive fractions use non-NaN rows only. Median features retain pandas non-NaN median. V1 partial fits are separate and not reused.",
            "absolute_gates":"previous actual close<=cap (0 removes cap), previous actual volume>=10000, actual volume>=5000, actual close>=20, current and previous source_usable and 45 complete features",
            "learning":"Frozen V7 seed42/160trees/4threads; monthly target_end_date < month_start. Daily top0.25% teacher reranked in each cap's eligible population; existing symbol shift(-5) target kept.",
            "selection":"Frozen five shadow selectors, no cooldown or retuning; ambiguous winner causes common-day exclusion across ALL SIX arms/all five modes, training unchanged.",
            "endpoint":"Entry signal+1 official bank-business session open; exit signal+5 official bank-business session close. Missing or bad endpoint remains unmeasured; it never moves to a later available quote.",
            "cash":"100 actual shares at entry; build_trade_economics verifies integral quantity after EVERY holding action, excludes unmodeled cash-in-lieu. CashPL uses actual prices; cost0, no fill proof.",
            "limitations":"Historical research on the current JPX surviving universe; provider action completeness is not independently certified. Relative source adjustment is assumed after quality checks. Post-hoc cap comparison does not prove live edge. Original published sealed ledger is not rewritten.",
        },
        "prepare_seconds": round(time.time()-began,2),
    }
    save_json(output / "prepared.json", metadata)
    save_json(output / "restriction_snapshot.json", json.loads((ROOT/"weak_early_beta/state/jpx_restricted_symbols_latest.json").read_text(encoding="utf-8")))
    (output/'actions.csv').write_bytes(actions_path.read_bytes())
    print(json.dumps({"phase":"prepared","rows":len(f),"seconds":metadata['prepare_seconds']}),flush=True)


def select_safe(tail: pd.DataFrame, output: Path, cap: int, month: pd.Period) -> pd.DataFrame:
    parts = []
    for day, rows in tail.groupby("date", sort=True):
        try:
            parts.append(shadow.select_candidates(rows))
        except RuntimeError as exc:
            if "unresolved winning tie" not in str(exc):
                raise
            item = {"date": str(day.date()), "cap": cap, "month": str(month), "reason": str(exc)}
            save_json(output / f"tie_cap{cap}_{day:%Y-%m-%d}.json", item)
            rows[shadow.USECOLS].to_csv(output / f"tie_candidates_cap{cap}_{day:%Y-%m-%d}.csv", index=False, float_format="%.17g")
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=SELECTED_COLUMNS)


def worker_unlocked(output_value: str, caps: tuple[int,...]) -> None:
    output = Path(output_value)
    info = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
    verify_frozen(info)
    f = pd.read_pickle(output / "rows.pkl")
    x = np.load(output / "features.npy", mmap_mode="r")
    common = f.source_usable & f.previous_source_usable & f.feature_complete & f.previous_actual_volume.ge(10000) & f.actual_volume.ge(5000) & f.actual_close.ge(20)
    months = pd.period_range(pd.Timestamp(info['start']).to_period('M'),pd.Timestamp(info['end']).to_period('M'),freq='M')
    populations={}
    for cap in caps:
        eligible = common & (f.previous_actual_close.le(cap) if cap>0 else True)
        labels = f.loc[eligible & f.target5_no.notna() & f.target_end_date.notna(), ['date','target5_no']]
        yall = (labels.groupby('date').target5_no.rank(pct=True,method='average')>=.9975).astype(np.int8)
        populations[cap]=(eligible,yall)
    del labels
    for month in months:
        for cap in caps:
            if (output/'STOP_REQUESTED.json').exists():
                print(json.dumps({'phase':'checkpoint_stopped','caps':caps,'next_month':str(month),'next_cap':cap}),flush=True)
                return
            eligible,yall=populations[cap]
            progress_path = output / f"progress_cap{cap}.json"
            progress = json.loads(progress_path.read_text(encoding='utf-8')) if progress_path.exists() else []
            selected_path = output / f"selected_cap{cap}_{month}.csv"
            receipt_path = output / f"receipt_cap{cap}_{month}.json"
            if selected_path.exists():
                if receipt_path.exists():
                    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
                    if receipt['selected_sha256'] != sha256(selected_path) or receipt['source_hashes'] != info['source_hashes']:
                        raise RuntimeError(f'changed completed checkpoint: {selected_path}')
                    continue
            began=time.time()
            train_index=yall.index[f.loc[yall.index,'target_end_date'].lt(month.start_time)]
            pred_index=f.index[eligible & f.date.between(month.start_time,month.end_time.normalize()) & f.date.between(pd.Timestamp(info['start']),pd.Timestamp(info['end']))]
            if len(train_index)<30000 or not len(pred_index):
                raise RuntimeError(f"invalid causal month cap{cap}/{month}: train={len(train_index)} pred={len(pred_index)}")
            y=yall.loc[train_index].to_numpy(dtype=np.int32)
            model=v7.model(pd.Series(y))
            train_x=np.asarray(x[train_index],dtype=np.float32)
            pred_x=np.asarray(x[pred_index],dtype=np.float32)
            model.fit(train_x,y,verbose=False)
            reference=model.predict_proba(train_x)[:,1]
            predicted=model.predict_proba(pred_x)[:,1]
            cdf=v7.cdf(reference,predicted)
            tail=f.loc[pred_index[cdf>=.999], [col for col in shadow.USECOLS if col in f]].copy()
            tail['model_period']=str(month)
            tail['tail_p']=predicted[cdf>=.999]
            tail['tail_cdf']=cdf[cdf>=.999]
            selected=select_safe(tail,output,cap,month)
            temporary=selected_path.with_suffix('.csv.tmp')
            selected.to_csv(temporary,index=False,date_format='%Y-%m-%d',float_format='%.17g')
            temporary.replace(selected_path)
            item={'cap':cap,'month':str(month),'train_rows':len(train_index),'prediction_rows':len(pred_index),'tail_rows':len(tail),'selected_rows':len(selected),'seconds':round(time.time()-began,2)}
            save_json(receipt_path,{**item,'selected_sha256':sha256(selected_path),'source_hashes':info['source_hashes']})
            progress=[row for row in progress if row['month']!=str(month)]
            progress.append(item)
            save_json(progress_path,progress)
            print(json.dumps(progress[-1]),flush=True)
            del model,train_x,pred_x,reference,predicted,cdf,tail,selected
            gc.collect()


def worker(output_value: str, caps: tuple[int,...]) -> None:
    output=Path(output_value)
    # Lock each arm, including overlapping standalone worker invocations.
    from contextlib import ExitStack
    with ExitStack() as stack:
        for cap in sorted(caps):
            stack.enter_context(output_lock(output/f'cap{cap}.lock'))
        worker_unlocked(output_value,caps)


def trades(selected: pd.DataFrame, prices: pd.DataFrame, actions: pd.DataFrame, info: dict) -> pd.DataFrame:
    result=selected.copy()
    if result.empty:
        return result.assign(entry_date=pd.NaT,gross_return=np.nan,one_hundred_shares_pl_yen=np.nan)
    dates=result.date.drop_duplicates()
    entry_dates={d:pd.Timestamp(add_bank_business_days(d.date(),1)) for d in dates}
    exit_dates={d:pd.Timestamp(add_bank_business_days(d.date(),5)) for d in dates}
    result['entry_date']=result.date.map(entry_dates)
    result['exit_date']=result.date.map(exit_dates)
    entry=prices[['symbol','date','open','actual_open','split_factor']].rename(columns={'date':'entry_date','open':'entry_open_adjusted','actual_open':'entry_open','split_factor':'entry_split_factor'})
    exit=prices[['symbol','date','close','actual_close','split_factor']].rename(columns={'date':'exit_date','close':'exit_close_adjusted','actual_close':'exit_close','split_factor':'exit_split_factor'})
    result=result.merge(entry,on=['symbol','entry_date'],how='left',validate='many_to_one').merge(exit,on=['symbol','exit_date'],how='left',validate='many_to_one')
    snapshots=[]
    for row in result.to_dict('records'):
        try:
            values=build_trade_economics(row['entry_date'],row['exit_date'],row['entry_open'],row['exit_close'],actions,symbol=row['symbol'],basis_date=max(info['source_basis_asof']),source_sha256=info['source_sha256'])
            values['unmodeled_economics_reason']=''
        except UnsupportedFractionalShares as exc:
            values={'entry_shares':100.0,'exit_shares':np.nan,'gross_return':np.nan,'one_hundred_shares_pl_yen':np.nan,'price_basis':PRICE_BASIS_VERSION,'status':'unmodeled_fractional_shares','unmodeled_economics_reason':str(exc)}
        snapshots.append(values)
    economic=pd.DataFrame(snapshots,index=result.index)
    for column in economic:
        result[column]=economic[column]
    measured=result.gross_return.notna()
    np.testing.assert_allclose(result.loc[measured,'gross_return'],result.loc[measured,'exit_close_adjusted']/result.loc[measured,'entry_open_adjusted']-1,rtol=1e-10,atol=1e-10)
    result['price_basis']=PRICE_BASIS_VERSION
    result['signal_date']=result.date
    result['fifth_xtks_exit_date']=result.exit_date
    result['fifth_xtks_exit_close']=result.exit_close
    return result


def summarize(data: pd.DataFrame, cap: int, excluded_dates: set[str]) -> list[dict]:
    if data.empty:
        return []
    data=performance_eligible(data)
    if 'comparison_restricted' in data:
        data=data[~data.comparison_restricted]
    data=data[~data.date.dt.strftime('%Y-%m-%d').isin(excluded_dates)]
    groups={selector:data[data.selector.eq(selector)] for selector in sorted(data.selector.unique())}
    groups['all_conditions_stacked']=data
    groups['all_conditions_unique']=data.drop_duplicates(['date','symbol'])
    result=[]
    for selector,group in groups.items():
        periods={'ALL':group,**{str(y):z for y,z in group.groupby(group.date.dt.year)}}
        for period,rows in periods.items():
            r=rows.gross_return.dropna()
            measured=rows.loc[r.index]
            capital=required_capital(measured)
            cash=float(measured.one_hundred_shares_pl_yen.sum())
            result.append({'cap':cap,'selector':selector,'period':period,'n':len(r),'pending':len(rows)-len(r),'win_rate':float((r>0).mean()) if len(r) else None,'mean':float(r.mean()) if len(r) else None,'median':float(r.median()) if len(r) else None,'worst':float(r.min()) if len(r) else None,'loss10_count':int((r<=-.1).sum()),'loss10_rate':float((r<=-.1).mean()) if len(r) else None,'mean_excluding_top3':float(r.drop(index=r.nlargest(3).index).mean()) if len(r)>3 else None,'one_hundred_share_total_pl_yen':cash,'required_capital_yen':capital,'capital_return':cash/capital if capital>0 else None})
    return result


def aggregate(output: Path) -> None:
    info=json.loads((output/'prepared.json').read_text(encoding='utf-8'))
    verify_frozen(info)
    prices=pd.read_pickle(output/'prices.pkl')
    actions=pd.read_csv(output/'actions.csv',parse_dates=['effective_date'],dtype={'symbol':str})
    ties=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(output.glob('tie_cap*.json'))]
    omitted_dates={r['date'] for r in ties}
    all_files={cap:sorted(output.glob(f'selected_cap{cap}_*.csv')) for cap in CAPS}
    month_sets=[{p.stem.split('_')[-1] for p in all_files[cap]} for cap in CAPS]
    common_months=set.intersection(*month_sets)
    metrics=[]
    counts=[]
    for cap in CAPS:
        files=[p for p in all_files[cap] if p.stem.split('_')[-1] in common_months]
        if not files:
            continue
        selected=pd.concat([pd.read_csv(p,parse_dates=['date'],dtype={'symbol':str}) for p in files],ignore_index=True)
        rows=trades(selected,prices,actions,info)
        snapshot=json.loads((output/'restriction_snapshot.json').read_text(encoding='utf-8'))
        rows['comparison_restricted']=restricted_mask(rows,snapshot['symbols'])
        rows['comparison_common_day_excluded']=rows.date.dt.strftime('%Y-%m-%d').isin(omitted_dates)
        rows.to_csv(output/f'trades_cap{cap}.csv',index=False,date_format='%Y-%m-%d',float_format='%.17g')
        metrics += summarize(rows,cap,omitted_dates)
        counts.append({'cap':cap,'completed_months':len(files),'available_months':len(all_files[cap]),'selected_rows':len(rows),'missing_or_unmodeled_endpoint_rows':int(rows.gross_return.isna().sum()),'unmodeled_fractional_rows':int(rows.unmodeled_economics_reason.ne('').sum()) if len(rows) else 0,'registry_excluded_rows':len(rows)-len(performance_eligible(rows)),'common_day_excluded_rows':int(rows.comparison_common_day_excluded.sum()),'causal_restriction_excluded_rows':int(rows.comparison_restricted.sum())})
    pd.DataFrame(metrics).to_csv(output/'metrics.csv',index=False,float_format='%.12g')
    save_json(output/'summary.json',{'identity':info['identity'],'status':'complete' if len(counts)==len(CAPS) and all(c['completed_months']==45 for c in counts) else 'partial','metadata':info,'metrics':metrics,'counts':counts,'compared_common_months':sorted(common_months),'quarantined_dates':ties,'common_day_excluded_calendar':sorted(omitted_dates),'common_day_excluded_count':len(omitted_dates)})
    print(json.dumps({'phase':'aggregate','counts':counts,'omitted_dates':sorted(omitted_dates)}),flush=True)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run','worker','aggregate'])
    parser.add_argument('--daily',type=Path)
    parser.add_argument('--actions',type=Path)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--start',default='2023-01-01')
    parser.add_argument('--end',default='2026-09-30')
    parser.add_argument('--quote-cutoff',default='2026-09-30')
    parser.add_argument('--caps',default='1000,1500,2000,3000,5000,0')
    parser.add_argument('--clear-stop',action='store_true',help='Explicitly resume from a stopped checkpoint after usage recovers')
    args=parser.parse_args()
    if args.mode in ('prepare','run'):
        if args.daily is None:
            parser.error('--daily normalized file is required')
    if args.mode=='worker':
        worker(str(args.output),tuple(int(x) for x in args.caps.split(',')))
    elif args.mode in ('prepare','run'):
        with output_lock(args.output/'run.lock'):
            if args.clear_stop and (args.output/'STOP_REQUESTED.json').exists():
                (args.output/'STOP_REQUESTED.json').unlink()
            prepare(args.daily,args.output,args.start,args.end,args.quote_cutoff,args.actions)
            if args.mode=='run':
                save_json(args.output/'run_status.json',{'status':'running','pid':os.getpid(),'started_at':pd.Timestamp.now().isoformat(),'runner_sha256':sha256(Path(__file__))})
                try:
                    with ProcessPoolExecutor(max_workers=2) as pool:
                        results=[pool.submit(worker,str(args.output),caps) for caps in ((1000,2000,5000),(1500,3000,0))]
                        for result in as_completed(results):
                            try:
                                result.result()
                            except BaseException as exc:
                                save_json(args.output/'STOP_REQUESTED.json',{'reason':'worker_error','error':repr(exc)})
                                raise
                    aggregate(args.output)
                    summary=json.loads((args.output/'summary.json').read_text(encoding='utf-8'))
                    save_json(args.output/'run_status.json',{'status':summary['status'],'finished_at':pd.Timestamp.now().isoformat(),'completed_models':sum(row['available_months'] for row in summary['counts'])})
                except BaseException as exc:
                    save_json(args.output/'run_status.json',{'status':'failed','error':repr(exc),'finished_at':pd.Timestamp.now().isoformat()})
                    raise
    elif args.mode=='aggregate':
        aggregate(args.output)

if __name__=='__main__':
    main()
