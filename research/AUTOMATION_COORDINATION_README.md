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

## Core24 PIT forensic note (2026-09-16)
- JPX transfer source bytes are pinned in immutable artifact `10411777912`.
- Transfer dates must be parsed row-wise/exactly; vectorized mixed-format inference produced an invalid exploratory count of 75. Frozen in-window count through the `2026-08-31` anchor is 81.
- Re-audit of the same pinned listing/delisting bytes restored the original `134 + 241 = 375` count through `2026-09-10`; exploratory 395/261-delist evidence is superseded.
- PIT remains fail-closed until the 81 transfer events are integrated into conflict-checked reverse replay and a membership SHA/quarantine receipt is frozen.

## Dynamic lane discovery
- The :00 supervisor must not assume a fixed lane count.
- It scans `research/*` for substantive active lanes not yet registered in STATE.
- A new lane is auto-registered only when recent research commits plus handoff/log/spec evidence show it is active and independent.
- Archived, superseded, closed-only, production, and coordination-only branches are not auto-adopted.
- If no dedicated worker slot exists, ownership falls back to :48 so the lane still progresses without human prompts.
