; ============================================================================
; PinkyBrain v5.2.0 — Windows Installer (Inno Setup)
; P2P Distributed AI Network
; ============================================================================

#define AppName "PinkyBrain"
#define AppVersion "5.2.0"
#define Publisher "PinkyBrain-ai"
#define AppURL "https://github.com/PinkyBrain-ai/pinkybrain"
#define AppId "{{A7B3C9D4-E5F6-7890-ABCD-EF1234567890}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName=C:\PinkyBrain
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\pinkybrain.exe
OutputBaseFilename=PinkyBrain-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
SetupIconFile=assets\pinkybrain.ico
WizardImageFile=assets\wizard-banner.bmp
WizardSmallImageFile=assets\wizard-small.bmp
LicenseFile=assets\LICENSE.rtf
CloseApplications=force

; Directories
DirExistsWarning=no
CreateAppDir=yes
UsePreviousAppDir=no

; Uninstaller
UninstallFilesDir={app}\uninstall

; =============================================================================
[Types]
Name: "full"; Description: "Full installation"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "main"; Description: "PinkyBrain Application"; Types: full custom; Flags: fixed
Name: "python"; Description: "Embedded Python 3.12"; Types: full custom; Flags: fixed
Name: "service"; Description: "Windows Service (auto-start)"; Types: full custom; Flags: fixed
Name: "tray"; Description: "System Tray Launcher"; Types: full custom
Name: "firewall"; Description: "Firewall Rule (P2P port)"; Types: full custom

; =============================================================================
[Files]
; --- Application files ---
Source: "app\src\pinkybrain_v5.py"; DestDir: "{app}\app\src"; Flags: ignoreversion; Components: main
Source: "app\requirements.txt"; DestDir: "{app}\app"; Flags: ignoreversion; Components: main
Source: "app\config\*"; DestDir: "{app}\app\config"; Flags: ignoreversion recursesubdirs; Components: main
Source: "app\assets\*"; DestDir: "{app}\app\assets"; Flags: ignoreversion recursesubdirs; Components: main
Source: "app\scripts\*"; DestDir: "{app}\app\scripts"; Flags: ignoreversion recursesubdirs; Components: main

; --- Embedded Python ---
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs; Components: python

; --- WinSW service wrapper ---
Source: "bin\pinkybrain-service.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: service
Source: "pinkybrain-service.xml"; DestDir: "{app}"; Flags: ignoreversion; Components: service

; --- Launcher ---
Source: "bin\pinkybrain.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: main

; --- Post-install script ---
Source: "post_install.py"; DestDir: "{app}\scripts"; Flags: ignoreversion; Components: main

; --- Tray launcher ---
Source: "pinkybrain_tray.py"; DestDir: "{app}\scripts"; Flags: ignoreversion; Components: tray

; --- Shared models README ---
Source: "shared_models_README.txt"; DestDir: "{app}\shared_models"; DestName: "README.txt"; Flags: ignoreversion; Components: main

; =============================================================================
[Dirs]
Name: "{app}\data"; Permissions: admins-full system-full
Name: "{app}\data\config"; Permissions: admins-full system-full
Name: "{app}\data\logs"; Permissions: admins-full system-full
Name: "{app}\data\conversations"; Permissions: admins-full system-full
Name: "{app}\data\memory"; Permissions: admins-full system-full
Name: "{app}\shared_models"; Permissions: admins-full system-full users-readexec

; =============================================================================
[Tasks]
Name: "desktopicon"; Description: "Create &Desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startservice"; Description: "Start PinkyBrain service after installation"; GroupDescription: "Service:"; Flags: checkedonce

; =============================================================================
[Run]
; --- Post-install: generate secrets, config, keys ---
Filename: "{app}\python\python.exe"; \
    Parameters: "{app}\scripts\post_install.py /NODENAME={code:GetNodeName} /PORT={code:GetPort}"; \
    WorkingDir: "{app}"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Generating P2P secret and node identity..."; \
    Components: main

; --- Install Windows Service ---
Filename: "{app}\pinkybrain-service.exe"; \
    Parameters: "install"; \
    WorkingDir: "{app}"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Installing PinkyBrain service..."; \
    Components: service

; --- Configure service recovery ---
Filename: "sc.exe"; \
    Parameters: "failure PinkyBrain reset=0 actions= restart/30000/restart/60000/restart/120000"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Configuring service recovery..."; \
    Components: service

; --- Set service to auto-start ---
Filename: "sc.exe"; \
    Parameters: "config PinkyBrain start= auto"; \
    Flags: runhidden waituntilterminated; \
    Components: service

