# Core + Cloud handoff — 2026-09-16 23:24 JST

## P0 result
Recovered the preserved V7 causal tail cache from Actions run `34600083474`, artifact `10264251140` and deterministically regenerated all five frozen Phase2 2023-2025 candidates. The regenerated n/mean/median/win match the frozen anchors exactly.

Endpoint audit against pinned daily corpus artifact `10264205130`:
- body_pct LOW: 172 trades / 344 required O/C fields / true missing 0 / invalid endpoint rows 0
- volr20 LOW: 172 / 344 / 0 / 0
- mean-rank: 172 / 344 / 0 / 0
- DUAL_TOP1: 140 / 280 / 0 / 0
- DUAL+G3: 117 / 234 / 0 / 0

Therefore frozen 2023-2025 performance anchors have zero direct OHLC endpoint-missing impact. The known 797 daily OHLC-order violations do not intersect these endpoints.

Receipt: `CORE_FIVE_CANDIDATE_ENDPOINT_COVERAGE_RECEIPT_20260916_2324.json`.

## Next
Recover the frozen 2022 fresh-validation rows/generator under unchanged history rules and run the same endpoint audit. Do not open 2026 until deterministic historical recovery requirements are satisfied. exact-hour/activity remains separate SEALED work.

No production/main/integration changes; no retune; no silent OHLC repair.
