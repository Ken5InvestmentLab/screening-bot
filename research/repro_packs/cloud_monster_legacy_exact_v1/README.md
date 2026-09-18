# CLOUD_MONSTER_LEGACY_EXACT_V1 recovery pack

Status: **EXACT_ROWS_AND_FINAL_SELECTOR_RECOVERED; FULL_PIPELINE_REPRO_BLOCKED**.

The historical 63 Monster rows, their legacy returns, the 19-row saved-score comparison, and the original final selector source were recovered from the ChatGPT Library/conversation evidence surface. `py research/repro_packs/cloud_monster_legacy_exact_v1/verify_recovered_rows.py` independently reproduces the published headline from the recovered rows. This is no longer `EXACT_NOT_YET_RECOVERED`, but it is not yet a from-raw full reproduction because the builder of `cloud4h_frame_dedup_sep.pkl` remains missing.

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
- Universe inherited from the missing base frame: recovered run contained 1,314 symbols. Its exact upstream universe construction remains missing.

## B-D. Source, input, execution

- Original final source: `/mnt/data/v3r/revalidate_lanes_jpx.py`, recovered from ChatGPT conversation `研修継続報告`, message `3141d527-c580-4ae7-a045-764138f04611`.
- Preserved Monster section: `recovered_selector.py`.
- Historical row artifact: ChatGPT Library file `libfile_a5ca557456f0819195d1d03342885513`, downloaded as `cloud_two_lane_union_jpx.csv`.
- Raw 4H input: Actions artifact `10266329903`, run `34608845800`, `teacher_ohlcv_4h_raw.csv`, SHA-256 `f28bcb4546a4806c67feae4b45f346d08a881dc530f95da870ee50a6be9b7ce2`.
- Exact upstream scripts also recovered in the conversation: `build_mtf_fast.py` and `relabel_jpx_5bd.py`; their source text is described in the ledger. Commit-safe extraction is still pending because the 2% usage stop boundary was reached.
- Verify recovered rows: `py research/repro_packs/cloud_monster_legacy_exact_v1/verify_recovered_rows.py`.
- Full selector execution requires historical `cloud4h_mtf_jpx5bd.pkl`, whose base predecessor builder is not yet recovered. Do not synthesize it to match n=63.

## E-F. Rows and evaluation

- `artifacts/cloud_two_lane_union_jpx.csv`: 210 union rows, including the exact 63 Monster rows; repository content SHA-256 `91f1f956a48a308e21e49aa2a80c7075677ac5aa6d5dfae5d26c1b1ad7db4a62`.
- `artifacts/cloud_priorityA_monsters_compare_teacher.csv`: 19 saved high-return score rows; SHA-256 `1920e2e69b89feee473cd2e6f6542fe1766f754c3ff60397b65d026614037d54`.
- Exact legacy metrics are in `output/legacy_metrics.json`: n=63, mean 9.8569%, median 3.3333%, win 57.1429%, +20 30.1587%, +30 19.0476%, -10 22.2222%, Top5-ex 4.0269%.
- The recovered CSV does not carry entry/exit dates and prices. Therefore a next-open→fifth-close canonical bridge has not been fabricated or mixed into the legacy headline.

## G. Identity

`CLOUD_MONSTER_LEGACY_EXACT_V1`. Exact row identity and final selector identity are recovered. Full raw-input-to-row reproducibility remains blocked only at the historical base 4H feature-frame builder/universe boundary.

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
10. Daily/MTF augmentation and JPX relabel sources were found in the same conversation.
11. The builder of `cloud4h_frame_dedup_sep.pkl` and exact universe construction remain missing.
12. Therefore full from-raw execution must not yet be labeled complete.
13. The next-open canonical bridge remains separate and pending.
14. No 2026 outcome was used to invent a rule or tune a threshold.
15. Production, main, workflows, Discord, Sheets, and existing modes are untouched.
