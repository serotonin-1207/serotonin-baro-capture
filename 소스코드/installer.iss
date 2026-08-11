; Serotonin 바로캡처 - Windows 설치 파일 빌드 스크립트 (Inno Setup 6)
; 빌드: "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
; 결과: Output\Serotonin_BaroCapture_Setup_v1.0.0.exe

#define AppName "Serotonin 바로캡처"
#define AppVersion "1.0.0"
#define AppPublisher "이은호"
#define AppPublisherURL "https://github.com/serotonin-1207/serotonin-baro-capture"
#define AppSupportURL "mailto:serotonin.1207@gmail.com"
#define AppExe "SerotoninBaroCapture.exe"

[Setup]
AppId={{8E5C2A41-7B3D-4F9A-9C1E-A1B2C3D4E5F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppSupportURL}
AppUpdatesURL={#AppPublisherURL}/releases
VersionInfoVersion=1.0.0.0
VersionInfoCompany=Serotonin
VersionInfoDescription=Serotonin 바로캡처 설치 프로그램
VersionInfoCopyright=이은호 · serotonin.1207@gmail.com
VersionInfoProductName=Serotonin 바로캡처
DefaultDirName={autopf}\Serotonin 바로캡처
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 관리자 권한 없이 현재 사용자에게만 설치 -> UAC 프롬프트 없음
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=Serotonin_BaroCapture_Setup_v1.0.0
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
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; v1 이전 이름으로 설치된 실행 파일을 같은 AppId의 업그레이드에서 정리한다.
Type: files; Name: "{app}\BaroCapture.exe"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; 자동 시작을 항상 등록한다(설치하면 기본으로 Windows 시작 시 자동 실행).
; 값 이름(NoAdsCapture)은 앱 내부 토글과 동일해 설정 화면과 일치한다.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "NoAdsCapture"; \
    ValueData: """{app}\{#AppExe}"" --minimized"; \
    Flags: uninsdeletevalue

[Run]
; 설치를 마치면 바로 실행한다(별도 체크 없이 기본 실행).
Filename: "{app}\{#AppExe}"; Description: "지금 {#AppName} 실행"; \
    Flags: nowait postinstall skipifsilent
