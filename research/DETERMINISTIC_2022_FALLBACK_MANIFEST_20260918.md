# DETERMINISTIC_2022_FALLBACK_MANIFEST

Status: INPUT/GENERATOR CONTRACT PINNED; deterministic fallback preparation only. No 2026 access, no production write, no return recomputation, and no retuning to the old 29-row / 23-date summary.

## Temporal admissibility
Only the already-frozen generator/spec/input chain recorded by the 2022 fresh-validation receipt is admissible. The old frozen 29 rows / 23 dates are a validation check only; they MUST NOT be used to tune thresholds, rank rules, candidate definitions, or input choice.

Authoritative validation commit: `d9792122a541847c3e4ed82604bffa220dab4a33`.
Upstream input-contract receipt commit: `aaf53ab8d9678dcade730b3f4554a1e8ba72b7f4`, file `research/WEAK_EARLY_2022_MINIMAL_MISSING_INPUT_RECEIPT_20260918.md`.

## 1. Code SHA
At validation commit `d9792122...`:
- `tvfree_screener/v7_full_tail_research.py` blob SHA: `f7f49ab2e09496494adfb365c94e969973c4070c`.
- `tvfree_screener/v9_conditional_quality_research.py` blob SHA: `45a1272fe49c526bbf69956419e34e96d696f7d6`.

Pinned V9 raw-pool operation: `score_tail_month()` / `generate_tail_pool(q,start,end)`. Monthly training is strictly causal (`target_end_date < month_start`), requires >=30,000 train rows, trains V7 `y_top025`, writes `tail_p`, `tail_cdf`, `model_period`, and retains raw Tail rows at `tail_cdf >= 0.999` before one-per-day selection.

## 2. Input artifact SHA/path
- GitHub Actions artifact ID: `10264205130` (`tvfree-frozen-dataset-run80-preserved`; source run `34545440155`).
- preserved daily corpus internal path: `tse_daily.csv` (workflow layout target: `tvfree_screener/out/tse_daily.csv`).
- daily corpus content SHA256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.
- columns pinned by prior provenance receipt: `date,open,high,low,close,volume,symbol`.

## 3. Deterministic command / entrypoint contract
Canonical V7 corpus invocation already present in `.github/workflows/tvfree-full-tail-test.yml`:
`python tvfree_screener/v7_full_tail_research.py --cache tvfree_screener/out/tse_daily.csv`

The deterministic 2022 fallback entrypoint MUST import the pinned V9/V7 implementation at the validation commit and perform exactly:
1. `prepare(raw)` on the pinned corpus.
2. `generate_tail_pool(q, "2022-06-01", "2022-12-31")`.
3. preserve the raw extreme Tail ledger before one-per-day selection.
4. apply the frozen weak+early gate exactly: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`.
5. write SHA256-addressed ledgers and candidate ledgers. Assertions against 89 raw Tail rows and old 29/23 may detect identity mismatch, but MUST NOT trigger retuning.

## 4. Rank/select logic
Frozen upstream Tail selection is top-0.25% monthly causal Tail model with `tail_cdf >= 0.999`. The weak+early gate is applied before primary-candidate ranking. Primary candidate selection is signal-date cross-sectional and uses only fields available at signal T. Endpoint semantics remain signal T -> next XTKS open -> fifth XTKS close, cost 0%, but this manifest does not calculate endpoint returns.

The five primary identities are fixed and MUST NOT be renamed/substituted:
1. `body_pct LOW`
2. `volr20 LOW`
3. `mean-rank(volr20, body_pct)`
4. `DUAL_TOP1_AGREEMENT`
5. `DUAL_TOP1_AGREEMENT + G3 NO_ACUTE_SELLOFF`

For fallback generation, LOW means ascending within the same signal-date eligible pool; mean-rank uses the two same-date ascending ranks; DUAL_TOP1_AGREEMENT requires the two component LOW selectors to agree on the same top-1 identity. Candidate 5 is candidate 4 plus the already-frozen G3 `NO_ACUTE_SELLOFF` gate. G3 threshold semantics MUST be imported from its pinned existing-value receipt/code; if that exact gate cannot be resolved, candidate 5 is fail-closed/PENDING rather than inferred or retuned.

## 5. Candidate identity and output contract
Every emitted row must retain enough identity to audit `signal_date + symbol + candidate_name`, plus source/model fields required to reproduce the selection. Candidate identity is definition-based, not old-summary-membership-based. Duplicate/same-day behavior must follow the frozen candidate definition, never a rule chosen to match 29/23.

Expected research-only outputs after deterministic generation:
- raw 2022 Tail ledger + SHA256;
- frozen weak+early gated ledger + SHA256;
- one canonical row ledger per primary candidate + SHA256;
- receipt recording code commit/blob SHA, input artifact/path/content SHA, exact command, row schema, date coverage, and any fail-closed candidate.

## Relay to Meta
Once canonical primary rows exist, this same task may join only causally pinned Meta inputs by signal date/key. `2022 SUMMARY_ONLY` is forbidden as a Meta source. Meta rule/mapping freeze remains blocked until both primary historical and alternate historical completion. 2026 remains SEALED.
