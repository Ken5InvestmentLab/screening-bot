---
name: tvfree-experiment-freeze
description: Preregister and freeze a TV-Free scoring-bot experiment before opening returns or outcome labels. Use for any new Core, Monster, Consensus, intraday, data-quality, selection-policy, or ranking experiment where leakage, post-hoc tuning, or evidence contamination must be prevented.
compatibility: Requires repository access to the screening-bot research tree. This skill creates research-only freeze/spec artifacts and must run before outcome inspection.
metadata:
  author: Ken5InvestmentLab
  version: "1.0"
---

# TV-Free Experiment Freeze

Use this skill **before** opening performance outcomes for a new hypothesis or policy.

The purpose is to make post-hoc tuning visible and difficult.

## First decide whether this is actually new

Classify the proposal as one of:

- genuinely new mechanism;
- fixed-policy replay;
- diagnostic with no performance conclusion;
- minor variation of an already-opened/rejected family.

If it is only a minor variation of a rejected family on already-opened outcomes, do not run it as a new experiment. Record it as blocked by prior exposure.

## Required frozen fields

Create a machine-readable spec containing at least:

1. **identity**
   - experiment ID
   - research role: Core / Monster / Consensus / data-integrity / other
   - owner lane and branch
   - parent experiment(s), if any

2. **mechanism**
   - exact feature definitions
   - timing/cutoff semantics
   - missing-data behavior
   - eligibility gates
   - ranking/selection policy
   - cooldown and same-symbol handling
   - abstain / NO TRADE behavior

3. **population**
   - JPX universe definition
   - exclusions
   - price/volume prerequisites
   - candidate-generation rules

4. **execution**
   - canonical entry/exit definition
   - transaction-cost assumptions
   - any slippage sensitivity
   - unresolved endpoint handling

5. **evidence partition**
   - development periods
   - locked replay/validation periods
   - unopened periods
   - report-only periods
   - explicitly exposed periods

6. **success/failure gates**
   - exact pass thresholds
   - minimum resolved sample size
   - required robustness checks
   - stop conditions

7. **reproducibility**
   - source artifact paths
   - source hashes
   - code/commit reference
   - random seed if applicable
   - generated spec hash

## Project invariants

Unless the user explicitly changes them:

- comparable 5BD endpoint is next official XTKS open -> fifth official XTKS close;
- 2026 historical returns cannot choose thresholds, gates, cooldowns, families, or models;
- daily bars cannot be used to invent intraday/4H path;
- future-known fundamentals or revised facts cannot be used before their public availability timestamp;
- benchmark labels such as Stable★6/Sniper/Mega are not dependencies of the replacement logic;
- do not compare a new result against a headline from a different population/endpoint as if directly equivalent.

## Frozen gate design

Choose gates from the role of the experiment, not from opened outcomes.

For all performance experiments, include:
- resolved n;
- mean;
- median;
- win rate;
- best-1-excluded mean;
- best-3-excluded mean;
- <= -10% rate;
- cost sensitivity.

For Monster/event-specific work also freeze right-tail requirements such as +10%, +20%, and where meaningful +50%.

For Core work emphasize cross-period stability, breadth, central tendency, and outlier independence.

For Consensus/specialist work include concentration, symbol overlap, cooldown/re-entry, and diversification/generalization checks.

## Freeze procedure

1. Write the spec before loading the locked outcomes.
2. Compute a SHA-256 hash for the final spec.
3. Commit the spec and hash to the research branch.
4. Add an experiment-ledger entry that points to the committed spec.
5. Only after the commit exists may the locked outcome evaluation begin.
6. If the spec must change after outcome exposure, create a new experiment ID and explicitly mark the old evidence as exposed.

## Required output

Return:
- experiment ID;
- branch;
- spec path;
- spec hash;
- development/locked/report-only period map;
- frozen pass/fail gates;
- confirmation that locked outcomes were not used to choose the contract.
