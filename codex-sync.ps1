# Entry point on Windows: .\codex-sync.ps1 <command> [options]
# Commands: catalog, bootstrap, preview, apply, verify, detail, rollback, prepare, scan, publish.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('catalog', 'bootstrap', 'preview', 'apply', 'verify', 'detail', 'rollback', 'prepare', 'scan', 'publish')]
    [string]$Command = 'preview',

    [string]$Message,
    [string[]]$Paths,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $RepoRoot 'scripts\runtime-windows.ps1')
$Python = Get-ProfilePython

switch ($Command) {
    'publish' {
        if (-not $Message -or -not $Paths) { throw 'Usage: .\codex-sync.ps1 publish -Message "commit message" -Paths file1,file2' }
        $Arguments = @($Python.Prefix) + @((Join-Path $RepoRoot 'scripts\publish_profile.py'), '--repo-root', $RepoRoot, '--message', $Message, '--paths') + $Paths
    }
    'scan' {
        $Arguments = @($Python.Prefix) + @((Join-Path $RepoRoot 'scripts\portable_config.py'), 'scan', '--repo-root', $RepoRoot) + @($RemainingArguments | Where-Object { $_ })
    }
    default {
        $Arguments = @($Python.Prefix) + @((Join-Path $RepoRoot 'scripts\sync_profile.py'), $Command, '--repo-root', $RepoRoot, '--platform', 'windows') + @($RemainingArguments | Where-Object { $_ })
    }
}
& $Python.File @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "codex-config-sync stopped with exit code $LASTEXITCODE; see the message above."
}
