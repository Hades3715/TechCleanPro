# -*- coding: utf-8 -*-
"""Monta una pieza de la interfaz sola y guarda una captura de ELLA, para
poder revisarla a ojo.

Por que existe: el banco de pruebas comprueba comportamiento —que el historial
funcione, que los colores esten aplicados, que nada reviente— pero no puede
decir si algo se VE bien. Y para eso, hasta ahora, habia que abrir la app
entera y capturar la pantalla completa, con todo lo que la persona tuviera
abierto dentro de la imagen.

Esto hace lo contrario: crea una ventana propia con solo la pieza, la rellena
con datos de mentira pero realistas —una consola vacia no dice nada— y
recorta la captura al rectangulo exacto de esa ventana. En la imagen no entra
nada mas de lo que haya en la pantalla.

  python herramientas\\ver_a_ojo.py consola  [salida.png]
  python herramientas\\ver_a_ojo.py widget   [salida.png]

Sin nombre de archivo lo deja en la carpeta actual como ver_consola.png o
ver_widget.png.
"""
import ctypes
import json
import math
import os
import subprocess
import sys
import tempfile
import time

if len(sys.argv) < 2 or sys.argv[1] not in ("consola", "widget"):
    print(__doc__)
    sys.exit(2)

PIEZA = sys.argv[1]
DESTINO = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else f"ver_{PIEZA}.png")

