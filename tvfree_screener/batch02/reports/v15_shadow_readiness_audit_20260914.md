# V15 -> prospective shadow readiness audit — 2026-09-14

## Classification

`READ_ONLY_HANDOFF_AUDIT`

This report does not change V15 representation, model features, thresholds, ranking, gates, training, or evaluation. It exists only to define when another lane may safely hand a frozen V15-derived candidate policy to the prospective-shadow infrastructure.

## Current V15 status observed

The current preregistration is `TENTEI-INSPIRED-4H-V15-REGIME-NORMALIZED-REPRESENTATION-20260913` with status `PREREGISTERED_BEFORE_V15_DRIFT_METRICS`.

It explicitly freezes an outcome-free representation-stability gate before V15 strategy-return evaluation. Its parent candidate generator remains V12 ALL with the existing prior-day close/volume gates. This is therefore a representation experiment, not yet a finalized forward candidate policy.

## Shadow readiness: NOT READY YET

The current V15 preregistration is intentionally missing several items that must exist before prospective shadow capture can begin:

1. **final candidate-policy identity** — a stable experiment/policy ID after the representation gate and any separately preregistered supervised evaluation;
2. **model freeze ID** — immutable identifier for the exact trained/selected model or deterministic scoring policy;
3. **freeze manifest + SHA-256** — manifest must identify the exact model/spec/code artifacts that generated forward candidates;
4. **selection/export policy** — exact frozen rule producing the rows to shadow (e.g. Pareto/Top-N/threshold/cooldown), rather than re-ranking inside shadow infrastructure;
5. **candidate-row export** with `symbol`, `signal_date`, `bin_name`, `feature_cutoff`, `source_tag`, plus optional frozen `score` and `rank`;
6. **causal source provenance** — `source_tag` must be `RAW_CAUSAL_INTRADAY`; daily-resolution fallback or post-close reconstruction cannot enter forward evidence;
7. **exact bin cutoff** — `AM_09_13` must carry 13:00 JST and `PM_13_CLOSE` must carry the applicable official close cutoff (15:00 before 2024-11-05, 15:30 thereafter);
8. **no outcome fields in candidate export** — candidate export is decision-time evidence only; 5BD outcomes are attached later by the shadow resolver.

## Ready-state handoff sequence

Once the V15 lane reaches a candidate policy it wants to observe prospectively:

1. freeze the candidate policy/model;
2. create the immutable freeze manifest and record its SHA-256;
3. export selected candidate rows without retrospective outcomes;
4. run `shadow_preflight.py`;
5. ingest only passing rows with the prospective shadow CLI;
6. leave them `PENDING_5BD` until the fifth official XTKS endpoint exists;
7. resolve endpoints without changing the frozen model;
8. evaluate accumulated genuinely post-freeze evidence separately from all retrospective 2025/2026 work.

## Important non-action

Do **not** start shadow capture from the current V15 representation preregistration alone. It has not yet frozen a final supervised/selection policy, and the shadow system must never decide the model, threshold, ranking, or Top-N policy on behalf of the research lane.

## Concurrency note

This audit was created in the separate prospective-shadow lane while the other lane continued V15 representation work. No V15 source/spec/evaluator file was edited by this audit.
