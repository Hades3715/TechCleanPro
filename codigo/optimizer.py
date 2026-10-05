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


# ---------------------------------------------------------------------------
# Liberación de memoria
#
# Hasta la 1.5.0 esto era SOLO un bucle de EmptyWorkingSet proceso por
# proceso, y por eso se quedaba muy por detrás de Mem Reduct con la misma
# RAM. Tres razones, todas medibles:
#
#  1. El bucle solo llega a los procesos que OpenProcess deja abrir. Los
#     protegidos (antivirus, servicios del sistema, el propio "System") se
#     quedaban sin tocar, y suelen ser de los que más memoria tienen.
#  2. La caché de archivos del sistema vive en el working set del SISTEMA,
#     no en el de ningún proceso: ningún EmptyWorkingSet la toca.
#  3. Las páginas MODIFICADAS (datos que todavía hay que escribir a disco)
#     cuentan como memoria en uso. Mientras nadie las escriba, no se liberan.
#
# Mem Reduct resuelve las tres con NtSetSystemInformation, la misma llamada
# que usa RAMMap de Sysinternals. Es una API nativa sin documentar en MSDN,
# pero estable desde Windows Vista y con las constantes publicadas en las
# cabeceras de System Informer (phnt). La caché de archivos sí tiene API
# documentada (SetSystemFileCacheSize) y se usa esa.
#
# La medida que se informa es la memoria DISPONIBLE antes y después
# (GlobalMemoryStatusEx, lo mismo que mira el Administrador de tareas y
# Mem Reduct): las páginas que pasan a la lista "en espera" ya cuentan como
# disponibles, así que vaciar esa lista NO sube ese número. Por eso el
# nivel profundo informa la caché en espera aparte.
# ---------------------------------------------------------------------------

_CLASE_LISTAS_MEMORIA = 80        # SystemMemoryListInformation
_CLASE_COMBINAR_MEMORIA = 130     # SystemCombinePhysicalMemoryInformation (Windows 10+)
_ORDEN_VACIAR_WORKING_SETS = 2    # MemoryEmptyWorkingSets — todos los procesos, protegidos incluidos
_ORDEN_ESCRIBIR_MODIFICADA = 3    # MemoryFlushModifiedList
_ORDEN_PURGAR_ESPERA = 4          # MemoryPurgeStandbyList
_ORDEN_PURGAR_ESPERA_BAJA = 5     # MemoryPurgeLowPriorityStandbyList

if IS_WINDOWS:
    class _ListasMemoria(ctypes.Structure):
        # SYSTEM_MEMORY_LIST_INFORMATION. Todo en PÁGINAS, no en bytes.
        _fields_ = [
            ("ZeroPageCount", ctypes.c_size_t),
            ("FreePageCount", ctypes.c_size_t),
            ("ModifiedPageCount", ctypes.c_size_t),
            ("ModifiedNoWritePageCount", ctypes.c_size_t),
            ("BadPageCount", ctypes.c_size_t),
            ("PageCountByPriority", ctypes.c_size_t * 8),
            ("RepurposedPagesByPriority", ctypes.c_size_t * 8),
            ("ModifiedPageCountPageFile", ctypes.c_size_t),
        ]

    class _CombinarMemoria(ctypes.Structure):
        # MEMORY_COMBINE_INFORMATION_EX
        _fields_ = [
            ("Handle", ctypes.c_void_p),
            ("PagesCombined", ctypes.c_size_t),
            ("Flags", ctypes.c_ulong),
        ]

    class _LUID(ctypes.Structure):
        _fields_ = [("LowPart", ctypes.wintypes.DWORD), ("HighPart", ctypes.wintypes.LONG)]

    class _TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", ctypes.wintypes.DWORD),
                    ("Luid", _LUID),
                    ("Attributes", ctypes.wintypes.DWORD)]


def _tamano_pagina():
    try:
        import mmap
        return mmap.PAGESIZE
    except Exception:
        return 4096


def _activar_privilegio(nombre):
    """Activa un privilegio en el token de este proceso. Ser administrador
    no basta: el privilegio viene APAGADO en el token y hay que encenderlo.
    Devuelve True solo si de verdad quedó activo.

    Ojo con AdjustTokenPrivileges: devuelve éxito aunque no haya podido
    asignar el privilegio, y avisa solo por GetLastError (1300,
    ERROR_NOT_ALL_ASSIGNED). Mirar solo lo que devuelve es suponer."""
    if not IS_WINDOWS:
        return False
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        HANDLE = ctypes.wintypes.HANDLE
        kernel32.GetCurrentProcess.restype = HANDLE
        kernel32.CloseHandle.argtypes = [HANDLE]
        advapi32.OpenProcessToken.argtypes = [HANDLE, ctypes.wintypes.DWORD, ctypes.POINTER(HANDLE)]
        advapi32.LookupPrivilegeValueW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR,
                                                   ctypes.POINTER(_LUID)]
        advapi32.AdjustTokenPrivileges.argtypes = [HANDLE, ctypes.wintypes.BOOL,
                                                   ctypes.POINTER(_TOKEN_PRIVILEGES),
                                                   ctypes.wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]

        TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY, SE_PRIVILEGE_ENABLED = 0x20, 0x08, 0x02
        token = HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                         TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)):
            return False
        try:
            luid = _LUID()
            if not advapi32.LookupPrivilegeValueW(None, nombre, ctypes.byref(luid)):
                return False
            tp = _TOKEN_PRIVILEGES(1, luid, SE_PRIVILEGE_ENABLED)
            ctypes.set_last_error(0)
            if not advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None):
                return False
            return ctypes.get_last_error() == 0
        finally:
            kernel32.CloseHandle(token)
    except Exception:
        return False


def _nt_set(clase, dato):
    """NtSetSystemInformation. Devuelve el NTSTATUS (0 = éxito)."""
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtSetSystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long
    return ntdll.NtSetSystemInformation(clase, ctypes.byref(dato), ctypes.sizeof(dato))


def _orden_listas(orden):
    try:
        return _nt_set(_CLASE_LISTAS_MEMORIA, ctypes.c_ulong(orden)) == 0
    except Exception:
        return False


def estado_listas_memoria():
    """Cuánta memoria hay en cada lista de Windows, en bytes:
    {"en_espera", "modificada", "libre"}. None si no se puede leer
    (hace falta ser administrador).

    Comprobación cruzada que usa prueba_memoria.py: libre + en espera debe
    parecerse a la memoria DISPONIBLE que da GlobalMemoryStatusEx. Si la
    estructura estuviera mal declarada, los números saldrían absurdos."""
    if not IS_WINDOWS or not _activar_privilegio("SeProfileSingleProcessPrivilege"):
        return None
    try:
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p,
                                                   ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        ntdll.NtQuerySystemInformation.restype = ctypes.c_long
        info = _ListasMemoria()
        largo = ctypes.c_ulong(0)
        if ntdll.NtQuerySystemInformation(_CLASE_LISTAS_MEMORIA, ctypes.byref(info),
                                          ctypes.sizeof(info), ctypes.byref(largo)) != 0:
            return None
    except Exception:
        return None
    pagina = _tamano_pagina()
    return {
        "en_espera": sum(info.PageCountByPriority) * pagina,
        "modificada": info.ModifiedPageCount * pagina,
        "libre": (info.ZeroPageCount + info.FreePageCount) * pagina,
    }


def _vaciar_working_sets_por_proceso(exclude_pids):
    """El método de siempre, proceso por proceso. Sigue haciendo falta para
    cuando hay que EXCLUIR un proceso (el juego del Modo Juego): la orden de
    sistema vacía todos a la vez, sin excepciones."""
    afectados = 0
    psapi = ctypes.WinDLL("psapi")
    kernel32 = ctypes.WinDLL("kernel32")
    HANDLE = ctypes.wintypes.HANDLE
    kernel32.OpenProcess.restype = HANDLE
    kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [HANDLE]
    psapi.EmptyWorkingSet.argtypes = [HANDLE]
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    for pid in psutil.pids():
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
    return afectados


def liberar_memoria(nivel="normal", exclude_pids=None):
    """
    Libera RAM como lo hace Mem Reduct. Dos niveles:

    - "normal": vacía los working sets de TODOS los procesos (protegidos
      incluidos), la caché de archivos del sistema, y escribe a disco la
      lista modificada para que esas páginas pasen a disponibles. Seguro
      para usar a menudo; es lo que hace el autopiloto.
    - "profunda": además vacía la lista EN ESPERA (la caché de lo que se
      leyó de disco) y combina páginas idénticas. Deja más memoria libre de
      verdad, pero los programas que se abran justo después tardan algo más
      la primera vez: Windows vuelve a llenar esa caché sobre la marcha. Por
      eso solo se hace cuando lo pide el usuario, nunca en automático.

    exclude_pids: si hay procesos que NO tocar (el juego del Modo Juego),
    se usa solo el método proceso por proceso y nada de órdenes de sistema:
    escribir la lista modificada a disco en mitad de una partida puede dar
    un tirón de disco justo cuando se quiere evitar.

    Nunca lanza. Devuelve un diccionario con lo medido y con qué pasos
    funcionaron de verdad (cada orden mira su NTSTATUS).
    """
    pasos = []
    comando_partes = []
    resultado = {"nivel": nivel, "liberado": 0, "procesos": 0, "pasos": pasos,
                 "completo": False, "espera_antes": None, "espera_despues": None,
                 "uso_antes": None, "uso_despues": None, "comando": ""}
    if not IS_WINDOWS:
        return resultado

    exclude_pids = set(exclude_pids or ())
    memoria = psutil.virtual_memory()
    disponible_antes = memoria.available
    resultado["uso_antes"] = memoria.percent

    if nivel == "profunda":
        listas = estado_listas_memoria()
        resultado["espera_antes"] = listas["en_espera"] if listas else None

    perfil_ok = _activar_privilegio("SeProfileSingleProcessPrivilege")
    cuota_ok = _activar_privilegio("SeIncreaseQuotaPrivilege")

    sistema_ok = False
    if not exclude_pids and perfil_ok:
        sistema_ok = _orden_listas(_ORDEN_VACIAR_WORKING_SETS)
        pasos.append(("working_sets_sistema", sistema_ok))
        if sistema_ok:
            comando_partes.append("NtSetSystemInformation(SystemMemoryListInformation, MemoryEmptyWorkingSets)")

    if sistema_ok:
        resultado["procesos"] = len(psutil.pids())
    else:
        # Sin privilegio (app abierta sin administrador) o con un proceso a
        # excluir: el bucle de siempre, que llega a lo que puede.
        resultado["procesos"] = _vaciar_working_sets_por_proceso(exclude_pids)
        pasos.append(("working_sets_procesos", resultado["procesos"] > 0))
        comando_partes.append("EmptyWorkingSet() vía psapi.dll sobre cada proceso accesible")

    if not exclude_pids:
        if cuota_ok:
            try:
                kernel32 = ctypes.WinDLL("kernel32")
                kernel32.SetSystemFileCacheSize.argtypes = [ctypes.c_size_t, ctypes.c_size_t,
                                                            ctypes.wintypes.DWORD]
                # (SIZE_T)-1 en los dos tamaños = vaciar la caché (documentado en MSDN).
                tope = ctypes.c_size_t(-1).value
                cache_ok = bool(kernel32.SetSystemFileCacheSize(tope, tope, 0))
            except Exception:
                cache_ok = False
            pasos.append(("cache_archivos", cache_ok))
            if cache_ok:
                comando_partes.append("SetSystemFileCacheSize(-1, -1, 0)")

        if perfil_ok:
            modificada_ok = _orden_listas(_ORDEN_ESCRIBIR_MODIFICADA)
            pasos.append(("lista_modificada", modificada_ok))
            if modificada_ok:
                comando_partes.append("MemoryFlushModifiedList")

            if nivel == "profunda":
                # Primero la de prioridad baja, que es la que menos se echa
                # de menos; luego el resto.
                baja_ok = _orden_listas(_ORDEN_PURGAR_ESPERA_BAJA)
                espera_ok = _orden_listas(_ORDEN_PURGAR_ESPERA)
                pasos.append(("lista_espera", baja_ok or espera_ok))
                if espera_ok:
                    comando_partes.append("MemoryPurgeStandbyList")
                elif baja_ok:
                    comando_partes.append("MemoryPurgeLowPriorityStandbyList")

                # Windows 8 y anteriores no tienen esta clase: devuelve error
                # y simplemente no se cuenta. No es un fallo de la limpieza.
                try:
                    combinar_ok = _nt_set(_CLASE_COMBINAR_MEMORIA, _CombinarMemoria()) == 0
                except Exception:
                    combinar_ok = False
                pasos.append(("combinar_paginas", combinar_ok))
                if combinar_ok:
                    comando_partes.append("SystemCombinePhysicalMemoryInformation")

    memoria = psutil.virtual_memory()
    resultado["uso_despues"] = memoria.percent
    resultado["liberado"] = max(0, memoria.available - disponible_antes)
    if nivel == "profunda":
        listas = estado_listas_memoria()
        resultado["espera_despues"] = listas["en_espera"] if listas else None
    # "Completo" = llegó a la memoria del sistema, no solo a procesos sueltos.
    resultado["completo"] = sistema_ok
    resultado["comando"] = " + ".join(comando_partes)
    return resultado


