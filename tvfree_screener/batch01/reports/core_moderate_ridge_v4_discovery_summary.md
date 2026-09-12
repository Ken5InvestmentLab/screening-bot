# Core Ridge attempt 04 discovery

- Decision: `REJECT_CORE_RIDGE_NO_TOP_N_POLICY_PASSED`.
- Spec SHA-256: `b85b6f38bae730fbe4b4066cdaac649a19965b2a3a3475ffb9662d44a2a91596`.
- Full report SHA-256: `28742e2dd8f929ffad516b0eacd3bdd200a7ce27ca257b92890cc194afd81923`.
- Evidence level: `RETROSPECTIVE_PROVISIONAL`. Attempt03 may have partially accessed 2022H2–2023 discovery OHLCV; attempt04 is the disclosed engineering replay of the unchanged frozen strategy.
- Period: 2022H2–2023 only. 2024 confirmation and 2025/2026 outcomes were not opened.

The full eligible daily candidate pool contained 1,215,777 rows across 365 active dates, averaging 3,330.9 candidates/day and reaching 3,452 on the largest date. The pool had 1,192,068 resolved and 23,709 unresolved five-session labels. At the assumed 0.5% round-trip cost, the resolved pool mean was -0.2845%, median -0.5000%, +10% rate 2.19%, +20% rate 0.48%, +50% rate 0.046%, -10% rate 1.87%, and -20% rate 0.187%. No candidate rows were capped to one name/day.

| Independent daily selection policy | Selected / resolved | Net mean | Net median | Win rate | +10% | +20% | +50% | -10% | -20% | All gates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Top-1 | 365 / 358 | -0.561% | -1.359% | 37.7% | 7.54% | 1.40% | 0.56% | 5.87% | 0.28% | Fail |
| Top-2 | 730 / 721 | -0.434% | -0.778% | 38.7% | 7.07% | 1.80% | 0.28% | 5.55% | 0.42% | Fail |
| Top-3 | 1,095 / 1,079 | -0.442% | -0.903% | 37.9% | 6.67% | 1.76% | 0.28% | 5.47% | 0.37% | Fail |
| Top-5 | 1,825 / 1,800 | -0.297% | -0.678% | 39.5% | 6.94% | 1.83% | 0.17% | 5.72% | 0.56% | Fail |

All four policies also had negative mean after removing their top three winners. The frozen ranking-value-add test could not be evaluated: none of the 365 full-pool daily cohorts was completely resolved, leaving zero common complete dates. This limitation is retained rather than silently dropping unresolved candidates or changing the frozen gate. No Top-N lock was created and 2024 remains closed.

The estimated 0.5% round-trip cost is a sensitivity assumption, not measured execution cost. The preserved Yahoo-derived universe is not point-in-time membership and does not prove historical delisted coverage, corporate-action adjustment, or executable fills.
