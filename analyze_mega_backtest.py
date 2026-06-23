#!/usr/bin/env python3
"""
Mega40 deep-reversal backtest trial

(1) 10BD/20BD/40BD × +50%/+100% でMega Hit銘柄を洗い出し
(2) Mega Hitに対するlift分析（どの指標が偏在するか）
(3) アンカー(ema25 + pre_down3 + 動的1) + 発見プール上位8 で C(8,3)=56 通り探索
(4) ベスト候補の★6シグナル一覧と成績
"""
import os, sys, math
from itertools import combinations
import pandas as pd
import numpy as np

# perf_20bd列が標準で読まれるoptimize_screener (5BD版) を流用
import optimize_screener as opt

# 固定アンカー (経験則: 中期トレンド回復 + 直近押し目)
FIXED_ANCHORS  = ["ema25", "pre_down3"]
ANCHOR_POOL    = ["vol12","vol15","sbull","macdpos","atr7","rci9_up","smbull_seq2"]
ANCHOR_LIFT_MIN = 1.2
DISCOVERY_POOL_SIZE = 8
DISCOVERY_SLOTS = 3
LIFT_MIN = 1.5
MEGA_N_MIN = 1
N_HIT_MIN = 3

def compute_lift(df, target_mask, cond_col):
    """指標condが target集団に偏在しているかのリフト計算"""
    target = target_mask.sum()
    if target == 0: return 0.0, 0.0, 0.0
    in_target = (target_mask & df[cond_col].astype(bool)).sum()
    in_all    = df[cond_col].astype(bool).sum()
    target_rate = in_target / target
    all_rate    = in_all / len(df) if len(df) else 0
    lift = target_rate / all_rate if all_rate > 0 else 0.0
    return lift, target_rate, all_rate