def trim_process_memory(exclude_pids=None, nivel="normal"):
    """Envoltorio con la firma de siempre, para los sitios que solo
    necesitan el número: (bytes_liberados, procesos_afectados, comando)."""
    r = liberar_memoria(nivel=nivel, exclude_pids=exclude_pids)
    return r["liberado"], r["procesos"], r["comando"]


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
    """Tamaño de una carpeta. Si se pasan carpetas intocables, no las cuenta:
    asi lo que se ESTIMA como recuperable coincide con lo que la limpieza va
    a borrar de verdad, en vez de prometer 22 MB de mas (los de la propia app
    descomprimida en %TEMP%)."""
    return _medir(path, excluir=(lambda d: _es_intocable(d, intocables)) if intocables else None)


def _carpeta_windows():
    """La carpeta de Windows de verdad. No siempre es C:/Windows: hay equipos
    con el sistema instalado en otra unidad, y ahí la ruta escrita a mano
    apuntaba a una carpeta que no existe y la limpieza no hacía nada."""
    return os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"


def estimate_reclaimable_space():
    """Calcula cuánto espacio se podría recuperar SIN borrar nada todavía."""
    candidatos = []
    temp_dir = tempfile.gettempdir()
    candidatos.append((t("optmod_temp_usuario"), temp_dir))

    if IS_WINDOWS:
        win_temp = os.path.join(_carpeta_windows(), "Temp")
        if os.path.isdir(win_temp):
            # BUG corregido: el nombre iba escrito en español a mano y en la
            # build en inglés salía "Temporales de Windows".
            candidatos.append((t("optmod_temp_windows"), win_temp))

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

    BUG corregido: recorría %TEMP% con os.walk, que en Windows SÍ entra en
    las uniones (junctions). Una unión dentro de %TEMP% apuntando a otra
    carpeta —la dejan algunos instaladores— hacía que "limpiar temporales"
    vaciara esa otra carpeta. Ahora pasa por _vaciar_contenido, que nunca
    entra en enlaces, y sigue sin tocar las carpetas _MEI (la propia app).
    """
    comando = 'del /s /q "%TEMP%\\*" y limpieza equivalente de C:\\Windows\\Temp'
    rutas = [tempfile.gettempdir()]
    win_temp = os.path.join(_carpeta_windows(), "Temp")
    if IS_WINDOWS and os.path.isdir(win_temp):
        rutas.append(win_temp)

    intocables = _carpetas_intocables()
    liberado = 0
    borrados = 0
    for ruta in rutas:
        bytes_ruta, archivos = _vaciar_contenido(ruta, excluir=lambda d: _es_intocable(d, intocables))
        liberado += bytes_ruta
        borrados += archivos
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
    """BUG corregido: no se miraba el resultado, así que la app decía
    "caché DNS limpiada ✅" aunque ipconfig hubiera fallado (pasa si hace
    falta elevación). Y sin timeout se podía quedar esperando para siempre
    si el servicio de DNS no responde."""
    comando = "ipconfig /flushdns"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        return r.returncode == 0, comando
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
    # BUG corregido: estas tres eran las UNICAS llamadas a shutdown.exe sin
    # capture_output ni CREATE_NO_WINDOW (comparar con
    # cancelar_apagado_programado, unas lineas mas abajo, que si los lleva).
    # En la app compilada con --windowed no hay consola, asi que al apagar,
    # reiniciar o entrar a la BIOS se veia asomar una ventana negra justo
    # antes de que la pantalla se fuera. Ademas no llevaban timeout.
    try:
        r = subprocess.run(["shutdown", "/r", "/fw", "/t", "5"], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


def apagar_equipo(segundos_espera=5):
    """Apaga el equipo por completo, con unos segundos de margen para cancelar."""
    comando = f"shutdown /s /t {segundos_espera}"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["shutdown", "/s", "/t", str(segundos_espera)], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


def reiniciar_equipo(segundos_espera=5):
    """Reinicio normal (no entra a BIOS), con unos segundos de margen para cancelar."""
    comando = f"shutdown /r /t {segundos_espera}"
    if not IS_WINDOWS:
        return False, comando
    try:
        r = subprocess.run(["shutdown", "/r", "/t", str(segundos_espera)], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        return r.returncode == 0, comando
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
    # "Máximo rendimiento" (Ultimate Performance) viene OCULTO en Windows:
    # hay que copiarlo de su plantilla con /duplicatescheme. Se copia con
    # un GUID fijo propio y no con uno al azar, para que pulsar el botón
    # diez veces no deje diez planes iguales en el Panel de control.
    "maximo": {"guid": "7ec1ea4c-0000-4d1a-9b5e-7ec1ea4c0001",
               "plantilla": "e9a42b02-d5df-448d-aa00-03f14749eb61",
               "palabras": ["ultimate performance", "máximo rendimiento", "rendimiento máximo"]},
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

    # Planes ocultos (Máximo rendimiento): crearlos desde su plantilla la
    # primera vez. En algunos portátiles con Modern Standby Windows no deja
    # crearlo; entonces sigue al respaldo por nombre y, si no, falla.
    plantilla = POWER_PLANS[perfil].get("plantilla")
    if plantilla:
        try:
            r = subprocess.run(["powercfg", "/duplicatescheme", plantilla, guid], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            if r.returncode == 0:
                exito, _ = activar_plan_guid(guid)
                if exito:
                    return True, f"powercfg /duplicatescheme {plantilla} {guid} + {comando}"
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

def _decodificar_salida_consola(datos):
    """sfc escribe en UTF-16 cuando su salida va a un archivo; DISM y casi
    todo lo demás, en la página de códigos OEM de la consola (cp850 en
    Windows en español). Leído todo como uno solo, el otro sale ilegible:
    letras separadas por caracteres nulos, o las tildes rotas."""
    if not datos:
        return ""
    # En UTF-16 el texto normal lleva un byte nulo en cada posición impar.
    muestra = datos[1:400:2]
    if datos.startswith(b"\xff\xfe") or (muestra and muestra.count(0) > len(muestra) * 0.4):
        return datos.decode("utf-16-le", errors="replace").lstrip("﻿")
    # Y no todas usan la misma página: pnputil escribe en la ANSI (cp1252),
    # no en la OEM, y leída como OEM "exportó" salía "export¾". Se prueban
    # las dos y gana la que deja más letras del idioma y menos símbolos raros.
    try:
        paginas = ([f"cp{ctypes.windll.kernel32.GetOEMCP()}", f"cp{ctypes.windll.kernel32.GetACP()}"]
                   if IS_WINDOWS else ["utf-8"])
    except AttributeError:
        paginas = ["utf-8"]
    buenas = set("áéíóúñüÁÉÍÓÚÑÜ¿¡àèìòùçÀÈÌÒÙÇ")
    candidatos = []
    for pagina in dict.fromkeys(paginas):
        try:
            texto = datos.decode(pagina, errors="replace")
        except LookupError:
            continue
        puntos = sum(c in buenas for c in texto) - sum(not c.isascii() and c not in buenas for c in texto)
        candidatos.append((puntos, texto))
    if not candidatos:
        return datos.decode("utf-8", errors="replace")
    return max(candidatos, key=lambda c: c[0])[1]


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
    # BUG corregido: la salida iba a un PIPE que no se leía hasta el final.
    # El búfer de una tubería en Windows ronda los 64 KB; si el comando
    # escribe más (DISM pinta su barra de progreso una y otra vez), se queda
    # bloqueado esperando a que alguien lea, y aquí se esperaba a que
    # terminara: los dos esperándose para siempre. A un archivo temporal se
    # puede escribir sin límite.
    try:
        salida_archivo = tempfile.TemporaryFile()
    except Exception as e:
        return False, t("optmod_no_inicio", error=e), False
    try:
        proceso = subprocess.Popen(comando_lista, stdout=salida_archivo, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        salida_archivo.close()
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
        salida_archivo.close()
        return False, t("optmod_cancelado"), True

    try:
        salida_archivo.seek(0)
        salida = _decodificar_salida_consola(salida_archivo.read())
    except Exception:
        salida = ""
    finally:
        salida_archivo.close()
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
    # BUG corregido: devolvía True pasara lo que pasara. Si el borrado
    # fallaba, el interruptor de la pantalla se apagaba igual y la limpieza
    # automática seguía ejecutándose sola cada día, sin nada que lo
    # explicara. Es el mismo fallo que tenía el inicio automático.
    try:
        r = subprocess.run(["schtasks", "/delete", "/tn", SCHEDULED_TASK_NAME, "/f"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if r.returncode == 0:
            return True, comando
        # schtasks también da error cuando la tarea no existía. En ese caso
        # el objetivo —que no quede ninguna— ya está cumplido, así que se
        # comprueba el resultado real en vez de fiarse del código de salida.
        return (not limpieza_programada_activa()), comando
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
    # BUG corregido: no se miraba el resultado, así que la app daba por
    # mostrada una notificación que podía no haber salido nunca (equipo con
    # notificaciones desactivadas, PowerShell restringido por directiva...).
    # Importa porque de esto dependen las alertas de temperatura de CPU: el
    # usuario las configura, cree que están funcionando, y no le avisan.
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                            timeout=10)
        return r.returncode == 0
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
    # BUG corregido: con un punto creado en las últimas 24 h, Windows NO
    # crea otro, pero Checkpoint-Computer solo avisa y termina con código
    # 0: la app decía "punto creado" antes de un sfc/DISM sin haberlo. Se
    # cuentan los puntos antes y después.
    antes = listar_puntos_restauracion()
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        if r.returncode != 0:
            return False, comando
    except Exception:
        return False, comando
    despues = listar_puntos_restauracion()
    if antes is not None and despues is not None:
        return len(despues) > len(antes), comando
    return True, comando


def listar_puntos_restauracion():
    """[{numero, descripcion, fecha}] del más nuevo al más viejo, o None si
    no se pudo leer (hace falta administrador)."""
    if not IS_WINDOWS:
        return None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-ComputerRestorePoint -ErrorAction Stop | ForEach-Object { [pscustomobject]@{ "
                            "numero = $_.SequenceNumber; descripcion = $_.Description; fecha = "
                            "[Management.ManagementDateTimeConverter]::ToDateTime($_.CreationTime).ToString('yyyy-MM-dd HH:mm') "
                            "} } | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        if r.returncode != 0:
            return None
        datos = json.loads((r.stdout or "").strip() or "[]")
    except Exception:
        return None
    if isinstance(datos, dict):
        datos = [datos]
    puntos = [{"numero": d.get("numero"), "descripcion": d.get("descripcion") or "", "fecha": d.get("fecha") or ""}
              for d in datos if isinstance(d, dict)]
    puntos.sort(key=lambda p: p["numero"] or 0, reverse=True)
    return puntos


def espacio_puntos_restauracion():
    """(usado, maximo) en bytes del espacio de instantáneas (donde viven los
    puntos), sumando todas las unidades. (None, None) si no se puede leer."""
    datos = _cim("Win32_ShadowStorage", ["UsedSpace", "MaxSpace"], timeout=20)
    if not datos:
        return None, None
    try:
        return sum(int(d.get("UsedSpace") or 0) for d in datos), sum(int(d.get("MaxSpace") or 0) for d in datos)
    except (TypeError, ValueError):
        return None, None


def borrar_puntos_antiguos():
    """Borra todos los puntos de restauración MENOS el más reciente, con
    vssadmin (los puntos son instantáneas de volumen). Devuelve
    (borrados, restantes, comando). No se puede deshacer: la interfaz lo
    confirma antes."""
    antes = listar_puntos_restauracion()
    comando = "vssadmin delete shadows /for=C: /oldest /quiet"
    if not antes or len(antes) < 2:
        return 0, len(antes or []), comando
    unidad = os.path.splitdrive(_carpeta_windows())[0] or "C:"
    for _ in range(len(antes) - 1):
        try:
            subprocess.run(["vssadmin", "delete", "shadows", f"/for={unidad}", "/oldest", "/quiet"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        except Exception:
            break
    despues = listar_puntos_restauracion() or []
    return max(0, len(antes) - len(despues)), len(despues), comando.replace("C:", unidad)


def informe_energia(carpeta, callback_progreso=None, evento_cancelar=None):
    """powercfg /energy: observa el equipo 60 s y genera un informe HTML con
    lo que impide suspender o gasta energía (dispositivos USB que no se
    duermen, procesos que no dejan bajar la CPU...). Necesita
    administrador. Devuelve (exito, ruta, resumen, cancelado)."""
    ruta = os.path.join(carpeta, "informe_energia_windows.html")
    exito, resumen, cancelado = _ejecutar_reparacion_cancelable(
        ["powercfg", "/energy", "/output", ruta, "/duration", "60"], timeout_seg=300,
        callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    # powercfg /energy sale con código distinto de 0 cuando ENCUENTRA
    # errores de energía (que es justo lo que se busca). El éxito real es
    # que el informe exista.
    existe = os.path.exists(ruta)
    return existe and not cancelado, ruta if existe else None, resumen, cancelado


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

_MB = 1024 * 1024


def clase_disco(lectura_mbs, aleatoria_mbs):
    """Qué tipo de disco se COMPORTA cada resultado: "hdd", "ssd" o "nvme".

    Referencias a profundidad de cola 1 (un pedido a la vez, como esta
    prueba): un disco mecánico lee unos 80-200 MB/s seguidos y menos de
    2 MB/s en bloques sueltos de 4 KB; un SSD SATA, unos 400-550 MB/s y
    20-40 MB/s; un NVMe pasa de 1000 MB/s seguidos."""
    if lectura_mbs >= 1000:
        return "nvme"
    if lectura_mbs >= 250 or aleatoria_mbs >= 8:
        return "ssd"
    return "hdd"


def _kernel32_sin_cache():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    from ctypes import wintypes as wt
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD,
                                wt.HANDLE]
    k32.CreateFileW.restype = wt.HANDLE
    k32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    k32.SetFilePointerEx.argtypes = [wt.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wt.DWORD]
    k32.FlushFileBuffers.argtypes = [wt.HANDLE]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
    k32.VirtualAlloc.restype = ctypes.c_void_p
    k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
    return k32


def prueba_velocidad_disco(tamano_mb=256, callback_progreso=None, carpeta=None, segundos_aleatoria=3):
    """
    Velocidad REAL del disco: escritura y lectura seguidas (copiar archivos
    grandes) y lectura de bloques sueltos de 4 KB (lo que más se nota al
    abrir programas y arrancar Windows).

    BUG corregido (1.7.0): se leía con open() normal y Windows servía la
    lectura desde la caché de la RAM, porque acababa de escribir ese mismo
    archivo: salían miles de MB/s también en un disco mecánico. El
    comentario de entonces decía que evitarlo "requería privilegios"; no:
    basta con abrir el archivo con FILE_FLAG_NO_BUFFERING, que cualquier
    usuario puede usar. Así se mide el disco y no la RAM.

    El archivo se abre con FILE_FLAG_DELETE_ON_CLOSE: Windows lo borra al
    cerrarlo, aunque la app se cierre de golpe a mitad de la prueba.

    Devuelve escritura_mbs, lectura_mbs, aleatoria_mbs, iops, clase
    ("hdd"/"ssd"/"nvme", ver clase_disco), unidad y tamano_probado_mb; o
    {"error": texto}. None fuera de Windows.
    """
    if not IS_WINDOWS:
        return None
    import random
    from ctypes import wintypes as wt

    def _avisar(texto):
        if callback_progreso:
            try:
                callback_progreso(texto)
            except Exception:
                pass

    carpeta = carpeta or tempfile.gettempdir()
    unidad = os.path.splitdrive(os.path.abspath(carpeta))[0] or carpeta
    try:
        libre = shutil.disk_usage(carpeta).free
    except OSError as e:
        return {"error": str(e)}
    # El doble de lo que se escribe y 1 GB de margen: con el disco casi
    # lleno la prueba no debe ser la que lo termine de llenar.
    if libre < tamano_mb * _MB * 2 + 1024 * _MB:
        return {"error": t("comp_disco_sin_espacio", libre=format_bytes(libre))}

    k32 = _kernel32_sin_cache()
    invalido = wt.HANDLE(-1).value
    buffer = k32.VirtualAlloc(None, _MB, 0x3000, 0x04)       # MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE
    if not buffer:
        return {"error": t("comp_disco_error_simple")}
    ruta = os.path.join(carpeta, f"techclean_prueba_disco_{os.getpid()}.tmp")
    manejador = invalido
    try:
        # Datos al azar: un disco que comprime (algunos SSD) no puede hacer trampa.
        ctypes.memmove(buffer, os.urandom(_MB), _MB)
        manejador = k32.CreateFileW(
            ruta, 0x80000000 | 0x40000000, 0, None, 2,           # GENERIC_READ|WRITE, CREATE_ALWAYS
            0x20000000 | 0x80000000 | 0x04000000, None)          # NO_BUFFERING|WRITE_THROUGH|DELETE_ON_CLOSE
        if manejador in (invalido, None):
            return {"error": t("comp_disco_no_crear", error=ctypes.get_last_error())}
        hechos = wt.DWORD()

        _avisar(t("comp_disco_fase_escribiendo"))
        inicio = time.perf_counter()
        for _ in range(tamano_mb):
            if not k32.WriteFile(manejador, buffer, _MB, ctypes.byref(hechos), None) or hechos.value != _MB:
                return {"error": t("comp_disco_no_escribir", error=ctypes.get_last_error())}
        k32.FlushFileBuffers(manejador)
        escritura = tamano_mb / max(time.perf_counter() - inicio, 1e-6)

        _avisar(t("comp_disco_fase_leyendo"))
        k32.SetFilePointerEx(manejador, 0, None, 0)
        inicio = time.perf_counter()
        for _ in range(tamano_mb):
            if not k32.ReadFile(manejador, buffer, _MB, ctypes.byref(hechos), None) or hechos.value != _MB:
                return {"error": t("comp_disco_no_leer", error=ctypes.get_last_error())}
        lectura = tamano_mb / max(time.perf_counter() - inicio, 1e-6)

        # Bloques de 4 KB en posiciones al azar, durante unos segundos. Es
        # múltiplo del tamaño de sector de cualquier disco actual (512 o
        # 4096 bytes), que es lo que exige NO_BUFFERING.
        _avisar(t("comp_disco_fase_aleatoria"))
        bloques = tamano_mb * _MB // 4096
        azar = random.Random()
        lecturas = 0
        inicio = time.perf_counter()
        fin = inicio + segundos_aleatoria
        while time.perf_counter() < fin and lecturas < 200000:
            k32.SetFilePointerEx(manejador, azar.randrange(bloques) * 4096, None, 0)
            if not k32.ReadFile(manejador, buffer, 4096, ctypes.byref(hechos), None):
                break
            lecturas += 1
        duracion = max(time.perf_counter() - inicio, 1e-6)
        iops = lecturas / duracion
        aleatoria = iops * 4096 / _MB

        _avisar(t("comp_disco_fase_listo"))
        return {
            "escritura_mbs": round(escritura, 1),
            "lectura_mbs": round(lectura, 1),
            "aleatoria_mbs": round(aleatoria, 1),
            "iops": int(iops),
            "clase": clase_disco(lectura, aleatoria),
            "unidad": unidad,
            "tamano_probado_mb": tamano_mb,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if manejador not in (invalido, None):
            k32.CloseHandle(manejador)              # DELETE_ON_CLOSE: aquí desaparece el archivo
        k32.VirtualFree(buffer, 0, 0x8000)          # MEM_RELEASE
        # Por si CreateFileW falló a medias y dejó algo (no debería).
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
        except OSError:
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
    roaming = os.environ.get("APPDATA") or os.path.join(base, "..", "Roaming")
    # Cada caché con sus posibles sitios, en orden; se usa el primero que
    # exista. BUG corregido: Steam y Discord apuntaban a carpetas donde
    # esas apps no guardan nada (Steam usa Local, Discord usa Roaming), así
    # que nunca aparecían en la lista. Spotify cambió Storage por Data.
    candidatos = {
        t("optmod_cache_steam"): [os.path.join(base, "Steam", "htmlcache")],
        t("optmod_cache_discord"): [os.path.join(roaming, "discord", "Cache")],
        t("optmod_cache_onedrive"): [os.path.join(base, "Microsoft", "OneDrive", "logs")],
        t("optmod_cache_pip"): [os.path.join(base, "pip", "Cache")],
        t("optmod_cache_npm"): [os.path.join(base, "npm-cache")],
        t("optmod_cache_spotify"): [os.path.join(base, "Spotify", "Data"),
                                    os.path.join(base, "Spotify", "Storage")],
    }
    resultados = []
    for nombre, posibles in candidatos.items():
        ruta = next((os.path.normpath(r) for r in posibles if os.path.isdir(r)), None)
        if ruta is None:
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
    (bytes_liberados, comando).

    BUG corregido: medía cada carpeta ANTES de borrarla y sumaba ese número,
    con rmtree(ignore_errors=True), que nunca avisa. Con la app abierta
    (Discord, Spotify) la mitad de los archivos están bloqueados: se borraba
    una parte y se anunciaba el total. Es el mismo fallo que ya se había
    corregido en la caché del navegador. Ahora se mide antes y después."""
    comando = f'Vaciar contenido de "{ruta}"'
    liberado, _ = _vaciar_contenido(ruta)
    return liberado, comando


