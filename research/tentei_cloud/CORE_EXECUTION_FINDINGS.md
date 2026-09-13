# Fixed Core executable-entry findings — 2026-09-14 JST

Research-only. No signal rule, production workflow, Discord, Spreadsheet, V12/V20 temporal-coverage work, or Monster logic was modified.

## Question

The standard reconstructed-Core label uses the signal session's CLOSE as the entry price. That is not directly executable because the session must finish before the signal is known.

This audit replaces the research entry with the first raw Yahoo 1H bar strictly AFTER the signal session's last raw bar and uses that bar's OPEN:
- AM signal -> normally the 13:00 JST next bar;
- PM signal -> normally the next trading day's opening bar.

The existing five-business-day target close is unchanged, so this isolates entry-timing realism.

## Audit hygiene

The first implementation produced zero matched rows because pandas 3 datetime storage units (microseconds) were compared against Timestamp.value nanoseconds. That output was rejected as an implementation failure, not interpreted as research evidence.

The timestamp lookup was fixed to use timezone-aware pandas Series.searchsorted. A fail-closed coverage guard was then added so future runs abort if executable-entry coverage falls below 90%.

Valid run:
- trigger commit: `1530c487d2d86b6bd9610dbe89b1668fc9c1a22f`
- workflow run: `34770326228`
- artifact: `10322340573`
- artifact ZIP SHA-256: `6d846e0f65a8a420c1e68fa12b0c51eb2869fd12ee855a7e021ca0aa4d484f48`
- coverage guard commit: `e36e0ecc6516b1fadd761a4900e0d68813668755`

## Coverage

Executable next-bar entries were found for **100%** of candidates:
- DEV: 169/169
- 2025H2: 140/140
- 2026 Jan-Aug: 118/118

2026 had 51 AM and 67 PM signals. Median entry gap versus signal close was 0.0%; mean gap was **-0.143%**, so the next executable open was slightly cheaper on average.

## Matched entry comparison

### 2026 Jan-Aug

Signal-session close entry:
- mean **+1.56%**
- median +0.48%
- win 53.39%
- <= -10% 1.69%

First executable next-bar open:
- mean **+1.71%**
- median +0.37%
- win 50.85%
- <= -10% **1.69%**
- top-3-winner-removed mean **+1.08%**

Mean changes by **+0.15 percentage points** in favor of the executable next-open proxy.

By session:
- AM: +2.21% signal-close -> **+2.23%** next-open
- PM: +1.06% signal-close -> **+1.31%** next-open

The PM improvement is mainly consistent with favorable average overnight/opening gaps in this 2026 sample. It must not be assumed to persist in future periods.

### Historical contrast

- DEV: +1.31% signal-close -> +1.28% next-open, essentially unchanged.
- 2025H2: +0.08% -> +0.05%, also essentially unchanged and still flat.

Therefore next-open execution does not rescue weak historical periods; it merely shows that the 2026 Core strength is not an artifact of using the signal-session close.

## Executable-entry cost sensitivity

Using next-open entry on 2026 Jan-Aug:

| assumed round-trip cost | mean | median | P(bootstrap mean > 0) | 95% week-cluster mean CI |
|---|---:|---:|---:|---:|
| 0.0% | **+1.71%** | +0.37% | **99.70%** | **+0.52% .. +2.84%** |
| 0.5% | **+1.21%** | -0.13% | **97.52%** | **+0.002% .. +2.43%** |
| 1.0% | **+0.71%** | -0.63% | 88.08% | -0.45% .. +1.88% |

At the fixed 0.5% cost scenario, the 95% bootstrap lower bound remains barely positive. At 1.0%, it crosses below zero.

Subperiods remain heterogeneous:
- Jan-Feb next-open gross: +0.31%
- Mar-Apr: +1.94%
- May-Jun: +2.52%
- Jul-Aug: +1.21%

So the aggregate remains dependent on regime/time even though no single 2026 month drives the full-year result.

## Decision

**The fixed reconstructed Core passes the executable-entry sanity check.**

This removes one important concern: the positive 2026 result is not being created by an impossible signal-close fill assumption.

Current Core assessment:
- broad-market pruning: rejected;
- simple local-feature pruning: rejected;
- positive peer-lag pruning: rejected;
- monthly/weekly stability: strong in 2026, weak in 2025H2;
- signal-close execution optimism: **not observed** in the matched next-open test;
- 0.5% assumed round-trip cost: still borderline-but-positive at the 95% week-bootstrap lower bound;
- 1.0% cost: not robust enough.

Core should remain broad and fixed as the current steadier lane, with forward/live execution monitoring required before production claims.
