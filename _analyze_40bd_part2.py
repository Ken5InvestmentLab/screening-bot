#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""40BD分析 part2: 大勝ち銘柄の正体 + 堅牢候補の詳細（読み取り専用）"""
import math
from itertools import combinations
import numpy as np
import pandas as pd
import optimize_screener as opt

WIN40, BIG50, BIG100 = 0.20, 0.50, 1.00
CUR_STABLE = ["vol20", "sbull", "body1", "macdpos", "pre_down3", "gap_up"]
NL = "\n"

svc = opt.get_service()
ar = opt.fetch(svc, "alerts_raw")
try:
    sa = opt.fetch(svc, "signals_archive")
except Exception:
    sa = []
oh = opt.fetch(svc, "ohlcv_4h")
ohlcv = opt.parse_ohlcv(oh)
ar_all = opt.parse_alerts(ar, include_unconfirmed=True); ar_all["_from_archive"] = False
sa_all = opt.parse_alerts(sa, include_unconfirmed=True); sa_all["_from_archive"] = True
allsig = pd.concat([ar_all, sa_all], ignore_index=True)
has_id = allsig["alert_id"].astype(str) != ""
allsig = pd.concat([allsig[has_id].drop_duplicates(subset=["alert_id"], keep="first"),
                    allsig[~has_id]], ignore_index=True)

rows = []
for _, r in allsig.iterrows():
    daily = ohlcv.get(r["symbol"], [])
    f = opt.get_features(daily, r["date"])
    if not f:
        continue
    rec = {**r.to_dict(), **f}
    lc = opt.latest_close_for_signal(daily, r["date"])
    entry = r.get("entry", float("nan"))
    rec["cur_perf"] = (lc / entry - 1) if (lc and math.isfinite(entry) and entry > 0) else np.nan
    rows.append(rec)
df = pd.DataFrame(rows)
conds = [c for c in opt.BOOL_CONDS if c in df.columns]
for c in conds:
    df[c] = df[c].astype(bool)
df_conf = df[df["perf_40bd"].notna()].reset_index(drop=True)
df_unconf = df[df["perf_40bd"].isna()].reset_index(drop=True)
perf40 = df_conf["perf_40bd"].to_numpy(dtype=float)

# ── 大勝ち銘柄の正体 ──
print("=" * 70)
print("【40BD大勝ち銘柄の正体】(+50%以上)")
print("=" * 70)
big = df_conf[df_conf["perf_40bd"] >= BIG50].sort_values("perf_40bd", ascending=False)
print(f"  {'日付':<11}{'銘柄':<7}{'社名':<22}{'40BD':>9}  満点条件プロフィール")
for _, row in big.iterrows():
    nm = (row["name"] or "")[:20]
    on = [c for c in ["stoch75","gap_up","rci9_os","rci26_os","pre_decline15","bb80","hb20","cci_os","macdpos","ema25","body2"] if row[c]]
    print(f"  {row['date']:<11}{row['symbol']:<7}{nm:<22}{row['perf_40bd']*100:>+8.0f}%  {','.join(on)}")

# ── 探索（堅牢ゾーン）──
col_bits = []
for c in conds:
    colv = df_conf[c].to_numpy(dtype=bool)
    bits = 0
    for i in np.nonzero(colv)[0]:
        bits |= (1 << int(i))
    col_bits.append(bits)

def bits_to_idx(bits):
    out = []
    while bits:
        low = bits & (-bits)
        out.append(low.bit_length() - 1)
        bits ^= low
    return out

def stats_of(idx_arr):
    v = perf40[idx_arr]; n = len(v)
    if n == 0:
        return dict(n=0, avg=0, med=0, wr20=0, n50=0, n100=0, mx=0, mn=0)
    return dict(n=n, avg=float(v.mean()), med=float(np.median(v)),
                wr20=float((v >= WIN40).mean()), n50=int((v >= BIG50).sum()),
                n100=int((v >= BIG100).sum()), mx=float(v.max()), mn=float(v.min()))

res20, res30 = [], []
for ci in combinations(range(len(conds)), 6):
    bits = col_bits[ci[0]]
    for j in ci[1:]:
        bits &= col_bits[j]
        if bits == 0:
            break
    if bits == 0:
        continue
    nhit = bits.bit_count()
    if nhit < 20:
        continue
    st = stats_of(np.array(bits_to_idx(bits)))
    rec = (st["avg"], st["n"], st["med"], st["wr20"], st["n50"], st["n100"], st["mx"], ci)
    res20.append(rec)
    if nhit >= 30:
        res30.append(rec)

