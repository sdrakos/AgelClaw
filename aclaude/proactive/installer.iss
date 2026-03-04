; AgelClaw Windows Installer — Inno Setup Script
; ================================================
; Packages the Nuitka-compiled AgelClaw.dist/ into a setup wizard.
;
; Build: ISCC.exe installer.iss
; Or:    python build_installer.py

#define MyAppName "AgelClaw"
#define MyAppVersion "3.1.1"
#define MyAppPublisher "AgelClaw"
#define MyAppURL "https://github.com/sdrakos/AgelClaw"
#define MyAppExeName "AgelClaw.exe"

[Setup]
AppId={{A8E1C3F0-7B2D-4E5A-9F1B-3C6D8E0A2B4F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=build\installer
OutputBaseFilename=AgelClaw-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add AgelClaw to PATH"; GroupDescription: "System:"
Name: "autostart"; Description: "Start AgelClaw daemon on login"; GroupDescription: "System:"; Flags: unchecked

[Files]
; Main distribution (Nuitka output)
Source: "build\AgelClaw.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AgelClaw CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#MyAppExeName}"""; WorkingDir: "{app}"; Comment: "AgelClaw interactive chat"
Name: "{group}\AgelClaw Web UI"; Filename: "{app}\{#MyAppExeName}"; Parameters: "web"; Comment: "Start Web UI + Daemon"
Name: "{group}\AgelClaw Setup Wizard"; Filename: "{app}\{#MyAppExeName}"; Parameters: "setup"; Comment: "Configure API keys and settings"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "web"; Tasks: desktopicon; Comment: "AgelClaw Web UI"

[Run]
; Post-install: install Claude Code CLI via bundled npm
Filename: "{app}\node\npm.cmd"; Parameters: "install -g @anthropic-ai/claude-code"; \
  StatusMsg: "Installing Claude Code CLI (may take a minute)..."; \
  Flags: runhidden waituntilterminated

; Post-install: run agelclaw init
Filename: "{app}\{#MyAppExeName}"; Parameters: "init"; \
  StatusMsg: "Initializing AgelClaw project..."; \
  Flags: runhidden waituntilterminated

; Post-install: open setup wizard (optional)
Filename: "{app}\{#MyAppExeName}"; Parameters: "setup"; \
  Description: "Launch setup wizard to configure API keys"; \
  Flags: postinstall nowait skipifsilent shellexec

[UninstallRun]
; Clean up PATH on uninstall (handled by registry changes below)

[Registry]
; Add to user PATH (app dir + bundled node)
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app};{app}\node"; Tasks: addtopath; \
  Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
// ── Pascal Script helpers ──────────────────────────

function NeedsAddPath(Param: string): Boolean;
var
  OrigPath: string;
begin
  // Check if the install dir is already in PATH
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
end;

procedure RemovePath(Path: string);
var
  OrigPath: string;
  P: Integer;
begin
  // Remove install dir from PATH on uninstall
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    P := Pos(';' + Uppercase(Path), Uppercase(OrigPath));
    if P > 0 then
    begin
      Delete(OrigPath, P, Length(Path) + 1);
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath);
    end
    else begin
      P := Pos(Uppercase(Path) + ';', Uppercase(OrigPath));
      if P > 0 then
      begin
        Delete(OrigPath, P, Length(Path) + 1);
        RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath);
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemovePath(ExpandConstant('{app}\node'));
    RemovePath(ExpandConstant('{app}'));
  end;
end;

// Auto-start daemon on login
procedure CreateAutoStartEntry;
var
  StartupDir, BatPath: string;
begin
  StartupDir := ExpandConstant('{userstartup}');
  BatPath := StartupDir + '\agelclaw_daemon.bat';
  SaveStringToFile(BatPath,
    '@echo off' + #13#10 +
    'start /min "" "' + ExpandConstant('{app}\{#MyAppExeName}') + '" daemon' + #13#10,
    False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsTaskSelected('autostart') then
      CreateAutoStartEntry;
  end;
end;
