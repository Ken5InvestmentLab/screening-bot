# Meta regime input provenance manifest — 2026-09-18

Scope: research-only provenance audit for primary-5 Meta inputs. No performance/outcome values were inspected or recomputed. 2026 is prohibited. No production files/workflows are changed.

## Controlling primary pool / period boundary

Primary five are frozen as: `body_pct LOW`, `volr20 LOW`, `mean-rank(volr20,body_pct)`, `DUAL_TOP1_AGREEMENT`, `DUAL+G3`. Meta work is restricted to exact-row periods; 2022 summary-only evidence is not eligible for Meta labeling. Target period here is 2023-2025 only.

## Axis manifest

| axis | KNOWN source artifact/path | source blob SHA | KNOWN column / reconstruction | causal lag rule | coverage possible from known source | status / MISSING |
|---|---|---|---|---|---|---|
| `breadth_ma20` | `tvfree_screener/run.py` `build_features()` from preserved daily OHLCV; V9 explicitly includes it in signal-time `QUALITY_FEATURES` | `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa` | `breadth_ma20`: on each date, fraction of symbols with `ma20_gap > 0`; `ma20_gap = close / rolling20(close) - 1` | Meta percentile must use only the 120 XTKS sessions strictly before signal T; current feature source gives signal-date raw value, but percentile/lag must be applied downstream | Definition/code chain exists for 2023-2025 if the exact preserved OHLCV artifact used by pinned rows is identified | **PARTIAL** — missing pinned preserved OHLCV artifact path+SHA joined to the primary-5 pinned 2023-25 rows. No complete chain yet. |
| rank-pre `candidate_count` | `tvfree_screener/v9_conditional_quality_research.py` `generate_tail_pool()` / `score_tail_month()` exposes raw extreme Tail pool before one-per-day selection; `tvfree_screener/v16_pre2025_volr20_rank.py` `select()` ranks same-day Tail candidates | V9 blob SHA not pinned in this manifest because only current branch file content was inspected; V16 blob `13fd0e87e81034757ca6b6f0a0b57abecae35109` | Required Meta value is count of the **exact primary-family pre-rank candidate universe on signal T**; V16 has same-day `z` before groupby/head/select, but this is evidence for V16/volr20 only and must not be substituted for the other primary candidates | same signal T, before ranking/selection/cooldown; SCARCE=1, MULTI=2+ | Potentially reconstructable for V16/volr20 lineage only once its exact 2023-25 input Tail-cache SHA is pinned | **BLOCKED** — no common pinned pre-rank universe artifact/path/SHA for all primary 5; nearest V16 logic cannot be generalized or substituted. |
| `range_pct` | `tvfree_screener/run.py` `build_features()`; V9 explicitly includes it in signal-time `QUALITY_FEATURES` | `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa` | symbol-date `range_pct = (high-low)/close` | Meta percentile must use only the 120 XTKS sessions strictly before signal T; prereg requires causal history, so signal T cannot enter its own 33/67 thresholds | Formula/code chain exists for 2023-2025 if exact preserved OHLCV and the intended signal-date aggregation key are pinned | **PARTIAL/BLOCKED** — source formula is exact, but manifest evidence does not yet pin (1) the preserved OHLCV artifact SHA used by primary rows and (2) whether Meta `range_pct` is the selected symbol's value or a date-level market aggregate. Do not guess. |

## Known supporting provenance

`tvfree_screener/run.py` defines both `range_pct` and `breadth_ma20` in one deterministic feature builder. The same file defines the eligible universe filters (`prev_volume >= 10000`, `volume >= 5000`, `close >= 20`, optional previous-close price cap). This is source-code provenance only; it is not by itself proof that a particular preserved OHLCV artifact is the exact input behind every pinned primary-5 row.

The frozen 2022 decision receipt records the V16/volr20 2023-25 command as `python tvfree_screener/v16_pre2025_volr20_rank.py --cache tvfree_screener/out/tse_daily.csv --tail-cache tail_cache/v7_causal_tail_cache_2023_2025.csv`, and distinguishes this from the separate backward-2022 chain. It identifies preserved dataset run `34599959356` and causal Tail cache run `34600083474`, but this manifest does not promote those run references to exact artifact SHA without an artifact receipt tying bytes/path/SHA to the pinned 2023-25 primary rows.

## Decision

No axis currently has a complete `primary pinned rows -> exact input artifact SHA -> signal-date raw series -> causal 120-session label` chain, so label generation remains fail-closed and Meta performance must not start.

The **minimum next missing provenance item** is the exact preserved 2023-2025 daily OHLCV artifact path + content SHA that is demonstrably the input behind the pinned primary-5 rows. One such SHA would simultaneously unblock the raw-series provenance for both `breadth_ma20` and `range_pct` (subject to resolving the prereg meaning of `range_pct`). Candidate-count remains a separate missing pre-rank-universe chain.

2026 remains unopened. Existing return metrics were not recalculated.