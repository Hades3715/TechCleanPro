"""
optimizer.py
Acciones reales de optimización: liberar working sets de RAM, limpiar
temporales, vaciar papelera, limpiar caché DNS, gestionar inicio automático
con Windows y reiniciar directo a BIOS/UEFI. Cada acción devuelve también
el "comando equivalente" para mostrarlo en el panel de desarrollador.
"""

import os
import sys
import re
import json
import time
import shutil
import tempfile
import platform
import subprocess
import ctypes
import psutil
import webbrowser

from idiomas import t
if platform.system() == "Windows":
    import ctypes.wintypes

IS_WINDOWS = platform.system() == "Windows"

APP_STARTUP_NAME = "TechClean"


def _cim(clase, propiedades, namespace="root/cimv2", timeout=8):
    """
    Consulta WMI a través de PowerShell (Get-CimInstance) — el reemplazo
    oficial de wmic. Devuelve una lista de diccionarios (uno por objeto
    encontrado), o lista vacía si algo falla — nunca lanza una excepción
    hacia afuera.

    BUG corregido: esta función se usaba en obtener_fabricante_soporte()
    sin estar definida en este archivo (existe una función con el mismo
    nombre en system_monitor.py, pero optimizer.py nunca la importaba) —
    tronaba con NameError cada vez que se abría la pantalla de Drivers.
    Se agrega aquí una copia propia, en vez de importar la de
    system_monitor.py, para no acoplar los dos archivos a través de una
    función "privada" (con guion bajo) de otro módulo.
    """
    if not IS_WINDOWS:
        return []
    props = ",".join(propiedades)
    ps_cmd = (
        f"Get-CimInstance -Namespace {namespace} -ClassName {clase} "
        f"-ErrorAction SilentlyContinue | Select-Object {props} | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout)
        salida = (r.stdout or "").strip()
    except Exception:
        return []
    if not salida:
        return []
    try:
        datos = json.loads(salida)
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    return datos if isinstance(datos, list) else []


def is_admin():
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Vuelve a lanzar el script actual solicitando elevación (UAC)."""
    if not IS_WINDOWS:
        return False
    try:
        # BUG corregido: antes se incluía sys.argv[0] (la ruta del propio
        # ejecutable/script) dentro de los parámetros, lo cual lo pasaba
        # como si fuera un argumento — ShellExecuteW ya recibe el ejecutable
        # por separado. Ahora solo se reenvían los argumentos reales.
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return True
    except Exception:
        return False


def trim_process_memory(exclude_pids=None):
    """
    Fuerza a los procesos accesibles a liberar memoria no usada al SO
    (EmptyWorkingSet de la API de Windows). Es una acción real y segura:
    no cierra procesos, solo compacta su huella de RAM.

    exclude_pids: PIDs a NO tocar (ej. un juego activo en primer plano,
    para no causarle un microcorte de rendimiento mientras se juega).

    Devuelve (bytes_liberados_estimados, procesos_afectados, comando_equivalente)
    """
    comando = "EmptyWorkingSet() vía psapi.dll (API nativa de Windows) sobre cada proceso accesible"
    if not IS_WINDOWS:
        return 0, 0, comando

    exclude_pids = exclude_pids or set()
    import psutil
    antes = psutil.virtual_memory().used
    afectados = 0
    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        if pid in exclude_pids:
            continue
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
        if handle:
            try:
                if psapi.EmptyWorkingSet(handle):
                    afectados += 1
            except Exception:
                pass
            finally:
                kernel32.CloseHandle(handle)

    despues = psutil.virtual_memory().used
    liberado = max(0, antes - despues)
    return liberado, afectados, comando


def _carpetas_intocables():
    """Carpetas de %TEMP% que NUNCA hay que borrar.

    BUG REAL, encontrado con la app ya publicada: en la build --onefile,
    PyInstaller descomprime la aplicacion ENTERA (el interprete, las DLL,
    los .pyd y los assets) en una carpeta temporal llamada _MEIxxxxx. Como
    esa carpeta vive dentro de %TEMP%, "Limpiar archivos temporales" la
    borraba: la app se destruia a si misma mientras corria.

    No se notaba enseguida, y eso lo hacia peor. Lo que ya estaba cargado en
    memoria seguia funcionando; lo que se importa tarde, no. La prueba de
    velocidad de internet reventaba con "ModuleNotFoundError: No module
    named '_ssl'" porque importa ssl recien cuando la usas, y para entonces
    el archivo ya no existia.

    Se protege la carpeta de ESTA instancia (sys._MEIPASS) y ademas
    cualquier _MEI* que haya: puede ser de otra app congelada con
    PyInstaller que este corriendo ahora mismo, y romperla seria igual de
    grave que rompernos a nosotros.
    """
    intocables = set()
    propia = getattr(sys, "_MEIPASS", None)
    if propia:
        intocables.add(os.path.normcase(os.path.abspath(propia)))
    for base in (tempfile.gettempdir(),):
        try:
            for nombre in os.listdir(base):
                if nombre.upper().startswith("_MEI"):
                    intocables.add(os.path.normcase(os.path.abspath(os.path.join(base, nombre))))
        except OSError:
            pass
    return intocables


def _es_intocable(ruta, intocables):
    """True si la ruta esta dentro de alguna carpeta protegida."""
    if not intocables:
        return False
    normal = os.path.normcase(os.path.abspath(ruta))
    return any(normal == p or normal.startswith(p + os.sep) for p in intocables)


def _dir_size(path, intocables=None):
    """Tamano de una carpeta. Si se pasan carpetas intocables, no las cuenta:
    asi lo que se ESTIMA como recuperable coincide con lo que la limpieza va
    a borrar de verdad, en vez de prometer 22 MB de mas (los de la propia app
    descomprimida en %TEMP%)."""
    total = 0
    for root, _, files in os.walk(path, topdown=True, onerror=lambda e: None):
        if intocables and _es_intocable(root, intocables):
            continue
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return total


def estimate_reclaimable_space():
    """Calcula cuánto espacio se podría recuperar SIN borrar nada todavía."""
    candidatos = []
    temp_dir = tempfile.gettempdir()
    candidatos.append((t("optmod_temp_usuario"), temp_dir))

    if IS_WINDOWS:
        win_temp = r"C:\Windows\Temp"
        if os.path.isdir(win_temp):
            candidatos.append(("Temporales de Windows", win_temp))

    intocables = _carpetas_intocables()
    resultados = []
    total = 0
    for nombre, ruta in candidatos:
        size = _dir_size(ruta, intocables) if os.path.isdir(ruta) else 0
        total += size
        resultados.append({"categoria": nombre, "ruta": ruta, "bytes": size})

    return resultados, total


def clear_temp_files():
    """
    Borra archivos temporales del usuario y del sistema (los que no estén
    en uso). Devuelve (bytes_liberados, archivos_borrados, comando_equivalente).
    """
    comando = 'del /s /q "%TEMP%\\*" y limpieza equivalente de C:\\Windows\\Temp'
    rutas = [tempfile.gettempdir()]
    if IS_WINDOWS and os.path.isdir(r"C:\Windows\Temp"):
        rutas.append(r"C:\Windows\Temp")

    intocables = _carpetas_intocables()
    liberado = 0
    borrados = 0
    for ruta in rutas:
        for root, dirs, files in os.walk(ruta, topdown=False):
            if _es_intocable(root, intocables):
                continue
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    liberado += size
                    borrados += 1
                except (OSError, PermissionError):
                    continue
            for d in dirs:
                dp = os.path.join(root, d)
                if _es_intocable(dp, intocables):
                    continue
                try:
                    os.rmdir(dp)
                except OSError:
                    continue
    return liberado, borrados, comando


class _SHQUERYRBINFO(ctypes.Structure):
    """Estructura que Windows rellena con el estado de la papelera."""
    _fields_ = [("cbSize", ctypes.c_uint32),
                ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64)]


def consultar_papelera():
    """Cuánto ocupa la papelera y cuántos elementos tiene, sin tocar nada.

    Devuelve (bytes, elementos). Se consulta ANTES de vaciar para poder
    decirle al usuario cuánto se liberó — el resto de la app siempre da un
    número concreto ("se liberaron 340 MB") y vaciar la papelera era la
    única acción que se limitaba a decir "listo"."""
    if not IS_WINDOWS:
        return 0, 0
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    try:
        shell32 = ctypes.windll.shell32
        shell32.SHQueryRecycleBinW.restype = ctypes.c_long
        # None como ruta = todas las unidades del equipo.
        if shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
            return 0, 0
        return int(info.i64Size), int(info.i64NumItems)
    except Exception:
        return 0, 0


def empty_recycle_bin():
    """Vacía la papelera de reciclaje.

    Devuelve (exito, comando, bytes_liberados, elementos).

    OJO al llamarla: SHEmptyRecycleBinW es SÍNCRONA — borra los archivos de
    verdad antes de volver. Con una papelera de varios GB tarda segundos, y
    con SHERB_NOPROGRESSUI ni siquiera sale la ventanita de progreso de
    Windows. Tiene que ejecutarse en un hilo aparte, nunca en el hilo de la
    interfaz, o la ventana se queda congelada y Windows la marca como "No
    responde".

    BUG corregido: no se miraba el valor que devuelve la llamada, así que
    la función contestaba "listo" pasara lo que pasara — incluso si Windows
    se negaba a borrar. El usuario veía "Papelera vaciada ✅" con la
    papelera intacta.
    """
    comando = "SHEmptyRecycleBinW() vía shell32.dll"
    if not IS_WINDOWS:
        return False, comando, 0, 0
    bytes_antes, elementos_antes = consultar_papelera()
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        shell32 = ctypes.windll.shell32
        shell32.SHEmptyRecycleBinW.restype = ctypes.c_long
        hr = shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        )
        # S_OK (0) es éxito. Con la papelera YA vacía, varias versiones de
        # Windows devuelven E_UNEXPECTED (0x8000FFFF) en vez de S_OK — no es
        # un fallo, simplemente no había nada que borrar.
        if hr == 0 or (hr & 0xFFFFFFFF) == 0x8000FFFF:
            return True, comando, bytes_antes, elementos_antes
        return False, comando, 0, 0
    except Exception:
        return False, comando, 0, 0


def flush_dns():
    comando = "ipconfig /flushdns"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW)
        return True, comando
    except Exception:
        return False, comando


def restart_to_uefi():
    """
    Reinicia el equipo directamente en el menú de configuración de UEFI/BIOS.
    Esto SIEMPRE implica un reinicio real: es una limitación de hardware,
    ninguna aplicación puede evitarlo.
    """
    comando = "shutdown /r /fw /t 5"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["shutdown", "/r", "/fw", "/t", "5"], check=True)
        return True, comando
    except Exception:
        return False, comando


def apagar_equipo(segundos_espera=5):
    """Apaga el equipo por completo, con unos segundos de margen para cancelar."""
    comando = f"shutdown /s /t {segundos_espera}"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["shutdown", "/s", "/t", str(segundos_espera)], check=True)
        return True, comando
    except Exception:
        return False, comando


def reiniciar_equipo(segundos_espera=5):
    """Reinicio normal (no entra a BIOS), con unos segundos de margen para cancelar."""
    comando = f"shutdown /r /t {segundos_espera}"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["shutdown", "/r", "/t", str(segundos_espera)], check=True)
        return True, comando
    except Exception:
        return False, comando


def cancelar_apagado_programado():
    """Cancela un apagado/reinicio ya en marcha (dentro de la ventana de
    espera de unos segundos) — por si te arrepientes justo a tiempo."""
    comando = "shutdown /a"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["shutdown", "/a"], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


def suspender_equipo():
    """
    Suspende el equipo (modo de bajo consumo, RAM sigue encendida — se
    reanuda casi al instante). No usa shutdown.exe: Windows suspende vía
    una llamada directa de la API del sistema.
    """
    comando = "SetSuspendState (API de Windows)"
    if not IS_WINDOWS:
        return False, comando
    try:
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        return True, comando
    except Exception:
        return False, comando


def hibernar_equipo():
    """
    Hiberna el equipo (guarda todo en disco y apaga por completo — arranca
    más lento que suspender, pero consume cero energía mientras está
    hibernado). Requiere que la hibernación esté habilitada en Windows
    (lo está por defecto en la mayoría de laptops).
    """
    comando = "shutdown /h"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["shutdown", "/h"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Inicio automático con Windows ----------------
# BUG corregido: la versión anterior usaba la clave de registro Run
# (HKCU\...\Run) — el mecanismo normal que usan la mayoría de apps. El
# problema es que esta app se compila pidiendo permisos de administrador
# (--uac-admin), y una app así NO puede iniciarse de forma confiable
# desde esa clave: Windows necesita mostrar un permiso de UAC en cada
# inicio de sesión, y si nadie está mirando en ese momento para aceptarlo
# (o el aviso no se muestra bien en esa fase del arranque), simplemente
# no pasa nada — parece que "no hace nada", sin ningún error visible.
#
# La forma correcta y documentada de iniciar automáticamente una app que
# necesita permisos de administrador es una TAREA PROGRAMADA con el nivel
# "Ejecutar con los privilegios más altos" marcado — eso se autoriza una
# sola vez, al crear la tarea (con esta misma app ya corriendo como
# administrador), y desde ahí Windows la deja iniciar sola sin pedir
# permiso de nuevo cada vez.

NOMBRE_TAREA_INICIO = "TechClean_InicioAutomatico"

# La app se llamaba "TechClean Pro" y su tarea llevaba ese nombre. Hay que
# seguir mirándola: si no, en un equipo que ya tenía el inicio automático
# activado el interruptor aparecería apagado, y al activarlo quedarían DOS
# tareas — la vieja rota y la nueva — intentando abrir la app a la vez.
NOMBRE_TAREA_INICIO_ANTERIOR = "TechCleanPro_InicioAutomatico"


def _existe_tarea(nombre):
    if not IS_WINDOWS:
        return False
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", nombre],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _borrar_tarea(nombre):
    if not IS_WINDOWS:
        return False
    try:
        r = subprocess.run(["schtasks", "/delete", "/tn", nombre, "/f"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _startup_registry_path():
    """Usada por listar_apps_inicio()/set_app_inicio_activa() para
    gestionar OTRAS apps de terceros que inician con Windows — no
    relacionada con el inicio automático de TechClean mismo (ver
    set_startup() más abajo, que usa una tarea programada en vez de
    esta clave, por requerir permisos de administrador)."""
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def _ruta_ejecutable_actual():
    """Con qué hay que arrancar esta app: el .exe si está compilada, o
    python + el script si se está ejecutando desde el código."""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    return sys.executable, os.path.abspath(sys.argv[0])


def is_startup_enabled():
    """¿Está activado el inicio automático? Cuenta también la tarea con el
    nombre anterior, para que en un equipo que venía de la versión "Pro" el
    interruptor no aparezca apagado cuando en realidad está puesto."""
    return _existe_tarea(NOMBRE_TAREA_INICIO) or _existe_tarea(NOMBRE_TAREA_INICIO_ANTERIOR)


def diagnostico_inicio_automatico():
    """Estado real de la tarea de inicio. Devuelve una CLAVE de idiomas.

    Que la tarea exista no significa que vaya a arrancar. Hay dos formas
    de tener una tarea que se ve perfecta y no hace nada:

      * "config_vieja": creada por una versión anterior de la app, con el
        bloqueo por batería que ponía `schtasks /create` por su cuenta. En
        un portátil sin enchufar, no arranca nunca.

      * "ruta_vieja": la tarea guarda una ruta absoluta. Si después mueves
        la carpeta de la app —de Descargas al Escritorio, por ejemplo— la
        tarea sigue ahí, el interruptor se sigue viendo encendido, y al
        encender el equipo no pasa nada: apunta a un archivo que ya no
        existe. Imposible de adivinar sin que alguien lo diga.

    Devuelve None si no hay tarea (que no es un problema: es que está
    apagado), o una de: "inicio_ok", "inicio_config_vieja",
    "inicio_ruta_vieja".
    """
    if not IS_WINDOWS:
        return None
    # Si solo queda la tarea con el nombre anterior, hay que rehacerla igual:
    # esa es justo la que trae la configuración mala de la que se habla abajo.
    if not _existe_tarea(NOMBRE_TAREA_INICIO):
        return "inicio_config_vieja" if _existe_tarea(NOMBRE_TAREA_INICIO_ANTERIOR) else None
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", NOMBRE_TAREA_INICIO, "/xml"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        if r.returncode != 0 or not r.stdout:
            return None
        xml = r.stdout.replace(" ", "").replace("\n", "").replace("\r", "")
        if "<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>" in xml:
            return "inicio_config_vieja"
        exe, _script = _ruta_ejecutable_actual()
        if os.path.normcase(exe) not in os.path.normcase(r.stdout):
            return "inicio_ruta_vieja"
        return "inicio_ok"
    except Exception:
        return None


def set_startup(habilitar):
    """
    Agrega o quita TechClean del inicio automático de Windows usando
    una tarea programada con privilegios más altos — necesario porque la
    app requiere permisos de administrador (ver nota arriba). Requiere
    que la app YA esté corriendo como administrador para poder crear la
    tarea (si no, el comando falla y se avisa en vez de fallar en silencio).
    Devuelve (exito, comando_equivalente).
    """
    if not IS_WINDOWS:
        return False, "N/A"

    if not habilitar:
        comando = f'schtasks /delete /tn "{NOMBRE_TAREA_INICIO}" /f'
        # Se borran las dos: la del nombre actual y la del anterior. Si no,
        # apagar el interruptor dejaría viva la vieja y la app seguiría
        # abriéndose sola sin que nada en la pantalla lo explique.
        borrada_nueva = _borrar_tarea(NOMBRE_TAREA_INICIO)
        borrada_vieja = _borrar_tarea(NOMBRE_TAREA_INICIO_ANTERIOR)
        return (borrada_nueva or borrada_vieja), comando

    # BUG GORDO corregido: "activo el interruptor pero la app no arranca
    # con Windows".
    #
    # La tarea SÍ se creaba, y se veía habilitada. El problema es lo que
    # `schtasks /create` pone por su cuenta, sin avisar, y que desde la
    # línea de comandos no se puede cambiar:
    #
    #     <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    #     <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
    #
    # O sea: **en un portátil con batería, la tarea no arranca**. Y si ya
    # estaba corriendo y desenchufas, Windows la mata. Para un estudiante
    # que casi siempre trabaja sin cargador, eso es "nunca funciona" — sin
    # ningún error, sin ninguna pista.
    #
    # Ese ajuste solo se puede tocar definiendo la tarea por XML, así que
    # eso se hace ahora. De paso se arreglan tres cosas más:
    #
    #   * Un retraso de 30 s tras iniciar sesión. Arrancar a la vez que el
    #     escritorio es pelearse con Windows por el disco justo en el peor
    #     momento, y encima se nota.
    #   * Sin límite de tiempo de ejecución. Por defecto Windows mata la
    #     tarea a los 3 días, y esta app está pensada para vivir en la
    #     bandeja.
    #   * La ruta va en su propio campo XML, así que una carpeta con
    #     espacios (C:\Program Files\...) deja de ser un problema de
    #     comillas.
    exe, script = _ruta_ejecutable_actual()
    argumentos = (f'"{script}" --minimizado' if script else "--minimizado")
    usuario = os.environ.get("USERNAME", "")
    dominio = os.environ.get("USERDOMAIN", "")
    id_usuario = f"{dominio}\\{usuario}" if dominio and usuario else usuario
    carpeta_trabajo = os.path.dirname(exe)

    comando = f'schtasks /create /tn "{NOMBRE_TAREA_INICIO}" /xml <definicion> /f'

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Inicia TechClean minimizado en la bandeja al iniciar sesion.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{id_usuario}</UserId>
      <Delay>PT30S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{id_usuario}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{exe}</Command>
      <Arguments>{argumentos}</Arguments>
      <WorkingDirectory>{carpeta_trabajo}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    ruta_xml = None
    try:
        # El Programador de tareas exige UTF-16 con marca de orden de bytes:
        # con UTF-8 rechaza el archivo sin dar una razón entendible.
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                          encoding="utf-16") as f:
            f.write(xml)
            ruta_xml = f.name
        r = subprocess.run(
            ["schtasks", "/create", "/tn", NOMBRE_TAREA_INICIO, "/xml", ruta_xml, "/f"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if r.returncode == 0:
            # Ya hay tarea buena: fuera la del nombre viejo, para que no
            # queden dos abriendo la app a la vez.
            _borrar_tarea(NOMBRE_TAREA_INICIO_ANTERIOR)
        return r.returncode == 0, comando
    except Exception:
        return False, comando
    finally:
        if ruta_xml:
            try:
                os.remove(ruta_xml)
            except OSError:
                pass


# ---------------- Perfiles de energía (Silencioso / Equilibrado / Rendimiento) ----------------
# Usa los planes de energía que trae Windows por defecto (mismo GUID en
# cualquier idioma). Si un equipo no los tiene (algunos fabricantes los
# quitan o agregan planes propios), se busca por nombre como respaldo.

POWER_PLANS = {
    "silencioso": {"guid": "a1841308-3541-4fab-bc81-f71556f20b4a",
                   "palabras": ["power saver", "economizador", "ahorro"]},
    "equilibrado": {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e",
                     "palabras": ["balanced", "equilibrado"]},
    "rendimiento": {"guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
                      "palabras": ["high performance", "alto rendimiento"]},
}


def set_power_plan(perfil):
    """Cambia el plan de energía activo de Windows. Devuelve (exito, comando_equivalente)."""
    if perfil not in POWER_PLANS:
        return False, "Perfil desconocido"
    guid = POWER_PLANS[perfil]["guid"]
    comando = f"powercfg /setactive {guid}"
    if not IS_WINDOWS:
        return False, comando

    try:
        r = subprocess.run(["powercfg", "/setactive", guid], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        if r.returncode == 0:
            return True, comando
    except Exception:
        pass

    # Respaldo: el GUID estándar no existe en este equipo — buscar por nombre.
    try:
        listado = subprocess.run(["powercfg", "/list"], capture_output=True, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        for linea in (listado.stdout or "").splitlines():
            if any(p in linea.lower() for p in POWER_PLANS[perfil]["palabras"]):
                for token in linea.split():
                    if len(token) == 36 and token.count("-") == 4:
                        r2 = subprocess.run(["powercfg", "/setactive", token], capture_output=True,
                                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                        return r2.returncode == 0, f"powercfg /setactive {token}"
    except Exception:
        pass
    return False, comando


def get_active_power_plan_name():
    """Nombre del plan de energía activo ahora mismo, o None si no se puede leer."""
    if not IS_WINDOWS:
        return None
    try:
        r = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        salida = (r.stdout or "").strip()
        if "(" in salida and ")" in salida:
            return salida.split("(", 1)[1].rsplit(")", 1)[0].strip()
        return salida or None
    except Exception:
        return None


# ---------------- Reparación del sistema ----------------
# Todas usan herramientas OFICIALES de Windows (sfc, DISM, fsutil, netsh) —
# TechClean no reemplaza ni reinventa nada de esto, solo les da un botón.

def _ejecutar_reparacion_cancelable(comando_lista, timeout_seg=3600, callback_progreso=None, evento_cancelar=None):
    """
    Ejecuta un comando de reparación largo (sfc, DISM) de forma que SÍ se
    pueda cancelar desde la interfaz y SÍ se pueda mostrar cuánto tiempo
    lleva corriendo — a diferencia de subprocess.run(), que bloquea sin
    dar ninguna forma de interrumpirlo antes de que termine (o del
    timeout), dejando como única salida cerrar toda la app a la fuerza.

    evento_cancelar: threading.Event() — si se marca (.set()) mientras
    corre, el proceso se termina de inmediato, sin esperar a que Windows
    "quiera" terminar por su cuenta.
    callback_progreso(segundos_transcurridos): se llama aproximadamente
    una vez por segundo mientras sigue corriendo.

    Devuelve (exito, resumen, cancelado).
    """
    try:
        proceso = subprocess.Popen(comando_lista, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        return False, t("optmod_no_inicio", error=e), False

    inicio = time.time()
    cancelado = False
    while True:
        try:
            proceso.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            transcurrido = time.time() - inicio
            if callback_progreso:
                try:
                    callback_progreso(transcurrido)
                except Exception:
                    pass
            if evento_cancelar is not None and evento_cancelar.is_set():
                cancelado = True
                break
            if transcurrido > timeout_seg:
                cancelado = True
                break

    if cancelado:
        try:
            proceso.terminate()
            proceso.wait(timeout=8)
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass
        return False, "Se detuvo antes de completarse (cancelado o por tardar demasiado).", True

    try:
        salida = proceso.stdout.read() if proceso.stdout else ""
    except Exception:
        salida = ""
    resumen = (salida or "").strip()[-600:] or t("optmod_sin_salida")
    return proceso.returncode == 0, resumen, False


def reparar_archivos_sistema(callback_progreso=None, evento_cancelar=None):
    """
    sfc /scannow — verifica y repara archivos protegidos del sistema
    dañados o modificados. Puede tardar bastante, sobre todo en equipos
    con poca RAM o disco lento — llamar desde un hilo aparte, nunca desde
    el hilo principal de la interfaz. Cancelable mientras corre.
    Devuelve (exito, resultado_resumido, comando_equivalente).
    """
    comando = "sfc /scannow"
    if not IS_WINDOWS:
        return False, "Solo disponible en Windows", comando
    exito, resumen, _ = _ejecutar_reparacion_cancelable(
        ["sfc", "/scannow"], timeout_seg=3600,
        callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    return exito, resumen, comando


def reparar_imagen_windows(callback_progreso=None, evento_cancelar=None):
    """
    DISM /Online /Cleanup-Image /RestoreHealth — repara el almacén de
    componentes de Windows (útil cuando sfc por sí solo no basta). En
    equipos con poca RAM o disco mecánico, esto puede tardar bastante más
    de lo que parece razonable a simple vista — es normal, no un bug.
    Cancelable mientras corre.
    """
    comando = "DISM /Online /Cleanup-Image /RestoreHealth"
    if not IS_WINDOWS:
        return False, "Solo disponible en Windows", comando
    exito, resumen, _ = _ejecutar_reparacion_cancelable(
        ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"], timeout_seg=3600,
        callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    return exito, resumen, comando


def revisar_salud_imagen_windows(callback_progreso=None, evento_cancelar=None):
    """
    DISM /Online /Cleanup-Image /ScanHealth — SOLO revisa si el almacén de
    componentes está dañado, sin reparar nada. Mucho más rápido que
    RestoreHealth (normalmente minutos, no la media hora o más que puede
    tardar la reparación completa) — pensado para saber de antemano si
    hace falta la reparación larga, o si el equipo ya está sano y te
    puedes ahorrar la espera por completo.
    """
    comando = "DISM /Online /Cleanup-Image /ScanHealth"
    if not IS_WINDOWS:
        return False, "Solo disponible en Windows", comando
    exito, resumen, _ = _ejecutar_reparacion_cancelable(
        ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"], timeout_seg=1200,
        callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    return exito, resumen, comando


def revisar_disco_en_reinicio(unidad="C:"):
    """
    Marca la unidad para que Windows la revise (chkdsk) automáticamente en
    el próximo reinicio. Se usa `fsutil dirty set` en vez de invocar
    `chkdsk /f` directamente porque chkdsk pide confirmación interactiva
    S/N cuyo texto cambia según el idioma de Windows (frágil de automatizar);
    fsutil no tiene ese problema. Requiere permisos de administrador.
    """
    comando = f"fsutil dirty set {unidad}"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["fsutil", "dirty", "set", unidad], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


def reparar_red():
    """
    Reinicia los componentes de red más propensos a fallar: catálogo
    Winsock, pila TCP/IP, y limpia la caché DNS. El reseteo de
    Winsock/TCP-IP requiere reiniciar el equipo para completarse del todo.
    """
    comando = "netsh winsock reset && netsh int ip reset && ipconfig /flushdns"
    if not IS_WINDOWS:
        return False, comando
    try:
        r1 = subprocess.run(["netsh", "winsock", "reset"], capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        r2 = subprocess.run(["netsh", "int", "ip", "reset"], capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        # winsock/ip reset requieren permisos de administrador para surtir
        # efecto real — si ambos fallan, se reporta honestamente en vez de
        # decir "listo" sin haber hecho nada.
        return (r1.returncode == 0 or r2.returncode == 0), comando
    except Exception:
        return False, comando


# ---------------- Limpieza programada automática ----------------

SCHEDULED_TASK_NAME = "TechClean_LimpiezaAutomatica"


def _accion_para_tarea_programada():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --limpieza-programada'
    script = os.path.abspath(sys.argv[0])
    return f'"{sys.executable}" "{script}" --limpieza-programada'


def crear_limpieza_programada(frecuencia="DAILY", hora="09:00"):
    """
    Crea una tarea programada de Windows (Task Scheduler) que ejecuta una
    limpieza silenciosa (RAM + temporales) sin abrir ninguna ventana.
    frecuencia: 'DAILY' o 'WEEKLY'. Devuelve (exito, comando_equivalente).
    """
    accion = _accion_para_tarea_programada()
    comando = (f'schtasks /create /tn "{SCHEDULED_TASK_NAME}" /tr {accion} '
               f'/sc {frecuencia} /st {hora} /f')
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(
            ["schtasks", "/create", "/tn", SCHEDULED_TASK_NAME, "/tr", accion,
             "/sc", frecuencia, "/st", hora, "/f"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


def quitar_limpieza_programada():
    comando = f'schtasks /delete /tn "{SCHEDULED_TASK_NAME}" /f'
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["schtasks", "/delete", "/tn", SCHEDULED_TASK_NAME, "/f"],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return True, comando
    except Exception:
        return False, comando


def limpieza_programada_activa():
    if not IS_WINDOWS:
        return False
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", SCHEDULED_TASK_NAME],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


# ---------------- Gestor de apps de inicio ----------------
# Solo administra HKCU (por usuario): no requiere administrador y no
# afecta a otras cuentas del equipo. Deshabilitar mueve la entrada a una
# clave de respaldo propia (no se borra el comando original), así se
# puede reactivar después sin haber perdido nada.

STARTUP_BACKUP_KEY = r"Software\TechClean\InicioDeshabilitado"


def listar_apps_inicio():
    """Lista apps de inicio automático (activas e inactivas, deshabilitadas por esta app)."""
    if not IS_WINDOWS:
        return []
    import winreg
    apps = []

    def _leer_valores(root, ruta, activo):
        try:
            with winreg.OpenKey(root, ruta, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        nombre, valor, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    apps.append({"nombre": nombre, "comando": valor, "activo": activo})
                    i += 1
        except Exception:
            pass

    _leer_valores(winreg.HKEY_CURRENT_USER, _startup_registry_path(), True)
    _leer_valores(winreg.HKEY_CURRENT_USER, STARTUP_BACKUP_KEY, False)
    apps.sort(key=lambda a: a["nombre"].lower())
    return apps


def set_app_inicio_activa(nombre, comando_valor, activar):
    """
    Mueve una entrada de inicio entre la clave real de Windows (Run) y la
    clave de respaldo propia. activar=True la vuelve a activar;
    activar=False la deshabilita sin perder su comando original.
    """
    if not IS_WINDOWS:
        return False
    import winreg
    destino_ruta = _startup_registry_path() if activar else STARTUP_BACKUP_KEY
    origen_ruta = STARTUP_BACKUP_KEY if activar else _startup_registry_path()
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, destino_ruta) as destino:
            winreg.SetValueEx(destino, nombre, 0, winreg.REG_SZ, comando_valor)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, origen_ruta, 0, winreg.KEY_SET_VALUE) as origen:
                winreg.DeleteValue(origen, nombre)
        except FileNotFoundError:
            pass
        return True
    except Exception:
        return False


# ---------------- Desinstalador ----------------
# Lee las mismas claves de registro que "Programas y características" de
# Windows y ejecuta el desinstalador OFICIAL de cada programa — TechClean
# Pro nunca borra archivos de otros programas a mano.

def listar_programas_instalados():
    if not IS_WINDOWS:
        return []
    import winreg
    ubicaciones = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    programas = []
    vistos = set()

    for root, ruta in ubicaciones:
        try:
            with winreg.OpenKey(root, ruta) as key_padre:
                i = 0
                while True:
                    try:
                        subclave_nombre = winreg.EnumKey(key_padre, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(key_padre, subclave_nombre) as subclave:
                            def _leer(nombre_valor):
                                try:
                                    return winreg.QueryValueEx(subclave, nombre_valor)[0]
                                except FileNotFoundError:
                                    return None

                            nombre = _leer("DisplayName")
                            desinstalar = _leer("UninstallString")
                            if not nombre or not desinstalar or _leer("SystemComponent") == 1:
                                continue
                            if nombre in vistos:
                                continue
                            vistos.add(nombre)
                            tamano_kb = _leer("EstimatedSize")
                            programas.append({
                                "nombre": nombre,
                                "editor": _leer("Publisher") or "N/D",
                                "version": _leer("DisplayVersion") or "N/D",
                                "desinstalar_cmd": desinstalar,
                                "tamano_mb": round(tamano_kb / 1024, 1) if tamano_kb else None,
                            })
                    except Exception:
                        continue
        except Exception:
            continue

    programas.sort(key=lambda p: p["nombre"].lower())
    return programas


def desinstalar_programa(comando_desinstalar):
    """
    Ejecuta el desinstalador propio del programa (el mismo comando que usa
    "Programas y características" de Windows). Devuelve (exito, comando).
    """
    if not IS_WINDOWS or not comando_desinstalar:
        return False, comando_desinstalar or ""
    try:
        subprocess.Popen(comando_desinstalar, shell=True)
        return True, comando_desinstalar
    except Exception:
        return False, comando_desinstalar


def format_bytes(b):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PB"


# ---------------- Notificaciones nativas de Windows ----------------

def notificar_windows(titulo, mensaje):
    """
    Muestra una notificación nativa de Windows (Centro de actividades),
    usando PowerShell + la API de Windows Runtime — no agrega ninguna
    dependencia nueva. Si algo falla (equipo con notificaciones
    desactivadas, versión de Windows muy antigua, etc.) simplemente no se
    muestra nada; nunca interrumpe el flujo de la app.
    """
    if not IS_WINDOWS:
        return False
    titulo_seguro = titulo.replace('"', "'")
    mensaje_seguro = mensaje.replace('"', "'")
    script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0)
$textos = $xml.GetElementsByTagName("text")
$textos.Item(0).AppendChild($xml.CreateTextNode("{titulo_seguro}")) | Out-Null
$textos.Item(1).AppendChild($xml.CreateTextNode("{mensaje_seguro}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("TechClean").Show($toast)
'''
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return True
    except Exception:
        return False


# ---------------- Punto de restauración del sistema ----------------

def crear_punto_restauracion(descripcion="TechClean - antes de reparar"):
    """
    Crea un punto de restauración de Windows antes de tocar archivos del
    sistema (sfc/DISM). Requiere administrador y que la Protección del
    sistema esté activada en la unidad; Windows además limita esto por
    defecto a un punto cada 24 horas — si falla por eso, se reporta
    honestamente en vez de fingir que se creó.
    """
    comando = f'Checkpoint-Computer -Description "{descripcion}" -RestorePointType "MODIFY_SETTINGS"'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Buscar actualizaciones de Windows (informativo) ----------------

def buscar_actualizaciones_pendientes():
    """
    Busca actualizaciones de Windows pendientes usando el Agente de
    Windows Update integrado (sin instalar nada, sin PSWindowsUpdate).
    ADVERTENCIA: esto puede tardar 30-90 segundos porque contacta al
    servicio de Windows Update — llamar siempre desde un hilo aparte.
    Devuelve (exito, lista_titulos, comando).
    """
    comando = "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0')"
    if not IS_WINDOWS:
        return False, [], comando
    script = (
        "$s = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher();"
        "$r = $s.Search('IsInstalled=0 and IsHidden=0');"
        "$r.Updates | ForEach-Object { $_.Title }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        titulos = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
        return r.returncode == 0, titulos, comando
    except subprocess.TimeoutExpired:
        return False, [], comando
    except Exception:
        return False, [], comando


# ---------------- Analizador de espacio en disco ----------------

def listar_carpetas_pesadas(ruta_base, top_n=15, max_profundidad=2):
    """
    Recorre `ruta_base` y devuelve las `top_n` carpetas que más espacio
    ocupan — versión simplificada de un analizador tipo WinDirStat,
    pensada para ejecutarse en un hilo aparte. El tamaño reportado es
    APROXIMADO: solo se cuentan archivos hasta `max_profundidad` niveles
    de profundidad (carpetas más anidadas que eso no se numeran) — es una
    decisión deliberada para que el análisis sea rápido incluso en
    unidades enormes, en vez de recorrer el disco completo archivo por
    archivo. Carpetas sin permiso de lectura se saltan en silencio.
    """
    resultados = []

    def _tamano_carpeta(ruta, profundidad_restante):
        total = 0
        try:
            with os.scandir(ruta) as it:
                for entrada in it:
                    try:
                        if entrada.is_symlink():
                            continue
                        if entrada.is_file(follow_symlinks=False):
                            total += entrada.stat(follow_symlinks=False).st_size
                        elif entrada.is_dir(follow_symlinks=False) and profundidad_restante > 0:
                            # BUG corregido: antes se recursaba sin límite sin
                            # importar profundidad_restante, así que analizar
                            # C:\ intentaba recorrer TODO el disco. Ahora sí
                            # se detiene al llegar al límite de profundidad.
                            total += _tamano_carpeta(entrada.path, profundidad_restante - 1)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, FileNotFoundError, OSError):
            return 0
        return total

    try:
        with os.scandir(ruta_base) as it:
            candidatos = [e for e in it if e.is_dir(follow_symlinks=False)]
    except (PermissionError, FileNotFoundError, OSError):
        return []

    for entrada in candidatos:
        try:
            tamano = _tamano_carpeta(entrada.path, max_profundidad)
            resultados.append({"ruta": entrada.path, "bytes": tamano})
        except Exception:
            continue

    resultados.sort(key=lambda r: r["bytes"], reverse=True)
    return resultados[:top_n]


# ---------------- Medidor de velocidad de internet ----------------

def test_velocidad_internet(callback_progreso=None, callback_muestra=None):
    """
    Prueba aproximada de latencia, bajada y subida contra los endpoints
    públicos de prueba de Cloudflare (sin API key, pensados exactamente
    para esto). No es tan preciso como una app dedicada, pero no agrega
    ninguna dependencia nueva.

    Devuelve un dict con `latencia_ms`, `bajada_mbps`, `subida_mbps`
    (None en el campo que no se haya podido medir) y `error` con un
    mensaje específico — sin internet vs. servidor de prueba bloqueado,
    SSL, tiempo agotado, etc. — en vez de un "no funcionó" genérico.

    callback_progreso(codigo): avisa la fase con un CÓDIGO estable
        ("conexion", "bajada", "subida", "listo"), nunca con texto: la
        interfaz es la que traduce y la que usa esos códigos como clave.

    callback_muestra(fase, mbps): se llama unas 4 veces por segundo
        mientras hay datos moviéndose, con la velocidad instantánea. Es
        lo que alimenta la aguja en vivo de la ventana; si no interesa,
        se omite y no cuesta nada.

    BUGS corregidos aquí (el usuario reportaba que "a veces no da la
    bajada y a veces no da la subida"):

      1. La subida mandaba SIEMPRE 10 MB con un límite de 15 segundos.
         En una conexión de 5 Mbps de subida —muy común— esos 10 MB
         tardan 16 segundos: la prueba reventaba por tiempo agotado y la
         subida salía vacía, en una conexión perfectamente sana. Ahora
         primero se manda un sondeo pequeño y, con ese dato, se elige un
         tamaño que tarde ~4 segundos en ESA conexión. Si el segundo
         intento falla, se conserva el número del sondeo: mientras algo
         haya subido, siempre sale un resultado.

      2. Un fallo en la bajada cortaba la función de golpe y la subida ni
         se intentaba. Ahora cada mitad es independiente y se reporta lo
         que sí se pudo medir.

      3. El timeout global de socket era de 20 s, MENOR que el límite que
         se le pasaba a algunas peticiones: mandaba el más corto de los
         dos y cortaba antes de tiempo.
    """
    import urllib.request
    import urllib.error
    import socket
    import ssl

    # Sin un User-Agent que se vea "de navegador", muchos servicios (Cloudflare
    # incluido) bloquean la petición con error 403 — no es que esté prohibido
    # usarlo por script, es que el User-Agent por defecto de Python
    # ("Python-urllib/x.x") se parece demasiado al de un bot genérico.
    HEADERS_NAVEGADOR = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    }

    # Red de seguridad extra: el "timeout" de urlopen no siempre cubre de
    # forma confiable la resolución de DNS en Windows (limitación conocida
    # de Python/sockets) — eso podía dejar la prueba colgada mucho más
    # tiempo del que cualquiera de los timeouts de abajo sugiere. Fijar un
    # timeout global de socket es una segunda capa que sí cubre esa fase.
    # Tiene que ser MAYOR que cualquier timeout de esta función: el socket
    # se queda con el más corto de los dos.
    socket_timeout_anterior = socket.getdefaulttimeout()
    socket.setdefaulttimeout(60)

    def _avisar(codigo):
        if callback_progreso:
            try:
                callback_progreso(codigo)
            except Exception:
                pass

    def _muestra(fase, mbps):
        if callback_muestra:
            try:
                callback_muestra(fase, mbps)
            except Exception:
                pass

    resultado = {"bajada_mbps": None, "subida_mbps": None,
                 "latencia_ms": None, "error": None}

    def _error_legible(e):
        if isinstance(e, ssl.SSLError):
            return t("optmod_err_ssl", detalle=e)
        if isinstance(e, socket.timeout):
            return t("optmod_err_timeout")
        if isinstance(e, urllib.error.HTTPError):
            return t("optmod_err_http", codigo=e.code)
        if isinstance(e, urllib.error.URLError):
            razon = getattr(e, "reason", e)
            if isinstance(razon, ssl.SSLError):
                return t("optmod_err_ssl", detalle=razon)
            return f"{razon}"
        return str(e)

    class _FuenteSubida:
        """Objeto tipo archivo que le va entregando bytes a urllib.

        Se usa en vez de pasar el payload entero como `data` por dos
        razones: no hay que tener 15 MB de golpe en RAM, y cada bloque
        que se entrega es una oportunidad de reportar la velocidad en
        vivo — que es lo que mueve la aguja mientras sube.

        Ojo con lo que mide: los bytes se cuentan cuando urllib los
        recoge, no cuando llegan al otro lado, así que el primer cuarto
        de segundo se ve más rápido de lo real (el búfer del socket se
        llena de un tirón). El número FINAL no depende de esto: ese se
        calcula con el tiempo total, desde que se empieza hasta que el
        servidor responde.
        """

        BLOQUE = 65536

        def __init__(self, total, avisar):
            self.total = total
            self.entregado = 0
            self._avisar = avisar
            self._datos = os.urandom(self.BLOQUE)
            self._ultimo_aviso = time.time()
            self._desde_aviso = 0

        def __len__(self):
            return self.total

        def read(self, n=-1):
            if self.entregado >= self.total:
                return b""
            if n is None or n < 0:
                n = self.BLOQUE
            n = min(n, self.BLOQUE, self.total - self.entregado)
            self.entregado += n
            self._desde_aviso += n
            ahora = time.time()
            transcurrido = ahora - self._ultimo_aviso
            if transcurrido >= 0.25:
                self._avisar("subida", (self._desde_aviso * 8 / 1_000_000) / transcurrido)
                self._ultimo_aviso = ahora
                self._desde_aviso = 0
            return self._datos[:n]

    try:
        # ---------------- Latencia y comprobación de conexión ----------------
        _avisar("conexion")
        latencias = []
        hay_internet = False
        for _ in range(3):
            try:
                req_ping = urllib.request.Request(
                    "https://speed.cloudflare.com/__down?bytes=0", headers=HEADERS_NAVEGADOR)
                marca = time.perf_counter()
                with urllib.request.urlopen(req_ping, timeout=8) as r:
                    r.read()
                latencias.append((time.perf_counter() - marca) * 1000)
                hay_internet = True
            except Exception:
                pass
        if latencias:
            # El mínimo, no el promedio: es la medición menos contaminada por
            # un pico puntual de la red o del propio equipo.
            resultado["latencia_ms"] = round(min(latencias), 1)
        if not hay_internet:
            # Segunda opinión: puede haber internet y estar bloqueado
            # justamente Cloudflare (pasa con algunos filtros corporativos).
            try:
                urllib.request.urlopen(
                    urllib.request.Request("https://www.gstatic.com/generate_204",
                                            headers=HEADERS_NAVEGADOR), timeout=8)
                hay_internet = True
            except Exception:
                hay_internet = False

        error_bajada = None
        error_subida = None

        # ---------------- Bajada ----------------
        _avisar("bajada")
        try:
            # Antes se descargaban 10 MB de una sola vez y se dividía el total
            # entre el tiempo total. El problema es que los primeros segundos
            # de una conexión TCP van ACELERANDO (slow start): en esos 10 MB,
            # la mayor parte del tiempo se pasa subiendo la rampa, no a
            # velocidad de crucero. Medido en la línea del desarrollador, esa
            # prueba reportaba ~18 Mbps sobre una conexión real de ~135 Mbps:
            # siete veces menos.
            #
            # Ahora se lee en trozos y se DESCARTAN los primeros segundos: el
            # cronómetro arranca cuando la conexión ya va a su ritmo, y se mide
            # una ventana corta de ese tramo estable. Se pide un archivo grande
            # pero no se descarga entero — se corta en cuanto la ventana se
            # cumple, así que una conexión lenta gasta pocos datos y una rápida
            # termina igual de rápido.
            CALENTAMIENTO_S = 1.2
            MEDICION_S = 3.5
            TROZO = 65536
            TOPE_BYTES = 45_000_000

            url_descarga = f"https://speed.cloudflare.com/__down?bytes={TOPE_BYTES}"
            req_descarga = urllib.request.Request(url_descarga, headers=HEADERS_NAVEGADOR)
            inicio = time.time()
            t_medicion = None
            bytes_medidos = 0
            bytes_totales = 0
            ultimo_aviso = inicio
            desde_aviso = 0
            with urllib.request.urlopen(req_descarga, timeout=20) as resp:
                while True:
                    trozo = resp.read(TROZO)
                    if not trozo:
                        break
                    bytes_totales += len(trozo)
                    desde_aviso += len(trozo)
                    ahora = time.time()

                    transcurrido = ahora - ultimo_aviso
                    if transcurrido >= 0.25:
                        _muestra("bajada", (desde_aviso * 8 / 1_000_000) / transcurrido)
                        ultimo_aviso = ahora
                        desde_aviso = 0

                    if t_medicion is None:
                        if ahora - inicio >= CALENTAMIENTO_S:
                            t_medicion = ahora
                        continue
                    bytes_medidos += len(trozo)
                    if ahora - t_medicion >= MEDICION_S:
                        break

            if t_medicion is not None and bytes_medidos > 0:
                duracion = max(time.time() - t_medicion, 0.001)
                resultado["bajada_mbps"] = round((bytes_medidos * 8 / 1_000_000) / duracion, 2)
            elif bytes_totales > 0:
                # La descarga entera terminó antes de salir del calentamiento
                # (conexión muy rápida): no hay tramo estable que aislar, así
                # que se mide la transferencia completa, que es lo que hay.
                duracion = max(time.time() - inicio, 0.001)
                resultado["bajada_mbps"] = round((bytes_totales * 8 / 1_000_000) / duracion, 2)
            else:
                raise OSError("0 bytes")
        except Exception as e:
            if not hay_internet:
                error_bajada = t("optmod_sin_internet")
            else:
                error_bajada = t("optmod_servidor_bloqueado", detalle=_error_legible(e))

        # ---------------- Subida ----------------
        _avisar("subida")

        def _subir(tamano_bytes, tiempo_limite):
            """Sube `tamano_bytes` y devuelve (mbps, segundos)."""
            fuente = _FuenteSubida(tamano_bytes, _muestra)
            headers = dict(HEADERS_NAVEGADOR, **{
                "Content-Type": "application/octet-stream",
                "Content-Length": str(tamano_bytes),
            })
            req = urllib.request.Request("https://speed.cloudflare.com/__up",
                                          data=fuente, method="POST", headers=headers)
            marca = time.time()
            with urllib.request.urlopen(req, timeout=tiempo_limite) as resp:
                resp.read()
            segundos = max(time.time() - marca, 0.001)
            return (tamano_bytes * 8 / 1_000_000) / segundos, segundos

        SONDEO_BYTES = 1_500_000
        OBJETIVO_S = 4.0          # cuánto queremos que dure la medición buena
        MIN_BYTES = 4_000_000
        MAX_BYTES = 15_000_000    # tope para no gastar datos de más

        try:
            mbps_subida, duracion_sondeo = _subir(SONDEO_BYTES, 40)
            resultado["subida_mbps"] = round(mbps_subida, 2)

            # Si el sondeo voló, ese número no vale gran cosa (demasiado corto
            # para significar algo): se repite con un tamaño calculado para
            # esta conexión en concreto. Si el sondeo ya tardó lo suyo, la
            # conexión es lenta y no tiene sentido mandarle más datos.
            if duracion_sondeo < 2.0:
                objetivo = int((mbps_subida / 8) * 1_000_000 * OBJETIVO_S)
                tamano = max(MIN_BYTES, min(MAX_BYTES, objetivo))
                try:
                    mbps_bueno, _ = _subir(tamano, 45)
                    resultado["subida_mbps"] = round(mbps_bueno, 2)
                except Exception:
                    # El intento grande falló, pero el sondeo sí funcionó:
                    # se conserva ese resultado en vez de dejar la subida
                    # vacía, que era justo la queja.
                    pass
        except Exception as e:
            error_subida = t("optmod_subida_error", detalle=_error_legible(e))

        # ---------------- Resultado ----------------
        if resultado["bajada_mbps"] is None and resultado["subida_mbps"] is None:
            resultado["error"] = error_bajada or error_subida or t("optmod_sin_internet")
        else:
            resultado["error"] = error_bajada or error_subida

        _avisar("listo")
        return resultado
    finally:
        # Pase lo que pase (éxito, error o timeout), nunca dejar el
        # timeout global de socket cambiado para el resto de la app.
        socket.setdefaulttimeout(socket_timeout_anterior)


# ---------------- Prueba de velocidad real de disco ----------------

def prueba_velocidad_disco(tamano_mb=256, callback_progreso=None):
    """
    Prueba real de velocidad de escritura y lectura secuencial — escribe
    un archivo temporal de tamaño conocido y mide cuánto tarda, luego lo
    vuelve a leer. El "% de uso en este momento" que ya mostramos en
    Componentes no dice nada sobre qué tan RÁPIDO es el disco en sí; esto
    sí da un número concreto y comparable (MB/s).

    Con honestidad sobre sus límites: no es tan preciso como un benchmark
    dedicado (no prueba distintas profundidades de cola como
    CrystalDiskMark), y la LECTURA puede salir más rápida de lo real
    porque Windows cachea en RAM lo que acaba de escribir — vaciar esa
    caché requeriría privilegios que no tiene un script normal. Aun así,
    refleja bien la diferencia entre un SSD decente y un disco mecánico
    viejo, que es la pregunta que de verdad importa aquí.
    """
    if not IS_WINDOWS:
        return None

    def _avisar(texto):
        if callback_progreso:
            try:
                callback_progreso(texto)
            except Exception:
                pass

    ruta_prueba = os.path.join(tempfile.gettempdir(), "techclean_prueba_disco.tmp")
    bloque = os.urandom(1024 * 1024)  # 1 MB de datos aleatorios — no comprimibles, prueba más honesta
    try:
        _avisar(t("comp_disco_fase_escribiendo"))
        inicio = time.time()
        with open(ruta_prueba, "wb") as f:
            for _ in range(tamano_mb):
                f.write(bloque)
            f.flush()
            os.fsync(f.fileno())
        duracion_escritura = time.time() - inicio
        velocidad_escritura = tamano_mb / duracion_escritura if duracion_escritura > 0 else 0

        _avisar(t("comp_disco_fase_leyendo"))
        inicio = time.time()
        with open(ruta_prueba, "rb") as f:
            while f.read(1024 * 1024):
                pass
        duracion_lectura = time.time() - inicio
        velocidad_lectura = tamano_mb / duracion_lectura if duracion_lectura > 0 else 0

        _avisar(t("comp_disco_fase_listo"))
        return {
            "escritura_mbs": round(velocidad_escritura, 1),
            "lectura_mbs": round(velocidad_lectura, 1),
            "tamano_probado_mb": tamano_mb,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        try:
            os.remove(ruta_prueba)
        except Exception:
            pass


# ---------------- Servicios de Windows ----------------
# Se listan TODOS los servicios (valor informativo, como HWiNFO) pero
# cambiar cualquiera de ellos siempre pasa por una confirmación explícita
# en la interfaz — no hay una lista blanca "segura" porque varía de
# equipo a equipo, así que la salvaguarda real es que el usuario decida
# con el nombre y estado del servicio delante, no una suposición nuestra.

def listar_servicios_por_consumo(limite=15):
    """
    Servicios de Windows agrupados por el proceso que los hospeda, con
    cuánta RAM está usando cada uno — a diferencia de la lista general de
    servicios (que solo dice si están corriendo o no), esto dice cuáles
    están consumiendo recursos de verdad todo el tiempo que el equipo
    está encendido, no solo al arrancar.

    Aviso honesto: varios servicios suelen compartir un mismo proceso
    "svchost.exe" (Windows los agrupa así para ahorrar memoria) — cuando
    eso pasa, la RAM mostrada es del PROCESO completo, compartida entre
    todos los servicios que viven ahí, no de uno solo por separado. Se
    listan juntos, con todos sus nombres, para que quede claro cuando es
    el caso — no hay forma de partir esa cifra por servicio individual
    sin herramientas más profundas.
    """
    if not IS_WINDOWS:
        return []
    script = ("Get-CimInstance Win32_Service | Where-Object {$_.State -eq 'Running' -and $_.ProcessId -ne 0} "
               "| Select-Object Name, DisplayName, ProcessId | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
        datos = json.loads(r.stdout) if r.stdout else []
        if isinstance(datos, dict):
            datos = [datos]
    except Exception:
        return []

    por_pid = {}
    for d in datos:
        pid = d.get("ProcessId")
        if not pid:
            continue
        por_pid.setdefault(pid, []).append(d.get("DisplayName") or d.get("Name") or "?")

    resultado = []
    for pid, nombres in por_pid.items():
        try:
            proceso = psutil.Process(pid)
            ram = proceso.memory_info().rss
        except Exception:
            continue
        resultado.append({"pid": pid, "servicios": nombres, "bytes_ram": ram})
    resultado.sort(key=lambda x: x["bytes_ram"], reverse=True)
    return resultado[:limite]


def listar_servicios_windows():
    if not IS_WINDOWS:
        return []
    script = (
        "Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
        return [{"nombre": d.get("Name"), "nombre_visible": d.get("DisplayName"),
                 "estado": d.get("Status"), "inicio": d.get("StartType")} for d in datos]
    except Exception:
        return []


def set_servicio_windows(nombre, accion):
    """accion: 'iniciar' o 'detener'. Requiere administrador para la
    mayoría de servicios del sistema. Devuelve (exito, comando)."""
    if not IS_WINDOWS or accion not in ("iniciar", "detener"):
        return False, ""
    cmdlet = "Start-Service" if accion == "iniciar" else "Stop-Service"
    # BUG corregido: -Force solo existe en Stop-Service. Pasárselo a
    # Start-Service hacía que PowerShell rechazara el comando entero por
    # un parámetro inválido — el botón "Iniciar" de cualquier servicio
    # siempre fallaba.
    extra = " -Force" if accion == "detener" else ""
    comando = f'{cmdlet} -Name "{nombre}"{extra}'
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             f'{comando} -ErrorAction Stop'],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Seguridad al detener servicios ----------------
# Mismo criterio que con los procesos (evaluar_riesgo_proceso): algunos
# servicios de Windows son tan centrales que detenerlos puede dejar
# partes completas del sistema sin responder, a veces sin arreglo fácil
# para alguien que no sabe qué pasó — esos quedan bloqueados por
# completo. Otros (Defender, Firewall, Windows Update) sí tienen razones
# legítimas para detenerse (por ejemplo, usar un antivirus de terceros),
# así que solo llevan una advertencia fuerte, no un bloqueo.

# Estos diccionarios se construyen AL IMPORTAR el modulo, antes de que
# establecer_idioma() haya corrido, asi que guardan el NOMBRE de la clave y
# no el texto: t() se llama al consultarlos, en evaluar_riesgo_servicio().
SERVICIOS_BLOQUEADOS = {
    "rpcss": "riesgo_srv_rpcss",
    "dcomlaunch": "riesgo_srv_dcomlaunch",
    "winmgmt": "riesgo_srv_winmgmt",
    "plugplay": "riesgo_srv_plugplay",
    "power": "riesgo_srv_power",
    "bfe": "riesgo_srv_bfe",
    "cryptsvc": "riesgo_srv_cryptsvc",
}

SERVICIOS_ADVERTENCIA = {
    "windefend": "riesgo_srv_windefend",
    "mpssvc": "riesgo_srv_mpssvc",
    "wuauserv": "riesgo_srv_wuauserv",
    "dnscache": "riesgo_srv_dnscache",
}


def evaluar_riesgo_servicio(nombre):
    """
    Devuelve ('bloqueado', motivo), ('advertencia', motivo) o ('normal', None)
    según qué tan crítico es un servicio de Windows — para que la
    interfaz decida si impedir detenerlo por completo, avisar con más
    fuerza, o solo pedir la confirmación normal.
    """
    clave = (nombre or "").strip().lower()
    if clave in SERVICIOS_BLOQUEADOS:
        return "bloqueado", t(SERVICIOS_BLOQUEADOS[clave])
    if clave in SERVICIOS_ADVERTENCIA:
        return "advertencia", t(SERVICIOS_ADVERTENCIA[clave])
    return "normal", None


# ---------------- Papelera segura para archivos individuales ----------------

def enviar_a_papelera(rutas):
    """
    Envía archivos a la papelera de reciclaje (NO los borra directo) usando
    SHFileOperationW — la misma API que usa el Explorador de Windows al
    arrastrar algo a la papelera, así el usuario puede deshacerlo si se
    equivocó. Pensada para borrar archivos elegidos por el usuario
    (instaladores viejos, archivos grandes) — a diferencia de los
    temporales, que sí se eliminan directo por ser desechables por diseño.
    Devuelve (eliminados, bytes_liberados, errores).
    """
    if not IS_WINDOWS or not rutas:
        return 0, 0, []

    bytes_totales = 0
    for r in rutas:
        try:
            bytes_totales += os.path.getsize(r)
        except OSError:
            pass

    lista_rutas = "\0".join(os.path.abspath(r) for r in rutas) + "\0\0"

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.wintypes.HWND),
            ("wFunc", ctypes.wintypes.UINT),
            ("pFrom", ctypes.wintypes.LPCWSTR),
            ("pTo", ctypes.wintypes.LPCWSTR),
            ("fFlags", ctypes.wintypes.WORD),
            ("fAnyOperationsAborted", ctypes.wintypes.BOOL),
            ("hNameMappings", ctypes.wintypes.LPVOID),
            ("lpszProgressTitle", ctypes.wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    FOF_NOERRORUI = 0x0400

    operacion = SHFILEOPSTRUCTW()
    operacion.hwnd = None
    operacion.wFunc = FO_DELETE
    operacion.pFrom = lista_rutas
    operacion.pTo = None
    operacion.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

    try:
        resultado = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operacion))
        if resultado == 0 and not operacion.fAnyOperationsAborted:
            return len(rutas), bytes_totales, []
        return 0, 0, [t("optmod_papelera_codigo", codigo=resultado)]
    except Exception as e:
        return 0, 0, [str(e)]


# ---------------- Archivos grandes individuales ----------------

def listar_archivos_grandes(ruta_base, min_mb=100, limite=30, presupuesto_seg=20):
    """
    Busca los archivos individuales más grandes dentro de `ruta_base`.
    Tiene un presupuesto de tiempo (20s por defecto): si el disco es
    enorme, se detiene ahí y devuelve lo que encontró hasta ese momento —
    mejor una respuesta rápida y parcial que dejar la app "pensando"
    varios minutos. No sigue enlaces simbólicos (evita bucles infinitos).
    """
    resultados = []
    inicio = time.time()
    min_bytes = min_mb * 1024 * 1024
    try:
        for carpeta_actual, _subcarpetas, archivos in os.walk(ruta_base, topdown=True, onerror=lambda e: None):
            if time.time() - inicio > presupuesto_seg:
                break
            for nombre in archivos:
                ruta = os.path.join(carpeta_actual, nombre)
                try:
                    tam = os.path.getsize(ruta)
                    if tam >= min_bytes:
                        resultados.append({"ruta": ruta, "bytes": tam})
                except (OSError, PermissionError):
                    continue
    except Exception:
        pass
    resultados.sort(key=lambda r: r["bytes"], reverse=True)
    return resultados[:limite]


# ---------------- Instaladores viejos en Descargas ----------------

def listar_instaladores_viejos(dias=30):
    """Instaladores y archivos comprimidos (.exe/.msi/.msix/.zip/.rar/.7z)
    en la carpeta Descargas más viejos que `dias` días — candidatos obvios
    a borrar sin drama: instaladores porque una vez instalado el programa
    ya no sirven, y comprimidos porque son fáciles de volver a descargar
    si de verdad hacen falta (útil, por ejemplo, para ir limpiando ZIPs
    de versiones de esta misma app que ya no necesites)."""
    carpeta = carpeta_conocida("descargas", respaldos=(
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Descargas"),
    ))
    if not carpeta:
        return []

    limite_tiempo = time.time() - dias * 86400
    resultados = []
    try:
        with os.scandir(carpeta) as it:
            for entrada in it:
                if not entrada.is_file(follow_symlinks=False):
                    continue
                if not entrada.name.lower().endswith((".exe", ".msi", ".msix", ".zip", ".rar", ".7z")):
                    continue
                try:
                    info = entrada.stat()
                    if info.st_mtime < limite_tiempo:
                        resultados.append({"ruta": entrada.path, "bytes": info.st_size, "mtime": info.st_mtime})
                except OSError:
                    continue
    except (FileNotFoundError, PermissionError):
        return []
    resultados.sort(key=lambda r: r["bytes"], reverse=True)
    return resultados


# ---------------- Caché de apps comunes ----------------
# Solo lee/borra dentro de carpetas de CACHÉ conocidas (nunca configuración
# ni datos de usuario) — regenerar una caché es normal y seguro; la app en
# cuestión simplemente la vuelve a crear la próxima vez que la abras.

def _ruta_localappdata():
    return os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


def listar_cache_apps_comunes():
    base = _ruta_localappdata()
    # Se arma DENTRO de la funcion, no a nivel de modulo, asi que aqui t() ya
    # tiene el idioma fijado y se puede traducir directo.
    candidatos = {
        t("optmod_cache_steam"): os.path.join(base, "..", "Roaming", "Steam", "htmlcache"),
        t("optmod_cache_discord"): os.path.join(base, "Discord", "Cache"),
        t("optmod_cache_onedrive"): os.path.join(base, "Microsoft", "OneDrive", "logs"),
        t("optmod_cache_pip"): os.path.join(base, "pip", "Cache"),
        t("optmod_cache_npm"): os.path.join(base, "npm-cache"),
        t("optmod_cache_spotify"): os.path.join(base, "Spotify", "Storage"),
    }
    resultados = []
    for nombre, ruta in candidatos.items():
        ruta = os.path.normpath(ruta)
        if not os.path.isdir(ruta):
            continue
        total = 0
        try:
            for carpeta_actual, _sub, archivos in os.walk(ruta, onerror=lambda e: None):
                for a in archivos:
                    try:
                        total += os.path.getsize(os.path.join(carpeta_actual, a))
                    except OSError:
                        continue
        except Exception:
            continue
        if total > 0:
            resultados.append({"nombre": nombre, "ruta": ruta, "bytes": total})
    resultados.sort(key=lambda r: r["bytes"], reverse=True)
    return resultados


def limpiar_cache_app(ruta):
    """Borra el CONTENIDO de una carpeta de caché (no la carpeta en sí, para
    que la app no truene la próxima vez que la busque). Devuelve
    (bytes_liberados, comando)."""
    comando = f'Vaciar contenido de "{ruta}"'
    liberado = 0
    if not os.path.isdir(ruta):
        return 0, comando
    try:
        with os.scandir(ruta) as it:
            for entrada in it:
                try:
                    if entrada.is_dir(follow_symlinks=False):
                        tam = sum(os.path.getsize(os.path.join(dp, f))
                                  for dp, _, fs in os.walk(entrada.path) for f in fs)
                        shutil.rmtree(entrada.path, ignore_errors=True)
                        liberado += tam
                    else:
                        tam = entrada.stat().st_size
                        os.remove(entrada.path)
                        liberado += tam
                except Exception:
                    continue
    except Exception:
        pass
    return liberado, comando


# ---------------- Drivers (solo canales oficiales) ----------------
# Deliberadamente NO se instala nada automáticamente aquí. Solo se informa
# y se dan enlaces/accesos oficiales — la razón está explicada en el README.

MAPA_SOPORTE_FABRICANTES = {
    "dell": "https://www.dell.com/support/home",
    "hp": "https://support.hp.com/",
    "hewlett-packard": "https://support.hp.com/",
    "lenovo": "https://pcsupport.lenovo.com/",
    "asus": "https://www.asus.com/support/",
    "acer": "https://www.acer.com/support",
    "msi": "https://www.msi.com/support",
    "microsoft": "https://support.microsoft.com/surface",
    "samsung": "https://www.samsung.com/support/",
    "toshiba": "https://support.dynabook.com/",
    "gigabyte": "https://www.gigabyte.com/Support",
}


def obtener_fabricante_soporte():
    """Fabricante/modelo del equipo (Win32_ComputerSystem) + el enlace de
    soporte oficial correspondiente, cuando se reconoce la marca."""
    if not IS_WINDOWS:
        return {"fabricante": "N/D", "modelo": "N/D", "url_soporte": None}
    filas = _cim("Win32_ComputerSystem", ["Manufacturer", "Model"])
    if not filas:
        return {"fabricante": "N/D", "modelo": "N/D", "url_soporte": None}
    fabricante = (filas[0].get("Manufacturer") or "N/D").strip()
    modelo = (filas[0].get("Model") or "N/D").strip()
    clave = fabricante.lower()
    url = None
    for k, v in MAPA_SOPORTE_FABRICANTES.items():
        if k in clave:
            url = v
            break
    return {"fabricante": fabricante, "modelo": modelo, "url_soporte": url}


def buscar_actualizaciones_drivers():
    """
    Busca actualizaciones de DRIVERS pendientes en Windows Update (mismo
    Agente de Windows Update oficial, filtrado por Type='Driver'). No
    instala nada — solo informa cuáles hay disponibles; instalarlas se
    hace desde Configuración > Windows Update, como cualquier actualización.
    Puede tardar 30-90 segundos. Devuelve (exito, lista_titulos, comando).
    """
    comando = "UpdateSearcher.Search(\"IsInstalled=0 and Type='Driver'\")"
    if not IS_WINDOWS:
        return False, [], comando
    script = (
        "$s = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher();"
        "$r = $s.Search(\"IsInstalled=0 and IsHidden=0 and Type='Driver'\");"
        "$r.Updates | ForEach-Object { $_.Title }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        titulos = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
        return r.returncode == 0, titulos, comando
    except subprocess.TimeoutExpired:
        return False, [], comando
    except Exception:
        return False, [], comando


def abrir_administrador_dispositivos():
    comando = "control hdwwiz.cpl (Administrador de dispositivos)"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["control", "hdwwiz.cpl"])
        return True, comando
    except Exception:
        return False, comando


# ---------------- Seguridad: Windows Defender ----------------
# No se reemplaza ni se reinventa un antivirus — Windows ya trae uno bueno
# (Defender). Solo se le da un botón a lo que ya existe.

def iniciar_escaneo_defender(tipo="rapido"):
    """
    Inicia un escaneo con Windows Defender. tipo: 'rapido' (unos minutos)
    o 'completo' (puede tardar horas). No se espera a que termine — el
    escaneo sigue corriendo en Windows aunque cierres TechClean.
    """
    scan_type = "QuickScan" if tipo == "rapido" else "FullScan"
    comando = f"Start-MpScan -ScanType {scan_type}"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                          creationflags=subprocess.CREATE_NO_WINDOW)
        return True, comando
    except Exception:
        return False, comando


def obtener_estado_defender():
    """Última vez que se escaneó y si la protección en tiempo real está
    activa (Get-MpComputerStatus) — informativo."""
    if not IS_WINDOWS:
        return None
    script = ("Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, "
              "QuickScanAge, FullScanAge | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if not r.stdout:
            return None
        datos = json.loads(r.stdout)
        return {
            "activo": bool(datos.get("AntivirusEnabled")),
            "tiempo_real": bool(datos.get("RealTimeProtectionEnabled")),
            "dias_desde_ultimo_rapido": datos.get("QuickScanAge"),
            "dias_desde_ultimo_completo": datos.get("FullScanAge"),
        }
    except Exception:
        return None


# ---------------- Seguridad: permisos de privacidad ----------------

def listar_permisos_privacidad(tipo="webcam"):
    """
    Lista qué apps tienen permiso de cámara/micrófono/ubicación — lee la
    misma configuración que Configuración > Privacidad de Windows.
    tipo: 'webcam', 'microphone' o 'location'.
    """
    if not IS_WINDOWS:
        return []
    import winreg
    ruta_base = rf"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{tipo}"

    def _estado(key, subclave):
        try:
            with winreg.OpenKey(key, subclave) as appkey:
                valor, _ = winreg.QueryValueEx(appkey, "Value")
                # Codigo interno, NO texto para mostrar: main.py lo traduce y
                # ademas elige el color a partir de el. Si aqui se devolviera
                # texto traducido, la comparacion que pinta el color en
                # main.py fallaria en cuanto cambiara el idioma.
                return "permitido" if valor == "Allow" else "bloqueado"
        except Exception:
            return "desconocido"

    resultados = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta_base) as key:
            i = 0
            while True:
                try:
                    nombre = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                if nombre == "NonPackaged":
                    # Apps de escritorio clásicas (no UWP) — anidadas una carpeta más adentro.
                    try:
                        with winreg.OpenKey(key, nombre) as sub:
                            j = 0
                            while True:
                                try:
                                    nombre_app = winreg.EnumKey(sub, j)
                                except OSError:
                                    break
                                j += 1
                                resultados.append({"app": nombre_app, "estado": _estado(sub, nombre_app)})
                    except Exception:
                        pass
                    continue
                resultados.append({"app": nombre, "estado": _estado(key, nombre)})
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return resultados


# ---------------- Seguridad: Firewall ----------------

def listar_reglas_firewall_bloqueadas(limite=100):
    """Reglas del Firewall de Windows que están BLOQUEANDO algo (lo más
    relevante para revisar) — Get-NetFirewallRule."""
    if not IS_WINDOWS:
        return []
    script = (f"Get-NetFirewallRule -Action Block -Enabled True | Select-Object -First {limite} "
              f"DisplayName, Direction | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
        return [{"nombre": d.get("DisplayName"), "direccion": d.get("Direction")} for d in datos]
    except Exception:
        return []


def bloquear_app_firewall(ruta_exe):
    """
    Crea una regla que le bloquea la conexión a internet (entrada Y
    salida) a un programa puntual — sin tocar el resto del firewall.
    Requiere administrador. Devuelve (exito, nombre_regla, comando).
    """
    nombre_regla = f"TechClean-Bloqueo-{os.path.basename(ruta_exe)}"
    comando = (f'New-NetFirewallRule -DisplayName "{nombre_regla}" -Direction Outbound '
               f'-Program "{ruta_exe}" -Action Block; '
               f'New-NetFirewallRule -DisplayName "{nombre_regla}-In" -Direction Inbound '
               f'-Program "{ruta_exe}" -Action Block')
    if not IS_WINDOWS:
        return False, nombre_regla, comando
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             comando + " -ErrorAction Stop"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        return r.returncode == 0, nombre_regla, comando
    except Exception:
        return False, nombre_regla, comando


def desbloquear_app_firewall(nombre_regla):
    comando = f'Remove-NetFirewallRule -DisplayName "{nombre_regla}*"'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             f'Get-NetFirewallRule -DisplayName "{nombre_regla}*" | Remove-NetFirewallRule -ErrorAction Stop'],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Contador de FPS (seguro, sin inyección) ----------------
# Deliberadamente NO se hace un overlay que se inyecte en el proceso del
# juego (así funcionan RTSS/MSI Afterburner) — eso es exactamente el
# patrón que los anti-cheats (BattlEye, EasyAntiCheat, Vanguard) marcan
# como sospechoso, con riesgo real de baneo en juegos competitivos. En vez
# de eso, se abre el overlay de Rendimiento de Xbox Game Bar: lo mantiene
# Microsoft a nivel de sistema operativo y los anti-cheats ya lo tienen en
# lista blanca porque es parte de Windows, no una inyección de terceros.

def protocolo_registrado(nombre):
    """¿Sabe Windows abrir un enlace del tipo `nombre:`?

    Se mira en el registro, bajo HKEY_CLASSES_ROOT, que es exactamente
    donde busca Windows al pedirle que abra uno. Es instantáneo — nada de
    lanzar PowerShell.

    Comprobar esto ANTES de intentar abrirlo es la única forma de saber si
    va a funcionar: `os.startfile` con un protocolo que nadie registró NO
    lanza ningún error. Windows lo considera "abierto con éxito" y a
    cambio muestra la Microsoft Store diciendo que te falta una app.
    """
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, nombre) as clave:
            winreg.QueryValueEx(clave, "URL Protocol")
        return True
    except OSError:
        return False


def abrir_contador_fps_windows():
    """Abre Xbox Game Bar, que trae el panel de Rendimiento con los FPS.

    BUG corregido (reportado por el usuario: "me manda a la Microsoft
    Store y no encuentra lo que busca").

    Se intentaba `ms-gamebaroverlay:` y, si fallaba, `ms-gamebar:`. El
    problema es que **el primero nunca fallaba**. `ms-gamebaroverlay:` era
    válido en versiones viejas de Game Bar y las nuevas ya no lo
    registran; pero `os.startfile` con un protocolo sin registrar no lanza
    excepción: Windows da la llamada por buena y abre la Microsoft Store
    ofreciendo "buscar una app". Como no había excepción, el respaldo
    —que sí funciona— no se probaba nunca.

    Comprobado en el equipo del desarrollador: el paquete
    Microsoft.XboxGamingOverlay está instalado y en estado Ok, `ms-gamebar`
    está registrado, y `ms-gamebaroverlay` NO.

    Ahora se mira el registro primero y solo se abre el protocolo que de
    verdad existe. Si no hay ninguno, se dice claramente en vez de mandar
    a nadie a la tienda.
    """
    comando = "Xbox Game Bar (protocolo ms-gamebar)"
    if not IS_WINDOWS:
        return False, comando

    # En orden de preferencia: el que lleva directo al overlay primero.
    for protocolo in ("ms-gamebaroverlay", "ms-gamebar"):
        if not protocolo_registrado(protocolo):
            continue
        try:
            os.startfile(protocolo + ":")
            return True, f"{protocolo}: (Xbox Game Bar)"
        except Exception:
            continue

    return False, comando


def game_bar_disponible():
    """(disponible, motivo_clave) — para poder explicar POR QUÉ no se puede.

    `motivo_clave` es una clave de idiomas, nunca texto ya traducido: si
    aquí viajara texto, la interfaz no podría traducirlo a su idioma.
    """
    if not IS_WINDOWS:
        return False, "gaming_fps_no_windows"
    if protocolo_registrado("ms-gamebaroverlay") or protocolo_registrado("ms-gamebar"):
        return True, ""
    return False, "gaming_fps_no_instalada"


# ---------------- Reparar: Windows Store y adaptador de red específico ----------------

def reparar_windows_store():
    """wsreset.exe — limpia la caché de la Tienda de Windows, arregla el
    caso típico de 'la Tienda no abre' o 'no descarga'. No borra apps
    instaladas, solo el estado interno de la Tienda."""
    comando = "wsreset.exe"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["wsreset.exe"])
        return True, comando
    except Exception:
        return False, comando


def listar_adaptadores_red():
    """Adaptadores de red activos (Get-NetAdapter) — para poder reiniciar
    solo uno en vez de resetear todo Winsock/TCP-IP de una vez."""
    if not IS_WINDOWS:
        return []
    script = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object Name, InterfaceDescription | ConvertTo-Json -Compress"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
        return [{"nombre": d.get("Name"), "descripcion": d.get("InterfaceDescription")} for d in datos]
    except Exception:
        return []


def reiniciar_adaptador_red(nombre):
    """Deshabilita y vuelve a habilitar UN adaptador de red puntual —
    más quirúrgico que reiniciar Winsock/TCP-IP completo. Requiere
    administrador."""
    comando = f'Restart-NetAdapter -Name "{nombre}"'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             comando + " -ErrorAction Stop"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Aplicaciones: actualizar vía winget (catálogo oficial) ----------------
# winget viene integrado en Windows 10/11 desde hace años — es el gestor de
# paquetes oficial de Microsoft. A diferencia de un "driver updater" de
# terceros, cada app se actualiza desde su propio publicador verificado en
# el catálogo, el mismo mecanismo que usa la Microsoft Store por debajo.

def winget_disponible():
    if not IS_WINDOWS:
        return False
    try:
        r = subprocess.run(["winget", "--version"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def listar_actualizaciones_winget():
    """Apps con actualización disponible según winget. Puede tardar
    30-60 segundos. Devuelve (exito, lista, comando)."""
    comando = "winget upgrade --include-unknown"
    if not IS_WINDOWS:
        return False, [], comando
    try:
        r = subprocess.run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)
        lineas = (r.stdout or "").splitlines()
        apps = []
        empezo = False
        for linea in lineas:
            texto = linea.strip()
            if texto.startswith("Name") and "Id" in texto:
                empezo = True
                continue
            if not empezo or not texto or texto.startswith("-"):
                continue
            # Winget termina la lista con una línea de resumen tipo "3 upgrades
            # available." — no es una app, se filtra para no mostrarla como una.
            if "upgrades available" in texto.lower() or texto.lower().startswith("no "):
                continue
            partes = texto.split()
            if len(partes) >= 2:
                apps.append(texto)
        return True, apps, comando
    except subprocess.TimeoutExpired:
        return False, [], comando
    except Exception:
        return False, [], comando


def actualizar_app_winget(id_o_nombre):
    """Actualiza UNA app puntual vía winget (no todas a la vez, para que
    el usuario decida cuál). Corre en segundo plano (Popen) porque puede
    tardar varios minutos según el tamaño del instalador."""
    comando = f'winget upgrade --id "{id_o_nombre}" --silent --accept-package-agreements --accept-source-agreements'
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["winget", "upgrade", "--id", id_o_nombre, "--silent",
                          "--accept-package-agreements", "--accept-source-agreements"],
                          creationflags=subprocess.CREATE_NO_WINDOW)
        return True, comando
    except Exception:
        return False, comando


def listar_tareas_programadas_terceros(limite=100):
    """
    Lista TODAS las tareas programadas activas del equipo (no solo la
    nuestra) — para que el usuario vea qué más se ejecuta solo, algo que
    a veces queda oculto de cuando se instaló un programa hace tiempo.
    Solo lectura, informativo.
    """
    if not IS_WINDOWS:
        return []
    script = (f"Get-ScheduledTask | Where-Object {{$_.State -ne 'Disabled'}} | "
              f"Select-Object -First {limite} TaskName, TaskPath | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
        return [{"nombre": d.get("TaskName"), "ruta": d.get("TaskPath")} for d in datos
                if d.get("TaskName") and not str(d.get("TaskName")).startswith("TechClean")]
    except Exception:
        return []


# ---------------- Privacidad: accesos recientes y portapapeles ----------------

def limpiar_accesos_recientes():
    """
    Vacía 'Accesos recientes' / Quick Access de Windows — borra los
    accesos directos a archivos y carpetas recientes que Windows guarda,
    no los archivos en sí.
    """
    comando = 'del "%APPDATA%\\Microsoft\\Windows\\Recent\\*" (accesos recientes)'
    if not IS_WINDOWS:
        return 0, comando
    carpeta = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
    borrados = 0
    if os.path.isdir(carpeta):
        try:
            with os.scandir(carpeta) as it:
                for entrada in it:
                    try:
                        if entrada.is_file():
                            os.remove(entrada.path)
                            borrados += 1
                    except Exception:
                        continue
        except Exception:
            pass
    return borrados, comando


def limpiar_portapapeles():
    """
    Vacía el portapapeles de Windows (texto/imágenes copiados). Usa la
    misma API que cualquier app normal usaría para 'limpiar' el
    portapapeles — no es nada invasivo ni de bajo nivel.
    """
    comando = "OpenClipboard + EmptyClipboard (user32.dll)"
    if not IS_WINDOWS:
        return False, comando
    try:
        ctypes.windll.user32.OpenClipboard(None)
        ctypes.windll.user32.EmptyClipboard()
        ctypes.windll.user32.CloseClipboard()
        return True, comando
    except Exception:
        try:
            ctypes.windll.user32.CloseClipboard()
        except Exception:
            pass
        return False, comando


# ---------------- Seguridad: BitLocker y Windows Hello ----------------

def obtener_estado_bitlocker():
    """Estado de cifrado BitLocker de la unidad C: — informativo (saber
    si el equipo está protegido si te lo roban), no lo activa ni desactiva."""
    if not IS_WINDOWS:
        return None
    script = "Get-BitLockerVolume -MountPoint C: | Select-Object VolumeStatus, ProtectionStatus | ConvertTo-Json -Compress"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if not r.stdout:
            return None
        datos = json.loads(r.stdout)
        return {
            "estado_volumen": datos.get("VolumeStatus"),
            "proteccion_activa": datos.get("ProtectionStatus") == 1,
        }
    except Exception:
        return None


def obtener_estado_windows_hello():
    """Si hay un PIN/biometría de Windows Hello configurado — se detecta
    por la presencia de credenciales NGC (Next Generation Credentials, el
    nombre interno de Hello) para algún usuario del equipo. Informativo."""
    if not IS_WINDOWS:
        return None
    return {"configurado": _tiene_credenciales_ngc()}


def _tiene_credenciales_ngc():
    """Windows Hello guarda sus credenciales (PIN/biometría) en
    %WINDIR%\\ServiceProfiles\\Local Service\\AppData\\Local\\Microsoft\\Ngc
    — si esa carpeta tiene contenido, hay al menos un método configurado."""
    try:
        base = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "ServiceProfiles",
                             "Local Service", "AppData", "Local", "Microsoft", "Ngc")
        return os.path.isdir(base) and len(os.listdir(base)) > 0
    except Exception:
        return False


# ---------------- Caché de miniaturas ----------------

def limpiar_cache_miniaturas():
    """
    Limpia la caché de miniaturas de Windows (thumbcache_*.db) — se
    regenera sola la próxima vez que abras el Explorador, así que
    borrarla es seguro; a veces también arregla miniaturas que se ven
    rotas o desactualizadas.
    """
    comando = 'del "%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer\\thumbcache_*.db"'
    if not IS_WINDOWS:
        return 0, 0, comando
    carpeta = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")
    liberado = 0
    borrados = 0
    if os.path.isdir(carpeta):
        try:
            with os.scandir(carpeta) as it:
                for entrada in it:
                    if entrada.name.lower().startswith("thumbcache_") and entrada.name.lower().endswith(".db"):
                        try:
                            liberado += entrada.stat().st_size
                            os.remove(entrada.path)
                            borrados += 1
                        except Exception:
                            continue
        except Exception:
            pass
    return borrados, liberado, comando


# ---------------- Limpieza programada de una sola vez ----------------

def crear_limpieza_unica(minutos_desde_ahora=5):
    """Tarea programada que corre UNA sola vez (no recurrente), pensada
    para 'límpiame en un rato, cuando termine lo que estoy haciendo' en
    vez de la limpieza recurrente diaria/semanal."""
    from datetime import datetime, timedelta
    hora_objetivo = (datetime.now() + timedelta(minutes=minutos_desde_ahora)).strftime("%H:%M")
    accion = _accion_para_tarea_programada()
    nombre_tarea = "TechClean_LimpiezaUnica"
    comando = f'schtasks /create /tn "{nombre_tarea}" /tr {accion} /sc once /st {hora_objetivo} /f'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(
            ["schtasks", "/create", "/tn", nombre_tarea, "/tr", accion,
             "/sc", "once", "/st", hora_objetivo, "/f"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Enfoque asistido (atajo seguro, sin tocar registro) ----------------

def abrir_configuracion_enfoque_asistido():
    """
    Abre la configuración de Enfoque asistido de Windows. Deliberadamente
    NO se activa por registro de forma automática: su estado vive en una
    estructura interna no documentada de Windows (CloudStore), y
    escribirla a ciegas podría corromper la configuración de
    notificaciones — mejor un atajo seguro a la pantalla oficial que el
    usuario confirma con un clic.
    """
    comando = "ms-settings:quiethours"
    if not IS_WINDOWS:
        return False, comando
    try:
        os.startfile("ms-settings:quiethours")
        return True, comando
    except Exception:
        return False, comando


# ---------------- Gaming: biblioteca de juegos instalados ----------------
# Solo LEE lo que cada launcher (Steam/Epic/GOG) ya tiene guardado en su
# propio registro/carpetas — no se inventa nada, no se instala nada.

def _tamano_carpeta_con_presupuesto(ruta, limite_tiempo):
    """Suma tamaños de archivos con presupuesto de tiempo compartido — las
    carpetas de juegos pueden ser enormes (50-100+ GB), así que se corta
    si se acaba el tiempo en vez de tardar minutos por un solo juego."""
    total = 0
    try:
        for carpeta_actual, _sub, archivos in os.walk(ruta, onerror=lambda e: None):
            if time.time() > limite_tiempo:
                break
            for a in archivos:
                try:
                    total += os.path.getsize(os.path.join(carpeta_actual, a))
                except OSError:
                    continue
    except Exception:
        pass
    return total


def detectar_juegos_instalados(calcular_tamano=True, presupuesto_seg=20):
    """
    Detecta juegos instalados de Steam, Epic Games y GOG. El tamaño es
    aproximado y comparte un presupuesto de tiempo entre todos los juegos
    (por defecto 20s en total) — en bibliotecas grandes, los últimos
    juegos pueden quedar sin tamaño calculado en vez de tardar minutos.
    """
    if not IS_WINDOWS:
        return []
    juegos = []
    limite_tiempo = time.time() + presupuesto_seg

    def _tamano_si_hay_tiempo(ruta):
        if calcular_tamano and time.time() < limite_tiempo:
            return _tamano_carpeta_con_presupuesto(ruta, limite_tiempo)
        return None

    # ---- Steam ----
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        steam_path = steam_path.replace("/", os.sep)
        bibliotecas = {steam_path}
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf_path):
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                contenido = f.read()
            for ruta_encontrada in re.findall(r'"path"\s*"([^"]+)"', contenido):
                bibliotecas.add(ruta_encontrada.replace("\\\\", "\\"))
        for biblioteca in bibliotecas:
            carpeta_common = os.path.join(biblioteca, "steamapps", "common")
            if not os.path.isdir(carpeta_common):
                continue
            with os.scandir(carpeta_common) as it:
                for entrada in it:
                    if entrada.is_dir(follow_symlinks=False):
                        juegos.append({"nombre": entrada.name, "plataforma": "Steam",
                                       "ruta": entrada.path, "bytes": _tamano_si_hay_tiempo(entrada.path)})
    except Exception:
        pass

    # ---- Epic Games ----
    try:
        for base in (r"C:\Program Files\Epic Games", r"C:\Program Files (x86)\Epic Games"):
            if not os.path.isdir(base):
                continue
            with os.scandir(base) as it:
                for entrada in it:
                    if entrada.is_dir(follow_symlinks=False) and entrada.name.lower() != "launcher":
                        juegos.append({"nombre": entrada.name, "plataforma": "Epic Games",
                                       "ruta": entrada.path, "bytes": _tamano_si_hay_tiempo(entrada.path)})
    except Exception:
        pass

    # ---- GOG ----
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games") as key:
            i = 0
            while True:
                try:
                    subclave = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(key, subclave) as gamekey:
                        nombre, _ = winreg.QueryValueEx(gamekey, "gameName")
                        ruta, _ = winreg.QueryValueEx(gamekey, "path")
                        if os.path.isdir(ruta):
                            juegos.append({"nombre": nombre, "plataforma": "GOG",
                                           "ruta": ruta, "bytes": _tamano_si_hay_tiempo(ruta)})
                except Exception:
                    continue
    except Exception:
        pass

    juegos.sort(key=lambda j: j["bytes"] or 0, reverse=True)
    return juegos


# ---------------- Gaming: biblioteca de juegos instalados ----------------
# Solo lectura de los propios archivos de manifiesto de cada plataforma
# (Steam/Epic/GOG) — nada de inyección, nada de tocar el juego en sí.
# El tamaño en disco solo se calcula para Steam (lo trae listo en su
# manifiesto); para Epic/GOG recorrer la carpeta completa para sumar
# tamaño sería lento en juegos grandes, así que se deja en "N/D" a
# propósito, para no romper la filosofía de "no consumir rendimiento".

def _juegos_steam():
    if not IS_WINDOWS:
        return []
    import winreg
    resultados = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
    except Exception:
        return []

    carpetas = [steam_path]
    try:
        with open(os.path.join(steam_path, "steamapps", "libraryfolders.vdf"),
                  "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
        for m in re.finditer(r'"path"\s*"([^"]+)"', contenido):
            ruta = m.group(1).replace("\\\\", "\\")
            if ruta not in carpetas:
                carpetas.append(ruta)
    except Exception:
        pass

    for carpeta in carpetas:
        steamapps = os.path.join(carpeta, "steamapps")
        if not os.path.isdir(steamapps):
            continue
        try:
            for archivo in os.listdir(steamapps):
                if not (archivo.startswith("appmanifest_") and archivo.endswith(".acf")):
                    continue
                try:
                    with open(os.path.join(steamapps, archivo), "r", encoding="utf-8", errors="ignore") as f:
                        contenido = f.read()
                    nombre_m = re.search(r'"name"\s*"([^"]+)"', contenido)
                    tamano_m = re.search(r'"SizeOnDisk"\s*"(\d+)"', contenido)
                    if nombre_m:
                        resultados.append({
                            "nombre": nombre_m.group(1),
                            "plataforma": "Steam",
                            "bytes": int(tamano_m.group(1)) if tamano_m else None,
                        })
                except Exception:
                    continue
        except Exception:
            continue
    return resultados


def _juegos_epic():
    if not IS_WINDOWS:
        return []
    carpeta = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
                            "Epic", "EpicGamesLauncher", "Data", "Manifests")
    if not os.path.isdir(carpeta):
        return []
    resultados = []
    try:
        for archivo in os.listdir(carpeta):
            if not archivo.lower().endswith(".item"):
                continue
            try:
                with open(os.path.join(carpeta, archivo), "r", encoding="utf-8", errors="ignore") as f:
                    datos = json.load(f)
                nombre = datos.get("DisplayName")
                if nombre:
                    resultados.append({"nombre": nombre, "plataforma": "Epic Games", "bytes": None})
            except Exception:
                continue
    except Exception:
        pass
    return resultados


def _juegos_gog():
    if not IS_WINDOWS:
        return []
    import winreg
    resultados = []
    for ruta in (r"SOFTWARE\WOW6432Node\GOG.com\Games", r"SOFTWARE\GOG.com\Games"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta) as key_padre:
                i = 0
                while True:
                    try:
                        subclave = winreg.EnumKey(key_padre, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(key_padre, subclave) as sub:
                            nombre = winreg.QueryValueEx(sub, "gameName")[0]
                            resultados.append({"nombre": nombre, "plataforma": "GOG", "bytes": None})
                    except Exception:
                        continue
        except Exception:
            continue
    return resultados


def listar_juegos_instalados():
    """Detecta juegos instalados de Steam/Epic/GOG leyendo sus propios
    manifiestos — solo informativo. Si una plataforma no está instalada,
    simplemente no aparece nada de ella (no es un error)."""
    juegos = []
    for fn in (_juegos_steam, _juegos_epic, _juegos_gog):
        try:
            juegos += fn()
        except Exception:
            continue
    juegos.sort(key=lambda j: (j["bytes"] is None, -(j["bytes"] or 0)))
    return juegos


# ---------------- Audio: dispositivos, prueba de sonido y accesos oficiales ----------------
# No se implementa grabación de micrófono ni medidor de nivel en vivo —
# eso requeriría una librería nueva (pyaudio/sounddevice, no están en el
# proyecto) solo para reinventar algo que Windows ya hace bien y de forma
# segura. En vez de eso, se usa el mismo patrón que FPS/Enfoque asistido:
# atajos directos a las pruebas oficiales de Windows.

def listar_dispositivos_audio():
    """Dispositivos de audio (reproducción y grabación) — informativo,
    vía CIM. No cambia el dispositivo predeterminado (Windows no expone
    eso por un cmdlet oficial sin herramientas de terceros)."""
    if not IS_WINDOWS:
        return []
    script = ("Get-CimInstance -ClassName Win32_SoundDevice | "
              "Select-Object Name, Status | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
        return [{"nombre": d.get("Name"), "estado": d.get("Status")} for d in datos if d.get("Name")]
    except Exception:
        return []


def generar_wav_tono(canal="ambos", notas=((660, 260), (880, 340)), volumen=0.5,
                      hz_muestreo=44100):
    """Sintetiza en memoria un WAV corto (dos notas, tipo timbre) y devuelve
    sus bytes, listos para winsound.PlaySound con SND_MEMORY.

    Se genera aquí en vez de traer un archivo .wav suelto porque así no hay
    nada que empaquetar ni que se pueda perder al compilar con PyInstaller
    —el tono existe siempre, aunque falte la carpeta assets—, y porque
    permite mandar la señal por un solo canal para probar cada bocina por
    separado.

    canal: "ambos", "izquierdo" o "derecho".
    """
    import io
    import math
    import struct
    import wave

    canal = canal if canal in ("ambos", "izquierdo", "derecho") else "ambos"
    volumen = max(0.05, min(1.0, float(volumen)))
    muestras = []
    for frecuencia, duracion_ms in notas:
        total = int(hz_muestreo * duracion_ms / 1000)
        # Rampa de entrada y de salida: sin ella, cortar la onda a media
        # oscilación produce un "clic" seco al principio y al final.
        rampa = max(1, int(hz_muestreo * 0.008))
        for i in range(total):
            atenuacion = 1.0
            if i < rampa:
                atenuacion = i / rampa
            elif i > total - rampa:
                atenuacion = max(0.0, (total - i) / rampa)
            valor = math.sin(2 * math.pi * frecuencia * i / hz_muestreo)
            muestras.append(int(valor * atenuacion * volumen * 32767))

    izquierdo = canal in ("ambos", "izquierdo")
    derecho = canal in ("ambos", "derecho")
    marco = struct.Struct("<hh")
    cuerpo = b"".join(marco.pack(m if izquierdo else 0, m if derecho else 0)
                      for m in muestras)

    memoria = io.BytesIO()
    with wave.open(memoria, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(hz_muestreo)
        w.writeframes(cuerpo)
    return memoria.getvalue()


def reproducir_sonido_prueba(canal="ambos"):
    """
    Reproduce un tono de prueba para confirmar que la salida de audio
    funciona. Devuelve (exito, comando_para_el_registro).

    Historia de dos bugs en el mismo sitio:

      1. La primera versión usaba winsound.PlaySound("SystemAsterisk"),
         que depende de que el TEMA DE SONIDOS de Windows tenga un archivo
         asignado a ese evento. Con el esquema en "Sin sonidos" —algo
         común— la llamada "funcionaba" sin ningún error y no sonaba nada.

      2. El arreglo fue winsound.Beep(), pero resultó ser peor: Beep() NO
         pasa por la tarjeta de sonido. Llama a la API del kernel, que usa
         el generador de tonos del sistema (beep.sys). En bastantes
         portátiles modernos ese controlador viene desactivado de fábrica,
         así que otra vez: ningún error, ningún sonido. Y aunque hubiera
         sonado, no habría probado NADA de lo que interesa aquí — ni el
         dispositivo de salida, ni el volumen, ni las bocinas.

    Esta versión sintetiza un WAV en memoria y lo reproduce por la ruta de
    audio normal de Windows: el mismo camino que usa cualquier otra
    aplicación. Si suena, el audio funciona de verdad; si no suena, el
    problema está en el volumen, en el dispositivo elegido o en las
    bocinas — y la ventana de la app ahora ayuda a mirar justo eso.
    """
    comando = f"winsound.PlaySound(<tono WAV sintetizado: {canal}>, SND_MEMORY)"
    if not IS_WINDOWS:
        return False, comando
    try:
        import winsound
        datos = generar_wav_tono(canal=canal)
        # Sin SND_ASYNC a propósito: la llamada vuelve cuando el tono ya
        # terminó, que es lo que necesita la ventana para preguntar
        # "¿lo escuchaste?" en el momento correcto y no antes de que empiece.
        winsound.PlaySound(datos, winsound.SND_MEMORY)
        return True, comando
    except Exception:
        # Último recurso: si la síntesis o la reproducción fallan, al menos
        # intentar el pitido del kernel antes de darse por vencido.
        try:
            import winsound
            winsound.Beep(880, 300)
            return True, "winsound.Beep(880, 300) [respaldo]"
        except Exception:
            return False, comando


def abrir_prueba_microfono():
    """Abre la configuración de Sonido de Windows, directo en el panel de
    Entrada, que ya trae su propio medidor de nivel en vivo para probar
    el micrófono — no reinventamos esto con una librería nueva."""
    comando = "ms-settings:sound (panel de Entrada)"
    if not IS_WINDOWS:
        return False, comando
    try:
        os.startfile("ms-settings:sound")
        return True, comando
    except Exception:
        return False, comando


def abrir_mezclador_volumen():
    comando = "sndvol.exe"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["sndvol.exe"])
        return True, comando
    except Exception:
        return False, comando


# ---------------- Buscar actualizaciones de TechClean ----------------
# Usa la API pública de GitHub Releases — gratis, sin necesitar un
# servidor propio. Requiere que el desarrollador publique cada versión
# como un "Release" en un repositorio de GitHub (ver README para el paso
# a paso). Mientras REPO_ACTUALIZACIONES no apunte a un repo real, esta
# función simplemente no encuentra nada — no rompe nada, solo no hace nada.

REPO_ACTUALIZACIONES = "Hades3715/TechCleanPro"


# ---------------- Carpetas conocidas de Windows ----------------
# BUG real encontrado en el equipo del desarrollador: el codigo armaba la
# ruta del Escritorio como ~/Desktop. Con OneDrive sincronizando el
# escritorio (y con Windows en espanol) el escritorio de verdad esta en
# ~/OneDrive/Escritorio, mientras que ~/Desktop sigue existiendo VACIO.
# Resultado: el reporte se exportaba sin error, la app avisaba la ruta, y
# el usuario no encontraba nada en su escritorio. Lo mismo aplica a
# Descargas. La unica forma correcta es preguntarle a Windows.
_FOLDERID = {
    "escritorio": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "descargas": "374DE290-123F-4565-9164-39C4925E467B",
}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


def carpeta_conocida(cual, respaldos=()):
    """Ruta real de una carpeta conocida de Windows, resolviendo
    redirecciones (OneDrive) y el idioma del sistema. Devuelve "" si no se
    pudo determinar ninguna ruta existente."""
    guid_txt = _FOLDERID.get(cual)
    if IS_WINDOWS and guid_txt:
        try:
            import uuid
            u = uuid.UUID(guid_txt)
            g = _GUID(u.fields[0], u.fields[1], u.fields[2],
                      (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            ptr = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(g), 0, None, ctypes.byref(ptr)) == 0:
                ruta = ptr.value                      # copiar ANTES de liberar
                ctypes.windll.ole32.CoTaskMemFree(ptr)
                if ruta and os.path.isdir(ruta):
                    return ruta
        except Exception:
            pass
    for r in respaldos:
        if r and os.path.isdir(r):
            return r
    return ""


# ---------------- Apoyar el proyecto (donaciones) ----------------
# Ko-fi (con PayPal conectado) es la opción que sí funciona pagando a una
# cuenta en El Salvador — Buy Me a Coffee solo paga vía Stripe, que no
# incluye El Salvador en su lista de países soportados; PayPal sí lo
# incluye, y Ko-fi acepta PayPal como alternativa a Stripe.
# Mientras URL_DONACION esté vacía, el botón de la app no aparece — no
# hay nada que mostrar sin un link real.

URL_DONACION = "https://ko-fi.com/hadesdev"


def abrir_pagina_donacion():
    """Abre la página de donación configurada en el navegador. Devuelve
    (exito, comando) — False si todavía no se configuró ningún link."""
    if not URL_DONACION:
        return False, "URL_DONACION vacía"
    try:
        webbrowser.open(URL_DONACION)
        return True, f"webbrowser.open({URL_DONACION})"
    except Exception:
        return False, f"webbrowser.open({URL_DONACION})"


def _version_es_mayor(v1, v2):
    """Compara dos versiones tipo '1.2.0' — True si v1 es más nueva que v2."""
    def _partes(v):
        try:
            return [int(p) for p in v.strip().split(".")]
        except ValueError:
            return [0]
    a, b = _partes(v1), _partes(v2)
    largo = max(len(a), len(b))
    a += [0] * (largo - len(a))
    b += [0] * (largo - len(b))
    return a > b


def buscar_actualizacion_app(version_actual):
    """
    Consulta la última versión publicada en GitHub Releases. Devuelve un
    dict: {"hay_nueva": bool, "version": str o None, "url": str o None,
    "notas": str o None}. Si no hay internet, el repo no existe todavía,
    o ya estás al día, "hay_nueva" es False sin ser un error — es un
    estado normal, no algo que deba mostrarse como falla.
    """
    import urllib.request
    import json as _json
    resultado = {"hay_nueva": False, "version": None, "url": None, "notas": None}
    if REPO_ACTUALIZACIONES == "TU_USUARIO/TU_REPO":
        return resultado
    try:
        url = f"https://api.github.com/repos/{REPO_ACTUALIZACIONES}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                     "User-Agent": "TechClean"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            datos = _json.loads(resp.read().decode("utf-8"))
        version_remota = (datos.get("tag_name") or "").lstrip("vV")
        if not version_remota:
            return resultado
        if _version_es_mayor(version_remota, version_actual):
            resultado["hay_nueva"] = True
            resultado["version"] = version_remota
            resultado["url"] = datos.get("html_url") or f"https://github.com/{REPO_ACTUALIZACIONES}/releases/latest"
            resultado["notas"] = (datos.get("body") or "").strip()[:500]
        return resultado
    except Exception:
        return resultado


# ---------------- Reparar (más profundo): Explorador, efectos visuales, indexación ----------------

def reiniciar_explorador():
    """
    Reinicia el proceso explorer.exe (barra de tareas, iconos de
    escritorio, ventanas del Explorador de archivos) — arregla iconos que
    no cargan, el menú Inicio que deja de responder, o la barra de tareas
    congelada, sin tener que reiniciar todo el equipo. Se ve un parpadeo
    de un par de segundos mientras se reinicia — es normal.
    """
    comando = "taskkill /f /im explorer.exe && start explorer.exe"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        time.sleep(1)
        subprocess.Popen(["explorer.exe"])
        return True, comando
    except Exception:
        return False, comando


def abrir_opciones_rendimiento_visual():
    """
    Abre el diálogo oficial de Windows "Opciones de rendimiento" en la
    pestaña de Efectos visuales — con un clic en "Ajustar para obtener el
    mejor rendimiento", Windows apaga animaciones, transparencias y
    sombras de una vez. Deliberadamente NO se hace por registro
    directamente: son varias claves distintas, y Windows no siempre las
    aplica en caliente sin pasar por este mismo diálogo — más confiable
    dejar que Windows lo haga él mismo. En equipos con poca RAM o una GPU
    integrada débil, esto libera recursos reales que se van en dibujar la
    interfaz en vez de en lo que estás haciendo.
    """
    comando = "SystemPropertiesPerformance.exe"
    if not IS_WINDOWS:
        return False, comando
    try:
        subprocess.Popen(["SystemPropertiesPerformance.exe"])
        return True, comando
    except Exception:
        return False, comando


def obtener_estado_indexacion():
    """True si el servicio de indexación de búsqueda (WSearch) está
    corriendo, False si está detenido, None si no se pudo leer."""
    if not IS_WINDOWS:
        return None
    try:
        r = subprocess.run(["sc", "query", "WSearch"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        salida = r.stdout or ""
        if "RUNNING" in salida:
            return True
        if "STOPPED" in salida:
            return False
        return None
    except Exception:
        return None


def pausar_indexacion_busqueda(pausar=True):
    """
    Detiene (o reinicia) el servicio de indexación de búsqueda de Windows
    (WSearch). En equipos con poca RAM o disco mecánico, este servicio
    compite en segundo plano por recursos de forma constante — pausarlo
    libera algo de margen, a cambio de que buscar por CONTENIDO de
    archivos sea más lento (buscar por nombre de archivo sigue igual).
    Reversible en cualquier momento con el mismo botón.
    """
    comando = f'{"net stop" if pausar else "net start"} WSearch'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["net", "stop" if pausar else "start", "WSearch"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Optimizar (más profundo): qué está usando la RAM ahora mismo ----------------

def listar_procesos_por_ram(limite=15):
    """
    Los procesos que más RAM están usando en este momento, de mayor a
    menor — para saber exactamente qué está apretando la memoria en un
    equipo justo de recursos, en vez de solo saber "la RAM está al 90%"
    sin más detalle. Informativo; terminar un proceso puntual es una
    función aparte (terminar_proceso), con confirmación siempre de por medio.
    """
    procesos = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            info = p.info
            mem_info = info.get('memory_info')
            if not mem_info:
                continue
            procesos.append({"pid": info['pid'], "nombre": info['name'] or "?", "bytes_ram": mem_info.rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    procesos.sort(key=lambda p: p["bytes_ram"], reverse=True)
    return procesos[:limite]


# ---------------- Seguridad al terminar procesos ----------------
# Clasificación honesta, no una promesa de "esto es 100% seguro": los
# nombres de procesos técnicos no le dicen nada a alguien que no trabaja
# con esto todos los días, así que antes de dejar terminar cualquier cosa
# se explica qué es y qué pasaría — y para los realmente críticos, ni
# siquiera se permite el intento, porque no hay ningún motivo legítimo
# para cerrarlos desde aquí y las consecuencias son inmediatas y graves.

PROCESOS_BLOQUEADOS = {
    "system": "riesgo_proc_system",
    "system idle process": "riesgo_proc_idle",
    "csrss.exe": "riesgo_proc_csrss",
    "wininit.exe": "riesgo_proc_wininit",
    "winlogon.exe": "riesgo_proc_winlogon",
    "services.exe": "riesgo_proc_services",
    "lsass.exe": "riesgo_proc_lsass",
    "smss.exe": "riesgo_proc_smss",
    "svchost.exe": "riesgo_proc_svchost",
    "memory compression": "riesgo_proc_memcomp",
}

PROCESOS_RECUPERABLES = {
    "explorer.exe": "riesgo_proc_explorer",
    "dwm.exe": "riesgo_proc_dwm",
}


def evaluar_riesgo_proceso(nombre):
    """
    Devuelve ('bloqueado', motivo), ('recuperable', motivo) o ('normal', None)
    según qué tan crítico es un proceso del sistema — para que la interfaz
    decida si impedir el cierre por completo, avisar con más fuerza, o
    solo pedir la confirmación normal.
    """
    clave = (nombre or "").strip().lower()
    if clave in PROCESOS_BLOQUEADOS:
        return "bloqueado", t(PROCESOS_BLOQUEADOS[clave])
    if clave in PROCESOS_RECUPERABLES:
        return "recuperable", t(PROCESOS_RECUPERABLES[clave])
    return "normal", None


def listar_procesos_por_cpu(limite=15, intervalo=0.6):
    """
    Los procesos que más CPU están usando, medido en una ventana corta de
    tiempo — a diferencia de la RAM (que se puede leer de un vistazo), el
    uso de CPU de un proceso solo tiene sentido como una TASA (cuánto
    trabajó en cierto tiempo), así que psutil necesita "cebar" cada
    proceso primero y medir la diferencia después. Por eso esta función
    tarda un poco más que la de RAM (el intervalo completo, medio segundo
    por defecto) — es esperado, no un error.
    """
    objetos = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            p.cpu_percent(interval=None)  # primera llamada "ceba" la medición, el valor se descarta
            objetos.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(intervalo)

    procesos = []
    nucleos = psutil.cpu_count(logical=True) or 1
    for p in objetos:
        try:
            # cpu_percent() de psutil puede superar 100% en equipos con
            # varios núcleos (100% = un núcleo completo) — se divide entre
            # el número de núcleos para que el número se lea como "% del
            # total del equipo", más intuitivo para quien no es técnico.
            cpu_total = p.cpu_percent(interval=None) / nucleos
            procesos.append({"pid": p.pid, "nombre": p.name() or "?", "cpu_pct": cpu_total})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procesos.sort(key=lambda x: x["cpu_pct"], reverse=True)
    return procesos[:limite]


def terminar_proceso(pid):
    """
    Termina un proceso puntual por su PID. Antes de esto, la interfaz ya
    revisó con evaluar_riesgo_proceso() si es un proceso crítico del
    sistema — esta función confía en que esa revisión ya se hizo y no
    vuelve a repetirla, para no bloquear por duplicado un cierre ya
    aprobado por el usuario.
    """
    try:
        proceso = psutil.Process(pid)
        nombre = proceso.name()
        proceso.terminate()
        return True, nombre
    except psutil.NoSuchProcess:
        return False, t("optmod_proc_no_existe")
    except psutil.AccessDenied:
        return False, t("optmod_permiso_denegado")
    except Exception as e:
        return False, str(e)


# ---------------- Aplicaciones abiertas (ventanas, no procesos de fondo) ----------------
# Distinto de "terminar proceso": esto son programas con los que puedes
# interactuar ahora mismo (lo que verías con Alt+Tab), y se cierran de
# forma NORMAL — el mismo mensaje que Windows manda cuando le das clic a
# la "X" de una ventana (WM_CLOSE) — no un cierre forzado. Si el programa
# tiene cambios sin guardar, va a preguntar igual que si lo cerraras tú.

def listar_ventanas_abiertas():
    """Ventanas de aplicaciones visibles ahora mismo, con su título,
    proceso y PID. Excluye la propia ventana de TechClean y la
    ventana de fondo del Explorador (Alt+Tab tampoco las muestra)."""
    if not IS_WINDOWS:
        return []

    ventanas = []
    propio_pid = os.getpid()
    shell_hwnd = ctypes.windll.user32.GetShellWindow()

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        if hwnd == shell_hwnd:
            return True
        largo = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if largo == 0:
            return True
        buffer = ctypes.create_unicode_buffer(largo + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, largo + 1)
        titulo = buffer.value.strip()
        if not titulo:
            return True
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == propio_pid:
            return True
        nombre_proceso = "?"
        try:
            nombre_proceso = psutil.Process(pid.value).name()
        except Exception:
            pass
        ventanas.append({"hwnd": int(hwnd), "titulo": titulo, "pid": pid.value, "proceso": nombre_proceso})
        return True

    try:
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        return []
    return ventanas


def cerrar_ventana(hwnd):
    """
    Envía una solicitud de cierre NORMAL a la ventana — el mismo mensaje
    (WM_CLOSE) que Windows manda cuando le das clic a la "X". No es un
    cierre forzado: si el programa tiene cambios sin guardar, va a
    preguntar igual que si lo cerraras tú mismo. Puede tardar un
    momento en desaparecer si el programa necesita hacer algo antes.
    """
    if not IS_WINDOWS:
        return False
    try:
        WM_CLOSE = 0x0010
        ctypes.windll.user32.PostMessageW(ctypes.wintypes.HWND(hwnd), WM_CLOSE, 0, 0)
        return True
    except Exception:
        return False




# ---------------- Reducir animaciones sin abrir el diálogo (API oficial) ----------------
# SystemParametersInfo es la API real de Windows para esto — el propio
# blog de ingeniería de Microsoft ("The Old New Thing") explica que la
# clave de registro del diálogo es "solo para mostrar": el cambio real
# pasa por esta función. Documentada y estable desde Windows 2000.
#
# Solo se implementan las DOS acciones cuyo valor hexadecimal y forma de
# llamada pude confirmar con certeza en documentación oficial —
# deliberadamente no se adivinan las demás (SPI_SETUIEFFECTS, etc.):
# equivocarse en un valor de estos podría terminar cambiando un parámetro
# de sistema distinto al que se quería. Para el resto de efectos
# visuales, sigue disponible el diálogo oficial completo
# (abrir_opciones_rendimiento_visual).

SPI_SETDRAGFULLWINDOWS = 0x0025
SPI_SETANIMATION = 0x0049
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


class _AnimationInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]


def reducir_animaciones_ahora(activar_reduccion=True):
    """
    Aplica en vivo, sin abrir ningún diálogo, dos de los efectos visuales
    que más se notan en equipos con poca RAM o GPU integrada débil:
    - Arrastrar solo el contorno de la ventana (no todo el contenido)
    - Sin animación al minimizar/restaurar ventanas
    activar_reduccion=False vuelve a encenderlas.
    """
    comando = "SystemParametersInfo(SPI_SETDRAGFULLWINDOWS / SPI_SETANIMATION)"
    if not IS_WINDOWS:
        return False, comando
    try:
        flags = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        valor_arrastre = 0 if activar_reduccion else 1
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDRAGFULLWINDOWS, valor_arrastre, None, flags)

        info = _AnimationInfo()
        info.cbSize = ctypes.sizeof(_AnimationInfo)
        info.iMinAnimate = 0 if activar_reduccion else 1
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETANIMATION, ctypes.sizeof(_AnimationInfo),
                                                     ctypes.byref(info), flags)
        return True, comando
    except Exception:
        return False, comando


# ---------------- Usuarios del equipo (el actual y los demás) ----------------

def listar_usuarios_sistema():
    """
    Cuentas de usuario LOCALES de este equipo — no solo la que tienes
    iniciada ahora, todas las que existen. Útil en equipos compartidos
    (familia, laboratorio) para saber quién más tiene acceso. Solo lectura.
    Usa el SID universal del grupo Administradores (S-1-5-32-544) para
    saber quién es admin, en vez del nombre del grupo — ese cambia según
    el idioma de Windows ("Administradores" vs "Administrators"), el SID no.
    """
    if not IS_WINDOWS:
        return []
    try:
        script = "Get-LocalUser | Select-Object Name, Enabled, Description | ConvertTo-Json -Compress"
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        datos = json.loads(r.stdout) if r.stdout else []
        if isinstance(datos, dict):
            datos = [datos]
    except Exception:
        return []

    admins = set()
    try:
        script_admins = ("(Get-LocalGroupMember -SID 'S-1-5-32-544' -ErrorAction SilentlyContinue) "
                          "| Select-Object -ExpandProperty Name")
        r2 = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script_admins],
                             capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        for linea in (r2.stdout or "").splitlines():
            linea = linea.strip()
            if "\\" in linea:
                linea = linea.split("\\")[-1]
            if linea:
                admins.add(linea.lower())
    except Exception:
        pass

    usuario_actual = os.environ.get("USERNAME", "").lower()
    resultado = []
    for d in datos:
        nombre = d.get("Name")
        if not nombre:
            continue
        resultado.append({
            "nombre": nombre,
            "habilitada": bool(d.get("Enabled")),
            "descripcion": d.get("Description") or "",
            "es_actual": nombre.lower() == usuario_actual,
            "es_admin": nombre.lower() in admins,
        })
    resultado.sort(key=lambda u: (not u["es_actual"], u["nombre"].lower()))
    return resultado


def escanear_hardware_nuevo():
    """
    pnputil /scan-devices — el mismo botón "Buscar cambios de hardware"
    del Administrador de dispositivos. A veces basta esto para que
    Windows detecte e instale solo un dispositivo que antes no había
    reconocido (típico justo después de una instalación limpia).
    """
    comando = "pnputil /scan-devices"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["pnputil", "/scan-devices"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Inicio rápido de Windows ----------------
# HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power\HiberbootEnabled
# — clave oficial y bien documentada (a diferencia de Enfoque Asistido).
# Ojo: esto NO afecta reinicios (un "Reiniciar" siempre hace arranque
# completo, con o sin esto activado) — solo afecta APAGAR y volver a
# encender. Se agrega porque puede interferir con que algunas
# actualizaciones de drivers/Windows Update terminen de instalarse bien
# (documentado por Microsoft), no porque resuelva lo de F12/F9 al
# reiniciar — esa parte vive en el firmware (BIOS), fuera del alcance de
# cualquier app de Windows.

def obtener_estado_inicio_rapido():
    """True si el Inicio rápido está activado, False si no, None si no
    se pudo leer (ej. equipo de escritorio sin hibernación disponible)."""
    if not IS_WINDOWS:
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SYSTEM\CurrentControlSet\Control\Session Manager\Power") as key:
            valor = winreg.QueryValueEx(key, "HiberbootEnabled")[0]
        return bool(valor)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def set_inicio_rapido(activar):
    """Activa o desactiva el Inicio rápido de Windows (requiere admin)."""
    comando = f'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power" /v HiberbootEnabled /t REG_DWORD /d {1 if activar else 0} /f'
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(
            ["reg", "add", r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power",
             "/v", "HiberbootEnabled", "/t", "REG_DWORD", "/d", "1" if activar else "0", "/f"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0, comando
    except Exception:
        return False, comando
