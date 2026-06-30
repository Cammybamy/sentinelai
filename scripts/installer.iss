; Inno Setup script for SentinelAI
; Produces: dist\SentinelAI-Setup.exe
; Requires: Inno Setup 6+ (https://jrsoftware.org/isdl.php)

#define MyAppName      "SentinelAI"
#define MyAppVersion   "0.1.0"
#define MyAppPublisher "DRGN Studios"
#define MyAppURL       "https://github.com/Cammybamy/sentinelai"
#define MyAppExeName   "SentinelAI.exe"
#define MyAppBuildDir  "..\dist\SentinelAI"

[Setup]
AppId={{E4A2B1C3-7F8D-4E9A-B0C2-3D5E6F7A8B9C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Uncomment when you have an icon file:
; SetupIconFile=..\assets\icon.ico
OutputDir=..\dist
OutputBaseFilename=SentinelAI-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Start SentinelAI automatically when Windows starts"; GroupDescription: "Windows startup:"
Name: "pshook"; Description: "Install PowerShell shell hook"; GroupDescription: "Shell integration:"

[Files]
; Bundle the entire PyInstaller output folder.
Source: "{#MyAppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Shell integration files.
Source: "..\shell\SentinelAI.psm1"; DestDir: "{app}\shell"; Flags: ignoreversion
Source: "..\shell\install_hook.ps1"; DestDir: "{app}\shell"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Registry]
; Auto-start on login (when user selects that task).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startup

[Run]
; Offer to launch SentinelAI after install.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Run the PS hook installer if the user selected that task.
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{app}\shell\install_hook.ps1"" -PythonPath ""{app}\{#MyAppExeName}"""; \
  Description: "Install PowerShell shell hook"; \
  Flags: nowait postinstall skipifsilent; \
  Tasks: pshook

[UninstallRun]
; Remove the auto-start registry entry on uninstall.
Filename: "powershell.exe"; \
  Parameters: "-Command ""Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name '{#MyAppName}' -ErrorAction SilentlyContinue"""; \
  Flags: runhidden
