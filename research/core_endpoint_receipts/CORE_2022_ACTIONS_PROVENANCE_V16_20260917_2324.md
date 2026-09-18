# Core P0 receipt — 2022 Actions provenance / V16

Date: 2026-09-17 JST
Scope: research-only. No production/main/workflow/Discord/Spreadsheet/Stable/Sniper/Mega/TradingView/watchlist changes. 2026 outcome not opened.

## New provenance recovered

Freeze ref: `4b37f18d7601f8fd6ff42155879faff5b7d1e9e3`.
Workflow blob: `.github/workflows/tvfree-v16-volr20-test.yml` = `548e8ac2d954c4841f46b7e5d39fd2b1d145d4a8`.

The V16 workflow fixes two upstream Actions sources:
- preserved frozen run80 dataset: run ID `34599959356`, artifact name `tvfree-frozen-dataset-run80-preserved`, downloaded to `tvfree_screener/out`.
- causal Tail cache: run ID `34600083474`, artifact name `tvfree-v7-causal-tail-cache-2023-2025`, downloaded to `tail_cache`.

Exact generator command recovered from the frozen workflow:

`python tvfree_screener/v16_pre2025_volr20_rank.py --cache tvfree_screener/out/tse_daily.csv --tail-cache tail_cache/v7_causal_tail_cache_2023_2025.csv`

The same workflow uploads V16 evidence under artifact name `tvfree-v16-volr20-${{ github.run_id }}` with `v16_volr20_report.json`, `v16_volr20_2025_picks.csv`, and `v16_volr20_2026_picks.csv`.

## P0 interpretation

This is a concrete Actions provenance edge and exact generator command, not a repeated headline search. It also shows that this frozen V16 workflow consumes a 2023-2025 Tail cache, so it must not be treated by itself as proof of the 2022 fresh-validation rows. The next reverse lookup should start from run IDs `34599959356` / `34600083474` and their jobs/artifacts/logs, or from the commit that added the 2022 fresh-validation summary/receipt, to locate the separate 2022 generation path.

No 2023-25 endpoint re-audit or 797-invalid-row recheck was performed.