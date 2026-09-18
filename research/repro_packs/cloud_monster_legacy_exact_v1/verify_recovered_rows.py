import csv, hashlib, json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent
UNION=ROOT/'artifacts/cloud_two_lane_union_jpx.csv'
COMPARE=ROOT/'artifacts/cloud_priorityA_monsters_compare_teacher.csv'
EXPECTED={
    'union_sha256':'91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62',
    'compare_sha256':'1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54',
    'n':63,'mean':0.09856926744273571,'median':0.03333333333333344,
    'win':0.5714285714285714,'plus20':0.30158730158730157,
    'plus30':0.19047619047619047,'minus10':0.2222222222222222,
    'top5_ex':0.04026860142497455,
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(UNION)==EXPECTED['union_sha256']
assert sha(COMPARE)==EXPECTED['compare_sha256']
rows=list(csv.DictReader(UNION.open(encoding='utf-8-sig')))
m=[r for r in rows if r['lane']=='Monster']; x=[float(r['ret5']) for r in m]; sx=sorted(x,reverse=True)
got={'n':len(x),'mean':statistics.fmean(x),'median':statistics.median(x),'win':sum(v>0 for v in x)/len(x),'plus20':sum(v>=.2 for v in x)/len(x),'plus30':sum(v>=.3 for v in x)/len(x),'minus10':sum(v<=-.1 for v in x)/len(x),'top5_ex':statistics.fmean(sx[5:])}
for k,v in EXPECTED.items():
    if k.endswith('sha256'): continue
    assert got[k]==v or math.isclose(got[k],v,rel_tol=0,abs_tol=2e-16),(k,got[k],v)
assert len(list(csv.DictReader(COMPARE.open(encoding='utf-8-sig'))))==19
print(json.dumps({'status':'EXACT_ROWS_VERIFIED',**got},indent=2))
