# TV-Free batch02 research instructions

- Keep all edits under this research-only package; production files and integrations are outside scope.
- Run via ordinary local Python only. No Codex/LLM/API calls, remote data fetching, paid services, production credentials or external notifications.
- Use the exact frozen `FAMILY_SPEC.json`; verify its SHA before outcome access. Feature-only ranking artifacts must not include future labels.
- Never synthesize hourly/4-hour bars from daily OHLCV. Do not silently replace missing prices or drop/replace unresolved selected outcomes.
- For a five-session target, inspect every official session from entry through the fifth-session exit. Any absent/invalid OHLCV bar, zero-volume session, or missing canonical label leaves that selected row unresolved; never forward-fill or jump to a later bar. Report requested, resolved, and unresolved counts by status, and label returns as resolved-subset metrics when any remain unresolved.
- Any external price source considered for gap repair must be free, explicitly permit the intended automated and Bot use, and run in ordinary Python without Codex. Do not automate Yahoo Finance scraping or JPX historical-page retrieval, and do not use paid JPX products. Already-cached Yahoo-derived daily OHLCV may be used for isolated research label rebuilds, with source hashes and a clear statement that this is not new authorized collection. If no eligible source is verified, retain raw price gaps as unresolved; separate them from missing label joins.
- Preserve multi-symbol-per-day candidate pools; Top-N policies are separately evaluated with their own cooldown state.
- 2024 is gated and retrospective only. Do not open 2025/2026 under this experiment.
- Save artifacts only under ignored `.cache/`; commit code, specs and summarized reports without cached price/label rows.
