$ErrorActionPreference = 'Stop'
foreach ($name in @('premium-task.ps1','install-premium-task.ps1')) {
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name), [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}
Write-Output ('PowerShell syntax OK: ' + $PSVersionTable.PSVersion)
