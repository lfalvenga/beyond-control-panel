
#define MyAppName "Beyond Control Panel"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Beyond Aerospace"
#define MyAppExeName "Beyond Control Panel.exe"

[Setup]
AppId={{A3C71E5B-9D62-4A71-B8F4-2C5E6D8A9012}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\Beyond Aerospace\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=installer
OutputBaseFilename=BeyondControlPanel-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "dist\Beyond Control Panel\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Beyond Control Panel"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Beyond Control Panel"; \
    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Abrir Beyond Control Panel"; \
    Flags: postinstall nowait skipifsilent
