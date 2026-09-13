# TV-Free batch02 research instructions

- Keep all edits under this research-only package; production files and integrations are outside scope.
- Run via ordinary local Python only. No Codex/LLM/API calls, remote data fetching, paid services, production credentials or external notifications.
- Use the exact frozen `FAMILY_SPEC.json`; verify its SHA before outcome access. Feature-only ranking artifacts must not include future labels.
- Never synthesize hourly/4-hour bars from daily OHLCV. Do not silently replace missing prices or drop/replace unresolved selected outcomes.
- Preserve multi-symbol-per-day candidate pools; Top-N policies are separately evaluated with their own cooldown state.
- 2024 is gated and retrospective only. Do not open 2025/2026 under this experiment.
- Save artifacts only under ignored `.cache/`; commit code, specs and summarized reports without cached price/label rows.