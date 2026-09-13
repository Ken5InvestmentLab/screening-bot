# Consensus independence from reconstructed Stable bits — 2026-09-14

Research-only audit. No model parameters or production behavior changed.

## Question

Consensus includes a locally reconstructed six-bit technical composite feature named `stable_score`.

Even though that feature is TradingView-free, the replacement would still be conceptually weak if Consensus simply selected reconstructed score=6 names.

## Existing V43/V42 selected-artifact audit

### 2025 fixed-min95, before ATR gate

n=112.

Distribution:
- score 0: 6
- score 1: 19
- score 2: 26
- score 3: 18
- score 4: 23
- score 5: 20
- score 6: **0**

### 2025 fixed-min95 + frozen ATR OOD gate

n=101.

Distribution:
- score 0: 4
- score 1: 17
- score 2: 26
- score 3: 14
- score 4: 21
- score 5: 19
- score 6: **0**

Median reconstructed score = 3.

Spearman relationships inside the selected gated set:
- `stable_score` vs `cons_min`: about **+0.095**
- `stable_score` vs `p_win`: about -0.123
- `stable_score` vs `p_hit10`: about +0.038
- `stable_score` vs `pred_ret`: about -0.128

As expected, `rank_stable_score` itself is highly correlated with the raw score because it is the cross-sectional rank of that feature, but the final three-head consensus is not dominated by it.

### 2026 fixed-min95 descriptive set

n=69.

The selected set spans score 0 through 6:
- 0: 5
- 1: 24
- 2: 14
- 3: 11
- 4: 6
- 5: 7
- 6: 2

The 2026 collapse occurs across reconstructed-score levels rather than being a score=6-specific failure.

## Conclusion

Current Consensus is **not a reconstructed Stable★6 filter in disguise**.

The six-bit composite is one model feature among many. The selected population is broad across that feature and, in 2025, contains no score=6 rows at all.

Therefore:
- runtime remains TradingView-free;
- legacy Stable★6 is not a required component;
- the family can continue to be evaluated as an independent replacement/specialist architecture.

If the family survives V44/V45, rename `stable_score` to a neutral name such as `technical_bits6` only in a later versioned refactor, not inside the frozen V44 code path.
