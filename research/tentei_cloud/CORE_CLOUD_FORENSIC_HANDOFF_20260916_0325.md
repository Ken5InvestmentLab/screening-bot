# Core + Cloud forensic handoff — 2026-09-16 03:25 JST

Core P0 advanced from verified JPX transfer URL/schema provenance to an actual exact-byte capture attempt.

- Core branch commit `7457709559f35f7cae1c2488998bcbeae0d37083` adds transfer current/2025/2024 to the existing research-only byte-preserving capture script.
- Research-only Actions run `35007416840` was triggered and was queued when inspected.
- Byte-pin is **not yet PASS**; collect the terminal run and inspect the artifact receipt before promoting provenance.
- PIT remains FAIL-CLOSED. Legacy 375-event receipt remains non-canonical pending the 375-vs-395 row audit and segment-transfer integration.
- Cloud exact forensic remains CLOSED / `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no guessing or surrogate promotion.
- No new performance was opened. Cost policy remains 0% only for any future new performance; win = gross return > 0.

Next: collect run 35007416840 → freeze transfer bytes/SHA receipt → deterministic transfer ledger → 375-vs-395 audit → conflict-checked reverse replay/PIT receipt.