def _es_enlace(ruta):
    """Enlace simbólico o unión (junction). NUNCA se entra en uno al borrar:
    una unión puede apuntar a cualquier sitio del disco, y seguirla
    convertiría "vaciar esta caché" en "vaciar lo que haya al otro lado"."""
    try:
        if os.path.islink(ruta):
            return True
        es_union = getattr(os.path, "isjunction", None)
        return bool(es_union and es_union(ruta))
    except OSError:
        return True


def _recorrer(ruta, excluir=None):
    """os.walk SIN entrar en enlaces ni uniones, y saltando las carpetas
    que `excluir(carpeta)` diga. Da las mismas tuplas (raiz, dirs, archivos).

    Ojo: os.walk(followlinks=False) NO basta en Windows. Solo esquiva los
    enlaces simbólicos; las UNIONES (junctions) no lo son para él y entra
    en ellas. Comprobado en prueba_limpieza_fondo.py."""
    for raiz, dirs, archivos in os.walk(ruta, topdown=True, onerror=lambda e: None):
        dirs[:] = [d for d in dirs
                   if not _es_enlace(os.path.join(raiz, d))
                   and not (excluir and excluir(os.path.join(raiz, d)))]
        yield raiz, dirs, archivos


def _medir(ruta, filtro=None, excluir=None):
    """Tamaño de una carpeta (o de un archivo suelto), contando solo lo que
    pase el filtro y sin entrar en enlaces."""
    if os.path.isfile(ruta):
        try:
            return os.path.getsize(ruta) if (filtro is None or filtro(ruta)) else 0
        except OSError:
            return 0
    total = 0
    for raiz, _, archivos in _recorrer(ruta, excluir):
        for a in archivos:
            fp = os.path.join(raiz, a)
            if filtro is not None and not filtro(fp):
                continue
            try:
                total += os.path.getsize(fp)
            except OSError:
                continue
    return total


