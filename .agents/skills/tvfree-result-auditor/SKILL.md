---
name: tvfree-result-auditor
description: Audit TV-Free scoring-bot backtest or replay results against a previously frozen contract. Use after an experiment finishes to detect leakage, population/endpoint mismatch, outlier dependence, concentration, failed robustness, or invalid promotion claims, and to issue pass/reject/inconclusive decisions without post-hoc tuning.
compatibility: Requires the frozen experiment spec plus result artifacts. Research-only; a pass never authorizes production by itself.
metadata:
  author: Ken5InvestmentLab
  version: "1.0"
---

# TV-Free Result Auditor

Use this skill **after** a frozen experiment produces results.

Do not optimize the experiment while auditing it.

## Step 1: identity and integrity

Verify:
- experiment ID matches the frozen spec;
- spec hash matches the committed freeze artifact;
- evaluator/code commit is recorded;
- input artifact hashes are known where required;
- the tested universe, period, endpoint, cooldown, costs, and selection policy match the frozen contract.

If any material field differs, classify the result as invalid or as a separate experiment. Do not silently reinterpret it.

## Step 2: leakage and timing audit

Check for:
- same-day finalized daily data used before it was available;
- future fundamentals or revised facts crossing the cutoff;
- 2026 historical outcomes influencing model/family/gate selection;
- ranking features computed from future cohort information;
- reconstructed intraday data that fabricated path from daily OHLCV;
- retuning after opening a locked block.

Any unresolved material leakage issue blocks promotion.

## Step 3: required performance table

For each relevant period/fold, report at minimum:
- resolved n / unresolved n;
- mean;
- median;
- win rate;
- +10%;
- +20%;
- +50% when relevant;
- <= -10%;
- <= -20% when relevant;
- best-1-excluded mean;
- best-3-excluded mean;
- cost sensitivity;
- symbol/date concentration;
- cooldown/re-entry effects where applicable.

Do not hide a weak median or outlier dependence behind a strong mean.

## Step 4: role-specific robustness

### Core
Require breadth and stability across periods. Strong central tendency in one block is not enough if later locked periods collapse.

### Monster / event-specific
Require meaningful right-tail capture **and** acceptable downside/outlier dependence. A calm low-volatility profile with almost no +20% events is not a Monster pass.

### Consensus / specialist
Audit repeated-symbol concentration, overlap, cooldown replacement, and whether the headline survives realistic one-position-per-symbol behavior.

### Data-integrity
Do not convert data-quality improvements into profitability claims unless a separately frozen performance experiment supports that conclusion.

## Step 5: comparison discipline

Only compare experiments directly when the contracts are comparable.

Always name:
- population;
- period;
- entry/exit;
- cooldown;
- costs;
- selection policy.

If two results differ on these dimensions, describe them separately instead of ranking headline means.

## Step 6: frozen decision

Apply only the gates that existed before outcome exposure.

Decision must be one of:
- **PASS_FROZEN_GATES**
- **REJECT**
- **INCONCLUSIVE**
- **INVALID_CONTRACT_MISMATCH**
- **BLOCKED_DATA_OR_LEAKAGE**

Do not move a threshold after seeing the result.

A pass means only that the research contract passed. It does **not** mean production-ready.

## Step 7: next action

If rejected:
- close the tested family/policy on the opened evidence;
- do not rescue it by renaming or micro-tuning;
- a new experiment must use a genuinely distinct mechanism and a new freeze.

If inconclusive:
- identify the missing evidence without choosing a direction from hidden or report-only outcomes.

If passed:
- state the next unopened confirmation or prospective-shadow requirement.

## Required output

Provide:
- contract integrity verdict;
- compact metric summary;
- strongest positive evidence;
- strongest negative evidence;
- outlier/concentration assessment;
- frozen-gate decision;
- what evidence remains unopened;
- next allowed action.
