"""Export every tested policy/exit metric from completed fixed DEV pools."""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'research/cloud_full_search_20261001'
sys.path.insert(0, str(HERE))
from common import CACHE, SCREEN_MONTHS, ENDPOINTS, write_json, sha, lease_ok
from search import Data, policies, choose, robust

def main():
    if not lease_ok(): raise RuntimeError('usage lease missing/expired')
    data = Data(); count = total = 0
    folder = CACHE/'all_policy_metrics'; folder.mkdir(exist_ok=True)
    summaries = []
    for stage in ('screen', 'refined'):
        full = stage == 'refined'
        months = [str(m) for m in pd.period_range('2023-01','2024-12',freq='M')] if full else SCREEN_MONTHS
        for p in sorted((CACHE/stage).glob('*.json')):
            cfg = json.loads(p.read_text(encoding='utf-8'))['config']
            target = folder/f"{stage}_{cfg['id']}.csv"
            receipt = target.with_suffix('.json')
            if receipt.exists():
                record = json.loads(receipt.read_text(encoding='utf-8'))
                if record['contract'] != data.info['hashes'] or sha(target) != record['sha256']:
                    raise RuntimeError('changed policy export checkpoint')
                summaries.append({k:v for k,v in record.items() if k!='contract'})
                continue
            if not lease_ok(): break
            pool = data.pool(cfg,months); rows=[]
            for i, policy in enumerate(policies(full)):
                if not lease_ok(): return
                ids=data.measured(choose(pool,policy,data.ordinal),'DEV')
                for endpoint in ENDPOINTS:
                    m=data.metrics(ids,endpoint)
                    rows.append({'policy_number':i,'policy_json':json.dumps(policy,sort_keys=True),'endpoint':endpoint,'quality_gate_pass':robust(m),**m})
            metrics=pd.DataFrame(rows)
            tmp=target.with_suffix('.tmp'); metrics.to_csv(tmp,index=False,float_format='%.15g'); tmp.replace(target)
            sufficiently_sized=metrics[metrics.n.ge(40)]
            mean_max = sufficiently_sized.sort_values('mean_pct',ascending=False).iloc[0].to_dict() if len(sufficiently_sized) else None
            record={'stage':stage,'config':cfg['id'],'metric_rows':len(metrics),'quality_passes':int(metrics.quality_gate_pass.sum()),
                    'mean_max_n40_dev_only':mean_max,'sha256':sha(target),'contract':data.info['hashes']}
            expected=json.loads(p.read_text(encoding='utf-8'))
            if record['quality_passes'] != expected['qualifying'] or len(metrics) != expected['tested_policies_endpoints']:
                raise AssertionError('export disagrees with completed selector search')
            write_json(receipt,record); summaries.append({k:v for k,v in record.items() if k!='contract'})
            count+=1; total+=len(metrics)
    write_json(HERE/'POLICY_EXPORTS.json',{'status':'PARTIAL' if len(list((CACHE/'screen').glob('*.json')))<864 else 'SCREEN_COMPLETE',
                                         'scope':'Fixed development periods only; not candidate validation or adoption.', 'exports':summaries})
    print(json.dumps({'exported_configurations':count,'exported_metric_rows':total,'total_saved_exports':len(summaries)}))

if __name__=='__main__': main()
