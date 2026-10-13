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

# PowerShell escribe por una tubería en la página de códigos OEM (cp850 en un
# Windows en español) y Python lee con la ANSI (cp1252): "Optimización" salía
# "Optimizaci¢n" en Servicios, Drivers, Tareas... (BUG corregido en la 1.8.0).
# Las llamadas que leen texto le piden UTF-8 a PowerShell con esto delante del
# script, y lo leen con encoding="utf-8".
PS_UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"

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
    # 1.8.0: también AppData sacada del perfil y no solo de las variables:
    # cualquier programa (o el propio banco de pruebas) puede cambiar
    # %APPDATA%, y entonces lo que hay en AppData\Roaming dejaba de contar
    # como carpeta de usuario y el malware del equipo del desarrollador
    # pasaba sin marcar.
    rutas = [os.environ.get("TEMP"), os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"),
             os.path.join(perfil, "AppData", "Roaming"), os.path.join(perfil, "AppData", "Local"),
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
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_UTF8 + script],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
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
#  Lo que arranca con Windows (1.8.0)
# ============================================================

def _ruta_real(ruta):
    """Sin el prefijo \\\\?\\ que ponen algunas tareas (McAfee)."""
    ruta = (ruta or "").strip().strip('"')
    return ruta[4:] if ruta.startswith("\\\\?\\") else ruta


def nombre_firmante(firma):
    """De "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond..."
    saca "Microsoft Corporation". Vacío si no está firmado de verdad."""
    if not firma or firma.get("estado") != "Valid":
        return ""
    m = re.search(r"CN=(\"[^\"]+\"|[^,]+)", firma.get("firmante") or "")
    return m.group(1).strip().strip('"') if m else ""


def evaluar_inicio(entradas, firmas=None, accesos=None, carpetas=None):
    """Para Aplicaciones → Inicio de Windows: a cada entrada (de
    optimizer.listar_inicio_completo y listar_tareas_inicio) le añade si su
    programa existe, quién lo firma, y si parece sospechosa, con las MISMAS
    reglas que la auditoría (un intérprete renombrado en una carpeta de
    usuario, comandos ocultos...). Solo lee. Las pruebas pasan sus propias
    `firmas` y `accesos`."""
    carpetas = carpetas or carpetas_de_usuario()
    if accesos is None:
        accesos = leer_accesos_inicio()
    destinos = {os.path.normcase(a.get("lnk") or ""): a for a in accesos if isinstance(a, dict)}
    for e in entradas:
        if e.get("tipo") == "carpeta":
            acceso = destinos.get(os.path.normcase(e.get("exe") or ""))
            if acceso:
                e["destino"] = acceso.get("destino") or ""
                e["args"] = acceso.get("args") or ""
    rutas = [_ruta_real(e.get("destino") or e.get("exe")) for e in entradas]
    if firmas is None:
        firmas = leer_firmas(rutas)
    for e, ruta in zip(entradas, rutas):
        firma = firmas.get(os.path.normcase(ruta))
        e["programa"] = ruta
        e["existe"] = bool(ruta) and os.path.exists(ruta)
        e["firmante"] = nombre_firmante(firma)
        e["producto"] = (firma or {}).get("producto") or ""
        nivel, motivos, original = _evaluar_ejecutable(ruta, firma, carpetas) if e["existe"] else (None, [], None)
        comando = ((e.get("comando") or "") + " " + (e.get("args") or "")).lower()
        if any(x in comando for x in COMANDOS_OCULTOS):
            nivel = "alto"
            motivos = motivos + ["seg_motivo_comando_oculto"]
        e["riesgo"], e["motivos"], e["original"] = nivel, motivos, original
    return entradas


# ============================================================
#  Estado de la protección (1.8.0)
# ============================================================
# Lo que dice "Seguridad de Windows", pero junto y explicado: qué antivirus
# está al mando, si el cortafuegos está encendido, el arranque seguro, el
# control de cuentas y el aislamiento del núcleo. Todo del registro y del
# Centro de seguridad; no necesita administrador.

def _valor_registro(raiz, ruta, nombre):
    if not IS_WINDOWS:
        return None
    import winreg
    raiz = winreg.HKEY_LOCAL_MACHINE if raiz == "HKLM" else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(raiz, ruta) as clave:
            return winreg.QueryValueEx(clave, nombre)[0]
    except OSError:
        return None


def _producto_activo(estado):
    """productState del Centro de seguridad: el segundo byte dice si está
    activo (0x10/0x11), el tercero si está al día (0x00). No es API pública
    documentada, pero es lo que leen todas las herramientas."""
    try:
        estado = int(estado or 0)
    except (TypeError, ValueError):
        estado = 0
    return ((estado >> 8) & 0xFF) in (0x10, 0x11), (estado & 0xFF) == 0x00


