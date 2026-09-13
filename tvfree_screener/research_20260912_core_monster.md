# TV-Free research update 2026-09-12

Research-only. No production writes. Do not use Stable/Sniper/Mega signal matching as an objective.

## Fixed evaluation premise
- 2026 is reporting/robustness only, never threshold tuning.
- Production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView and watchlist workflows remain untouched.
- Main objective: independent TV-Free Core and Monster that can compete with or exceed legacy Stable★6 on forward 5BD performance and robustness.

## Core independent deterministic families — rejected
Using frozen run-80 daily OHLCV, four low-DOF non-ML families were tested with next-open -> 5BD:
- C1 controlled reversal
- C2 early momentum after pullback
- C3 compression continuation
- C4 rebound confirmation

All four failed cross-period robustness or lacked sufficient right-tail payoff. Typical means stayed around 0-1%, with Top3-excluded means frequently <=0. They are too defensive to compete with Stable★6 and are rejected rather than threshold-tuned.

## Monster weak+early gate — confirmed as a useful structure
Fixed gate:
1. market `med_ret5 <= 0`
2. candidate `ret10 <= 0.5735294117647058`

The gate is applied to the preserved causal V7 Tail population. No 2026 outcomes were used.

### Same-day ranking comparison, 2023-2024 development
One candidate per day, Tail CDF only as tie-break.

`volr20 LOW`:
- n=128
- mean +6.24%
- median +1.06%
- +20% 18.75%
- +50% 8.59%
- -10% 25.78%
- Top1 excluded +5.41%
- Top3 excluded +3.81%

`body_pct LOW`:
- n=128
- mean +6.46%
- median +1.25%
- +20% 17.97%
- +50% 7.81%
- -10% 28.12%
- Top1 excluded +5.64%
- Top3 excluded +4.03%

`volr20 + body_pct` mean percentile rank:
- n=128
- mean +7.16%
- median +1.81%
- +20% 19.53%
- +50% 8.59%
- -10% 25.78%
- Top1 excluded +6.35%
- Top3 excluded +4.75%

Period means for the combined rank:
- 2023H1 +9.07%
- 2023H2 +0.21%
- 2024H1 +10.41%
- 2024H2 +6.92%

### 2025 descriptive check
2025 is not treated as pristine because it has already been inspected in prior research.

`body_pct LOW`:
- n=44
- mean +6.78%
- Top3 excluded +0.03%
- +20% 20.45%
- -10% 31.82%

`volr20 LOW`:
- n=44
- mean +6.58%
- Top3 excluded -0.19%
- +20% 18.18%
- -10% 31.82%

`volr20 + body_pct`:
- n=44
- mean +6.09%
- Top3 excluded -0.71%
- +20% 18.18%
- -10% 34.09%

Interpretation: combining the two improves 2023-2024 development strongly, but does not improve 2025 tail robustness. `body_pct LOW` deserves to remain an independent Monster ranking candidate rather than being automatically blended into V16.

## Next research
1. Walk-forward/fold test `body_pct LOW` versus `volr20 LOW` under the fixed weak+early gate without adding thresholds.
2. Audit monthly/weekly concentration and symbol concentration for both rankers.
3. Core: stop pure low-volatility reversal families; next architecture must explicitly preserve a moderate right tail (+10/+20 capture) while constraining loss10.

## 2026-09-13 ChatGPT manual restart — canonical reconciliation and next freeze

This manual restart resumed from the Codex research state on `research/tvfree-canonical-batch02`. The canonical batch01 reports supersede the older exploratory headline numbers in this file for promotion/go-no-go decisions.

### Canonical state rechecked
- Production migration remains **NO-GO**. No TV-Free production candidate is promoted by the 2026-09-13 leaderboard.
- Core First Reversal, Ridge, and the current orderly-pullback path are not promotion candidates.
- V29 remains a historical 350-symbol reference only; its full-universe V40 countercheck failed, so it is not a Core replacement candidate.
- Monster weak+early remains the only canonical exploratory family with a useful pool-level signal, but canonical v1 could not freeze a selection count.

### Monster v1 selection-layer finding
Under the already-frozen weak+early family gate and the canonical next-open -> fifth-session-close target:

