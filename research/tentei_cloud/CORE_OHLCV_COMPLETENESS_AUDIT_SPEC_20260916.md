# Core OHLCV completeness audit — fail-closed contract (2026-09-16)

## Scope
Research-only Core24 evidence. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes.

## Required ledgers
1. `daily_expected.csv`: XTKS session × point-in-time JPX membership only. Never current-universe backfill.
2. `daily_observed.csv`: rows actually present in acquired raw source evidence.
3. `daily_missing.csv`: one row per `symbol,date,field` for O/H/L/C/V with classification.
4. `hourly_activity_observed.csv`: independently witnessed actual trading activity only; membership×calendar×hour Cartesian products are forbidden.
5. `hourly_missing.csv`: only against independently witnessed expected activity.
6. `trade_impact.csv`: missing observations intersecting canonical trade entry/exit requirements; DUAL+G3 2022-2026 endpoint impacts separately tagged.
7. `receipt.json`: counts, hashes, source lineage, parser versions and fail-closed status.

## Classification
`TRUE_MISSING`, `NORMAL_PRE_LISTING`, `NORMAL_POST_DELISTING`, `NORMAL_NO_ACTIVITY_PROVEN`, `UNKNOWN_FAIL_CLOSED`.
Trading halt/suspension is normal only when independent dated evidence proves no expected observation; otherwise UNKNOWN.

## Source policy
A source is `AVAILABLE_FOR_COMPLETION` only if its raw bytes/artifact and provenance are already acquired and pinned. Yahoo/Google Finance/Alpha Vantage/J-Quants/FLEX must never be marked as filled from documentation, assumed availability, or a successful endpoint probe alone.

## Metrics
Receipt must report expected targets, complete targets, true missing targets, unknown targets, symbol-date-field ledger, yearly/monthly counts, acquired-source completion matrix, trade-impact count, and DUAL+G3 2022-2026 endpoint impact table.

## Current gate
PIT membership receipt is available, but independent exact-hour activity raw evidence remains unacquired. Therefore hourly expected/completeness counts remain SEALED rather than fabricated. Daily audit may proceed only from actual acquired daily raw artifacts plus XTKS/PIT evidence. If the repository/action artifacts do not contain those raw daily bytes, status must be `DAILY_RAW_EVIDENCE_NOT_ACQUIRED` and no zero-missing claim is permitted.
