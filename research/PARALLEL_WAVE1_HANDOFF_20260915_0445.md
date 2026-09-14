# Parallel Wave-1 handoff — 2026-09-15 04:45 JST

Status: **SOURCE + EXACT SCHEMA + INDEPENDENT XTKS CALENDAR PINNED / ENDPOINT VERIFIER IMPLEMENTED / PERFORMANCE UNOPENED**

## Cross-lane audit first

Coordination STATE/README/dashboard and all STATE-registered active research branch heads were checked before lane work. Canonical, Core and OSS actual heads still matched their processed SHA. Consensus had advanced from `b9579857c598730bc7e3dbad35517fd5c6dc98a4` to `fd7f7c5d26f154a760dd9a025bb242620bce0dc9` with two coordination/dashboard-only commits. The material new observation is transport-only: raw48 run `34849054884` now has shards 0-3 completed with **324 requested / 0 ok / 0 raw rows / 324 final HTTP 429**; artifacts `10357093848`, `10357611796`, `10363982190`, `10364352429` are visible. The run remains nonterminal/queued and was not duplicate-triggered. No strategy/performance change was present.

## Parallel Wave-1 progress

The formal Wave-1 calendar is no longer inferred from observed price rows. An independent XTKS calendar was generated with `exchange_calendars 4.13.1` and the committed bytes are now the formal pinned artifact:

- `research/PARALLEL_WAVE1_XTKS_CALENDAR_2022_2026.csv`
- 1,220 sessions
- first: `2022-01-04`
- last: `2026-12-30`
- SHA-256: `58e67bd20be08d04c143fa7e8f707bb3b82c21c2de2af9dfd7c2a05a406de71b`
- calendar commit: `cd667f598bcdd980cb186350f4ecb49f1e57661e`

The machine-readable calendar/endpoint contract is recorded in `research/PARALLEL_WAVE1_XTKS_CALENDAR_RECEIPT_20260915.json` (commit `69f49c879fec2eded3dfd84d7bf1f8f249b865aa`). Mapping is frozen as:

`signal XTKS session -> next XTKS session open -> fifth XTKS session close`, counting the entry session as session 1.

An outcome-blind verifier was added at `research/parallel_wave1_endpoint_receipt.py` (commit `f5bff8131e723d09698596fed8b23ef6e09fe236`). It never computes a return. It fails closed unless calendar SHA, daily-source SHA, exact schemas, pick-ledger rows and every required entry-open/exit-close endpoint are valid. It emits only a provenance/completeness receipt, including the pick-ledger SHA and endpoint-key SHA. A mapping smoke check confirmed `2026-09-01 -> 2026-09-02 open -> 2026-09-08 close` under the pinned calendar.

A1/B1/E1 thresholds and definitions were not changed. The bound daily source remains SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`, 4,061,361 rows, exact header `date,open,high,low,close,volume,symbol`. Because the bound source has no `tail_p`, the already-preregistered deterministic fallback remains symbol ascending. Transaction cost remains 0%; win remains gross return > 0; 2026 remains report/robustness-only.

## Next action

Derive the A1/B1/E1 causal pick ledger from the frozen daily source **without computing returns**, freeze its bytes/SHA, then run `parallel_wave1_endpoint_receipt.py` against the pinned calendar + frozen daily CSV. Only after the actual endpoint-session completeness receipt passes may the one-shot cost0 performance batch be opened. No A2/B2/E2, threshold/ranker/weight/gate retuning, or 2022-fresh tuning is allowed.

Production/main, production workflow, Discord, Spreadsheet, Stable★6, Sniper, Mega, TradingView, watchlist-builder and updater were untouched.
