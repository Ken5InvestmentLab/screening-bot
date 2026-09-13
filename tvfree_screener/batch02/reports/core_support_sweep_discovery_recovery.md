# Support-Sweep Reclaim — corrected evaluation

- Decision: `REJECT_SUPPORT_SWEEP`.
- This recovery repairs only the report-side join: frozen candidate and selection hashes are unchanged.
- The initial report `0385737e936325a68db963114e3746ca43f3e7a8a2ebb3d3cbec1b981bcf14b1` is invalid because it used the full candidate label set for selected-signal metrics; do not cite its signal metrics.
- Canonical label digest matches the labels opened in the first pass. Only purge-safe 2022H2/2023 outcomes were processed; 2024+ stayed closed.
- Complete per-period metrics and gates are in the matching JSON.
