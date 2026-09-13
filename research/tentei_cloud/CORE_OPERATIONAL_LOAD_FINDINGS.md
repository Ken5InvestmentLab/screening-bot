# Fixed Core operational-load findings — 2026-09-14 JST

Research-only. No signal rule, ranking threshold, production workflow, Discord webhook, or parallel V20 work was modified.

## Purpose

Quantify the user/operator load created by surfacing every fixed reconstructed Core signal. This is a capacity/UX audit, not a performance filter.

## Reproducibility

- trigger commit: `5e97a3255dc9942c285f4614b82ff3b90f911c55`
- workflow run: `34771263457`
- artifact: `10322007138`
- artifact ZIP SHA-256: `f79b54bf7f2390e365fce789243a3cb3b099ec1b2e0482c87eb233b9ffe30696`
- script: `research/tentei_cloud/audit_core_operational_load.py`

## 2026 Jan-Aug

Fixed Core:
- signals: **118**
- unique symbols: **107**
- signal-active days: **68**
- active weeks: **30**
- AM signals: 51 (**43.2%**)
- PM signals: 67 (**56.8%**)

### Daily alert load on active days

- mean: **1.74 signals**
- median: **1**
- p90: **3**
- p95: **4**
- maximum: **11**

Distribution across the 68 active days:
- exactly 1 signal: **42 days**
- exactly 2: **16 days**
- 3 or more: **10 days**
- 5 or more: **2 days**

Largest 2026 burst:
- **2026-04-10: 11 signals**
  - AM: 3
  - PM: 8

The next largest day had 5 signals.

### Session burst

- average signals per active session: **1.44**
- p95: **3**
- maximum: **8**
- maximum exact-timestamp burst: **8**

The fixed reconstructed timestamps concentrate at:
- AM last raw bar: 12:00 JST
- PM last raw bar: 15:00 JST

Thus the operational problem is not a continuous stream of alerts; it is an occasional same-session burst.

### Weekly load

Across active weeks:
- mean: **3.93 signals**
- p95: **9.55**
- maximum: **15**

### Symbol recurrence

Of 107 unique 2026 symbols:
- **97** appeared once
- **10** appeared at least twice
- maximum signals for the same symbol: **3**

The existing 5BD same-symbol cooldown is therefore already preventing heavy repeated-notification behavior.

## Historical burst caveat

Earlier development history contains much larger clustered events:
- 2025-04-16: 26 Core signals, 24 in PM
- 2025-04-17: 25 signals, 18 in AM

2025H2 maximum was 12 signals/day and 10 in one session.

Therefore a future regime can plausibly recreate much larger bursts than the 2026 maximum of 11. Notification design should not assume 2026 is a hard upper bound.

## Operational decision

**Do not prune Core because of alert volume.**

2026 load is modest enough to surface all Core candidates. The rare-burst problem should be solved in presentation, not by suppressing signals.

Recommended delivery contract for eventual production:
- keep every candidate as an independent stored signal;
- preserve exact lane identity `Core`;
- deliver Core to Discord as **at most one batch message per completed Core session** (AM / PM);
- a batch lists every candidate generated in that session; no top-N truncation;
- one-signal sessions still render naturally as a one-item batch;
- Monster Watch / Prime stay separate from the Core batch.

This bounds Core notification-message count to at most two session batches per trading day while preserving all candidate information, and it remains safe if 20+ candidates appear in a future clustered regime.

This is a UX/delivery recommendation only. It is not yet a production change.
