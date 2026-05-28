#!/usr/bin/env python3
"""
任意評価軸(5BD/10BD/20BD) で C(38,6) を全データ ブルートフォース探索し
品質ゲート無視で「最良ロジック」を出す。

使い方:
    py analyze_best_brute.py 10  # 10BD
    py analyze_best_brute.py 20  # 20BD
    py analyze_best_brute.py 5   # 5BD
"""
import os, sys
import numpy as np
import pandas as pd
from itertools import combinations

EVAL = sys.argv[1] if len(sys.argv) > 1 else "10"
if EVAL not in ("5", "10", "20"):
    print(f"❌ 引数は 5 / 10 / 20 のいずれかにしてください (received: {EVAL})")
    sys.exit(1)

if EVAL == "5":
    import optimize_screener as opt
elif EVAL == "10":
    import optimize_screener_10bd as opt
else:
    import optimize_screener_20bd as opt

CURRENT = ["body1","stoch75","rsi5070","ich_price_kijun","pre_down3","gap_up"]
MIN_N = 10  # ★6サンプル最低件数（外れ値1個で全部動かないように）

def main():
    print("="*70)
    print(f"{EVAL}BD評価モード — 全データ ブルートフォース最良ロジック探索")
    print("="*70)

    print("\n📡 データ取得...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")
    print(f"  alerts_raw: {len(ar)}行 / signals_archive: {len(sa)}行")

    ar_c = opt.parse_alerts(ar); ar_c['_from_archive'] = False
    sa_c = opt.parse_alerts(sa); sa_c['_from_archive'] = True
    alerts = pd.concat([ar_c, sa_c], ignore_index=True)
    if "alert_id" in alerts.columns and len(alerts) > 0:
        _has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_has_id].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_has_id],
        ], ignore_index=True)
    print(f"  {EVAL}BD確定済み合計: {len(alerts)}件")

    print("\n📊 指標計算...")
    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件 / 全体勝率{df['win_5bd'].mean()*100:.1f}% 平均{df['perf_5bd'].mean()*100:+.2f}%")

    CONDS = opt.BOOL_CONDS
    print(f"\n🔬 ブルートフォース探索: C({len(CONDS)},6) = {len(list(combinations(CONDS, 6)))}通り")

    # ブール行列 (N x 38)
    M = np.stack([df[c].astype(bool).to_numpy() for c in CONDS], axis=1)
    perf = df["perf_5bd"].to_numpy()
    win  = df["win_5bd"].to_numpy().astype(float)
    win10 = (perf >= 0.10).astype(float)
    lose10 = (perf <= -0.10).astype(float)
    N = len(df)

    # 現行ベースライン
    cur_idx = [CONDS.index(c) for c in CURRENT]
    cur_mask = M[:, cur_idx].all(axis=1)
    cur_n = int(cur_mask.sum())
    cur_wr = float(win[cur_mask].mean()) if cur_n else 0
    cur_avg = float(perf[cur_mask].mean()) if cur_n else 0
    cur_w10 = int(win10[cur_mask].sum())
    cur_l10 = int(lose10[cur_mask].sum())
    print(f"\n📏 現行ロジック ({'+'.join(CURRENT)}) を{EVAL}BD評価:")
    print(f"   ★6 {cur_n}件 / 勝率{cur_wr*100:.1f}% / 平均{cur_avg*100:+.2f}%"
          f" / +10%{cur_w10}件 / -10%{cur_l10}件")

    # 全探索
    print(f"\n  探索開始 (MIN_N={MIN_N}件)...")
    best_wr = (-1, None, None)   # (wr, combo_idx, stats)
    best_avg = (-99, None, None)
    best_comp = (-9999, None, None)
    progress_step = 200_000
    cnt = 0
    for combo in combinations(range(len(CONDS)), 6):
        cnt += 1
        if cnt % progress_step == 0:
            print(f"    {cnt:,}通り処理済み...")
        mask = M[:, combo[0]] & M[:, combo[1]] & M[:, combo[2]] & M[:, combo[3]] & M[:, combo[4]] & M[:, combo[5]]
        n = int(mask.sum())
        if n < MIN_N: continue
        sub_perf = perf[mask]
        sub_win  = win[mask]
        wr  = float(sub_win.mean())
        avg = float(sub_perf.mean())
        w10 = float(win10[mask].sum())
        l10 = float(lose10[mask].sum())
        # composite (rate_adjusted): wr*40 + avg*100 + (w10-l10)/n*250
        composite = wr*40 + avg*100 + (w10-l10)/n*250
        stats = (n, wr, avg, int(w10), int(l10), composite)
        if wr > best_wr[0]:
            best_wr = (wr, combo, stats)
        if avg > best_avg[0]:
            best_avg = (avg, combo, stats)
        if composite > best_comp[0]:
            best_comp = (composite, combo, stats)
    print(f"  ✅ 探索完了: {cnt:,}通り")

    def fmt(label, best):
        _, combo_idx, stats = best
        n, wr, avg, w10, l10, comp = stats
        combo = [CONDS[i] for i in combo_idx]
        print(f"\n🏆 {label}")
        print(f"   {'+'.join(combo)}")
        print(f"   ★6 {n}件 / 勝率{wr*100:.1f}% / 平均{avg*100:+.2f}%"
              f" / +10%{w10}件 / -10%{l10}件 / composite {comp:.2f}")
        return combo

    combo_wr = fmt("勝率最大", best_wr)
    combo_avg = fmt("平均最大", best_avg)
    combo_comp = fmt("composite最大", best_comp)

    # ★6シグナル一覧（compositeベスト基準）
    def show_signals(combo, label):
        idxs = [CONDS.index(c) for c in combo]
        mask = M[:, idxs].all(axis=1)
        s6_df = df[mask].sort_values("date", ascending=False)
        cur_pairs = set(zip(df[cur_mask]["symbol"], df[cur_mask]["date"]))
        new_pairs = set(zip(s6_df["symbol"], s6_df["date"]))
        keep = len(cur_pairs & new_pairs)
        add  = len(new_pairs - cur_pairs)
        drop = len(cur_pairs - new_pairs)
        print(f"\n── 【{label}】★6シグナル一覧 ({'+'.join(combo)}) ──")
        print(f"  現行★6との: 継続{keep}件 / 新規{add}件 / 脱落{drop}件")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {EVAL+'BD騰落率':>10}  状態")
        for _, row in s6_df.iterrows():
            sign = "+" if row["perf_5bd"] >= 0 else ""
            status = "★継続" if (row["symbol"], row["date"]) in cur_pairs else "🆕新規"
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24}"
                  f" {sign}{row['perf_5bd']*100:>7.1f}%  {status}")

    show_signals(combo_comp, "composite最大")
    if combo_wr != combo_comp:
        show_signals(combo_wr, "勝率最大")
    if combo_avg != combo_comp and combo_avg != combo_wr:
        show_signals(combo_avg, "平均最大")

if __name__ == "__main__":
    main()
