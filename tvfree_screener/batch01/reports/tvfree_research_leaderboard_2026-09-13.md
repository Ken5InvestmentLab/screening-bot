# TV-Free research leaderboard and migration decision — 2026-09-13

## Decision

**No TV-Free production candidate is promoted in this batch. Production migration is NO-GO.** The Core families have no passing policy. Monster retains one exploratory candidate pool, but none of its registered Top1/2/3/5 policies passed. The V29 result remains a small-population historical reference, not a full-universe replacement. No same-definition comparison establishes that TV-Free has matched or exceeded the current production bot.

Every result below is retrospective and provisional. The common Yahoo-derived daily history is not proven point-in-time universe membership, delisted coverage, corporate-action completeness, or executable fills. The 0.5% round-trip cost is a sensitivity assumption rather than measured fees, tax, slippage, or fill quality.

## Candidate table

| Lane / family | Sample and period | 5-session result after assumed 0.5% cost | Decision |
|---|---:|---|---|
| Core — First Reversal, strongest discovery policy (legacy rank Top1) | 63 resolved of 65 selected; 2022H2–2023 | mean +1.35%; median -0.50%; Top3-winner-excluded mean -0.11%; +10 19.0%; +20 3.2%; +50 1.6%; -10 4.8%; -20 0% | All eight registered Top-N variants failed at least one gate. The frozen dd60 direction reversed in the separate 2024 feature-only confirmation. Reject; do not rescue with threshold tuning. |
| Core — Ridge Top1 / Top2 / Top3 / Top5 | 365/730/1,095/1,825 selected; 358/721/1,079/1,800 resolved; 2022H2–2023 | net means -0.56%/-0.43%/-0.44%/-0.30%; medians -1.36%/-0.78%/-0.90%/-0.68%; Top3-excluded means -1.02%/-0.65%/-0.63%/-0.41%. All four failed gates. | Reject family. 2024 remained closed. |
| Core — PIT industry lead / individual lag | Required historical industry membership unavailable | No performance result; no current-sector backfill was used | Inconclusive, slot consumed. |
| Core — orderly pullback | 207,694 candidate signals; 202,177 resolved, 5,517 unresolved; 2022H2–2023 | At 0.5% cost: mean -0.21%; median -0.38%; Top3-excluded mean -0.22%; +10 2.44%; +20 0.51%; +50 0.03%; -10 1.88%; -20 0.18%. All 365 active dates had partial pool labels; 0 complete daily cohorts and 5 abstain dates. | Exact frozen family gate is inconclusive due no complete cohort days, while all three measurable signal checks are negative. No Top-N policy was evaluated in recovery; no 2024 open. |
| Monster — weak + early + volr20-low pool | 2023 discovery: 69 requested / 68 resolved; 51 candidate dates; 41 symbols | mean +2.20%; median -2.30%; +10 25.00%; +20 17.65%; +50 7.35%; -10 35.29%; -20 14.71%; Top1-excluded +0.65%; Top3-excluded -2.08%. | Pool gate kept as exploratory. Every registered Top1/2/3/5 policy failed; no selected policy. |
| Monster — same pool, 2024 pool diagnostic | 138 requested / 133 resolved; policy was not frozen | mean +1.84%; median -2.55%; +20 15.04%; +50 5.26%; -10 32.33%; -20 12.78%. Against the matched weak-tail reference, 72 paired complete dates had +5.47 percentage points mean cohort difference. | Descriptive pool diagnostic only; it did not select an N. 2025/2026 remain unopened for this family. |
| V29 fixed_min98_both | 35 signals from a historical 350-symbol watchlist-frequency sample | mean +4.86%; median +2.90%; robust mean +5.07%; win 55.88%; +10 31.43%; one loss at or below -20% | Reference only. Removing the population cap did not retain the result: V40 full-universe fixed_min97 n=41 mean -3.05%, median -5.04%; min98 n=32 mean -3.96%, median -5.91%. |

The canonical daily studies use next XTKS-session open to fifth-session close. V29’s saved target begins at signal close, so its headline cannot be ranked directly against the canonical studies. The research selections permit multiple distinct symbols per lane/day; no implicit one-symbol/day cap was used.

## Operational readiness

- Fundamental V2 passed repeated scoring on identical frozen facts. Independent source extraction and date-aligned point-in-time fundamentals are not verified, so no predictive-value backtest or production integration was attempted.
- The recovery and scoring research code is ordinary local Python and makes no Codex/LLM calls. It remains research-only. Production Bot, Discord, Sheets, workflows, secrets, and watchlists were not changed.
- Yahoo daily bars cannot reconstruct missing hourly or 4-hour bars. No such fallback was implemented. Any future repair must acquire, validate, and process data in the ordinary production runtime without Codex; otherwise the intraday gap remains unresolved.
- The full research unit suite passed: 65 tests. This verifies the research code paths and gates; it does not establish historical data quality or future profitability.

## Next evidence

Keep the current production system. Treat TV-Free as not ready to replace it. Further Core work should not reuse exposed 2022–2024 outcomes as OOS or finely retune these failed families. A new Core family requires a distinct mechanism and an explicit prospective evidence plan. Keep Monster visible only as an exploratory pool until an unchanged policy passes a valid selection study and later confirmation. Begin any future daily shadow record only through an ordinary, Codex-free runtime after its data source, timing, and authorization are verified.
