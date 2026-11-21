#ifndef AppVersion
  #error Supply /DAppVersion with the application version
#endif

[Setup]
AppId={{D9028ED7-4D7B-40B7-8485-D4C195B2FFEE}
AppName=Касов дневник
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\KasovDnevnik
DefaultGroupName=Касов дневник
UninstallDisplayIcon={app}\KasovDnevnik.exe
OutputDir=..\installers
OutputBaseFilename=KasovDnevnik-{#AppVersion}-windows-x64
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Files]
Source: "..\dist\KasovDnevnik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Касов дневник"; Filename: "{app}\KasovDnevnik.exe"

[Run]
Filename: "{app}\KasovDnevnik.exe"; Description: "Open Cash Ledger"; Flags: postinstall nowait skipifsilent