def leer_proteccion():
    productos = _ps_json(
        "@('AntiVirusProduct','FirewallProduct') | ForEach-Object { $c = $_; "
        "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName $c -ErrorAction SilentlyContinue | "
        "ForEach-Object { [pscustomobject]@{ clase = $c; nombre = $_.displayName; estado = $_.productState } } } "
        "| ConvertTo-Json -Compress", timeout=40)
    antivirus, cortafuegos_terceros = [], []
    for p in productos:
        if not isinstance(p, dict):
            continue
        activo, al_dia = _producto_activo(p.get("estado"))
        dato = {"nombre": p.get("nombre") or "?", "activo": activo, "al_dia": al_dia}
        if p.get("clase") == "FirewallProduct":
            cortafuegos_terceros.append(dato)
        else:
            antivirus.append(dato)
    politica = r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy"
    perfiles = {}
    for perfil, clave in (("dominio", "DomainProfile"), ("privada", "StandardProfile"), ("publica", "PublicProfile")):
        valor = _valor_registro("HKLM", politica + "\\" + clave, "EnableFirewall")
        perfiles[perfil] = None if valor is None else bool(valor)
    sistema = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    return {
        "antivirus": antivirus,
        "cortafuegos_terceros": cortafuegos_terceros,
        "cortafuegos": perfiles,
        "arranque_seguro": _valor_registro("HKLM", r"SYSTEM\CurrentControlSet\Control\SecureBoot\State",
                                           "UEFISecureBootEnabled"),
        "uac": _valor_registro("HKLM", sistema, "EnableLUA"),
        "uac_avisos": _valor_registro("HKLM", sistema, "ConsentPromptBehaviorAdmin"),
        "aislamiento": _valor_registro(
            "HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
            "Enabled"),
    }


def evaluar_proteccion(p):
    """[(clave, nivel, clave_texto, campos)] para pintar. nivel: bien /
    atencion / critico / info. Pura."""
    filas = []
    activos = [a for a in p.get("antivirus") or [] if a["activo"]]
    if activos:
        a = activos[0]
        filas.append(("antivirus", "bien" if a["al_dia"] else "atencion",
                      "prot_av_activo" if a["al_dia"] else "prot_av_viejo", {"nombre": a["nombre"]}))
    elif p.get("antivirus"):
        filas.append(("antivirus", "critico", "prot_av_ninguno", {}))
    else:
        filas.append(("antivirus", "info", "prot_av_desconocido", {}))
    perfiles = p.get("cortafuegos") or {}
    apagados = [k for k, v in perfiles.items() if v is False]
    terceros = [c for c in p.get("cortafuegos_terceros") or [] if c["activo"]]
    if terceros:
        filas.append(("cortafuegos", "bien", "prot_fw_terceros", {"nombre": terceros[0]["nombre"]}))
    elif apagados:
        filas.append(("cortafuegos", "critico" if "publica" in apagados else "atencion", "prot_fw_apagado",
                      {"perfiles": ", ".join(apagados)}))
    elif perfiles and all(v for v in perfiles.values() if v is not None):
        filas.append(("cortafuegos", "bien", "prot_fw_activo", {}))
    else:
        filas.append(("cortafuegos", "info", "prot_desconocido", {}))
    arranque = p.get("arranque_seguro")
    filas.append(("arranque", "info" if arranque is None else ("bien" if arranque else "atencion"),
                  "prot_desconocido" if arranque is None else ("prot_sb_si" if arranque else "prot_sb_no"), {}))
    uac, avisos = p.get("uac"), p.get("uac_avisos")
    if uac == 0:
        filas.append(("uac", "critico", "prot_uac_apagado", {}))
    elif avisos == 0:
        filas.append(("uac", "atencion", "prot_uac_sin_avisos", {}))
    elif uac is None:
        filas.append(("uac", "info", "prot_desconocido", {}))
    else:
        filas.append(("uac", "bien", "prot_uac_si", {}))
    aislamiento = p.get("aislamiento")
    filas.append(("aislamiento", "bien" if aislamiento else "info",
                  "prot_hvci_si" if aislamiento else "prot_hvci_no", {}))
    return filas


# ============================================================
#  Secuestros: hosts, proxy, DNS, certificados y navegador (1.8.0)
# ============================================================
# Lo que cambia el adware (y algún malware) para espiar o redirigir lo que
# navegas, sin tocar ningún archivo de programa: por eso ningún antivirus
# clásico lo mira. Todo se lee; nada se cambia.

