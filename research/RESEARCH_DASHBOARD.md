# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 16:47 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 16:17 JST  
> 5本すべて **ENABLED**。Consensusは再arm後 **16:11に実run復帰**。Coreは16:24、Supervisorは17:00の再arm確認待ち。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 14:58 | 🟠 遅延疑い・再arm、次回17:00 |
| Canonical :12 | 15:14 | 🟢 90分以内 |
| Core :24 | 14:22 | 🔴 停止疑い継続、再arm、次回16:24 |
| Consensus :36 | 16:11 | 🟢 再arm後に実run復帰 |
| OSS+Parallel :48 | 16:06 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。
### ⚠️ 16:10 自動実行ギャップ検知

ダッシュボードの見た目だけでなくautomationの実`last_run_time`を確認したところ、Coreは14:22、Consensusは14:36から次runがなく、16:09時点で90分閾値を超えていた。Supervisorも14:58以降の次slotが欠落。**Core 16:24 / Consensus 16:36 / Supervisor 17:00** をAsia/Tokyo明示で再armした。Canonicalは15:14、OSS+Parallelは16:06に実runあり。次3slotの実行有無をheartbeatで再確認し、再度欠落する場合はscheduler-level faultとして手動前進/再配分する。


## 👤 ユーザー作業待ち

**現在0件。** EDINET_API_KEYは設定・疎通確認済み。Parallel/Consensus/EDINET repair/Core24/Canonicalはいずれもworker側または外部transport/data取得側の課題で、ユーザー操作は不要。新しいSecret・API key・手動ファイル提供などが必須になった場合だけここを「要対応」に変更する。

## 📈 全体進捗

**研究全体の進捗率: 約74%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 75% | official JPX PIT source route特定済み。exact input bytes/SHA pin → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | formal raw1H run `34849054884` はusable raw=0。単純待機は打切り、V47 frozen inventoryとCore24 SHA-pinned raw1H互換性をoutcome-blind監査。duplicate retry・threshold緩和禁止 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 88% | `90f56dcd…` processed済み。resolution receipt + cross-run chainをresolved書込み前にdurable化。CI `34943418395` PASS |
| Core endpoint provenance | 🟢 稼働中 | 87% | JPX source route確認済み。byte-pinned PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。新しいidentity-critical一次証拠時のみ再開 |
| OSS / Validation | 🟢 手動前進・再実行中 | 90% | retry `34936903153` はAPI取得成功後、repeat `doc_id` でFAILしていた。2023-2025実artifactをoutcome-blind監査し、1,017 repeated doc IDs / 2,056 observationsを確認。120/130に触れる7件は全て120→120・同一submitDateTime。sample-safe repeatのみreceipt付き許可し、conflictはfail-closed。OSS test `34940882491` とfull freeze `34940882530` 実行中 |
| V20 Session-Impulse | ⚫ CLOSED / deprioritized | 100% | active queueから除外 |

## Weak+Early Phase-2 frozen ranking

| Rank | Candidate | n | Mean | Median | Win | Top3-ex | Status |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | **DUAL + G3** | 117 | **+7.98%** | **+1.74%** | **53.85%** | **+5.14%** | frozen comparator / 2022 fresh robustness FAIL |
| 2 | DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% | frozen |
| 3 | mean-rank(volr20,body_pct) | 172 | +6.89% | +1.45% | 52.33% | +4.95% | frozen baseline |
| 4 | body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% | frozen baseline |
| 5 | volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% | frozen baseline |

G3 = `med_ret1 >= -1%` は**凍結維持**。2022 fresh validationは**FAILED ROBUSTNESS**として固定し、surrogate/retune禁止。Regime Round2は**CLOSEDのまま再開しない**。

## 今回のSupervisor前進

**16:17 JSTに手動one-shotを実行。** EDINET retry `34936903153` は15:35 JSTに既にFAILしており、原因はAPIではなくrepeated `doc_id` だった。exact 2023-2025 artifactsをoutcome-blind監査した結果、normalized non-inert 216,094 rows中、**1,017 doc IDs / 2,056 observations**が重複。全repeatでsubmitDateTimeは一致し、pre-registered docType 120/130に触れるrepeatは**7件すべて120→120**でsample membershipに曖昧性なし。56件のdocType変更repeatは全て120/130外。

そのため全重複を雑に削除せず、sample-safe repeatをreceipt付きで保持し、submitDateTime conflictまたは120/130を含むdocType conflictだけfail-closedとする最小修正を入れた。implementation `e05a1771…`、tests `43fcdaa2…`、audit `dd1cd33d…`。現在 OSS validation `34940882491` と full EDINET freeze `34940882530` が実行中。

automation側ではConsensusが再arm後16:11に実run復帰。Core 16:24 / Supervisor 17:00は引き続き実run確認対象。

### Canonical/Shadow 16:47 JST前進

cross-run resolution chainを**実際のresolved write boundaryへ強制配線**した。既存chainを検証し、staged resolved bytesに対するresolution receiptと次chain linkを作成・全chain検証したうえで、receipt + chain linkを先にdurable保存できた場合だけ `staged.replace(resolved)` を許可する。既存chain tailと現在resolved SHAが一致しない場合、chain tamper、sidecar persistence errorはいずれもresolved履歴を変更せずfail-closed。最終Canonical HEAD `90f56dcd…`、最終contract CI `34943418395` **SUCCESS**。performance/H1/H2/2026 outcomeは新規開封なし。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET `34940882491` / `34940882530` terminal監査→sample receipt/selected ZIP SHA固定、Core24 official-JPX exact bytes/SHA pin。  
P1: Canonicalはdurable prewrite chain後のcrash/orphan recovery semanticsをoutcome-blind監査、Consensus Core24 raw1H互換性監査。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
