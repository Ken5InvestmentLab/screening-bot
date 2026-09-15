# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 23:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 23:24 JST  
> Core :24 は正常進行。前回Supervisor監査で再armしたOSS+Parallel :48は23:48 actual run要確認。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 22:02 | 🟢 GREEN |
| Canonical :12 | 22:10 | 🟢 GREEN |
| Core :24 | 23:24 | 🟢 GREEN / JPX parser contract frozen |
| Consensus :36 | 22:38 | 🟢 GREEN |
| OSS+Parallel :48 | 22:46 | 🟠 再arm済み、23:48 actual run待ち |

## 📈 全体進捗

**研究全体の進捗率: 約81%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / worker再arm | 72% | causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 88% | JPX `data_e.xlsx` exact bytes/SHA + header/effective date + eligibility parser固定済み → 375-event reverse replay → PIT receipt |
| Consensus V47 | 🟢 corrected H1 diagnostic完了 / formal raw BLOCKED | 78% | CAP1000_PITのみcorrected H2 prereg/repair |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 89% | outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 parser contract PASS | 98% | anchor 2026-08-31、eligible domestic individual equities 3,707。次はPIT membership receipt |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟠 worker再arm / policy固定 | 98% | 27 findings source-grounded taxonomy。unresolvedはfail-closed |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Core24 今回の前進
Actions run `34974864648` / artifact `10398473275` のimmutable `data_e.xlsx` を直接検査。227,579 bytes / SHA-256 `4d10497c2aa03bcca0b92f0673d3ab19ecc6aca6a9c9a70a3e19cd490f1d8754`。Workbookは1 sheet / 4,442 rows incl. header / 10 columns。`Effective Date` は `20260831` で、parserは全non-empty rowで単一日付を要求するfail-closed契約に固定。

国内個別株anchor eligibilityもexact labelで固定：Prime 1,556 + Standard 1,555 + Growth 596 = **3,707**。ETF/ETN、PRO、REIT等、Foreign、Equity Contribution Securities、unknown labelは除外/quarantine。2022 correction workbookは引き続きexcluded。

Core branchはparser spec / log / handoffを更新しHEAD `5ea40f52e6bd967406446ebc2574d6c06628a71b`。次は凍結済み375-event ledgerを2026-08-31から2024-09-17へdeterministic reverse replayし、conflict quarantineとmembership SHA/receiptを固定する。membershipだけからhourly expected keysは生成しない。

## Frozen comparator
DUAL+G3 (`med_ret1 >= -1%`) は n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh robustness FAIL固定、surrogate/retune禁止、Regime Round2 CLOSED。

## Cloud forensic
旧Cloud Monster exact modelは `HISTORICAL_EXACT_REPRO_UNAVAILABLE` の結論維持。新証拠なし、model-family guessing/retuneなし。

## Guardrails
production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。新規performanceはcost 0%のみ、win=gross return>0。2026はreport/robustness-only。

## GO / NO-GO
**NO-GO / 研究継続。GO候補0件。**
