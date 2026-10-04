# -*- coding: utf-8 -*-
"""Revisa los errores que la APP registró mientras corría el banco.

Por que existe
--------------
Cuando algo falla dentro de la app, la app lo atrapa, lo apunta en
ultimo_error.txt y enseña una ventana de error. Durante el banco de
pruebas esa ventana salía un instante en la pantalla y desaparecía al
cerrarse la prueba — y la prueba decía "ok", porque el error no llegaba a
ella. Asi estuvo escondido "main thread is not in main loop" 22 veces: lo
vio el desarrollador pasar por la pantalla, no el banco.

Cada prueba usa su propia carpeta de datos en %TEMP% (para no tocar las
preferencias reales), asi que los registros quedan ahi. Esto los busca.

Uso (lo hace Verificar_Todo.bat):
    python herramientas/revisar_errores_banco.py --inicio   al empezar
    python herramientas/revisar_errores_banco.py            al terminar
"""
import glob
import os
import sys
import tempfile
import time

MARCA = os.path.join(tempfile.gettempdir(), "techclean_banco_inicio.txt")

# Errores PROVOCADOS a proposito por alguna prueba: se reconocen por el
# archivo de la prueba en el traceback, nunca por el tipo de error.
PROVOCADOS = ("prueba_hilos_interfaz.py",)

if "--inicio" in sys.argv:
    with open(MARCA, "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    print("Inicio del banco apuntado.")
    sys.exit(0)

try:
    inicio = float(open(MARCA, encoding="utf-8").read().strip())
except (OSError, ValueError):
    # Sin marca se miran solo las ultimas 2 horas, para no mezclar con
    # errores viejos de otras ejecuciones.
    inicio = time.time() - 2 * 3600

patron = os.path.join(tempfile.gettempdir(), "*", "TechClean", "ultimo_error.txt")
errores = []
for ruta in glob.glob(patron):
    try:
        if os.path.getmtime(ruta) < inicio:
            continue
        contenido = open(ruta, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    for bloque in contenido.split("\n=== ")[1:]:
        if any(p in bloque for p in PROVOCADOS):
            continue
        lineas = [l for l in bloque.strip().splitlines() if l.strip()]
        # La última línea de NUESTRO código, no la de dentro de tkinter o
        # de Python: esa es la que hay que ir a mirar.
        marcos = [l.strip() for l in lineas if l.strip().startswith("File ")]
        propios = [m for m in marcos if os.sep + "codigo" + os.sep in m or "/codigo/" in m]
        sitio = (propios or marcos or ["?"])[-1]
        errores.append(f"{lineas[-1][:160]}\n      en {sitio[:200]}\n      ({ruta})")

if errores:
    print(f"{len(errores)} ERROR(ES) que la app registro durante el banco:\n")
    vistos = set()
    for e in errores:
        clave = e.split("\n")[0] + e.split("\n")[1]
        if clave in vistos:
            continue
        vistos.add(clave)
        print("  - " + e)
    sys.exit(1)
print("La app no registro ningun error inesperado durante el banco.")
sys.exit(0)
