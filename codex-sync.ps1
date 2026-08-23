[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'plan', 'apply', 'verify', 'rollback', 'scan')]
    [string]$Command = 'doctor',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $RepoRoot 'scripts\codex_config_sync.py'

$PythonArguments = @()
if ($env:PYTHON_BIN) {
    $Python = Get-Command $env:PYTHON_BIN -ErrorAction Stop
}
else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) {
        $Python = Get-Command py -ErrorAction Stop
        $PythonArguments = @('-3.11')
    }
}

& $Python.Source @PythonArguments $Script $Command --repo-root $RepoRoot --platform windows @RemainingArguments
if ($LASTEXITCODE -ne 0) {
    throw "codex-config-sync failed with exit code $LASTEXITCODE"
}
