# TV-Free Screener — Next Actions

TEST ONLY. Execute from top to bottom unless a new result invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Search for a genuinely different Short Attack event family

The reconstructed whole-universe percentile Attack based on +10%/+20% heads was selected on 2025 but failed the frozen 2026 side and is rejected. Do NOT keep retuning its thresholds/weights to 2026.

Goal: find a sparse event-driven lane capable of large-winner capture while remaining causally valid and reasonably stable pre-2026.

Constraints:
- Same Yahoo daily TSE common-stock universe and next-open -> 5BD target.
- Keep all work test-only.
- Event definition must use only information observable at signal close.
- Select event family and thresholds from pre-2026 periods only. Prefer 2024 + 2025 if data support adequate samples; use 2025H1/H2 at minimum.
- 2026 Mar-Aug is contaminated fixed-side evidence only.
- Preserve one-business-day same-symbol cooldown.
- Avoid another small variation of `r_hit20-r_loss10` / `r_hit10` thresholds.

Prioritize materially distinct hypotheses such as transition/event structures rather than static whole-universe ranks. Candidate families worth testing only if sample size permits:
- multi-day compression -> expansion transition,
- capitulation/reversal transition with confirmation,
- gap/volume shock followed by controlled close-location structure,
- volatility contraction -> momentum ignition,
- new-high/new-range breakout after bounded prior volatility.

For each family report 2024H1/H2, 2025H1/H2 where available, then one frozen 2026 Mar-Aug check only after locking a candidate. Required: n, mean, median, win, +5%, +10%, +20%, -10%, max/min, monthly stability.

Reject event families that depend on a single extreme winner, have materially negative median in repeated periods, or are only good in 2026.

## 2. Decide Short architecture explicitly

After event-family Attack search:
- If no robust Attack survives, record `Short Attack = none` instead of forcing one.
- Defensive whole-universe Core may remain a supporting lane only; its reconstructed 2026 edge is weak.
- Do not revive the rejected recent-outcome Meta by tuning to 2026.
- Deep Reversal fallback is allowed only if supported by a new pre-2026 event hypothesis.

Produce a reproducible `v3_short_reconstruction.py` runner once the architecture is settled, with JSON/CSV reports and no production writes.

## 3. Freeze and reproduce Swing S

`v3_swing_v2.py` remains the current 10BD S candidate. Do not tune its quality threshold from 2026.

Run reproducibility in GitHub Actions and preserve report artifacts. Swing A remains unaccepted unless a new pre-2026-stable hypothesis emerges.

## 4. Unified Short/Swing comparison

Generate a test-only comparison covering 5BD, 10BD, 20BD, 40BD, n, mean, median, win rate, +10%, -10%, max/min, and monthly breakdown.

Rows should include:
- Stable★6 historical reference,
- reconstructed Short defensive lane if retained,
- Short Attack if any accepted,
- Short combined if justified,
- Swing S,
- Swing A only if accepted.

Label the old +5.42% Short V3 figures as historical non-reproducible reference, not as a current system result.

## 5. Operational-cost validation

After model architecture is stable:
- Measure GitHub Actions full-universe runtime.
- Measure artifact/cache size.
- Confirm GitHub free usage practicality.
- Optimize feature generation by symbol batches / retained candidates rather than giant all-universe DataFrames.

## 6. Production integration — BLOCKED until user Go

Do NOT automatically:
- merge PR #13 to main,
- change production screening-bot,
- send production Discord notifications,
- write production Spreadsheet,
- replace Stable★6/Sniper/Mega,
- disable TradingView/watchlist builders/updaters.

Only prepare implementation plans and test outputs until explicit user Go approval.
