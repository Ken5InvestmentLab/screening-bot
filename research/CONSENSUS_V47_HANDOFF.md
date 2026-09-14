# Consensus V47 clean PIT handoff

Updated: 2026-09-14 20:33 JST
Branch: `research/consensus-atr-regime-gate`
Scope: research-only. Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater untouched.

## Promotion boundary
Only V47 clean PIT evidence after frozen raw acceptance is promotion-relevant. V43/V44 returns remain non-promotion evidence because of point-in-time split/universe leakage. The user-authorized midterm diagnostic path is explicitly separate and may open partial-coverage performance only under `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`.

## Current cost policy
All new V47 backtests, diagnostics, and NOCAP/CAP1000_PIT comparisons use **0% round-trip transaction cost only**. Win rate means gross canonical return > 0. Historical 0.5%/1% results are legacy evidence only and must not drive new ranking or GO/NO-GO decisions.

## Frozen contracts
- PIT universe replay: run `34771221050` accepted.
- V46 split audit: run `34775030470` accepted.
- Price-policy arms: exactly `NOCAP` and `CAP1000_PIT`.
- Canonical target: next official XTKS open -> fifth official XTKS close.
- V11 3-head architecture / threshold 0.95 frozen for first clean comparison.
- 2026 outcomes forbidden for selection.
- PIT daily volume = frozen adjusted daily volume / cumulative future split factor.
- Prior-volume gate and daily-volume ratio technicals use PIT daily volume.
- Yahoo raw 1H volume stays unchanged for session-volume gate and session-volume ratio technicals; never divide raw 1H volume by split factor.
- Listing identity epochs isolate prelisting history from feature/target/cooldown state.
- Missing raw pairs are never interpolated and synthetic bars are forbidden.
- Once H1/H2 is opened diagnostically, that period is no longer untouched and same-family retuning is forbidden.

## Authoritative daily source
96ut restoration run `34798987098` recovered 251/251 historical/restored symbols and merge audit `34799650589` passed. Final V47 daily PIT materialization run `34799835035` is authoritative and passed all daily gates:
- `daily_coverage_pass=true`
- `required_coverage_pass=true`
- `restored_daily_coverage_pass=true`
- missing required symbols = 0
- missing required symbol/date pairs = 0

## Formal raw 1H status
First raw run `34800587082` was transport-rate-limited. Frozen acceptance run `34810234454` correctly emitted `accepted=false` with zero usable pairs from that run. This is a data-acquisition failure, not strategy evidence.

Formal missing-universe retry `34810592135` remains active and must not be duplicate-triggered. Current job-level status at 20:33 JST:
- `fetch (0)` and `fetch (1)` reached the 180-minute boundary and are cancelled/completed with upload step succeeding but fetch step cancelled;
- `fetch (2)` and `fetch (3)` are in progress in `Fetch raw 1H shard`;
- remaining shard jobs are queued under the intentional `max-parallel: 2` policy.

Future missing-only retries are already hardened to a 48-shard layout with max-parallel 2 to reduce per-job timeout risk. Do not lower acceptance thresholds or broaden provider semantics to rescue transport failure.

Frozen formal acceptance remains:
- pair coverage >= 99.5%
- monthly coverage >= 99%
- completely missing required symbols = 0
- symbols requiring >=20 dates must have >=95% coverage
- restored-pair coverage >=99%

## Existing preserved Yahoo raw seed
Preserved run `34592896202` provides immutable exact historical Yahoo bars but is not formal V47 acceptance evidence by itself:
- NOCAP required-pair coverage: **35.3898%**
- CAP1000_PIT required-pair coverage: **83.1124%**
- restored historical identity coverage: 0%

Any formal merged pool must preserve source/artifact/digest provenance, deduplicate exact `(symbol,timestamp)`, forbid interpolation/synthetic bars, and rerun the unchanged frozen verifier.

## Midterm H1 diagnostic — NOT promotion evidence
Run `34824194221` opened H1 under the user-authorized diagnostic exception using preserved partial raw only, cost 0%, canonical next-open -> D+5, frozen threshold/ranker/arms/cooldown, no interpolation.

