# Core + Cloud handoff — 2026-09-15 06:26 JST

## Frozen status
- Cloud exact: **CLOSED / HISTORICAL_EXACT_REPRO_UNAVAILABLE**. Reopen only on genuinely new contemporaneous identity-critical evidence.
- Old Cloud Monster `n=63 / 5BD mean +9.86%`: historical evidence only, never a reproduced result.
- current fixed Core, Failed-Breakdown Reclaim, Prior-Close Reclaim, Precision 3-family and other rejected families: closed; no retune/rescue.
- performance unopened; all future new performance cost 0% only; win = gross return > 0; 2026 report-only.

## Material advance this run
The exact successful extended Yahoo raw1H source was recovered:
- workflow run: `34592896202`
- trigger/source HEAD: `a331b96c8b7391a146ed3a8d28dd5e66d6ae0679`
- eight retained artifacts: `tentei-cloud-1h-shard-0` through `-7`
- raw manifest: **PASS**
- rows: **4,019,524**
- timestamp envelope: `2024-09-17 09:00:00+0900` → `2026-09-10 15:00:00+0900`
- raw bundle SHA-256: `de7710adaf52ba5a1fb783e7bde35feea9528294be557ef4e011dc4be7e8ed18`

Exact per-shard SHA/size/row/symbol/timestamp/artifact identity is frozen in `RAW1H_ARTIFACT_PIN_20260915_0626.json`. The formal rules are in `CORE_RAW1H_ARTIFACT_PIN_SPEC_20260915.md`.

Historical failure receipts also cross-check exactly: 272 failed chunks / 61 symbols / HTTP400=153 / HTTP404=119. Existing forensic classification remains 44 before-first-only, 17 never observed, 0 detected internal-overlap failures.

## Important retention caveat
The GitHub artifacts expire on 2026-09-25. The repo receipt pins the exact identity of the downloaded bytes but does not itself make those ~250 MB raw bytes permanently available after expiry. Do not claim durable raw-byte archive without a separate storage receipt.

## Exact continuation
The previous raw-byte blocker is resolved. The remaining formal gate is the **exact expected endpoint-key universe**.

Next worker should:
1. reconstruct/pin the expected endpoint-key CSV from outcome-blind historical eligibility evidence: target universe + XTKS sessions + point-in-time listing/delisting boundaries;
2. explicitly preserve delisted/provider-truncated cases rather than silently excluding them;
3. bind expected CSV SHA-256;
4. run `missing_inventory_runner.py` exactly once against the pinned observed bytes;
5. acquire fallback only for declared missing pairs and record accepted/rejected/conflicted + coverage delta;
6. keep performance closed until that gate passes.

Do not use a naive full Cartesian `symbols × timestamps` expansion as proof of historical expected keys. Do not synthesize intraday from Alpha Vantage free daily or Google Finance snapshots.
