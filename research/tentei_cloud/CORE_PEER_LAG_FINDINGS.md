# Core correlation-peer lag audit — 2026-09-14 JST

Research-only. Production, Discord, Spreadsheet, current Stable/Sniper/Mega, V12/V15 event-representation work, and legacy-4H reconstruction were not modified.

## Hypothesis

Test whether a Core candidate improves when highly correlated peers have already turned positive.

To avoid a current-only industry map and its survivorship bias, peers were defined causally from prices only:
- trailing 60 observed trading dates strictly before the candidate date;
- minimum 40 overlapping daily return observations;
- top 5 positively correlated symbols by Pearson correlation;
- at least 3 usable peers required;
- peer momentum uses only the prior session's already-known 1D / 5D returns.

Fixed gates:
- `PEER1_POS`: median prior-session 1D peer return > 0
- `PEER5_POS`: median prior-session 5D peer return > 0
- `PEER1_AND_5_POS`: both conditions

A gate could freeze only if BOTH DEV halves had n>=15, higher mean, no-worse median, and no-worse <=-10% rate versus the fixed Core baseline.

## Reproducibility

- trigger commit: `7db1ed57787f3915f5d40108e6e8d2255ac2e18c`
- workflow run: `34765505153`
- artifact: `10320032194`
- artifact ZIP SHA-256: `63b1063fe068ed9cf090ee1b05dfec77001efda2a6857784437a8ff1bee0fafe`
- script: `research/tentei_cloud/audit_core_peer_lag.py`

## Discovery result

### DEV_A — 2024-11 through 2025-02

| gate | n | mean | median | <=-10% |
|---|---:|---:|---:|---:|
| BASE | 67 | +0.00% | -0.28% | 2.99% |
| PEER1_POS | 21 | -0.25% | -0.97% | 4.76% |
| PEER5_POS | 30 | **-1.40%** | -1.54% | 6.67% |
| PEER1_AND_5_POS | 14 | -1.02% | -1.54% | 7.14% |

Positive peer momentum made the early DEV Core subset worse, especially on the 5D peer condition.

### DEV_B — 2025-03 through 2025-06

| gate | n | mean | median | <=-10% |
|---|---:|---:|---:|---:|
| BASE | 102 | +2.16% | +2.23% | 2.94% |
| PEER1_POS | 45 | +2.22% | +2.33% | 4.44% |
| PEER5_POS | 88 | **+2.45%** | +2.49% | 2.27% |
| PEER1_AND_5_POS | 42 | +2.41% | +2.62% | 4.76% |

The sign flips in the later DEV block: PEER5_POS is mildly beneficial there.

## Decision

**Reject the preregistered positive correlation-peer lag gate. No gate is frozen.**

The same condition is harmful in DEV_A and mildly beneficial in DEV_B, so there is no stable evidence that Core is a simple “follow peers/sector leadership” setup.

Do not rescue this experiment by immediately flipping the sign to “negative peer momentum” on the same opened data. That would be post-hoc tuning. A contrarian peer hypothesis, if ever tested, must be separately preregistered and preferably judged on genuinely new forward data.

Combined with the other independent Core audits, three simple pruning paths are now rejected:
1. broad-market hard regime gates;
2. single candidate-local hard filters;
3. positive peer-momentum hard gates.

Current evidence favors keeping the fixed Core broad rather than repeatedly filtering it.
