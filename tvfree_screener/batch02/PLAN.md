# TV-Free Core batch02 preregistration and run plan

Registered: `2026-09-12T23:20:04.469Z` UTC. Status: `REGISTERED`; no experiment outcomes were read before freezing `FAMILY_SPEC.json` and its SHA-256.

## Why this family

Batch01 consumed its three Core slots with no viable policy. This is a new mechanism: continuation after a measured volatility contraction while both 20-session and 5-session price direction remain nonnegative. It excludes negative-ret5 pullbacks and uses no volume trigger, separating it from First Reversal, orderly pullback, and quiet-volume ignition. It is still retrospective because this market history has been examined in other research; any result is provisional and cannot prove true OOS.

## Fixed experiment

- ID: `CORE-TREND-COMPRESSION-20260913-01`.
- The complete machine-readable candidate, rank, target, selection, evaluation and period contract is [FAMILY_SPEC.json](FAMILY_SPEC.json); exact bytes are pinned by [FAMILY_SPEC.sha256](FAMILY_SPEC.sha256).
- Discovery: 2022H2–2023 with the canonical fifth-session exit purge. Model/policy selection is limited to that window.
- No 2024 access unless discovery pool and a fixed Top-N policy pass the existing registered Core gates. If opened, call it retrospective confirmation, not OOS. 2025/2026 remain closed in this experiment.
- The candidate pool permits multiple symbols/day; Top1/2/3/5 policies are separate and each has its own one-prior-XTKS-session selected-symbol cooldown.
- 0.5% round-trip cost is the primary assumption; 0% and 1% are sensitivity cases, not measured fees.
- Missing outcomes stay unresolved. No survivor-only cohort reweighting, candidate replacement, or daily-to-intraday fabrication.

## Run sequence

1. Verify spec, frozen OHLCV/feature/calendar and outcome-artifact hashes and target implementation.
2. Build the complete feature-only pool and ranking artifact; selection hash must not contain future labels.
3. Open only discovery labels after the frozen selection artifacts exist; retain unresolved rows and audit cohort coverage.
4. Apply the existing Core pool gate. If rejected/inconclusive, stop this family and do not inspect 2024 or run Top-N policy selection.
5. Only after KEEP, run the four registered Top-N policies and existing pass gates. If none passes, record `SELECTION_COUNT_UNRESOLVED` and close the family.
6. If a policy passes, freeze it, log real freeze/open UTC timestamps, then optionally inspect 2024 solely as retrospective confirmation. Do not select a different N from that period.
7. Save metrics, decision, code/spec/data hashes and reproducibility result in the report/ledger. A pass remains research-only and requires true-forward evidence before production discussion.

## Safety and execution

The package is ordinary local Python and must run with no Codex/LLM/API, network fetch, broker, paid service or production credentials. It does not alter production, Discord, Sheets, GAS, TradingView or workflows. Missing intraday inputs cannot be reconstructed from daily bars. The family’s tests and local commands are not a production implementation.

## Stop criteria for this family

`REJECT`, `INCONCLUSIVE`, or `SELECTION_COUNT_UNRESOLVED` is a valid completed experiment disposition. Do not tune this family afterward. Any next family receives a new ID and frozen evidence contract.