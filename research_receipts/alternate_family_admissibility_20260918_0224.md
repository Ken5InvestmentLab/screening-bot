# Alternate-family admissibility manifest

Scope: research-only. No production/main/workflow/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes. 2026 excluded. No performance recomputation.

## Decision rule
A PARKED family may be resumed only when existing evidence leaves at most one missing item between its frozen source/spec/code/input chain and canonical trade rows. Unknowns are fail-closed.

## core_bollinger_reclaim
- KNOWN source: prior Supervisor evidence classifies this family as `SOURCE_POOL_EXACT`.
- KNOWN code: no code SHA is presently bound to the `SOURCE_POOL_EXACT` evidence in the accessible repository/default-branch index.
- KNOWN input: source-pool exactness is asserted by existing evidence, but the concrete frozen input path/SHA needed to execute the selector is not presently bound in the recovered chain.
- KNOWN outcome: no performance calculation performed in this manifest.
- MISSING: (1) exact selector/spec/code SHA; (2) executable frozen input/source path/SHA and the deterministic source-pool-to-canonical-rows invocation/chain.
- Decision: PARKED. Missing chain count is greater than one, so it fails the Supervisor GO rule.

## strict_3pt
- KNOWN source/code/input/outcome: no new admissibility evidence recovered beyond the already-known PARKED status.
- MISSING: reproducible source/spec/code/input chain to canonical rows.
- Decision: PARKED / excluded from restart selection per Supervisor instruction because there is no new evidence.

## Cloud Monster
- KNOWN source/code/input/outcome: retained only as the last alternate family; no new admissibility evidence used here.
- MISSING: reproducible frozen source/spec/code/input chain to canonical rows under the current common endpoint protocol.
- Decision: PARKED. It remains last and is not selected ahead of core_bollinger_reclaim.

## Selection
No alternate family qualifies for restart GO in this pass. `core_bollinger_reclaim` remains the highest-priority PARKED family because SOURCE_POOL_EXACT evidence exists, but at least two independent links remain unbound. Therefore no canonical rows generation is authorized yet.

## Evidence checks performed for this manifest
- Repository code search for exact `SOURCE_POOL_EXACT`: no indexed default-branch hit.
- Repository code search for exact `core_bollinger_reclaim`: no indexed default-branch hit.
- Repository code search for exact `strict_3pt`: no indexed default-branch hit.
- Commit-message search for `bollinger reclaim`: no hit.

These negative checks are used only to count currently unbound links; they do not prove historical nonexistence and are not a broad provenance search.