- 2023 full qualifying pool, 0.5% round-trip sensitivity: n=68, mean **+2.20%**, +20% **17.65%**, -10% **35.29%**, top-1-winner-excluded mean **+0.65%**.
- Registered Top1: mean **+1.72%**.
- Registered Top2: mean **+1.58%**.
- Registered Top3/Top5: mean **+1.48%**.
- All Top-N policies failed their frozen selection study; `chosen_top_n=null`.
- 2024 pool diagnostic, still with no chosen N: n=133, mean **+1.84%**, +20% **15.04%**, -10% **32.33%**, top-1-winner-excluded mean **+0.96%**.
- On 72 paired complete 2024 dates, the pool beat its matched weak-tail reference by about **+5.47 percentage points** in mean cohort return.

Interpretation: the family gate may contain useful breadth/right-tail information, while the volr20-driven Top-N selection layer is not adding evidence and may be deleting part of the edge. Do not keep tuning Top1/2/3/5 on the already exposed years.

### New frozen follow-up
Created `tvfree_screener/batch01/reports/monster_canonical_v2_all_policy_spec.json` as a **new v2 family**, not a rewrite of v1:

- keep the v1 weak+early eligibility gates unchanged;
- remove daily volr20 ranking and daily Top-N cap;
- select all eligible names, with the pre-existing one-official-session same-symbol cooldown retained as an operational guard;
- treat 2023+2024 as development evidence because both are already exposed;
- use 2025 only as a locked retrospective replay (not pristine OOS, because older family research has already inspected 2025);
- keep historical 2026 reporting-only and forbidden for tuning;
- begin prospective post-freeze shadow logging for genuinely forward evidence.

The parent-pool +2.20% / +1.84% figures are **motivation only**, not v2 results, because the v2 cooldown replay must be recomputed exactly before any performance claim.

### Locked 2025 replay gates
At the 0.5% round-trip sensitivity, freeze before opening the v2 2025 replay:
- resolved n >= 30;
- mean return > 0;
- +20% rate >= 10%;
- -10% rate <= 40%;
- mean excluding the single best winner > 0.

Do not relax these gates after seeing the replay.

### Next execution
1. Recompute v2 on 2023-2024 with the frozen cooldown and store exact metrics/artifact hashes.
2. Open the unchanged 2025 locked replay and apply the frozen gates.
3. Do not tune from 2026 historical outcomes.
4. Add an ordinary-runtime prospective shadow path so future post-freeze signals can accumulate true forward evidence.

No production code, production workflow, Discord, Sheets, Stable★6, Sniper, Mega, TradingView, watchlist-builder, or watchlist-updater setting was changed in this manual restart.

## 2026-09-13 daily-anchor materializer freeze

The data-quality handoff was resumed before further 4H model work. The previously recorded five-stage daily-anchor comparison was treated as reconstruction evidence only, not a strategy result. Its key complete-session figures remain: raw all-OHLC-within-1% 494/1,087 (45.446%); common-scale 574/1,087 (52.806%); open/close anchors 985/1,087 (90.616%); extrema anchors 1,074/1,087 (98.804%); eligible volume reconciliation 846/1,087 (77.829%). No 2026 strategy return was used.

A deterministic policy is now frozen in `batch02/DAILY_ANCHOR_MATERIALIZER_SPEC.json` and implemented by `batch02/daily_anchor_materializer.py`:
- raw 1h rows are immutable;
- common OHLC scale uses the median O/H/L/C ratio and requires <=2% normalized factor spread;
- daily open/close and H/L extrema anchoring require complete seven-slot coverage plus defensible common scale;
- volume is scaled only when the completed-day ratio is 0.5..2.0;
- failed intraday reconstruction emits exactly one tagged 1D fallback, never fake AM/PM/4H rows;
- same-day finalized daily anchors are `POSTCLOSE_RECON_ONLY` before an explicitly supplied final-daily availability timestamp;
- daily-only fallback is not eligible to become the final 4H scoring representation.

Frozen tiers: `A_FULL_RECON_POSTCLOSE`, `B_PRICE_RECON_POSTCLOSE`, `C_DAILY_RESOLUTION_FALLBACK`, `D_UNUSABLE`. Focused local verification passed 6/6 tests, including raw immutability, one-row fallback, inconsistent-scale rejection, volume compatibility, and cutoff causality.

Decision: the daily repair layer is now fixed as a tagged data-quality/post-close reconstruction boundary. Resume 4H/session feature research only with cutoff-eligible raw intraday inputs and prior-completed calibration. First measure usable coverage by tier/bin; only after that return to the causal relative-volume / 4H feature path. Production remains unchanged.

