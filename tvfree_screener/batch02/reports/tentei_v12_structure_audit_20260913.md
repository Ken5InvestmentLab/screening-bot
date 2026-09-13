# Tentei-inspired V12 event-generator structure audit — 2026-09-13

Research-only, outcome-free structural audit. This work was run in a separate parallel lane while the main research lane evaluated V12/V13. It does **not** use 5BD returns, strategy outcomes, 2026 returns, daily-to-intraday synthesis, or any production data write.

## Scope

The frozen V12 signal logic was applied to the already-authorized raw Yahoo-derived 1h shards from Actions run `34592896202`. The structure audit measures the event generator **before** the prior-daily price/volume gate and before the five-session cooldown. Therefore these counts are intentionally larger than the official V12 evaluated population and must not replace that report.

For runtime efficiency the local diagnostic retained raw rows from 2024-12-01 through 2025-12-31. This provides substantially more than the required BB20/RSI12/ATR14 warm-up before the registered H1 window beginning 2025-03-01. No outcome column was loaded.

## Results

### H1: 2025-03-01 through 2025-06-30

- Complete AM/PM bins: **169,328**
- V12 signal rows: **10,217 (6.034%)**
- Symbols / signal dates: **1,265 / 82**
- AM / PM: **5,788 / 4,429** (AM 56.65%)
- RSI recovery flags: **4,396**
- Trend-flip flags: **914**
- Emergency-reversal flags: **6,220**
- Single-path / multi-path rows: **8,960 / 1,257** (multi-path 12.30%)
- Signal rows whose same-symbol immediately previous complete bin was also a V12 signal: **3,705 / 10,217 = 36.26%**
- Emergency-reversal rows whose previous complete bin was also emergency-reversal: **3,331**

Monthly signal rates were not stable: March **4.96%**, April **11.23%**, May **3.22%**, June **4.36%**. April alone produced 4,999 signals, including 3,832 emergency-reversal flags.

### H2 structure only: 2025-07-01 through 2025-12-31

No H2 returns were opened. Feature/event structure only:

- Complete bins: **268,045**
- Signals: **15,596 (5.818%)**
- Same-symbol previous-complete-bin also signal: **4,260 = 27.31%**
- Emergency-reversal flags: **7,050**; RSI recovery **8,032**; trend flip **1,652**
- Multi-path rows: **1,046 = 6.71%**
- AM / PM: **9,392 / 6,204**

Monthly signal rate ranged from **3.35% in August** to **9.38% in October**.

### Full 2025 structure only

- Complete bins: **514,098**
- Signals: **29,964 (5.828%)**
- 1,286 symbols / 243 signal dates
- Previous-complete-bin also signal: **9,373 = 31.28%**
- Emergency reversal: **15,456 (51.58% of signal rows, overlaps allowed)**
- RSI recovery: **14,274 (47.64%, overlaps allowed)**
- Trend flip: **3,016**

## Interpretation

V12 is structurally much denser and more persistent than a one-shot reversal/ignition event generator. Roughly one third of 2025 signal rows occur immediately after another signal for the same symbol, and emergency reversal shows especially strong persistence. The monthly firing rate also varies materially, with visible bursts in April and October.

This is **not** a performance conclusion. The official V12 report applies prior-day gates and cooldown and is the authoritative source for V12 performance. The present audit only shows that candidate generation contains a substantial state/persistence component rather than isolated transition events.

Because the return results for V12 became available in the parallel lane after this structure diagnostic had already been computed, these findings must not be used to retroactively validate V12, select a trigger path, or alter V13/V14. A future experiment may test a genuinely preregistered state-entry / first-transition representation, but it must be treated as a new retrospective hypothesis with its own frozen rule and must not claim untouched OOS evidence from 2025.

2026 strategy outcomes opened: **false**. Production modified: **false**.
