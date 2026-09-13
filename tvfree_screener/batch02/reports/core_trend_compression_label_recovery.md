# Core Trend Compression: canonical label-coverage recovery

- Evidence: retrospective repair diagnostic; not untouched OOS.
- The prior Top-N resolved-only summaries are invalid because labels were scoped to a different model's eligible rows.
- Full candidate pool labels were rebuilt from the saved decision-only daily OHLCV panel; all frozen candidate rows were retained.
- Top1/2/3/5 choices, rank, features, thresholds, cooldown, and period were unchanged.
- No policy is promoted by this report. 2024+ numeric OHLCV was not opened.
- Primary net return subtracts a hypothetical 0.5% round-trip cost; cost is not measured execution friction.

| Frozen Top-N | selected | resolved | unresolved | net mean | median | win | +10% | +20% | +50% | -10% | -20% | top1 removed mean | top3 removed mean | complete days | family gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 365 | 276 | 89 | -0.0014071620834561849 | -0.005 | 0.391304347826087 | 0.021739130434782608 | 0.0 | 0.0 | 0.007246376811594203 | 0.0036231884057971015 | -0.0018673911104807688 | -0.0027070790831562517 | 276 | REJECT_FROZEN_POLICY |
| 2 | 730 | 600 | 130 | -0.0008507908023119518 | -0.005 | 0.4073455759599332 | 0.021666666666666667 | 0.0016666666666666668 | 0.0 | 0.006666666666666667 | 0.0016666666666666668 | -0.0011890507490490891 | -0.0017541258099616503 | 243 | REJECT_FROZEN_POLICY |
| 3 | 1095 | 916 | 179 | -0.0008472710922005308 | -0.005 | 0.40765027322404374 | 0.024017467248908297 | 0.004366812227074236 | 0.0 | 0.012008733624454149 | 0.0032751091703056767 | -0.0013897746434060716 | -0.0020033294551513995 | 212 | REJECT_FROZEN_POLICY |
| 5 | 1825 | 1582 | 243 | -0.0008206928065559715 | -0.005 | 0.40632911392405063 | 0.02465233881163085 | 0.006321112515802781 | 0.0006321112515802782 | 0.012642225031605562 | 0.0018963337547408343 | -0.0012129830891043551 | -0.0017412799038200766 | 175 | REJECT_FROZEN_POLICY |

The current Bot benchmark in the frozen diagnostic spec is not directly comparable: it uses BOTTOM-signal events and a different entry/target definition.
