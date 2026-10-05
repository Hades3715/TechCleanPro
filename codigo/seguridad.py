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


# ============================================================
#  Extensiones del navegador (1.7.0)
# ============================================================
# Una extensión con permiso para "leer y cambiar todos tus datos en todas
# las webs" ve tus contraseñas al escribirlas, tu banco y tu correo. Es la
# forma más barata de robar cuentas que hay, y ningún antivirus la mira
# porque, técnicamente, es una función del navegador. SOLO SE LEE: no se
# desactiva ni se borra nada (eso se hace desde el propio navegador).

# (nombre, carpeta de datos) de los navegadores basados en Chromium.
NAVEGADORES_CHROMIUM = (
    ("Chrome", os.path.join("%LOCALAPPDATA%", "Google", "Chrome", "User Data")),
    ("Edge", os.path.join("%LOCALAPPDATA%", "Microsoft", "Edge", "User Data")),
    ("Brave", os.path.join("%LOCALAPPDATA%", "BraveSoftware", "Brave-Browser", "User Data")),
    ("Vivaldi", os.path.join("%LOCALAPPDATA%", "Vivaldi", "User Data")),
    ("Opera", os.path.join("%APPDATA%", "Opera Software", "Opera Stable")),
    ("Opera GX", os.path.join("%APPDATA%", "Opera Software", "Opera GX Stable")),
)

# Claves de registro de directivas (HKLM y HKCU) de cada navegador.
DIRECTIVAS_NAVEGADOR = {"Chrome": r"SOFTWARE\Policies\Google\Chrome",
                        "Edge": r"SOFTWARE\Policies\Microsoft\Edge",
                        "Brave": r"SOFTWARE\Policies\BraveSoftware\Brave"}

# Manifest::Location de Chromium -> de dónde salió la extensión.
#   1 tienda · 2/3/6 la instaló otro programa · 4/8 cargada desde una
#   carpeta (sin tienda) · 7/9 forzada por directiva · 5/10 parte del
#   propio navegador (no se listan).
ORIGEN_POR_UBICACION = {1: "tienda", 2: "externa", 3: "externa", 6: "externa",
                        4: "sin_tienda", 8: "sin_tienda", 7: "directiva", 9: "directiva"}
UBICACIONES_INTERNAS = {5, 10}

TODAS_LAS_WEBS = {"<all_urls>", "*://*/*", "http://*/*", "https://*/*", "*://*/", "http://*/", "https://*/"}
# Permisos que, juntos con "todas las webs", dan acceso a cuentas y datos.
PERMISOS_DATOS = {"cookies", "webRequest", "webRequestBlocking", "history", "clipboardRead"}


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _mensaje_extension(carpeta, texto, idioma):
    """Resuelve "__MSG_appName__" con los _locales de la extensión: el
    idioma de la app, si la extensión lo trae, y si no el suyo por defecto."""
    if not isinstance(texto, str) or not texto.startswith("__MSG_") or not texto.endswith("__"):
        return texto
    clave = texto[6:-2].lower()
    manifiesto = _leer_json(os.path.join(carpeta, "manifest.json")) or {}
    for loc in (idioma, idioma + "_419", manifiesto.get("default_locale"), "en", "en_US"):
        if not loc:
            continue
        mensajes = _leer_json(os.path.join(carpeta, "_locales", loc, "messages.json"))
        if isinstance(mensajes, dict):
            for k, v in mensajes.items():
                if k.lower() == clave and isinstance(v, dict) and v.get("message"):
                    return v["message"]
    return texto


def _carpeta_version(base_ext):
    """Carpeta de la versión instalada (Extensions/<id>/<versión>): la más
    reciente si hubiera varias a medio actualizar."""
    try:
        versiones = [d for d in os.listdir(base_ext) if os.path.isdir(os.path.join(base_ext, d))]
    except OSError:
        return None
    return os.path.join(base_ext, sorted(versiones)[-1]) if versiones else None


def _permisos_de(manifiesto):
    permisos = set()
    for clave in ("permissions", "host_permissions"):
        for p in manifiesto.get(clave) or []:
            if isinstance(p, str):
                permisos.add(p)
    # Un script de contenido en todas las webs lee las páginas igual que un permiso.
    for cs in manifiesto.get("content_scripts") or []:
        if isinstance(cs, dict):
            for m in cs.get("matches") or []:
                if isinstance(m, str) and m in TODAS_LAS_WEBS:
                    permisos.add(m)
    return permisos


