"""
autopilot.py
Motor de optimización automática en segundo plano. Diseñado para consumir
muy pocos recursos: revisa cada varios segundos (no en bucle activo/tight loop).

Hace dos cosas:
1. Si la RAM supera un umbral configurable, libera memoria automáticamente.
2. Si detecta una ventana en pantalla completa (heurística de "juego activo"),
   le sube la prioridad de CPU mientras dura, y la revierte al salir.
"""

import os
import platform
import threading
import time

import psutil
import optimizer as opt

from idiomas import t

IS_WINDOWS = platform.system() == "Windows"

# Después de liberar RAM por pasar el umbral, no se vuelve a intentar hasta
# que pase este tiempo. BUG corregido: si tras liberar la RAM seguía por
# encima del umbral (lo normal cuando de verdad hace falta esa memoria: un
# juego, el navegador con 40 pestañas), se volvía a liberar en el tic
# siguiente, cada 8 segundos, para siempre. Cada vez fuerza a todos los
# programas a recargar de disco lo que estaban usando: era el autopiloto el
# que daba los tirones que se supone que evita.
ESPERA_TRAS_LIBERAR_SEG = 120

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32

    # Tipos declarados a mano: por defecto ctypes trata lo que devuelven
    # estas funciones como enteros de 32 bits, y en 64 bits eso recorta los
    # punteros.
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetShellWindow.restype = wintypes.HWND
    user32.GetDesktopWindow.restype = wintypes.HWND
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000
    MONITOR_DEFAULTTONEAREST = 2

    # Ventanas del propio Windows que SIEMPRE ocupan la pantalla entera y
    # nunca son un juego: el escritorio, el fondo de pantalla, la barra de
    # tareas y la vista de tareas.
    CLASES_DEL_SISTEMA = {
        "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
        "Windows.UI.Core.CoreWindow", "MultitaskingViewFrame",
        "XamlExplorerHostIslandWindow", "ForegroundStaging",
    }


def _get_foreground_fullscreen_pid():
    """PID de la app en pantalla completa, o None si no hay ninguna.

    BUG GORDO corregido. La heurística anterior era: "si la ventana activa
    mide lo mismo o más que la pantalla, es un juego". Dos falsos positivos
    graves, los dos comprobados en el equipo de pruebas:

      1. EL ESCRITORIO. Al minimizar todo, la ventana en primer plano pasa
         a ser Progman —el escritorio de Windows, dueño explorer.exe— que
         mide exactamente la pantalla. O sea: con Modo Juego encendido,
         mirar el escritorio le subía la prioridad de CPU al explorador de
         Windows, y ahí se quedaba hasta apagar el modo.

      2. CUALQUIER VENTANA MAXIMIZADA. Windows le da a una ventana
         maximizada un rectángulo un poco MÁS grande que la pantalla (los
         bordes invisibles de redimensionado se salen unos píxeles por cada
         lado), así que el navegador maximizado también contaba como
         "juego a pantalla completa".

    Ahora se piden tres cosas, y las tres a la vez:

      - Que no sea una ventana del propio Windows (escritorio, barra de
        tareas...) ni la nuestra.
      - Que NO tenga barra de título (WS_CAPTION). Esta es la que de verdad
        separa los casos: un juego a pantalla completa —o en modo ventana
        sin bordes— no tiene barra de título; una ventana maximizada
        normal sí la conserva.
      - Que cubra el monitor DONDE ESTÁ, no el principal: con dos pantallas
        de distinto tamaño, comparar siempre contra la principal daba
        cualquier cosa.
    """
    if not IS_WINDOWS:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        if hwnd in (user32.GetShellWindow(), user32.GetDesktopWindow()):
            return None

        clase = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, clase, 256)
        if clase.value in CLASES_DEL_SISTEMA:
            return None

        if user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CAPTION:
            return None                     # ventana normal, aunque esté maximizada

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(ctypes.c_void_p(monitor), ctypes.byref(info)):
            return None
        pantalla = info.rcMonitor
        cubre_todo = (rect.left <= pantalla.left and rect.top <= pantalla.top
                      and rect.right >= pantalla.right and rect.bottom >= pantalla.bottom)
        if not cubre_todo:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        valor = pid.value
        # PID 0 y 4 son del propio sistema; y tocarnos a nosotros mismos no
        # tendría ningún sentido.
        if not valor or valor in (0, 4) or valor == os.getpid():
            return None
        return valor
    except Exception:
        return None


