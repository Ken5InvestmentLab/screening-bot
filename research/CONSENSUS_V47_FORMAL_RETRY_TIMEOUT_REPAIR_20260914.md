# Consensus V47 formal raw retry timeout repair — 2026-09-14

Scope: research-only transport/data-acquisition hardening for the clean PIT V47 formal path. No strategy threshold, ranker, price arm, cooldown, target, cost, feature semantics, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or updater change.

## Observation

Formal raw retry run `34810592135` remains the only active retry and must not be duplicated. Its first two matrix jobs (`fetch (0)` and `fetch (1)`) each reached the workflow `timeout-minutes: 180` boundary while still inside `Fetch raw 1H shard`, were cancelled by GitHub, and then uploaded only tiny timeout artifacts. This is transport/runtime evidence, not strategy-performance evidence.

The run was launched from commit `6fcf600245e0a04b3d8bc9c3f6c566a81c9fa03d`, which partitioned the required NOCAP symbol list into 12 shards with `max-parallel: 2`. Because each shard contains roughly one quarter of the symbols that a 48-shard layout would contain, 12-way partitioning is not reliable under the current Yahoo retry/backoff policy and the 180-minute GitHub job ceiling.

## Repair staged for future retry only

Commit `7aa230a0434136cf33589a2fdda010113d57db62` changes only the future workflow partition:

- matrix shard count: `12 -> 48`
- `max-parallel` remains `2`
- per-job timeout remains `180` minutes
- same Yahoo fetcher and transport policy
- same authoritative daily materializer dependency
- same required NOCAP symbol source
- no automatic trigger was fired by this workflow-only change because the workflow push path remains restricted to `research/RUN_V47_RAW1H_FETCH`

The currently running `34810592135` remains pinned to its original trigger SHA and is not altered or cancelled by this change.

## Formal acceptance rule unchanged

After the current run finishes, merge only physically valid raw artifacts with the preserved immutable seed and run the exact frozen verifier. If formal acceptance still fails, derive the next request strictly from emitted missing symbol/date pairs. No threshold relaxation and no interpolation.

Frozen acceptance remains:

- pair coverage >= 99.5%
- monthly coverage >= 99.0%
- zero completely missing required symbols
- per-symbol coverage >= 95% for symbols requiring >=20 days
- restored/delisted required-pair coverage >= 99.0%

## Midterm diagnostic separation

`34824194221` is a separate user-authorized `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` path at cost 0%. It does not relax formal raw acceptance and must not be used to retune this family after opened outcomes.