Label: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`.

### NOCAP H1
- pair coverage: **35.3898%**
- period: 2025-01-06..2025-06-30
- n=50
- mean **+0.1074%**
- median **-2.7270%**
- win **36.00%**
- +10% **16.00%**
- +20% **8.00%**
- +50% **0.00%**
- -10% **12.00%**
- -20% **2.00%**
- Top1-ex **-0.7566%**
- Top3-ex **-2.0148%**

### CAP1000_PIT H1
- pair coverage: **83.1124%**
- period: 2025-01-06..2025-06-30
- n=60
- mean **-1.1568%**
- median **-0.4011%**
- win **46.67%**
- +10% **13.33%**
- +20% **0.00%**
- +50% **0.00%**
- Top3-ex **-2.0601%**

Frozen H1 mean-first chooser therefore selected NOCAP for diagnostic H2 opening. This selection cannot be changed after seeing H2.

## Midterm NOCAP H2 diagnostic — completed
Run `34832358609` completed SUCCESS at 2026-09-14 20:26 JST-equivalent run completion window. Artifact `consensus-v47-midterm-h2-diagnostic-34832358609`, digest `sha256:2ceea9b8a20eed60b1e65e19963f1f2e51974a8f2e2b14ed315032ef4ffda8e9`.

The run re-materialized partial PIT features from the same preserved raw seed, did not interpolate missing pairs, kept 2026 closed, and opened **NOCAP only** on H2. CAP1000_PIT H2 remains closed; it must not be opened as a rescue after seeing NOCAP H2.

Label: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`.
Coverage caveat: preserved partial Yahoo seed; formal raw acceptance is still false. The NOCAP raw-pair coverage basis remains **35.3898%**, so this is coverage-bypassed diagnostic evidence only.

### NOCAP H2 cost-0 result
- period: **2025-07-01..2025-12-30**
- endpoint: **next official XTKS open -> D+5 close**
- cost: **0%**
- strict same-symbol cooldown: **5 sessions**, with H1 cooldown state carried into H2
- n = **37**
- mean = **+3.0295%**
- median = **+0.3817%**
- win = **51.35%**
- +10% = **27.03%**
- +20% = **16.22%**
- +50% = **2.70%**
- -10% = **13.51%**
- -20% = **2.70%**
- Top1-ex = **+1.5562%**
- Top3-ex = **-0.5393%**
- unique symbols = **10**
- max-symbol share = **35.14%**

Interpretation: H2 mean/median/win and Top1-ex are positive, but Top3-ex is negative, so the partial-coverage H2 diagnostic shows material right-tail/top-winner dependence. This does **not** reject the family by itself under the user's performance-first rule, but it is an explicit fake-edge/concentration warning. No same-family retune is permitted because H1 and H2 are now opened.

## Formal vs diagnostic status
- Formal Daily PIT acceptance: **PASS**.
- Formal raw 1H acceptance: **NOT PASS / acquisition still active**.
- Formal clean feature materialization: **not authorized yet**.
- Formal H1: **unopened**.
- Formal H2: **unopened**.
- Midterm H1: **opened, diagnostic only**.
- Midterm NOCAP H2: **opened, diagnostic only**.
- Midterm CAP1000_PIT H2: **closed and must remain closed**.
- 2026: **closed for selection**.

## Frozen next action
1. Do not duplicate-trigger formal retry `34810592135` while active.
2. Continue monitoring retry artifacts and collect immutable shard outputs as they finish.
3. When the retry ends, merge retry raw + preserved raw with explicit provenance and rerun the exact frozen raw verifier.
4. If formal acceptance still fails, target only newly missing symbol/date pairs/codes using the already hardened 48-shard layout. No threshold lowering/interpolation.
5. Only after formal raw acceptance PASS may promotion-grade clean features be materialized and formal NOCAP/CAP1000_PIT comparison begin.
6. Do not retune V47 from opened midterm H1/H2. Do not open CAP1000_PIT H2 as a rescue.
7. V45 ATR remains deferred until V47 formal path is resolved.