def main():
    print("="*78)
    print("Mega40 backtest trial")
    print("="*78)

    print("\n📡 データ取得...")
    svc = opt.get_service()
    ar = opt.fetch(svc, "alerts_raw")
    sa = opt.fetch(svc, "signals_archive")
    oh = opt.fetch(svc, "ohlcv_4h")
    ar_c = opt.parse_alerts(ar); ar_c['_from_archive']=False
    sa_c = opt.parse_alerts(sa); sa_c['_from_archive']=True
    alerts = pd.concat([ar_c, sa_c], ignore_index=True)
    if "alert_id" in alerts.columns:
        _h = alerts["alert_id"].astype(str) != ""
        alerts = pd.concat([
            alerts[_h].drop_duplicates(subset=["alert_id"], keep="first"),
            alerts[~_h]], ignore_index=True)

    print("📊 指標計算...")
    ohlcv = opt.parse_ohlcv(oh)
    rows = []
    for _, r in alerts.iterrows():
        f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
        if f: rows.append({**r.to_dict(), **f})
    df = pd.DataFrame(rows)
    print(f"  有効データ: {len(df)}件")

    # === Section 1: Mega Hit 銘柄洗い出し ===
    print("\n" + "="*78)
    print("📊 Section 1: 各評価軸 × 各閾値で Mega Hit 銘柄を洗い出し")
    print("="*78)
    for perf_col, label in [("perf_10bd","10BD"),("perf_20bd","20BD"),("perf_40bd","40BD")]:
        confirmed = df[df[perf_col].apply(lambda v: isinstance(v,(int,float)) and math.isfinite(v))]
        for th_label, th in [("+50%",0.50),("+100%",1.00)]:
            hits = confirmed[confirmed[perf_col] >= th].sort_values(perf_col, ascending=False)
            print(f"\n  【{label} × {th_label}】確定母数 {len(confirmed)}件 → Mega Hit {len(hits)}件")
            for _, r in hits.iterrows():
                print(f"    {r['date']:<12} {r['symbol']:<6} {r['name']:<24} {r[perf_col]*100:+8.1f}%")

    # === Section 2: 20BD × +100% を主軸として lift 分析 ===
    print("\n" + "="*78)
    print("🔬 Section 2: 20BD × +100% Mega Hit に対する Lift 分析")
    print("="*78)
    perf_col = "perf_20bd"
    threshold = 1.00
    confirmed = df[df[perf_col].apply(lambda v: isinstance(v,(int,float)) and math.isfinite(v))]
    mega_mask = (confirmed[perf_col] >= threshold)
    n_mega = int(mega_mask.sum())
    print(f"  Mega母集団: {n_mega}件 / 確定母数 {len(confirmed)}件 ({n_mega/max(len(confirmed),1)*100:.2f}%)")
    if n_mega < 2:
        print(f"  ⚠ +100%は{n_mega}件しかないため、閾値を +50% に下げて続行")
        threshold = 0.50
        mega_mask = (confirmed[perf_col] >= threshold)
        n_mega = int(mega_mask.sum())
        print(f"  Mega母集団 (+50%以上): {n_mega}件")

    # 全BOOL_CONDSのlift
    print(f"\n  全指標 lift ランキング (target={n_mega}件):")
    print(f"  {'指標':<20} {'lift':>5} {'target率':>8} {'全体率':>7}")
    print(f"  {'-'*20} {'-'*5} {'-'*8} {'-'*7}")
    lift_list = []
    for c in opt.BOOL_CONDS:
        if c not in confirmed.columns: continue
        lift, tr, ar_rate = compute_lift(confirmed, mega_mask, c)
        lift_list.append((lift, c, tr, ar_rate))
    lift_list.sort(reverse=True)
    for lift, c, tr, ar_rate in lift_list[:20]:
        print(f"  {c:<20} {lift:>5.2f} {tr*100:>7.1f}% {ar_rate*100:>6.1f}%")

    # === Section 3: アンカー選定 ===
    print("\n" + "="*78)
    print("⚓ Section 3: アンカー条件の選定")
    print("="*78)
    print(f"  固定アンカー: {FIXED_ANCHORS}")
    # 固定アンカー自体のlift確認
    for c in FIXED_ANCHORS:
        lift, tr, ar_rate = compute_lift(confirmed, mega_mask, c)
        flag = "✓" if lift >= ANCHOR_LIFT_MIN else "⚠"
        print(f"    {flag} {c}: lift {lift:.2f} (target {tr*100:.1f}% / all {ar_rate*100:.1f}%)")
    # 動的アンカー (ANCHOR_POOLからlift最大1個)
    anchor_pool_lifts = [(compute_lift(confirmed, mega_mask, c)[0], c)
                         for c in ANCHOR_POOL if c in confirmed.columns]
    anchor_pool_lifts.sort(reverse=True)
    print(f"\n  動的アンカー候補 (ANCHOR_POOL lift順):")
    for lift, c in anchor_pool_lifts[:5]:
        print(f"    {c:<20} lift {lift:.2f}")
    dyn_anchor = anchor_pool_lifts[0][1] if anchor_pool_lifts else None
    anchors = FIXED_ANCHORS + ([dyn_anchor] if dyn_anchor else [])
    print(f"  → アンカー確定 ({len(anchors)}個): {anchors}")

    # === Section 4: 発見プール (アンカー除外、lift上位8) ===
    print("\n" + "="*78)
    print(f"🔭 Section 4: 発見プール選定 (lift上位{DISCOVERY_POOL_SIZE}個, アンカー除外)")
    print("="*78)
    exclude = set(anchors)
    discovery_pool = []
    for lift, c, tr, ar_rate in lift_list:
        if c in exclude: continue
        if len(discovery_pool) >= DISCOVERY_POOL_SIZE: break
        discovery_pool.append((c, lift))
    print(f"  プール (size={len(discovery_pool)}):")
    for c, lift in discovery_pool:
        print(f"    {c:<20} lift {lift:.2f}")
    pool_names = [c for c, _ in discovery_pool]

    # === Section 5: C(8,3) 探索 ===
    print("\n" + "="*78)
    print(f"🧪 Section 5: 候補探索 C({len(pool_names)},{DISCOVERY_SLOTS}) = {len(list(combinations(pool_names,DISCOVERY_SLOTS)))}通り")
    print("="*78)
    # 評価関数: mega_recall × lift × min(n/5, 1)
    candidates = []
    for combo in combinations(pool_names, DISCOVERY_SLOTS):
        all_conds = anchors + list(combo)
        for c in all_conds:
            confirmed[c] = confirmed[c].astype(bool)
        sc = sum(confirmed[c].astype(int) for c in all_conds)
        s6 = confirmed[sc == len(all_conds)]
        n_hit = len(s6)
        if n_hit == 0: continue
        s6_mega = (s6[perf_col] >= threshold).sum()
        mega_recall = s6_mega / max(n_mega, 1)
        wr = (s6[perf_col] > 0).mean() if n_hit else 0
        avg = s6[perf_col].mean() if n_hit else 0
        # lift_mega = s6内のmega率 / 全体のmega率
        s6_mega_rate = s6_mega / max(n_hit, 1)
        all_mega_rate = n_mega / max(len(confirmed), 1)
        lift_mega = s6_mega_rate / max(all_mega_rate, 1e-9)
        score = mega_recall * lift_mega * min(n_hit/5, 1.0)
        candidates.append({
            "combo": all_conds, "discovered": combo,
            "n_hit": n_hit, "mega": int(s6_mega), "recall": mega_recall,
            "wr": wr, "avg": avg, "lift_mega": lift_mega, "score": score,
            "s6_df": s6,
        })
    candidates.sort(key=lambda x: -x["score"])

    # === Section 6: トップ候補表示 ===
    print(f"\n  上位10候補:")
    print(f"  {'#':<3} {'score':>6} {'件':>3} {'mega':>4} {'recall':>7} {'勝率':>5} {'平均':>7} {'lift':>5}  発見条件")
    print(f"  {'-'*3} {'-'*6} {'-'*3} {'-'*4} {'-'*7} {'-'*5} {'-'*7} {'-'*5}  {'-'*40}")
    for i, c in enumerate(candidates[:10], 1):
        print(f"  #{i:<2} {c['score']:>6.2f} {c['n_hit']:>3} {c['mega']:>4} {c['recall']*100:>6.1f}%"
              f" {c['wr']*100:>4.1f}% {c['avg']*100:>+6.1f}% {c['lift_mega']:>5.2f}  "
              f"{'+'.join(c['discovered'])}")

    # 品質ゲート通過候補
    quality_ok = [c for c in candidates if c['n_hit']>=N_HIT_MIN and c['mega']>=MEGA_N_MIN and c['lift_mega']>=LIFT_MIN]
    print(f"\n  品質ゲート通過: {len(quality_ok)}/{len(candidates)} (n>={N_HIT_MIN} AND mega>={MEGA_N_MIN} AND lift>={LIFT_MIN})")

    if not quality_ok:
        print("  ⚠ ゲート通過候補なし。設計再考が必要")
        return

    # === Section 7: ベスト候補の★6シグナル一覧 ===
    print("\n" + "="*78)
    print("🏆 Section 7: ベスト候補のシグナル一覧")
    print("="*78)
    best = quality_ok[0]
    print(f"  条件: {'+'.join(best['combo'])}")
    print(f"  ★6: {best['n_hit']}件 / Mega Hit {best['mega']}件 / Recall {best['recall']*100:.1f}%")
    print(f"  勝率 {best['wr']*100:.1f}% / 平均 {best['avg']*100:+.2f}% / lift_mega {best['lift_mega']:.2f}\n")
    s6 = best['s6_df'].sort_values("date", ascending=False)
    print(f"  {'日付':<12} {'銘柄':<6} {'社名':<24} {'5BD':>7} {'10BD':>7} {'20BD':>8}  Mega")
    for _, r in s6.iterrows():
        def fmt(v):
            return f"{v*100:+.1f}%" if isinstance(v,(int,float)) and math.isfinite(v) else "—"
        mega_flag = "🚀MEGA" if (isinstance(r[perf_col],(int,float)) and math.isfinite(r[perf_col]) and r[perf_col]>=threshold) else ""
        print(f"  {r['date']:<12} {r['symbol']:<6} {r['name']:<24} "
              f"{fmt(r.get('perf_5bd')):>7} {fmt(r.get('perf_10bd')):>7} {fmt(r.get('perf_20bd')):>8}  {mega_flag}")

    # 上位3候補も簡易表示
    print("\n" + "="*78)
    print("📋 上位3候補の比較サマリー")
    print("="*78)
    for i, c in enumerate(quality_ok[:3], 1):
        print(f"\n  ── 候補#{i} score={c['score']:.2f} ──")
        print(f"  条件: {'+'.join(c['combo'])}")
        print(f"  ★6:{c['n_hit']}件 mega:{c['mega']} recall:{c['recall']*100:.1f}% wr:{c['wr']*100:.1f}% avg:{c['avg']*100:+.1f}% lift:{c['lift_mega']:.2f}")
        s6_simple = c['s6_df'].sort_values(perf_col, ascending=False)
        for _, r in s6_simple.iterrows():
            p20 = r[perf_col]
            tag = "🚀" if (isinstance(p20,(int,float)) and math.isfinite(p20) and p20>=threshold) else "  "
            print(f"    {tag} {r['date']:<12} {r['symbol']:<6} {r['name']:<24} {p20*100:+8.1f}% (20BD)")

if __name__ == "__main__":
    main()
