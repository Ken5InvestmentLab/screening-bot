---
name: tvfree-research-supervisor
description: Coordinate the TV-Free JPX scoring-bot research across parallel ChatGPT/Codex lanes. Use when the user says to continue/proceed, supervise multiple research chats, avoid duplicate work, reconcile conflicting findings, or choose the next non-overlapping experiment.
compatibility: Requires repository access to Ken5InvestmentLab/screening-bot and the active research branches. Research-only; never modify production unless the user explicitly authorizes a separate production task.
metadata:
  author: Ken5InvestmentLab
  version: "1.0"
---

# TV-Free Research Supervisor

Use this skill to decide **what should be worked on next** and to keep parallel research lanes consistent.

The user's current instruction takes precedence over this skill. If the user explicitly changes the research goal or constraints, follow the new instruction and record the change in the project coordination record.

## Core objective

Advance a TradingView-free JPX individual-stock screening/scoring system that can compete with the current benchmark on forward 5-business-day performance and robustness while retaining meaningful right-tail capture.

Stable★6, Sniper, Mega, TradingView, watchlist-builder/updater, production Discord, Sheets, GAS, and production workflows are benchmark/context only unless the user explicitly authorizes a separate migration step.

## Mandatory pre-flight

Before advancing any lane:

1. Read the newest cross-lane coordination contract under `research/`.
2. Re-fetch the current HEAD of every active research branch.
3. Read the latest branch-local handoff/log for the lane you may advance.
4. Read the current frozen spec/ledger entry for any active experiment.
5. Build a short ownership map:
   - active experiment
   - owning lane/branch
   - closed/rejected families
   - unopened evidence periods
   - current blockers
6. If a lane contradicts the newest coordination contract, fix the lane's log/spec first and record the correction before continuing.

Never assume an older chat summary is newer than branch-local evidence.

## Non-overlap rule

Do not duplicate, pre-empt, or silently re-run another active lane's experiment.

If two lanes touch similar features, distinguish them by:
- research role,
- exact mechanism,
- source data,
- frozen population,
- execution endpoint,
- evidence period,
- selection policy.

If they are still materially the same experiment, stop one lane and redirect it to a different unanswered question.

## Closed-family rule

A rejected family stays closed on already-opened outcomes.

Do not rescue it by:
- renaming,
- small threshold tuning,
- trigger reweighting,
- changing Top-N after seeing results,
- adding a gate discovered from the same opened outcomes.

A follow-up may proceed only when it is a genuinely distinct mechanism with a new frozen contract and clearly documented ancestry.

## Shared research invariants

Preserve these unless the user explicitly changes them:

- Final scoring should be 4H/intraday-led.
- Daily data may provide completed-day context, canonical labels, repair/reconciliation, or explicit fallback.
- Never fabricate AM/PM/4H bars from one daily row.
- Canonical comparable endpoint: next official XTKS session open -> fifth official XTKS session close.
- Keep legacy signal-close metrics separate from canonical endpoint metrics.
- Historical 2026 outcomes are report/robustness evidence only and must not select thresholds, models, gates, cooldowns, or families.
- State universe, period, endpoint, cooldown, costs, and selection policy for every cross-experiment comparison.
- Preserve preregistration/freeze artifacts and their hashes.
- Allow NO TRADE when no lane passes its frozen validity/availability conditions.

## Choosing the next task

Prefer work that maximizes information gain without reopening exposed evidence.

Priority order:
1. resolve correctness/data-integrity blockers;
2. finish already-frozen unopened evaluations;
3. test a genuinely new mechanism with a frozen contract;
4. improve prospective shadow evidence collection;
5. only then consider integration architecture.

Avoid spending a lane on cosmetic refactors, duplicate metrics, or more tuning of a failed family.

## During execution

Keep work on a research branch. Do not touch main or production surfaces.

If the task will open strategy outcomes, use the `tvfree-experiment-freeze` skill first.

If the task is evaluating completed results, use the `tvfree-result-auditor` skill.

## Required supervisor output

Report:
- lane advanced;
- why it did not overlap another lane;
- branch and frozen experiment ID;
- what changed;
- strongest new evidence;
- decision: continue / reject / inconclusive / blocked;
- next non-overlapping action.

When the work chunk ends, use `tvfree-handoff-recorder`.
