# V44 authoritative run disposition — 2026-09-14

Research-only. No production writes.

## Authoritative run
- run: 34767664140
- head: fe24a4b2b350a94a20d0c90c04d36ef975e62870
- conclusion: failure

## Frozen reproduction guard result
Expected DEV cooldown0 baseline:
- n = 67
- mean_pct = 8.424148981560009
- max_symbol_share = 0.44776119402985076

Observed live-refetch DEV baseline:
- n = **61**

The evaluator stopped immediately at the baseline reproduction guard:

`RuntimeError: V44 baseline drift: n=61 expected=67`

No authoritative H2 replacement conclusion was accepted.

## Classification
**DATA_REPRO_FAILURE**, not strategy failure.

Reason:
- same frozen code/spec/dependency path;
- Yahoo 1H was live-refetched;
- candidate count changed before the cooldown policy could be validly evaluated;
- the hard guard behaved correctly by refusing to interpret returns.

## Final V44 status
- Do not claim that cooldown-with-replacement passed or failed.
- Do not rerun/tune V44 now.
- PIT universe/split leakage discovered later makes old V44 non-promotion evidence anyway.
- Replacement mechanics may be revisited only after clean V47 PIT data are frozen, if still relevant.

Production modified: false.