## 2026-09-13 parallel lane — V12 outcome-free structure audit

A separate lane was used to avoid colliding with the concurrently advancing V12/V13/V14 evaluation work. It audited the frozen V12 event generator on the already-authorized raw 1h shards without loading 5BD returns or any 2026 strategy outcome.

- H1 (2025-03-01..06-30), before prior-daily price/volume gates and before cooldown: 169,328 complete bins, 10,217 V12 signal rows = **6.034%**; AM/PM 5,788/4,429.
- H1 trigger flags: RSI recovery 4,396, trend flip 914, emergency reversal 6,220. Multi-path rows were 1,257 = **12.30%**.
- **3,705/10,217 = 36.26%** of H1 signals had the same symbol also signaling in the immediately previous complete bin; 3,331 emergency-reversal rows followed another emergency-reversal bin.
- H1 monthly firing rate varied materially: March 4.96%, April **11.23%**, May 3.22%, June 4.36%.
- H2 structure only (no H2 returns): 268,045 complete bins, 15,596 signals = 5.818%; previous-complete-bin also signal **27.31%**.
- Full 2025 structure only: 514,098 complete bins, 29,964 signals = 5.828%; previous-complete-bin also signal **31.28%**. Emergency flags appeared on 51.58% of signal rows and RSI recovery on 47.64%, overlaps allowed.

Interpretation: V12 is structurally a persistent state detector as much as a sparse one-shot reversal event generator. This does not invalidate V12 and is not return evidence. Because official V12 return results became visible in the parallel lane only after this structural diagnostic had already been computed, these counts must not be used post hoc to validate V12, pick a trigger path, or alter V13/V14. A future state-entry/first-transition representation, if tested, must be separately preregistered and treated as a new retrospective hypothesis.

Artifacts committed in `86a378e`: `batch02/TENTEI_V12_STRUCTURE_AUDIT_SPEC.json`, `batch02/audit_tentei_v12_structure_no_outcomes.py`, and `batch02/reports/tentei_v12_structure_audit_20260913.md`. Production remained unchanged.

## 2026-09-13 parallel lane — frozen V12 state-entry H1 evaluation

The outcome-free structure audit motivated a separately frozen `state_entry = V12 signal AND NOT previous complete-bin V12 signal` representation. This was treated as a new retrospective hypothesis and did not modify V12/V13/V14.

The first reconstruction produced 6,521 H1 state-entry rows and was rejected before result acceptance because it did not reproduce the frozen 6,512-row structural reference. The discrepancy was traced to warm-up scope: the frozen structure audit used raw rows beginning **2024-12-01**, while the first rebuild had included earlier September-November observations. Because RSI/ATR state is recursive, warm-up scope matters. After restoring the frozen 2024-12-01 warm-up, H1 reproduced exactly at **6,512** state-entry rows.

Frozen sequence: V12 causal state -> first-transition filter -> prior completed daily close <=1,000 JPY and volume >=10,000 shares -> five-XTKS-session same-symbol cooldown -> next-session-open to fifth-session-close endpoint.

H1 results after 0.5% assumed round-trip cost:
- 6,512 structural state-entry rows -> 5,330 after prior-day gates -> 3,445 after cooldown; all 3,445 endpoint labels resolved.
- mean **+1.4647%**, median **+0.6385%**, win **55.27%**.
- +10% **9.06%**, +20% **2.03%**, +50% **0.087%**.
- <=-10% **4.41%**, <=-20% **0.58%**.
- best-one-excluded mean **+1.3354%**, best-three-excluded **+1.2987%**.
- mean cost sensitivity: +1.9647% at 0% cost, +0.9647% at 1% cost.

Decision: **REJECT_AS_MONSTER / DO_NOT_OPEN_H2_FOR_THIS_HYPOTHESIS**. The central tendency and downside are good, but the frozen Monster right-tail gate requires +20% >=10%; state-entry achieved only 2.03%. This is not a near miss, so H2 remains unopened and no threshold/path/cooldown/gate tuning is allowed from this result.

Reproducible evaluator: `batch02/eval_tentei_state_entry_h1.py`. Result report: `batch02/reports/tentei_state_entry_h1_20260913.md`. 2026 strategy outcomes remained unopened. Production remained unchanged.
