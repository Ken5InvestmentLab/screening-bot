# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 22:59 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 22:59 JST  
> heartbeat実監査で **OSS+Parallel :48 が無効化されていた**ことを検知。23:48からhourly exactで再arm済み。現在5本すべてENABLED、90分超停止疑い0本。次回23:48のactual runを要確認。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 22:02 | 🟢 GREEN / current supervisor cycle |
| Canonical :12 | 22:10 | 🟢 GREEN |
| Core :24 | 22:26 | 🟢 GREEN |
| Consensus :36 | 22:38 | 🟢 GREEN |
| OSS+Parallel :48 | 22:46 | 🟠 無効化を検知→再arm、次回23:48 |

GitHub commit時刻だけでは停止判定しない。automation actual enabled/last_runを毎回監査する。

## 📈 全体進捗

**研究全体の進捗率: 約81%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / worker再arm | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 87% | official JPX current `data_e.xlsx` exact bytes/SHA固定済み → header/effective month-end → parser contract → 375-event reverse replay → PIT receipt |
| Consensus V47 | 🟢 corrected H1 diagnostic完了 / formal raw BLOCKED | 78% | CAP1000_PITがdiagnostic leader。次はCAP1000_PITのみcorrected H2 prereg/repair |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 current anchor byte-pin PASS | 97% | `data_e.xlsx` 227,579 bytes / SHA-256 `4d10497c…d8754`。次はworkbook header/effective month-endとPIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟠 worker再arm / policy固定 | 98% | 27 findings source-grounded taxonomy。unresolvedはfail-closed |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Frozen comparator
DUAL+G3 (`med_ret1 >= -1%`) は n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh robustness FAIL固定、surrogate/retune禁止、Regime Round2 CLOSED。

## 今回のSupervisor前進
CoreのSTATE pointerが実HEADより遅れていたため回収。corrected JPX anchor capture run `34974864648` はSUCCESS。公式publication pageから発見した current `data_e.xlsx` を **227,579 bytes / SHA-256 `4d10497c2aa03bcca0b92f0673d3ab19ecc6aca6a9c9a70a3e19cd490f1d8754`** として固定。artifact `10398473275`、digest `sha256:b788cabf1a82706ea3be9925f96b6d9ef5133bcf7776f8bbe769c86e5b194516`。2022 correction workbook `jyoujyou(updated)_e.xlsx` は引き続きexcluded evidenceでPIT anchorには使わない。

同時にheartbeat監査でOSS+Parallel :48が実際にはdisabledだったことを検知し、23:48から再arm。これによりParallelのSTALE P0とOSS taxonomyを既存5本体制のまま再開する。

## Consensus V47
corrected H1 run `34943802848` はSUCCESS、cost 0%、2025-01-06..2025-06-30、next XTKS open → D+5 close。NOCAP n43 mean+1.38% win39.53%、CAP1000_PIT n41 mean+1.71% win43.90%。CAP1000_PITがdiagnostic leaderだがpromotion evidenceではなくformal raw acceptance未PASS。次は同一contractでCAP1000_PITのみcorrected H2。

## STALE / blocked / closed
Parallel Wave-1はcausal pick ledger未生成のため🔴STALE。Consensus formal rawはBLOCKED。Weak+Early、Regime Round2、Cloud exact forensic、V20はCLOSED。OSS workerは無効化を検知したが再arm済み。

## 残タスク
P0: Core24 `data_e.xlsx` header/effective month-end確認→parser/eligibility freeze→375-event reverse replay→PIT receipt、Consensus corrected H2 prereg/repair、Parallel causal A1/B1/E1 pick ledger。P1: OSS/EDINET taxonomy、Canonical outcome-blind integrity。heartbeatは23:48 OSS+Parallel actual runを確認。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
