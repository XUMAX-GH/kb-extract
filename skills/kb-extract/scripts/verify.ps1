$ErrorActionPreference = "Stop"
$path = $args[0]
if (-not $path) { Write-Error "用法: verify.ps1 <路径> [--fail-fast]" }

$extra = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extra += $args[$i] }

if (-not (Get-Command kb -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 kb CLI。请先运行 install.ps1。"
}
& kb verify $path --json @extra
exit $LASTEXITCODE
