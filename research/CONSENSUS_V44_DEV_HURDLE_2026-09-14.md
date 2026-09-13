# V44 development hurdle context — 2026-09-14

Research-only arithmetic context. No rule is changed.

Frozen H1 baseline (2025-01-06..2025-06-30):
- cooldown0 n=67
- next-open mean = +8.42415%
- original DEV retention gate = 80%
- required retained mean = **+6.73932%**

Simple no-replacement cooldown stress on the same frozen Top-1 selections:

### 3 sessions
- n=33
- mean +3.51839%
- 34 baseline slots are suppressed.

If the retained 33 trades stayed identical and all 34 suppressed slots were filled one-for-one, the replacement trades would need an average of roughly **+9.87%** to restore the full 67-trade portfolio to the +6.73932% DEV gate.

### 5 sessions
- n=30
- mean +2.66403%
- 37 baseline slots are suppressed.

Under the same simplifying one-for-one assumption, the replacement trades would need an average of roughly **+10.04%** to restore the full 67-trade portfolio to the +6.73932% DEV gate.

This is only a hurdle diagnostic:
- actual V44 state changes can alter which later candidates remain blocked/available;
- V44 may not fill every suppressed slot;
- no replacement outcome is inferred from this arithmetic.

Interpretation: the frozen 80% DEV-retention requirement is demanding. A V44 pass would indicate genuinely strong alternative names rather than a cosmetic reduction in concentration.


## Where the strict5 replacement demand comes from

Within the 2025H1 fixed-min95 + frozen-ATR Top-1 baseline:
- raw selected rows: 67
- strict 5-session no-replacement rows: 30
- suppressed rows needing replacement to keep the original opportunity count: 37

Suppressed-row count by symbol:
- **3350: 24 / 37 (64.9%)**
- 2334: 4
- 7318: 4
- 3137: 1
- 8107: 1
- 2315: 1
- 7409: 1
- 6574: 1

Therefore V44 is not mostly solving dozens of unrelated duplicate problems. Its largest test is whether the ranker can substitute credible alternatives while a single persistent winner (3350) is already occupied.

This makes the test especially informative:
- if replacements retain performance, Consensus has broader cross-sectional information than the Top-1 headline suggests;
- if replacements collapse, the 2025H1 edge is strongly tied to repeated exposure to the same exceptional trend.
