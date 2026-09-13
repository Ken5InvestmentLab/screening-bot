# EXPERIMENT_LEDGER pending append — prospective shadow lane

Status: SAFE_APPEND_PENDING
Reason: `EXPERIMENT_LEDGER.md` is concurrently edited by parallel research lanes and GitHub contents writes replace the whole file. The current connector response is too large to reconstruct the ledger byte-for-byte safely. Do not overwrite or truncate the shared ledger.

The following entries must be appended to `EXPERIMENT_LEDGER.md` once a byte-safe append/rebase path is available. Dedicated source reports/specs are authoritative until then.

## TENTEI-V12-STATE-ENTRY-H1-20260913 — REJECT_AS_MONSTER

- Frozen representation: first transition only, `V12_signal AND NOT previous_complete_bin_V12_signal`; V12 ALL trigger logic unchanged.
- H1 structural state-entry rows: 6,512. Prior-day close/volume gates: 5,330. Five-session cooldown: 3,445. Resolved: 3,445.
- 0.5% cost: mean +1.4647%, median +0.6385%, win 55.27%, gross +20% rate 2.03%, <=-10% 4.41%, Top1-removed mean +1.3354%, Top3-removed +1.2987%.
- Decision: reject as Monster because frozen +20% gate required >=10%. Do not open H2 for this hypothesis and do not tune from H1.
- Source: `reports/tentei_state_entry_h1_20260913.md`.

## TENTEI-V12-CORE-RETROSPECTIVE-H2-20260913 — REJECT_V12_AS_CORE_RETROSPECTIVE

- Separate post-hoc Core interpretation of unchanged V12 ALL, preregistered as hypothesis-refutation-only before H2 readout.
- H2 raw V12 ALL signals: 15,604; after prior-day gates: 12,438; after five-session cooldown: 6,205; all 6,205 resolved.
- 0.5% cost: mean -0.5023%, median -0.5000%, win 41.05%, gross +20% 1.03%, <=-10% 3.63%, Top1-removed mean -0.5455%, Top3-removed -0.5736%.
- Decision: reject V12 ALL as retrospective Core. Do not threshold-rescue or tune from H2. 2026 outcomes remain closed for strategy selection.
- Sources: `TENTEI_V12_CORE_RETROSPECTIVE_SPEC.json`, `reports/tentei_v12_core_h2_20260913.md`.

## PROSPECTIVE-SHADOW-EVIDENCE-20260913 — INFRASTRUCTURE_READY

- Research-only append/idempotent prospective evidence recorder. Accepts only `RAW_CAUSAL_INTRADAY`; rejects post-close reconstruction and daily-resolution fallback as intraday evidence.
- Candidate identity includes experiment/model freeze/symbol/signal date/bin. Target is next official XTKS session open to fifth official XTKS session close. Missing endpoints are explicit and never imputed.
- Local CLI verifies model-spec SHA/freeze identity, ingests CSV/JSONL candidate exports, resolves 5BD endpoints from local daily input, and emits audit summaries. No network/prod writes.
- Candidate export contract is generic and forbids shadow-side model/rank/threshold recomputation.
- Causal preflight enforces source tag, signal/cutoff date match, XTKS bin cutoff, unique candidate keys, and positive integer ranks.
- Verification: core shadow tests 4/4 passed; CLI integrated tests 7/7 passed at implementation milestone; causal preflight tests 8/8 passed.
- Sources: `PROSPECTIVE_SHADOW_EVIDENCE_SPEC.json`, `prospective_shadow.py`, `prospective_shadow_cli.py`, `test_prospective_shadow.py`, `test_prospective_shadow_cli.py`, `prospective_shadow_preflight.py`, `test_prospective_shadow_preflight.py`, and companion reports.

## V15-PROSPECTIVE-SHADOW-READINESS-20260913 — NOT_READY_YET

- Read-only compatibility audit only; no V15 model logic modified.
- V15 cannot enter prospective shadow until final representation/evaluation passes are complete and a selection policy, immutable model freeze ID/spec digest, and per-candidate export are frozen.
- Once frozen, handoff order is: model freeze -> candidate export -> causal preflight -> append prospective record -> 5BD maturity resolution.
- Do not create a provisional V15 shadow stream from a representation-only preregistration.
- Source: `reports/v15_prospective_shadow_readiness_20260913.md`.

## Reconciliation rule

When merging these entries into `EXPERIMENT_LEDGER.md`:
1. fetch the latest ledger bytes immediately before write;
2. preserve every pre-existing parallel-lane entry exactly;
3. append only missing entries from this file;
4. use optimistic blob SHA and abort/re-fetch on conflict;
5. never force-write or truncate the shared ledger;
6. after successful merge, mark this file as reconciled rather than deleting audit history.
