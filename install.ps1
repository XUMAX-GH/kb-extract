# install.ps1 — kb-extract installer for Windows
$ErrorActionPreference = "Stop"

$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
$venvPath = Join-Path $venvRoot "venv"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install with: winget install --id=astral-sh.uv -e"
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating venv at $venvPath ..."
    uv venv $venvPath --python 3.11
}

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Installing kb-extract from $repo ..."
uv pip install --python (Join-Path $venvPath "Scripts\python.exe") -e $repo

Write-Host "Pre-downloading docling models (may take several minutes)..."
$env:DOCLING_ARTIFACTS_PATH = Join-Path $venvRoot "docling-models"
& (Join-Path $venvPath "Scripts\python.exe") -c "import docling; print('docling import ok')"

$kbBin = Join-Path $venvPath "Scripts"
Write-Host ""
Write-Host "Install complete. Add to PATH (one-time):"
Write-Host "  setx PATH `"$kbBin;`$env:PATH`""
Write-Host ""
Write-Host "Then run: kb --version"
