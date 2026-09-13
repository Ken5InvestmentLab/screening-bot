# Consensus reconstructed stable_score provenance — 2026-09-14

Research-only provenance audit. No model or production behavior changed.

## Finding

Consensus V11/V43/V44 includes a feature named `stable_score`.

Despite the name, this feature is **not read from TradingView or from the production Stable★6 bot at runtime**.

It is recomputed locally from the causal Yahoo-derived as-of OHLCV frame inside `research/no_tv_v10_standalone.py::technical_features()`.

The six Boolean components are:
1. current as-of close > EMA25;
2. MACD histogram > 0;
3. stochastic(14) >= 75;
4. Bollinger position >= 0.80;
5. the prior three completed closes form a down sequence;
6. current as-of open > previous completed close (gap up).

`stable_score` is simply the integer sum of those six bits (0..6).

V11 then uses:
- the regular standalone features;
- this locally reconstructed 0..6 score;
- cross-sectional ranks;
- market/session regime features.

## Runtime dependency conclusion

- TradingView signal required: **NO**
- production Stable★6 score required: **NO**
- historical TV teacher required by V43/V44 execution: **NO**
- Yahoo OHLCV / reconstructed as-of frame required: **YES**

Therefore the Consensus family remains valid as a TradingView-free runtime candidate.

## Naming caution

The name `stable_score` is potentially misleading because it sounds like a dependency on legacy Stable★6.

It should be treated conceptually as a **six-bit technical composite feature**, not as a Stable★6 oracle.

If Consensus survives V44/V45 and proceeds toward a new clean implementation, rename this feature (for example `technical_bits6`) in a versioned refactor so the replacement architecture does not imply a dependency on the retired system. Do not rename it during the frozen V44 evaluation because that would unnecessarily alter the tested code path.
