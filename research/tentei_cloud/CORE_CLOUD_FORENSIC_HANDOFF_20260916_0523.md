# Core + Cloud forensic handoff — 2026-09-16 05:23 JST

## Canonical Core status
- Exact-byte JPX provenance remains PASS.
- Anchor: 2026-08-31, 3,707 eligible domestic Prime/Standard/Growth codes.
- IMPORTANT: prior `375 = 134 + 241` listing/delisting count is superseded again. Root cause: JPX uses `May` without a period; period-required parser silently omitted valid May delistings.
- Correct through 2026-09-10: **134 listings + 263 delistings = 397**.
- Reverse replay `(2024-09-17, 2026-08-31]`: **134 listings + 261 delistings + 81 transfers = 476 events**.
- Strict reverse replay: quarantine/conflicts **0**; target membership **3,834**.
- Sorted `CODE,SEGMENT\n` membership SHA-256: `9f54f11242b0c6b510de44b3b9adc900a9892d43ed084b70b9d9eda1cec1332e`.

## Parser rule
Date parsing must be row-wise and accept `%b. %d, %Y` and `%b %d, %Y`; unknown non-empty dates fail closed. Do not use vectorized coercion.

## Next P0
Freeze machine-readable PIT membership receipt binding source SHAs, parser contract, event counts, target count/SHA and zero-quarantine result. Then proceed to independent exact-hour activity evidence. Membership alone must never generate expected hourly keys.

Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no family guessing. All new performance remains cost 0% only; none was opened this run.