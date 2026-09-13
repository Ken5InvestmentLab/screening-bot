# V20 session-impulse H1 raw-universe coverage audit — 2026-09-14

Research-only, outcome-free input audit. No V20 strategy returns were opened.

## Finding

The existing frozen Core 1H panel from run `34592896202` contains a fixed **1,332-symbol** comparison universe.

That panel is not sufficient for the preregistered V20 session-impulse H1 experiment.

Using the frozen canonical daily dataset (SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`) and only the preregistered production-like prior-day eligibility:

- H1 official signal sessions: **82**
- prior completed daily close <= 1,000 JPY
- prior completed daily volume >= 10,000 shares
- unique symbols eligible on at least one H1 signal date: **1,810**
- minimum eligible symbols on a H1 session: **993**
- maximum eligible symbols on a H1 session: **1,669**
- sorted symbol-list SHA-256: `2437e240d549074594b8584a9e2403a153c20a377bcc9b842dc7f8b538d1516b`

Because 1,332 < 1,810, the old raw panel necessarily omits at least **478** H1-eligible symbols. Running V20 on that panel could change both signal availability and within-session percentile ranking.

## Decision

**DO NOT RUN V20 H1 ON THE EXISTING 1,332-SYMBOL PANEL.**

Instead:
1. regenerate the exact 1,810-symbol H1 universe from canonical daily;
2. freeze its count and SHA;
3. fetch dedicated Yahoo 1H only for that frozen universe;
4. require exact symbol coverage and zero final fetch failures before opening H1 outcomes;
5. run the frozen V20 evaluator only after the input receipt passes.

## Yahoo split-adjustment query-mode note

Cross-lane Consensus auditing found that Yahoo range-query and explicit-period 1H requests can differ by later stock-split scale factors.

V20 does not use absolute intraday price level. Its signal representation uses:
- session return,
- close location,
- within-bar range/close,
- volume relative to prior sessions.

Those are invariant to a uniform stock-split scale factor within a bar/history segment. Absolute prior-day price/liquidity eligibility and 5BD entry/exit labels come from the frozen canonical daily source.

Therefore explicit-period 1H is acceptable for this V20 shape/continuation experiment, while the raw input is still frozen and receipt-checked before outcome access.

The canonical daily universe itself remains the current-survivor historical panel, so survivorship-neutral point-in-time JPX membership remains a promotion-stage dependency.

2026 outcomes opened: false.
Production modified: false.
