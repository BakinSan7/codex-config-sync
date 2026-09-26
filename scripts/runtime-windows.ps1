function Get-ProfilePython {
    $Candidates = @()
    foreach ($Name in @('python', 'python3', 'py')) {
        $Command = Get-Command $Name -ErrorAction SilentlyContinue
        if ($Command) {
            $Prefix = if ($Name -eq 'py') { @('-3', '-X', 'utf8') } else { @('-X', 'utf8') }
            $Candidates += [pscustomobject]@{ File = $Command.Source; Prefix = $Prefix }
        }
    }
    $Bundled = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $Bundled) {
        $Candidates += [pscustomobject]@{ File = $Bundled; Prefix = @('-X', 'utf8') }
    }
    foreach ($Candidate in $Candidates) {
        $ProbeArgs = @($Candidate.Prefix) + @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)')
        try {
            & $Candidate.File @ProbeArgs 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $Candidate }
        } catch { continue }
    }
    throw 'Python 3.11+ was not found. Install Python or use the available Codex workspace runtime.'
}
