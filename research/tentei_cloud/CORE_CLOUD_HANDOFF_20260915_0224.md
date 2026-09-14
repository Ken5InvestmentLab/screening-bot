# Core + Cloud handoff — 2026-09-15 02:24 JST

## Decision state
- Fixed Core and all previously rejected Core families remain closed; no retuning.
- Cloud Monster exact replay remains unavailable. Historical `n=63 / 5BD mean +9.86%` is legacy forensic evidence only, not a reproduced result.
- New OHLCV supplementation work is **data-plane only**. Formal dataset adoption and strategy performance recomputation remain prohibited until the Supervisor acceptance handoff is complete.

## Core/Cloud branch
Current implementation sequence advanced from prior processed HEAD `adca8963302644857e4bb05f668e660c84bffb82` through:
- `64285861fcea7c52170ede078740d3104e31a1cf` — fail-closed supplement verifier
- `a0fa4a190bc37684fc555d6864e2d0b31092ac08` — frozen source policy
- `1e984993a1f538a0eee4ce56e4ade265259952a3` — contract tests
- `680bb021af67a8249c4e8e714ee889176870ed8f` — CI workflow; run `34874773548` SUCCESS
- `d2f24b99d66c2cbfa6dbc3f1aa6e1d623973c3be` — additional source-priority guard; run `34874848913` in progress at handoff time
- later log/handoff-only commits do not change the data-plane implementation contract.

## Frozen fallback policy
1. `yahoo_chart_api_native`: native path, exact observed data only; no new HTML scraping.
2. `stooq_intraday_candidate`: registered but formal_eligible=false until overlap/provenance/timestamp/adjustment checks pass.
3. `alpha_vantage_free`: low-priority, formal daily-only fallback; may not repair 1H/4H by synthesis.
4. `alpha_vantage_intraday_premium`: disabled unless entitlement and provenance are explicitly verified.
5. `googlefinance_snapshot`: non-formal corroboration/future snapshot collection only.
6. Unresolved/conflicted pair => fail closed.

## What the verifier now proves
- pair existed in predeclared missing inventory before supplementation;
- exact symbol/timestamp/timeframe normalization;
- finite positive OHLC, consistent high/low, nonnegative volume;
- source registration + timeframe eligibility;
- raw SHA-256 presence;
- represented market timestamp does not exceed the endpoint/decision boundary;
- later acquisition is allowed only as historical repair of the same completed interval;
- conflicting formal sources are excluded rather than averaged;
- deterministic frozen source priority is used only when eligible sources agree exactly;
- no interpolation / forward-fill / back-fill / daily-to-intraday synthesis / performance-aware source choice.

## Missing Supervisor handoff items
Still required before formal adoption:
- exact real missing-pair inventory;
- real raw payload/file receipts for each fallback acquisition;
- accepted/rejected/conflicted counts by source and month;
- deterministic verifier output on the real gap set;
- coverage delta before/after supplementation;
- for Stooq or any new vendor: overlap agreement + timestamp/session + adjustment-policy verification;
- real XTKS/vendor endpoint manifest and canonical evaluator wiring remain independently required for formal Core returns.

No performance opened in this run. Future new performance remains cost 0%, win = gross return > 0; 2026 report-only.
