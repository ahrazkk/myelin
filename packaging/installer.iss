; Inno Setup script for the Myelin installer. Built by .github/workflows/windows-app.yml:
;   ISCC.exe /DMyAppVersion=0.2.0 packaging\installer.iss
; Installs per user (no admin prompt) into %LOCALAPPDATA%\Programs\Myelin.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{8C8F5D2A-6B5E-4E1A-9B7F-4D2C1E0A9F31}
AppName=Myelin
AppVersion={#MyAppVersion}
AppPublisher=Ahraz Kibria
AppPublisherURL=https://github.com/ahrazkk/myelin
DefaultDirName={localappdata}\Programs\Myelin
DefaultGroupName=Myelin
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist-installer
OutputBaseFilename=Myelin-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=myelin.ico
UninstallDisplayIcon={app}\Myelin.exe
CloseApplications=yes

[Tasks]
Name: "autostart"; Description: "Start Myelin when I sign in (recommended for the wallpaper)"; Flags: checkedonce
Name: "desktopicon"; Description: "Add a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Myelin\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Myelin"; Filename: "{app}\Myelin.exe"
Name: "{autodesktop}\Myelin"; Filename: "{app}\Myelin.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Myelin"; \
  ValueData: """{app}\Myelin.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Myelin.exe"; Description: "Open Myelin now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM Myelin.exe /F"; Flags: runhidden; RunOnceId: "StopMyelin"
