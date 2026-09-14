# Supervisor Core24 reorder — 2026-09-15 08:02 JST

## Decision
Core24 remains active, but its next work is reordered so the lane does not idle on the independent exact-hour activity source blocker.

The current fail-closed contract is retained unchanged: membership + XTKS session + required clock hour does not prove a trade occurred in every hour, and the audited Yahoo raw1H bundle may not define its own expected activity. No Cartesian expected-key expansion, interpolation, daily-to-intraday synthesis, or performance recomputation is allowed.

## Immediate work order
1. Freeze the exact official-JPX point-in-time membership input/source receipts already identified by the Core lane. Record immutable source identity, bytes/hash, acquisition/provenance and the reconstruction rule used by the PIT implementation.
2. Freeze the adopted XTKS calendar CSV + manifest bytes on Core, including the existing 1,220-session calendar identity and SHA binding.
3. Only after steps 1-2 are pinned, continue the independent exact `(symbol, session_date, hour)` activity-evidence search.
4. If suitable independent activity evidence is found, preserve raw bytes/source semantics and then generate the expected-key CSV exactly once; otherwise leave formal missing inventory, supplementation adoption and performance closed.

## Worker allocation
The Core worker must not spend a whole cycle merely rechecking the activity-source blocker while steps 1-2 remain locally actionable. Consensus and EDINET remain external-wait lanes and likewise must not consume a full cycle without a new artifact/input.

No production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder or updater changes are authorized. New performance remains cost 0%, win = gross return > 0, and 2026 remains report/robustness-only.
