# Daily-anchor repair audit and causal-use correction — 2026-09-13

Research-only. No production writes. No strategy-return files were opened for this audit.

## Audit identity
- audit_id: `DATA-QUALITY-DAILY-ANCHOR-OPTIONS-20260913-02`
- raw hourly source: cached `cloud_1h_monsters.csv`
- symbols: 2338, 3444, 4052, 5575, 6085, 6217, 6666, 8105
- observed symbol-sessions: 1,325
- complete seven-slot sessions: 1,087
- fallback or unassessable sessions: 238
- strategy outcomes opened: **false**
- raw hourly rows were not overwritten.

## Repair-ladder data-quality result

On the 1,087 complete sessions:

| stage | all OHLC within 1% | all OHLC within 2% | median open APE | median close APE | median volume APE | volume within 5% |
|---|---:|---:|---:|---:|---:|---:|
| raw | 494 (45.446%) | 814 (74.885%) | 0.6889% | 0.3793% | 37.723% | 65 (5.98%) |
| common OHLC scale | 574 (52.806%) | 838 (77.093%) | 0.4386% | 0.3367% | 37.723% | 65 (5.98%) |
| daily open/close anchor | 985 (90.616%) | 1,047 (96.320%) | 0% | 0% | 37.723% | 65 (5.98%) |
| daily high/low extrema anchor | 1,074 (98.804%) | 1,074 (98.804%) | 0% | 0% | 37.723% | 65 (5.98%) |
| volume reconciliation | same OHLC | same OHLC | 0% median OHLC APE | 0% median close APE | 0% | 846 (77.829%) |

Eligibility diagnostics:
- common-scale correction applied: 769 / 1,087 (70.745%)
- volume reconciled: 846 / 1,087 (77.829%)
- fully-corrected intraday: 596 / 1,087 (54.830%)
- partial-review: 455 sessions

Scale factor distribution:
- median 1.000000
- p10 0.995415
- p90 1.005339
- min 0.0986842
- max 1.049973

Volume factor distribution:
- median 1.605659
- p10 1.131488
- p90 2.530032

## Per-symbol diagnostic

| symbol | n | raw all4 <=1% | scale all4 <=1% | fully-corrected |
|---|---:|---:|---:|---:|
| 2338 | 162 | 45.06% | 50.00% | 53.09% |
| 3444 | 162 | 52.47% | 58.02% | 69.14% |
| 4052 | 60 | 65.00% | 66.67% | 58.33% |
| 5575 | 79 | 53.16% | 60.76% | 62.03% |
| 6085 | 142 | 25.35% | 41.55% | 24.65% |
| 6217 | 156 | 49.36% | 57.05% | 58.97% |
| 6666 | 162 | 51.85% | 59.26% | 60.49% |
| 8105 | 164 | 35.37% | 40.85% | 54.27% |

6085 remains a specific pathology and must not drive a universal correction rule.

## Important correction to the prior handoff

The repair ladder proves that completed daily OHLCV can improve **post-close reconstruction consistency**. It does **not** prove that the repaired rows are valid inputs for an intraday/4H signal whose cutoff occurs before the official close.

Using same-day final daily close/high/low/volume to repair an earlier intraday feature would leak information from after the feature cutoff. Therefore two independent dimensions are now mandatory:

1. **reconstruction_quality** — how well the archived intraday series can be reconciled after the day is complete;
2. **causal_signal_eligibility** — whether every input used by the feature was actually available by the feature timestamp.

Any row using same-day final daily H/L/C/volume is tagged `POSTCLOSE_RECON_ONLY` unless the feature cutoff is at or after the official close. It may not be silently used for a pre-close 4H score.

## Provisional quality policy

- `A_FULL_RECON_POSTCLOSE`: complete hourly coverage and defensible OHLCV repair. Useful for post-close archival/research. Not automatically pre-close signal eligible.
- `B_PRICE_RECON_POSTCLOSE`: price reconstruction defensible but volume or another component remains unreliable. Price-only post-close features may be studied separately.
- `C_DAILY_RESOLUTION_FALLBACK`: intraday path is not defensible. Keep one daily-resolution record; never fabricate AM/PM or call it 4H.
- `RAW_CAUSAL_INTRADAY`: separate causal flag. Only information available by cutoff may feed a pre-close 4H feature. Same-day completed daily anchors are forbidden before close.

Do not infer Tier C counts by subtraction until the materializer freezes mutually-exclusive status rules.

## Decision

**KEEP repair ladder for data-quality reconstruction, but CORRECT its role.**

The large consistency gain (raw all-OHLC-within-1% 45.4% -> extrema-anchored 98.8%) is useful for historical data hygiene, but it is not permission to inject final daily values into earlier 4H signals. The next implementation must carry source/correction tags and a causal cutoff flag all the way into the feature extractor.

No 2026 strategy return was used to choose this policy.

## Next action
1. Freeze a deterministic tier + causal-eligibility materializer.
2. Build 4H/session features only from rows allowed by the feature cutoff.
3. For pre-close features, start from raw/cached intraday values and prior-completed-session calibration only; never use the current day's finalized daily H/L/C/volume.
4. Keep post-close-reconstructed rows available for diagnostics and post-close features, but do not mix them with pre-close 4H features.
5. Expand coverage diagnostics before any new strategy outcome test.
