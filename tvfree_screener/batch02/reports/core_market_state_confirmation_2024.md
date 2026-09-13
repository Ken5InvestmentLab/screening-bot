# All-market winner/loser state audit — 2024 confirmation

- Decision: `REJECT_ALL_MARKET_STATE_FEATURES`.
- 2024 was opened only after the discovery feature freeze; it is historical directional confirmation, not untouched OOS.
- 2025+ features/outcomes were not opened. A failure rejects this feature family without replacement search or threshold changes.

| Feature | Discovery direction | 2024 Cliff delta | Median delta | Effect sign | Outer tercile winner-share direction | Counts sufficient | Confirmed |
|---|---|---:|---:|---|---|---|---|
| range_pct | lower_for_winners | 0.10374247641220857 | 0.005156004801392555 | False | high=0.5443760324373029, low=0.44209514656415183 | True | False |
| dispersion20 | lower_for_winners | 0.15879134350000323 | 0.0065314387902617455 | False | high=0.5697008664768378, low=0.3633254969010472 | True | False |

Resolved outcomes: 828077 of 844820; cost scenarios are in the JSON report.