class Autopilot:
    def __init__(self, log_callback=None, intervalo_seg=8, umbral_ram=85):
        self.activo = False
        self.intervalo_seg = intervalo_seg
        self.umbral_ram = umbral_ram
        self.log_callback = log_callback or (lambda *a, **k: None)
        self._hilo = None
        self._pid_priorizado = None
        # BUG corregido: si se activa/desactiva/activa Modo Juego muy rápido
        # seguido, el hilo viejo podía tardar hasta intervalo_seg en darse
        # cuenta de que debía parar (estaba dormido en time.sleep) — mientras
        # tanto un hilo nuevo ya arrancaba, y quedaban DOS corriendo a la vez.
        # Cada hilo ahora lleva su propio número de "generación": si ya no es
        # la generación activa, se detiene solo aunque self.activo diga True.
        self._generacion = 0
        self._ultima_liberacion = None

    def iniciar(self):
        if self.activo:
            return
        self.activo = True
        self._generacion += 1
        mi_generacion = self._generacion
        self._hilo = threading.Thread(target=self._loop, args=(mi_generacion,), daemon=True)
        self._hilo.start()

    def detener(self):
        self.activo = False
        self._restaurar_prioridad()

    def _loop(self, mi_generacion):
        while self.activo and mi_generacion == self._generacion:
            try:
                self._chequear_ram()
                self._chequear_juego()
            except Exception:
                pass
            time.sleep(self.intervalo_seg)

    def _chequear_ram(self):
        uso = psutil.virtual_memory().percent
        ahora = time.monotonic()
        if self._ultima_liberacion is not None and ahora - self._ultima_liberacion < ESPERA_TRAS_LIBERAR_SEG:
            return
        if uso >= self.umbral_ram:
            self._ultima_liberacion = ahora
            # BUG corregido: si hay un juego/app priorizado en pantalla
            # completa, se excluye de la compactación de RAM — antes podía
            # tocarse igual, causando micro-tirones justo mientras se
            # supone que el modo automático lo está protegiendo.
            excluir = {self._pid_priorizado} if self._pid_priorizado else set()
            liberado, afectados, comando = opt.trim_process_memory(exclude_pids=excluir)
            self.log_callback(
                t("auto_ram_accion"), comando,
                t("auto_ram_resultado", uso=f"{uso:.0f}", umbral=self.umbral_ram,
                  procesos=afectados, tamano=opt.format_bytes(liberado)),
                seccion=t("seccion_automatico"), exito=True,
                bytes_liberados=liberado, archivos_afectados=afectados,
            )

    def _chequear_juego(self):
        pid = _get_foreground_fullscreen_pid()
        if pid == self._pid_priorizado:
            return

        self._restaurar_prioridad()

        if pid:
            try:
                proceso = psutil.Process(pid)
                nombre = proceso.name()
                proceso.nice(psutil.HIGH_PRIORITY_CLASS)
                self._pid_priorizado = pid
                self.log_callback(
                    t("auto_juego_on_accion"),
                    f"SetPriorityClass(HIGH_PRIORITY_CLASS) sobre PID {pid}",
                    t("auto_juego_on_resultado", nombre=nombre),
                    seccion=t("seccion_automatico"), exito=True,
                )
            except Exception:
                self._pid_priorizado = None

    def _restaurar_prioridad(self):
        if self._pid_priorizado:
            try:
                proceso = psutil.Process(self._pid_priorizado)
                proceso.nice(psutil.NORMAL_PRIORITY_CLASS)
                self.log_callback(
                    t("auto_juego_off_accion"), "SetPriorityClass(NORMAL_PRIORITY_CLASS)",
                    t("auto_juego_off_resultado", pid=self._pid_priorizado),
                    seccion=t("seccion_automatico"), exito=True,
                )
            except Exception:
                pass
            self._pid_priorizado = None


