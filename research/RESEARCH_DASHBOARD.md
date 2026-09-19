# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-19 JST
> **最優先:** Cloud Monster legacy exact復元 + weak+early exact復元  
> **比較契約:** cost 0%、win = gross return > 0、signal T → next XTKS open → fifth XTKS close。  
> **重要:** 2026はMeta mapping SHA freeze + STATE明示許可までSEALED。production/mainは変更禁止。

## 現在地

**通常研究全体: 約90%** / **historical比較: 80%** / **Meta: 12%**。  
ただしユーザー指示により、通常P0を一時的に二次優先へ下げ、**Cloud Monster / weak+early exact復元を絶対最優先**へ切替。

## 今回の実成果

- Cloud Monsterの歴史的63行CSV、19行saved-score比較、最終Watch/ranker sourceを旧ChatGPT会話から回収し、commit `bb597947`でhash固定。
- `verify_recovered_rows.py`が n=63 / mean +9.8569% / median +3.3333% / win 57.1429% / +20 30.1587% / +30 19.0476% / -10 22.2222% / Top5-ex +4.0269%を独立再計算して全一致。
- 固定5候補を2026 reporting-onlyへ無調整延長。daily cutoff 2026-09-11、成熟済みsignal cutoff 2026-09-03。
- 2026単年はmean-rankがn=42 / mean +5.08% / median +1.38% / win 50.00% / Top3-ex +1.99%で最も均衡。
- Exact 2023-2026総合順位: 1 mean-rank、2 DUAL+G3、3 body_pct LOW、4 DUAL、5 volr20 LOW。
- 完全表: `research/repro_packs/weak_early_exact_v1/output/full_period_2026/FULL_PERIOD_COMPARISON_20260918.md`。
- `WEAK_EARLY_EXACT_V1`をPhase-2の5 selectorまで拡張し、DUAL n=140とDUAL+G3 n=117のcanonical rowsをexact固定。
- DUAL+G3は2023-2025でmean +7.98%、median +1.74%、win 53.85%、Top3-ex +5.14%を再現。
- outcome列を読まないresearch-only shadow selectorを追加し、5 selectorすべてでcanonical date+symbol identity一致を確認。
- `research/TVFREE_REPLACEMENT_READINESS_20260918.md`に、現行production scoringとのapples-to-apples比較へ進むための未完bridgeを固定。現時点は`FORWARD_SHADOW_READY / PRODUCTION NO-GO`。

- 復元専用ledgerを新規作成: `0527fd106f0c3c2c74156e4ef98a5f97073d2b4f`
  - `research/CLOUD_MONSTER_RECOVERY_LEDGER_20260918.md`
- weak+earlyの核を既存sourceから再確認:
  - branch `research/tvfree-canonical-batch02`
  - `tvfree_screener/research_20260912_core_monster.md`
  - blob `762b38e99d11866925abbdb47b5fd61854897120`
  - fixed gate: market `med_ret5 <= 0`
  - candidate `ret10 <= 0.5735294117647058`
  - population: preserved causal V7 Tail
- 同ファイルに2023-2024の `volr20 LOW` / `body_pct LOW` / `mean-rank(volr20, body_pct)` のranker成績が残っていることを確認。
- `EXPERIMENT_LEDGER.md` にV7/V9 source recipe、monthly causal training、matured labels before month start、minimum 30,000 rows等のweak+early再構築手掛かりを確認。
- 4 workerを重複しない復元laneへ全面再配分。

## Cloud Monster legacy

旧headline search signature:
- n=63
- mean +9.86%
- median +3.33%
- win 57.1%
- +20% 30.2%
- +30% 19.0%
- <=-10% 22.2%
- Top5-ex +4.03%

**状態:** `EXACT_REPRODUCED_FROM_RAW / CANONICAL_BRIDGE_COMPLETE`。artifact `10266329903` → base 4H frame → MTF → JPX +5-session relabel → final selectorを原文ソースで再実行し、63 row identity / close / ret5が最大差0.0で一致。固定63件のnext-open→fifth-close版も別identityで完成。headlineへ合わせるretuneは行っていない。

## weak+early

**`WEAK_EARLY_EXACT_V1 / EXACT_REPRODUCED`。** 2023-2025の5 selectorと2026 reporting-only延長を実行可能chain、canonical rows、SHA付きで固定済み。

## 担当割当

| Lane | 担当 | 成果条件 |
|---|---|---|
| :12 | Cloud Monster provenance復元 | branch/history/workflow artifact/code/specから旧generator/rowsを回収、各leadをSHA固定 |
| :24 | weak+early exact復元 | V7/V9→gate→rank/cooldown→rowsをidentity-levelで再現 |
| :36 | Cloud Monster artifact逆引き | n=63/+9.86 signatureからreports/CSV/JSON/Actions artifactを特定 |
| :48 | deterministic reproducer | 発見specを実行可能entrypointへ統合しrows SHA/metrics SHAを固定 |
| :00 | Supervisor | 重複探索/NONE×2を即再配分、recovery ledger/STATE/Dashboard更新 |

## REPRO_PACK完了条件

以下が全部揃うまで「復元完了」と呼ばない:
1. exact expression / threshold / tie-break / causal timing
2. source path + commit SHA
3. input artifact id/path + content SHA
4. exact command / entrypoint + args
5. canonical trade rows + rows SHA
6. evaluation contract + metrics SHA
7. identity name + version
8. A-Gを結ぶhandoff receipt

## 通常P0の扱い

primary historical / Meta freezeは**復元完了まで一時二次優先**。  
V16 alternate historical completeや既存primary exact成果は保持し、捨てない。復元完了後にそこから再開する。

## 最大blocker

Cloud Monster legacy exactとcanonical endpoint bridgeは完了。残る研究判断は、期間差を明示したforward shadowで現行productionとapples-to-apples比較すること。

## GO / NO-GO

**Cloud full-pipeline handoff ready / weak+early exact / production NO-GO。2026は固定候補のreporting-only以外SEALED。**
