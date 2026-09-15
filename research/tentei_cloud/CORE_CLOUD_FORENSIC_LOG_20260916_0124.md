# Core + Cloud forensic log — 2026-09-16 01:24 JST

- Start Core HEAD: `5ea40f52e6bd967406446ebc2574d6c06628a71b`; coordination STATE v98 already marked it processed, so no duplicate processing.
- Fresh official-JPX verification found the missing PIT state-change family: List of Segment Transferred Companies.
- Official current page explicitly includes `277A Globe-ing Inc.` effective 2026-04-30, new segment Prime, previous segment Growth, explaining the previously observed reverse-replay state mismatch.
- Archive routing verified: current `/transfers/`, 2025 `/transfers/00-archives-01.html`, 2024 `/transfers/00-archives-02.html`.
- 2024 archive includes transfers after the target 2024-09-17 date (e.g. GENOVA 2024-09-20 Growth -> Prime), so transfer events are materially required for the requested PIT interval.
- Frozen repair contract added in `CORE_JPX_PIT_SEGMENT_TRANSFER_SPEC_20260916.md`.
- Existing 375-event listing/delisting receipt remains non-canonical because later forensic recount found 395 replay-eligible events; exact row-set difference must be audited before membership PASS.
- No performance calculation, no costed calculation, no reject-family retune, no production change.
- Cloud Monster exact forensic remains CLOSED / `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no model-family guessing reopened.

Next P0: byte-pin current/2025/2024 transfer pages, parse normalized transfer ledger, audit 375-vs-395 listing/delisting delta, then perform conflict-checked reverse replay and freeze PIT membership receipt.
