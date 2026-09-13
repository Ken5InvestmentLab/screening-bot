# Frozen Top-N policy diagnostic

- Status: exploratory only; no policy promotion.
- All four pre-outcome Top-N selections were evaluated together; no parameter search or threshold change.
- The original full-pool gate was inconclusive because every active day had unresolved candidates.
- Unresolved selected rows remain in requested counts; resolved-return summaries are explicitly conditional on resolved labels.
- 2024, 2025, and 2026 outcomes remain closed.
- Full-pool net mean / median / win: -0.003996591923047243 / -0.005 / 0.41654879773691655.

| Top-N | n | resolved | net mean | median | win | +10% | -10% | complete policy days | unresolved |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 365 | 252 | -0.0014325493921127442 | -0.005 | 0.3968253968253968 | 0.023809523809523808 | 0.007936507936507936 | 252 | 113 |
| 2 | 730 | 545 | -0.0009210042557743944 | -0.005 | 0.40625 | 0.023853211009174313 | 0.007339449541284404 | 196 | 185 |
| 3 | 1095 | 842 | -0.0011511378989131277 | -0.005 | 0.40309155766944116 | 0.02494061757719715 | 0.013064133016627079 | 167 | 253 |
| 5 | 1825 | 1486 | -0.0009547053064138586 | -0.005 | 0.4056603773584906 | 0.02489905787348587 | 0.013458950201884253 | 132 | 339 |

The local current Bot benchmark report (generated 2026-09-09) lists Stable ★6 at n=55, mean +6.6%, median +1.5%, win 56.4%. This is context only: its BOTTOM-signal population and signal-close target differ from this all-TSE, next-session-open experiment, so the figures are not directly comparable.
