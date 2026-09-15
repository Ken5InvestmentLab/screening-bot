# Core + Cloud handoff — 2026-09-16 02:24 JST

Core branch advanced to include independent JPX transfer archive URL/schema verification. Canonical PIT is still fail-closed.

Verified official transfer source family:
- current `/english/listing/stocks/transfers/`
- 2025 `/english/listing/stocks/transfers/00-archives-01.html`
- 2024 `/english/listing/stocks/transfers/00-archives-02.html`

Do not treat rendered/search text as byte-pinned evidence. Next worker must use the existing research-only byte-preserving workflow to capture all three exact page objects and SHA-256 them, then build the transfer ledger. Preserve the 375-vs-395 listing/delisting discrepancy as an unresolved forensic item; audit it row-by-row before any PIT PASS.

Independent rendered evidence confirms 277A Growth->Prime on 2026-04-30 and multiple post-2024-09-17 transfers in the 2024 archive, so transfer replay is mandatory.

Cloud exact forensic remains closed/unavailable. No retune, no performance opening, no production changes.
