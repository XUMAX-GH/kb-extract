$ErrorActionPreference = "Stop"
$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
if (Test-Path $venvRoot) {
    Write-Host "正在移除 $venvRoot ..."
    Remove-Item -Recurse -Force $venvRoot
    Write-Host "完成。"
} else {
    Write-Host "没有需要卸载的内容。"
}
