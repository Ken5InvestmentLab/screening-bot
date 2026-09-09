param(
    [Parameter(Mandatory=$true)][string]$RepoPath,
    [Parameter(Mandatory=$true)][string]$CliJs,
    [ValidateSet('Probe','Scheduled')][string]$Mode = 'Probe'
)
$ErrorActionPreference = 'Stop'
$runtimeDir = Join-Path $env:USERPROFILE '.codex\premium-runner'
$binDir = Join-Path $runtimeDir 'bin'
New-Item -ItemType Directory -Path $binDir -Force | Out-Null
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$cli = (Resolve-Path -LiteralPath $CliJs).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo 'premium_worker\worker.mjs'))) { throw 'Premium worker repository missing.' }
$taskName = if ($Mode -eq 'Probe') { 'PremiumAlertCliProbe' } else { 'PremiumAlertCli' }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.State -eq 'Running') { throw 'Existing task is running; do not replace its configuration.' }
$node = (Get-Command node.exe).Source
# Keep only the runtime's required OneDrive inputs available before user logon.
# Never enumerate or print credential values; only the configured credential file path is used.
$requiredFiles = @('AGENTS.md','.env','premium_worker\worker.mjs','premium_worker\.env','premium_worker\AUTOMATION_PROMPT.md','premium_worker\FUNDAMENTAL_EXAMPLES.md','premium_worker\state','premium_worker\state\premium_alert_state.json')
foreach ($relative in $requiredFiles) {
    $localFile = Join-Path $repo $relative
    if (Test-Path -LiteralPath $localFile) { & attrib.exe +P -U $localFile | Out-Null }
}
foreach ($envFile in @((Join-Path $repo '.env'), (Join-Path $repo 'premium_worker\.env'))) {
    if (-not (Test-Path -LiteralPath $envFile)) { continue }
    foreach ($line in [IO.File]::ReadAllLines($envFile)) {
        if ($line -match '^\s*(?:GOOGLE_APPLICATION_CREDENTIALS|GOOGLE_SERVICE_ACCOUNT_FILE)\s*=\s*(.*?)\s*$') {
            $credentialFile = $Matches[1].Trim().Trim('"').Trim("'")
            if (-not [IO.Path]::IsPathRooted($credentialFile)) { $credentialFile = Join-Path $repo $credentialFile }
            if (Test-Path -LiteralPath $credentialFile) { & attrib.exe +P -U $credentialFile | Out-Null }
        }
    }
}
$configFile = Join-Path $runtimeDir 'config.json'
$config = [ordered]@{
    repoPath = $repo
    cliJs = $cli
    nodePath = $node
    codexHome = (Join-Path $env:USERPROFILE '.codex')
    userProfile = $env:USERPROFILE
    runtimeDir = $runtimeDir
    model = 'gpt-5.6-terra'
    reasoningEffort = 'xhigh'
    automationFiles = @(
        (Join-Path $env:USERPROFILE '.codex\automations\premium-alert-snapshot-worker\automation.toml'),
        (Join-Path $env:USERPROFILE '.codex\automations\premium-alert-snapshot-worker-1540\automation.toml')
    )
}
if ($Mode -eq 'Scheduled') {
    $probeFile = Join-Path $runtimeDir 'probe-latest.json'
    $probe = Get-Content -LiteralPath $probeFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $probe.ok -or $probe.sessionId -ne 0 -or -not $probe.cli -or -not $probe.sheetsRead -or -not $probe.discordRead) {
        throw 'A successful noninteractive Session 0 probe is required before cutover.'
    }
    if ((Get-Date) - [datetime]$probe.completedAt -gt (New-TimeSpan -Hours 24)) { throw 'Probe is stale; run a fresh probe.' }
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($configFile, ($config | ConvertTo-Json -Depth 5), $utf8)
foreach ($file in @('premium-task.ps1','premium-runner.mjs')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $binDir $file) -Force
}
if ($existing) {
    Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $runtimeDir ($taskName+'-before-'+(Get-Date -Format yyyyMMddHHmmss)+'.xml')) -Encoding Unicode
}
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType S4U -RunLevel Limited
$action = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -Argument (
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Mode {1} -ConfigPath "{2}"' -f (Join-Path $binDir 'premium-task.ps1'), $Mode, $configFile
) -WorkingDirectory $runtimeDir
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances Queue -ExecutionTimeLimit (New-TimeSpan -Hours 4)
# Stage production disabled. Pause desktop automations only after registration succeeds,
# then explicitly enable this task. Registration failure cannot create a schedule gap.
if ($Mode -eq 'Scheduled') { $settings.Enabled = $false }
$taskArgs = @{TaskName=$taskName; Action=$action; Principal=$principal; Settings=$settings; Force=$true; Description='ChatGPT subscription Premium worker. S4U, no desktop session, shared lock, no API billing fallback.'}
if ($Mode -eq 'Scheduled') {
    $taskArgs.Trigger = @((New-ScheduledTaskTrigger -Daily -At '12:55'), (New-ScheduledTaskTrigger -Daily -At '15:26'))
}
Register-ScheduledTask @taskArgs | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, @{n='LogonType';e={$_.Principal.LogonType}} | ConvertTo-Json -Compress
if ($Mode -eq 'Probe') { Start-ScheduledTask -TaskName $taskName }
