# -*- coding: utf-8 -*-
"""Comprueba que la ventana no se congele.

Por que importa
---------------
Tres fallos reales que esta prueba vigila:

  * Inicio pedia el uso de CPU con psutil.cpu_percent(interval=0.3), que
    DUERME 0.3 s, desde el hilo de la interfaz y cada 2 s: la ventana
    estaba congelada el 15 % del tiempo (clics y scroll a tirones).
  * customtkinter llama a update_idletasks() en cada dibujo de una barra
    de desplazamiento o un menu desplegable: recalcula la ventana entera y
    se encadena. Era cerca del 30 % de lo que tardaba abrir una pantalla.
  * La lista de drivers era una tarjeta por driver (hasta 300): 3 s
    congelada al cargar y otros 3 s con CADA letra del buscador.

Y de paso, la fecha de los drivers: PowerShell la manda como
'/Date(1150848000000)/' y se mostraba tal cual.

No toca el sistema: los drivers son de mentira y la ventana va fuera de
la pantalla.

Uso:  python herramientas/prueba_rendimiento.py
"""
import json
import os
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_rend_")
os.environ["APPDATA"] = perfil
os.makedirs(os.path.join(perfil, "TechClean"), exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(perfil, "TechClean", "preferencias.json"), "w", encoding="utf-8"))

import _rutas
_rutas.poner_en_ruta()
import system_monitor as sysmon
import main

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def ms(funcion):
    a = time.perf_counter()
    funcion()
    return (time.perf_counter() - a) * 1000


print("== Lecturas que hace el hilo de la interfaz ==")
sysmon.get_cpu_info()
peor = max(ms(sysmon.get_cpu_info) for _ in range(5))
comprobar(peor < 50, f"get_cpu_info no espera ({peor:.0f} ms; con interval=0.3 eran 300)")
comprobar(0 <= sysmon.get_cpu_info()["porcentaje"] <= 100, "y devuelve un porcentaje valido")

print("== Fechas de los drivers ==")
for entrada, esperado in (("/Date(1150848000000)/", "2006-06-21"),
                          ("\\/Date(1150848000000)\\/", "2006-06-21"),
                          ("20190614000000.000000+000", "2019-06-14"),
                          ("2019-06-14T00:00:00", "2019-06-14"),
                          (None, None), ("", None), ("basura", None)):
    comprobar(sysmon._fecha_cim(entrada) == esperado, f"{entrada!r} -> {esperado!r}")

print("== customtkinter sin redibujo forzado ==")
app = main.TechCleanApp()
app.geometry("1400x900+4000+4000")
for _ in range(10):
    app.update()
for clase in (main.ctk.CTkScrollbar, main.ctk.CTkOptionMenu):
    comprobar(clase._draw.__name__ == "_draw" and clase._draw.__qualname__.startswith("_sin_redibujo_forzado"),
              f"{clase.__name__}._draw esta parcheado")
barra = main.ctk.CTkScrollbar(app)
llamadas = []
barra._canvas.__dict__.pop("update_idletasks", None)
original = type(barra._canvas).update_idletasks
type(barra._canvas).update_idletasks = lambda self: llamadas.append(1)
try:
    for i in range(20):
        barra.set(i / 40, i / 40 + 0.5)
finally:
    type(barra._canvas).update_idletasks = original
comprobar(not llamadas, f"mover la barra 20 veces no recalcula la ventana ({len(llamadas)} veces)")
barra.destroy()

print("== Lista de drivers ==")
app.mostrar_drivers()
app.update()
comprobar(isinstance(app.lista_drivers, main.ctk.CTkTextbox), "es un solo cuadro de texto, no una tarjeta por driver")
app._drivers_cache = [{"nombre": f"Dispositivo {i}", "fabricante": "Intel" if i % 3 else "Realtek",
                       "version": "1.0", "fecha": "2024-01-01", "clase": "NET"} for i in range(300)]
tiempo = ms(lambda: (app._filtrar_drivers(), app.update_idletasks()))
comprobar(tiempo < 300, f"pintar 300 drivers: {tiempo:.0f} ms (antes unos 3000)")
texto = app.lista_drivers.get("1.0", "end")
comprobar(texto.count("Dispositivo") == 300, "salen los 300")

app.entry_buscar_driver.insert(0, "realtek")
tiempo = ms(lambda: (app._filtrar_drivers(), app.update_idletasks()))
comprobar(tiempo < 150, f"filtrar al escribir: {tiempo:.0f} ms (antes unos 3000 por letra)")
comprobar(app.lista_drivers.get("1.0", "end").count("Dispositivo") == 100, "el filtro deja solo los de Realtek")

app.entry_buscar_driver.delete(0, "end")
app.entry_buscar_driver.insert(0, "zzzz")
app._filtrar_drivers()
comprobar("zzzz" in app.lista_drivers.get("1.0", "end"), "sin coincidencias lo dice (no 'no se pudo leer')")
comprobar(app.lista_drivers.cget("state") == "disabled", "la lista es de solo lectura")

app._drivers_cache = [{"nombre": None, "fabricante": None}]
app.entry_buscar_driver.delete(0, "end")
app._filtrar_drivers()
comprobar(True, "datos a medias no rompen el pintado")

print("== Inicio no se congela ==")
app.mostrar_dashboard()
for _ in range(20):
    app.update()
peor = max(ms(app._refrescar_gauges) for _ in range(5))
comprobar(peor < 100, f"refrescar los indicadores: {peor:.0f} ms (antes mas de 300 cada 2 s)")

app.destroy()
print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