def show(res, title, key):
    res = sorted(res, key=key)
    print(NL + f"  ── {title} ──")
    print(f"  {'#':>2}{'件数':>5}{'平均':>8}{'中央':>8}{'+20%率':>7}{'+50%':>5}{'+100%':>6}{'最大':>8}  条件")
    for rk, (avg, n, med, wr20, n50, n100, mx, ci) in enumerate(res[:8], 1):
        combo = [conds[i] for i in ci]
        print(f"  {rk:>2}{n:>5}{avg*100:>+7.1f}%{med*100:>+7.1f}%{wr20*100:>6.0f}%{n50:>5}{n100:>6}{mx*100:>+7.0f}%  {'+'.join(combo)}")

print(NL + "=" * 70)
print("【堅牢ゾーン探索】満点AND・N≥20（外れ値依存を抑える）")
print("=" * 70)
show(res20, "N≥20で平均トップ8", key=lambda x: (-x[0], -x[5]))
show(res20, "N≥20で+50%捕捉数トップ8", key=lambda x: (-x[4], -x[5], -x[0]))
show(res30, "N≥30で平均トップ8", key=lambda x: (-x[0], -x[5]))

# ── 堅牢候補の詳細 ──
def all_pass_idx(frame, combo):
    m = np.ones(len(frame), dtype=bool)
    for c in combo:
        m &= frame[c].to_numpy(dtype=bool)
    return np.nonzero(m)[0]

def detail(combo, label):
    print(NL + "=" * 70)
    print(f"【詳細】{label}")
    print(f"  条件(満点6/6 AND): {'+'.join(combo)}")
    print("=" * 70)
    idxs = all_pass_idx(df_conf, combo)
    st = stats_of(idxs)
    print(f"  ◆40BD確定 {st['n']}件  平均{st['avg']*100:+.1f}%  中央{st['med']*100:+.1f}%  "
          f"+20%率{st['wr20']*100:.0f}%  +50%{st['n50']}件  +100%{st['n100']}件  最大{st['mx']*100:+.0f}%")
    sub = df_conf.iloc[idxs].sort_values("perf_40bd", ascending=False)
    # 上位8 + 下位3のみ表示
    head = sub.head(10); tail = sub.tail(3)
    seen = set()
    print(f"  {'日付':<11}{'銘柄':<7}{'社名':<22}{'40BD':>9}")
    for _, row in pd.concat([head, tail]).iterrows():
        if row['alert_id'] in seen:
            continue
        seen.add(row['alert_id'])
        nm = (row["name"] or "")[:20]
        print(f"  {row['date']:<11}{row['symbol']:<7}{nm:<22}{row['perf_40bd']*100:>+8.1f}%")
    cur_set = set(df_conf.iloc[all_pass_idx(df_conf, CUR_STABLE)]["alert_id"])
    new_set = set(sub["alert_id"])
    print(f"  ◆現行Stable満点との入替(40BD確定): 共通{len(cur_set&new_set)} / 新規{len(new_set-cur_set)} / 消失{len(cur_set-new_set)}")
    uidx = all_pass_idx(df_unconf, combo)
    usub = df_unconf.iloc[uidx].sort_values("cur_perf", ascending=False)
    cur_vals = usub["cur_perf"].dropna().to_numpy()
    print(f"  ◆40BD未確定 {len(usub)}件 検出（現在値で暫定評価）")
    if len(cur_vals):
        print(f"    暫定平均{cur_vals.mean()*100:+.1f}%  暫定+20%率{(cur_vals>=WIN40).mean()*100:.0f}%  最大{cur_vals.max()*100:+.0f}%")
    print(f"    上位の現在値: " + ", ".join(
        f"{r['symbol']}{(r['name'] or '')[:6]}{r['cur_perf']*100:+.0f}%"
        for _, r in usub.head(10).iterrows() if pd.notna(r['cur_perf'])))

# 堅牢候補: N≥20平均トップ と +100%を2件拾う既知の組み合わせ
res20_byavg = sorted(res20, key=lambda x: (-x[0], -x[5]))
detail([conds[i] for i in res20_byavg[0][7]], "堅牢候補X: N≥20で平均トップ")
detail(["ema25", "atr7", "stoch75", "stoch60", "ich_price_tenkan", "gap_up"],
       "堅牢候補Y: +100%を2件捕捉(N=65)")
print(NL + "分析完了（ファイル更新・デプロイなし）")
