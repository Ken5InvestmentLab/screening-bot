# Prospective shadow verified append boundary — 2026-09-14

## Scope
Research-only integrity boundary for the prospective-shadow lane. No production systems, strategy thresholds, model logic, Discord, Sheets, TradingView, watchlist builder/updater, Stable★6, Sniper, or Mega were modified.

## Purpose
Require exact admission evidence before any prospective-shadow candidate batch is appended. The official safe append path now replays the live admission gate, verifies the exact admission receipt against the current manifest/candidate rows/admission result, and only then delegates to the append-only writer.

## Added
- `prospective_shadow_verified_append.py`
- `test_prospective_shadow_verified_append.py`

## Guard behavior
Append is blocked before write when:
- the supplied admission result no longer equals a fresh replay on the exact current manifest and rows;
- the admission receipt is invalid or altered;
- the candidate batch changed after receipt creation;
- the manifest changed after receipt creation;
- a row is noncausal or otherwise fails the unified admission gate.

A successful append returns `VERIFIED_APPEND_COMPLETE`. Duplicate replay of the exact same admitted batch is idempotent: zero new rows and the JSONL bytes remain unchanged.

## Verification
Equivalent local execution of the six focused cases: **6/6 PASS**.

Covered cases:
1. valid receipt + live admission replay -> one row appended;
2. tampered receipt -> blocked and existing shadow bytes unchanged;
3. changed candidate row -> blocked before shadow file creation;
4. changed admission result -> blocked before shadow file creation;
5. noncausal source -> blocked before shadow file creation;
6. exact duplicate re-append -> `added=0`, `skipped_duplicate=1`, shadow bytes unchanged.

## Concurrency check
Immediately before this report, `research/tvfree-canonical-batch02` HEAD was `d69d98afc080d0b89358a703cbc57ff448c7d955`, the verified-append test commit. No intervening parallel commit was present on the shared branch at that boundary.

Other lanes remained separate: Core was advancing canonical-entry-date capacity work; Consensus was revising the JPY1000 cap from mandatory to performance-selected. The point-in-time split reconstruction remains owned by V46 and was not duplicated here.

## Integrity statement
This boundary does not open strategy returns, rank candidates, modify model parameters, alter thresholds/cooldowns/eligibility, or authorize production. It only hardens the append boundary for forward evidence collection.
