# V44 failure disposition — 2026-09-14

Research-only decision contract. No production writes.

The authoritative V44 workflow can fail for two fundamentally different reasons. They must not be conflated.

## A. Data/reproducibility failure

Examples:
- Yahoo 1H coverage drift / rate-limit failures;
- dependency or checkout mismatch;
- V43 DEV baseline reproduction guard fails;
- required artifact/receipt missing;
- input coverage is materially below the frozen V43 receipt.

Disposition:
- label **DATA_REPRO_FAILURE**;
- do **not** interpret as evidence that cooldown replacement is bad;
- do **not** open H2 replacement outcomes;
- do **not** retune thresholds, ATR cap, Top-K, cooldown or model;
- next action is data freezing / exact-input reconstruction, preferably from a preserved intraday source, then rerun the same frozen V44 spec.

## B. Strategy/policy failure

Only applies after the authoritative DEV baseline is reproduced.

Examples:
- cooldown5 fails the frozen DEV retention/diversification gate;
- strict cooldown5 reaches H2 and fails any frozen H2 gate;
- the original 3/5 chooser has no eligible policy.

Disposition:
- label **STRATEGY_FAIL** for the corresponding claim;
- no post-hoc rescue on opened H2;
- strict Stable★6 replacement claim is demoted;
- continuation/re-entry/pyramiding research may remain, but requires a later-data preregistered experiment.

## Why this separation matters

Three V44 runs were temporarily overlapping during 2026-09-14 research. The authoritative run has a hard V43 DEV reproduction receipt specifically so temporary provider-side fetch degradation cannot be mistaken for a strategy result.

A failed baseline receipt is therefore a data-integrity result, not a return-performance result.
