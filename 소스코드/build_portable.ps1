$ErrorActionPreference = "Stop"

$compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$payload = Join-Path $PSScriptRoot "dist\SerotoninBaroCapture.exe"
$output = Join-Path $PSScriptRoot "Output\Serotonin_BaroCapture_Portable_v1.0.0.exe"

if (-not (Test-Path -LiteralPath $compiler)) { throw "C# compiler not found: $compiler" }
if (-not (Test-Path -LiteralPath $payload)) { throw "Build the PyInstaller portable payload first: $payload" }

& $compiler /nologo /target:winexe /platform:x64 /optimize+ `
    /reference:System.Windows.Forms.dll `
    "/win32icon:$PSScriptRoot\app.ico" `
    "/resource:$payload,payload" `
    "/out:$output" `
    "$PSScriptRoot\portable_launcher.cs"

if ($LASTEXITCODE -ne 0) { throw "Portable launcher build failed: $LASTEXITCODE" }
Get-Item -LiteralPath $output
