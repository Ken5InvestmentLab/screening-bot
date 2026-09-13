# All-market winner/loser state audit — discovery

- Decision: `FREEZE_FOR_2024_CONFIRMATION`.
- Signal universe is every valid, positive-volume TSE daily bar with signal-day gap ratio in [0.60, 1.40]. No First Reversal prefilter or ranking is applied.
- Target: next XTKS session open through the fifth XTKS session close; large winner >= +10%, large loser <= -10%.
- Discovery signals are separately purged to 2022H2 and 2023. Candidate features were frozen before outcomes; 2024 outcomes remain unopened.
- This is descriptive feature research with repeated-symbol and cross-sectional dependence; effect sizes are not independent-sample significance tests.
- 2025+ features/outcomes were not used. DD60 is excluded because its previous First Reversal direction reversed in 2024; days-since-drop is excluded because missingness was ambiguous.

| Split | Eligible rows | Resolved | Winners >=10% | Losers <=-10% |
|---|---:|---:|---:|---:|
| 2022H2 | 398118 | 384563 | 9046 | 5937 |
| 2023 | 829740 | 810940 | 20729 | 14362 |
| discovery_pooled | 1244858 | 1211947 | 30091 | 20438 |

## Frozen discovery features

- `range_pct` — lower_for_winners, pooled Cliff's delta -0.1462, discovery tercile edges [0.013355592265725136, 0.02361111156642437].
- `dispersion20` — lower_for_winners, pooled Cliff's delta -0.1301, discovery tercile edges [0.011891510337591171, 0.01889415830373764].

Full per-feature effect sizes and period sample counts are in the JSON report.
