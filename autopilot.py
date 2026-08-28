"""
autopilot.py
Motor de optimización automática en segundo plano. Diseñado para consumir
muy pocos recursos: revisa cada varios segundos (no en bucle activo/tight loop).

Hace dos cosas:
1. Si la RAM supera un umbral configurable, libera memoria automáticamente.
2. Si detecta una ventana en pantalla completa (heurística de "juego activo"),
   le sube la prioridad de CPU mientras dura, y la revierte al salir.
"""

import platform
import threading
import time

import psutil
import optimizer as opt

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32


def _get_foreground_fullscreen_pid():
    """Heurística: si la ventana activa ocupa toda la pantalla, se asume juego/app fullscreen."""
    if not IS_WINDOWS:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ancho_pantalla = user32.GetSystemMetrics(0)
        alto_pantalla = user32.GetSystemMetrics(1)
        ventana_ancho = rect.right - rect.left
        ventana_alto = rect.bottom - rect.top
        es_fullscreen = ventana_ancho >= ancho_pantalla and ventana_alto >= alto_pantalla
        if not es_fullscreen:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value
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
        if uso >= self.umbral_ram:
            # BUG corregido: si hay un juego/app priorizado en pantalla
            # completa, se excluye de la compactación de RAM — antes podía
            # tocarse igual, causando micro-tirones justo mientras se
            # supone que el modo automático lo está protegiendo.
            excluir = {self._pid_priorizado} if self._pid_priorizado else set()
            liberado, afectados, comando = opt.trim_process_memory(exclude_pids=excluir)
            self.log_callback(
                "Auto-liberación de RAM", comando,
                f"RAM al {uso:.0f}% (umbral {self.umbral_ram}%) — se compactó memoria en "
                f"{afectados} procesos ({opt.format_bytes(liberado)} liberados).",
                seccion="Automático", exito=True,
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
                    "Modo juego activado",
                    f"SetPriorityClass(HIGH_PRIORITY_CLASS) sobre PID {pid}",
                    f"Se detectó pantalla completa y se priorizó '{nombre}'.",
                    seccion="Automático", exito=True,
                )
            except Exception:
                self._pid_priorizado = None

    def _restaurar_prioridad(self):
        if self._pid_priorizado:
            try:
                proceso = psutil.Process(self._pid_priorizado)
                proceso.nice(psutil.NORMAL_PRIORITY_CLASS)
                self.log_callback(
                    "Modo juego desactivado", "SetPriorityClass(NORMAL_PRIORITY_CLASS)",
                    f"Se restauró la prioridad normal del proceso {self._pid_priorizado}.",
                    seccion="Automático", exito=True,
                )
            except Exception:
                pass
            self._pid_priorizado = None
