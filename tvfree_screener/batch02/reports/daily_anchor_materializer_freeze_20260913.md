# Daily-anchor deterministic materializer freeze — 2026-09-13

Research-only. Production unchanged. No strategy-return file was opened for this step.

## What was advanced

The prior `DATA-QUALITY-DAILY-ANCHOR-OPTIONS-20260913-02` audit had already shown that post-close daily anchoring materially improves reconstruction consistency, but it explicitly left mutually-exclusive tier precedence and cutoff causality unimplemented. This step closes that gap by freezing and implementing `daily_anchor_materializer.py`.

## Frozen rules

1. Raw hourly rows are never overwritten; repaired rows are copied and source-tagged.
2. A complete intraday day requires exactly one normal 1h bar at each JST start 09:00 through 15:00 for this cached-sample materializer.
3. Common OHLC scaling is allowed only when the median daily/hourly O/H/L/C ratio has normalized maximum spread <=2%.
4. Open/close daily anchors and daily H/L extrema anchors are applied only after complete coverage and a defensible common scale.
5. Daily H/L are assigned to the already-observed raw extrema locations; no unobserved intraday time is invented.
6. Volume is proportionally reconciled only with complete coverage and `0.5 <= daily_volume / hourly_sum <= 2.0`.
7. If intraday reconstruction is not defensible but a valid daily row exists, exactly ONE `1D` fallback row is emitted. No fake AM/PM or fake 4H rows are created.
8. Same-day finalized daily anchors are `POSTCLOSE_RECON_ONLY` unless the feature cutoff is explicitly at/after an explicitly supplied final-daily availability timestamp.
9. Pre-close 4H/session scoring remains raw/cached-intraday-led plus prior-completed calibration only. The materializer cannot silently make a pre-close feature causal.

## Tiers

- `A_FULL_RECON_POSTCLOSE`: common price scale defensible and volume reconciliation defensible.
- `B_PRICE_RECON_POSTCLOSE`: common price scale defensible, price reconstruction retained, volume left unscaled/untrusted.
- `C_DAILY_RESOLUTION_FALLBACK`: valid daily data, but no defensible intraday reconstruction. One daily row only.
- `D_UNUSABLE`: neither defensible intraday reconstruction nor valid daily fallback.

## Existing data-quality numbers retained as evidence

The underlying eight-symbol cached audit remains unchanged: 1,087 complete seven-slot sessions; raw all-OHLC-within-1% 494/1,087 (45.446%); common-scale 574/1,087 (52.806%); open/close anchor 985/1,087 (90.616%); extrema anchor 1,074/1,087 (98.804%); compatible volume reconciliation 846/1,087 (77.829%). The prior audit recorded 596 complete sessions as fully corrected under the diagnostic. These are reconstruction-quality numbers only, not strategy results or proof of intraday truth.

## Verification in this step

Focused unit tests were executed locally against the committed module: **6 passed / 0 failed**.

The tests verify:
- raw input immutability;
- seven repaired 1h rows on a valid complete session;
- one-row daily fallback on missing hourly coverage;
- fallback on inconsistent OHLC scale;
- no volume rescaling when the volume factor is outside the frozen compatibility range;
- post-close causality requires an explicit daily availability timestamp;
- unusable status when neither source is valid.

## Data / outcome access

- Reused only the already-authorized raw-hourly artifact context; no new Yahoo request was made.
- No `cloud_1h_monster_precursors.csv` strategy/outcome data was opened.
- No 2026 strategy return was used for a threshold, model, tier, or repair choice.
- Production Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater and production workflows were untouched.

## Decision

`FREEZE_MATERIALIZER_AND_RETURN_TO_CAUSAL_4H_FEATURES`.

The daily-anchor repair ladder is now an explicit post-close reconstruction/data-quality layer, not a way to manufacture intraday signal inputs. Daily-only fallback stays visible and tagged, but is not eligible to become a final 4H scoring candidate.

## Next action

1. Feed the new tier/causal tags into the research feature-preparation boundary.
2. For pre-close bins, accept only raw causal intraday fields available by cutoff and prior-completed calibration; reject `POSTCLOSE_RECON_ONLY` fields.
3. Measure broader 1h/4H usable coverage by tier and bin before opening any new strategy outcomes.
4. Then resume causal 4H feature research (including the already-registered relative-volume quality path) with 4H/intraday features primary.
