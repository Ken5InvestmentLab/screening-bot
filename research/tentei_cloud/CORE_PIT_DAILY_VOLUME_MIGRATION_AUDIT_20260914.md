# Core PIT daily-volume migration audit — 2026-09-14

## Scope
Research-only cross-lane reproducibility audit. No new Core mechanism is introduced, no rejected family is reopened, no return threshold is changed, and no production path is touched.

## Why this audit exists
The Core research universe historically uses an absolute prior-day volume eligibility gate (`previous daily volume >= 10,000 shares`). The shared data-integrity work has established that Yahoo frozen historical **daily** volume is retrospectively adjusted by future stock splits. Therefore a historical absolute-share gate can be wrong unless daily volume is restored to point-in-time share-count scale.

This does **not** rescue current fixed Core or Failed-Breakdown Reclaim. Both remain rejected under their already-opened canonical evidence, and the reclaim locked 2025H2 remains unopened. This audit only constrains future reproducibility / any genuinely new preregistered Core mechanism.

## Frozen shared volume semantics
Adopt the same causal volume contract already frozen by the clean-PIT data lane:

1. For Yahoo frozen historical **daily** data, point-in-time daily share volume is:
   `pit_daily_volume(date) = adjusted_daily_volume(date) / cumulative_future_split_factor(date)`.
2. Any absolute historical daily-volume gate such as `prior_volume >= 10000` must use `pit_daily_volume`.
3. Any daily-volume technical ratio that depends on historical share counts must use the PIT daily-volume series rather than the provider's retrospectively adjusted daily volume.
4. Yahoo raw **1H** volume remains on point-in-time share-count scale under the accepted split-volume receipt and must remain unchanged.
5. Intraday absolute gates such as `session_volume >= 5000` and any raw-1H volume ratio must therefore use raw 1H volume unchanged; do not divide/multiply it by split factors.

Reference contract: `research/CONSENSUS_V47_RAW1H_VOLUME_CONTRACT_CORRECTION_20260914.md` on the Consensus branch.

## Disposition of existing Core evidence
- `REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE` remains unchanged.
- `REJECT_PRECONFIRMATION` for Failed-Breakdown Reclaim remains unchanged.
- Do not reinterpret old negative outcomes as potentially positive because of this data issue.
- Do not use the data issue as permission to change thresholds, cooldown, ranker, session split, liquidity conditions, or feature inequalities.
- Historical studies whose candidate universe depended on an absolute daily-volume gate are **provisional as data-lineage evidence** until rebuilt under PIT daily-volume semantics, but their already-recorded rejection decisions remain closed unless a separately preregistered reproduction-only audit is explicitly authorized without retuning.

## Rule for future Core work
Before any genuinely different low-DOF canonical 5BD Core mechanism is allowed to open outcomes, its preregistration must pin:
- canonical next-XTKS-open -> fifth-XTKS-close target;
- PIT daily-volume construction and split-event source/hash;
- raw 1H volume unchanged semantics;
- candidate-universe digest before outcomes;
- exact selection/cooldown/cost policy;
- 2026 as report-only.

Until such a distinct mechanism exists, Core remains on integrity/reproducibility/endpoint audit duty.

Production/main, production workflows, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder and updater remain untouched.


## Raw1H reconstructed-Core lineage addendum

A later outcome-free lineage audit on this branch clarified an important scope distinction.

The fixed reconstructed Core implemented by `reconstruct_4h_from_1h.py` does **not** source its absolute prior-close / prior-volume gates from the frozen Yahoo daily panel:
- prior daily close is the last explicit-period raw 1H close on the prior date;
- prior daily volume is the sum of explicit-period raw 1H volume on the prior date;
- session volume is summed raw 1H volume.

The shared V47 receipts separately establish that raw 1H volume is already on point-in-time share-count scale, and the explicit-period raw 1H price archive preserves historical nominal split scale on audited split-affected rows.

Therefore the daily-volume PIT migration requirement applies when a Core implementation consumes the frozen **daily** provider fields. It must **not** be applied a second time to this raw1H-derived reconstructed Core path.

Outcome-free lineage run `34798921728` passed all guards. See:
`research/tentei_cloud/CORE_RAW1H_PIT_LINEAGE_FINDINGS_20260914.md`.

This addendum does **not** change `REJECT_CURRENT_FIXED_CORE_AS_REPLACEMENT_CANDIDATE`; that decision remains based on the already-opened canonical performance evidence, not on a newly claimed raw1H daily-volume contamination.
