# TV-Free Screener — Next Actions

TEST ONLY. Execute from top to bottom unless a new result invalidates the next item. Keep `HANDOFF.md` synchronized.

## 1. Complete Short V3 Reconstruction Attack lane

Goal: add large-winner capture without destroying the defensive Core+Meta characteristics.

Constraints:
- Use the same Yahoo daily candidate universe and next-open -> 5BD target.
- Train causally by month; outcome must be known before prediction month.
- Select Attack design using 2025 development/validation only.
- Treat 2026 Mar-Aug only as a fixed contaminated check after the design is locked.
- Avoid absolute probability thresholds across retrained models; convert scores to daily percentile or training-distribution CDF.
- Attack is allowed only when the already-selected defensive Core Meta is ON unless pre-2026 evidence clearly supports a separate regime rule.
- Preserve one-business-day same-symbol cooldown.

Test at minimum:
- +10% head percentile.
- +20% head percentile if sample size permits.
- relative top-decile 5BD head.
- combined Attack score with explicit loss-risk penalty.
- one Attack pick per eligible day versus sparse high-quality Attack gate.

Report for 2025H1, 2025H2, and fixed 2026 Mar-Aug:
- n, mean, median, win rate, +5%, +10%, +20%, -10%, max, min, monthly stability.

Do not accept an Attack design if 2026 is the only period where it looks good.

## 2. Combine reconstructed Short lanes

Once Attack is locked or explicitly rejected:
- Defensive Core+Meta lane.
- Attack lane if accepted.
- Test Deep Reversal fallback only if there is a new pre-2026-supported hypothesis; do not revive previously failed arbitrary reversal rules.
- Apply one-day same-symbol notification cooldown.
- Produce one reproducible `v3_short_reconstruction.py` runner and JSON/CSV reports.

Compare against the old Short V3 reference and Stable★6, but label the old Short figures as historical reference rather than exact reproduction.

## 3. Freeze and document Swing S

`v3_swing_v2.py` is the current 10BD S candidate. Do not tune its quality threshold using 2026 further.

Run reproducibility checks in GitHub Actions and preserve the report artifact. Swing A remains unaccepted unless a new pre-2026-stable hypothesis emerges.

## 4. Unified Short/Swing comparison

Generate a test-only comparison report covering:
- 5BD, 10BD, 20BD, 40BD
- n
- mean
- median
- win rate
- +10% rate
- -10% rate
- max / min
- monthly breakdown

Rows should include at least:
- Stable★6 reference
- Short reconstructed S/Core
- Short Attack if accepted
- Short combined
- Swing S
- Swing A if accepted

## 5. Operational-cost validation

After model architecture is stable:
- Measure GitHub Actions runtime for full TSE universe.
- Measure artifact/cache size.
- Confirm whether Yahoo full-universe download cadence and GitHub free usage are operationally practical.
- Optimize feature generation by symbol batches / retained candidate rows rather than giant all-universe feature DataFrames.

## 6. Production integration — BLOCKED until user Go

Do NOT perform any of these automatically:
- merge PR #13 to main
- change production screening-bot
- send production Discord notifications
- write production Spreadsheet
- replace Stable★6/Sniper/Mega logic
- disable TradingView/watchlist builders/updaters

Only prepare an implementation plan and test outputs until the user explicitly says Go for production migration.
