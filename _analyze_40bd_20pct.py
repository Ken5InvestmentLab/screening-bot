#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
40BD×+20% 平均騰落率特化スコアリングの分析（読み取り専用・本番に一切触れない）

目的:
  現行Stable(5BD×+10%基準) を 40BD×+20%基準・平均騰落率重視・満点(全条件通過)抽出に
  変えると、検出される銘柄群と成績がどう変わるかを試算する。デプロイ・ファイル更新なし。
"""
import math
from itertools import combinations
import numpy as np
import pandas as pd
import optimize_screener as opt

WIN40 = 0.20          # 「勝ち」定義: 40BDで+20%以上
BIG50 = 0.50          # 大勝ち閾値
BIG100 = 1.00         # 超大勝ち閾値
MIN_N_SEARCH = 5      # 探索の最低検出数（満点6条件ANDは選択性が高いので低め）
TOPK = 18             # 候補表示数
CUR_STABLE = ["vol20", "sbull", "body1", "macdpos", "pre_down3", "gap_up"]

NL = "\n"

# ─────────────────────────────────────────────────────────────
# Step 1: データ取得
# ─────────────────────────────────────────────────────────────
print("=" * 70)
print("40BD × +20% 平均騰落率特化スコアリング 分析（試算のみ・本番非変更）")
print("=" * 70)
svc = opt.get_service()
ar = opt.fetch(svc, "alerts_raw")
try:
    sa = opt.fetch(svc, "signals_archive")
except Exception as e:
    sa = []
    print("signals_archive 取得失敗:", e)
oh = opt.fetch(svc, "ohlcv_4h")
ohlcv = opt.parse_ohlcv(oh)

ar_all = opt.parse_alerts(ar, include_unconfirmed=True)
sa_all = opt.parse_alerts(sa, include_unconfirmed=True)
ar_all["_from_archive"] = False
sa_all["_from_archive"] = True
allsig = pd.concat([ar_all, sa_all], ignore_index=True)
if "alert_id" in allsig.columns and len(allsig) > 0:
    has_id = allsig["alert_id"].astype(str) != ""
    allsig = pd.concat([
        allsig[has_id].drop_duplicates(subset=["alert_id"], keep="first"),
        allsig[~has_id],
    ], ignore_index=True)
print(f"BOTTOM総数(dedup後): {len(allsig)}件 / OHLCV銘柄: {len(ohlcv)}")

# ─────────────────────────────────────────────────────────────
# Step 2: 全シグナルの特徴量計算
# ─────────────────────────────────────────────────────────────
rows = []
for _, r in allsig.iterrows():
    daily = ohlcv.get(r["symbol"], [])
    f = opt.get_features(daily, r["date"])
    if not f:
        continue
    rec = {**r.to_dict(), **f}
    # 未確定銘柄の現在値（最新終値 / entry - 1）
    lc = opt.latest_close_for_signal(daily, r["date"])
    entry = r.get("entry", float("nan"))
    rec["latest_close"] = lc
    rec["cur_perf"] = (lc / entry - 1) if (lc and math.isfinite(entry) and entry > 0) else np.nan
    rows.append(rec)
df = pd.DataFrame(rows)
conds = [c for c in opt.BOOL_CONDS if c in df.columns]
for c in conds:
    df[c] = df[c].astype(bool)

df_conf = df[df["perf_40bd"].notna()].reset_index(drop=True)    # 40BD確定
df_unconf = df[df["perf_40bd"].isna()].reset_index(drop=True)   # 40BD未確定
print(f"特徴量計算済み: {len(df)}件 / 40BD確定 {len(df_conf)}件 / 40BD未確定 {len(df_unconf)}件")

perf40 = df_conf["perf_40bd"].to_numpy(dtype=float)
N = len(df_conf)


def stats_of(idx_arr):
    """40BD確定の行index配列から成績辞書を返す。"""
    v = perf40[idx_arr]
    n = len(v)
    if n == 0:
        return dict(n=0, avg=0, med=0, wr20=0, n50=0, n100=0, mx=0, mn=0)
    return dict(
        n=n, avg=float(v.mean()), med=float(np.median(v)),
        wr20=float((v >= WIN40).mean()),
        n50=int((v >= BIG50).sum()), n100=int((v >= BIG100).sum()),
        mx=float(v.max()), mn=float(v.min()),
    )


def all_pass_idx(frame, combo):
    """frame上で combo 全条件を満たす行のpositional index配列。"""
    m = np.ones(len(frame), dtype=bool)
    for c in combo:
        m &= frame[c].to_numpy(dtype=bool)
    return np.nonzero(m)[0]


# ─────────────────────────────────────────────────────────────
# Step 3: ベースライン — 現行Stableロジックを40BDで評価
# ─────────────────────────────────────────────────────────────
print(NL + "─" * 70)
print("【ベースライン】現行Stableロジックを 40BD で評価")
print(f"  条件: {'+'.join(CUR_STABLE)}")
print("─" * 70)
print(f"  母集団(40BD確定全{N}件): 平均{perf40.mean()*100:+.1f}%  "
      f"中央値{np.median(perf40)*100:+.1f}%  +20%率{(perf40>=WIN40).mean()*100:.1f}%  "
      f"+100%{int((perf40>=BIG100).sum())}件")
cur_idx = all_pass_idx(df_conf, CUR_STABLE)
cs = stats_of(cur_idx)
print(f"  現行満点(6/6 AND)検出: {cs['n']}件  平均{cs['avg']*100:+.1f}%  中央値{cs['med']*100:+.1f}%  "
      f"+20%率{cs['wr20']*100:.1f}%  +50%{cs['n50']}件  +100%{cs['n100']}件  最大{cs['mx']*100:+.1f}%")

# ─────────────────────────────────────────────────────────────
# Step 4: 大勝ち銘柄の共通点（リフト分析） on 40BD確定
# ─────────────────────────────────────────────────────────────
def lift_table(frame, mask_win, title):
    base_rate = {c: frame[c].mean() for c in conds}
    win = frame[mask_win]
    n_win = len(win)
    print(NL + f"【{title}】winner {n_win}件 / 全{len(frame)}件 の指標リフト上位12")
    if n_win == 0:
        print("  該当なし")
        return
    lifts = []
    for c in conds:
        ra = base_rate[c]
        rw = win[c].mean()
        lift = rw / ra if ra > 0 else 0.0
        lifts.append((lift, c, rw, ra))
    lifts.sort(reverse=True)
    print(f"  {'指標':<14}{'リフト':>7}{'winner率':>10}{'全体率':>9}")
    for lift, c, rw, ra in lifts[:12]:
        print(f"  {c:<14}{lift:>7.2f}{rw*100:>9.0f}%{ra*100:>8.0f}%")

print(NL + "─" * 70)
print("【大勝ち銘柄の共通点（リフト分析）】 40BD確定母集団")
print("─" * 70)
lift_table(df_conf, perf40 >= WIN40, "+20%以上 winner の共通点")
lift_table(df_conf, perf40 >= BIG50, "+50%以上 winner の共通点")
lift_table(df_conf, perf40 >= BIG100, "+100%以上 winner の共通点")

# ─────────────────────────────────────────────────────────────
# Step 5: 全探索 C(38,6) 満点AND・平均騰落率最大化（ビットマスク高速化）
# ─────────────────────────────────────────────────────────────
print(NL + "─" * 70)
print(f"【全探索】C({len(conds)},6)={math.comb(len(conds),6):,}通り 満点AND・平均最大化 (N≥{MIN_N_SEARCH})")
print("─" * 70)

# 各条件の通過行をビットマスク化（40BD確定母集団上）
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

results = []
ncond = len(conds)
for combo_i in combinations(range(ncond), 6):
    bits = col_bits[combo_i[0]]
    for j in combo_i[1:]:
        bits &= col_bits[j]
        if bits == 0:
            break
    if bits == 0:
        continue
    nhit = bits.bit_count()
    if nhit < MIN_N_SEARCH:
        continue
    idxs = np.array(bits_to_idx(bits))
    st = stats_of(idxs)
    results.append((st["avg"], st["n"], st["med"], st["wr20"], st["n50"],
                    st["n100"], st["mx"], combo_i))

print(f"  N≥{MIN_N_SEARCH} を満たす満点組み合わせ: {len(results):,}件")
# 平均騰落率降順で並べる
results.sort(key=lambda x: (-x[0], -x[5], -x[4], -x[1]))

print(NL + f"  ── 平均騰落率トップ{TOPK}（満点AND, N≥{MIN_N_SEARCH}）──")
print(f"  {'#':>2} {'件数':>4} {'平均':>8} {'中央':>8} {'+20%率':>7} {'+50%':>5} {'+100%':>6} {'最大':>8}  条件")
for rank, (avg, n, med, wr20, n50, n100, mx, ci) in enumerate(results[:TOPK], 1):
    combo = [conds[i] for i in ci]
    print(f"  {rank:>2} {n:>4} {avg*100:>+7.1f}% {med*100:>+7.1f}% {wr20*100:>6.0f}% "
          f"{n50:>5} {n100:>6} {mx*100:>+7.0f}%  {'+'.join(combo)}")

# 参考: +50%catch数を最大化する並べ替えトップ
results_big = sorted(results, key=lambda x: (-x[4], -x[5], -x[0]))
print(NL + f"  ── 参考: +50%以上の捕捉数トップ8（満点AND, N≥{MIN_N_SEARCH}）──")
print(f"  {'#':>2} {'件数':>4} {'平均':>8} {'+50%':>5} {'+100%':>6} {'+20%率':>7}  条件")
for rank, (avg, n, med, wr20, n50, n100, mx, ci) in enumerate(results_big[:8], 1):
    combo = [conds[i] for i in ci]
    print(f"  {rank:>2} {n:>4} {avg*100:>+7.1f}% {n50:>5} {n100:>6} {wr20*100:>6.0f}%  {'+'.join(combo)}")

# ─────────────────────────────────────────────────────────────
# Step 6: 採用候補を1つ選んで詳細（平均トップ かつ N が極小すぎない最初の候補）
# ─────────────────────────────────────────────────────────────
def detail_combo(combo, label):
    print(NL + "=" * 70)
    print(f"【詳細】{label}")
    print(f"  条件(満点6/6 AND): {'+'.join(combo)}")
    print("=" * 70)
    # 40BD確定 検出銘柄
    idxs = all_pass_idx(df_conf, combo)
    st = stats_of(idxs)
    print(f"  ◆40BD確定 検出 {st['n']}件  平均{st['avg']*100:+.1f}%  中央{st['med']*100:+.1f}%  "
          f"+20%率{st['wr20']*100:.0f}%  +50%{st['n50']}件  +100%{st['n100']}件  "
          f"最大{st['mx']*100:+.0f}% 最小{st['mn']*100:+.0f}%")
    sub = df_conf.iloc[idxs].copy()
    sub = sub.sort_values("perf_40bd", ascending=False)
    print(f"  {'日付':<11}{'銘柄':<7}{'社名':<22}{'40BD騰落':>9}")
    for _, row in sub.iterrows():
        nm = (row["name"] or "")[:20]
        print(f"  {row['date']:<11}{row['symbol']:<7}{nm:<22}{row['perf_40bd']*100:>+8.1f}%")

    # 現行Stableとの入れ替わり
    cur_set = set(df_conf.iloc[all_pass_idx(df_conf, CUR_STABLE)]["alert_id"])
    new_set = set(sub["alert_id"])
    print(NL + f"  ◆現行Stable満点との入れ替わり(40BD確定): "
          f"共通{len(cur_set & new_set)}件 / 新規{len(new_set - cur_set)}件 / 消失{len(cur_set - new_set)}件")

    # 40BD未確定 検出銘柄（現在値ベース）
    uidx = all_pass_idx(df_unconf, combo)
    usub = df_unconf.iloc[uidx].copy()
    usub = usub.sort_values("date", ascending=False)
    cur_vals = usub["cur_perf"].dropna().to_numpy()
    print(NL + f"  ◆40BD未確定 検出 {len(usub)}件（現在値=最新終値/entry-1 で暫定評価）")
    if len(cur_vals) > 0:
        print(f"    暫定平均{cur_vals.mean()*100:+.1f}%  暫定+20%率{(cur_vals>=WIN40).mean()*100:.0f}%  "
              f"暫定+100%{int((cur_vals>=BIG100).sum())}件  最大{cur_vals.max()*100:+.0f}%")
    print(f"    {'日付':<11}{'銘柄':<7}{'社名':<20}{'perf20BD':>9}{'現在値':>9}")
    for _, row in usub.iterrows():
        nm = (row["name"] or "")[:18]
        p20 = f"{row['perf_20bd']*100:+.0f}%" if pd.notna(row["perf_20bd"]) else "  --"
        cp = f"{row['cur_perf']*100:+.0f}%" if pd.notna(row["cur_perf"]) else "  --"
        print(f"    {row['date']:<11}{row['symbol']:<7}{nm:<20}{p20:>9}{cp:>9}")
    return st

# 採用候補: 平均トップ（最もアグレッシブ）と、N≥10の最良（より堅牢）の2つを詳細表示
if results:
    top_combo = [conds[i] for i in results[0][7]]
    detail_combo(top_combo, "候補A: 平均騰落率トップ（最アグレッシブ）")

    robust = [r for r in results if r[1] >= 10]
    if robust:
        rob_combo = [conds[i] for i in robust[0][7]]
        detail_combo(rob_combo, "候補B: N≥10で平均トップ（より堅牢）")

print(NL + "分析完了（ファイル更新・デプロイなし）")
