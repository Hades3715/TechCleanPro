# -*- coding: utf-8 -*-
"""Comprueba que los bucles de refresco no se dupliquen con el uso.

El problema
-----------
Varias pantallas se refrescan solas: hacen su consulta y se vuelven a
programar. Para pararlas se comprueba si el widget de esa pantalla sigue
vivo — y eso casi siempre basta, pero deja una ventana de unos segundos.

Al salir de Componentes, el bucle viejo tiene un tic YA programado. Si el
usuario vuelve a entrar antes de que ese tic salte, se encuentra un panel
nuevo, da la comprobacion por buena y sigue vivo, sumandose al bucle que
acaba de arrancar la pantalla. Entrar y salir dos veces seguidas es de lo
mas normal, y cada ida y vuelta rapida dejaba un bucle mas corriendo para
siempre, cada uno lanzando consultas WMI cada pocos segundos.

En una app cuyo trabajo es aligerar el equipo, que se vaya cargando sola
con el uso es de lo peor que puede pasar.

Esta prueba entra y sale de Componentes varias veces MUY seguidas —
justo el caso malo— y cuenta cuantos bucles quedan vivos.

Uso:  python herramientas\\prueba_bucles.py
"""
import json
import os
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_bucles_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


app = main.TechCleanApp()
app.geometry("1200x800+4000+4000")
app.withdraw()
for _ in range(10):
    app.update()
    time.sleep(0.02)

# Se cuenta cuantas veces ARRANCA de verdad un ciclo de refresco.
ciclos = {"veces": 0}
original = app._refrescar_componentes


def espia(generacion=None):
    # Solo cuentan los tics que pasan el filtro de generacion: los que se
    # descartan no hacen ninguna consulta.
    antes = getattr(app, "_generacion_componentes", 0)
    resultado = original(generacion)
    if generacion is None or generacion == getattr(app, "_generacion_componentes", antes):
        ciclos["veces"] += 1
    return resultado


app._refrescar_componentes = espia

print("== Entrar y salir de Componentes 5 veces seguidas ==")
for vuelta in range(5):
    app.mostrar_componentes()
    for _ in range(4):
        app.update()
        time.sleep(0.02)
    app.mostrar_dashboard()          # salir enseguida, sin dar tiempo al tic
    for _ in range(4):
        app.update()
        time.sleep(0.02)

generacion_final = getattr(app, "_generacion_componentes", 0)
comprobar("cada visita estrena numero de generacion", generacion_final == 5,
          f"generacion={generacion_final}")

# Ahora se entra y se deja correr: solo el ultimo bucle debe seguir vivo.
app.mostrar_componentes()
ciclos["veces"] = 0
inicio = time.time()
while time.time() - inicio < 6:
    app.update()
    time.sleep(0.02)

# Con el intervalo de 3s + lo que tarda la consulta, en 6 segundos un solo
# bucle da 1 o 2 vueltas. Seis bucles vivos darian muchas mas.
print(f"\n  ciclos ejecutados en 6 segundos: {ciclos['veces']}")
comprobar("no hay bucles acumulados de las visitas anteriores",
          ciclos["veces"] <= 3, f"{ciclos['veces']} ciclos (un solo bucle da 1-2)")

print("\n== Al salir, el bucle se apaga ==")
app.mostrar_dashboard()
for _ in range(10):
    app.update()
    time.sleep(0.02)
ciclos["veces"] = 0
inicio = time.time()
while time.time() - inicio < 5:
    app.update()
    time.sleep(0.02)
comprobar("fuera de Componentes no se refresca nada", ciclos["veces"] == 0,
          f"{ciclos['veces']} ciclos")

app.destroy()
print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
