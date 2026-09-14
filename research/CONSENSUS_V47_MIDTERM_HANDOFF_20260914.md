# Consensus V47 midterm diagnostic handoff — 2026-09-14

Scope: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE` only. Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater remain untouched.

## Formal promotion path remains unchanged
- Promotion-relevant evidence remains V47 clean PIT only.
- Daily PIT source `34799835035` is accepted.
- Formal raw acceptance is still FAIL from `34810234454` because the first V47 raw acquisition produced zero usable symbol/date pairs.
- Missing-universe retry `34810592135` remains active and must not be duplicate-triggered.
- Formal acceptance still requires the frozen pair/monthly/completely-missing/20-day/restored gates. Diagnostic opening does not lower or bypass those gates for promotion.

## User-authorized midterm diagnostic opening
Before opening performance, the following were frozen and committed:
- spec: `research/CONSENSUS_V47_MIDTERM_DIAGNOSTIC_SPEC_20260914.json`
- authoritative daily run/artifact digest;
- all eight preserved raw-seed artifact digests from run `34592896202`;
- known partial pair coverage: NOCAP 35.3898%, CAP1000_PIT 83.1124%, restored pair coverage 0%;
- cost = 0%; win = gross canonical return > 0;
- frozen V11 three-head Consensus min threshold 0.95, no guard, both sessions;
- canonical endpoint next official XTKS open -> D+5 close;
- strict same-symbol five-session no-replacement handling;
- no 2026 selection, no interpolation/synthetic missing bars, no price-cap grid search, and no same-family retuning after opened results.

## Diagnostic workflow
Run `34824194221` (`Consensus V47 Midterm Diagnostic`) was triggered from commit `47985d866c779fed63972f6397c73b462ad97e10`.

At the latest scan the run is in progress. Frozen daily, PIT membership, authoritative V47 daily, and all preserved raw-seed artifacts have downloaded successfully; the workflow is currently verifying the pre-open contract / preparing the partial raw pool. No performance result has been emitted yet.

The workflow intentionally uses the preserved immutable Yahoo raw seed only for this first diagnostic. Missing raw remains missing. It materializes NOCAP and CAP1000_PIT features separately under non-promotion shadow mode, then runs the unchanged H1 prequential V11 Consensus logic and reports gross cost-0 metrics.

## Holdout state
- H1 performance remains **not yet emitted** at this handoff timestamp. Once run `34824194221` emits H1 metrics, H1 becomes `OPENED_NOT_UNTOUCHED` and same-family retuning from those results is forbidden.
- H2 remains unopened.
- 2026 remains unopened for selection.

## Next action
1. Recover run `34824194221` result/artifact when complete.
2. If it succeeds, record period / n / mean / median / win / +10/+20/+50 / -10/-20 / Top1-ex / Top3-ex for both arms with the partial-coverage caveat and label them non-promotion evidence.
3. Do not retune V47 from those opened metrics.
4. Independently continue watching formal retry `34810592135`; when complete, provenance-merge retry + preserved raw, rerun the unchanged frozen coverage verifier, and only then proceed with formal clean features/promotion path.
