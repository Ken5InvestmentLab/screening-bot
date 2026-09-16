# Research automation coordination

This branch is a research-only coordination channel for the staggered ChatGPT workers.

## Dashboard
- Human-readable status board: `research/RESEARCH_DASHBOARD.md`
- Machine-readable state: `research/AUTOMATION_COORDINATION_STATE.json`
- The :00 supervisor refreshes the dashboard every run.
- The :48 cross-lane/OSS worker also refreshes it whenever substantive state, candidate, Actions, backtest, or task status changes.

## Rules
- This is not a production branch.
- The coordination state is advisory/locking metadata, not a source of trading logic.
- Before processing a branch update, compare its actual current head SHA with `last_seen_sha` / `last_processed_sha`.
- If a substantive update is new, inspect its diff/log/Actions/artifacts, correct inconsistencies if needed, then continue the appropriate lane safely.
- After processing, update the state with the processed SHA and a short note.
- If another worker already processed the same SHA, do not repeat that work.
- Do not use this mechanism to touch production/main or production integrations.

## Core24 PIT forensic note
- Machine-readable PIT receipt is frozen at `research/tentei_cloud/CORE_JPX_PIT_MEMBERSHIP_RECEIPT_20260916.json` on `research/tentei-cloud-mtf`.
- Reverse replay `(2024-09-17, 2026-08-31]`: 476 events = listing134 + delisting261 + transfer81.
- Anchor 3,707 -> target 3,834, zero quarantine/conflict, membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.

## Core24 OHLCV completeness P0 (2026-09-16 09:24)
- P0 is now empirical missing-data enumeration, not provider-option speculation.
- Spec: `research/tentei_cloud/CORE_OHLCV_COMPLETENESS_AUDIT_SPEC_20260916.md`.
- Daily: use XTKS sessions + date-specific PIT membership and actual acquired raw rows; emit one missing row per symbol/date/O-H-L-C-V field. Pre-listing/post-delisting/no-activity are normal only when independently proven; unknown is fail-closed.
- This run did not establish a pinned exhaustive daily raw corpus covering the requested audit, so daily missing count is **unknown**, not zero.
- Exact-hour/activity remains SEALED until independent raw activity evidence is acquired. Membership×calendar×hour Cartesian expected rows are forbidden.
- Google Finance, Alpha Vantage, J-Quants, FLEX or Yahoo only receive completion credit for raw bytes/artifacts actually acquired and pinned; documentation or assumed availability is insufficient.
- Confirmed missing rows must be intersected with canonical trade entry/exit needs and 2022-2026 DUAL+G3 endpoints in a separate impact ledger.

## Cloud forensic
Cloud Monster exact model remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`. No model-family guessing without new exact evidence.
