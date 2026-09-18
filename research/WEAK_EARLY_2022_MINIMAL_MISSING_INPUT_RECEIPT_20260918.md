# 2022 weak+early fresh-validation — minimal missing input receipt

Status: INPUT CONTRACT PINNED; rows not regenerated in this receipt.

Authoritative validation commit:
- `d9792122a541847c3e4ed82604bffa220dab4a33` (`research: record 2022 weak-early fresh validation failure`)
- parent: `f302ed9e7efd27195ff6fb1fc238b3dc616c58ce`

Authoritative target recorded by that commit:
- frozen daily corpus artifact: `10264205130` (source run `34545440155`)
- V7/V9 monthly causal Tail implementation
- `train >= 30,000`
- top-0.25% Tail model, `tail_cdf >= 0.999`
- 2022 computable months June–December
- 89 extreme Tail candidate rows
- frozen weak+early gate `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`
- target after gate: 29 candidate rows / 23 signal dates

Pinned generator implementation at validation commit:
- `tvfree_screener/v7_full_tail_research.py`
- `tvfree_screener/v9_conditional_quality_research.py`
- V9 `score_tail_month()` is the exact raw-pool operation needed for reconstruction: monthly training rows are `target_end_date < month_start`; it requires `len(train) >= 30000`; trains V7 `y_top025`; writes `tail_p`, `tail_cdf`, `model_period`; and returns all rows with `tail_cdf >= 0.999` BEFORE one-per-day selection.
- V9 `generate_tail_pool(q,start,end)` concatenates those monthly raw Tail rows.

Existing workflow proves the V7 invocation/corpus layout:
- `.github/workflows/tvfree-full-tail-test.yml`
- input path: `tvfree_screener/out/tse_daily.csv`
- canonical V7 command: `python tvfree_screener/v7_full_tail_research.py --cache tvfree_screener/out/tse_daily.csv`

## Minimal missing element — exactly one

`MISSING_2022_RECONSTRUCTION_ENTRYPOINT`

No committed script/command at the validation commit is pinned that invokes V9's raw-pool generator for `2022-06-01..2022-12-31`, applies the frozen weak+early gate, and saves the resulting 89-row and 29-row ledgers. The existing V9 `main()` begins its warmup at 2023 and therefore is not itself the 2022 reconstruction entrypoint.

Everything upstream of that entrypoint is now pinned by path/commit/logic. The next run should resolve only this item by adding a research-only reconstruction entrypoint which imports the pinned V9/V7 implementation, calls `prepare(raw)` then `generate_tail_pool(q,"2022-06-01","2022-12-31")`, asserts 89 rows, applies exactly `med_ret5 <= 0` and `ret10 <= 0.5735294117647058`, asserts 29 rows / 23 unique dates, and writes both ledgers with SHA256 receipts. Do not use V16 backward n=31.

No 2023–25 regeneration, 2026 opening, return recomputation, or production/main modification is authorized by this receipt.