def _vaciar_contenido(ruta, filtro=None, excluir=None):
    """Borra lo que hay DENTRO de una carpeta (o un archivo suelto) y deja
    la carpeta en su sitio. Devuelve (bytes_liberados, archivos_borrados).

    Solo se suma el tamaño de lo que se borró DE VERDAD (os.remove sin
    error), nunca lo que se intentó: un archivo en uso no se borra, y
    anunciarlo como liberado sería mentir (ya pasó dos veces en esta app,
    con el navegador y con las cachés)."""
    if not os.path.exists(ruta):
        return 0, 0

    def borrar(fp):
        try:
            tam = os.path.getsize(fp)
            os.remove(fp)
            return tam
        except OSError:
            return None

    if os.path.isfile(ruta):
        if filtro is not None and not filtro(ruta):
            return 0, 0
        tam = borrar(ruta)
        return (tam, 1) if tam is not None else (0, 0)

    liberado = 0
    borrados = 0
    carpetas = []
    for raiz, dirs, archivos in _recorrer(ruta, excluir):
        carpetas.extend(os.path.join(raiz, d) for d in dirs)
        for a in archivos:
            fp = os.path.join(raiz, a)
            if filtro is not None and not filtro(fp):
                continue
            tam = borrar(fp)
            if tam is not None:
                liberado += tam
                borrados += 1
    # Las subcarpetas que quedaron vacías, de la más profunda a la menos.
    # rmdir no borra una carpeta con algo dentro, así que es seguro.
    for carpeta in sorted(carpetas, key=len, reverse=True):
        try:
            os.rmdir(carpeta)
        except OSError:
            continue
    return liberado, borrados


def _mas_viejo_que(dias):
    limite = time.time() - dias * 86400

    def filtro(fp):
        try:
            return os.path.getmtime(fp) < limite
        except OSError:
            return False
    return filtro


def _categorias_limpieza_sistema():
    """Lo mismo que limpia el Liberador de espacio de Windows (cleanmgr),
    categoría por categoría. Se arma al llamarla, no al importar el módulo,
    para que t() ya tenga el idioma fijado.

    Lo que NO está, a propósito:
    - Caché de sombreadores (DirectX/NVIDIA/AMD): borrarla hace que los
      juegos vuelvan a compilarlos y den tirones las primeras partidas. En
      una app que tiene Modo Juego, eso es ir en contra de sí misma.
    - Prefetch: Windows lo usa para abrir los programas más rápido. Las
      "guías de optimización" que dicen borrarlo están equivocadas.
    - Windows.old: Windows lo borra solo a los 10 días y quitarlo a mano
      exige tomar posesión de miles de archivos del sistema."""
    win = _carpeta_windows()
    datos_programa = os.environ.get("ProgramData") or r"C:\ProgramData"
    local = _ruta_localappdata()
    return [
        {
            "clave": "update",
            "nombre": t("fondo_update"),
            "desc": t("fondo_update_desc"),
            "rutas": [os.path.join(win, "SoftwareDistribution", "Download")],
            # Lo de los últimos 3 días se respeta: puede ser una
            # actualización que se está descargando o instalando ahora.
            "filtro": _mas_viejo_que(3),
        },
        {
            "clave": "entrega",
            "nombre": t("fondo_entrega"),
            "desc": t("fondo_entrega_desc"),
            "rutas": [os.path.join(win, "ServiceProfiles", "NetworkService", "AppData", "Local",
                                   "Microsoft", "Windows", "DeliveryOptimization", "Cache")],
            "filtro": None,
        },
        {
            "clave": "errores",
            "nombre": t("fondo_errores"),
            "desc": t("fondo_errores_desc"),
            "rutas": [os.path.join(datos_programa, "Microsoft", "Windows", "WER", "ReportArchive"),
                      os.path.join(datos_programa, "Microsoft", "Windows", "WER", "ReportQueue"),
                      os.path.join(local, "Microsoft", "Windows", "WER")],
            "filtro": None,
        },
        {
            "clave": "volcados",
            "nombre": t("fondo_volcados"),
            "desc": t("fondo_volcados_desc"),
            "rutas": [os.path.join(win, "Minidump"),
                      os.path.join(win, "MEMORY.DMP"),
                      os.path.join(local, "CrashDumps")],
            "filtro": None,
        },
        {
            "clave": "registros",
            "nombre": t("fondo_registros"),
            "desc": t("fondo_registros_desc"),
            # Solo los registros ARCHIVADOS (CbsPersist_*). CBS.log, el
            # actual, se deja: es el que se lee después de un sfc /scannow.
            "rutas": [os.path.join(win, "Logs", "CBS")],
            "filtro": lambda fp: os.path.basename(fp).lower().startswith("cbspersist_"),
        },
    ]


def listar_limpieza_sistema():
    """Cuánto ocupa cada categoría de la limpieza a fondo, sin borrar nada.
    Devuelve una lista de {"clave", "nombre", "desc", "bytes"}."""
    resultado = []
    for c in _categorias_limpieza_sistema():
        total = sum(_medir(r, c["filtro"]) for r in c["rutas"] if os.path.exists(r))
        resultado.append({"clave": c["clave"], "nombre": c["nombre"], "desc": c["desc"], "bytes": total})
    return resultado


def limpiar_sistema(claves):
    """Limpia las categorías pedidas (por su clave interna, nunca por el
    texto visible). Devuelve (bytes_liberados, archivos_borrados, comando)."""
    liberado = 0
    borrados = 0
    rutas_usadas = []
    for c in _categorias_limpieza_sistema():
        if c["clave"] not in claves:
            continue
        for ruta in c["rutas"]:
            if not os.path.exists(ruta):
                continue
            bytes_ruta, archivos = _vaciar_contenido(ruta, c["filtro"])
            liberado += bytes_ruta
            borrados += archivos
            rutas_usadas.append(ruta)
    comando = "Vaciar contenido de: " + "; ".join(rutas_usadas) if rutas_usadas else "N/A"
    return liberado, borrados, comando


