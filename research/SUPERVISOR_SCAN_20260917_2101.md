# Supervisor scan — 2026-09-17 21:01 JST

Scope: P0 coordination only. 2026 remains SEALED. No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.

## Source of truth checked
- `research/AUTOMATION_COORDINATION_STATE.json`: still version 123 / 09:38 JST and therefore stale as a worker-result ledger.
- `research/RESEARCH_DASHBOARD.md`: updated 20:48 JST with the new anti-duplication worker allocation.
- latest substantive research commit known on the research branch: `d02eaef8cb680ca233053072ae7418eb1f3adc5c` at 17:46 JST, alternate-family forensic receipt.
- five active research automations inspected by last-run/update timestamp.

## Worker result classification since the 20:47-20:48 reallocation
- :12 2022 exact recovery — `NONE_YET_AFTER_REALLOCATION`: last run predates the new prompt; do not count as a failed optimized run.
- :24 new-rows endpoint audit — `NONE_YET_AFTER_REALLOCATION`: last run predates the new prompt; do not count as a failed optimized run.
- :36 comparison + Meta prep — `NONE_YET_AFTER_REALLOCATION`: last run predates the new prompt; do not count as a failed optimized run.
- :48 alternate-family rows normalization — `NONE x1`: one post-reallocation run observed, but no new SHA / trade rows / receipt / admissibility decision was visible at scan time.
- :00 supervisor — coordination only; heartbeat does not count toward research progress.

No worker has reached the `NONE x2` automatic reassignment threshold under the new optimized prompts yet. Therefore another immediate reassignment would be churn rather than optimization.

## Active independent P0 paths
1. Primary path: recover exact 2022-computable trade rows + generator/input SHA for the five primary candidates.
2. Alternate path: normalize `core_bollinger_reclaim` (or another already SOURCE_POOL_EXACT family) to canonical historical trade rows.
3. Non-blocking prep path: fill missing 2023-2025 comparison metrics / 100-share P&L and generate preregistered causal regime-label coverage without opening Meta performance.

## Blockers
- 2022 primary exact trade-row/generator chain is not yet pinned.
- `core_bollinger_reclaim` has deterministic source/pool provenance but not yet a normalized 2022-computable/2023/2024/2025 canonical trade-row chain.
- `strict_3pt` remains PARKED / REFERENCE_ONLY; no repeated search is authorized without new immutable evidence.

## Supervisor decision
Hold the new allocation for one full optimized cycle. At the next scan, any worker at `NONE x2`, repeating the same blocker, or re-running completed 2023-2025/OHLC work must be reassigned immediately to another executable P0 path. Do not increase the 84%/68% progress figures from this coordination receipt alone.
