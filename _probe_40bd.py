#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""40BDデータ蓄積状況の診断（読み取り専用・本番に一切触れない）"""
import math
import numpy as np
import pandas as pd
import optimize_screener as opt

svc = opt.get_service()
ar = opt.fetch(svc, "alerts_raw")
try:
    sa = opt.fetch(svc, "signals_archive")
except Exception as e:
    sa = []
    print("signals_archive 取得失敗:", e)
oh = opt.fetch(svc, "ohlcv_4h")
print(f"行数: alerts_raw={len(ar)} / signals_archive={len(sa)} / ohlcv_4h={len(oh)}")

# 確定済み + 未確定すべて
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

print(f"\nBOTTOM総数(確定+未確定, dedup後): {len(allsig)}件")
for col in ["perf_5bd", "perf_10bd", "perf_20bd", "perf_40bd"]:
    n_conf = allsig[col].notna().sum()
    print(f"  {col} 確定: {n_conf}件")

# perf_40bd 分布
p40 = allsig["perf_40bd"].dropna()
print(f"\n=== perf_40bd 確定 {len(p40)}件 の分布 ===")
if len(p40) > 0:
    print(f"  平均: {p40.mean()*100:+.1f}%  中央値: {p40.median()*100:+.1f}%  最大: {p40.max()*100:+.1f}%  最小: {p40.min()*100:+.1f}%")
    for th in [0.20, 0.30, 0.50, 1.00]:
        c = (p40 >= th).sum()
        print(f"  +{th*100:.0f}%以上: {c}件 ({c/len(p40)*100:.1f}%)")

# 日付レンジ
dts = pd.to_datetime(allsig["date"], errors="coerce")
print(f"\n日付レンジ: {dts.min()} 〜 {dts.max()}")

# 確定の定義別カウント
conf40 = allsig[allsig["perf_40bd"].notna()]
unconf40 = allsig[allsig["perf_40bd"].isna()]
print(f"\n40BD確定: {len(conf40)}件 / 40BD未確定: {len(unconf40)}件")

# OHLCV カバレッジ
ohlcv = opt.parse_ohlcv(oh)
print(f"OHLCV銘柄数: {len(ohlcv)}")
# 特徴量が計算できる確定40BD件数
ok = 0
for _, r in conf40.iterrows():
    f = opt.get_features(ohlcv.get(r["symbol"], []), r["date"])
    if f:
        ok += 1
print(f"40BD確定のうち特徴量計算可能: {ok}件")
