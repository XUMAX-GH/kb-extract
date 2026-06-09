$ErrorActionPreference = "Stop"

$path = $args[0]
if (-not $path) { Write-Error "usage: extract.ps1 <path> [--force] [--dry-run]" }

$extraArgs = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extraArgs += $args[$i] }

# 1. Verify CLI is installed.
$adapters = & kb adapters --json 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "kb CLI not found. Run install.ps1 from the kb-extract repo first."
}

# 2. Invoke extract.
$report = & kb extract $path --json @extraArgs
$exit = $LASTEXITCODE
Write-Host $report
exit $exit
