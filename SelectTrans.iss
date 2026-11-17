; 划词翻译 SelectTrans 安装脚本（Inno Setup 6）
; 编译：ISCC.exe SelectTrans.iss  →  dist\SelectTransSetup.exe

[Setup]
AppId={{17B667A0-5578-453A-9D62-49E21F72B84D}
AppName=划词翻译
AppVersion=1.0
AppPublisher=SelectTrans
DefaultDirName={localappdata}\Programs\SelectTrans
DisableProgramGroupPage=yes
DisableReadyMemo=no
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=SelectTransSetup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\SelectTrans.exe
UninstallDisplayName=划词翻译
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "autostart"; Description: "开机自动启动"; GroupDescription: "常规选项："
Name: "tray"; Description: "最小化到托盘运行（推荐）"; GroupDescription: "常规选项："
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "常规选项："

[Files]
Source: "dist\SelectTrans\SelectTrans.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\SelectTrans\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; 升级时不覆盖用户可能编辑过的词库
Source: "dist\SelectTrans\glossary.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{autoprograms}\划词翻译"; Filename: "{app}\SelectTrans.exe"
Name: "{autodesktop}\划词翻译"; Filename: "{app}\SelectTrans.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SelectTrans"; ValueData: """{app}\SelectTrans.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\SelectTrans.exe"; Description: "立即运行划词翻译"; Flags: nowait postinstall skipifsilent

[Code]
function BoolStr(B: Boolean): string;
begin
  if B then
    Result := 'true'
  else
    Result := 'false';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Dir: string;
  Lines: TStringList;
begin
  if CurStep = ssPostInstall then
  begin
    Dir := ExpandConstant('{userappdata}\SelectTrans');
    ForceDirectories(Dir);
    Lines := TStringList.Create;
    try
      Lines.Add('{');
      Lines.Add('  "autostart": ' + BoolStr(WizardIsTaskSelected('autostart')) + ',');
      Lines.Add('  "minimize_to_tray": ' + BoolStr(WizardIsTaskSelected('tray')));
      Lines.Add('}');
      Lines.SaveToFile(Dir + '\config.json');
    finally
      Lines.Free;
    end;
  end;
end;
