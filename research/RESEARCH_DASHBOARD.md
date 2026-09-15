# TV-Free スコアリングBot研究ダッシュボード

> **最終更新:** 2026-09-15 20:24 JST  
> **比較契約:** 新規performanceは取引コスト0%、win = gross return > 0。canonical endpoint = next XTKS open -> fifth XTKS close。2026 outcomeはreport/robustness-only。

## ⏱ 自動研究ハートビート

Core :24は20:24に正常稼働。前回Supervisor監査でCanonical :12を再arm済み。task-level停滞とautomation heartbeatは分離する。

| Worker | 直近確認(JST) | 状態 |
|---|---:|---|
| Supervisor :00 | 18:58 | 🟢 GREEN / last supervisor scan |
| Canonical :12 | 19:11 | 🟠 rearm後の実run確認はSupervisor側継続 |
| Core :24 | 20:24 | 🟢 GREEN / current run |
| Consensus :36 | 19:36 | 🟢 GREEN |
| OSS+Parallel :48 | 19:48 | 🟢 GREEN |

## 👤 ユーザー作業待ち

**現在0件。** worker側で継続可能。

## 📈 全体進捗

**研究全体の進捗率: 約78%**

| タスク | 状態 | 進捗 | 現在地 / 完了条件 |
|---|---|---:|---|
| Weak+Early Phase-2 frozen検証 | ⚫ CLOSED | 100% | 2022 fresh robustness FAIL、retune禁止、Round2 CLOSED |
| Parallel Wave-1 | 🔴 STALE / P0 | 72% | causal A1/B1/E1 pick ledger SHA固定 → completeness receipt → one-shot cost0 |
| Core24 OHLCV補完 | 🟢 稼働中 | 80% | JPX exact-byte capture harnessをresearch branchへ追加。Action/artifact成功確認 → deterministic membership receipt → independent exact-hour activity evidence |
| Consensus V47 | 🟠 transport STALE / reuse監査へ再配分 | 67% | raw=0。Core24 SHA-pinned raw1H互換性をoutcome-blind監査 |
| Canonical/Shadow endpoint integrity | 🟠 worker再arm | 88% | research state active。再arm後の実run復帰確認後outcome-blind integrity継続 |
| Core endpoint provenance | 🟢 稼働中 | 92% | official JPX 6-source URL map + byte-preserving capture tool/workflow固定。成功artifactのSHA receipt確認が残り |
| Cloud Monster exact forensic | ⚫ CLOSED | 100% | HISTORICAL_EXACT_REPRO_UNAVAILABLE |
| OSS / Validation | 🟢 disposition policy固定 | 98% | same-ZIP 44 comparable / 17 all-match / 27 findings / 4 unavailable。未解決はfail-closed、performanceでparser/value選択禁止 |
| V20 Session-Impulse | ⚫ CLOSED / deprioritized | 100% | active queue外 |

## Core :24 今回の前進

前回までのblockerは、automation containerからJPX公式ページのexact bytesを直接取得できないnetwork/DNS transportだった。今回はproductionを触らず、`research/tentei-cloud-mtf` に研究専用の `capture_jpx_pit_sources.py` と `tentei-cloud-core-jpx-pit-source-capture` workflowを追加した。6本の公式JPX current/2025/2024 listing/delisting sourceをbyte-preservingに保存し、URL・final URL・HTTP status・byte size・SHA-256・取得時刻をreceiptへ記録してActions artifact化する契約。

workflowの存在だけではPIT PASSにしない。SUCCESS artifactと6-source receiptを実確認して初めて次のdeterministic event ledger / conflict quarantine / membership receiptへ進む。Cartesianなhourly expected universeは禁止継続。Cloud exact forensicもCLOSED継続。

## Frozen comparator（変更なし）

DUAL+G3: 2023-25 n=117 / mean +7.98% / median +1.74% / win 53.85% / Top3-ex +5.14%。2022 fresh robustness FAIL固定、retune禁止。

## 残タスク

P0: Core24 JPX capture Action/artifact確認 → six-source SHA receipt固定 → deterministic PIT membership receipt。Parallel causal pick ledger。  
P1: Core independent exact-hour activity evidence、OSS/EDINET source-grounded taxonomy、Consensus Core24 raw1H互換性監査、Canonical outcome-blind integrity。  
CLOSED: Weak+Early Phase-2、Cloud exact forensic、V20。

## GO / NO-GO

**NO-GO / 研究継続。GO候補0件。** production/main、本番workflow、Discord、Spreadsheet、Stable★6、Sniper、Mega、TradingView、watchlist-builder/updaterは変更しない。
