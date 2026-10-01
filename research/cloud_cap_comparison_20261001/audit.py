"""Independent checks for frozen six-cap research; never fits or retunes models."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('cap_comparison',HERE/'compare.py')
comparison=importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def audit_prepared(output: Path, legacy: Path | None) -> dict:
    info=json.loads((output/'prepared.json').read_text(encoding='utf-8'))
    comparison.verify_frozen(info)
    rows=pd.read_pickle(output/'rows.pkl')
    features=np.load(output/'features.npy',mmap_mode='r')
    assert features.shape==(len(rows),45)
    assert not rows.duplicated(['date','symbol']).any()
    names=comparison.base.FEATURES
    raw=pd.DataFrame({'date':rows.date,'ret1':features[:,names.index('ret1')],
        'ma20_gap':features[:,names.index('ma20_gap')]})
    market=raw.groupby('date').agg(
        valid_ret1=('ret1','count'),positive_ret1=('ret1',lambda s:s.gt(0).sum()),
        valid_ma20=('ma20_gap','count'),positive_ma20=('ma20_gap',lambda s:s.gt(0).sum()))
    for name,positive,valid in [('breadth_ret1_pos','positive_ret1','valid_ret1'),('breadth_ma20','positive_ma20','valid_ma20')]:
        expected=rows.date.map(market[positive]/market[valid]).to_numpy()
        np.testing.assert_allclose(features[:,names.index(name)],expected,atol=3e-8,rtol=0,equal_nan=True)
    market.to_csv(output/'breadth_denominator_audit.csv',date_format='%Y-%m-%d')
    changed={}
    if legacy:
        old=np.load(legacy/'features.npy',mmap_mode='r')
        assert old.shape==features.shape
        oldrows=pd.read_pickle(legacy/'rows.pkl')
        pd.testing.assert_series_equal(rows.date,oldrows.date)
        pd.testing.assert_series_equal(rows.symbol,oldrows.symbol)
        for at in range(0,len(features),100000):
            a=np.asarray(old[at:at+100000]);b=np.asarray(features[at:at+100000])
            unequal=~((a==b)|(np.isnan(a)&np.isnan(b)))
            for ix,name in enumerate(names):
                changed[name]=changed.get(name,0)+int(unequal[:,ix].sum())
        assert set(name for name,n in changed.items() if n)<= {'breadth_ret1_pos','breadth_ma20'},changed
    artifacts=['features.npy','rows.pkl','prices.pkl','actions.csv','restriction_snapshot.json','prepared.json']
    receipt={'status':'passed','identity':info['identity'],'rows':len(rows),
        'artifact_sha256':{name:comparison.sha256(output/name) for name in artifacts},
        'only_changed_features_from_v1':{name:n for name,n in changed.items() if n},
        'breadth_contract':'positive non-NaN rows divided by non-NaN count; all-NaN returns NaN',
        'source_sha256':info['source_sha256'],'actions_sha256':info['actions_sha256']}
    comparison.save_json(output/'independent_prepared_audit.json',receipt)
    return receipt


def capital_independent(rows: pd.DataFrame) -> float:
    if not len(rows):return 0.
    ledger={}
    for row in rows.itertuples():
        principal=float(row.entry_open)*float(row.entry_shares)
        entry=ledger.setdefault(pd.Timestamp(row.entry_date),[0.,0.]);entry[0]+=principal
        exit=ledger.setdefault(pd.Timestamp(row.exit_date),[0.,0.]);exit[1]+=principal
    current=peak=0.
    for day in sorted(ledger):
        buy,sell=ledger[day]
        current+=buy;peak=max(peak,current);current-=sell
    return peak


def audit_results(output: Path) -> dict:
    from weak_early_beta.entry_feasibility import performance_eligible
    from weak_early_beta.trade_basis import build_trade_economics,UnsupportedFractionalShares
    summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    assert summary['status']=='complete'
    metrics=pd.read_csv(output/'metrics.csv',dtype={'period':str})
    actions=pd.read_csv(output/'actions.csv',dtype={'symbol':str},parse_dates=['effective_date'])
    completed_receipts=0
    count_economics=0
    all_economic_rows=0
    disagreements=[]
    for cap in comparison.CAPS:
        source=pd.read_csv(output/f'trades_cap{cap}.csv',dtype={'symbol':str},parse_dates=['date','entry_date','exit_date'])
        assert not source.duplicated(['date','symbol','selector']).any()
        economics_columns=['entry_date','exit_date','entry_open','exit_close','gross_return','one_hundred_shares_pl_yen','entry_shares','exit_shares','status','price_basis']
        assert source.groupby(['date','symbol'])[economics_columns].nunique(dropna=False).le(1).all().all()
        all_economic_rows+=len(source)
        for period in pd.period_range('2023-01','2026-09',freq='M'):
            path=output/f'selected_cap{cap}_{period}.csv'
            receipt=json.loads((output/f'receipt_cap{cap}_{period}.json').read_text(encoding='utf-8'))
            assert receipt['selected_sha256']==comparison.sha256(path)
            assert receipt['source_hashes']==summary['metadata']['source_hashes']
            completed_receipts+=1
        unique=source.drop_duplicates(['date','symbol'])
        for row in unique.to_dict('records'):
            try:
                value=build_trade_economics(row['entry_date'],row['exit_date'],row['entry_open'],row['exit_close'],actions,symbol=row['symbol'],basis_date='2026-10-01',source_sha256=summary['metadata']['source_sha256'])
                np.testing.assert_allclose([row['gross_return'],row['one_hundred_shares_pl_yen']],
                    [value['gross_return'],value['one_hundred_shares_pl_yen']],atol=1e-7,rtol=1e-11,equal_nan=True)
                if pd.notna(row['gross_return']):
                    share_count=100.
                    events=actions[actions.symbol.eq(row['symbol']) & actions.effective_date.gt(row['entry_date']) & actions.effective_date.le(row['exit_date'])].sort_values('effective_date')
                    for action in events.itertuples():
                        share_count*=float(action.ratio)
                        assert np.isclose(share_count,round(share_count),atol=1e-8,rtol=0)
                    buy_cash=float(row['entry_open'])*100.
                    sell_cash=float(row['exit_close'])*share_count
                    np.testing.assert_allclose([row['entry_shares'],row['exit_shares'],row['gross_return'],row['one_hundred_shares_pl_yen']],
                        [100.,share_count,sell_cash/buy_cash-1,sell_cash-buy_cash],atol=1e-7,rtol=1e-11)
            except UnsupportedFractionalShares:
                assert pd.isna(row['gross_return']) and row['status']=='unmodeled_fractional_shares'
            count_economics+=1
        eligible=performance_eligible(source)
        eligible=eligible[~eligible.comparison_restricted & ~eligible.comparison_common_day_excluded]
        modes={name:eligible[eligible.selector.eq(name)] for name in eligible.selector.unique()}
        modes['all_conditions_stacked']=eligible
        modes['all_conditions_unique']=eligible.drop_duplicates(['date','symbol'])
        for recorded in metrics[metrics.cap.eq(cap)].to_dict('records'):
            rows=modes[recorded['selector']]
            if recorded['period']!='ALL':rows=rows[rows.date.dt.year.eq(int(recorded['period']))]
            measured=rows[rows.gross_return.notna()]
            r=measured.gross_return
            assert len(r)==recorded['n']
            assert len(rows)-len(r)==recorded['pending']
            value={'win_rate':(r>0).sum()/len(r),'mean':r.sum()/len(r),'median':r.median(),
                'worst':r.min(),'loss10_count':int((r<=-.1).sum()),'loss10_rate':(r<=-.1).sum()/len(r),
                'mean_excluding_top3':np.sort(r.to_numpy())[:-3].mean() if len(r)>3 else np.nan,
                'one_hundred_share_total_pl_yen':measured.one_hundred_shares_pl_yen.sum(),
                'required_capital_yen':capital_independent(measured)}
            value['capital_return']=value['one_hundred_share_total_pl_yen']/value['required_capital_yen'] if value['required_capital_yen'] else np.nan
            for key,expected in value.items():
                if not np.isclose(recorded[key],expected,atol=1e-5 if 'yen' in key else 1e-10,rtol=1e-10,equal_nan=True):
                    disagreements.append({'cap':cap,'selector':recorded['selector'],'period':recorded['period'],'metric':key,'recorded':recorded[key],'independent':expected})
    assert not disagreements,disagreements
    assert completed_receipts==270
    receipt={'status':'passed','completed_monthly_checkpoint_receipts':completed_receipts,
        'independent_metric_rows':len(metrics),'trade_economics_unique_arm_identities_checked':count_economics,
        'all_selected_rows_economics_checked_through_identical_identity_inputs':all_economic_rows,
        'win_rate_denominator':'all measured returns including zero, matching current Cloud metrics.py',
        'cash_method':'independent chronological event ratios on 100 entry shares; verifies integral intermediate shares, then exit_price*exit_shares-entry_price*100',
        'capital_method':'independent date ledger: all open purchases before close sales; releases purchase principal',
        'common_day_excluded_calendar':summary['common_day_excluded_calendar'],
        'disagreements':disagreements,'summary_sha256':comparison.sha256(output/'summary.json')}
    comparison.save_json(output/'independent_result_audit.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepared','results'])
    parser.add_argument('--output',type=Path,default=comparison.DEFAULT_OUT)
    parser.add_argument('--legacy',type=Path)
    args=parser.parse_args()
    result=audit_prepared(args.output,args.legacy) if args.mode=='prepared' else audit_results(args.output)
    print(json.dumps(result,ensure_ascii=True))
