# -*- coding: utf-8 -*-
"""Reproduce el fallo que reporto un usuario al abrir la app:

    RuntimeError: main thread is not in main loop
      File "main.py", line 1152, in worker_limpieza
      File "tkinter/__init__.py", in after

Por que pasaba
--------------
En toda la app el patron para tocar la interfaz desde un hilo es
`self.after(0, ...)`. Es el patron correcto, pero tiene letra chica:
Tkinter solo acepta llamadas desde otros hilos MIENTRAS el hilo principal
esta dentro de mainloop(). Si no lo esta, revienta.

Y hay dos momentos en que no lo esta:

  * AL ARRANCAR. La primera pantalla se construye dentro de __init__, o
    sea ANTES de llamar a mainloop(). Los hilos que lanza esa pantalla ya
    estan corriendo; si alguno termina rapido, llama a after() cuando
    todavia no hay mainloop.

  * AL CERRAR. Los hilos son daemon y siguen vivos un rato despues de que
    la ventana se destruye.

Habia 89 llamadas asi. La solucion no fue tocarlas una por una —eso
garantiza que la numero 90 vuelva a estar mal— sino que TechCleanApp.after
detecta si viene de un hilo de fondo y, en ese caso, encola en vez de
tocar Tk.

Esta prueba comprueba justo eso, en los dos momentos peligrosos.

Uso:  python herramientas\\prueba_hilos_interfaz.py
"""
import json
import os
import queue
import sys
import tempfile
import threading
import time

perfil = tempfile.mkdtemp(prefix="tcp_hilos_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import main

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


# Cualquier excepcion de un hilo se apunta aqui en vez de abrir una ventana.
excepciones = []
threading.excepthook = lambda args: excepciones.append(
    f"{args.exc_type.__name__}: {args.exc_value}")

print("== 1. ANTES de mainloop: es el caso que reventaba ==")
app = main.TechCleanApp()
app.geometry("900x600+4000+4000")
app.withdraw()

# La app ya esta construida pero mainloop() NO ha arrancado: exactamente el
# momento en el que worker_limpieza llamaba a after() y explotaba.
recibido = []
listo = threading.Event()


def hilo_temprano():
    try:
        app.after(0, lambda: recibido.append("antes-de-mainloop"))
    except Exception as e:
        excepciones.append(f"{type(e).__name__}: {e}")
    listo.set()


threading.Thread(target=hilo_temprano, daemon=True).start()
listo.wait(3)
comprobar("un hilo puede llamar a after() sin mainloop, sin reventar",
          not excepciones, f"excepciones={excepciones}")

# Ahora se deja correr el bucle un momento: lo encolado debe ejecutarse.
inicio = time.time()
while not recibido and time.time() - inicio < 3:
    app.update()
    time.sleep(0.01)
comprobar("y el encargo NO se pierde: se ejecuta al arrancar el bucle",
          recibido == ["antes-de-mainloop"], f"recibido={recibido}")

print("\n== 2. Con la app en marcha: se respeta el retraso pedido ==")
marcas = []
threading.Thread(target=lambda: app.after(0, lambda: marcas.append("ya")),
                 daemon=True).start()
threading.Thread(target=lambda: app.after(300, lambda: marcas.append("tarde")),
                 daemon=True).start()
inicio = time.time()
while len(marcas) < 2 and time.time() - inicio < 4:
    app.update()
    time.sleep(0.01)
comprobar("llegan los dos encargos", len(marcas) == 2, f"marcas={marcas}")
comprobar("el inmediato va primero y el retrasado despues",
          marcas == ["ya", "tarde"], f"orden={marcas}")

print("\n== 3. Desde el hilo principal se comporta como el de siempre ==")
directo = []
identificador = app.after(10, lambda: directo.append("directo"))
comprobar("devuelve un identificador cancelable", bool(identificador),
          f"id={identificador!r}")
inicio = time.time()
while not directo and time.time() - inicio < 2:
    app.update()
    time.sleep(0.01)
comprobar("y se ejecuta", directo == ["directo"])

print("\n== 4. Un encargo que falla no para la bomba ==")
despues_del_fallo = []
threading.Thread(target=lambda: app.after(0, lambda: 1 / 0), daemon=True).start()
time.sleep(0.15)
for _ in range(30):
    app.update()
    time.sleep(0.01)
threading.Thread(target=lambda: app.after(0, lambda: despues_del_fallo.append("sigue")),
                 daemon=True).start()
inicio = time.time()
while not despues_del_fallo and time.time() - inicio < 3:
    app.update()
    time.sleep(0.01)
comprobar("los encargos siguientes se siguen atendiendo",
          despues_del_fallo == ["sigue"], f"={despues_del_fallo}")

print("\n== 5. DESPUES de cerrar: los hilos daemon siguen un rato ==")
app.destroy()
excepciones.clear()
fin = threading.Event()


def hilo_tardio():
    try:
        app.after(0, lambda: None)
    except Exception as e:
        excepciones.append(f"{type(e).__name__}: {e}")
    fin.set()


threading.Thread(target=hilo_tardio, daemon=True).start()
fin.wait(3)
comprobar("llamar a after() con la ventana ya destruida no revienta",
          not excepciones, f"excepciones={excepciones}")

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
