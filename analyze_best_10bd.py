#!/usr/bin/env python3
"""
10BD評価モードでの「品質ゲート無視・最良ロジック」分析。

optimize_screener_10bd.py が出力した Step 6 上位10候補を全データ(1549件)で再評価し、
勝率・平均・大幅上昇/下落・★6シグナル一覧を出してベスト候補を決める。
"""
import os, sys, json
import pandas as pd
import numpy as np
from datetime import datetime

# 10BD版モジュールを再利用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import optimize_screener_10bd as opt

# Step 6 上位10候補（log抽出: 全て方式A）
TOP10 = [
    ["vol30","body2","macdgc","atr5","rsi5070","bb80"],
    ["vol30","body2","macdpos","atr5","stoch75","rsi5070"],
    ["vol30","macdpos","atr5","stoch75","rsi5070","bb80"],
    ["vol20","body2","macdgc","atr5","rsi5070","bb80"],
    ["vol30","sbull","macdgc","atr5","rsi5070","bb80"],
    ["vol30","body1","macdgc","atr5","rsi5070","bb80"],
    ["vol30","body2","macdgc","atr5","rsi5070","ich_price_tenkan"],
    ["vol30","body2","macdgc","atr5","stoch60","rsi5070"],
    ["vol30","body2","macdgc","atr5","rsi5070","ich_price_kijun"],
    ["vol30","body2","atr5","stoch75","rsi5070","bb80"],
]
CURRENT = ["body1","stoch75","rsi5070","ich_price_kijun","pre_down3","gap_up"]

def main():
    print("="*70)
    print("10BD評価モード — ベスト候補ロジック分析")
    print("="*70)

    # データ取得（optimize_screener_10bd の main() と同じ流れ）
    print("\n📡 Step 1: データ取得中...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")

    print(f"  alerts_raw: {len(ar)}行 / signals_archive: {len(sa)}行 / ohlcv_4h: {len(oh)}行")

    # parse（10BD基準: 内部でperf_5bd列にp10を格納）
    ar_c = opt.parse_alerts(ar)
    sa_c = opt.parse_alerts(sa)
    ar_c['_from_archive'] = False
    sa_c['_from_archive'] = True
    alerts = pd.concat([ar_c, sa_c], ignore_index=True)
    if "alert_id" in alerts.columns and len(alerts) > 0:
        _has_id = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_has_id].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_has_id],
        ], ignore_index=True)
    print(f"  10BD確定済み合計: {len(alerts)}件")

    # 指標計算
    print("\n📊 Step 2: 指標計算中...")
    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件")
    print(f"  全体勝率(10BD): {df['win_5bd'].mean()*100:.1f}%"
          f" / 全体平均(10BD): {df['perf_5bd'].mean()*100:+.2f}%")

    # 評価関数
    def eval_combo(combo, label):
        for c in combo:
            df[c] = df[c].astype(bool)
        sc = sum(df[c].astype(int) for c in combo)
        s6 = df[sc == 6].copy()
        st = opt.calc_stats(s6)
        return {
            "label": label, "combo": combo, "df_s6": s6,
            "n": st["n"], "wr": st["wr_raw"]*100, "avg": st["avg_raw"]*100,
            "win10": st["win10_raw"], "lose10": st["lose10_raw"],
            "composite": st["composite"],
        }

    print("\n🔬 候補10通り + 現行ロジック を全データ(10BD)で評価")
    print(f"  {'#':<3} {'勝率':>6} {'平均':>8} {'件数':>5} {'+10%':>5} {'-10%':>5} {'composite':>10}  条件")
    print(f"  {'-'*3} {'-'*6} {'-'*8} {'-'*5} {'-'*5} {'-'*5} {'-'*10}  {'-'*40}")

    results = []
    cur = eval_combo(CURRENT, "現行")
    results.append(cur)
    print(f"  {'現行':<3} {cur['wr']:>5.1f}% {cur['avg']:>+7.2f}% {cur['n']:>5}件"
          f" {int(cur['win10']):>5} {int(cur['lose10']):>5} {cur['composite']:>10.2f}  "
          f"{'+'.join(cur['combo'])}")

    for i, combo in enumerate(TOP10, 1):
        r = eval_combo(combo, f"#{i}")
        results.append(r)
        print(f"  #{i:<2} {r['wr']:>5.1f}% {r['avg']:>+7.2f}% {r['n']:>5}件"
              f" {int(r['win10']):>5} {int(r['lose10']):>5} {r['composite']:>10.2f}  "
              f"{'+'.join(r['combo'])}")

    # 候補からベスト選定（composite最大 / 勝率最大 / 平均最大 の3軸）
    cands_only = results[1:]  # 現行を除く
    best_comp = max(cands_only, key=lambda r: r["composite"])
    best_wr   = max(cands_only, key=lambda r: (r["wr"], r["n"]))
    best_avg  = max(cands_only, key=lambda r: (r["avg"], r["n"]))

    print("\n🏆 軸別ベスト（候補10通りから / 全データ評価）")
    print(f"  composite最大: {best_comp['label']} → 勝率{best_comp['wr']:.1f}% 平均{best_comp['avg']:+.2f}% {best_comp['n']}件")
    print(f"      条件: {'+'.join(best_comp['combo'])}")
    print(f"  勝率最大     : {best_wr['label']} → 勝率{best_wr['wr']:.1f}% 平均{best_wr['avg']:+.2f}% {best_wr['n']}件")
    print(f"      条件: {'+'.join(best_wr['combo'])}")
    print(f"  平均最大     : {best_avg['label']} → 勝率{best_avg['wr']:.1f}% 平均{best_avg['avg']:+.2f}% {best_avg['n']}件")
    print(f"      条件: {'+'.join(best_avg['combo'])}")

    # 各ベストの★6シグナル一覧（現行と差分も）
    for tag, r in [("composite最大", best_comp), ("勝率最大", best_wr), ("平均最大", best_avg)]:
        print(f"\n  ── 【{tag}】★6シグナル一覧 ({r['label']}: {'+'.join(r['combo'])}) ──")
        s6 = r["df_s6"].sort_values("date", ascending=False)
        cur_syms = set(zip(cur["df_s6"]["symbol"], cur["df_s6"]["date"]))
        new_syms = set(zip(s6["symbol"], s6["date"]))
        print(f"  現行★6との重複: {len(cur_syms & new_syms)}件 / 新規追加: {len(new_syms - cur_syms)}件"
              f" / 脱落: {len(cur_syms - new_syms)}件")
        print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'10BD騰落率':>10}  状態")
        for _, row in s6.iterrows():
            sign = "+" if row["perf_5bd"] >= 0 else ""
            status = "★継続" if (row["symbol"], row["date"]) in cur_syms else "🆕新規"
            print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24}"
                  f" {sign}{row['perf_5bd']*100:>7.1f}%  {status}")

    print("\n  ── 【現行ロジック】★6シグナル一覧（10BD評価で再採点）──")
    s6 = cur["df_s6"].sort_values("date", ascending=False)
    print(f"  {'日付':<12} {'銘柄':<8} {'社名':<24} {'10BD騰落率':>10}")
    for _, row in s6.iterrows():
        sign = "+" if row["perf_5bd"] >= 0 else ""
        print(f"  {row['date']:<12} {row['symbol']:<8} {row['name']:<24} {sign}{row['perf_5bd']*100:>7.1f}%")

if __name__ == "__main__":
    main()
