$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & python -m PyInstaller --noconfirm BaroCapture.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    New-Item -ItemType Directory -Force "Output" | Out-Null
    Copy-Item -LiteralPath "dist\SerotoninBaroCapture.exe" -Destination "Output\Serotonin_BaroCapture_Portable_v3.0.6.exe" -Force
    Get-Item -LiteralPath "Output\Serotonin_BaroCapture_Portable_v3.0.6.exe"
} finally {
    Pop-Location
}
