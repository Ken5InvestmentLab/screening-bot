# Meta regime input provenance manifest — 2026-09-18

Scope: research-only provenance audit for primary-5 Meta inputs. No performance/outcome values were inspected or recomputed. 2026 is prohibited. No production files/workflows are changed.

## Controlling primary pool / period boundary

Primary five are frozen as: `body_pct LOW`, `volr20 LOW`, `mean-rank(volr20,body_pct)`, `DUAL_TOP1_AGREEMENT`, `DUAL+G3`. Meta work is restricted to exact-row periods; target period here is 2023-2025 only.

## Axis manifest

| axis | KNOWN source artifact/path/SHA/column | causal lag rule | coverage possible | status / MISSING |
|---|---|---|---|---|
| `breadth_ma20` | `tvfree_screener/run.py` `build_features()` blob `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`; `breadth_ma20` = date-level fraction with `ma20_gap>0`; preserved daily OHLCV internal `tse_daily.csv` SHA256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0` | percentile uses only 120 XTKS sessions strictly before signal T; 33/67 fixed | raw-series reconstruction is mechanically possible for 2023-2025 from preserved OHLCV | **PARTIAL** — still missing receipt joining primary-5 pinned rows to OHLCV SHA `6adfb626...`. |
| rank-pre `candidate_count` | causal Tail artifact ID `10264251140`, artifact digest `2f67833af2881754336c8f92cbf463ddf1cb995bd0fc808a962479d1bfd44198`; internal `v7_causal_tail_cache_2023_2025.csv` SHA256 **`0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`**, columns include `date,...,tail_p,tail`; companion `v7_causal_tail_cache_meta.json` SHA256 `7f992eaf8944c00018fd03311f92a1204fdf7df6d390b4a11ecabf028daf0a59`; V16 selection code blob `13fd0e87e81034757ca6b6f0a0b57abecae35109` | count exact same-signal-T candidate universe before rank/selection/cooldown; SCARCE=1, MULTI=2+ | exact Tail-cache bytes now pinned for 2023-2025, but applicability is only established for V16/volr20 lineage | **PARTIAL/BLOCKED** — file-level Tail-cache SHA/columns are now KNOWN; missing receipt tying this exact cache/pre-rank universe to each primary candidate. Do not generalize V16 to all primary 5. |
| `range_pct` | `tvfree_screener/run.py` blob `b639a6f6f33c643c2dcf09383ccf7dbfc7790cfa`; symbol-date `range_pct=(high-low)/close`; preserved `tse_daily.csv` SHA256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0` | percentile uses only 120 XTKS sessions strictly before signal T; signal T excluded; 33/67 fixed | formula/raw OHLCV coverage exists for 2023-2025 | **PARTIAL/BLOCKED** — missing pinned-rows→OHLCV receipt and prereg/source clarification whether Meta `range_pct` means selected-symbol value or a date-level market aggregate. Do not guess. |

## Newly pinned artifact bytes

Downloaded GitHub Actions artifact `tvfree-v7-causal-tail-cache-2023-2025` (artifact ID `10264251140`) and inspected its ZIP members without opening any performance summary. `v7_causal_tail_cache_2023_2025.csv` is 1,293,015 bytes with SHA256 `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`; header is `date,open,high,low,close,volume,symbol,ret1,ret2,ret3,ret5,ret10,ret20,ret40,ma5_gap,volr5,ma10_gap,volr10,ma20_gap,volr20,ma40_gap,volr40,rsi14,atr14p,body_pct,lower_wick,upper_wick,range_pct,gap,pos10,dd10,bounce10,pos20,dd20,bounce20,pos40,dd40,bounce40,pos60,dd60,bounce60,stoch14,bbpct,bbwidth,volz20,log_dv,down3,down5,target5_cc,next_open,target5_no,target_end_date,prev_close,prev_volume,breadth_ret1_pos,med_ret1,med_ret5,breadth_ma20,future_rank,y_top1,y_top025,y_hit20,y_loss10,tail_p,tail`. Companion metadata SHA is recorded above. Outcome/performance columns were not read or evaluated.

## Decision

No Meta axis yet has a complete `primary pinned rows -> exact input artifact SHA -> signal-date raw series/pre-rank universe -> causal label` chain, so label generation and Meta performance remain fail-closed.

The minimum missing provenance is now more precise: **a receipt binding the primary-5 pinned 2023-2025 rows to their exact input artifact(s)**. For breadth/range this means binding to preserved OHLCV SHA `6adfb626...`; for candidate-count, binding the applicable primary lineage to Tail-cache SHA `0398969e...` and its exact pre-rank universe. `range_pct` additionally requires semantic resolution of selected-symbol vs market aggregate from prereg/source evidence.

2026 remains unopened. Existing return metrics were not recalculated.