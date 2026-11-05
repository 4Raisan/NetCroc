#ifndef AppVersion
#define AppVersion "0.4.8"
#endif
#ifndef PortablePath
#define PortablePath "..\releases\NetCroc-v" + AppVersion + "-windows-x64-Portable.exe"
#endif
[Setup]
AppId=NetCroc.Desktop
AppName=NetCroc
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\NetCroc
DefaultGroupName=NetCroc
PrivilegesRequired=lowest
OutputDir=..\releases
OutputBaseFilename=NetCroc-v{#AppVersion}-windows-x64-Setup
SetupIconFile=..\assets\netcroc.ico
UninstallDisplayIcon={app}\NetCroc.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Files]
Source: "{#PortablePath}"; DestDir: "{app}"; DestName: "NetCroc.exe"; Flags: ignoreversion
[Icons]
Name: "{group}\NetCroc"; Filename: "{app}\NetCroc.exe"
Name: "{autodesktop}\NetCroc"; Filename: "{app}\NetCroc.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\NetCroc.exe"; Description: "Open NetCroc"; Flags: nowait postinstall skipifsilent
