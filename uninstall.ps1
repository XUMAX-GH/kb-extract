$ErrorActionPreference = "Stop"
$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
if (Test-Path $venvRoot) {
    Write-Host "Removing $venvRoot ..."
    Remove-Item -Recurse -Force $venvRoot
    Write-Host "Done."
} else {
    Write-Host "Nothing to uninstall."
}
