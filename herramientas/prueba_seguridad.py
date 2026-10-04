# -*- coding: utf-8 -*-
"""Comprueba el auditor de seguridad (seguridad.py).

Por que importa
---------------
El auditor nacio de un malware REAL encontrado en el equipo del
desarrollador, que el antivirus no vio en seis meses: una tarea programada
con nombre aleatorio que lanzaba pythonw.exe renombrado a "gep.exe" desde
una carpeta falsa de Autodesk en AppData. El primer caso de esta prueba es
ese malware, tal cual: si alguien cambia las reglas y deja de verse, falla.

Igual de importante es lo contrario: no marcar software legitimo. Un
auditor que grita por todo ensena a ignorarlo. Los casos de Lenovo y
Discord son de programas reales que una primera version marcaba sin razon.

evaluar() es pura: todo con datos inventados, sin tocar el sistema. Al
final se corre una vez el analisis real, solo para ver que no revienta.

Uso:  python herramientas/prueba_seguridad.py
"""
import os
import sys

import _rutas
_rutas.poner_en_ruta()
import seguridad as seg

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


U = r"C:\Users\ana"
CARPETAS = [os.path.normcase(os.path.abspath(r)) + os.sep for r in
            (U + r"\AppData\Roaming", U + r"\AppData\Local", U + r"\AppData\Local\Temp",
             U + r"\Downloads", r"C:\ProgramData")]
MALWARE = U + r"\AppData\Roaming\Autodesk\Inventor Interoperability 2026\FileCache\gep.exe"
LENOVO = r"C:\ProgramData\Lenovo\Udc\Hosts\x64\MessagingPlugin.exe"
DISCORD = U + r"\AppData\Local\Discord\app-1.0\Discord.exe"
SIN_FIRMA = U + r"\AppData\Local\Temp\abc\x.exe"


def firma(estado, original, producto=""):
    return {"estado": estado, "original": original, "producto": producto, "firmante": ""}


base = {
    "carpetas": CARPETAS,
    "firmas": {os.path.normcase(MALWARE): firma("Valid", "pythonw.exe", "Python"),
               os.path.normcase(LENOVO): firma("Valid", "UdcPluginHost.exe", "UdcPluginHost"),
               os.path.normcase(DISCORD): firma("Valid", "Discord.exe", "Discord"),
               os.path.normcase(SIN_FIRMA): firma("NotSigned", "x.exe")},
    "tareas": [{"nombre": "Orion Terrorist Ghana 32308-S-1-5-21-1-2-3-1001", "carpeta": "\\", "autor": "",
                "estado": "Running", "exe": MALWARE, "args": '"' + MALWARE.replace("gep.exe", "node_modules.asar") + '"'},
               {"nombre": "OneDrive Reporting Task", "carpeta": "\\", "autor": "Microsoft",
                "exe": U + r"\AppData\Local\Microsoft\OneDrive\OneDriveStandaloneUpdater.exe", "args": ""},
               {"nombre": "Actualizador", "carpeta": "\\Vendor\\", "autor": "",
                "exe": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "args": "-w hidden -enc SQBFAFgA"}],
    "inicio": [{"lnk": U + r"\...\Startup\server.lnk", "destino": U + r"\AppData\Local\Temp\tmp-1\m1kvrKfB8.exe",
                "existe": False},
               {"lnk": U + r"\...\Startup\Spotify.lnk", "destino": r"C:\Program Files\Spotify\Spotify.exe",
                "existe": False}],
    "procesos": [{"pid": 10, "nombre": "gep.exe", "exe": MALWARE, "cmd": "gep.exe node_modules.asar"},
                 {"pid": 11, "nombre": "MessagingPlugin.exe", "exe": LENOVO, "cmd": ""},
                 {"pid": 12, "nombre": "Discord.exe", "exe": DISCORD, "cmd": ""},
                 {"pid": 13, "nombre": "x.exe", "exe": SIN_FIRMA, "cmd": ""},
                 {"pid": 14, "nombre": "svc.exe", "exe": r"C:\Windows\svc.exe",
                  "cmd": "svc.exe -o stratum+tcp://pool.example:3333 --donate-level 1"}],
    "conexiones": [{"pid": 14, "estado": "ESTABLISHED", "local": ("192.168.1.5", 50000), "remoto": ("1.2.3.4", 3333)}],
    "defender": {"exclusiones": ["C:\\", r"C:\Program Files\MiApp"], "exclusiones_legibles": True,
                 "antivirus": [{"nombre": "Windows Defender", "activo": False, "al_dia": True},
                               {"nombre": "McAfee", "activo": True, "al_dia": False}]},
}

h = seg.evaluar(base)
por_ruta = {}
for x in h:
    por_ruta.setdefault((x["ruta"] or "").lower(), []).append(x)

