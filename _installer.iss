; Card Forge installer — Inno Setup 6.
;
; Per-user like Playlist Flow: no UAC, installs under
; %LOCALAPPDATA%\Programs ({autopf} under lowest privileges).
;
; Version comes from the build command:  ISCC /DAppVersion=1.0.0 _installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId is the identity Windows tracks the install by. NEVER change it,
; or upgrades stop finding the old install and uninstall entries orphan.
AppId={{6002082D-82B9-4D88-976A-D26DF8447884}
AppName=Card Forge
AppVersion={#AppVersion}
AppPublisher=darkrelay.net
AppPublisherURL=https://github.com/Crazy8697/CardForge
DefaultDirName={autopf}\CardForge
DefaultGroupName=Card Forge
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=CardForge-Setup-v{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\CardForge.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\CardForge\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Card Forge"; Filename: "{app}\CardForge.exe"
Name: "{autodesktop}\Card Forge"; Filename: "{app}\CardForge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CardForge.exe"; Description: "Start Card Forge"; Flags: nowait postinstall skipifsilent

; User data (config + presets in %APPDATA%\CardForge) is deliberately NOT
; touched by the uninstaller.
