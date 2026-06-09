$ErrorActionPreference = "Stop"

$path = $args[0]
if (-not $path) { Write-Error "用法: extract.ps1 <路径> [--force] [--dry-run]" }

$extraArgs = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extraArgs += $args[$i] }

# 1. 确认 CLI 已安装。
$adapters = & kb adapters --json 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "未找到 kb CLI。请先在 kb-extract 仓库根目录运行 install.ps1。"
}

# 2. 调用 extract。
$report = & kb extract $path --json @extraArgs
$exit = $LASTEXITCODE
Write-Host $report
exit $exit
