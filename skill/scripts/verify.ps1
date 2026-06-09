$ErrorActionPreference = "Stop"
$path = $args[0]
if (-not $path) { Write-Error "usage: verify.ps1 <path> [--fail-fast]" }

$extra = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extra += $args[$i] }

if (-not (Get-Command kb -ErrorAction SilentlyContinue)) {
    Write-Error "kb CLI not found. Run install.ps1 first."
}
& kb verify $path --json @extra
exit $LASTEXITCODE
