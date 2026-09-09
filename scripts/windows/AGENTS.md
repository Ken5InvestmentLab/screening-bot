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
