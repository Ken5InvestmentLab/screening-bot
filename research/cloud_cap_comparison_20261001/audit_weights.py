"""Reconstruct each fitted month's teacher class counts and dynamic weight."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cap_comparison',HERE/'compare.py')
comparison=importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
output=comparison.DEFAULT_OUT
info=json.loads((output/'prepared.json').read_text(encoding='utf-8'))
comparison.verify_frozen(info)
f=pd.read_pickle(output/'rows.pkl')
common=f.source_usable & f.previous_source_usable & f.feature_complete & f.previous_actual_volume.ge(10000) & f.actual_volume.ge(5000) & f.actual_close.ge(20)
rows=[]
for cap in comparison.CAPS:
    eligible=common & (f.previous_actual_close.le(cap) if cap else True)
    labels=f.loc[eligible & f.target5_no.notna() & f.target_end_date.notna(),['date','target5_no','target_end_date']].copy()
    labels['teacher']=(labels.groupby('date').target5_no.rank(pct=True,method='average')>=.9975).astype(np.int8)
    labels=labels.sort_values('target_end_date',kind='mergesort')
    endpoints=labels.target_end_date.to_numpy()
    positive_sum=labels.teacher.to_numpy().cumsum(dtype=np.int64)
    for month in pd.period_range(info['start'],info['end'],freq='M'):
        count=int(endpoints.searchsorted(month.start_time.to_datetime64(),side='left'))
        pos=int(positive_sum[count-1]) if count else 0
        neg=count-pos
        effective_pos=max(pos,1)
        effective_neg=max(count-effective_pos,1)
        expected=min(effective_neg/effective_pos,80)
        receipt=output/f'receipt_cap{cap}_{month}.json'
        recorded=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else None
        if recorded:assert recorded['train_rows']==count
        rows.append({'cap':cap,'month':str(month),'training_rows':count,'positive_teacher_rows':pos,
            'negative_teacher_rows':neg,'uncapped_negative_positive_ratio':neg/max(pos,1),
            'effective_scale_pos_weight':expected,'completed_fit_receipt_checked':bool(recorded)})
table=pd.DataFrame(rows)
table.to_csv(output/'actual_monthly_model_weights.csv',index=False,float_format='%.15g')
receipt={'status':'passed','identity':info['identity'],'expected_models':len(table),
    'completed_receipts_checked':int(table.completed_fit_receipt_checked.sum()),
    'effective_weight_values':sorted(table.effective_scale_pos_weight.unique().tolist()),
    'prepared_model_parameters_are_template':True,
    'template_scale_pos_weight':info['model_parameters']['scale_pos_weight'],
    'actual_dynamic_formula':'effective_pos=max(positive_teacher_rows,1); effective_neg=max(training_rows-effective_pos,1); scale_pos_weight=min(effective_neg/effective_pos,80)',
    'teacher_definition':'eligible within cap, same-date target5_no average percentile rank >= 0.9975',
    'monthly_causality':'target_end_date < month_start',
    'source_sha256':info['source_sha256'],
    'source_hashes':info['source_hashes'],
    'csv_sha256':comparison.sha256(output/'actual_monthly_model_weights.csv')}
comparison.save_json(output/'actual_monthly_model_weights_metadata.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='source_hashes'}))
