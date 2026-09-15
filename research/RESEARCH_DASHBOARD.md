# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 21:00 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## 📈 全体進捗

**研究全体の進捗率: 約79%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、surrogate/retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0再指示 | 72% | actual HEADを `57d28537…` へreconcile。既処理XTKS forensicを繰り返さず causal A1/B1/E1 pick ledger → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 82% | JPX exact-byte capture PASS。6-source deterministic event ledger → conflict quarantine → PIT membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査 | 67% | Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟢 再arm確認済み | 89% | 20:12 actual run確認。outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 94% | JPX 6-source exact bytes/SHA固定済み。membership ledger/receiptが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 disposition policy固定 | 98% | unresolved findingsはfail-closed、performanceでparser/value選択禁止 |
| V20 Session-Impulse | ⚫ CLOSED | 100% | active queue外 |

## Weak+Early Phase-2 frozen status

順位は変更なし。

1. **DUAL_TOP1_AGREEMENT** — n140 / mean +7.17% / median +1.25% / win 52.14% / Top3-ex +4.79%
2. **mean-rank(volr20, body_pct)** — n172 / mean +6.89% / median +1.45% / win 52.33% / Top3-ex +4.95%
3. **body_pct LOW** — n172 / mean +6.54% / median +0.99% / win 50.58% / Top3-ex +4.60%
4. **volr20 LOW** — n172 / mean +6.33% / median +1.06% / win 51.74% / Top3-ex +4.38%

Frozen G3 `NO_ACUTE_SELLOFF = med_ret1 >= -1%` は 2023-2025 total **n117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%**。-1% thresholdはretune禁止。2022 fresh validationは **ROBUSTNESS FAIL** 固定、2022 surrogate禁止。Regime Round2は **CLOSED / 再開禁止**。

## 今回のSupervisor前進

STATEに記録されていたParallel HEAD `858998cc…` と実GitHub HEADが一致していないことを検出。実HEADは `57d285370898b13ee93e7cb941667e2550ac6950`（outcome-blind XTKS calendar forensic）で、19:45 JST以降の新commitは0件だった。古いSHAを再処理せず、実HEADをprocessed pointerへreconcileし、**次actionを「既処理forensicの再確認ではなく、returnsを開かず causal A1/B1/E1 pick ledgerをfreeze → completeness receipt」へ再明示**した。Parallel自体は引き続き🔴 STALE扱い。

Canonicalは前回の再arm後、20:12 actual runを確認できたため停止疑いを解除。Core/Consensus/OSS+Parallelも直近1時間内にactual runあり。

## 自動研究ハートビート

> **確認時刻:** 2026-09-15 21:00 JST  
> 5本すべて **ENABLED**。予定時刻から90分超の停止疑い **0本**。

| Worker | 直近実run (JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 20:59 | 🟢 current run |
| Canonical :12 | 20:12 | 🟢 再arm復帰確認済み |
| Core :24 | 20:27 | 🟢 GREEN |
| Consensus :36 | 20:39 | 🟢 GREEN |
| OSS+Parallel :48 | 20:45 | 🟢 GREEN |

※ automation heartbeatのGREENとlane taskのSTALEは別概念。ParallelとConsensusのtask-level停滞は継続監視する。

## 残タスク

P0は、Core24の6-source JPX event ledger/conflict quarantine/PIT membership receipt、Parallelのcausal pick ledger freeze/completeness receipt、ConsensusのCore24 raw1H compatibility audit。OSSは27 findingsのsource-grounded taxonomy、Canonicalはoutcome-blind integrityを継続。V47は実rawが得られた場合のみfrozen contractで0% diagnosticを追加する。

production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更なし。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。**
