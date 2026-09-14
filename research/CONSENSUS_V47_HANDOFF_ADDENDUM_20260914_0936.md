# Consensus V47 handoff addendum — 2026-09-14 09:36 JST

Promotion-relevant path remains V47 clean PIT only.

Authoritative daily v6 run `34788533946` completed successfully at the workflow level but failed the frozen data acceptance: restored/delisted daily recovery was 0/251 because every direct Yahoo request was HTTP 429. This is classified as transient provider-rate-limit failure, not historical-code unavailability. No strategy returns or model scores were opened.

Do not trigger V47 raw 1H. Do not start alias/provider substitution from this receipt. First repeat the direct Yahoo historical-code daily step under a rate-limit-safe launch while preserving the exact 251 required symbols and all frozen PIT price, PIT daily-volume, identity-epoch, NOCAP/CAP1000 contracts. Only terminal/unavailable direct-provider results from a valid attempt may move to official identity-continuity verification under `research/consensus_v47_restored_data_repair_spec.json`.

Disposition detail: `research/CONSENSUS_V47_DAILY_V6_DISPOSITION_20260914.md`.

Production/main, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater remain untouched.
