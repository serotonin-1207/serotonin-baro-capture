; Serotonin 바로캡처 - Windows 설치 파일 빌드 스크립트 (Inno Setup 6)
; 빌드: "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
; 결과: Output\Serotonin_BaroCapture_Setup_v3.0.7.exe

#define AppName "Serotonin 바로캡처"
#define AppVersion "3.0.7"
#define AppPublisher "이은호"
#define AppPublisherURL "https://github.com/serotonin-1207/serotonin-baro-capture"
#define AppSupportURL "mailto:serotonin.1207@gmail.com"
#define AppExe "SerotoninBaroCapture.exe"

#ifdef TestInstall
#define SetupAppId "SerotoninBaroCaptureBuildTest"
#define SetupUninstallId SetupAppId
#define StartupName "SerotoninBaroCaptureBuildTest"
#else
#define SetupAppId "{{8E5C2A41-7B3D-4F9A-9C1E-A1B2C3D4E5F6}"
#define SetupUninstallId "{8E5C2A41-7B3D-4F9A-9C1E-A1B2C3D4E5F6}"
#define StartupName "NoAdsCapture"
#endif

[Setup]
AppId={#SetupAppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppSupportURL}
VersionInfoVersion=3.0.7.0
VersionInfoCompany=Serotonin
VersionInfoDescription=Serotonin 바로캡처 설치 프로그램
VersionInfoCopyright=이은호 · serotonin.1207@gmail.com
VersionInfoProductName=Serotonin 바로캡처
DefaultDirName={code:DefaultInstallDir}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 신규 설치는 현재 사용자용이 기본값이다. 업그레이드는 기존 설치 범위를 따른다.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousPrivileges=yes
UsePreviousAppDir=yes
AppMutex=Global\NoAdsCapture_SingleInstance
OutputDir=Output
OutputBaseFilename=Serotonin_BaroCapture_Setup_v3.0.7
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "dist\SerotoninBaroCaptureInstalled\SerotoninBaroCaptureApp.exe"; DestDir: "{app}"; DestName: "{#AppExe}"; Flags: ignoreversion
Source: "dist\SerotoninBaroCaptureInstalled\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs

[InstallDelete]
; v1 이전 이름으로 설치된 실행 파일을 같은 AppId의 업그레이드에서 정리한다.
Type: files; Name: "{app}\BaroCapture.exe"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; 기존 설치 범위에 맞춰 Windows 로그인 시 트레이에서 시작한다.
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#StartupName}"; \
    ValueData: """{app}\{#AppExe}"" --minimized"; Flags: uninsdeletevalue

[Run]
; 설치를 마치면 바로 실행한다(별도 체크 없이 기본 실행).
Filename: "{app}\{#AppExe}"; Description: "지금 {#AppName} 실행"; \
    Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupUninstallId}_is1';
  StartupKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

var
  PreviousDir: String;

function ReadInstallDir(RootKey: Integer; var Dir: String): Boolean;
begin
  Result := RegKeyExists(RootKey, UninstallKey);
  if Result then begin
    if not RegQueryStringValue(RootKey, UninstallKey, 'Inno Setup: App Path', Dir) then
      RegQueryStringValue(RootKey, UninstallKey, 'InstallLocation', Dir);
    Dir := RemoveBackslashUnlessRoot(Trim(Dir));
  end;
end;

function InitializeSetup: Boolean;
var
  MachineDir, UserDir: String;
  MachineInstalled, UserInstalled: Boolean;
  Problem: String;
begin
  MachineInstalled := ReadInstallDir(HKLM64, MachineDir);
  UserInstalled := ReadInstallDir(HKCU64, UserDir);
  if MachineInstalled and UserInstalled then
    Problem := '모든 사용자용과 현재 사용자용 바로캡처가 모두 등록되어 있습니다. Windows 설정의 설치된 앱에서 중복 설치를 정리한 뒤 다시 실행해 주세요.'
  else if MachineInstalled and not IsAdminInstallMode then
    Problem := '모든 사용자용 바로캡처가 설치되어 있습니다. /CURRENTUSER 옵션 없이 설치 파일을 다시 실행해 주세요.'
  else if UserInstalled and IsAdminInstallMode then
    Problem := '현재 사용자용 바로캡처가 설치되어 있습니다. /ALLUSERS 옵션 없이 기존에 설치한 계정에서 설치 파일을 다시 실행해 주세요.'
  else if MachineInstalled then
    PreviousDir := MachineDir
  else if UserInstalled then
    PreviousDir := UserDir;

  if (Problem = '') and (MachineInstalled or UserInstalled) and (PreviousDir = '') then
    Problem := '기존 바로캡처 설치 경로를 확인할 수 없습니다. Windows 설정의 설치된 앱에서 설치 상태를 확인해 주세요.';
  Result := Problem = '';
  if not Result then begin
    Log(Problem);
    SuppressibleMsgBox(Problem, mbError, MB_OK, IDOK);
  end;
end;

function DefaultInstallDir(Param: String): String;
begin
  if PreviousDir <> '' then
    Result := PreviousDir
  else
    Result := ExpandConstant('{autopf}\Serotonin 바로캡처');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectDir) and (PreviousDir <> '');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if (PreviousDir <> '') and
     (CompareText(RemoveBackslashUnlessRoot(WizardDirValue), PreviousDir) <> 0) then begin
    Result := '업데이트는 기존 설치 폴더에서만 진행할 수 있습니다. /DIR 옵션 없이 다시 실행해 주세요.';
    Log(Result);
  end;
end;

#ifndef TestInstall
procedure CurStepChanged(CurStep: TSetupStep);
var
  InstallDir, OldCommand, NewCommand, UserCommand, MachineCommand: String;
begin
  if (CurStep <> ssPostInstall) or not IsAdminInstallMode then
    Exit;
  InstallDir := ExpandConstant('{app}');
  OldCommand := '"' + InstallDir + '\BaroCapture.exe" --minimized';
  NewCommand := '"' + InstallDir + '\{#AppExe}" --minimized';
  { 같은 설치를 가리키는 이전 사용자별 항목만 통합한다. }
  if RegQueryStringValue(HKLM64, StartupKey, '{#StartupName}', MachineCommand) and
     (CompareText(MachineCommand, NewCommand) = 0) and
     RegQueryStringValue(HKCU64, StartupKey, '{#StartupName}', UserCommand) and
     ((CompareText(UserCommand, OldCommand) = 0) or (CompareText(UserCommand, NewCommand) = 0)) then
    RegDeleteValue(HKCU64, StartupKey, '{#StartupName}');
end;
#endif