; --- Firewall rule (Private + Domain profiles only) ---
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""PinkyBrain P2P"" dir=in action=allow protocol=TCP localport={code:GetPort} profile=private,domain"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Adding firewall rule for P2P port..."; \
    Components: firewall

; --- Start the service ---
Filename: "sc.exe"; \
    Parameters: "start PinkyBrain"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Starting PinkyBrain service..."; \
    Components: service; \
    Tasks: startservice

; --- Launch tray app ---
Filename: "{app}\python\python.exe"; \
    Parameters: "{app}\scripts\pinkybrain_tray.py"; \
    WorkingDir: "{app}"; \
    Flags: nowait runhidden; \
    Components: tray

; =============================================================================
[UninstallRun]
; --- Stop service ---
Filename: "sc.exe"; Parameters: "stop PinkyBrain"; Flags: runhidden waituntilterminated

; --- Remove service ---
Filename: "{app}\pinkybrain-service.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated

; --- Remove firewall rule ---
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PinkyBrain P2P"""; Flags: runhidden waituntilterminated

; =============================================================================
[UninstallDelete]
; Data is only deleted if user confirms in CurUninstallStepChanged
; These entries clean up logs/temp; user data is handled by the confirmation dialog
Type: filesandordirs; Name: "{app}\\data\\logs"
Type: filesandordirs; Name: "{app}\\data\\conversations"

; =============================================================================
[Registry]
; Add to PATH (user level)
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; \
    Flags: dontcreatekey uninsdeletevalue

; =============================================================================
[Code]
var
  NodeNameEdit: TEdit;
  PortEdit: TEdit;
  CustomPage: TWizardPage;

procedure InitializeWizard();
var
  NodeNameLabel: TLabel;
  PortLabel: TLabel;
  PortNote: TLabel;
begin
  CustomPage := CreateCustomPage(
    wpLicense,
    'PinkyBrain Configuration',
    'Configure your PinkyBrain node settings.'
  );

  NodeNameLabel := TLabel.Create(WizardForm);
  NodeNameLabel.Caption := 'Node Name (unique identifier on the mesh):';
  NodeNameLabel.Parent := CustomPage.Surface;

  NodeNameEdit := TEdit.Create(WizardForm);
  NodeNameEdit.Parent := CustomPage.Surface;
  NodeNameEdit.Top := NodeNameLabel.Top + NodeNameLabel.Height + 4;
  NodeNameEdit.Width := CustomPage.SurfaceWidth;
  NodeNameEdit.Text := '';

  PortLabel := TLabel.Create(WizardForm);
  PortLabel.Caption := 'P2P Port:';
  PortLabel.Top := NodeNameEdit.Top + NodeNameEdit.Height + 16;
  PortLabel.Parent := CustomPage.Surface;

  PortEdit := TEdit.Create(WizardForm);
  PortEdit.Parent := CustomPage.Surface;
  PortEdit.Top := PortLabel.Top + PortLabel.Height + 4;
  PortEdit.Width := 80;
  PortEdit.Text := '8080';

  PortNote := TLabel.Create(WizardForm);
  PortNote.Caption := 'Default: 8080. Change if another service uses this port.';
  PortNote.Top := PortEdit.Top + PortEdit.Height + 4;
  PortNote.Font.Color := clGrayText;
  PortNote.Parent := CustomPage.Surface;
end;

function GetNodeName(Param: string): string;
begin
  Result := NodeNameEdit.Text;
  if Result = '' then
    Result := 'pinkybrain-' + GetComputerNameString();
end;

function GetPort(Param: string): string;
var
  PortVal: Integer;
begin
  try
    PortVal := StrToInt(PortEdit.Text);
    if (PortVal < 1) or (PortVal > 65535) then
      PortVal := 8080;
  except
    PortVal := 8080;
  end;
  Result := IntToStr(PortVal);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsAdminLoggedOn then
  begin
    MsgBox('PinkyBrain installation requires Administrator privileges.' + #13#10 +
           'Please run this installer as Administrator.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Secure data directory: SYSTEM + Admin only
    DataDir := ExpandConstant('{app}\data');
    Exec('icacls.exe', DataDir + ' /inheritance:r /grant:r SYSTEM:F /grant:r Administrators:F', '',
         SW_HIDE, ewWaitUntilTerminated, ErrorCode);

    // Secure node.json specifically
    Exec('icacls.exe', ExpandConstant('{app}\data\config\node.json') +
         ' /inheritance:r /grant:r SYSTEM:F /grant:r Administrators:F', '',
         SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Delete all PinkyBrain data (configs, logs, conversations, memory)?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{app}\data'), True, True, True);
      DelTree(ExpandConstant('{app}\shared_models'), True, True, True);
    end;
  end;
end;