class LimpiezaAutomaticaRAM:
    """Libera RAM sola en segundo plano, como Mem Reduct: cuando el uso
    pasa del umbral y, si se pide, además cada N minutos.

    BUG corregido: Ajustes decía "TechClean libera memoria sola en segundo
    plano, sin que tengas que hacer nada", y no era verdad. Eso solo lo
    hacía el autopiloto, y el autopiloto solo corre con el Modo Juego
    encendido. Con el Modo Juego apagado —lo normal— el umbral se guardaba
    y no pasaba nada nunca.

    Mientras el Modo Juego está activo, esta clase no hace nada: el
    autopiloto ya libera RAM, y lo hace EXCLUYENDO el juego. Si las dos
    actuaran, esta vaciaría la memoria del juego, que es justo lo que el
    Modo Juego evita.

    Usa el nivel "normal", nunca el profundo: vaciar la caché en espera en
    automático haría que todo se abriera más lento sin que el usuario
    supiera por qué.
    """

    def __init__(self, log_callback=None, umbral_ram=85, intervalo_min=0,
                 modo_juego_activo=None, segundos_entre_revisiones=5, leer_uso=None, liberar=None):
        self.umbral_ram = umbral_ram
        self.intervalo_min = intervalo_min
        self.log_callback = log_callback or (lambda *a, **k: None)
        self.modo_juego_activo = modo_juego_activo or (lambda: False)
        self.segundos_entre_revisiones = segundos_entre_revisiones
        # Inyectables para las pruebas, que no deben liberar RAM de verdad.
        self._leer_uso = leer_uso or (lambda: psutil.virtual_memory().percent)
        self._liberar = liberar or (lambda: opt.liberar_memoria(nivel="normal"))
        self.activo = False
        self._generacion = 0
        self._ultima_por_umbral = None
        self._ultima_periodica = time.monotonic()

    def iniciar(self):
        if self.activo:
            return
        self.activo = True
        self._generacion += 1
        # El intervalo cuenta desde que se enciende, no desde que arrancó
        # la app: si no, encenderlo tras una hora dispararía una al momento.
        self._ultima_periodica = time.monotonic()
        threading.Thread(target=self._loop, args=(self._generacion,), daemon=True).start()

    def detener(self):
        self.activo = False

    def _loop(self, mi_generacion):
        while self.activo and mi_generacion == self._generacion:
            try:
                self.revisar()
            except Exception:
                pass
            time.sleep(self.segundos_entre_revisiones)

    def revisar(self, ahora=None):
        """Un tic. Devuelve "umbral", "periodica" o None según lo que hizo.
        Separado del bucle para poder probarlo sin hilos ni esperas."""
        if self.modo_juego_activo():
            return None
        ahora = time.monotonic() if ahora is None else ahora
        uso = self._leer_uso()

        motivo = None
        en_espera = (self._ultima_por_umbral is not None
                     and ahora - self._ultima_por_umbral < ESPERA_TRAS_LIBERAR_SEG)
        if uso >= self.umbral_ram and not en_espera:
            motivo = "umbral"
            self._ultima_por_umbral = ahora
        elif self.intervalo_min and ahora - self._ultima_periodica >= self.intervalo_min * 60:
            motivo = "periodica"
        if motivo is None:
            return None
        # Cualquier liberación reinicia la cuenta del intervalo: liberar por
        # umbral y, un minuto después, otra vez porque "tocaba" no aporta.
        self._ultima_periodica = ahora

        r = self._liberar()
        if motivo == "umbral":
            texto = t("auto_ram_resultado", uso=f"{uso:.0f}", umbral=self.umbral_ram,
                      procesos=r["procesos"], tamano=opt.format_bytes(r["liberado"]))
        else:
            texto = t("auto_ram_periodica", minutos=self.intervalo_min,
                      tamano=opt.format_bytes(r["liberado"]))
        self.log_callback(t("auto_ram_accion"), r["comando"], texto,
                          seccion=t("seccion_automatico"), exito=True,
                          bytes_liberados=r["liberado"], archivos_afectados=r["procesos"])
        return motivo


# ---------------------------------------------------------------------------
# Vigilante: fugas de memoria y disco casi lleno
# ---------------------------------------------------------------------------

# Una "fuga" es un programa cuya memoria propia (privada) no para de crecer.
# Los umbrales son a propósito conservadores: un navegador que pasa de 1 a
# 1.3 GB al abrir pestañas no es una fuga, y un aviso falso enseña al
# usuario a ignorar los verdaderos.
FUGA_CRECIMIENTO_MINIMO = 500 * 1024 * 1024   # al menos 500 MB más...
FUGA_FACTOR_MINIMO = 1.5                       # ...y al menos un 50 % más que al empezar
FUGA_VENTANA_MINIMA_SEG = 30 * 60              # observado durante 30 minutos o más
FUGA_PROPORCION_SUBIDAS = 0.6                  # sube en 6 de cada 10 muestras
FUGA_MUESTRAS_MAX = 120                        # 2 horas a una muestra por minuto

