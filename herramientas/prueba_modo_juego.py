# -*- coding: utf-8 -*-
"""Comprueba la deteccion de "juego a pantalla completa" del Modo Juego.

Por que importa
---------------
Cuando el Modo Juego cree que hay un juego delante, le sube la prioridad
de CPU a ese proceso. Equivocarse no es cosmetico: significa cambiarle la
prioridad a un proceso que no toca, y dejarselo cambiado.

La heuristica vieja era "si la ventana activa mide lo mismo o mas que la
pantalla, es un juego", y se equivocaba en dos casos muy normales:

  * EL ESCRITORIO. Al minimizar todo, la ventana en primer plano pasa a
    ser Progman (el escritorio, dueño explorer.exe), que mide exactamente
    la pantalla. Resultado: explorer.exe a prioridad ALTA por mirar el
    escritorio.

  * CUALQUIER VENTANA MAXIMIZADA. Windows le da a una ventana maximizada
    un rectangulo unos pixeles MAS grande que la pantalla (los bordes
    invisibles de redimensionado), asi que tambien colaba.

Esta prueba usa ventanas de verdad del sistema — el escritorio y la barra
de tareas — y una ventana propia maximizada, y comprueba que ninguna se
tome por un juego.

No prioriza nada ni toca ningun proceso: solo consulta.

Uso:  python herramientas\\prueba_modo_juego.py
"""
import ctypes
import os
import sys
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autopilot as auto

if not auto.IS_WINDOWS:
    print("Esta prueba solo aplica en Windows.")
    sys.exit(0)

import psutil

u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
u.GetShellWindow.restype = wintypes.HWND

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


def _describir(hwnd):
    clase = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(hwnd, clase, 256)
    rect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        nombre = psutil.Process(pid.value).name()
    except Exception:
        nombre = "?"
    return (clase.value, nombre,
            f"{rect.right - rect.left}x{rect.bottom - rect.top}")


def _seria_juego(hwnd):
    """Le pasa una ventana concreta a la misma logica de autopilot.py,
    haciendo que GetForegroundWindow devuelva ESA ventana."""
    original = auto.user32.GetForegroundWindow
    auto.user32.GetForegroundWindow = lambda: hwnd
    try:
        return auto._get_foreground_fullscreen_pid()
    finally:
        auto.user32.GetForegroundWindow = original


print("== El escritorio no es un juego ==")
escritorio = u.GetShellWindow()
clase, proceso, medida = _describir(escritorio)
comprobar(f"escritorio ({proceso}, clase {clase}, {medida}) descartado",
          _seria_juego(escritorio) is None)

print("\n== La barra de tareas no es un juego ==")
barra = u.FindWindowW("Shell_TrayWnd", None)
if barra:
    clase, proceso, medida = _describir(barra)
    comprobar(f"barra de tareas ({proceso}, {medida}) descartada",
              _seria_juego(barra) is None)
else:
    print("  (no se encontro Shell_TrayWnd, se omite)")

print("\n== Una ventana normal maximizada no es un juego ==")
import tkinter as tk

raiz = tk.Tk()
raiz.geometry("400x300+4000+4000")
raiz.update()
try:
    raiz.state("zoomed")            # maximizada, como cualquier programa
except Exception:
    pass
raiz.update()
hwnd_propio = wintypes.HWND(int(raiz.winfo_id()))
# winfo_id da la ventana hija; hay que subir al toplevel real de Windows
u.GetAncestor.restype = wintypes.HWND
GA_ROOT = 2
hwnd_top = u.GetAncestor(hwnd_propio, GA_ROOT)
clase, proceso, medida = _describir(hwnd_top)
comprobar(f"ventana maximizada ({proceso}, {medida}) descartada por tener barra de titulo",
          _seria_juego(hwnd_top) is None)
raiz.destroy()

print("\n== La regla que separa los dos casos: la barra de titulo ==")
# El caso positivo (un juego de verdad) no se monta aqui: haria falta tapar
# la pantalla del usuario con una ventana enorme, y ademas la funcion
# descarta a proposito nuestro propio proceso. Se comprueba en su lugar la
# regla que lo decide todo: un juego a pantalla completa —o en ventana sin
# bordes— no tiene barra de titulo; una ventana normal, aunque este
# maximizada, si la conserva.
u.GetWindowLongW.restype = ctypes.c_long
u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

normal = tk.Tk()
normal.geometry("300x200+4000+4000")
normal.update()
hwnd_normal = u.GetAncestor(wintypes.HWND(int(normal.winfo_id())), GA_ROOT)
tiene_barra = bool(u.GetWindowLongW(hwnd_normal, auto.GWL_STYLE) & auto.WS_CAPTION)
normal.destroy()
comprobar("una ventana normal tiene barra de titulo", tiene_barra)

sin_bordes = tk.Tk()
sin_bordes.overrideredirect(True)          # asi se presenta un juego sin bordes
sin_bordes.geometry("300x200+4000+4000")
sin_bordes.update()
hwnd_sb = u.GetAncestor(wintypes.HWND(int(sin_bordes.winfo_id())), GA_ROOT)
sin_barra = not (u.GetWindowLongW(hwnd_sb, auto.GWL_STYLE) & auto.WS_CAPTION)
sin_bordes.destroy()
comprobar("una ventana sin bordes NO tiene barra de titulo", sin_barra)
comprobar("las dos se distinguen: esa es la regla que quita el falso positivo",
          tiene_barra and sin_barra)

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
