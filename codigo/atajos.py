"""
atajos.py
Atajo de teclado GLOBAL: funciona con TechClean minimizada en la bandeja o
en mitad de un juego. Lo pidió el usuario para liberar RAM sin salir de lo
que está haciendo.

Se usa RegisterHotKey de Windows, en un hilo propio con su bucle de
mensajes. Nada de librerías tipo `keyboard`: esas instalan un gancho de
bajo nivel que ve CADA tecla que se pulsa en el equipo. Es más pesado, y es
exactamente lo que hace un keylogger, así que un antivirus lo mira con
lupa. RegisterHotKey solo se entera de la combinación registrada.

Mientras espera, el hilo está dormido dentro de GetMessageW: no gasta CPU.
"""

import platform
import threading

IS_WINDOWS = platform.system() == "Windows"

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
VK_F10 = 0x79
ID_ATAJO = 0x7EC1          # cualquier número entre 0x0000 y 0xBFFF, propio de este hilo

# clave interna -> (modificadores, tecla, texto que se enseña)
COMBINACIONES = {
    "ctrl+alt+r": (MOD_CONTROL | MOD_ALT, ord("R"), "Ctrl + Alt + R"),
    "ctrl+shift+r": (MOD_CONTROL | MOD_SHIFT, ord("R"), "Ctrl + Shift + R"),
    "ctrl+alt+f10": (MOD_CONTROL | MOD_ALT, VK_F10, "Ctrl + Alt + F10"),
}


def texto_combinacion(clave):
    return COMBINACIONES.get(clave, (0, 0, clave))[2]


class AtajoGlobal:
    """Un atajo registrado. `al_pulsar` se llama desde el hilo del atajo,
    NO desde el de la interfaz: quien lo use debe pasarlo por after(0)."""

    def __init__(self, combinacion, al_pulsar):
        self.combinacion = combinacion
        self.al_pulsar = al_pulsar
        self.activo = False
        self._hilo = None
        self._id_hilo = None

    def iniciar(self, espera=2.0):
        """Registra el atajo. True si Windows lo aceptó; False si otro
        programa ya usa esa combinación (o fuera de Windows)."""
        if self.activo:
            return True
        if not IS_WINDOWS or self.combinacion not in COMBINACIONES:
            return False
        import ctypes
        from ctypes import wintypes

        modificadores, tecla, _ = COMBINACIONES[self.combinacion]
        listo = threading.Event()
        resultado = {"ok": False}

        def bucle():
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                           wintypes.UINT, wintypes.UINT]
            self._id_hilo = ctypes.windll.kernel32.GetCurrentThreadId()
            # El atajo queda atado a ESTE hilo (hwnd=None): los WM_HOTKEY
            # llegan a su cola de mensajes, y solo él puede quitarlo.
            ok = bool(user32.RegisterHotKey(None, ID_ATAJO, modificadores | MOD_NOREPEAT, tecla))
            resultado["ok"] = ok
            listo.set()
            if not ok:
                return
            mensaje = wintypes.MSG()
            try:
                while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
                    if mensaje.message == WM_HOTKEY and mensaje.wParam == ID_ATAJO:
                        try:
                            self.al_pulsar()
                        except Exception:
                            pass
            finally:
                user32.UnregisterHotKey(None, ID_ATAJO)

        self._hilo = threading.Thread(target=bucle, daemon=True, name="TechClean-atajo")
        self._hilo.start()
        listo.wait(espera)
        self.activo = resultado["ok"]
        if not self.activo:
            self._hilo = None
        return self.activo

    def detener(self):
        """Quita el atajo: le manda WM_QUIT a su hilo, que sale del bucle y
        lo desregistra él mismo."""
        hilo, id_hilo = self._hilo, self._id_hilo
        self.activo = False
        self._hilo = None
        if hilo is None or not id_hilo or not IS_WINDOWS:
            return
        import ctypes
        ctypes.windll.user32.PostThreadMessageW(id_hilo, WM_QUIT, 0, 0)
        hilo.join(1.0)