# Procesos del propio Windows que crecen por diseño: "Memory Compression"
# ES la memoria comprimida de todos los demás, y crecer es su trabajo.
PROCESOS_SIN_VIGILAR = {"system", "registry", "memory compression", "system idle process",
                        "secure system", "vmmem", "vmmemwsl"}

DISCO_REAVISO_SEG = 24 * 3600                  # como mucho un aviso al día por unidad
DISCO_MARGEN_REARME = 5                        # vuelve a avisar si bajó 5 puntos y volvió a subir


def es_fuga(muestras):
    """muestras: lista de (segundos, bytes), de la más vieja a la más nueva.
    Función pura, para poder probarla con series inventadas."""
    if len(muestras) < 6:
        return False
    (t0, v0), (t1, v1) = muestras[0], muestras[-1]
    if t1 - t0 < FUGA_VENTANA_MINIMA_SEG:
        return False
    if v1 - v0 < FUGA_CRECIMIENTO_MINIMO or v1 < v0 * FUGA_FACTOR_MINIMO:
        return False
    subidas = sum(1 for (_, a), (_, b) in zip(muestras, muestras[1:]) if b > a)
    if subidas < FUGA_PROPORCION_SUBIDAS * (len(muestras) - 1):
        return False
    # Y tiene que seguir arriba AHORA: si creció y luego soltó la memoria
    # (lo que hace un juego al cambiar de nivel), no es una fuga.
    return v1 >= 0.95 * max(v for _, v in muestras)


if IS_WINDOWS:
    class _InfoProceso(ctypes.Structure):
        # SYSTEM_PROCESS_INFORMATION. winternl.h la publica con los campos
        # del principio como "Reserved1[48]"; aquí van con nombre (de las
        # cabeceras de System Informer) porque CreateTime está dentro.
        # Se comprueba contra psutil en prueba_vigilante.py.
        _fields_ = [
            ("NextEntryOffset", ctypes.c_ulong),
            ("NumberOfThreads", ctypes.c_ulong),
            ("WorkingSetPrivateSize", ctypes.c_longlong),
            ("HardFaultCount", ctypes.c_ulong),
            ("NumberOfThreadsHighWatermark", ctypes.c_ulong),
            ("CycleTime", ctypes.c_ulonglong),
            ("CreateTime", ctypes.c_longlong),
            ("UserTime", ctypes.c_longlong),
            ("KernelTime", ctypes.c_longlong),
            ("ImageNameLength", ctypes.c_ushort),
            ("ImageNameMaximumLength", ctypes.c_ushort),
            ("ImageNameBuffer", ctypes.c_void_p),
            ("BasePriority", ctypes.c_long),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
            ("HandleCount", ctypes.c_ulong),
            ("SessionId", ctypes.c_ulong),
            ("UniqueProcessKey", ctypes.c_size_t),
            ("PeakVirtualSize", ctypes.c_size_t),
            ("VirtualSize", ctypes.c_size_t),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivatePageCount", ctypes.c_size_t),
        ]


