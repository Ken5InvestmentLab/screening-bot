# Fixed Core capacity findings — 2026-09-14 JST

Research-only. No Core signal rule, ranking, capital allocation, production workflow, Discord, or parallel V20 work was modified.

## Question

If every fixed Core signal is treated as a five-business-day holding candidate, how many concurrent position slots would be needed?

Entry proxy:
- first raw Yahoo 1H bar strictly after the completed signal session.

Exit proxy:
- existing five-business-day target date at that day's close.

One Core signal = one position slot. No sizing, prioritization, or capacity filtering was applied.

## Reproducibility

- trigger commit: `9bf07ef9d91a69b2af28aa499605aec20a2b4a22`
- workflow run: `34771393714`
- artifact: `10321544380`
- artifact ZIP SHA-256: `e7b9d938e1c17bb7eddfba30d4ea056b7e314996b4275b7c794d1136f6e88343`
- executable-entry coverage: 100%

## 2026 Jan-Aug

118 fixed Core signals:
- mean concurrent positions: **3.85**
- median: **3**
- p90: **8**
- p95: **10**
- maximum: **16**
- days with >=5 concurrent positions: 54
- days with >=10: 11
- days with >=15: 4
- maximum new entries on one executable-entry date: **8**

Peak:
- **2026-04-14: 16 concurrent positions**

The peak cluster was created by the April 10 signal burst flowing into executable entries and the fixed 5BD holding window.

## Historical stress evidence

2025H2:
- median concurrent: 5
- p95: 16
- maximum: 22

DEV contains a much more extreme cluster:
- 2025-04-17: 42 new entries
- 2025-04-22: **57 concurrent positions**
- p95 concurrent: 14.3 despite the one extreme episode

Therefore 2026's maximum of 16 is not a safe hard upper bound. Core can cluster dramatically in some market states.

## Decision

**Do not put a hard capacity cap inside the signal engine.**

Reasons:
- the user's objective is detection quality/performance, not a fixed model portfolio;
- a 10- or 20-position signal cap would silently discard candidates during exactly the unusual clustered periods that may contain important opportunities;
- there is currently no causally validated ranking inside Core for deciding which candidate to discard when capacity is exceeded.

Operational contract:
- store every valid Core signal;
- notify every valid Core signal;
- never truncate to top-N merely for UI convenience;
- if a session has too many candidates for one message, split presentation into multiple ordered batches while preserving every candidate;
- any future trading-capital allocator must be a separate downstream layer and must never redefine the underlying Core signal set.

Core itself remains a detector, not a portfolio-capacity filter.
