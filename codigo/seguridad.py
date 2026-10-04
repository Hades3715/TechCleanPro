"""
seguridad.py
Auditor de seguridad: busca señales de malware que los antivirus no
siempre ven. SOLO LEE. No cierra, no borra, no desactiva nada: dice qué
encontró, por qué es sospechoso y dónde está, y la decisión es de quien
lo mira.

Por qué existe
--------------
Nació de un caso real, en el equipo del propio desarrollador: un malware
en Python que llevaba seis meses instalado sin que el antivirus (McAfee)
lo viera. Sus señales eran claras una vez que se miraban:

  * Una tarea programada con nombre aleatorio ("Orion Terrorist Ghana
    32308-..."), sin autor, que se lanzaba al iniciar sesión.
  * El programa que lanzaba, `gep.exe`, era en realidad python.exe
    renombrado (firmado por la Python Software Foundation, con
    OriginalFilename = python.exe), escondido en una carpeta con nombre de
    Autodesk dentro de AppData.
  * Ejecutaba un "node_modules.asar" que era código Python ofuscado.

Un antivirus busca FIRMAS de malware conocido; este estaba cifrado para no
coincidir con ninguna. Este auditor busca COMPORTAMIENTOS: dónde vive un
programa, cómo se arranca, si es un intérprete disfrazado. Ningún
programa legítimo necesita hacer esas cosas.

Separado en dos: `recolectar()` pregunta al sistema y `evaluar()` decide
qué es sospechoso. evaluar() es pura, para poder probarla con datos que
imitan casos reales (prueba_seguridad.py) sin tener malware a mano.
"""

import json
import os
import platform
import re
import subprocess

import psutil

from idiomas import t

IS_WINDOWS = platform.system() == "Windows"

# Programas que ejecutan código ajeno: un script, un comando. Que uno de
# estos aparezca RENOMBRADO es de las señales más fuertes que hay.
INTERPRETES = {"python.exe", "pythonw.exe", "node.exe", "powershell.exe", "pwsh.exe", "cmd.exe",
               "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe", "regsvr32.exe", "autoit3.exe",
               "java.exe", "javaw.exe", "ruby.exe", "perl.exe", "php.exe", "bun.exe", "deno.exe"}

# Señales en la línea de comandos de algo que se arranca solo.
COMANDOS_OCULTOS = ("-enc ", "-encodedcommand", "frombase64string", "-windowstyle hidden", "-w hidden",
                    "mshta", "wscript", "cscript", "regsvr32 /s /i:http", "bitsadmin", "certutil -urlcache",
                    "iex(", "invoke-expression", "downloadstring")

MINEROS_NOMBRES = ("xmrig", "nbminer", "t-rex", "phoenixminer", "lolminer", "gminer", "nanominer", "ethminer",
                   "cpuminer", "ccminer", "nicehash", "teamredminer", "srbminer", "xmr-stak", "minergate")
MINEROS_COMANDO = ("stratum+tcp", "stratum+ssl", "--donate-level", "cryptonight", "randomx", "--cpu-max-threads")
PUERTOS_POOL = {3333, 4444, 5555, 7777, 14444, 14433, 45560, 45700}