def _leer_procesos_nt():
    """Todos los procesos en UNA llamada a NtQuerySystemInformation, la
    misma que usa el Administrador de tareas.

    Por qué no psutil: para los procesos protegidos (antivirus, servicios)
    OpenProcess falla, y psutil recurre a pedir la lista ENTERA del sistema
    una vez por cada uno. Con ~330 procesos tardaba 1.6 s por muestra, cada
    minuto, en segundo plano. Así son unos milisegundos.

    Devuelve [(pid, creacion, nombre, bytes_privados)] o None si falla."""
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p,
                                               ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    ntdll.NtQuerySystemInformation.restype = ctypes.c_long
    STATUS_INFO_LENGTH_MISMATCH = ctypes.c_long(0xC0000004).value
    tamano = 512 * 1024
    for _ in range(6):
        buf = ctypes.create_string_buffer(tamano)
        necesario = ctypes.c_ulong(0)
        estado = ntdll.NtQuerySystemInformation(5, buf, tamano, ctypes.byref(necesario))   # SystemProcessInformation
        if estado == STATUS_INFO_LENGTH_MISMATCH:
            # Entre una llamada y otra pueden nacer procesos: margen de sobra.
            tamano = max(tamano * 2, necesario.value + 64 * 1024)
            continue
        if estado != 0:
            return None
        break
    else:
        return None

    procesos = []
    base = ctypes.addressof(buf)
    desplazamiento = 0
    while True:
        info = _InfoProceso.from_address(base + desplazamiento)
        pid = info.UniqueProcessId or 0
        nombre = (ctypes.wstring_at(info.ImageNameBuffer, info.ImageNameLength // 2)
                  if info.ImageNameBuffer and info.ImageNameLength else "")
        procesos.append((pid, info.CreateTime, nombre, info.PagefileUsage))
        if not info.NextEntryOffset:
            break
        desplazamiento += info.NextEntryOffset
    return procesos


def _leer_procesos():
    """[(pid, momento_de_creacion, nombre, bytes_privados)]. Memoria PRIVADA
    y no la del working set: el working set baja cada vez que TechClean
    libera RAM, y una fuga parecería curarse sola cada pocos minutos."""
    if IS_WINDOWS:
        try:
            rapidos = _leer_procesos_nt()
        except Exception:
            rapidos = None
        if rapidos:
            return rapidos
    procesos = []
    for p in psutil.process_iter(["pid", "name", "create_time", "memory_info"]):
        info = p.info
        mi = info.get("memory_info")
        if mi is None:
            continue
        privada = getattr(mi, "private", None) or getattr(mi, "vms", 0)
        procesos.append((info["pid"], info.get("create_time") or 0, info.get("name") or "?", privada))
    return procesos


def _leer_discos():
    """[(unidad, porcentaje_usado, bytes_libres)] de las unidades fijas."""
    discos = []
    for part in psutil.disk_partitions(all=False):
        if "fixed" not in (part.opts or "") and IS_WINDOWS:
            continue
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        discos.append((part.mountpoint.rstrip("\\"), uso.percent, uso.free))
    return discos


class Vigilante:
    """Mira en segundo plano dos cosas que el usuario no suele vigilar y
    avisa con una notificación de Windows:

    - Un programa con una fuga de memoria (su memoria privada no para de
      crecer). Mem Reduct no lo hace: liberar RAM a un programa con fuga
      solo esconde el problema unos minutos.
    - Una unidad casi llena, con el mismo umbral que el semáforo de Inicio.

    Una muestra por minuto: leer la memoria de ~200 procesos cuesta unos
    milisegundos. Los discos, cada 10 muestras.
    """

    def __init__(self, log_callback=None, notificar=None, avisar_fugas=None, avisar_disco=None,
                 umbral_disco=None, segundos_entre_muestras=60, leer_procesos=None, leer_discos=None,
                 avisos_disco_guardados=None, guardar_avisos_disco=None):
        self.log_callback = log_callback or (lambda *a, **k: None)
        self.notificar = notificar or opt.notificar_windows
        self.avisar_fugas = avisar_fugas or (lambda: True)
        self.avisar_disco = avisar_disco or (lambda: True)
        self.umbral_disco = umbral_disco or (lambda: 85)
        self.segundos_entre_muestras = segundos_entre_muestras
        self._leer_procesos = leer_procesos or _leer_procesos
        self._leer_discos = leer_discos or _leer_discos
        self.activo = False
        self._generacion = 0
        # (pid, creacion) -> {"nombre", "muestras": [(t, bytes)]}. La clave
        # lleva el momento de creación porque Windows recicla los PID: sin
        # eso, un programa nuevo heredaría la historia de uno ya cerrado.
        self._historial = {}
        self._fugas_avisadas = set()
        # {unidad: hora (time.time) del último aviso}. Se GUARDA en disco: la
        # app arranca con Windows, y en memoria "una vez al día" era en
        # realidad "una vez cada vez que se enciende el equipo".
        self._disco_avisado = dict(avisos_disco_guardados or {})
        self._guardar_avisos_disco = guardar_avisos_disco or (lambda avisos: None)
        # Lo que la interfaz puede consultar: {pid: {"nombre", "crecimiento", "actual", "minutos"}}
        self.fugas = {}

    def iniciar(self):
        if self.activo:
            return
        self.activo = True
        self._generacion += 1
        threading.Thread(target=self._loop, args=(self._generacion,), daemon=True).start()

    def detener(self):
        self.activo = False

    def _loop(self, mi_generacion):
        vuelta = 0
        while self.activo and mi_generacion == self._generacion:
            try:
                self.revisar_fugas()
                # El disco, cada 10 vueltas y NO en la primera: al encender el
                # equipo ya hay bastante en pantalla como para sumar un aviso
                # en el primer segundo.
                if vuelta % 10 == 9:
                    self.revisar_discos()
            except Exception:
                pass
            vuelta += 1
            time.sleep(self.segundos_entre_muestras)

    # ---------------- Fugas ----------------
    def revisar_fugas(self, ahora=None):
        """Toma una muestra y devuelve la lista de fugas NUEVAS avisadas."""
        if not self.avisar_fugas():
            # Apagado: se olvida todo, para no avisar con datos de hace
            # horas al volver a encenderlo.
            self._historial.clear()
            self.fugas = {}
            return []
        ahora = time.monotonic() if ahora is None else ahora
        vivos = set()
        nuevas = []
        fugas = {}
        for pid, creacion, nombre, privada in self._leer_procesos():
            if pid in (0, 4) or nombre.lower().removesuffix(".exe") in PROCESOS_SIN_VIGILAR:
                continue
            clave = (pid, creacion)
            vivos.add(clave)
            entrada = self._historial.setdefault(clave, {"nombre": nombre, "muestras": []})
            muestras = entrada["muestras"]
            muestras.append((ahora, privada))
            if len(muestras) > FUGA_MUESTRAS_MAX:
                del muestras[0]
            if es_fuga(muestras):
                datos = {"nombre": nombre, "crecimiento": muestras[-1][1] - muestras[0][1],
                         "actual": muestras[-1][1], "minutos": int((muestras[-1][0] - muestras[0][0]) / 60)}
                fugas[pid] = datos
                if clave not in self._fugas_avisadas:
                    self._fugas_avisadas.add(clave)
                    nuevas.append(datos)
        # Procesos que ya no existen: fuera, o el diccionario crece sin fin.
        for clave in list(self._historial):
            if clave not in vivos:
                del self._historial[clave]
        self._fugas_avisadas &= vivos
        self.fugas = fugas

        for f in nuevas:
            texto = t("vig_fuga_msg", nombre=f["nombre"], crecimiento=opt.format_bytes(f["crecimiento"]),
                      minutos=f["minutos"], actual=opt.format_bytes(f["actual"]))
            mostrada = self.notificar(t("vig_fuga_titulo"), texto)
            self.log_callback(t("vig_fuga_log"), "psutil.Process.memory_info().private (1 muestra/min)",
                              texto, seccion=t("seccion_automatico"), exito=bool(mostrada))
        return nuevas

    # ---------------- Disco casi lleno ----------------
    def revisar_discos(self, ahora=None):
        """Devuelve la lista de unidades avisadas en esta revisión."""
        if not self.avisar_disco():
            return []
        # Hora de reloj, no monotonic: se guarda y tiene que valer tras reiniciar.
        ahora = time.time() if ahora is None else ahora
        umbral = self.umbral_disco()
        avisadas = []
        for unidad, porcentaje, libre in self._leer_discos():
            if porcentaje < umbral - DISCO_MARGEN_REARME:
                if self._disco_avisado.pop(unidad, None) is not None:
                    self._guardar_avisos_disco(dict(self._disco_avisado))
                continue
            if porcentaje < umbral:
                continue
            ultima = self._disco_avisado.get(unidad)
            if ultima is not None and ahora - ultima < DISCO_REAVISO_SEG:
                continue
            self._disco_avisado[unidad] = ahora
            self._guardar_avisos_disco(dict(self._disco_avisado))
            texto = t("vig_disco_msg", unidad=unidad, porcentaje=f"{porcentaje:.0f}",
                      libre=opt.format_bytes(libre))
            mostrada = self.notificar(t("vig_disco_titulo"), texto)
            self.log_callback(t("vig_disco_log"), "psutil.disk_usage()", texto,
                              seccion=t("seccion_automatico"), exito=bool(mostrada))
            avisadas.append(unidad)
        return avisadas