# Perfil temporal: no se tocan las preferencias reales del usuario.
perfil = tempfile.mkdtemp(prefix="tc_ojo_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

# Sin esto, en una pantalla escalada (125%, 150%) la captura sale RECORTADA
# arriba a la izquierda en vez de escalada: PowerShell no es consciente del
# DPI y las coordenadas que le pasamos no son las que el usa.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
import customtkinter as ctk


def capturar(ventana, margen=0):
    """Recorta la pantalla al rectangulo de ESTA ventana, y nada mas."""
    x = ventana.winfo_rootx() - margen
    y = ventana.winfo_rooty() - margen
    ancho = ventana.winfo_width() + margen * 2
    alto = ventana.winfo_height() + margen * 2
    ps = (
        "Add-Type -AssemblyName System.Drawing; "
        f"$b = New-Object System.Drawing.Bitmap {ancho}, {alto}; "
        "$g = [System.Drawing.Graphics]::FromImage($b); "
        f"$g.CopyFromScreen({x}, {y}, 0, 0, $b.Size); "
        f'$b.Save("{DESTINO}", [System.Drawing.Imaging.ImageFormat]::Png)'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, check=False)


def bombear(raiz, veces=30):
    for _ in range(veces):
        raiz.update()
        time.sleep(0.02)


# ---------------------------------------------------------------- consola
if PIEZA == "consola":
    import main

    main.EDICION = "admin"
    raiz = ctk.CTk()
    raiz.title("TechClean - consola")
    raiz.geometry("1180x760+60+40")
    raiz.attributes("-topmost", True)
    raiz.configure(fg_color="#12141a")

    consola = main.DevConsole(raiz, on_comando=lambda t: None)
    consola.pack(fill="both", expand=True, padx=18, pady=18)

    # Una sesion de mentira, pero con las cuatro clases de linea que existen:
    # el eco de lo que se escribe, la salida normal, un exito y un error. Es
    # lo unico que permite juzgar si los colores se distinguen de verdad.
    consola.imprimir("/help", "orden", prefijo="❯ ")
    consola.imprimir("\n".join([
        "/dns          Limpia la cache DNS",
        "/estado       Foto rapida de CPU, RAM, disco, GPU y temperatura",
        "/papelera     Vacia la papelera de reciclaje",
        "/ram          Libera memoria RAM",
    ]), "info")
    consola.imprimir("/ram", "orden", prefijo="❯ ")
    consola.imprimir("Liberando memoria RAM...", "dim")
    consola.imprimir("Listo. RAM compactada en 84 procesos (412.6 MB liberados).", "ok")
    consola.log("Liberar RAM (Consola Dev)", "EmptyWorkingSet (psapi.dll)",
                "84 procesos, 412.6 MB liberados")
    consola.imprimir("/papelra", "orden", prefijo="❯ ")
    consola.imprimir('Comando no reconocido: "/papelra". Escribe /help para ver la lista.',
                     "error")
    consola.imprimir("Quizas quisiste decir:  /papelera   /reparar", "aviso")
    consola.imprimir("/estado", "orden", prefijo="❯ ")
    consola.imprimir("\n".join([
        "CPU        24%  (16 hilos)",
        "RAM        48%  (9.37 GB de 19.69 GB)",
        "Disco      57%  (204.05 GB libres)",
        "GPU        AMD Radeon(TM) Graphics  (--%)",
        "CPU temp   53 C",
        "Encendido  5 h 53 min",
        "Bateria    51%",
    ]), "info")
    consola.entry.insert(0, "/temp")

    bombear(raiz)
    raiz.after(400, lambda: (capturar(raiz), raiz.destroy()))
    raiz.mainloop()

# ---------------------------------------------------------------- widget
else:
    import widget as widget_mod

    raiz = ctk.CTk()
    raiz.geometry("620x540+80+80")
    raiz.overrideredirect(True)
    # Un panel de color liso detras: es lo que permite ver si las esquinas
    # quedaron redondeadas. Sobre el fondo oscuro de la propia app no se
    # distinguiria la curva. Y siendo un panel propio, en la captura no entra
    # el escritorio del usuario.
    raiz.configure(fg_color="#5a4a7a")
    # El panel de fondo tiene que estar TAMBIEN siempre encima. El widget lo
    # esta (es un overlay), asi que sin esto el panel se queda detras de
    # cualquier otra ventana abierta y en el margen de la captura entra un
    # trozo de lo que el usuario tenga en la pantalla — que es exactamente lo
    # que este script existe para evitar.
    raiz.attributes("-topmost", True)
    raiz.lift()
    raiz.update()

    w = widget_mod.PerformanceWidget(raiz)
    w.geometry("+160+160")
    w._toggle_expandir()
    print("esquinas redondeadas:", w._redondeada)

    # Historia con forma, para ver la minigrafica poblada en vez de plana.
    for i in range(40):
        for clave, base, amplitud in (("cpu", 45, 30), ("ram", 62, 8), ("gpu", 30, 22)):
            w._barras[clave]._historia.append(
                max(2.0, min(98.0, base + amplitud * math.sin(i / 4.0 + len(clave)))))
    for clave, valor in (("cpu", 71), ("ram", 64), ("gpu", 38)):
        w._metricas_grandes[clave].configure(text=f"{valor}%",
                                             fg=widget_mod._color(valor))
        w._barras[clave].set_valor(valor)

    bombear(raiz, 20)

    # Los textos se ponen DESPUES de bombear: el bucle de refresco del widget
    # corre cada segundo y sobreescribiria lo que pongamos antes.
    def poner_textos():
        if w.lbl_cpu:
            w.lbl_cpu.configure(text="CPU 71%", fg=widget_mod._color(71))
        if w.lbl_ram:
            w.lbl_ram.configure(text="RAM 64%", fg=widget_mod._color(64))
        if w.lbl_gpu:
            w.lbl_gpu.configure(text="GPU 38%", fg=widget_mod._color(38))
        if w.lbl_net_down:
            w.lbl_net_down.configure(text="↓" + widget_mod._formato_red(4820))
        if w.lbl_net_up:
            w.lbl_net_up.configure(text="↑" + widget_mod._formato_red(96))
        for clave, valor in (("cpu", 71), ("ram", 64), ("gpu", 38)):
            w._metricas_grandes[clave].configure(text=f"{valor}%",
                                                 fg=widget_mod._color(valor))
        w.filas_sistema["disco"][1].configure(text="Disco: 57% usado (204.05 GB libres)")
        w.filas_sistema["bateria"][1].configure(text="Bateria: 51%")
        w.filas_sistema["temp"][1].configure(text="Temperatura CPU: 53°C")
        w.filas_sistema["uptime"][1].configure(text="Encendido hace: 5h 53m")
        raiz.lift()
        w.lift()
        raiz.update_idletasks()
        raiz.update()
        time.sleep(0.25)
        raiz.update()
        # 16 px de margen: lo justo para que se vean las cuatro esquinas.
        capturar(w, margen=16)
        w.destruir()
        raiz.destroy()

    raiz.after(300, poner_textos)
    raiz.mainloop()

print("captura en", DESTINO)