def carpetas_de_usuario():
    """Carpetas donde cualquier programa puede escribir sin permisos de
    administrador. Ahí vive mucho software legítimo (Discord, Roblox,
    OneDrive...), así que estar aquí NO es malo por sí solo: es la base
    sobre la que las demás señales pesan más."""
    perfil = os.path.expanduser("~")
    rutas = [os.environ.get("TEMP"), os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"),
             os.path.join(perfil, "Downloads"), os.path.join(perfil, "Descargas"),
             os.environ.get("PUBLIC"), os.environ.get("ProgramData"),
             os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")]
    return [os.path.normcase(os.path.abspath(r)) + os.sep for r in rutas if r]


def en_carpeta_de_usuario(ruta, carpetas=None):
    if not ruta:
        return False
    ruta = os.path.normcase(os.path.abspath(ruta))
    return any(ruta.startswith(c) for c in (carpetas or carpetas_de_usuario()))


def _ps_json(script, timeout=90):
    if not IS_WINDOWS:
        return []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        datos = json.loads((r.stdout or "").strip() or "[]")
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    return datos if isinstance(datos, list) else []


def _lista_ps(rutas):
    return ",".join("'" + r.replace("'", "''") + "'" for r in rutas)


# ============================================================
#  Recolectar (pregunta al sistema; no decide nada)
# ============================================================

def leer_tareas_programadas():
    """[{nombre, carpeta, autor, estado, exe, args}] de las tareas con un
    programa como acción. Las variables (%APPDATA%...) ya expandidas."""
    return _ps_json(
        "Get-ScheduledTask | ForEach-Object { $t = $_; $t.Actions | Where-Object { $_.Execute } | "
        "ForEach-Object { [pscustomobject]@{ nombre = $t.TaskName; carpeta = $t.TaskPath; "
        "autor = [string]$t.Author; estado = [string]$t.State; "
        "exe = [Environment]::ExpandEnvironmentVariables($_.Execute.Trim('\"')); "
        "args = [string]$_.Arguments } } } | ConvertTo-Json -Compress", timeout=120)


def leer_accesos_inicio():
    """Accesos directos de las carpetas de Inicio, con su destino resuelto
    (inspeccionar_arranque los da como la ruta del .lnk, no de lo que abren)."""
    carpetas = [os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")]
    lnks = []
    for c in carpetas:
        try:
            lnks += [os.path.join(c, f) for f in os.listdir(c) if f.lower().endswith(".lnk")]
        except OSError:
            pass
    if not lnks:
        return []
    return _ps_json(
        f"$sh = New-Object -ComObject WScript.Shell; @({_lista_ps(lnks)}) | ForEach-Object {{ "
        "$l = $sh.CreateShortcut($_); [pscustomobject]@{ lnk = $_; destino = [string]$l.TargetPath; "
        "args = [string]$l.Arguments; existe = (Test-Path -LiteralPath $l.TargetPath) } } | ConvertTo-Json -Compress")


def leer_firmas(rutas):
    """{ruta: {estado, firmante, original, producto}}. `original` es el
    OriginalFilename de la versión del archivo: el nombre con el que se
    compiló. Si no coincide con el nombre actual, alguien lo renombró."""
    rutas = sorted({r for r in rutas if r and os.path.isfile(r)})
    if not rutas:
        return {}
    datos = _ps_json(
        f"@({_lista_ps(rutas)}) | ForEach-Object {{ $s = Get-AuthenticodeSignature -LiteralPath $_; "
        "$v = (Get-Item -LiteralPath $_).VersionInfo; [pscustomobject]@{ ruta = $_; estado = [string]$s.Status; "
        "firmante = [string]$s.SignerCertificate.Subject; original = [string]$v.OriginalFilename; "
        "producto = [string]$v.ProductName } } | ConvertTo-Json -Compress", timeout=180)
    return {os.path.normcase(d.get("ruta", "")): d for d in datos if isinstance(d, dict)}


def leer_defender():
    """Exclusiones de Defender (necesita administrador: sin él vienen vacías
    y se marca `exclusiones_legibles` False) y antivirus registrados."""
    pref = _ps_json("$p = Get-MpPreference -ErrorAction SilentlyContinue; [pscustomobject]@{ "
                    "rutas = @($p.ExclusionPath); procesos = @($p.ExclusionProcess); "
                    "extensiones = @($p.ExclusionExtension) } | ConvertTo-Json -Compress -Depth 3")
    pref = pref[0] if pref else {}
    rutas = [r for r in (pref.get("rutas") or []) if r]
    legibles = not any("N/A" in r or "admin" in r.lower() for r in rutas)
    antivirus = []
    for a in _ps_json("Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
                      "-ErrorAction SilentlyContinue | Select-Object displayName, productState | ConvertTo-Json -Compress"):
        try:
            estado = int(a.get("productState") or 0)
        except (TypeError, ValueError):
            estado = 0
        # productState: el segundo byte dice si está activo (0x10/0x11),
        # el tercero si las firmas están al día (0x00). No es API pública
        # documentada, pero es lo que leen todas las herramientas.
        antivirus.append({"nombre": a.get("displayName") or "?",
                          "activo": ((estado >> 8) & 0xFF) in (0x10, 0x11),
                          "al_dia": (estado & 0xFF) == 0x00})
    return {"exclusiones": rutas if legibles else [], "exclusiones_legibles": legibles,
            "exclusiones_procesos": [p for p in (pref.get("procesos") or []) if p],
            "antivirus": antivirus}


def leer_procesos():
    procesos = []
    for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        procesos.append({"pid": p.info["pid"], "nombre": p.info.get("name") or "",
                         "exe": p.info.get("exe") or "", "cmd": " ".join(p.info.get("cmdline") or [])})
    return procesos


def leer_conexiones():
    conexiones = []
    try:
        for c in psutil.net_connections(kind="inet"):
            conexiones.append({"pid": c.pid, "estado": c.status,
                               "local": (c.laddr.ip, c.laddr.port) if c.laddr else None,
                               "remoto": (c.raddr.ip, c.raddr.port) if c.raddr else None})
    except Exception:
        pass
    return conexiones


def recolectar():
    """Todo lo que evaluar() necesita. Tarda ~20-40 s (las firmas y las
    tareas programadas van por PowerShell): llamar desde un hilo."""
    procesos = leer_procesos()
    tareas = leer_tareas_programadas()
    inicio = leer_accesos_inicio()
    carpetas = carpetas_de_usuario()
    a_firmar = [p["exe"] for p in procesos if en_carpeta_de_usuario(p["exe"], carpetas)]
    a_firmar += [x.get("exe") for x in tareas if en_carpeta_de_usuario(x.get("exe"), carpetas)]
    a_firmar += [x.get("destino") for x in inicio if x.get("existe") and en_carpeta_de_usuario(x.get("destino"), carpetas)]
    return {"procesos": procesos, "tareas": tareas, "inicio": inicio, "firmas": leer_firmas(a_firmar),
            "defender": leer_defender(), "conexiones": leer_conexiones(), "carpetas": carpetas}


# ============================================================
#  Evaluar (puro: decide qué es sospechoso)
# ============================================================

NIVELES = ("alto", "medio", "info")


def _renombrado(ruta, firma):
    """El nombre con el que se compiló, si el archivo ahora se llama de
    otra forma. None si no hay dato o coincide."""
    original = ((firma or {}).get("original") or "").strip().lower()
    actual = os.path.basename(ruta or "").lower()
    if not original or not actual:
        return None
    # Algunos ponen el nombre sin .exe o con .mui/.dll de recurso: se
    # compara la base.
    if original.rsplit(".", 1)[0] == actual.rsplit(".", 1)[0]:
        return None
    return original


def _evaluar_ejecutable(ruta, firma, carpetas):
    """(nivel, [claves de motivo], original) para un .exe, o (None, [], None)."""
    if not en_carpeta_de_usuario(ruta, carpetas):
        return None, [], None
    motivos = []
    nivel = None
    original = _renombrado(ruta, firma)
    if original and original in INTERPRETES:
        return "alto", ["seg_motivo_interprete_renombrado"], original
    estado = (firma or {}).get("estado")
    # Renombrado pero FIRMADO y sin ser un intérprete: es normal. Lenovo
    # firma un solo "UdcPluginHost.exe" que instala con varios nombres, y
    # Roblox compila "RobloxApp.exe" y lo instala como RobloxPlayerBeta.exe.
    # Se vio en el equipo del desarrollador: marcarlos era ruido.
    if original and estado and estado != "Valid":
        nivel, motivos = "medio", ["seg_motivo_renombrado"]
    if estado and estado != "Valid":
        nivel = "medio"
        motivos.append("seg_motivo_sin_firma")
    return nivel, motivos, original


def evaluar(datos):
    """Lista de hallazgos {nivel, clave (título), motivos [claves], ruta,
    detalle}, de más grave a menos. `datos` es lo que da recolectar()."""
    carpetas = datos.get("carpetas") or carpetas_de_usuario()
    firmas = datos.get("firmas") or {}
    hallazgos = []

    def firma_de(ruta):
        return firmas.get(os.path.normcase(ruta or ""))

    # 1. Tareas programadas que arrancan algo desde carpetas de usuario.
    for tarea in datos.get("tareas") or []:
        exe = tarea.get("exe") or ""
        args = (tarea.get("args") or "").lower()
        nivel, motivos, original = _evaluar_ejecutable(exe, firma_de(exe), carpetas)
        oculto = any(x in (exe.lower() + " " + args) for x in COMANDOS_OCULTOS)
        if oculto:
            nivel = "alto"
            motivos.append("seg_motivo_comando_oculto")
        if nivel is None and en_carpeta_de_usuario(exe, carpetas) and not tarea.get("autor") \
                and (tarea.get("carpeta") or "\\") == "\\":
            # Una tarea en la raíz, sin autor, que arranca algo de AppData:
            # sola no prueba nada, pero merece una mirada.
            nivel, motivos = "medio", ["seg_motivo_tarea_anonima"]
        if nivel:
            if not tarea.get("autor"):
                motivos.append("seg_motivo_sin_autor")
            hallazgos.append({"nivel": nivel, "clave": "seg_hallazgo_tarea", "motivos": motivos, "ruta": exe,
                              "detalle": f'{tarea.get("carpeta", "")}{tarea.get("nombre", "")}  →  {exe} {tarea.get("args") or ""}'.strip(),
                              "original": original})

    # 2. Accesos directos de Inicio.
    for acceso in datos.get("inicio") or []:
        destino = acceso.get("destino") or ""
        if not acceso.get("existe"):
            if en_carpeta_de_usuario(destino, carpetas):
                hallazgos.append({"nivel": "info", "clave": "seg_hallazgo_inicio_huerfano",
                                  "motivos": ["seg_motivo_destino_borrado"], "ruta": acceso.get("lnk"),
                                  "detalle": f'{acceso.get("lnk")}  →  {destino}'})
            continue
        nivel, motivos, original = _evaluar_ejecutable(destino, firma_de(destino), carpetas)
        if nivel:
            hallazgos.append({"nivel": nivel, "clave": "seg_hallazgo_inicio", "motivos": motivos,
                              "ruta": destino, "detalle": f'{acceso.get("lnk")}  →  {destino}', "original": original})

    # 3. Procesos en ejecución.
    ya = {h["ruta"].lower() for h in hallazgos if h.get("ruta")}
    pids_por_exe = {}
    for p in datos.get("procesos") or []:
        nombre = (p.get("nombre") or "").lower()
        cmd = (p.get("cmd") or "").lower()
        if any(m in nombre for m in MINEROS_NOMBRES) or any(m in cmd for m in MINEROS_COMANDO):
            hallazgos.append({"nivel": "alto", "clave": "seg_hallazgo_minero", "motivos": ["seg_motivo_minero"],
                              "ruta": p.get("exe"), "detalle": f'PID {p.get("pid")}  {p.get("nombre")}  {p.get("cmd", "")[:200]}'})
            continue
        exe = p.get("exe") or ""
        if exe.lower() in ya or exe in pids_por_exe:
            pids_por_exe.setdefault(exe, []).append(p.get("pid"))
            continue
        nivel, motivos, original = _evaluar_ejecutable(exe, firma_de(exe), carpetas)
        if nivel:
            pids_por_exe[exe] = [p.get("pid")]
            hallazgos.append({"nivel": nivel, "clave": "seg_hallazgo_proceso", "motivos": motivos, "ruta": exe,
                              "detalle": f'PID {p.get("pid")}  {p.get("cmd", "")[:240]}', "original": original})

    # 4. Conexiones a puertos típicos de minería.
    nombres = {p.get("pid"): p.get("nombre") for p in datos.get("procesos") or []}
    for c in datos.get("conexiones") or []:
        remoto = c.get("remoto")
        if remoto and remoto[1] in PUERTOS_POOL and c.get("estado") == "ESTABLISHED":
            hallazgos.append({"nivel": "alto", "clave": "seg_hallazgo_conexion_pool", "motivos": ["seg_motivo_pool"],
                              "ruta": None, "detalle": f'{nombres.get(c.get("pid"), "?")} (PID {c.get("pid")})  →  {remoto[0]}:{remoto[1]}'})

    # 5. Defender: exclusiones y antivirus.
    defender = datos.get("defender") or {}
    for ruta in defender.get("exclusiones") or []:
        nivel = "alto" if (en_carpeta_de_usuario(ruta, carpetas) or re.fullmatch(r"[A-Za-z]:\\?", ruta.strip())) else "info"
        hallazgos.append({"nivel": nivel, "clave": "seg_hallazgo_exclusion",
                          "motivos": ["seg_motivo_exclusion_usuario" if nivel == "alto" else "seg_motivo_exclusion"],
                          "ruta": ruta, "detalle": ruta})
    antivirus = defender.get("antivirus") or []
    if antivirus and not any(a["activo"] for a in antivirus):
        hallazgos.append({"nivel": "alto", "clave": "seg_hallazgo_sin_antivirus", "motivos": ["seg_motivo_sin_antivirus"],
                          "ruta": None, "detalle": ", ".join(a["nombre"] for a in antivirus)})
    for a in antivirus:
        if a["activo"] and not a["al_dia"]:
            hallazgos.append({"nivel": "medio", "clave": "seg_hallazgo_antivirus_viejo",
                              "motivos": ["seg_motivo_firmas_viejas"], "ruta": None, "detalle": a["nombre"]})

    orden = {n: i for i, n in enumerate(NIVELES)}
    hallazgos.sort(key=lambda h: orden[h["nivel"]])
    return hallazgos


# ============================================================
#  Programas que escuchan en la red
# ============================================================

LOCALES = ("127.", "::1", "0:0:0:0:0:0:0:1")


def programas_en_red(procesos=None, conexiones=None):
    """Por programa: puertos abiertos a la red (escuchando en algo que no
    sea solo este equipo) y conexiones salientes establecidas. Lo que
    escucha hacia afuera es una puerta abierta: casi siempre legítima (un
    juego, Spotify, Windows), pero conviene saber cuáles hay."""
    procesos = procesos if procesos is not None else leer_procesos()
    conexiones = conexiones if conexiones is not None else leer_conexiones()
    info = {p["pid"]: p for p in procesos}
    resumen = {}
    for c in conexiones:
        pid = c.get("pid")
        if not pid:
            continue
        p = info.get(pid, {})
        clave = (p.get("exe") or p.get("nombre") or f"PID {pid}").lower()
        r = resumen.setdefault(clave, {"nombre": p.get("nombre") or f"PID {pid}", "exe": p.get("exe") or "",
                                       "escucha": set(), "conexiones": 0, "pids": set()})
        r["pids"].add(pid)
        local = c.get("local")
        if c.get("estado") == "LISTEN" and local and not str(local[0]).startswith(LOCALES):
            r["escucha"].add(local[1])
        elif c.get("estado") == "ESTABLISHED" and c.get("remoto") and not str(c["remoto"][0]).startswith(LOCALES):
            r["conexiones"] += 1
    salida = []
    for r in resumen.values():
        if not r["escucha"] and not r["conexiones"]:
            continue
        salida.append({"nombre": r["nombre"], "exe": r["exe"], "escucha": sorted(r["escucha"]),
                       "conexiones": r["conexiones"], "pids": sorted(r["pids"]),
                       "de_usuario": en_carpeta_de_usuario(r["exe"])})
    salida.sort(key=lambda r: (-len(r["escucha"]), -r["conexiones"]))
    return salida