def limpiar_componentes_windows(callback_progreso=None, evento_cancelar=None):
    """DISM /StartComponentCleanup: quita las versiones viejas de los
    componentes de Windows que dejan las actualizaciones (la carpeta
    WinSxS). Es lo que hace la tarea programada de Windows, pero esa solo
    corre con el equipo inactivo y a veces nunca llega a correr.

    Sin /ResetBase, a propósito: con /ResetBase ya no se puede desinstalar
    ninguna actualización instalada, y si una sale mala, no hay vuelta atrás.

    Lo liberado se mide como espacio libre del disco del sistema antes y
    después: DISM no informa cuánto quitó, y estimarlo antes cuesta otros
    tantos minutos (/AnalyzeComponentStore).

    Devuelve (exito, bytes_liberados, resumen, cancelado)."""
    unidad = os.path.splitdrive(_carpeta_windows())[0] + "\\"
    try:
        libre_antes = shutil.disk_usage(unidad).free
    except OSError:
        libre_antes = None
    exito, resumen, cancelado = _ejecutar_reparacion_cancelable(
        ["Dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
        timeout_seg=3600, callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    liberado = 0
    if libre_antes is not None:
        try:
            liberado = max(0, shutil.disk_usage(unidad).free - libre_antes)
        except OSError:
            pass
    return exito, liberado, resumen, cancelado


def _guid_en(texto):
    """El primer GUID que aparezca en una línea de powercfg."""
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", texto or "")
    return m.group(0).lower() if m else None


def plan_activo_guid():
    """GUID del plan de energía activo, o None.

    Para deshacer hace falta el plan EXACTO de antes, no el perfil que
    TechClean tenía guardado: si el usuario estaba en un plan propio (o en
    el del fabricante del portátil), "deshacer" lo mandaba a Equilibrado."""
    if not IS_WINDOWS:
        return None
    try:
        r = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return _guid_en(r.stdout)
    except Exception:
        return None


def activar_plan_guid(guid):
    """Activa un plan por su GUID. Devuelve (exito, comando)."""
    comando = f"powercfg /setactive {guid}"
    if not IS_WINDOWS or not _guid_en(guid):
        return False, comando
    try:
        r = subprocess.run(["powercfg", "/setactive", guid], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return r.returncode == 0, comando
    except Exception:
        return False, comando


# ---------------- Optimizar unidades (TRIM / desfragmentar) ----------------

# El tipo de cada disco no cambia mientras la app está abierta, y leerlo
# cuesta ~8 s en equipos con WMI lento (Get-PhysicalDisk). Se lee una vez;
# las siguientes solo se actualiza el espacio libre, que es instantáneo.
_tipos_unidad_cache = None


def listar_unidades_optimizables():
    global _tipos_unidad_cache
    if _tipos_unidad_cache is not None:
        unidades = []
        for part in psutil.disk_partitions(all=False):
            if "fixed" not in (part.opts or ""):
                continue
            letra = _letra_unidad(part.mountpoint)
            if letra is None:
                continue
            try:
                uso = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            unidades.append({"letra": letra, "tipo": _tipos_unidad_cache.get(letra, "?"),
                             "tamano": uso.total, "libre": uso.free})
        if unidades:
            return sorted(unidades, key=lambda u: u["letra"])
    unidades = _listar_unidades_powershell()
    if unidades:
        _tipos_unidad_cache = {u["letra"]: u["tipo"] for u in unidades}
    return unidades


def _listar_unidades_powershell():
    """Unidades fijas con su tipo de disco. Devuelve una lista de
    {"letra", "tipo" ("SSD"|"HDD"|"?"), "tamano", "libre"}.

    El tipo importa para decirle al usuario qué va a pasar: en un SSD se
    hace TRIM (segundos) y en un disco mecánico se desfragmenta (puede
    tardar más de una hora). Desfragmentar un SSD no sirve de nada y lo
    gasta; por eso la acción la decide Optimize-Volume, que mira el tipo
    él mismo, igual que la herramienta "Desfragmentar y optimizar unidades"
    de Windows."""
    ps = (
        "Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' } | ForEach-Object { "
        "$letra = [string]$_.DriveLetter; $tipo = '?'; "
        "try { $disco = Get-Partition -DriveLetter $letra -ErrorAction Stop | Get-Disk -ErrorAction Stop; "
        "$fisico = Get-PhysicalDisk | Where-Object { $_.DeviceId -eq [string]$disco.Number }; "
        "if ($fisico) { $tipo = [string]$fisico.MediaType } } catch {} ; "
        "[pscustomobject]@{ letra = $letra; tipo = $tipo; tamano = [int64]$_.Size; libre = [int64]$_.SizeRemaining } "
        "} | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                           timeout=30)
        datos = json.loads((r.stdout or "").strip() or "[]")
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    unidades = []
    for d in datos if isinstance(datos, list) else []:
        letra = str(d.get("letra") or "").strip().upper()[:1]
        if not letra.isalpha():
            continue
        tipo = str(d.get("tipo") or "").upper()
        unidades.append({"letra": letra, "tipo": tipo if tipo in ("SSD", "HDD") else "?",
                         "tamano": int(d.get("tamano") or 0), "libre": int(d.get("libre") or 0)})
    unidades.sort(key=lambda u: u["letra"])
    return unidades


def _letra_unidad(texto):
    """La letra de unidad, o None. Va dentro de un comando de PowerShell:
    de lo que llegue solo se queda UNA letra de la A a la Z, nada más."""
    letra = str(texto or "").strip().upper()[:1]
    return letra if len(letra) == 1 and "A" <= letra <= "Z" else None


def optimizar_unidad(letra, callback_progreso=None, evento_cancelar=None):
    """Optimize-Volume con la acción por defecto para el tipo de disco
    (TRIM en SSD, desfragmentar en HDD). Devuelve (exito, resumen, cancelado)."""
    letra = _letra_unidad(letra)
    if letra is None:
        return False, t("unid_letra_invalida"), False
    return _ejecutar_reparacion_cancelable(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"Optimize-Volume -DriveLetter {letra} -Verbose 4>&1"],
        timeout_seg=4 * 3600, callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)


# ---------------- DNS: medir y elegir el más rápido ----------------

# Direcciones publicadas por cada proveedor. Las de IPv6 van también: si
# solo se cambian las de IPv4, Windows puede seguir preguntando al DNS de
# IPv6 que da el router y el cambio no surte efecto.
PROVEEDORES_DNS = {
    "cloudflare": {"nombre": "Cloudflare", "v4": ["1.1.1.1", "1.0.0.1"],
                   "v6": ["2606:4700:4700::1111", "2606:4700:4700::1001"]},
    "google": {"nombre": "Google", "v4": ["8.8.8.8", "8.8.4.4"],
               "v6": ["2001:4860:4860::8888", "2001:4860:4860::8844"]},
    "quad9": {"nombre": "Quad9", "v4": ["9.9.9.9", "149.112.112.112"],
              "v6": ["2620:fe::fe", "2620:fe::9"]},
    "opendns": {"nombre": "OpenDNS", "v4": ["208.67.222.222", "208.67.220.220"],
                "v6": ["2620:119:35::35", "2620:119:53::53"]},
}

DOMINIOS_PRUEBA_DNS = ["google.com", "youtube.com", "facebook.com", "microsoft.com",
                       "wikipedia.org", "amazon.com", "whatsapp.net", "netflix.com"]


def _paquete_dns(dominio, ident):
    """Una consulta DNS de tipo A, armada a mano (RFC 1035): no hace falta
    ninguna librería para algo de 30 bytes."""
    import struct
    cabecera = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0)   # recursión deseada, 1 pregunta
    nombre = b"".join(bytes([len(p)]) + p.encode("ascii") for p in dominio.split(".")) + b"\x00"
    return cabecera + nombre + struct.pack(">HH", 1, 1)               # tipo A, clase IN


def medir_servidor_dns(ip, dominios=None, timeout=2.0):
    """Tiempo de respuesta de un servidor DNS, en milisegundos (la mediana
    de varias consultas), o None si no contesta a la mayoría.

    La mediana y no la media: una sola consulta lenta (el servidor no
    tenía ese dominio en caché) no debe hundir a un servidor bueno."""
    import socket
    import statistics
    dominios = dominios or DOMINIOS_PRUEBA_DNS
    tiempos = []
    familia = socket.AF_INET6 if ":" in ip else socket.AF_INET
    for dominio in dominios:
        ident = int.from_bytes(os.urandom(2), "big")
        try:
            with socket.socket(familia, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                inicio = time.perf_counter()
                s.sendto(_paquete_dns(dominio, ident), (ip, 53))
                while True:
                    datos, _ = s.recvfrom(1500)
                    # Solo cuenta la respuesta a ESTA pregunta.
                    if len(datos) >= 2 and int.from_bytes(datos[:2], "big") == ident:
                        break
                tiempos.append((time.perf_counter() - inicio) * 1000)
        except OSError:
            continue
    if len(tiempos) < len(dominios) / 2:
        return None
    return statistics.median(tiempos)


def leer_dns_actual():
    """Los adaptadores conectados a internet (con puerta de enlace) y su
    DNS. Devuelve una lista de {"indice", "nombre", "dns", "fijos_v4",
    "fijos_v6"}.

    "fijos" son los que alguien escribió a mano (registro NameServer). Si
    están vacíos, el DNS lo da el router (DHCP). Hace falta saberlo para
    deshacer: volver a "automático" no es lo mismo que volver a 8.8.8.8 si
    eso era lo que el usuario tenía puesto."""
    ps = (
        "Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | "
        "ForEach-Object { $guid = $_.NetAdapter.InterfaceGuid; "
        "$v4 = (Get-ItemProperty \"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\$guid\" "
        "-ErrorAction SilentlyContinue).NameServer; "
        "$v6 = (Get-ItemProperty \"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters\\Interfaces\\$guid\" "
        "-ErrorAction SilentlyContinue).NameServer; "
        "[pscustomobject]@{ indice = $_.InterfaceIndex; nombre = $_.InterfaceAlias; "
        "dns = @($_.DNSServer | Where-Object AddressFamily -eq 2 | ForEach-Object { $_.ServerAddresses }); "
        "fijos_v4 = [string]$v4; fijos_v6 = [string]$v6 } } | ConvertTo-Json -Compress -Depth 3"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                           timeout=30)
        datos = json.loads((r.stdout or "").strip() or "[]")
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]

    def separar(texto):
        return [x for x in re.split(r"[,\s]+", texto or "") if x]

    adaptadores = []
    for d in datos if isinstance(datos, list) else []:
        try:
            indice = int(d.get("indice"))
        except (TypeError, ValueError):
            continue
        dns = d.get("dns") or []
        if isinstance(dns, str):
            dns = [dns]
        adaptadores.append({"indice": indice, "nombre": str(d.get("nombre") or ""),
                            "dns": [str(x) for x in dns],
                            "fijos_v4": separar(d.get("fijos_v4")), "fijos_v6": separar(d.get("fijos_v6"))})
    return adaptadores


def comparar_dns(callback_progreso=None):
    """Mide el DNS actual y los cuatro públicos. Devuelve una lista de
    {"clave", "nombre", "ip", "ms"} ordenada de más rápido a más lento
    (los que no contestan, al final con ms=None). clave="actual" es el
    que el equipo usa ahora."""
    candidatos = []
    actuales = []
    for a in leer_dns_actual():
        for ip in a["dns"]:
            if ip not in actuales:
                actuales.append(ip)
    if actuales:
        candidatos.append(("actual", t("dns_actual"), actuales[0]))
    for clave, p in PROVEEDORES_DNS.items():
        candidatos.append((clave, p["nombre"], p["v4"][0]))

    resultados = []
    for i, (clave, nombre, ip) in enumerate(candidatos):
        if callback_progreso:
            try:
                callback_progreso(i, len(candidatos), nombre)
            except Exception:
                pass
        resultados.append({"clave": clave, "nombre": nombre, "ip": ip, "ms": medir_servidor_dns(ip)})
    resultados.sort(key=lambda r: (r["ms"] is None, r["ms"] or 0))
    return resultados


def _ps_lista(direcciones):
    # Solo direcciones IP (dígitos, letras hex, puntos y dos puntos): van
    # dentro de un comando de PowerShell.
    limpias = [d for d in direcciones if re.fullmatch(r"[0-9A-Fa-f:.]+", d or "")]
    return ",".join(f"'{d}'" for d in limpias)


def _ps(comando, timeout=30):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                           timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def aplicar_dns(clave):
    """Pone el DNS de un proveedor en todos los adaptadores conectados.
    Devuelve (exito, comando, estado_anterior). estado_anterior es lo que
    hace falta para deshacerlo.

    "Exito" es que el DNS que Windows tiene puesto DESPUÉS sea el pedido,
    releído, no que el comando no haya dado error."""
    if clave not in PROVEEDORES_DNS:
        return False, "N/A", []
    p = PROVEEDORES_DNS[clave]
    direcciones = p["v4"] + p["v6"]
    anteriores = leer_dns_actual()
    if not anteriores:
        return False, "N/A", []
    comandos = []
    for a in anteriores:
        comando = (f"Set-DnsClientServerAddress -InterfaceIndex {int(a['indice'])} "
                   f"-ServerAddresses ({_ps_lista(direcciones)})")
        comandos.append(comando)
        if not _ps(comando):
            # Con IPv6 desactivado en el adaptador, Windows puede rechazar la
            # lista entera por las direcciones IPv6. Entonces, solo IPv4.
            comando = (f"Set-DnsClientServerAddress -InterfaceIndex {int(a['indice'])} "
                       f"-ServerAddresses ({_ps_lista(p['v4'])})")
            comandos.append(comando)
            _ps(comando)
    _ps("Clear-DnsClientCache")

    despues = {a["indice"]: a["dns"] for a in leer_dns_actual()}
    exito = all(despues.get(a["indice"], [])[:1] == [p["v4"][0]] for a in anteriores)
    estado = [{"indice": a["indice"], "nombre": a["nombre"],
               "fijos_v4": a["fijos_v4"], "fijos_v6": a["fijos_v6"]} for a in anteriores]
    return exito, "; ".join(comandos), estado


def restaurar_dns(estado):
    """Deshace aplicar_dns: cada adaptador vuelve a lo que tenía. Si no
    tenía nada escrito a mano, vuelve a automático (lo que dé el router)."""
    comandos = []
    exito = bool(estado)
    for a in estado or []:
        try:
            indice = int(a.get("indice"))
        except (TypeError, ValueError):
            exito = False
            continue
        comando = f"Set-DnsClientServerAddress -InterfaceIndex {indice} -ResetServerAddresses"
        comandos.append(comando)
        exito = _ps(comando) and exito
        fijos = list(a.get("fijos_v4") or []) + list(a.get("fijos_v6") or [])
        if fijos:
            comando = f"Set-DnsClientServerAddress -InterfaceIndex {indice} -ServerAddresses ({_ps_lista(fijos)})"
            comandos.append(comando)
            exito = _ps(comando) and exito
    _ps("Clear-DnsClientCache")
    return exito, "; ".join(comandos)


# ---------------- Ajustes de Windows para juegos ----------------
# Los mismos interruptores que Configuración > Juegos y Configuración >
# Pantalla > Gráficos, escritos donde los escribe la propia Configuración.
# Cada ajuste puede tocar VARIAS claves (la grabación en segundo plano vive
# en dos sitios); por eso cada uno es una lista de (raíz, ruta, valor).
# "on"/"off" son los valores que pone Windows en cada estado; "defecto" es
# lo que Windows hace si la clave no existe todavía.

AJUSTES_JUEGO = {
    "modo_juego": {
        "claves": [("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": True, "reinicio": False,
    },
    "grabacion_fondo": {
        # Captura en segundo plano de Xbox Game Bar: graba los últimos
        # minutos SIEMPRE, por si quieres guardarlos. Cuesta rendimiento.
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"),
                   ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled")],
        "on": 1, "off": 0, "defecto": 0, "recomendado": False, "reinicio": False,
    },
    "gpu_hags": {
        # Programación de GPU acelerada por hardware. 2 = activada, 1 =
        # desactivada. Solo surte efecto con GPU y controlador compatibles,
        # y tras reiniciar.
        "claves": [("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")],
        "on": 2, "off": 1, "defecto": None, "recomendado": True, "reinicio": True,
    },
}


def _raiz_registro(nombre):
    import winreg
    return {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}[nombre]


def _leer_dword(raiz, ruta, nombre):
    """El valor DWORD, o None si la clave o el valor no existen."""
    if not IS_WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(_raiz_registro(raiz), ruta) as k:
            valor, tipo = winreg.QueryValueEx(k, nombre)
            return int(valor) if tipo == winreg.REG_DWORD else None
    except (OSError, ValueError):
        return None


def _escribir_dword(raiz, ruta, nombre, valor):
    """Escribe el DWORD, o BORRA el valor si `valor` es None (para volver a
    como estaba cuando la clave no existía)."""
    import winreg
    try:
        with winreg.CreateKeyEx(_raiz_registro(raiz), ruta, 0, winreg.KEY_SET_VALUE) as k:
            if valor is None:
                try:
                    winreg.DeleteValue(k, nombre)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(k, nombre, 0, winreg.REG_DWORD, int(valor))
        return True
    except OSError:
        return False


def leer_ajustes_juego(tabla=None):
    """{clave: True | False | None}. None = no se sabe (no existe y Windows
    no tiene un valor por defecto fijo, como la GPU)."""
    tabla = tabla or AJUSTES_JUEGO
    estado = {}
    for clave, a in tabla.items():
        r, ruta, nombre = a["claves"][0]
        valor = _leer_dword(r, ruta, nombre)
        if valor is None:
            valor = a["defecto"]
        estado[clave] = None if valor is None else (valor == a["on"])
    return estado


def set_ajuste_juego(clave, activar, tabla=None):
    """Cambia un ajuste. Devuelve (exito, comando, anteriores) donde
    `anteriores` son los valores CRUDOS de cada clave antes del cambio (None
    = no existía), que es lo que hace falta para deshacerlo.

    Éxito = releer el registro y ver el valor pedido."""
    tabla = tabla or AJUSTES_JUEGO
    if clave not in tabla or not IS_WINDOWS:
        return False, "N/A", []
    a = tabla[clave]
    valor = a["on"] if activar else a["off"]
    anteriores = [_leer_dword(r, ruta, nombre) for r, ruta, nombre in a["claves"]]
    for r, ruta, nombre in a["claves"]:
        _escribir_dword(r, ruta, nombre, valor)
    exito = all(_leer_dword(r, ruta, nombre) == valor for r, ruta, nombre in a["claves"])
    comando = "; ".join(f"reg add {r}\\{ruta} /v {nombre} /t REG_DWORD /d {valor} /f" for r, ruta, nombre in a["claves"])
    return exito, comando, anteriores


def restaurar_ajuste_juego(clave, anteriores, tabla=None):
    """Deshace set_ajuste_juego: cada clave vuelve a su valor crudo (o se
    borra si no existía)."""
    tabla = tabla or AJUSTES_JUEGO
    if clave not in tabla or len(anteriores or []) != len(tabla[clave]["claves"]):
        return False, "N/A"
    claves = tabla[clave]["claves"]
    for (r, ruta, nombre), valor in zip(claves, anteriores):
        _escribir_dword(r, ruta, nombre, valor)
    exito = all(_leer_dword(r, ruta, nombre) == valor for (r, ruta, nombre), valor in zip(claves, anteriores))
    return exito, f"restaurar {clave}: {anteriores}"


# ---------------- Privacidad de Windows ----------------
# Mismo mecanismo que AJUSTES_JUEGO (leer_ajustes_juego / set_ajuste_juego /
# restaurar_ajuste_juego aceptan otra tabla). "on" = la función de Windows
# ENCENDIDA; lo recomendado aquí es casi siempre apagarla. Solo claves que
# escribe la propia Configuración de Windows (o la directiva documentada
# de Bing en el buscador), nada adivinado.
AJUSTES_PRIVACIDAD = {
    "publicidad": {
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": False, "reinicio": False,
    },
    "sugerencias_inicio": {
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SystemPaneSuggestionsEnabled"),
                   ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338388Enabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": False, "reinicio": False,
    },
    "sugerencias_configuracion": {
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338393Enabled"),
                   ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-353694Enabled"),
                   ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-353696Enabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": False, "reinicio": False,
    },
    "consejos": {
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338389Enabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": False, "reinicio": False,
    },
    "experiencias": {
        "claves": [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Privacy", "TailoredExperiencesWithDiagnosticDataEnabled")],
        "on": 1, "off": 0, "defecto": 1, "recomendado": False, "reinicio": False,
    },
    "bing_inicio": {
        # Directiva: 1 = DESACTIVA los resultados web en el buscador del
        # menú Inicio. Por eso "on" (Bing encendido) es 0. Explorer la lee
        # al arrancar: hace falta cerrar sesión o reiniciar el Explorador.
        "claves": [("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions")],
        "on": 0, "off": 1, "defecto": 0, "recomendado": False, "reinicio": True,
    },
}


def leer_ajustes_privacidad():
    return leer_ajustes_juego(AJUSTES_PRIVACIDAD)


def set_ajuste_privacidad(clave, activar):
    return set_ajuste_juego(clave, activar, AJUSTES_PRIVACIDAD)


def restaurar_ajuste_privacidad(clave, anteriores):
    return restaurar_ajuste_juego(clave, anteriores, AJUSTES_PRIVACIDAD)


# ---------------- Medidor de lag (ping, variación, pérdida) ----------------

if IS_WINDOWS:
    class _OpcionesIP(ctypes.Structure):
        _fields_ = [("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte),
                    ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]

    class _RespuestaEco(ctypes.Structure):
        # ICMP_ECHO_REPLY (iphlpapi, documentada en MSDN)
        _fields_ = [("Address", ctypes.c_ulong), ("Status", ctypes.c_ulong), ("RoundTripTime", ctypes.c_ulong),
                    ("DataSize", ctypes.c_ushort), ("Reserved", ctypes.c_ushort), ("Data", ctypes.c_void_p),
                    ("Options", _OpcionesIP)]


def _ping_una_vez(ip, timeout_ms=1000):
    """Un ping con IcmpSendEcho: no necesita administrador ni lanzar
    ping.exe (cuya salida, además, está traducida). Devuelve ms o None."""
    import socket
    iphlpapi = ctypes.WinDLL("iphlpapi")
    iphlpapi.IcmpCreateFile.restype = ctypes.wintypes.HANDLE
    iphlpapi.IcmpSendEcho.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ushort,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    iphlpapi.IcmpCloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    manejador = iphlpapi.IcmpCreateFile()
    if not manejador:
        return None
    try:
        datos = b"TechClean-ping-32bytes-de-relleno"[:32]
        tam = ctypes.sizeof(_RespuestaEco) + len(datos) + 8
        respuesta = ctypes.create_string_buffer(tam)
        destino = int.from_bytes(socket.inet_aton(ip), "little")
        n = iphlpapi.IcmpSendEcho(manejador, destino, datos, len(datos), None, respuesta, tam, timeout_ms)
        if n == 0:
            return None
        r = _RespuestaEco.from_buffer(respuesta)
        # RoundTripTime viene en ms enteros: una red local da 0-1 ms.
        return float(r.RoundTripTime) if r.Status == 0 else None
    finally:
        iphlpapi.IcmpCloseHandle(manejador)


def estadisticas_ping(tiempos):
    """De una lista de ms (None = perdido) saca media, mínimo, máximo,
    variación (jitter: media de la diferencia entre pings seguidos, que es
    lo que se nota como tirones) y pérdida. Función pura."""
    recibidos = [x for x in tiempos if x is not None]
    total = len(tiempos)
    if not recibidos:
        return {"enviados": total, "recibidos": 0, "perdida_pct": 100.0,
                "media_ms": None, "min_ms": None, "max_ms": None, "jitter_ms": None}
    saltos = [abs(b - a) for a, b in zip(recibidos, recibidos[1:])]
    return {"enviados": total, "recibidos": len(recibidos),
            "perdida_pct": round((total - len(recibidos)) * 100 / total, 1),
            "media_ms": round(sum(recibidos) / len(recibidos), 1),
            "min_ms": min(recibidos), "max_ms": max(recibidos),
            "jitter_ms": round(sum(saltos) / len(saltos), 1) if saltos else 0.0}


def medir_ping(ip, cantidad=30, intervalo=0.2, callback=None):
    tiempos = []
    for i in range(cantidad):
        inicio = time.perf_counter()
        tiempos.append(_ping_una_vez(ip))
        if callback:
            try:
                callback(i + 1, cantidad)
            except Exception:
                pass
        espera = intervalo - (time.perf_counter() - inicio)
        if espera > 0:
            time.sleep(espera)
    return estadisticas_ping(tiempos)


def puerta_de_enlace():
    """La IP del router de la conexión activa, o None."""
    salida = ""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and "
                            "$_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4DefaultGateway.NextHop"],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        salida = (r.stdout or "").strip().splitlines()[0] if (r.stdout or "").strip() else ""
    except Exception:
        return None
    return salida if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", salida) else None


def veredicto_lag(router, internet):
    """De dónde viene el lag: "bien", "local" (Wi-Fi / cable / router) o
    "proveedor" (de tu router hacia afuera). Si el tramo local ya va mal,
    el de internet lo arrastra, así que se mira primero. Función pura."""
    def malo(s, media, jitter):
        return (s is None or s["recibidos"] == 0 or s["perdida_pct"] >= 2
                or (s["media_ms"] or 0) >= media or (s["jitter_ms"] or 0) >= jitter)
    if router is not None and malo(router, 15, 8):
        return "local"
    if malo(internet, 80, 20):
        return "proveedor"
    return "bien"


def diagnosticar_lag(callback=None):
    """Mide el router y un servidor de internet (1.1.1.1). Devuelve
    {"router": stats|None, "router_ip", "internet": stats, "veredicto"}."""
    router_ip = puerta_de_enlace()
    router = None
    if router_ip:
        router = medir_ping(router_ip, callback=(lambda i, n: callback("router", i, n)) if callback else None)
    internet = medir_ping("1.1.1.1", callback=(lambda i, n: callback("internet", i, n)) if callback else None)
    return {"router": router, "router_ip": router_ip, "internet": internet,
            "veredicto": veredicto_lag(router, internet)}


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
    30-60 segundos. Devuelve (exito, lista, comando): cada elemento de la
    lista es la fila tal cual (nombre, id, versión, disponible, origen)
    unida con espacios, como antes."""
    comando = "winget upgrade --include-unknown"
    if not IS_WINDOWS:
        return False, [], comando
    try:
        r = subprocess.run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        filas = _filas_tabla_winget(_decodificar_salida_consola(r.stdout))
        return True, ["   ".join(c for c in fila if c) for fila in filas], comando
    except Exception:
        return False, [], comando


def _filas_tabla_winget(texto):
    """Las filas de una tabla de winget, sin depender del idioma.

    BUG corregido: se buscaba una cabecera que empezara por "Name". Con
    winget en español la cabecera es "Nombre  Id  Versión  Disponible
    Origen", no se encontraba nunca, y la lista salía vacía como si no
    hubiera nada que actualizar. La cabecera es SIEMPRE la línea de encima
    de la de guiones; eso no se traduce."""
    lineas = [l.rstrip() for l in (texto or "").replace("\r", "").split("\n")]
    for i, linea in enumerate(lineas):
        if i > 0 and re.fullmatch(r"-{10,}", linea.strip()):
            cabecera = lineas[i - 1]
            # Inicio de cada columna = donde empieza cada palabra de la
            # cabecera. Las cabeceras de winget son de una palabra ("Nombre",
            # "Disponible"...), pero entre dos de ellas puede haber UN solo
            # espacio ("Disponible Origen"): no se puede exigir dos.
            inicios = [m.start() for m in re.finditer(r"\S+", cabecera)]
            if not inicios:
                continue
            filas = []
            for fila in lineas[i + 1:]:
                # El resumen del final ("18 upgrades available.") es más
                # corto que el inicio de la última columna: no es una fila.
                if not fila.strip() or len(fila) <= inicios[-1]:
                    continue
                filas.append([fila[a:b].strip() for a, b in zip(inicios, inicios[1:] + [None])])
            return filas
    return []


def actualizar_todo_winget(callback_progreso=None, evento_cancelar=None):
    """winget upgrade --all. Puede tardar mucho (descarga e instala cada
    una). Devuelve (exito, resumen, cancelado)."""
    return _ejecutar_reparacion_cancelable(
        ["winget", "upgrade", "--all", "--silent", "--include-unknown",
         "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"],
        timeout_seg=3 * 3600, callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)


# ---------------- Bloatware (apps preinstaladas de la Tienda) ----------------
# Solo apps que vienen de serie o que Windows instala solo para promocionar
# algo. Nunca: Tienda, Fotos, Calculadora, Bloc de notas, Terminal, Recortes,
# Xbox ni sus servicios (los juegos de Game Pass dependen de ellos),
# códecs, ni el propio motor de apps. Prefijos de PackageFamilyName.
BLOATWARE = {
    "king.com.": "bloat_juegos_promocion",              # Candy Crush y compañía
    "Microsoft.MicrosoftSolitaireCollection": "bloat_juegos_promocion",
    "Microsoft.BingNews": "bloat_noticias",
    "Microsoft.BingWeather": "bloat_noticias",
    "Microsoft.BingFinance": "bloat_noticias",
    "Microsoft.BingSports": "bloat_noticias",
    "Microsoft.GetHelp": "bloat_ayuda",
    "Microsoft.Getstarted": "bloat_ayuda",
    "Microsoft.WindowsFeedbackHub": "bloat_ayuda",
    "Microsoft.MicrosoftOfficeHub": "bloat_promocion",
    "Microsoft.SkypeApp": "bloat_promocion",
    "Microsoft.People": "bloat_promocion",
    "Microsoft.WindowsMaps": "bloat_promocion",
    "Microsoft.MixedReality.Portal": "bloat_promocion",
    "Microsoft.Microsoft3DViewer": "bloat_promocion",
    "Microsoft.Print3D": "bloat_promocion",
    "Microsoft.3DBuilder": "bloat_promocion",
    "Clipchamp.Clipchamp": "bloat_promocion",
    "MicrosoftCorporationII.MicrosoftFamily": "bloat_promocion",
    "Microsoft.Todos": "bloat_promocion",
    "Microsoft.PowerAutomateDesktop": "bloat_promocion",
    "SpotifyAB.SpotifyMusic": "bloat_terceros",
    "Disney.": "bloat_terceros",
    "Facebook.": "bloat_terceros",
    "BytedancePte.Ltd.TikTok": "bloat_terceros",
    "AmazonVideo.PrimeVideo": "bloat_terceros",
    "4DF9E0F8.Netflix": "bloat_terceros",
}


def listar_bloatware():
    """[{nombre, familia, paquete, categoria (clave de idiomas)}] de las
    apps de la lista que están instaladas para este usuario."""
    salida = ""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-AppxPackage | Select-Object Name, PackageFamilyName, PackageFullName, NonRemovable "
                            "| ConvertTo-Json -Compress"],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        salida = (r.stdout or "").strip()
        datos = json.loads(salida or "[]")
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    encontrados = []
    for d in datos if isinstance(datos, list) else []:
        familia = d.get("PackageFamilyName") or ""
        if d.get("NonRemovable"):
            continue
        for prefijo, categoria in BLOATWARE.items():
            if familia.startswith(prefijo):
                encontrados.append({"nombre": d.get("Name") or familia, "familia": familia,
                                    "paquete": d.get("PackageFullName") or "", "categoria": categoria})
                break
    encontrados.sort(key=lambda x: x["nombre"].lower())
    return encontrados


def quitar_bloatware(paquetes):
    """Remove-AppxPackage para cada paquete (solo para este usuario). Se
    pueden volver a instalar desde la Tienda. Devuelve (quitados, fallidos,
    comando). Solo acepta paquetes de la lista BLOATWARE: aunque alguien
    pase otro nombre, no se toca."""
    quitados, fallidos = [], []
    for p in paquetes:
        if not any(p.startswith(prefijo) for prefijo in BLOATWARE) or not re.fullmatch(r"[\w.\-~ ]+", p):
            fallidos.append(p)
            continue
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                f"Remove-AppxPackage -Package '{p}' -ErrorAction Stop"],
                               capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                               timeout=180)
            (quitados if r.returncode == 0 else fallidos).append(p)
        except Exception:
            fallidos.append(p)
    return quitados, fallidos, "Remove-AppxPackage -Package <paquete>"


# ---------------- Archivos duplicados ----------------

def buscar_duplicados(carpeta, min_bytes=1024 * 1024, presupuesto_seg=90, callback=None, evento_cancelar=None):
    """Grupos de archivos con el MISMO contenido (no solo el mismo nombre).

    En tres pasadas, de barata a cara, para no leer GB de disco sin
    necesidad: 1) agrupar por tamaño (gratis), 2) entre los de igual tamaño,
    comparar los primeros 64 KB, 3) solo los que sigan iguales, el
    contenido entero (BLAKE2). Nunca entra en enlaces ni uniones.

    Devuelve (grupos, completo). grupos = [{"bytes", "rutas"[...]}] ordenados
    por espacio desperdiciado; completo=False si se acabó el tiempo."""
    import hashlib
    inicio = time.time()
    por_tamano = {}
    completo = True
    for raiz, _dirs, archivos in _recorrer(carpeta):
        if evento_cancelar is not None and evento_cancelar.is_set() or time.time() - inicio > presupuesto_seg:
            completo = False
            break
        for a in archivos:
            ruta = os.path.join(raiz, a)
            try:
                tam = os.path.getsize(ruta)
            except OSError:
                continue
            if tam >= min_bytes:
                por_tamano.setdefault(tam, []).append(ruta)

    def huella(ruta, limite=None):
        h = hashlib.blake2b(digest_size=20)
        leidos = 0
        try:
            with open(ruta, "rb") as f:
                while True:
                    bloque = f.read(1024 * 1024 if limite is None else min(65536, limite - leidos))
                    if not bloque:
                        break
                    h.update(bloque)
                    leidos += len(bloque)
                    if limite is not None and leidos >= limite:
                        break
        except OSError:
            return None
        return h.hexdigest()

    grupos = []
    candidatos = [(tam, rutas) for tam, rutas in por_tamano.items() if len(rutas) > 1]
    for n, (tam, rutas) in enumerate(candidatos):
        if evento_cancelar is not None and evento_cancelar.is_set() or time.time() - inicio > presupuesto_seg:
            completo = False
            break
        if callback:
            try:
                callback(n + 1, len(candidatos))
            except Exception:
                pass
        parciales = {}
        for r in rutas:
            parciales.setdefault(huella(r, 65536), []).append(r)
        for clave, iguales in parciales.items():
            if clave is None or len(iguales) < 2:
                continue
            completos = {}
            for r in iguales:
                completos.setdefault(huella(r), []).append(r)
            for clave2, mismos in completos.items():
                if clave2 is not None and len(mismos) > 1:
                    grupos.append({"bytes": tam, "rutas": sorted(mismos, key=lambda x: (len(x), x))})
    grupos.sort(key=lambda g: g["bytes"] * (len(g["rutas"]) - 1), reverse=True)
    return grupos, completo


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


GALAXY_DB = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "GOG.com", "Galaxy", "storage",
                         "galaxy-2.0.db")


def _gog_registro():
    """Juegos con el instalador clásico de GOG (sin Galaxy): cada uno deja
    una clave en el registro con su nombre y su carpeta."""
    import winreg
    juegos = []
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
                            try:
                                carpeta = winreg.QueryValueEx(sub, "path")[0]
                            except OSError:
                                carpeta = ""
                            juegos.append({"id": str(subclave), "nombre": nombre, "ruta": carpeta})
                    except OSError:
                        continue
        except OSError:
            continue
    return juegos


def _gog_galaxy(ruta_db=None):
    """Juegos instalados con GOG Galaxy 2.0, que NO siempre escribe en el
    registro: su lista está en su propia base de datos SQLite.

    Se lee una COPIA: con Galaxy abierto la base está en uso, y abrir el
    original podría bloquearla. Tablas: InstalledBaseProducts (productId,
    installationPath) y LimitedDetails (productId, title). Si Galaxy cambia
    el esquema, se devuelve vacío en vez de reventar."""
    import shutil
    import sqlite3
    ruta_db = ruta_db or GALAXY_DB
    if not os.path.isfile(ruta_db):
        return []
    copia = os.path.join(tempfile.gettempdir(), f"techclean_galaxy_{os.getpid()}.db")
    juegos = []
    try:
        shutil.copy2(ruta_db, copia)
        con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        try:
            filas = con.execute(
                "SELECT i.productId, i.installationPath, d.title FROM InstalledBaseProducts i "
                "LEFT JOIN LimitedDetails d ON d.productId = i.productId").fetchall()
        finally:
            con.close()
        for producto, carpeta, titulo in filas:
            carpeta = carpeta or ""
            juegos.append({"id": str(producto), "nombre": titulo or os.path.basename(carpeta.rstrip("\\/")) or str(producto),
                           "ruta": carpeta})
    except Exception:
        return []
    finally:
        try:
            os.remove(copia)
        except OSError:
            pass
    return juegos


def _gog_carpetas_juegos():
    """Donde GOG suele instalar: la biblioteca por defecto de Galaxy y
    "GOG Games" en la raíz de cada unidad fija."""
    raices = [os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "GOG Galaxy", "Games")]
    try:
        for part in psutil.disk_partitions(all=False):
            if "fixed" in (part.opts or ""):
                raices.append(os.path.join(part.mountpoint, "GOG Games"))
    except Exception:
        pass
    return raices


def _gog_archivos_info(raices=None):
    """Cada juego de GOG deja un goggame-<id>.info (JSON) en su carpeta, con
    su nombre. Así se encuentran también los copiados de otro disco o de
    otro equipo, que no están ni en el registro ni en Galaxy. Solo se mira
    un nivel (raíz/Juego/goggame-*.info): nada de recorrer discos enteros."""
    juegos = []
    for raiz in raices if raices is not None else _gog_carpetas_juegos():
        try:
            carpetas = [e.path for e in os.scandir(raiz) if e.is_dir(follow_symlinks=False)]
        except OSError:
            continue
        for carpeta in carpetas:
            try:
                infos = [e.path for e in os.scandir(carpeta)
                         if e.is_file() and e.name.lower().startswith("goggame-") and e.name.lower().endswith(".info")]
            except OSError:
                continue
            for info in infos:
                try:
                    with open(info, encoding="utf-8-sig") as f:
                        datos = json.load(f)
                except (OSError, ValueError):
                    continue
                # Los DLC traen su propio .info con rootGameId distinto: no
                # son juegos aparte.
                if datos.get("rootGameId") and str(datos.get("rootGameId")) != str(datos.get("gameId")):
                    continue
                juegos.append({"id": str(datos.get("gameId") or ""), "nombre": datos.get("name") or os.path.basename(carpeta),
                               "ruta": carpeta})
    return juegos


def _juegos_gog(fuentes=None):
    """Junta las tres fuentes sin repetir (por id de GOG o por carpeta)."""
    if not IS_WINDOWS and fuentes is None:
        return []
    if fuentes is None:
        fuentes = []
        for f in (_gog_registro, _gog_galaxy, _gog_archivos_info):
            try:
                fuentes.append(f())
            except Exception:
                fuentes.append([])
    vistos_id, vistas_rutas = set(), set()
    resultados = []
    for fuente in fuentes:
        for j in fuente:
            ruta = os.path.normcase(os.path.normpath(j.get("ruta") or "")) if j.get("ruta") else ""
            if (j.get("id") and j["id"] in vistos_id) or (ruta and ruta in vistas_rutas):
                continue
            if j.get("id"):
                vistos_id.add(j["id"])
            if ruta:
                vistas_rutas.add(ruta)
            resultados.append({"nombre": j["nombre"], "plataforma": "GOG", "bytes": None})
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

# Se prueban en orden. Hay DOS porque la app pasó de llamarse "TechClean
# Pro" a "TechClean" y el repositorio de GitHub puede o no haberse
# renombrado todavía. Poner solo el nombre nuevo rompería el buscador de
# actualizaciones hoy mismo (da 404); poner solo el viejo obligaría a tocar
# el código el día que se renombre, y para entonces ya habrá copias
# repartidas por ahí que nunca se enterarían. Con los dos funciona antes y
# después, sin que nadie tenga que acordarse de nada.
#
# GitHub redirige del nombre viejo al nuevo al renombrar, pero solo
# mientras nadie registre un repo con el nombre que quedó libre — por eso
# no se confía en esa redirección.
REPOS_ACTUALIZACIONES = ("Hades3715/TechClean", "Hades3715/TechCleanPro")

# Se conserva porque la pantalla de Ajustes lo muestra como texto.
REPO_ACTUALIZACIONES = REPOS_ACTUALIZACIONES[-1]


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
    "escritorio_publico": "C4AA340D-F20F-4863-AFEF-F87EF2E6BA25",
    "programas": "A77F5D77-2E2B-44C3-A6A2-ABA601054A51",          # menú Inicio del usuario
    "programas_comunes": "0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8",  # menú Inicio de todos
    "arranque": "B97D20BB-F46A-4C97-BA10-5E3608430854",           # Inicio > Programas > Inicio
    "arranque_comun": "82A5EA35-D9CD-47C5-9629-E15D2F714E6E",
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


# ---------------- Accesos directos rotos (1.7.0) ----------------
# Al desinstalar un programa a veces quedan sus accesos directos en el
# Escritorio o en el menú Inicio, apuntando a algo que ya no existe. Se leen
# los .lnk a mano (formato MS-SHLLINK): es rápido y no necesita PowerShell.

_LNK_TAMANO_CABECERA = 0x4C
_LNK_CON_IDLIST, _LNK_CON_LINKINFO, _LNK_UNICODE = 0x1, 0x2, 0x80
_LNK_CON_VARIABLES, _LNK_ANUNCIADO = 0x200, 0x1000
_LNK_BLOQUE_VARIABLES, _LNK_BLOQUE_DARWIN = 0xA0000001, 0xA0000006
_UNIDAD_FIJA = 3                       # DRIVE_FIXED, en el VolumeID del .lnk


def _cadena_c(datos, inicio, unicode=False):
    """Cadena terminada en cero dentro de `datos`."""
    if inicio <= 0 or inicio >= len(datos):
        return ""
    if unicode:
        fin = inicio
        while fin + 1 < len(datos) and datos[fin:fin + 2] != b"\0\0":
            fin += 2
        return datos[inicio:fin].decode("utf-16-le", "replace")
    fin = datos.find(b"\0", inicio)
    return datos[inicio:fin if fin != -1 else len(datos)].decode("mbcs" if IS_WINDOWS else "latin-1", "replace")


def leer_destino_lnk(ruta):
    """A dónde apunta un acceso directo. Devuelve (tipo, destino):

      ("local", ruta)   — un archivo o carpeta de un disco fijo
      ("otro", None)    — algo que no se puede comprobar desde aquí: un
                          programa "anunciado" de un instalador MSI (Office),
                          una app de la Tienda, el Panel de control, una
                          unidad de red o un USB
      ("invalido", None) — no es un .lnk o está dañado

    Solo un "local" puede darse por roto: ante la duda, nunca se marca."""
    try:
        with open(ruta, "rb") as f:
            datos = f.read(1024 * 1024)
    except OSError:
        return "invalido", None
    if len(datos) < _LNK_TAMANO_CABECERA or int.from_bytes(datos[0:4], "little") != _LNK_TAMANO_CABECERA:
        return "invalido", None
    banderas = int.from_bytes(datos[0x14:0x18], "little")
    if banderas & _LNK_ANUNCIADO:
        return "otro", None
    pos = _LNK_TAMANO_CABECERA
    try:
        if banderas & _LNK_CON_IDLIST:
            pos += 2 + int.from_bytes(datos[pos:pos + 2], "little")
        destino = None
        tipo_unidad = None
        if banderas & _LNK_CON_LINKINFO:
            info = datos[pos:]
            tam_info = int.from_bytes(info[0:4], "little")
            tam_cabecera = int.from_bytes(info[4:8], "little")
            banderas_info = int.from_bytes(info[8:12], "little")
            if banderas_info & 0x1:                     # VolumeIDAndLocalBasePath
                volumen = int.from_bytes(info[12:16], "little")
                tipo_unidad = int.from_bytes(info[volumen + 4:volumen + 8], "little")
                if tam_cabecera >= 0x24:
                    base = _cadena_c(info, int.from_bytes(info[28:32], "little"), unicode=True)
                    sufijo = _cadena_c(info, int.from_bytes(info[32:36], "little"), unicode=True)
                else:
                    base = _cadena_c(info, int.from_bytes(info[16:20], "little"))
                    sufijo = _cadena_c(info, int.from_bytes(info[24:28], "little"))
                if base:
                    destino = os.path.join(base, sufijo) if sufijo else base
            pos += tam_info
        # Saltar las cadenas (nombre, ruta relativa, carpeta de trabajo,
        # argumentos, icono) para llegar a los bloques extra.
        ancho = 2 if banderas & _LNK_UNICODE else 1
        for bit in (0x4, 0x8, 0x10, 0x20, 0x40):
            if banderas & bit:
                pos += 2 + int.from_bytes(datos[pos:pos + 2], "little") * ancho
        con_variables = None
        while pos + 8 <= len(datos):
            tam = int.from_bytes(datos[pos:pos + 4], "little")
            if tam < 8:
                break
            firma = int.from_bytes(datos[pos + 4:pos + 8], "little")
            if firma == _LNK_BLOQUE_DARWIN:
                return "otro", None
            if firma == _LNK_BLOQUE_VARIABLES and banderas & _LNK_CON_VARIABLES and tam >= 0x314:
                con_variables = (_cadena_c(datos, pos + 268, unicode=True)
                                 or _cadena_c(datos, pos + 8))
            pos += tam
    except (IndexError, ValueError):
        return "invalido", None
    if con_variables:
        # Un destino con %ProgramFiles% y similares: es el que manda.
        return "local", os.path.expandvars(con_variables)
    if destino and tipo_unidad == _UNIDAD_FIJA:
        return "local", destino
    return "otro", None


def _destino_existe(destino):
    if os.path.exists(destino):
        return True
    # Un acceso creado por un programa de 32 bits con %ProgramFiles% apunta
    # a "Program Files (x86)" aunque la variable diga otra cosa.
    bajo = destino.lower()
    for a, b in (("\\program files\\", "\\program files (x86)\\"),
                 ("\\program files (x86)\\", "\\program files\\")):
        i = bajo.find(a)
        if i != -1 and os.path.exists(destino[:i] + b + destino[i + len(a):]):
            return True
    return False


def buscar_accesos_rotos(carpetas=None):
    """Accesos directos del Escritorio y del menú Inicio cuyo destino ya
    no existe. Cada uno: ruta, nombre, destino, lugar ("escritorio",
    "inicio" o "arranque", la carpeta de lo que se abre al encender) y comun (True si es de todos los usuarios: hace falta ser
    administrador para quitarlo).

    Solo se marca lo que se puede comprobar de verdad: un destino en un
    disco fijo que SÍ está conectado. Si la unidad entera no existe (un
    disco externo desenchufado), no se toca."""
    if carpetas is None:
        carpetas = [
            (carpeta_conocida("escritorio"), "escritorio", False, False),
            (carpeta_conocida("escritorio_publico"), "escritorio", True, False),
            (carpeta_conocida("programas"), "inicio", False, True),
            (carpeta_conocida("programas_comunes"), "inicio", True, True),
        ]
    rotos = []
    vistos = set()
    arranque = tuple(os.path.normcase(c) + os.sep for c in
                     (carpeta_conocida("arranque"), carpeta_conocida("arranque_comun")) if c)
    for carpeta, lugar, comun, recursivo in carpetas:
        if not carpeta or not os.path.isdir(carpeta):
            continue
        if recursivo:
            recorrido = _recorrer(carpeta)
        else:
            try:
                recorrido = [(carpeta, [], os.listdir(carpeta))]
            except OSError:
                continue
        for raiz, _, archivos in recorrido:
            for nombre in archivos:
                if not nombre.lower().endswith(".lnk"):
                    continue
                ruta = os.path.join(raiz, nombre)
                clave = os.path.normcase(ruta)
                if clave in vistos:
                    continue
                vistos.add(clave)
                tipo, destino = leer_destino_lnk(ruta)
                if tipo != "local" or not destino:
                    continue
                unidad = os.path.splitdrive(destino)[0]
                if not unidad or not os.path.exists(unidad + os.sep):
                    continue
                if not _destino_existe(destino):
                    en_arranque = bool(arranque) and os.path.normcase(ruta).startswith(arranque)
                    rotos.append({"ruta": ruta, "nombre": nombre[:-4], "destino": destino,
                                  "lugar": "arranque" if en_arranque else lugar, "comun": comun})
    rotos.sort(key=lambda r: (r["lugar"], r["nombre"].lower()))
    return rotos


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

    for repo in REPOS_ACTUALIZACIONES:
        try:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                        "User-Agent": "TechClean"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                datos = _json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue          # ese nombre de repo no existe (todavía): se prueba el siguiente

        version_remota = (datos.get("tag_name") or "").lstrip("vV")
        if not version_remota:
            return resultado
        if _version_es_mayor(version_remota, version_actual):
            resultado["hay_nueva"] = True
            resultado["version"] = version_remota
            resultado["url"] = datos.get("html_url") or f"https://github.com/{repo}/releases/latest"
            resultado["notas"] = (datos.get("body") or "").strip()[:500]
        return resultado

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
    def _explorador_vivo():
        try:
            for p in psutil.process_iter(["name"]):
                if (p.info.get("name") or "").lower() == "explorer.exe":
                    return True
        except Exception:
            pass
        return False

    # BUG corregido, y este era feo: se mataba explorer.exe, se lanzaba de
    # nuevo, y se devolvía True SIN COMPROBAR NADA. Si el arranque fallaba,
    # el usuario se quedaba sin barra de tareas, sin menú Inicio y sin
    # iconos del escritorio — mientras la app le decía que todo había ido
    # bien. Justo la situación en la que menos se puede uno permitir
    # mentir, porque para salir de ahí a mano hay que saber abrir el
    # Administrador de tareas con Ctrl+Shift+Esc y lanzar explorer desde
    # dentro, y quien usa esta app no tiene por qué saber eso.
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        time.sleep(1)
        for _intento in range(2):
            try:
                subprocess.Popen(["explorer.exe"],
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
            # Windows tarda un momento en levantarlo: se espera a verlo de
            # verdad en la lista de procesos antes de cantar victoria.
            for _ in range(10):
                time.sleep(0.4)
                if _explorador_vivo():
                    return True, comando
        return False, comando
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
    # BUG corregido: SystemParametersInfoW devuelve un valor que dice si
    # funcionó (0 = no), y no se miraba. La app daba por aplicado el cambio
    # aunque Windows lo hubiera rechazado, y el usuario se quedaba mirando
    # unas animaciones que seguían exactamente igual que antes.
    try:
        flags = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        valor_arrastre = 0 if activar_reduccion else 1
        ok_arrastre = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDRAGFULLWINDOWS, valor_arrastre, None, flags)

        info = _AnimationInfo()
        info.cbSize = ctypes.sizeof(_AnimationInfo)
        info.iMinAnimate = 0 if activar_reduccion else 1
        ok_animacion = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETANIMATION, ctypes.sizeof(_AnimationInfo), ctypes.byref(info), flags)

        # Basta con que UNA de las dos haya entrado para que se note algo;
        # decir que no se pudo cuando la mitad sí se aplicó también sería
        # mentir, solo que en el otro sentido.
        return bool(ok_arrastre or ok_animacion), comando
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
