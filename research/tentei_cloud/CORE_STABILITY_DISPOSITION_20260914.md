# Core stability disposition — 2026-09-14

Research-only. Production remains unchanged.

## Endpoint correction history

The first stability/cost audit used a legacy **signal-session close -> fifth XTKS-session close** target. That evidence remains descriptive only and is not the canonical replacement endpoint.

A dedicated repair run then relabeled the **exact unchanged fixed-Core candidate set** with:
- entry: next observed official XTKS session open;
- exit: signal date + 5 official XTKS sessions close;
- no candidate-rule, threshold, cooldown, or cost change;
- 2026 kept report-only.

Canonical repair run: `34766143681` — success.
Artifact: `tentei-cloud-core-canonical-endpoint`, id `10320537228`, SHA-256 `ad66fd569f7d7423b5649ba314eb5dee4d752027ea76d44b85581148f06c7d8f`.

## Canonical next-open evidence

### DEV — 2024-11 through 2025-06

At 0.5% assumed round-trip cost:
- n = **169**
- mean **+0.712%**
- median **+0.509%**
- win **55.62%**
- +10% **7.10%**
- +20% **0.59%**
- <=-10% **3.55%**
- Top1-excluded mean **+0.587%**
- Top3-excluded mean **+0.393%**
- Top5-excluded mean **+0.211%**

The fixed architecture is positive in DEV under the canonical endpoint.

### 2025H2

At the same 0.5% cost:
- n = **140**
- mean **-0.452%**
- median **-0.745%**
- win **41.43%**
- +10% **1.43%**
- +20% **0.71%**
- <=-10% **2.14%**
- Top1-excluded mean **-0.700%**
- Top3-excluded mean **-0.874%**
- Top5-excluded mean **-1.006%**

This is a clear out-of-development deterioration.

At **0% cost**, H2 still does not show a robust Core profile:
- mean **+0.048%**
- median **-0.245%**
- win **45.71%**
- Top1-excluded mean **-0.200%**
- Top3-excluded mean **-0.374%**
- Top5-excluded mean **-0.506%**

Therefore the weakness is not explained by the 0.5% cost assumption alone.

### 2026YTD — report only

The canonical replay reports 116 resolved of 120 selected:
- 0.5% cost mean **+1.432%**
- median **+0.098%**
- win **50.86%**

This block is **report-only** and cannot rescue or tune the candidate.

## Canonical disposition

**REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE.**

Reason:
- canonical DEV is positive;
- canonical 2025H2 is negative on mean, median and winner-excluded robustness at the primary 0.5% cost;
- even zero-cost H2 has negative median, sub-50% win rate and negative winner-excluded means;
- 2026 is not allowed to overturn the H2 failure.

This decision rejects the **current fixed reconstructed Core architecture as a replacement candidate**. It does not authorize threshold tuning on the opened blocks.

Already rejected pruning paths remain closed:
- broad-market hard regime gates;
- simple local single-feature hard gates;
- positive peer-momentum hard gates.

## New-family status

`CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json` remains an outcome-unopened, genuinely new low-DOF Core hypothesis.

Now that the canonical endpoint repair is complete, that family may proceed only under its already-frozen contract. It must not inherit or retune the rejected fixed-Core thresholds from opened outcomes.

Production remains unchanged.


## Failed-breakdown reclaim staging status

The preregistered new family is now **implemented but NOT TRIGGERED**.

Frozen implementation:
- spec: `research/tentei_cloud/CORE_FAILED_BREAKDOWN_RECLAIM_SPEC_20260914.json`
- evaluator: `research/tentei_cloud/eval_core_failed_breakdown_reclaim.py`
- workflow: `.github/workflows/tentei-cloud-core-failed-breakdown-reclaim.yml`
- evaluator commit: `c5dc9b704b514e4c777e2fdd1d948b6de7c244fd`
- workflow commit: `9c276a4499c0be89a59b0c7d96b8f62d06181430`

Safety properties:
- workflow is manual-dispatch only; no push trigger;
- default phase opens DEVELOPMENT + INTERNAL_VALIDATION only;
- LOCKED_CONFIRMATION is opened only with explicit `locked_confirmation` dispatch;
- evaluator then independently blocks H2 unless both preconfirmation blocks pass every frozen gate;
- 2026 is not computed by this evaluator;
- no threshold sweep, rank, Top-N, or backfill exists.

Execution ordering:
- corrected Consensus V44 run `34766353425` is currently still fetching/reconstructing Yahoo 1H;
- **do not trigger this Core workflow concurrently** with that run;
- wait until the corrected V44 run is complete (success/failure both acceptable for resource scheduling), then launch only the `preconfirmation` phase;
- do not open locked 2025H2 unless the produced preconfirmation artifact proves both frozen blocks passed.

This staging step changes no production code or strategy thresholds.


## Failed-breakdown reclaim contract-test receipt

Lightweight contract test workflow:
- workflow: `Tentei Cloud Core Reclaim Contract Tests`
- run: `34767726209`
- result: **completed / success**
- tested HEAD: `4883e0da68a3a5829ce636046cf6245a9bc03c3d`

The tests freeze the following pre-outcome invariants:
1. candidate rule uses strict inequalities exactly as preregistered:
   - session low < previous completed daily low;
   - session close > previous completed daily low;
   - session close > session open;
2. primary gate boundaries are exact:
   - mean and Top3-removed mean are strictly >0;
   - median may equal 0;
   - win must be strictly >50%;
   - gross <=-10% rate may equal 10% but not exceed it;
3. locked confirmation requires **both** DEVELOPMENT and INTERNAL_VALIDATION to pass every frozen gate;
4. canonical endpoint maps signal day to next official-session open and signal+5 official-session close.

This test run uses no market download and opens no strategy outcomes.

Execution status remains **STAGED_NOT_TRIGGERED** until authoritative hardened Consensus V44 run `34767664140` completes.


## Failed-breakdown preconfirmation integrity correction

Run `34768879678` completed successfully at the workflow level but is **INVALID FOR RESEARCH CONCLUSIONS**.

Reason discovered before its performance was interpreted:
- evaluator commit in that run derived previous-day low/close/volume by aggregating the raw 1H panel;
- the frozen spec requires **previous completed XTKS daily bar** context;
- this can change the candidate universe and therefore violates the preregistered data contract.

Disposition:
- do not inspect or use the run's performance metrics;
- do not treat the run as a strategy failure or success;
- corrected evaluator commit `37e422240690d6ebed849d2c7a491ed70e0d9627` reads prior-day context from the frozen canonical daily source;
- corrected workflow commit `047787fd9a69ef678172b8d748e0036759d9426b` pins raw source run `34592896202` and canonical daily artifact run `34599959356`;
- corrected contract-test fixtures were aligned in commit `784e57e1c366cf57e1cbfd5f9bc4a074e6cd1dc0`.

No 2025H2 locked-confirmation outcome was opened by this invalid run.
