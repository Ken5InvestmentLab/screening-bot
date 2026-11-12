# Cloud startup-chain hardening (2026-11-12, staging)

## Evidence and scope
- 11/12 cloud-2 ran at 17:01 but did not launch the runner after a truncated affirmative preflight. Console truncation is not an abnormal condition.
- 11/12 cloud-3 launched at 17:34 and terminated in detection at 18:46: endpoint entry price revision for 3042 (ledger 986, fetched 989). JPX official 11/11 evidence supports 986. Do not rewrite ledger/raw data to force agreement.
- Implemented only in an isolated worktree. Production tasks/configuration have NOT been switched. Existing delivery and branch protections remain enforced.

## Design
1. task-entry writes an independent invocation JSON before config/preflight. This establishes that the wrapper was reached, even when config inspection fails. An absent record means no *verified* invocation, not proof the computer never woke (disk/permission failure must also be checked).
2. Official launchPreflight is used, not ad-hoc PowerShell regex clones. Unknown inspections receive at most 3 attempts, 30 seconds apart. Affirmative readiness is mandatory. Confirmed lock/process/branch/data errors are not blindly retried.
3. All child processes have a durable PID/status record, and runner progress saves result.json and append-only events per run. A terminal detection failure can resume from the SHA-verified source cache without downloading everything again. Receipt must still equal the latest result, target JST day must match, and automatic recovery is claimed once per failed run.
4. Known symbol-scoped endpoint revisions are isolated with a dedicated validated audit, preserving the old ledger economics and receipts. Unknown errors, corrupted source, systemic preflight and unverified adjustments remain fatal; continuing arbitrary failures would falsify results.
5. cloud-3 can invoke task-entry --start: no same-day receipt starts the daily runner; terminal detection failure resumes detection; completed runs stay complete; nonterminal runs are observed; post-deploy/notification ambiguity requires receipt reconciliation, never blind replay. This is deliberately not an automatic retry for every arbitrary stage.

## Safe activation requirements / limitations
- Coordinate with running daily/reminder processes before deployment. Do not modify live files while an owned process is running.
- Back up production files/definitions; review all changes; run regression tests; deploy via existing research branch procedure so clean-checkout and exact-remote-HEAD checks remain meaningful. No guard bypass.
- Change cloud-2/cloud-3 definitions to the entry wrapper only AFTER its code is present on the correct live branch. Read back exact definitions. A text-only saved instruction is not an active watchdog.
- Launch arbitration lock is exclusive. A stale lock is evidence to reconcile, not automatically delete. Disk failures and OS scheduler absence cannot be repaired by a wrapper that was never invoked; existing independent rescue slots are still required.
- No generic automatic resumption for fundamental/deploy/send stages in this version: their existing output, live deployment and receipt verification must establish the exact next unfinished step first.
- Cloud-5 records benefit from shared child process journaling, but this daily task-entry intentionally cannot launch a daily run under cloud-5; reminder recovery requires its own receipts.
- Tests are local synthetic tests, not evidence of a successful production daily run, notification, or future scheduled launch.

## Local validation / activation block
JavaScript: 79 tests, 78 pass, 1 skip (Windows directory-link permission), 0 fail. The new wrapper has 8 tests including bounded retries, immutable invocation on config failure, inspection mode/no launch, occupied arbitration lock, no daily launch under cloud-5, and once-per-original-failure recovery.
Python endpoint quarantine: focused and related regression tests performed separately; see endpoint-regression-output.txt.
Independent review found a remaining stale task-entry.lock requires explicit reconciliation rather than unsafe deletion. Child planned records are written before spawn; disk failure after spawn still requires process/receipt inspection rather than blindly repeating.

Production remains unchanged. Origin is https://github.com/Ken5InvestmentLab/screening-bot.git, branch research/weak-early-beta. A normal code push is needed because the live runner requires a clean checkout and HEAD equal to that remote branch. The owner has not yet authorized this external synchronization under the recovery-only permission, so no commit/push/live definition change was performed. Code push would trigger existing Cloud Reliability Regression only; deployment requires a separate cloud-deploy-* tag.

## Approval update
Ken5 subsequently authorized sending only this improvement's source code, tests and design documents to Ken5InvestmentLab/screening-bot research/weak-early-beta. No stock CSV, authentication material, or execution logs are included. This does not authorize starting publication or notification phases.
