; Navigrad Windows installer.
; Build with: & "C:\Users\Niljn\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
; Requires the PyInstaller onedir build to already exist at dist\Navigrad\
; (run packaging\navigrad.spec first).

#define MyAppName "Navigrad"
#define MyAppVersion "1.0.3"
#define MyAppExeName "Navigrad.exe"
#define MyAppPublisher "Nil J"

[Setup]
AppId={{6E9B6B7A-6A9B-4F2C-9C1E-2B3A7E9C4D1F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=Navigrad-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\Navigrad\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "check_webview2.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{tmp}\check_webview2.ps1"""; \
  StatusMsg: "Checking for Microsoft Edge WebView2 Runtime..."; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent

; Uninstall deliberately does NOT remove %APPDATA%\Navigrad -- the user's
; profile data, uploaded CVs, and saved API keys survive an uninstall, same
; convention as most Windows desktop apps.

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    ExtractTemporaryFile('check_webview2.ps1');
end;
