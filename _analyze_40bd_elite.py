#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""少数精鋭スコアリング探索: 6条件AND・低N・40BD平均&+100%捕捉重視（読み取り専用）

候補A(52件=確定11+未確定41)が多すぎるので、もっと過学習寄りで検出数を絞る。
確定 N_MIN〜N_MAX 件 / 未確定 ≤ UNCONF_MAX 件 に収まる6条件ANDを総当たりし、
平均40BD・+100%捕捉・中央値の3軸でランキングする。本番ファイルには一切触れない。
"""
import math
from itertools import combinations
import numpy as np
import pandas as pd
import optimize_screener as opt

WIN40, BIG50, BIG100 = 0.20, 0.50, 1.00
N_MIN, N_MAX = 3, 10        # 少数精鋭: 40BD確定3〜10件
UNCONF_MAX = 12             # 現在の検出(未確定)も絞る
TODAY = pd.Timestamp.today().normalize()
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
    d = pd.to_datetime(r["date"], errors="coerce")
    rec["days"] = int((TODAY - d).days) if pd.notna(d) else -1
    rows.append(rec)
df = pd.DataFrame(rows)
conds = [c for c in opt.BOOL_CONDS if c in df.columns]
for c in conds:
    df[c] = df[c].astype(bool)
df_conf = df[df["perf_40bd"].notna()].reset_index(drop=True)
df_unconf = df[df["perf_40bd"].isna()].reset_index(drop=True)
perf40 = df_conf["perf_40bd"].to_numpy(dtype=float)


def make_bits(frame):
    out = []
    for c in conds:
        v = frame[c].to_numpy(dtype=bool)
        b = 0
        for i in np.nonzero(v)[0]:
            b |= (1 << int(i))
        out.append(b)
    return out


conf_bits = make_bits(df_conf)
unconf_bits = make_bits(df_unconf)


def bits_to_idx(bits):
    out = []
    while bits:
        low = bits & (-bits)
        out.append(low.bit_length() - 1)
        bits ^= low
    return out


def stats_of(idx):
    v = perf40[idx]; n = len(v)
    if n == 0:
        return None
    return dict(n=n, avg=float(v.mean()), med=float(np.median(v)),
                wr20=float((v >= WIN40).mean()), n50=int((v >= BIG50).sum()),
                n100=int((v >= BIG100).sum()), mx=float(v.max()), mn=float(v.min()))


def pf(v):
    return f"{v*100:+.1f}%" if pd.notna(v) else "  --"


results = []
for ci in combinations(range(len(conds)), 6):
    b = conf_bits[ci[0]]
    for j in ci[1:]:
        b &= conf_bits[j]
        if b == 0:
            break
    if b == 0:
        continue
    nconf = b.bit_count()
    if nconf < N_MIN or nconf > N_MAX:
        continue
    ub = unconf_bits[ci[0]]
    for j in ci[1:]:
        ub &= unconf_bits[j]
        if ub == 0:
            break
    nunconf = ub.bit_count()
    if nunconf > UNCONF_MAX:
        continue
    st = stats_of(bits_to_idx(b))
    results.append((st, nunconf, ci))


def show(res, title, key):
    res = sorted(res, key=key)
    print(NL + f"── {title} (上位10) ──")
    print(f"  {'#':>2}{'確定':>4}{'平均':>8}{'中央':>8}{'+20%':>6}{'+50%':>5}{'+100%':>6}"
          f"{'最大':>8}{'未確':>5}{'計':>4}  条件")
    for rk, (st, nu, ci) in enumerate(res[:10], 1):
        combo = "+".join(conds[i] for i in ci)
        print(f"  {rk:>2}{st['n']:>4}{st['avg']*100:>+7.1f}%{st['med']*100:>+7.1f}%"
              f"{st['wr20']*100:>5.0f}%{st['n50']:>5}{st['n100']:>6}{st['mx']*100:>+7.0f}%"
              f"{nu:>5}{st['n']+nu:>4}  {combo}")


print("=" * 100)
print(f"少数精鋭探索  6条件AND  確定{N_MIN}〜{N_MAX}件 / 未確定≤{UNCONF_MAX}件")
print(f"  比較対象: 候補A(超攻め)=確定11+未確定41=52件")
print(f"  該当候補: {len(results)}通り")
print("=" * 100)

if not results:
    print("該当なし（フィルタが厳しすぎ）。N_MAX/UNCONF_MAXを緩めて再実行してください。")
    raise SystemExit

show(results, "平均40BDトップ", key=lambda x: (-x[0]["avg"], -x[0]["n100"], -x[0]["n50"]))
show(results, "+100%捕捉トップ", key=lambda x: (-x[0]["n100"], -x[0]["n50"], -x[0]["avg"]))
show(results, "中央値トップ(再現性重視)", key=lambda x: (-x[0]["med"], -x[0]["wr20"], -x[0]["avg"]))


def detail(ci, label):
    combo = [conds[i] for i in ci]
    print(NL + "=" * 100)
    print(f"【{label}】  {'+'.join(combo)}")
    print("=" * 100)
    cb = conf_bits[ci[0]]
    for j in ci[1:]:
        cb &= conf_bits[j]
    cidx = bits_to_idx(cb)
    st = stats_of(cidx)
    print(f"■ 40BD確定 {st['n']}件  平均{st['avg']*100:+.1f}% 中央{st['med']*100:+.1f}% "
          f"+20%率{st['wr20']*100:.0f}% +50%{st['n50']}件 +100%{st['n100']}件 "
          f"最大{st['mx']*100:+.0f}% 最小{st['mn']*100:+.0f}%")
    sub = df_conf.iloc[cidx].sort_values("perf_40bd", ascending=False)
    print(f"  {'日付':<11}{'銘柄':<6}{'社名':<22}{'5BD':>7}{'10BD':>7}{'20BD':>7}{'40BD':>8}")
    for _, r in sub.iterrows():
        nm = (r["name"] or "")[:20]
        print(f"  {r['date']:<11}{r['symbol']:<6}{nm:<22}"
              f"{pf(r['perf_5bd']):>7}{pf(r['perf_10bd']):>7}{pf(r['perf_20bd']):>7}{pf(r['perf_40bd']):>8}")
    ub = unconf_bits[ci[0]]
    for j in ci[1:]:
        ub &= unconf_bits[j]
    uidx = bits_to_idx(ub)
    usub = df_unconf.iloc[uidx].sort_values("cur_perf", ascending=False, na_position="last")
    cv = usub["cur_perf"].dropna().to_numpy()
    msg = ""
    if len(cv):
        msg = (f"  暫定平均{cv.mean()*100:+.1f}% 暫定+20%率{(cv>=WIN40).mean()*100:.0f}% "
               f"最大{cv.max()*100:+.0f}%")
    print(f"■ 40BD未確定 {len(usub)}件（現在値=最新終値/entry-1）{msg}")
    print(f"  {'日付':<11}{'銘柄':<6}{'社名':<20}{'経過':>4}{'5BD':>7}{'10BD':>7}{'20BD':>7}{'現在値':>8}")
    for _, r in usub.iterrows():
        nm = (r["name"] or "")[:18]
        print(f"  {r['date']:<11}{r['symbol']:<6}{nm:<20}{r['days']:>3}d"
              f"{pf(r['perf_5bd']):>7}{pf(r['perf_10bd']):>7}{pf(r['perf_20bd']):>7}{pf(r['cur_perf']):>8}")


by_avg = sorted(results, key=lambda x: (-x[0]["avg"], -x[0]["n100"], -x[0]["n50"]))
by_n100 = sorted(results, key=lambda x: (-x[0]["n100"], -x[0]["n50"], -x[0]["avg"]))
# 中央値重視: 同点は勝率→平均→合計件数(少ない方)でタイブレーク
by_med = sorted(results, key=lambda x: (-x[0]["med"], -x[0]["wr20"], -x[0]["avg"], x[0]["n"] + x[1]))
detail(by_avg[0][2], "平均40BDトップ候補(外れ値依存に注意)")
if by_n100[0][2] != by_avg[0][2]:
    detail(by_n100[0][2], "+100%捕捉トップ候補(外れ値依存に注意)")
detail(by_med[0][2], "中央値トップ候補(再現性重視・推奨)")

print(NL + "探索完了（ファイル更新・デプロイなし）")
