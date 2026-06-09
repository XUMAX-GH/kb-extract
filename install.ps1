# install.ps1 — kb-extract Windows 端安装脚本
$ErrorActionPreference = "Stop"

$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
$venvPath = Join-Path $venvRoot "venv"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 uv。请先安装：winget install --id=astral-sh.uv -e"
}

if (-not (Test-Path $venvPath)) {
    Write-Host "正在 $venvPath 创建 venv ..."
    uv venv $venvPath --python 3.11
}

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "正在从 $repo 安装 kb-extract ..."
uv pip install --python (Join-Path $venvPath "Scripts\python.exe") -e $repo

Write-Host "预下载 docling 模型中（首次可能需要几分钟）..."
$env:DOCLING_ARTIFACTS_PATH = Join-Path $venvRoot "docling-models"
& (Join-Path $venvPath "Scripts\python.exe") -c "import docling; print('docling import ok')"

$kbBin = Join-Path $venvPath "Scripts"
Write-Host ""
Write-Host "安装完成。请把以下目录加入 PATH（一次性）："
Write-Host "  setx PATH `"$kbBin;`$env:PATH`""
Write-Host ""
Write-Host "之后运行：kb --version"
