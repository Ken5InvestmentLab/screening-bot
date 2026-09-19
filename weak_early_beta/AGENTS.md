# Weak+Early Beta Guidance

- Keep this beta isolated from `screener.js`, `index.js`, `current_logic*.json`, the existing Mega report/gate, production Discord channels, and Google Sheets.
- Preserve the five frozen selector IDs, fixed gates, causal monthly timing, Tail threshold, rank direction, tie-break, and no-cooldown contract. Japanese display names may change without changing internal identities.
- Combined results must show both allocations: 100 shares per matched condition (`all_conditions_stacked`) and 100 shares per signal-date/symbol (`all_conditions_unique`). Do not describe overlapping selectors as independent evidence.
- Historical canonical rows remain `not_requested_historical`; only forward causal detections enter the fundamental queue. Fundamental worker state must stay under `weak_early_beta/fundamental_worker/` and must never reuse production Premium state.
- Regenerate outputs with `python -m weak_early_beta.cli report`, test with `python -m unittest tests.test_weak_early_beta`, and verify the separate gate with `cd weak-early-beta-gate && npm run check`.
