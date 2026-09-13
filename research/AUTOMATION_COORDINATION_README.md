# Research automation coordination

This branch is a research-only coordination channel for the staggered ChatGPT workers.

## Why
Native scheduled tasks can run at most once per hour. Four research workers are therefore staggered at :00, :15, :30 and :45 JST. Every worker first scans all active research branches and this shared state, so substantive GitHub updates can be noticed within about 15 minutes rather than waiting up to an hour for a lane-specific worker.

## Rules
- This is not a production branch.
- The coordination state is advisory/locking metadata, not a source of trading logic.
- Before processing a branch update, compare its actual current head SHA with `last_seen_sha` / `last_processed_sha`.
- If a substantive update is new, inspect its diff/log/Actions/artifacts, correct inconsistencies if needed, then continue the appropriate lane safely.
- After processing, update the state with the processed SHA and a short note.
- If another worker already processed the same SHA, do not repeat that work.
- Prefer the worker's assigned lane when there is no cross-lane GitHub update waiting.
- Do not use this mechanism to touch production/main or production integrations.
