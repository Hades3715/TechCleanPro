# -*- coding: utf-8 -*-
"""Revisa el script del instalador sin compilarlo.

Compilarlo hace falta Inno Setup, que no todo el mundo tiene instalado. Lo
que si se puede comprobar desde aqui, y es donde estan los errores de
verdad, es que el script no mienta:

  * que los archivos que dice empaquetar existan
  * que la version coincida con la de la app — si no, se publica un
    instalador que dice 1.5.0 y por dentro trae otra cosa
  * que los nombres de las tareas programadas que borra al desinstalar
    sean EXACTAMENTE los que crea la app; si se escribe uno mal, la tarea
    queda huerfana intentando ejecutar un archivo que ya no existe, que es
    justo la basura que esta app le critica a otros programas
  * que las secciones del .iss esten bien formadas

Uso:  python herramientas\\revisar_instalador.py
"""
import io
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(RAIZ, "instalador", "TechClean.iss")

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


if not os.path.exists(ISS):
    print(f"No existe {ISS}")
    sys.exit(1)

script = io.open(ISS, encoding="utf-8").read()

print("== Version ==")
version_iss = re.search(r'#define\s+VersionApp\s+"([^"]+)"', script)
version_app = re.search(r'APP_VERSION\s*=\s*"([^"]+)"',
                        io.open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read())
comprobar("el .iss declara una version", version_iss is not None)
if version_iss and version_app:
    comprobar("coincide con APP_VERSION de la app",
              version_iss.group(1) == version_app.group(1),
              f"instalador={version_iss.group(1)}  app={version_app.group(1)}")

print("\n== Archivos que dice empaquetar ==")
for origen in re.findall(r'^Source:\s*"([^"]+)"', script, re.M):
    ruta = os.path.normpath(os.path.join(RAIZ, "instalador", origen))
    existe = os.path.exists(ruta)
    # Los .exe se generan al compilar: no tenerlos ahora no es un fallo del
    # script, pero conviene decirlo.
    if origen.endswith(".exe") and not existe:
        print(f"  [aviso] {origen:26} todavia no generado (corre Generar_App_Instalable.bat)")
        continue
    comprobar(f"existe {origen}", existe, "" if existe else ruta)

print("\n== Tareas programadas que borra al desinstalar ==")
fuente_opt = io.open(os.path.join(RAIZ, "optimizer.py"), encoding="utf-8").read()
tareas_app = set(re.findall(r'^(?:SCHEDULED_TASK_NAME|NOMBRE_TAREA_INICIO(?:_ANTERIOR)?)\s*=\s*"([^"]+)"',
                            fuente_opt, re.M))
tareas_iss = set(re.findall(r'/delete /tn ""([^"]+)""', script))
comprobar("la app crea al menos una tarea", bool(tareas_app), f"{sorted(tareas_app)}")
print(f"      la app usa      : {sorted(tareas_app)}")
print(f"      el instalador borra: {sorted(tareas_iss)}")
sin_borrar = tareas_app - tareas_iss
comprobar("el desinstalador borra todas las que la app crea", not sin_borrar,
          f"quedarian huerfanas: {sorted(sin_borrar)}" if sin_borrar else "")
inventadas = tareas_iss - tareas_app
comprobar("no intenta borrar tareas que la app nunca crea", not inventadas,
          f"sobran: {sorted(inventadas)}" if inventadas else "")

print("\n== Estructura del .iss ==")
secciones = re.findall(r'^\[(\w+)\]', script, re.M)
obligatorias = ["Setup", "Files", "Icons"]
for s in obligatorias:
    comprobar(f"tiene la seccion [{s}]", s in secciones)
comprobar("no repite ninguna seccion", len(secciones) == len(set(secciones)),
          f"{secciones}")
comprobar("declara el icono del instalador", "SetupIconFile=" in script)
comprobar("pide permisos de administrador (la app los necesita)",
          "PrivilegesRequired=admin" in script)
comprobar("incluye la licencia", "LicenseFile=" in script)

print("\n== Carpeta de datos que ofrece borrar ==")
fuente_prefs = io.open(os.path.join(RAIZ, "preferences.py"), encoding="utf-8").read()
carpetas_app = set(re.findall(r'^NOMBRE_CARPETA(?:_ANTERIOR)?\s*=\s*"([^"]+)"', fuente_prefs, re.M))
carpetas_iss = set(re.findall(r'\{userappdata\}\\\\?([A-Za-z]+)', script))
print(f"      la app usa      : {sorted(carpetas_app)}")
print(f"      el instalador mira: {sorted(carpetas_iss)}")
comprobar("ofrece borrar todas las carpetas de datos que la app usa",
          carpetas_app <= carpetas_iss,
          f"le faltan: {sorted(carpetas_app - carpetas_iss)}" if not carpetas_app <= carpetas_iss else "")

print("\n== Inno Setup instalado en este equipo ==")
posibles = [
    os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"),
    os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe"),
]
encontrado = next((p for p in posibles if os.path.exists(p)), None)
if encontrado:
    print(f"  [OK  ] encontrado: {encontrado}")
    print("         doble clic en instalador\\Compilar_Instalador.bat para generarlo")
else:
    print("  [info ] no esta instalado — el script esta listo, pero para")
    print("          generar el .exe del instalador hace falta Inno Setup:")
    print("          https://jrsoftware.org/isdl.php  (gratis)")

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