def _leer_perfiles_chromium(navegador, carpeta, idioma):
    """Extensiones de todos los perfiles de un navegador Chromium."""
    estado_local = _leer_json(os.path.join(carpeta, "Local State")) or {}
    cache_perfiles = (estado_local.get("profile") or {}).get("info_cache") or {}
    nombres_perfil = {k: (v or {}).get("name") for k, v in cache_perfiles.items()}
    # Perfiles con cuenta de una escuela o empresa (Google Workspace,
    # Microsoft 365): su organización puede instalar extensiones a la
    # fuerza, y eso es legítimo. Sin distinguirlo, el auditor marcaba como
    # peligrosas las diez extensiones que pone la escuela.
    organizacion = {}
    for k, v in cache_perfiles.items():
        dominio = (v or {}).get("hosted_domain") or ""
        if (v or {}).get("is_managed") and dominio and dominio != "NO_HOSTED_DOMAIN":
            organizacion[k] = dominio
    # Opera guarda el perfil directamente en la carpeta, sin "Default".
    perfiles = [carpeta] if navegador.startswith("Opera") else []
    try:
        perfiles += [os.path.join(carpeta, d) for d in os.listdir(carpeta)
                     if d == "Default" or d.startswith("Profile ")]
    except OSError:
        return []
    salida = []
    for perfil in perfiles:
        ajustes = {}
        for archivo in ("Preferences", "Secure Preferences"):
            datos = _leer_json(os.path.join(perfil, archivo)) or {}
            for ext_id, v in ((datos.get("extensions") or {}).get("settings") or {}).items():
                if isinstance(v, dict):
                    ajustes.setdefault(ext_id, {}).update(v)
        base = os.path.join(perfil, "Extensions")
        try:
            instaladas = [d for d in os.listdir(base) if len(d) == 32 and d.isalpha()]
        except OSError:
            instaladas = []
        nombre_perfil = nombres_perfil.get(os.path.basename(perfil)) or os.path.basename(perfil)
        dominio = organizacion.get(os.path.basename(perfil))
        for ext_id in set(instaladas) | {k for k, v in ajustes.items() if v.get("location") in (4, 8)}:
            v = ajustes.get(ext_id, {})
            ubicacion = v.get("location")
            if ubicacion in UBICACIONES_INTERNAS:
                continue
            # Las cargadas desde una carpeta no viven en Extensions/: su
            # ruta es absoluta y apunta a donde estén.
            ruta = v.get("path") or ""
            if ruta and not os.path.isabs(ruta):
                ruta = os.path.join(base, ruta)
            if not ruta or not os.path.isdir(ruta):
                ruta = _carpeta_version(os.path.join(base, ext_id))
            manifiesto = (_leer_json(os.path.join(ruta, "manifest.json")) if ruta else None) \
                or v.get("manifest") or {}
            if not manifiesto:
                continue
            if manifiesto.get("theme") and not manifiesto.get("permissions"):
                continue                     # un tema de colores no hace nada
            desactivada = bool(v.get("disable_reasons")) or v.get("state") == 0
            origen = ORIGEN_POR_UBICACION.get(ubicacion, "tienda")
            if origen == "tienda" and v.get("from_webstore") is False:
                origen = "fuera_tienda"
            if origen == "directiva" and dominio:
                origen = "organizacion"
            salida.append({
                "navegador": navegador, "perfil": nombre_perfil, "id": ext_id,
                "nombre": _mensaje_extension(ruta or "", manifiesto.get("name") or ext_id, idioma) or ext_id,
                "version": manifiesto.get("version") or "?",
                "activa": not desactivada, "origen": origen,
                "permisos": sorted(_permisos_de(manifiesto)), "ruta": ruta or "",
                "organizacion": dominio if origen == "organizacion" else None,
            })
    return salida


def _leer_firefox():
    """Extensiones de Firefox, de extensions.json de cada perfil."""
    raiz = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")
    salida = []
    try:
        perfiles = [os.path.join(raiz, d) for d in os.listdir(raiz)]
    except OSError:
        return []
    for perfil in perfiles:
        datos = _leer_json(os.path.join(perfil, "extensions.json")) or {}
        for a in datos.get("addons") or []:
            if not isinstance(a, dict) or a.get("type") != "extension":
                continue
            if a.get("location") in ("app-builtin", "app-system-defaults", "app-system-addons"):
                continue
            permisos = (a.get("userPermissions") or {})
            local = a.get("defaultLocale") or {}
            origen = "tienda"
            if a.get("foreignInstall"):
                origen = "externa"
            if a.get("signedState") is not None and a.get("signedState") <= 0:
                origen = "sin_tienda"
            salida.append({
                "navegador": "Firefox", "perfil": os.path.basename(perfil), "id": a.get("id") or "?",
                "nombre": local.get("name") or a.get("id") or "?", "version": a.get("version") or "?",
                "activa": bool(a.get("active")), "origen": origen,
                "permisos": sorted(set(permisos.get("permissions") or []) | set(permisos.get("origins") or [])),
                "ruta": a.get("path") or "", "organizacion": None,
            })
    return salida


