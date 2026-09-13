# Canonical Monster v2 ALL_WEAK_EARLY exact replay — 2026-09-14

Research-only. Production unchanged. 2026 outcomes were not opened.

## Why this replay was done

After closing the V12 reversal family and rejecting the distinct V20 compression-breakout discovery, the event-specific lane stopped generating adjacent heuristics and returned to the strongest previously documented Monster structure.

The frozen v2 spec already existed:
`tvfree_screener/batch01/reports/monster_canonical_v2_all_policy_spec.json`.

No v2 result report was present in GitHub, so this replay fills that reproducibility gap. The v2 rule was **not changed**.

## Exact frozen rule

Candidate family:
- preserved V7 Tail cache;
- `tail_cdf >= 0.999`;
- **previous official XTKS session** full-market median 5-session close return <= 0;
- signal-date `ret10 <= 0.5735294117647058`.

Selection:
- no volr20 ranking;
- no daily Top-N cap;
- select every eligible name;
- one immediately preceding official-session same-symbol cooldown;
- empty official sessions clear the one-session cooldown;
- symbol sort is deterministic only.

Target:
- next official XTKS session open to fifth official XTKS session close;
- canonical OHLCV actionability guards;
- 0%, 0.5%, 1% cost scenarios.

## Input reconstruction verification

Preserved Tail cache:
- SHA-256 `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`
- 1,306 rows, 2023-2025.

Canonical daily:
- SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.

XTKS calendar:
- SHA-256 `74ab2aaf72a0c055af31b461dd1b5776cf83eebc9576830954248aa03f518f68`.

The full-market `market_median_ret5_lag1` was rebuilt from the canonical daily source using the exact existing batch01 implementation: dense official-session close matrix -> 5-session pct_change converted to float32 -> exact row-wise finite median -> one official-session lag.

Pool receipt exactly reproduces canonical v1 known counts:
- 2023: **69** rows / 51 dates
- 2024: **138** rows / 77 dates
- 2025: **67** rows / 42 dates

This validates the market-gate reconstruction before evaluating v2.

## ALL_WEAK_EARLY cooldown effect

| Year | Pool | Selected after one-session cooldown |
|---|---:|---:|
| 2023 | 69 | **55** |
| 2024 | 138 | **109** |
| 2025 | 67 | **54** |

Canonical year-boundary purge is retained:
- 2023 cutoff 2023-12-29
- 2024 cutoff 2024-12-30
- 2025 cutoff 2025-12-30

Two selected late-2024 rows exit in January 2025 and are therefore marked `PURGED_SPLIT_BOUNDARY`.

## Development replay

### 2023

Selected 55 / resolved 54.

At 0.5% cost:
- mean **+1.476%**
- median **-1.513%**
- win 40.74%
- +20% **18.52%**
- +50% 5.56%
- -10% 37.04%
- -20% 16.67%
- mean excluding top winner **-0.494%**
- mean excluding top 3 winners **-3.270%**

The all-candidate cooldown policy is weaker than the uncooled parent-pool mean and remains strongly winner-dependent.

### 2024

Selected 109; 105 resolved after two actionability failures and two year-boundary purges.

At 0.5% cost:
- mean **+1.683%**
- median **-3.586%**
- win 42.86%
- +20% **15.24%**
- +50% 5.71%
- -10% 31.43%
- -20% 13.33%
- mean excluding top winner **+0.569%**
- mean excluding top 3 winners **-1.337%**

The family retains right-tail frequency but is still dependent on its largest winners.

## Locked 2025 replay

Selected **54 / resolved 54**.

At the frozen 0.5% cost:
- mean **+2.190%**
- median **-7.531%**
- win **37.04%**
- +10% 25.93%
- +20% **12.96%**
- +50% 5.56%
- -10% **35.19%**
- -20% 5.56%
- mean excluding top winner **-0.212%**
- mean excluding top 3 winners **-2.902%**

Frozen locked-replay gates:
- resolved n >=30: **PASS**
- mean >0: **PASS**
- +20% >=10%: **PASS**
- -10% <=40%: **PASS**
- mean excluding top winner >0: **FAIL**

Overall locked replay: **FAIL**.

At 0% cost, mean excluding the top winner is +0.288%, but the decision contract was frozen at 0.5% cost. The cost assumption is therefore not relaxed after seeing the result.

## Decision

**REJECT canonical Monster v2 ALL_WEAK_EARLY as a passed Monster policy.**

This exact replay confirms the previous partial handoff:
- the weak+early family does preserve an unusually high right-tail rate;
- but the unchanged ALL policy remains too winner-dependent at the frozen cost assumption.

This is stronger evidence than another threshold search. Do not rescue the policy by reintroducing a Top-N rank, changing the cooldown, or relaxing the cost/gate on already exposed 2023-2025 outcomes.

The family may remain useful as mechanism context or for unchanged prospective shadow logging, but it is not a passed replacement candidate.

2026 outcomes opened: false.
Production modified: false.
