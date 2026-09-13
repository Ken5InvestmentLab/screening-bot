# V12 first-transition / state-entry representation freeze — 2026-09-13

Research-only. This is a separate parallel-lane hypothesis and does not alter V12, V13, or the concurrently developed V14 model. No 5BD return was opened to define this representation and no 2026 strategy outcome was opened.

## Why freeze this separately

The outcome-free V12 structure audit found that V12 is materially state-persistent rather than purely event-like. Before the prior-daily gate and five-session cooldown, 3,705 of 10,217 H1 signal rows (36.26%) followed another V12 signal in the immediately previous complete causal bin for the same symbol. Full-2025 structure showed 9,373 of 29,964 rows (31.28%) with the same property.

This motivates a distinct representation: keep only the first complete-bin transition into the V12 signal state. This is not presented as an improvement; it is a new retrospective hypothesis whose performance remains unknown.

## Frozen representation

`state_entry = V12_signal AND NOT previous_complete_bin_V12_signal`

The predecessor is the immediately previous available complete AM/PM causal bin for the same symbol, in chronological order. Trigger logic remains V12 ALL; RSI recovery, trend flip, and emergency reversal are not selected or reweighted. Daily OHLCV is never synthesized into intraday bars.

If performance is evaluated later, ordering is fixed as: causal V12 state construction -> state-entry filter -> existing prior-completed-daily price/volume gates -> existing five-XTKS-session same-symbol cooldown. Target remains next official XTKS session open to fifth official XTKS session close.

## Outcome-free structural compression

These counts are before prior-daily gates/cooldown and therefore are not official candidate counts:

- H1 Mar-Jun 2025: 10,217 V12 signal rows; 3,705 immediate repeats; implied state-entry rows **6,512**, retaining **63.74%**.
- H2 Jul-Dec 2025 structure only: 15,596 signal rows; 4,260 immediate repeats; implied state-entry rows **11,336**, retaining **72.69%**.
- Full 2025 structure: 29,964 signal rows; 9,373 immediate repeats; implied state-entry rows **20,591**, retaining **68.72%**.

## Integrity boundary

The parent V12 H1 aggregate return results are already exposed, so any H1 state-entry evaluation is retrospective and cannot be called OOS. H2 also belongs to historically exposed 2025 and cannot establish forward validity. Any eventual promotion requires post-freeze prospective shadow evidence.

This freeze must not be used to rewrite V12, rescue V13, alter V14, choose a trigger path post hoc, or tune thresholds from 2025. The purpose is only to preserve a clean future test of whether isolated state-entry is a better event representation than repeated-state firing.

2026 strategy outcomes opened by this lane: **false**. Production modified: **false**.
