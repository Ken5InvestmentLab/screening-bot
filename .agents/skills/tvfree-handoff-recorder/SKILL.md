---
name: tvfree-handoff-recorder
description: Record a durable GitHub handoff for a TV-Free research work chunk. Use after meaningful research progress, before pausing for context/usage limits, when switching chats or workers, or whenever another lane must be able to resume without re-discovering decisions, evidence exposure, branch state, and next actions.
compatibility: Requires GitHub write access to a research branch. Never place secrets, webhook URLs, private credentials, or uncommitted cache data in the handoff.
metadata:
  author: Ken5InvestmentLab
  version: "1.0"
---

# TV-Free Handoff Recorder

Use this skill at the end of every meaningful research chunk.

The handoff is the durable source for the next ChatGPT/Codex worker. It should be sufficient to resume safely without relying on chat memory.

## Required contents

Record:

1. **scope**
   - date/time
   - lane
   - branch
   - experiment ID(s)

2. **repository state**
   - starting HEAD
   - ending HEAD
   - changed files
   - committed artifacts
   - ignored/local-only cache paths, if relevant

3. **what was done**
   - hypothesis or engineering task
   - commands/evaluators run
   - tests and pass counts
   - workflow run IDs if used

4. **evidence**
   - exact population/period
   - execution endpoint
   - cost/cooldown/selection policy
   - important metrics
   - artifact/spec hashes

5. **decision**
   - continue / pass frozen gates / reject / inconclusive / blocked
   - why
   - whether the family is now closed on exposed evidence

6. **outcome exposure map**
   - which periods were opened
   - which periods remain unopened
   - whether 2026 historical strategy outcomes were viewed
   - whether any result may be used for tuning

7. **parallel-lane coordination**
   - active experiment owned by this lane
   - work that other lanes must not duplicate
   - any cross-lane correction that changes the supervisor contract

8. **next actions**
   - 1 to 3 concrete next steps in priority order
   - blockers or prerequisites
   - exact file/spec to read first

9. **production safety**
   - explicitly state whether main, production Bot, Discord, Sheets, GAS, TradingView, watchlist builder/updater, secrets, or production workflows were modified.

## Recording rules

- Research work must remain on a research branch unless the user explicitly authorizes production work.
- Never commit raw secrets or webhook URLs.
- Never commit ignored caches just to make a handoff reproducible; record hashes/receipts instead.
- If an experiment failed, write the failure and the closed decision. Do not omit it to make the research history look cleaner.
- If an older handoff is contradicted by newer evidence, state exactly what is superseded.
- If a cross-lane fact changed, update the supervisor coordination record in the same research-only change or explicitly flag it as the first next action.

## Commit convention

Use a concise research commit message describing the durable state change, for example:
- `research: record Vxx frozen rejection and next lane action`
- `research: sync supervisor contract after canonical replay`
- `research: add handoff for prospective-shadow integrity audit`

## Required final message

Tell the user:
- what was completed;
- where it was recorded;
- the commit SHA;
- the current decision;
- the exact next task that can safely continue.
