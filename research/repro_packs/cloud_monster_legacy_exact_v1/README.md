# CLOUD_MONSTER_LEGACY_EXACT_V1 recovery pack

Status: **EXACT_REPRODUCED_FROM_RAW**.

The historical 63 Monster rows, their legacy returns, the 19-row saved-score comparison, and all four original pipeline scripts were recovered from the ChatGPT Library/conversation evidence surface. The preserved Actions raw input now reproduces all 63 identities, closes, and returns with maximum return difference `0.0`; it independently reproduces every published headline metric without tuning.

## A. Exact rule

- Watch window: `2026-03-01 <= date < 2026-09-01`.
- Watch gate: `d_pre3 AND d_gap AND ret3 >= 0.06 AND ret3 < 5 AND ret5.notna()`.
- Dedup: sort `symbol,date,timestamp`, then first row per `symbol,date`.
- Label: `monster = ret5 >= 0.20`; diagnostic danger: `ret5 <= -0.10`.
- Features: the exact 52-column ordered list in `recovered_selector.py`.
- Missing values: median imputation; scaling: `StandardScaler`.
- Model: `LogisticRegression(C=0.15,max_iter=500,class_weight='balanced',random_state=1)`.
- Walk-forward selection: April, May, June monthly folds; each fold trains on all prior rows. Fractions tested were fixed `.10,.20,.30`.
- Objective: `mean(avg)+1.5*mean(p20)+.15*mean(win)-.6*mean(m10)+.5*min(avg)`; selected fraction `.10`.
- Final fit: rows before `2026-07-01`. Fixed recovered threshold: training-score 90th percentile `0.7480177317229793`.
- Selection: `priority_score >= threshold`; no cooldown; no daily quota beyond first symbol-day Watch row.
- Legacy endpoint: signal snapshot close to fifth official XTKS session close, cost 0%; JPX mapping was session index `+5`.
- Universe: the recovered base builder applies `prev_close <= 1000`, `prev_volume >= 10000`, current 4H `volume >= 5000`, non-null legacy outcome, and `2026-01-01 <= timestamp < 2026-09-11`; the exact run contains 245,334 rows and 1,314 symbols.

## B-D. Source, input, execution

- Original sources: `/mnt/data/v3r/build_cloud4h_dedup_sep.py`, `build_mtf_fast.py`, `relabel_jpx_5bd.py`, and `revalidate_lanes_jpx.py`, preserved under `source/` (with the Monster-only final section also preserved as `recovered_selector.py`).
- Historical row artifact: ChatGPT Library file `libfile_a5ca557456f0819195d1d03342885513`, downloaded as `cloud_two_lane_union_jpx.csv`.
- Raw 4H input: Actions artifact `10266329903`, run `34608845800`, `teacher_ohlcv_4h_raw.csv`, SHA-256 `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`.
- Verify recovered rows: `py research/repro_packs/cloud_monster_legacy_exact_v1/verify_recovered_rows.py`.
- Full raw reproduction command:
  `uv run --python 3.12 --with "numpy==2.5.3" --with "pandas==2.3.3" --with "scikit-learn==1.9.1" --with "exchange-calendars==4.13.2" python research/repro_packs/cloud_monster_legacy_exact_v1/reproduce_from_raw.py --input-dir <artifact-10266329903-dir> --work-dir <scratch-dir> --receipt research/repro_packs/cloud_monster_legacy_exact_v1/output/raw_reproduction_receipt.json`.
- The runner substitutes only the original hard-coded `/mnt/data/v3r` work directory in memory. It fails on input-SHA drift, stage failure, row identity drift, close drift, or any `ret5` difference above `1e-15`.
- `output/raw_reproduction_receipt.json` records the exact successful runtime and zero-difference comparison.

## E-F. Rows and evaluation

- `artifacts/cloud_two_lane_union_jpx.csv`: 210 union rows, including the exact 63 Monster rows; repository content SHA-256 `91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62`.
- `artifacts/cloud_priorityA_monsters_compare_teacher.csv`: 19 saved high-return score rows; SHA-256 `1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54`.
- Exact legacy metrics are in `output/legacy_metrics.json`: n=63, mean 9.8569%, median 3.3333%, win 57.1429%, +20 30.1587%, +30 19.0476%, -10 22.2222%, Top5-ex 4.0269%.
- The recovered CSV does not carry entry/exit dates and prices. Therefore a next-open→fifth-close canonical bridge has not been fabricated or mixed into the legacy headline.

## G. Identity

`CLOUD_MONSTER_LEGACY_EXACT_V1`. Exact raw-input-to-row reproduction is complete for the historical legacy close→fifth-close endpoint.

## H. Handoff receipt

1. The exact historical 63 Monster rows are recovered and hash-pinned.
2. Their metrics reproduce every supplied signature without tuning.
3. The 19-row score comparison is recovered and hash-pinned.
4. The final Watch expression, dedup, feature order, model, folds, objective, threshold, and selection are recovered from source.
5. Fraction `.10` was chosen by the historical three-fold objective, not by matching n=63.
6. Final training ends before July 2026; July-August are later rows.
7. No cooldown and no per-day quota exist in this exact generator.
8. The original legacy endpoint is close→fifth XTKS close, not next-open.
9. Raw teacher 4H input remains independently authenticated by Actions artifact and SHA.
10. Base, daily/MTF augmentation, JPX relabel, and final selector sources are preserved under `source/`.
11. Artifact `10266329903` reproduces the base frame at 245,334 rows / 1,314 symbols.
12. The final 63 identities, closes, and `ret5` values match exactly with maximum difference `0.0`.
13. The next-open canonical bridge remains separate and pending; it will never replace the legacy headline.
14. No 2026 outcome was used to invent a rule or tune a threshold.
15. Production, main, workflows, Discord, Sheets, and existing modes are untouched.
