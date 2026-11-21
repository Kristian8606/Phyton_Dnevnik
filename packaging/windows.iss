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