def leer_directivas_extensiones():
    """{navegador: [(id, url)]} de las extensiones FORZADAS por directiva
    (ExtensionInstallForcelist), en HKLM y HKCU. Así se instala a la fuerza
    una extensión que el usuario no puede quitar desde el navegador."""
    if not IS_WINDOWS:
        return {}
    import winreg
    salida = {}
    for navegador, clave in DIRECTIVAS_NAVEGADOR.items():
        for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(raiz, clave + r"\ExtensionInstallForcelist") as k:
                    i = 0
                    while True:
                        try:
                            _, valor, _ = winreg.EnumValue(k, i)
                        except OSError:
                            break
                        i += 1
                        partes = str(valor).split(";", 1)
                        salida.setdefault(navegador, []).append(
                            (partes[0].strip(), partes[1].strip() if len(partes) > 1 else ""))
            except OSError:
                continue
    return salida


def evaluar_extension(ext):
    """(nivel, [claves de motivo]) de una extensión. Pura: se prueba con
    datos de mentira. Los niveles son los del resto del auditor."""
    motivos = []
    nivel = "info"
    permisos = set(ext.get("permisos") or [])
    todas = bool(permisos & TODAS_LAS_WEBS)
    origen = ext.get("origen")
    if origen == "sin_tienda":
        motivos.append("ext_mot_sin_tienda")
        nivel = "alto"
    elif origen == "directiva":
        motivos.append("ext_mot_directiva")
        nivel = "alto"
    elif origen == "fuera_tienda":
        motivos.append("ext_mot_fuera_tienda")
        nivel = "medio"
    elif origen == "externa":
        motivos.append("ext_mot_externa")
    elif origen == "organizacion":
        motivos.append("ext_mot_organizacion")
    if "debugger" in permisos:
        # Con "debugger" puede controlar pestañas enteras; si además llega a
        # todas las webs, es de lo más peligroso que una extensión puede pedir.
        motivos.append("ext_mot_debugger")
        nivel = "alto" if todas or nivel == "alto" else "medio"
    if "proxy" in permisos:
        motivos.append("ext_mot_proxy")
        if nivel == "info":
            nivel = "medio"
    if todas:
        if permisos & PERMISOS_DATOS:
            motivos.append("ext_mot_todo_y_datos")
            if nivel == "info":
                nivel = "medio"
        else:
            motivos.append("ext_mot_todas_webs")
    if "nativeMessaging" in permisos:
        motivos.append("ext_mot_nativo")
    # Lo que pone la escuela o la empresa ya lo revisó alguien: se informa
    # de los permisos, pero no se pinta como amenaza.
    if origen == "organizacion" and nivel != "alto":
        nivel = "info"
    return nivel, motivos


def auditar_extensiones(idioma="es"):
    """Todas las extensiones de todos los navegadores, agrupadas: la misma
    extensión en varios perfiles del mismo navegador sale UNA vez, con la
    lista de perfiles. Ordenadas de más a menos preocupante."""
    crudas = []
    for navegador, carpeta in NAVEGADORES_CHROMIUM:
        carpeta = os.path.expandvars(carpeta)
        if os.path.isdir(carpeta):
            crudas += _leer_perfiles_chromium(navegador, carpeta, idioma)
    crudas += _leer_firefox()
    forzadas = leer_directivas_extensiones()

    grupos = {}
    for e in crudas:
        g = grupos.setdefault((e["navegador"], e["id"]), dict(e, perfiles=[]))
        g["perfiles"].append(e["perfil"])
        g["activa"] = g["activa"] or e["activa"]
        g["permisos"] = sorted(set(g["permisos"]) | set(e["permisos"]))
        # Si en algún perfil llegó por una vía peor, manda esa.
        peor = ("sin_tienda", "directiva", "fuera_tienda", "externa", "organizacion", "tienda")
        if peor.index(e["origen"]) < peor.index(g["origen"]):
            g["origen"] = e["origen"]
        g["organizacion"] = g.get("organizacion") or e.get("organizacion")
    # Forzadas por directiva que el auditor no vio en ninguna carpeta:
    # también cuentan (puede que el navegador aún no las haya descargado).
    for navegador, lista in forzadas.items():
        for ext_id, url in lista:
            g = grupos.get((navegador, ext_id))
            if g is None:
                grupos[(navegador, ext_id)] = {
                    "navegador": navegador, "perfil": "", "perfiles": [], "id": ext_id, "nombre": ext_id,
                    "version": "?", "activa": True, "origen": "directiva", "permisos": [],
                    "ruta": url, "organizacion": None}
            else:
                g["origen"] = "directiva"
    salida = []
    for g in grupos.values():
        g["nivel"], g["motivos"] = evaluar_extension(g)
        salida.append(g)
    orden = {n: i for i, n in enumerate(NIVELES)}
    salida.sort(key=lambda e: (orden.get(e["nivel"], 9), not e["activa"], e["navegador"], e["nombre"].lower()))
    return salida
