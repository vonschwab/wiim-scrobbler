#define MyAppName "WiiM Scrobbler"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "vonschwab"
#define MyAppURL "https://github.com/vonschwab/wiim-scrobbler"
#define MyAppExeName "WiiM Scrobbler.exe"
#define MyAppCliExeName "WiiM Scrobbler CLI.exe"

[Setup]
AppId={{0F9710F6-E9D2-47E3-9EB1-3067166413A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=wiim-scrobbler-setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Start WiiM Scrobbler when I sign in"; GroupDescription: "Startup options:"; Flags: unchecked

[Files]
Source: "..\dist\WiiM Scrobbler.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\WiiM Scrobbler CLI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.example.yaml"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Authorize Last.fm"; Filename: "{app}\{#MyAppCliExeName}"; Parameters: "--config ""{userappdata}\WiiM Scrobbler\config.yaml"" auth"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\WiiM Scrobbler.lnk"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  MaxWiimDevices = 3;

var
  ConfigPage: TWizardPage;
  LastFmPage: TInputQueryWizardPage;
  WiimPage: TWizardPage;
  ReplaceConfigCheck: TNewCheckBox;
  WiimNameLabels: array[0..2] of TNewStaticText;
  WiimNameEdits: array[0..2] of TNewEdit;
  WiimHostLabels: array[0..2] of TNewStaticText;
  WiimHostEdits: array[0..2] of TNewEdit;
  AddDeviceButton: TNewButton;
  VisibleWiimDevices: Integer;

function UserConfigPath(): String;
begin
  Result := ExpandConstant('{userappdata}\WiiM Scrobbler\config.yaml');
end;

function ConfigWriteAllowed(): Boolean;
begin
  Result := (not FileExists(UserConfigPath())) or ReplaceConfigCheck.Checked;
end;

function HasAnyConfigInput(): Boolean;
var
  Index: Integer;
begin
  Result :=
    (Trim(LastFmPage.Values[0]) <> '') or
    (Trim(LastFmPage.Values[1]) <> '') or
    (Trim(LastFmPage.Values[2]) <> '') or
    (Trim(LastFmPage.Values[3]) <> '');

  for Index := 0 to MaxWiimDevices - 1 do
  begin
    if Trim(WiimHostEdits[Index].Text) <> '' then
    begin
      Result := True;
    end;
  end;
end;

function HasCompleteConfigInput(): Boolean;
begin
  Result :=
    (Trim(LastFmPage.Values[0]) <> '') and
    (Trim(LastFmPage.Values[1]) <> '') and
    (Trim(LastFmPage.Values[2]) <> '') and
    (Trim(WiimHostEdits[0].Text) <> '');
end;

function YamlQuote(Value: String): String;
var
  Escaped: String;
begin
  Escaped := Value;
  StringChangeEx(Escaped, '''', '''''', True);
  Result := '''' + Escaped + '''';
end;

function NormalizeHost(Host: String): String;
begin
  Result := Trim(Host);
  if (Result <> '') and (Pos('://', Result) = 0) then
  begin
    Result := 'https://' + Result;
  end;
end;

function LineBreak(): String;
begin
  Result := Chr(13) + Chr(10);
end;

function DeviceName(Index: Integer): String;
begin
  Result := Trim(WiimNameEdits[Index].Text);
  if Result = '' then
  begin
    if Index = 0 then
      Result := 'WiiM'
    else
      Result := 'WiiM ' + IntToStr(Index + 1);
  end;
end;

procedure UpdateDeviceRows();
var
  Index: Integer;
  RowVisible: Boolean;
begin
  for Index := 0 to MaxWiimDevices - 1 do
  begin
    RowVisible := Index < VisibleWiimDevices;
    WiimNameLabels[Index].Visible := RowVisible;
    WiimNameEdits[Index].Visible := RowVisible;
    WiimHostLabels[Index].Visible := RowVisible;
    WiimHostEdits[Index].Visible := RowVisible;
  end;

  AddDeviceButton.Enabled := VisibleWiimDevices < MaxWiimDevices;
end;

procedure AddDeviceButtonClick(Sender: TObject);
begin
  if VisibleWiimDevices < MaxWiimDevices then
  begin
    VisibleWiimDevices := VisibleWiimDevices + 1;
    UpdateDeviceRows();
  end;
end;

procedure CreateStaticText(Page: TWizardPage; var Control: TNewStaticText; Caption: String; Top: Integer; Height: Integer);
begin
  Control := TNewStaticText.Create(Page);
  Control.Parent := Page.Surface;
  Control.Caption := Caption;
  Control.Left := 0;
  Control.Top := Top;
  Control.Width := Page.SurfaceWidth;
  Control.Height := Height;
  Control.WordWrap := True;
end;

procedure CreateDeviceRow(Index: Integer; Top: Integer);
begin
  WiimNameLabels[Index] := TNewStaticText.Create(WiimPage);
  WiimNameLabels[Index].Parent := WiimPage.Surface;
  WiimNameLabels[Index].Caption := 'Device name';
  WiimNameLabels[Index].Left := 0;
  WiimNameLabels[Index].Top := Top;
  WiimNameLabels[Index].Width := ScaleX(150);

  WiimNameEdits[Index] := TNewEdit.Create(WiimPage);
  WiimNameEdits[Index].Parent := WiimPage.Surface;
  WiimNameEdits[Index].Left := 0;
  WiimNameEdits[Index].Top := Top + ScaleY(16);
  WiimNameEdits[Index].Width := ScaleX(150);
  if Index = 0 then
    WiimNameEdits[Index].Text := 'WiiM'
  else
    WiimNameEdits[Index].Text := 'WiiM ' + IntToStr(Index + 1);

  WiimHostLabels[Index] := TNewStaticText.Create(WiimPage);
  WiimHostLabels[Index].Parent := WiimPage.Surface;
  WiimHostLabels[Index].Caption := 'IP address or host';
  WiimHostLabels[Index].Left := ScaleX(170);
  WiimHostLabels[Index].Top := Top;
  WiimHostLabels[Index].Width := ScaleX(230);

  WiimHostEdits[Index] := TNewEdit.Create(WiimPage);
  WiimHostEdits[Index].Parent := WiimPage.Surface;
  WiimHostEdits[Index].Left := ScaleX(170);
  WiimHostEdits[Index].Top := Top + ScaleY(16);
  WiimHostEdits[Index].Width := WiimPage.SurfaceWidth - ScaleX(170);
end;

procedure InitializeWizard();
var
  InfoLabel: TNewStaticText;
  ExistingLabel: TNewStaticText;
  Index: Integer;
begin
  ConfigPage := CreateCustomPage(
    wpSelectTasks,
    'WiiM Scrobbler Configuration',
    'Choose how the installer should handle your user config.'
  );
  CreateStaticText(
    ConfigPage,
    ExistingLabel,
    'WiiM Scrobbler stores settings at %APPDATA%\WiiM Scrobbler\config.yaml. If that file already exists, the installer will keep it unless you check the replacement option below.',
    0,
    ScaleY(48)
  );

  ReplaceConfigCheck := TNewCheckBox.Create(ConfigPage);
  ReplaceConfigCheck.Parent := ConfigPage.Surface;
  ReplaceConfigCheck.Caption := 'Replace existing config';
  ReplaceConfigCheck.Left := 0;
  ReplaceConfigCheck.Top := ScaleY(64);
  ReplaceConfigCheck.Width := ConfigPage.SurfaceWidth;
  ReplaceConfigCheck.Checked := False;

  LastFmPage := CreateInputQueryPage(
    ConfigPage.ID,
    'Last.fm Settings',
    'Enter your Last.fm API credentials.',
    'Create or view your Last.fm API account at https://www.last.fm/api/account to get the API key and shared secret. The session key is optional during setup; after install, use Start Menu > WiiM Scrobbler > Authorize Last.fm to create it, then paste it into the config if you did not enter it here.'
  );
  LastFmPage.Add('API key:', False);
  LastFmPage.Add('Username:', False);
  LastFmPage.Add('Shared secret:', False);
  LastFmPage.Add('Session key (optional; use Authorize Last.fm after install):', False);

  WiimPage := CreateCustomPage(
    LastFmPage.ID,
    'WiiM Devices',
    'Enter the WiiM devices this scrobbler should poll.'
  );
  CreateStaticText(
    WiimPage,
    InfoLabel,
    'Start with one WiiM device. Enter an IP address like 192.168.1.50, or a full host like https://192.168.1.50. Use + Add another WiiM for more devices.',
    0,
    ScaleY(44)
  );

  for Index := 0 to MaxWiimDevices - 1 do
  begin
    CreateDeviceRow(Index, ScaleY(54 + (Index * 48)));
  end;

  AddDeviceButton := TNewButton.Create(WiimPage);
  AddDeviceButton.Parent := WiimPage.Surface;
  AddDeviceButton.Caption := '+ Add another WiiM';
  AddDeviceButton.Left := 0;
  AddDeviceButton.Top := ScaleY(54 + (MaxWiimDevices * 48));
  AddDeviceButton.Width := ScaleX(160);
  AddDeviceButton.OnClick := @AddDeviceButtonClick;

  VisibleWiimDevices := 1;
  UpdateDeviceRows();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if (not ConfigWriteAllowed()) or (not HasAnyConfigInput()) then
  begin
    Exit;
  end;

  if CurPageID = LastFmPage.ID then
  begin
    if (Trim(LastFmPage.Values[0]) = '') or
       (Trim(LastFmPage.Values[1]) = '') or
       (Trim(LastFmPage.Values[2]) = '') then
    begin
      MsgBox('Enter the Last.fm API key, username, and shared secret, or leave the installer config fields blank and edit config.yaml after installation.', mbError, MB_OK);
      Result := False;
    end;
  end;

  if CurPageID = WiimPage.ID then
  begin
    if Trim(WiimHostEdits[0].Text) = '' then
    begin
      MsgBox('Enter the IP address or host for at least one WiiM device, or leave all installer config fields blank and edit config.yaml after installation.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure SaveConfigFile();
var
  ConfigPath: String;
  ConfigText: String;
  Host: String;
  Index: Integer;
begin
  if (not ConfigWriteAllowed()) or (not HasCompleteConfigInput()) then
  begin
    Exit;
  end;

  ConfigPath := UserConfigPath();
  ForceDirectories(ExtractFileDir(ConfigPath));

  ConfigText :=
    'lastfm:' + LineBreak() +
    '  api_key: ' + YamlQuote(Trim(LastFmPage.Values[0])) + LineBreak() +
    '  username: ' + YamlQuote(Trim(LastFmPage.Values[1])) + LineBreak() +
    '  shared_secret: ' + YamlQuote(Trim(LastFmPage.Values[2])) + LineBreak() +
    '  session_key: ' + YamlQuote(Trim(LastFmPage.Values[3])) + LineBreak() +
    LineBreak() +
    'devices:' + LineBreak();

  for Index := 0 to MaxWiimDevices - 1 do
  begin
    Host := NormalizeHost(WiimHostEdits[Index].Text);
    if Host <> '' then
    begin
      ConfigText := ConfigText +
        '  - name: ' + YamlQuote(DeviceName(Index)) + LineBreak() +
        '    host: ' + YamlQuote(Host) + LineBreak();
    end;
  end;

  if not SaveStringToFile(ConfigPath, ConfigText, False) then
  begin
    MsgBox('Could not write ' + ConfigPath + '. Use the tray menu to open and edit config.yaml after installation.', mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveConfigFile();
  end;
end;
