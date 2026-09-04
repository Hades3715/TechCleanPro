# -*- coding: utf-8 -*-
"""Prueba en vivo del medidor de velocidad de internet.

Corre la misma funcion que usa la ventana de la app, imprimiendo las
fases y las muestras instantaneas — sirve para comprobar de un vistazo
que la bajada Y la subida devuelven numero, que era justo lo que fallaba
de forma intermitente (la subida mandaba 10 MB fijos con 15 s de limite:
en una conexion de subida modesta eso se pasa de tiempo y salia vacia).

Uso:  python herramientas\\prueba_velocidad.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimizer as opt

ultima = {"fase": None}


def fase(codigo):
    ultima["fase"] = codigo
    print(f"\n[fase] {codigo}")


def muestra(cual, mbps):
    print(f"   {cual:7} {mbps:8.2f} Mbps", end="\r")


arranque = time.time()
r = opt.test_velocidad_internet(callback_progreso=fase, callback_muestra=muestra)
total = time.time() - arranque

print("\n\n=== RESULTADO ===")
print(f"  latencia : {r['latencia_ms']} ms")
print(f"  bajada   : {r['bajada_mbps']} Mbps")
print(f"  subida   : {r['subida_mbps']} Mbps")
print(f"  error    : {r['error']}")
print(f"  duracion : {total:.1f} s")

fallos = []
if r["bajada_mbps"] is None:
    fallos.append("sin bajada")
if r["subida_mbps"] is None:
    fallos.append("sin subida")
if total > 75:
    fallos.append(f"tardo demasiado ({total:.0f} s)")

print("\nRESULTADO: " + ("sin fallos" if not fallos else "FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
