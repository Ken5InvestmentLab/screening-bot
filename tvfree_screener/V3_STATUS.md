# TV-Free V3 research status (TEST ONLY)

## Guardrails
- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord/Spreadsheet writes.
- No production Stable★6/Sniper/Mega/TradingView changes.
- Realistic entry: next trading session open.
- 2026 is contaminated; never tune to it.

## Reproducibility status
The first durable fixed-start pipeline is Actions run `34545440155` on head `5461eef6f35ea2cea2b4bc38ca7177c681681783`, and it completed successfully.

Verified fixed-start contract:
- Yahoo history: `2022-01-01 -> current`
- current JPX domestic common-stock universe: 3,700 symbols
- OHLCV rows: 4,061,361
- rows through frozen historical cutoff 2026-08-31: 4,031,154
- runtime: about 27m03s
- artifact: 51,126,879 bytes (~48.8 MiB)

Manifest v3 frozen hashes for run #80:
- universe: `271033ea30220e1731537a2b453d2f5bfffb9fbc29d7d43a46f8efd1f9f54cbe`
- historical date/symbol coverage: `2686163d4e4342198590d34a8708c5c142a11441befdd74da3475bafd3e9a935`
- historical OHLCV: `475ae6166ed21220aaa7f9f98d5bfff6c2d221bf1e3571b59fc6656758f453ab`
- Short Core: `5fbb16417b3cd87afcbba824ada77d912124c9c623aba470a1f1fa849a9df757`
- Short defensive: `063b9c63bda60c298feb84e8e3d0d5f935f46da9dbc5900ba297bac21fbc723d`
- Swing S: `0907e351e914a278e9a41f57f627c7fdb6f10ca43301139c1ba14154b070ceac`
- research contract: `63b40267f9cdc6018aab701f36f79b1e675b35350a0ac5e6c35532f4c6046058`

Later test-only overlay/audit changes intentionally alter the research-contract hash. Run #80 remains the frozen numeric baseline for comparison; do not interpret a contract-hash change as market-data drift.

## V3 Short (5BD)
Historical non-reproducible old reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed.

`v3_short_reconstruction.py` is executable and implements the same 45 `run.py` features, monthly causal 180-tree XGBoost, prediction-day percentile normalization, Core `r_top10 - 2*r_loss10`, one-day same-symbol cooldown, next-open -> 5BD, rejected/inactive recent-outcome Meta, and no accepted Attack.

Durable fixed-start run #80:
- Core 2025H1: n=119 mean +0.69%, median +0.45%, win 55.5%, +10% 3.36%, -10% 2.52%.
- Core 2025H2: n=124 mean +0.26%, median +0.58%, win 53.2%, +10% 0%, -10% 0%.
- Core 2026 Mar-Aug reporting-only: n=124 mean +0.015%, median -0.13%, win 47.6%, +10% 1.61%, -10% 0.81%.
- Defensive 2026 Mar-Aug reporting-only: n=97 mean +0.14%, median 0%, win 48.5%, +10% 2.06%, -10% 1.03%.

The prior rolling-3y values remain historical context only. Short Core is reproducible but weak relative to the Stable★6 reference.

Attack:
- Whole-universe Attack heads rejected.
- Distinct event-family Attack: 10/10 variants failed pre-2026 robustness; 2026 was not opened for those candidates.
- Short Attack = none/unaccepted.

## V3 Swing (10BD)
Frozen architecture: `v3_swing_v2.py`, MomCross -> causal semiannual quality model -> training CDF -> Breadth Meta -> `score_R >= 0.20`.

Durable fixed-start run #80 at unchanged frozen threshold 0.20:
- 2025H1 10BD: n=36 mean -0.14%, median -1.96%, win 36.1%, +10% 11.1%, -10% 2.78%.
- 2025H2 10BD: n=24 mean +2.68%, median +0.90%, win 54.2%, +10% 12.5%, -10% 0%.
- 2026 Mar-Aug reporting-only 10BD: n=27 mean +0.017%, median 0%, win 48.1%, +10% 7.41%, -10% 7.41%.

The earlier rolling-3y +6% results did not reproduce under the durable fixed-start contract. This is a material negative finding: Swing S is not accepted as durable replacement evidence. Do NOT retune the 0.20 threshold using 2026. Swing A remains none/unaccepted.

## Operational snapshot
Durable fixed-start run `34545440155`:
- total runtime about 27m03s,
- artifact 51,126,879 bytes (~48.8 MiB),
- job timeout 90 minutes,
- all synthetic checks and all heavy research steps passed.

## Current decision
- Short Core: reproducible fixed-start baseline established; performance is too weak to displace Stable★6.
- Short defensive gate: supporting only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: fixed-start performance failed to reproduce the old rolling advantage; not accepted as durable replacement evidence.
- Swing A: none.
- Fundamental/dilution overlays: research-only; missing-data safety is being hardened before any performance comparison.
- Production migration: blocked pending explicit user Go.

## Next
1. Validate the corrected missing-data/coverage-matched overlay semantics in CI.
2. Live-validate JPX point-in-time membership reconstruction and then quantify Yahoo coverage for delisted members/code reuse.
3. Add 2024H1/H2 reporting to frozen technical runners without tuning from 2026.
4. Live-validate EDINET accounting and dilution evidence once `EDINET_API_KEY` is available.
5. Continue testing stronger causal technical architectures against the fixed-start baseline; reject unstable gains.