print("== El malware real ==")
tarea = [x for x in h if x["clave"] == "seg_hallazgo_tarea" and x["ruta"] == MALWARE]
comprobar(tarea and tarea[0]["nivel"] == "alto", "la tarea que lanza el pythonw.exe renombrado es ALTO")
comprobar(tarea and "seg_motivo_interprete_renombrado" in tarea[0]["motivos"]
          and tarea[0]["original"] == "pythonw.exe", "y dice que es pythonw.exe disfrazado")
comprobar(tarea and "seg_motivo_sin_autor" in tarea[0]["motivos"], "y que la tarea no tiene autor")
comprobar(h and h[0]["nivel"] == "alto", "lo grave sale primero")
comprobar(sum(1 for x in h if x["ruta"] == MALWARE) == 1,
          "el mismo .exe no sale dos veces (tarea y proceso son el mismo hallazgo)")
huerfano = [x for x in h if x["clave"] == "seg_hallazgo_inicio_huerfano"]
comprobar(len(huerfano) == 1 and huerfano[0]["nivel"] == "info",
          "el server.lnk que apunta a un .exe borrado de Temp sale como INFO (y el de Program Files no)")

print("== Sin falsos positivos ==")
comprobar(LENOVO.lower() not in por_ruta, "Lenovo: renombrado pero firmado y no es interprete -> nada")
comprobar(DISCORD.lower() not in por_ruta, "Discord en AppData, firmado y con su nombre -> nada")
comprobar(not any("onedrivestandaloneupdater" in (x["ruta"] or "").lower() for x in h),
          "tarea de OneDrive con autor y firmada -> nada")

print("== Otras señales ==")
comprobar(any(x["ruta"] == SIN_FIRMA and x["nivel"] == "medio" for x in h), "sin firma en Temp -> MEDIO")
oculto = [x for x in h if "seg_motivo_comando_oculto" in x["motivos"]]
comprobar(oculto and oculto[0]["nivel"] == "alto", "PowerShell -w hidden -enc al arrancar -> ALTO (aunque este en System32)")
comprobar(any(x["clave"] == "seg_hallazgo_minero" for x in h), "parametros de minero (stratum, --donate-level) -> ALTO")
comprobar(any(x["clave"] == "seg_hallazgo_conexion_pool" for x in h), "conexion al puerto 3333 -> ALTO")
excl = {x["ruta"]: x["nivel"] for x in h if x["clave"] == "seg_hallazgo_exclusion"}
comprobar(excl.get("C:\\") == "alto", "excluir la unidad C entera de Defender -> ALTO")
comprobar(excl.get(r"C:\Program Files\MiApp") == "info", "excluir una carpeta de programa -> INFO")
comprobar(not any(x["clave"] == "seg_hallazgo_sin_antivirus" for x in h),
          "Defender apagado con McAfee activo NO es 'sin antivirus'")
comprobar(any(x["clave"] == "seg_hallazgo_antivirus_viejo" for x in h), "McAfee con firmas viejas -> MEDIO")
sin_av = seg.evaluar({"carpetas": CARPETAS, "defender": {"antivirus": [{"nombre": "Defender", "activo": False,
                                                                        "al_dia": True}]}})
comprobar(any(x["clave"] == "seg_hallazgo_sin_antivirus" and x["nivel"] == "alto" for x in sin_av),
          "ningun antivirus activo -> ALTO")
comprobar(seg.evaluar({"carpetas": CARPETAS}) == [], "sin datos -> sin hallazgos (no inventa)")

print("== Programas en la red ==")
red = seg.programas_en_red(
    procesos=[{"pid": 1, "nombre": "steam.exe", "exe": r"C:\Program Files\Steam\steam.exe"},
              {"pid": 2, "nombre": "raro.exe", "exe": U + r"\AppData\Local\raro.exe"},
              {"pid": 3, "nombre": "local.exe", "exe": r"C:\x\local.exe"}],
    conexiones=[{"pid": 1, "estado": "LISTEN", "local": ("0.0.0.0", 27036), "remoto": None},
                {"pid": 2, "estado": "LISTEN", "local": ("0.0.0.0", 4444), "remoto": None},
                {"pid": 2, "estado": "ESTABLISHED", "local": ("192.168.1.5", 50001), "remoto": ("8.8.8.8", 443)},
                {"pid": 3, "estado": "LISTEN", "local": ("127.0.0.1", 9000), "remoto": None}])
nombres = {r["nombre"]: r for r in red}
comprobar("local.exe" not in nombres, "escuchar solo en 127.0.0.1 no cuenta (no es una puerta a la red)")
comprobar(nombres.get("raro.exe", {}).get("escucha") == [4444] and nombres["raro.exe"]["conexiones"] == 1,
          "puertos y conexiones por programa")

print("== Analisis real (solo que no reviente) ==")
if seg.IS_WINDOWS:
    try:
        real = seg.evaluar(seg.recolectar())
        comprobar(isinstance(real, list), f"recolectar + evaluar en este equipo: {len(real)} hallazgo(s)")
    except Exception as e:
        comprobar(False, f"el analisis real lanzo {type(e).__name__}: {e}")

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
