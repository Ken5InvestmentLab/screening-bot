# Fixed Core cluster-risk findings — 2026-09-14 JST

Research-only descriptive audit. No signal filtering, threshold tuning, production write, Discord change, or V20 work was modified.

## Question

Do same-day Core signal bursts behave as a stable downside-risk proxy?

Fixed operational density buckets:
- N1 = 1 signal/day
- N2 = 2
- N3_4 = 3-4
- N5_PLUS = 5+

These buckets were not optimized and are not eligible to become a new historical filter from this audit.

## Reproducibility

- trigger commit: `5181e3690275fdea03289d9b05f3e650a16e4471`
- workflow run: `34787773571`
- artifact: `10326733411`
- artifact ZIP SHA-256: `ed99bc0c87b7895b01b50daf63677d60616db2bcecde7e2e4d9f7d1a5545b65a`
- script: `research/tentei_cloud/audit_core_cluster_risk.py`

## Result: density sign is non-stationary

### DEV

5+ signal days were unusually strong:
- n73 candidates
- mean **+3.33%**
- median **+3.34%**
- win **79.45%**
- <=-10% **0%**

This includes the April 2025 burst:
- 2025-04-16: 26 signals, day mean +5.80%
- 2025-04-17: 25 signals, day mean +3.92%

### 2025H2

The sign reverses:
- 5+ bucket n32
- mean **-1.30%**
- median -1.72%
- win 28.13%

Examples:
- 2025-10-27: 12 signals, day mean -2.95%
- 2025-12-01: 8 signals, day mean -1.11%

### 2026 Jan-Aug

The sign becomes positive again:
- 5+ bucket n16
- mean **+3.22%**
- median +1.91%
- win 62.5%
- <=-10% 0%

Only two 5+ signal days occurred:
- 2026-03-03: 5 signals, all 5 winners, day mean +4.61%
- 2026-04-10: 11 signals, day mean +2.59%

2026's two <=-10% Core outcomes did **not** occur on 5+ signal days.

## Decision

**Signal density is not a validated risk score.**

Do not:
- suppress burst-day Core signals;
- lower Core confidence merely because many signals appear together;
- use 5+ signals/day as a negative market-regime proxy;
- use the strong DEV/2026 burst performance as a positive filter either.

The direction changed materially across historical blocks.

Operational use only:
- display a neutral `集中発生` / `clustered signals` context marker when many Core candidates arrive together;
- the marker means “many correlated opportunities may require more capital / attention,” not “bad signal”;
- preserve every candidate.

This reinforces the separation between:
- signal quality logic; and
- downstream notification/capital-capacity context.
