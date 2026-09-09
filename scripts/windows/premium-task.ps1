param(
    [ValidateSet('Probe','Scheduled')][string]$Mode = 'Probe',
    [Parameter(Mandatory=$true)][string]$ConfigPath
)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$env:CODEX_HOME = $config.codexHome
$env:USERPROFILE = $config.userProfile
$env:OPENAI_API_KEY = $null
$env:CODEX_API_KEY = $null
$env:PYTHONIOENCODING = 'utf-8'
$env:PATH = (Split-Path $config.nodePath) + ';' + $env:PATH
$mutex = New-Object System.Threading.Mutex($false, 'Global\CodexPremiumScheduledWorker')
$held = $false
$exitCode = 1
try {
    try { $held = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $held = $true }
    if (-not $held) { throw 'Another Premium task owns the execution lock.' }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class PremiumTaskPower {
    [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
}
'@
    [PremiumTaskPower]::SetThreadExecutionState([uint32]2147483649) | Out-Null
    $env:PREMIUM_RUNNER_SESSION_ID = [string][System.Diagnostics.Process]::GetCurrentProcess().SessionId
    & $config.nodePath (Join-Path $PSScriptRoot 'premium-runner.mjs') $Mode $ConfigPath
    $exitCode = $LASTEXITCODE
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $config.runtimeDir 'launcher-error.txt') -Encoding UTF8
} finally {
    if ('PremiumTaskPower' -as [type]) { [PremiumTaskPower]::SetThreadExecutionState([uint32]2147483648) | Out-Null }
    if ($held) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
exit $exitCode