LOCALES_HOSTS = {"127.0.0.1", "0.0.0.0", "::1", "::"}
DNS_CONOCIDOS = {
    "8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112", "208.67.222.222",
    "208.67.220.220", "94.140.14.14", "94.140.15.15", "1.1.1.2", "1.0.0.2", "1.1.1.3", "1.0.0.3",
    "2001:4860:4860::8888", "2001:4860:4860::8844", "2606:4700:4700::1111", "2606:4700:4700::1001",
    "2620:fe::fe", "2620:fe::9",
}
# Raíces que se ponen en medio de tus conexiones HTTPS. Las de un antivirus
# o una herramienta de programador tienen sentido si los instalaste tú; las
# de adware (Superfish, eDellRoot...) no lo tienen nunca.
INTERCEPTORES = (
    ("superfish", "adware"), ("edellroot", "adware"), ("privdog", "adware"), ("komodia", "adware"),
    ("wajam", "adware"), ("netfilter", "adware"), ("fiddler", "depuracion"), ("mitmproxy", "depuracion"),
    ("charles proxy", "depuracion"), ("portswigger", "depuracion"), ("burp", "depuracion"),
    ("avast", "antivirus"), ("avg ", "antivirus"), ("kaspersky", "antivirus"), ("eset ssl", "antivirus"),
    ("bitdefender", "antivirus"), ("mcafee web", "antivirus"), ("sophos ssl", "antivirus"),
)
POLITICAS_NAVEGADOR = ("HomepageLocation", "NewTabPageLocation", "DefaultSearchProviderSearchURL",
                       "DefaultSearchProviderName", "ProxyServer", "ProxyPacUrl")


def leer_hosts(ruta=None):
    """{"bloqueos", "locales", "redirecciones"}: lo que el archivo hosts manda
    a "ningún sitio" (0.0.0.0, 127.0.0.1...: así bloquean anuncios los
    bloqueadores, y hasta algún antivirus), lo que manda a una dirección de
    tu red o de tu VPN (Tailscale escribe ahí los nombres de tus equipos) y
    lo que manda a una dirección PÚBLICA de internet: así se suplanta una
    web. None si no se pudo leer.

    Probado en el equipo del desarrollador: con la primera regla ("todo lo
    que no va a 127.0.0.1 es una redirección") salía en rojo un bloqueo de
    McAfee (0.0.0.1) y los nombres de Tailscale (100.92.x.x)."""
    ruta = ruta or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            lineas = f.readlines()
    except OSError:
        return None
    hosts = {"bloqueos": [], "locales": [], "redirecciones": []}
    for linea in lineas:
        partes = linea.split("#", 1)[0].split()
        if len(partes) < 2:
            continue
        ip, nombres = partes[0], [n.lower() for n in partes[1:] if n.lower() != "localhost"]
        if not nombres:
            continue
        if ip in LOCALES_HOSTS or ip.startswith("0.") or ip.startswith("127."):
            destino = "bloqueos"
        elif _red_privada(ip):
            destino = "locales"
        else:
            destino = "redirecciones"
        hosts[destino].extend((n, ip) for n in nombres)
    return hosts


def _red_privada(ip):
    """Una dirección de tu red, de una VPN o de "ningún sitio": la de casa
    (192.168...), la de Tailscale y otras VPN (100.64.0.0/10), loopback..."""
    import ipaddress
    try:
        d = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return (d.is_private or d.is_loopback or d.is_link_local or d.is_unspecified
            or (d.version == 4 and d in ipaddress.ip_network("100.64.0.0/10")))


def leer_dns():
    """Los servidores DNS puestos A MANO en cada adaptador (los que da el
    router por DHCP no cuentan: los cambia la red, no un programa)."""
    if not IS_WINDOWS:
        return []
    import winreg
    base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    puestos = set()
    for ruta in (base, base.replace("Tcpip", "Tcpip6")):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta) as interfaces:
                i = 0
                while True:
                    try:
                        guid = winreg.EnumKey(interfaces, i)
                    except OSError:
                        break
                    i += 1
                    valor = _valor_registro("HKLM", ruta + "\\" + guid, "NameServer")
                    for servidor in re.split(r"[,\s]+", str(valor or "")):
                        if servidor:
                            puestos.add(servidor)
        except OSError:
            continue
    return sorted(puestos)


def leer_certificados_raiz():
    """Las raíces de confianza (tuyas y del equipo) cuyo nombre es el de un
    programa que intercepta HTTPS."""
    certificados = _ps_json(
        "@('Cert:\\CurrentUser\\Root','Cert:\\LocalMachine\\Root') | ForEach-Object { $a = $_; "
        "Get-ChildItem $a -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ "
        "almacen = $a; nombre = [string]$_.Subject; huella = $_.Thumbprint } } } | ConvertTo-Json -Compress",
        timeout=40)
    encontrados = []
    for c in certificados:
        nombre = (c.get("nombre") or "") if isinstance(c, dict) else ""
        for marca, tipo in INTERCEPTORES:
            if marca in nombre.lower():
                encontrados.append({"nombre": nombre, "tipo": tipo, "almacen": c.get("almacen") or ""})
                break
    return encontrados


