#ifndef AppVersion
  #error Supply /DAppVersion with the application version
#endif

[Setup]
AppId={{D9028ED7-4D7B-40B7-8485-D4C195B2FFEE}
AppName=Дневник
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Dnevnik
UsePreviousAppDir=no
DefaultGroupName=Дневник
UninstallDisplayIcon={app}\Dnevnik.exe
OutputDir=..\installers
OutputBaseFilename=Dnevnik-{#AppVersion}-windows-x64
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Files]
Source: "..\dist\Dnevnik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Дневник"; Filename: "{app}\Dnevnik.exe"

[Run]
Filename: "{app}\Dnevnik.exe"; Description: "Отвори Дневник"; Flags: postinstall nowait skipifsilent
Filename: "{app}\Dnevnik.exe"; Flags: nowait skipifnotsilent; Check: IsDnevnikUpdate

[Code]
function OpenProcess(Access: DWORD; InheritHandle: BOOL; ProcessId: DWORD): THandle;
  external 'OpenProcess@kernel32.dll stdcall setuponly';
function WaitForSingleObject(ProcessHandle: THandle; Milliseconds: DWORD): DWORD;
  external 'WaitForSingleObject@kernel32.dll stdcall setuponly';
function CloseHandle(ProcessHandle: THandle): BOOL;
  external 'CloseHandle@kernel32.dll stdcall setuponly';

function DnevnikParentProcess: Integer;
begin
  Result := StrToIntDef(ExpandConstant('{param:DnevnikParent|0}'), 0);
end;

function IsDnevnikUpdate: Boolean;
begin
  Result := DnevnikParentProcess > 0;
end;

function InitializeSetup: Boolean;
var
  ProcessHandle: THandle;
begin
  Result := True;
  if not IsDnevnikUpdate then
    Exit;

  { Wait for the running copy to unload the files being replaced. }
  ProcessHandle := OpenProcess($00100000, False, DnevnikParentProcess);
  if ProcessHandle = 0 then
    Exit;

  try
    Result := WaitForSingleObject(ProcessHandle, 30000) = 0;
  finally
    CloseHandle(ProcessHandle);
  end;
  if not Result then
    SuppressibleMsgBox('Затвори „Дневник“ и опитай да го обновиш отново.', mbError, MB_OK, IDOK);
end;
