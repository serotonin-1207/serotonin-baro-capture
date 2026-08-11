$ErrorActionPreference = "Stop"

$payload = Join-Path $PSScriptRoot "dist\SerotoninBaroCapture.exe"
$outputDir = Join-Path $PSScriptRoot "Output"
$output = Join-Path $outputDir "Serotonin_BaroCapture_Portable_v1.0.0.exe"
$iexpress = Join-Path $env:WINDIR "System32\iexpress.exe"
$stage = Join-Path $env:TEMP ("SerotoninBaroCaptureIExpress-" + $PID)
$stagePayload = Join-Path $stage "SerotoninBaroCapture.exe"
$stageOutput = Join-Path $stage "Serotonin_BaroCapture_Portable_v1.0.0.exe"
$sedPath = Join-Path $stage "portable.sed"

if (-not (Test-Path -LiteralPath $payload)) { throw "Build the PyInstaller payload first: $payload" }
if (-not (Test-Path -LiteralPath $iexpress)) { throw "IExpress was not found: $iexpress" }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "node_modules\rcedit"))) {
    throw "Install the build dependency first: npm install rcedit@4.0.1 --no-save"
}

New-Item -ItemType Directory -Force $stage, $outputDir | Out-Null
Copy-Item -LiteralPath $payload -Destination $stagePayload -Force

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$stageOutput
FriendlyName=Serotonin BaroCapture v1.0.0 Portable
AppLaunched=SerotoninBaroCapture.exe
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0=SerotoninBaroCapture.exe
[SourceFiles]
SourceFiles0=$stage\
[SourceFiles0]
%FILE0%=
"@
Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII

Start-Process -FilePath $iexpress -ArgumentList @("/N", "/Q", $sedPath) -Wait
if (-not (Test-Path -LiteralPath $stageOutput)) { throw "IExpress did not create the portable executable." }

& node (Join-Path $PSScriptRoot "brand_portable.js") $stageOutput (Join-Path $PSScriptRoot "app.ico")
if ($LASTEXITCODE -ne 0) { throw "Portable branding failed: $LASTEXITCODE" }

Copy-Item -LiteralPath $stageOutput -Destination $output -Force
Get-Item -LiteralPath $output
