# Multi-event quality score — 2024 development

- Decision: `REJECT_MULTI_EVENT_QUALITY`.
- 2024 is retrospective development, not OOS. 2025+ data were not read.
- Each model variant may select up to five names per XTKS session; same-symbol one-session cooldown is applied after score gating.

| Variant | H1 n | H1 net mean | H1 net median | H1 win | H2 n | H2 net mean | H2 net median | H2 win | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| balanced | 597 | -0.2443% | -0.3681% | 46.7% | 589 | -0.7718% | -0.7413% | 39.0% | False |
| winner_aware | 597 | -0.2394% | -0.5000% | 44.7% | 590 | -0.6747% | -0.6378% | 41.8% | False |
| defensive | 597 | -0.2177% | -0.5000% | 45.4% | 589 | -0.8398% | -0.6859% | 39.2% | False |
| balanced_high_gate | 597 | -0.2443% | -0.3681% | 46.7% | 584 | -0.7693% | -0.7189% | 39.0% | False |

The JSON report contains all win/loss thresholds, top-winner exclusions, monthly/weekly cohorts, bootstrap intervals, symbol concentration, unresolved counts, and the frozen variant scores.
