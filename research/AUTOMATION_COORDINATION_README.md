# Research automation coordination

This branch is a research-only coordination channel for the staggered ChatGPT workers.

## Dashboard
- Human-readable status board: `research/RESEARCH_DASHBOARD.md`
- Machine-readable state: `research/AUTOMATION_COORDINATION_STATE.json`
- The :00 supervisor refreshes the dashboard every run.
- The :48 cross-lane/OSS worker also refreshes it whenever substantive state, candidate, Actions, backtest, or task status changes.

## Why
Native scheduled tasks can run at most once per hour per task. Five research workers are therefore staggered at :00, :12, :24, :36 and :48 JST. Every worker first scans all active research branches and this shared state, so substantive GitHub updates can normally be noticed within about 12 minutes rather than waiting up to an hour for a lane-specific worker.

## Worker roles
- :00 — cross-lane supervisor
- :12 — Canonical Batch02 / Event + Shadow/Data preferred worker
- :24 — Core breadth/stability preferred worker
- :36 — Consensus specialist preferred worker
- :48 — cross-lane follow-up / result collector + OSS/Validation + fallback owner for newly discovered unowned active research lanes

## Rules
- This is not a production branch.
- The coordination state is advisory/locking metadata, not a source of trading logic.
- Before processing a branch update, compare its actual current head SHA with `last_seen_sha` / `last_processed_sha`.
- If a substantive update is new, inspect its diff/log/Actions/artifacts, correct inconsistencies if needed, then continue the appropriate lane safely.
- After processing, update the state with the processed SHA and a short note.
- If another worker already processed the same SHA, do not repeat that work.
- Prefer the worker's assigned lane when there is no cross-lane GitHub update waiting.
- The :48 worker fills gaps such as completed-but-uncollected Actions/artifacts or work left waiting by another worker.
- Do not use this mechanism to touch production/main or production integrations.

## Core24 PIT forensic note (2026-09-16 05:23)
- JPX source bytes are pinned in immutable artifact `10411777912`.
- Dates must be parsed row-wise with both `%b. %d, %Y` and `%b %d, %Y`; JPX writes `May` without a period. Unknown non-empty dates fail closed.
- Prior `375 = 134 + 241` is superseded: corrected through 2026-09-10 is `397 = 134 listings + 263 delistings`.
- Reverse replay `(2024-09-17, 2026-08-31]` uses `134 listings + 261 delistings + 81 transfers = 476` events.
- From anchor 3,707, strict replay produced target 3,834 with zero quarantine/conflict; sorted membership SHA-256 `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.
- Next: freeze machine-readable PIT receipt, then independent exact-hour activity evidence. Do not derive expected hourly keys from membership alone.

## Dynamic lane discovery
- The :00 supervisor must not assume a fixed lane count.
- It scans `research/*` for substantive active lanes not yet registered in STATE.
- A new lane is auto-registered only when recent research commits plus handoff/log/spec evidence show it is active and independent.
- Archived, superseded, closed-only, production, and coordination-only branches are not auto-adopted.
- If no dedicated worker slot exists, ownership falls back to :48 so the lane still progresses without human prompts.
