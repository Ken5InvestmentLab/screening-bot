# Windows Premium runner

- Run `node --test scripts/windows/test-premium-runner.mjs`, `node --check scripts/windows/premium-runner.mjs`, and `powershell.exe -NoProfile -File scripts/windows/test-powershell.ps1` (Windows PowerShell 5.1) after changes.
- Keep the existing Premium model, reasoning effort, skill, field contract, freshness validation and authoritative posted/claim state. Do not replace research with templates or bypass dry-run failures.
- Deploy through `install-premium-task.ps1`. Require a successful Session 0 Probe before staging Scheduled mode (disabled). Enabling/disabling S4U tasks can also require administrator rights: verify CLI task activation first, then pause both desktop Premium automations. The CLI guard must prevent collection while either desktop automation is ACTIVE. Restore desktop automations if cutover fails; retire GUI recovery only after successful cutover.
- Probes must never collect, post, send completion notices or deploy. Use Google read-only scope and Discord GET only. Validate real CLI file/search tool events, not just a completion marker.
- Keep API billing keys out of child environments and force ChatGPT login. Do not copy authentication secrets into Git, logs or task arguments.
- Preserve serialized claim ownership. After an ambiguous or interrupted send, reconcile receipts before resuming; never blindly repost active claims.
- Keep HTML dispatch and its completion notice in the existing GitHub workflow. The CLI must not produce a second HTML notification.
- Keep wake/recovery bounded to scheduled execution. Do not disable Windows updates, configure automatic logon, store a Windows password, or kill unrelated Codex processes.
- A Session 0 probe establishes noninteractive capability; only actual scheduled-run evidence establishes successful recovery after reboot. Do not conflate them.

## Cloud beta daily runner

- Drain the initial forward fundamental queue with a bounded loop: each successful child must remove exactly its verified HTML import count. Stop on errors or no progress and reconcile retained claims before stage-only recovery; do not repeat completed analysis.
- Commit only the explicit beta generated leaves, require HEAD to equal the latest research remote ref, and deploy once through the exact `cloud-deploy-*` tag workflow. Require matching tag/SHA success and live health/OAuth checks before notifications. Rebuild private canonical input after Discord receipts change the ledger hash, then commit/push receipts without a second deploy. Check `node --test scripts/windows/test-weak-early-beta-daily-runner.mjs` after changing this sequence.

- Fundamental analysis is delivered to HTML only. Use the beta validator's `--save-only` path without a webhook, retain claim ownership through receipt import/HTML generation, and then finalize. Preserve Luna xhigh, cutoff validation, and legacy receipts. Verify changes with `node --test scripts/windows/test-weak-early-beta-point-in-time-post.mjs scripts/windows/test-weak-early-beta-model-preflight.mjs` and the relevant beta Python tests.
- Inspect streamed child logs and `CLOUD_DAILY_PHASE_V1` records before treating a quiet daily process as stalled. Full-corpus validation and monthly model fitting can remain silent for minutes; unchanged final receipts or one low CPU sample do not establish a deadlock. After acquisition completed, verify the cache SHA-256 against its source-quality receipt and resume the failed detection with that cache rather than downloading OHLCV again.
- For diagnostic GPT-6.1 Sol calls, probe the current Codex app executable with ChatGPT login before declaring the model unavailable; the separate fundamental CLI runtime may have a different version/catalog. Keep its fundamental model/configuration unchanged.

- Keep the Luna `xhigh` model used by the fundamental runner and the claim metadata in `weak_early_beta/fundamental.py` aligned. Verify a model with the same ChatGPT-login Codex CLI before changing it, and preserve the daily model preflight before OHLCV detection so an unsupported model cannot leave a new active claim.
- On Windows, launch npm through `node.exe` and the `npm-cli.js` beside the configured `npm.cmd`. Direct `spawn(npm.cmd, ...)` fails with `EINVAL`, and `shell: true` can break paths containing spaces. Resolve the CLI before starting the daily OHLCV work.
- When using a temporary clean clone, copy both the repository-root `.env` and `weak-early-beta-gate/.env` along with the two runner configs; Wrangler's `CLOUDFLARE_API_TOKEN` is loaded from the latter. Repoint the configs to the clone and remove both copied `.env` files after the run.
