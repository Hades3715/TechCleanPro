; ============================================================
;  TechClean - Instalador
;  Se compila con Inno Setup (gratis): https://jrsoftware.org/isdl.php
;
;  Que consigue esto, y que NO consigue:
;
;    SI: se instala en Archivos de programa, aparece en "Agregar o quitar
;        programas", crea accesos directos, y se desinstala limpio
;        llevandose todo lo que dejo.
;
;    NO: no reemplaza la firma digital. Windows va a seguir avisando la
;        primera vez, porque el instalador tampoco esta firmado. Avisa
;        menos y molesta menos, pero avisa.
;
;  Para compilarlo:
;    1. Instalar Inno Setup
;    2. Doble clic en Compilar_Instalador.bat (al lado de este archivo)
;
;  IMPORTANTE: antes hay que haber generado los .exe con
;  Generar_App_Instalable.bat, porque este script los empaqueta.
; ============================================================

#define NombreApp "TechClean"
#define VersionApp "1.5.0"
#define Autor "Edwin Javier Cortez Cardoza (Hades)"
#define WebApp "https://github.com/Hades3715/TechCleanPro"

[Setup]
AppId={{8F3C21A4-6D5B-4E92-9A17-TECHCLEAN0001}
AppName={#NombreApp}
AppVersion={#VersionApp}
AppVerName={#NombreApp} {#VersionApp}
AppPublisher={#Autor}
AppPublisherURL={#WebApp}
AppSupportURL={#WebApp}/issues
AppUpdatesURL={#WebApp}/releases
DefaultDirName={autopf}\{#NombreApp}
DefaultGroupName={#NombreApp}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE.md
OutputDir=.\salida
OutputBaseFilename=TechClean_{#VersionApp}_Instalador
SetupIconFile=..\assets\icono.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; La app pide permisos de administrador para funcionar, asi que se instala
; para todos los usuarios. Si se instalara solo para el usuario actual, la
; elevacion posterior podria no encontrar la instalacion.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "espanol"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
espanol.ElegirIdiomaApp=Que version de la aplicacion quieres instalar:
espanol.VersionES=TechClean en espanol
espanol.VersionEN=TechClean en ingles
espanol.CrearAccesoEscritorio=Crear un acceso directo en el Escritorio
english.ElegirIdiomaApp=Which version of the application do you want to install:
english.VersionES=TechClean in Spanish
english.VersionEN=TechClean in English
english.CrearAccesoEscritorio=Create a desktop shortcut

[Types]
Name: "espanol"; Description: "{cm:VersionES}"
Name: "ingles"; Description: "{cm:VersionEN}"
Name: "ambos"; Description: "Ambos / Both"

[Components]
Name: "es"; Description: "{cm:VersionES}"; Types: espanol ambos
Name: "en"; Description: "{cm:VersionEN}"; Types: ingles ambos

[Tasks]
Name: "escritorio"; Description: "{cm:CrearAccesoEscritorio}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\TechClean_ES.exe"; DestDir: "{app}"; Components: es; Flags: ignoreversion
Source: "..\TechClean_EN.exe"; DestDir: "{app}"; Components: en; Flags: ignoreversion
Source: "..\README.md";        DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md";       DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TechClean";           Filename: "{app}\TechClean_ES.exe"; Components: es
Name: "{group}\TechClean (English)"; Filename: "{app}\TechClean_EN.exe"; Components: en
Name: "{autodesktop}\TechClean";     Filename: "{app}\TechClean_ES.exe"; Components: es; Tasks: escritorio
Name: "{autodesktop}\TechClean (English)"; Filename: "{app}\TechClean_EN.exe"; Components: en and not es; Tasks: escritorio
Name: "{group}\{cm:UninstallProgram,TechClean}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\TechClean_ES.exe"; Description: "{cm:LaunchProgram,TechClean}"; Components: es; Flags: nowait postinstall skipifsilent
Filename: "{app}\TechClean_EN.exe"; Description: "{cm:LaunchProgram,TechClean}"; Components: en and not es; Flags: nowait postinstall skipifsilent

[UninstallRun]
; La app deja una tarea programada para arrancar con Windows y otra para la
; limpieza automatica. Si el desinstalador no las quita, quedan huerfanas
; intentando ejecutar un archivo que ya no existe — que es exactamente el
; tipo de basura que esta app critica de otros programas.
Filename: "{sys}\schtasks.exe"; Parameters: "/delete /tn ""TechClean_InicioAutomatico"" /f"; Flags: runhidden; RunOnceId: "QuitarInicioAuto"
Filename: "{sys}\schtasks.exe"; Parameters: "/delete /tn ""TechCleanPro_InicioAutomatico"" /f"; Flags: runhidden; RunOnceId: "QuitarInicioAutoViejo"
Filename: "{sys}\schtasks.exe"; Parameters: "/delete /tn ""TechClean_LimpiezaAutomatica"" /f"; Flags: runhidden; RunOnceId: "QuitarLimpiezaAutomatica"

[UninstallDelete]
; Los datos del usuario (preferencias, historial, registro de deshacer) NO
; se borran al desinstalar: si alguien reinstala, los recupera. Solo se
; limpia si marca la casilla del final.
Type: filesandordirs; Name: "{app}"

[Code]
var
  BorrarDatos: Boolean;

function InitializeUninstall(): Boolean;
begin
  BorrarDatos := MsgBox(
    'Quieres borrar tambien tus preferencias y el historial?' + #13#10 + #13#10 +
    'Si dices que NO, se conservan por si vuelves a instalar TechClean.' + #13#10 +
    'Si dices que SI, se borra todo lo que la aplicacion guardo sobre ti.',
    mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CarpetaDatos: String;
begin
  if (CurUninstallStep = usPostUninstall) and BorrarDatos then
  begin
    CarpetaDatos := ExpandConstant('{userappdata}\TechClean');
    if DirExists(CarpetaDatos) then
      DelTree(CarpetaDatos, True, True, True);
    // La carpeta del nombre anterior, por si viene de TechClean Pro
    CarpetaDatos := ExpandConstant('{userappdata}\TechCleanPro');
    if DirExists(CarpetaDatos) then
      DelTree(CarpetaDatos, True, True, True);
  end;
end;