def leer_politicas_navegador():
    """Página de inicio, buscador o proxy IMPUESTOS por directiva a Chrome o
    Edge (no se pueden cambiar desde el navegador). Normal en un equipo de
    escuela o empresa; en uno personal, es la firma de un secuestrador."""
    encontradas = []
    for raiz in ("HKLM", "HKCU"):
        for navegador, ruta in (("Chrome", r"SOFTWARE\Policies\Google\Chrome"),
                                ("Edge", r"SOFTWARE\Policies\Microsoft\Edge")):
            for valor in POLITICAS_NAVEGADOR:
                dato = _valor_registro(raiz, ruta, valor)
                if dato not in (None, ""):
                    encontradas.append({"navegador": navegador, "politica": valor, "valor": str(dato)})
    return encontradas


def chequeo_secuestros():
    hosts = leer_hosts() or {}
    ajustes = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    return {
        "hosts_leido": bool(hosts), "hosts_bloqueos": hosts.get("bloqueos", []),
        "hosts_locales": hosts.get("locales", []), "hosts_redirecciones": hosts.get("redirecciones", []),
        "proxy_activo": bool(_valor_registro("HKCU", ajustes, "ProxyEnable")),
        "proxy": _valor_registro("HKCU", ajustes, "ProxyServer") or "",
        "proxy_pac": _valor_registro("HKCU", ajustes, "AutoConfigURL") or "",
        "dns": leer_dns(),
        "certificados": leer_certificados_raiz(),
        "politicas": leer_politicas_navegador(),
    }


def evaluar_secuestros(d):
    """[(clave, nivel, clave_texto, campos)] como evaluar_proteccion. Pura."""
    filas = []
    if d.get("hosts_redirecciones"):
        n, ip = d["hosts_redirecciones"][0]
        filas.append(("hosts", "critico", "sec_hosts_redirige",
                      {"n": len(d["hosts_redirecciones"]), "nombre": n, "ip": ip}))
    elif not d.get("hosts_leido", True):
        filas.append(("hosts", "info", "prot_desconocido", {}))
    elif d.get("hosts_bloqueos") or d.get("hosts_locales"):
        filas.append(("hosts", "bien", "sec_hosts_bloquea",
                      {"n": len(d.get("hosts_bloqueos") or []), "locales": len(d.get("hosts_locales") or [])}))
    else:
        filas.append(("hosts", "bien", "sec_hosts_limpio", {}))
    if d.get("proxy_pac"):
        filas.append(("proxy", "atencion", "sec_proxy_pac", {"url": d["proxy_pac"]}))
    elif d.get("proxy_activo") and d.get("proxy"):
        local = d["proxy"].split(":", 1)[0].lower() in ("127.0.0.1", "localhost")
        filas.append(("proxy", "atencion" if not local else "info",
                      "sec_proxy_local" if local else "sec_proxy", {"proxy": d["proxy"]}))
    else:
        filas.append(("proxy", "bien", "sec_proxy_no", {}))
    raros = [s for s in d.get("dns") or [] if s not in DNS_CONOCIDOS and not _red_privada(s)]
    if raros:
        filas.append(("dns", "atencion", "sec_dns_raro", {"dns": ", ".join(raros[:3])}))
    elif d.get("dns"):
        filas.append(("dns", "bien", "sec_dns_conocido", {"dns": ", ".join(d["dns"][:3])}))
    else:
        filas.append(("dns", "bien", "sec_dns_router", {}))
    certificados = d.get("certificados") or []
    peor = next((c for c in certificados if c["tipo"] == "adware"), None) or (
        next((c for c in certificados if c["tipo"] == "depuracion"), None)) or (certificados[0] if certificados else None)
    if peor:
        nivel = {"adware": "critico", "depuracion": "atencion"}.get(peor["tipo"], "info")
        nombre = re.search(r"CN=([^,]+)", peor["nombre"])
        texto = {"adware": "sec_cert_adware", "depuracion": "sec_cert_depuracion",
                 "antivirus": "sec_cert_antivirus"}[peor["tipo"]]
        filas.append(("certificados", nivel, texto,
                      {"nombre": nombre.group(1) if nombre else peor["nombre"]}))
    else:
        filas.append(("certificados", "bien", "sec_cert_limpio", {}))
    politicas = d.get("politicas") or []
    if politicas:
        p = politicas[0]
        filas.append(("navegador", "atencion", "sec_politica", {"navegador": p["navegador"], "valor": p["valor"][:80]}))
    else:
        filas.append(("navegador", "bien", "sec_politica_no", {}))
    return filas


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
