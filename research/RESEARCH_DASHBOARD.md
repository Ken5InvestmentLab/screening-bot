# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 15:26 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

> **確認時刻:** 2026-09-15 15:26 JST  
> 5本すべて **ENABLED**、90分超の停止疑い **0本**。

| Worker | 直近実行(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 14:58 | 🟢 GREEN |
| Canonical :12 | 15:14 | 🟢 GREEN |
| Core :24 | 14:22 | 🟢 GREEN（90分以内） |
| Consensus :36 | 14:36 | 🟢 GREEN |
| OSS+Parallel :48 | 14:48 | 🟢 GREEN |

GitHub最終commit時刻だけでは停止判定しない。task-level停滞とautomation heartbeatは分離する。

## 👤 ユーザー作業待ち

**現在0件。** EDINET_API_KEYは設定・疎通確認済み。Parallel/Consensus/EDINET repair/Core24/Canonicalはいずれもworker側または外部transport/data取得側の課題で、ユーザー操作は不要。新しいSecret・API key・手動ファイル提供などが必須になった場合だけここを「要対応」に変更する。

## 📈 全体進捗

**研究全体の進捗率: 約73%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 75% | official JPX PIT source route特定済み。exact input bytes/SHA pin → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | formal raw1H run `34849054884` はusable raw=0。単純待機は打切り、V47 frozen inventoryとCore24 SHA-pinned raw1H互換性をoutcome-blind監査。duplicate retry・threshold緩和禁止 |
| Canonical/Shadow endpoint integrity | 🟢 稼働中 | 84% | `fe0e89c5…` processed済み。cross-run shadow receipt chain guard CI `34902927347` PASS |
| Core endpoint provenance | 🟢 稼働中 | 87% | JPX source route確認済み。byte-pinned PIT receiptとexact-hour activity sourceが残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | `HISTORICAL_EXACT_REPRO_UNAVAILABLE`。新しいidentity-critical一次証拠時のみ再開 |
| OSS / Validation | 🟢 EDINET再実行中 | 88% | 第2null形を実rawで特定しfixture化。`docTypeCode=null + disclosureStatus=0 + 全content/legal flag=0` のinert rowだけ最小除外、他はfail-closed維持。OSS test `34936903249` PASS、full freeze retry `34936903153` 実行中 |
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

OSS/EDINETを実際に1段階進めた。run `34922234308` の2023 artifact（ID `10378661856`）から第2の失敗行を直接監査し、`2023-01-10 result[292]` / docID `S100PXGH` が **docTypeCode=nullだがsubmitDateTimeは保持**されたinert document-list rowであることを固定した。2023全artifactをoutcome-blindに走査すると、この系統は計 **32,935 rows**（timestampなし32,904 / timestamp保持31）だった。

修正は広範なnull無視ではなく、`docTypeCode=null` かつ `disclosureStatus=0` かつXBRL/PDF/添付/英語/CSV/legalの全flag=0だけを除外する最小predicate。その他の欠損はfail-closedのまま。実raw fixture commit `90265c5e…`、監査記録 `00df55b8…` を固定し、OSS test run `34936903249` は **PASS**。2023-2025 full metadata freeze retry `34936903153` を実行中。

他active laneはprocessed済みHEADの重複処理なし。Consensus Yahoo待ちはSTALE/reuse監査、ParallelはSTALE/P0を維持。Phase-2順位・G3・2022 fresh FAIL・Round2 CLOSEDは変更なし。

## 残タスク

P0: Parallel causal pick ledger、OSS/EDINET full freeze retry `34936903153` のterminal監査→sample receipt/selected ZIP SHA固定、Core24 official-JPX exact bytes/SHA pin。  
P1: Canonical次のoutcome-blind shadow integrity、Consensus Core24 raw1H互換性監査。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
