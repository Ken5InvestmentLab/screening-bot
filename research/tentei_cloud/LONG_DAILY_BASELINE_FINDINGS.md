# TV-free long-horizon direct semantic baseline — 2026-09-14 JST

Research-only. No production, Core, Monster, V20 prospective-shadow, or current report logic was modified.

## Purpose

Test the most direct TV-free interpretation of the current Mega40 semantics:

- **Deep**: 20-day high drawdown >=15%, previous three completed daily closes descending, BB(20,2) position <=20%, bullish body >=2%.
- **Wick**: 20-day high drawdown >=15%, CCI(20)<=-100, lower wick >=50% of candle range, current close > close 26 sessions ago.

Unlike the current report logic, these conditions were applied directly to the TV-free daily TSE universe without requiring a TradingView/BOTTOM event.

Two fixed universe variants were declared in advance:
- CAP1000: previous close <=1000 JPY plus liquidity filters.
- NO_PRICE_CAP: same liquidity filters, no price cap.

Primary entry was the next trading day's first Yahoo 1H open. Same-symbol cooldown was fixed at 5 business dates. No result-dependent threshold sweep was allowed.

## Reproducibility

- trigger commit: `a81e946fc1a5fca914128adbc659659c9296e403`
- workflow run: `34788285067`
- artifact: `10327507225`
- artifact ZIP SHA-256: `c7b49e043865a3e4677d07310334975eb66c955f386e8bd26c274b0378b67321`
- script: `research/tentei_cloud/audit_long_daily_baseline.py`

## Result

### CAP1000 Deep

Executable next-open entry:

- DEV 2025H1: n561, mean **+18.47%**, median +14.46%, win 82.89%, >=30% 18.54%, >=50% 7.49%, <=-20% 2.67%, top-5-removed mean +16.68%.
- VALID 2025H2: n289, mean **-0.44%**, median -2.74%, win 41.87%, >=30% 5.54%, <=-20% 17.65%, top-5-removed mean -3.41%.
- 2026 matured: n475, mean **-0.86%**, median -4.14%, win 36.63%, >=30% 6.11%, >=50% 2.32%, <=-20% 18.95%, top-5-removed mean -4.02%.

The spectacular DEV result completely failed to persist.

### CAP1000 Wick

Executable next-open entry:

- DEV: n101, mean **+10.48%**, median +2.90%, win 59.41%, >=30% 16.83%.
- VALID: n79, mean **+3.03%**, median -8.00%, win 29.11%, <=-20% 16.46%, top-5-removed mean -7.16%.
- 2026 matured: n111, mean **-1.00%**, median -7.76%, win 28.83%, <=-20% 17.12%, top-5-removed mean -7.34%.

The positive VALID mean is tail-driven and does not represent a stable long-horizon lane.

### Removing the 1,000 JPY cap

Removing the price cap did not improve this baseline.

Executable next-open:
- NO_PRICE_CAP Deep VALID: -2.04%; 2026: -1.65%.
- NO_PRICE_CAP Wick VALID: -0.03%; 2026: -1.84%.

For this specific long-horizon direct-semantic baseline, CAP1000 was less bad. This does **not** reinstate the 1,000 JPY rule globally; it only rejects “remove the cap and the Mega40 direct baseline improves” on this experiment.

## Decision

**Reject direct daily application of the published Mega40 semantic conditions as the TV-free long-horizon replacement.**

The published four-condition overlays are not sufficient by themselves. The current system's event timing — the fact that these overlays are evaluated around a BOTTOM-like event — appears to carry major information.

Do not:
- tune the -15%, BB20%, body2%, CCI, wick, or 26-session thresholds on these opened results;
- rescue the baseline with a post-hoc price threshold;
- call the strong 2025H1 block validation.

## Next architecture step

The long-horizon lane needs a causal TV-free **event entrance** plus the long-horizon overlay.

The parallel canonical/V20 lane already owns TV-free event reconstruction, PIT/source contracts, and prospective-shadow infrastructure. This branch must not duplicate that work.

Next task:
- inspect the frozen V20 event specifications and persisted event detections;
- consume an existing canonical event stream if available;
- evaluate Mega40-style 40BD overlays on top of that event stream;
- if no stable export exists, define the consumer/export contract and mark long-horizon evaluation blocked on that canonical event source rather than inventing a competing event detector here.
