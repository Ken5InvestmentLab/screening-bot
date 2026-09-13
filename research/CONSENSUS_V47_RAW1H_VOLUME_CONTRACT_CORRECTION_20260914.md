# Consensus V47 raw-1H volume contract correction — 2026-09-14

## Scope
Research-only correction before any V47 strategy outcome access. Production paths are untouched.

## Frozen contract
The authoritative V47 contract distinguishes daily and raw intraday volume semantics:

- Yahoo frozen daily historical volume is retrospectively adjusted by future splits. Point-in-time daily share volume is therefore `adjusted_daily_volume / cumulative_future_split_factor(date)`.
- `prior_volume >= 10000`, `day_vol_ratio5`, and `day_vol_ratio20` must use that PIT daily volume series.
- Yahoo raw 1H volume is already on point-in-time share-count scale according to the frozen 22/22 split-volume receipt.
- `session_volume >= 5000` and `session_vol_ratio20` therefore use raw 1H volume unchanged.
- Raw 1H volume must not be divided, multiplied, or otherwise rebased by split factors.

## Discrepancy found
Commits `f16884b050bee965d43ca191d6205d01387b0f88` and `2e5136bab6c07b6db3657d17c41acfee0c58b74e` changed the clean-feature materializer so prior raw 1H volumes were multiplied by a split-factor quotient for `session_vol_ratio20`, and changed daily feature history from per-date PIT daily volume to a signal-date rebased basis. That conflicts with the frozen user contract above.

No V47 strategy outcomes have been opened. Raw 1H fetch has not been authorized because authoritative daily run `34788533946` remains in progress, so the discrepancy is corrected before it can affect promotion evidence.

## Correction
Restore the pre-discrepancy clean-feature implementation:

1. `load_daily()` materializes `volume = volume_adjusted / future_split_factor_daily` per historical date.
2. `build_symbol_rows()` passes that PIT daily-volume series directly into the official as-of builder.
3. `session_vol_ratio20` uses the stored raw synthetic-session volumes unchanged.
4. Receipt text again states that raw Yahoo 1H volume is unchanged for both the session gate and `session_vol_ratio20`.
5. Remove the synthetic test that expected signal-date raw-volume rebasing; restore the contract test immediately before that change.

## Ordering
The daily v6 materializer itself already applies PIT daily volume to the prior-day eligibility gate and is not changed by this correction. It may finish normally. Do not trigger raw1H until `daily_coverage_pass=true`. After this correction commit, require the clean-feature contract workflow to pass before any future clean-feature materialization.

Strategy returns opened: false.
Model scores opened: false.
2026 selection use: false.
Production writes: false.
