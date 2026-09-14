# WEAK+EARLY Phase 2 Regime Gate Preregistration — 2026-09-14

目的: DUAL_TOP1_AGREEMENTの勝率を上げつつ、平均5BD >= +6%、Top3-ex >= +4%を可能な限り維持する。

共通:
- transaction cost = 0%
- win = gross return > 0
- endpoint = next XTKS open -> fifth XTKS close
- base = frozen DUAL_TOP1_AGREEMENT
- 2026 outcomeは選択に使わない
- threshold grid search禁止
- ここに書いた4 gate以外を、結果を見て同一runで追加しない

Preregistered semantic gates:
G1 TREND_SUPPORT:
- previous-session breadth_ma20 >= 0.50
- 「市場の過半が20日線上」

G2 NO_PANIC_DAY:
- previous-session breadth_ret1_pos >= 0.40
- 「前日上昇銘柄比率が40%未満の急激な全面安を避ける」

G3 NO_ACUTE_SELLOFF:
- previous-session med_ret1 >= -0.01
- 「市場中央値の1日騰落が-1%未満の急落日を避ける」

G4 TREND_AND_NO_PANIC:
- G1 AND G2
- 単純な2条件ANDのみ。weight/score化しない。

判定順:
1. 2023-2024で各gateをDUAL_TOP1_AGREEMENTに固定適用。
2. Discovery合格候補は mean >= +6%, win >= 55%, Top3-ex >= +4%, n >= 60 を目安とする。
3. 合格が複数なら win優先、次にTop3-ex、次にmean、次にn。
4. 選んだgateだけを2025へ無調整で確認。
5. 2025で win >= 50%, mean > 0%, n >= 15 を最低確認ラインとする。
6. 2025を見てthreshold変更・gate追加・組合せ追加は禁止。
