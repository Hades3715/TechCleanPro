# -*- coding: utf-8 -*-
"""Comprueba que cambiar un ajuste surta efecto SIN reiniciar la app.

El problema que busca
---------------------
La app carga las preferencias UNA vez al arrancar y las deja en
self.prefs. Todo el codigo lee de ahi. Cuando el usuario cambia un ajuste
se llama a prefs.guardar(), que escribe en el disco... pero si nadie
actualiza tambien self.prefs, la app sigue leyendo el valor VIEJO hasta
que se reinicie.

Es un fallo especialmente feo porque no da ningun error: el interruptor
se mueve, el ajuste queda guardado de verdad, y simplemente no pasa nada.
El usuario piensa que la funcion no sirve.

El patron correcto es:

    self.prefs["mi_ajuste"] = valor        # la copia que lee la app
    prefs.guardar({"mi_ajuste": valor})    # y el disco, para la proxima vez

Que hace
--------
Por cada prefs.guardar({...}) busca, en las lineas de alrededor, o bien
la actualizacion de self.prefs para esa misma clave, o bien una recarga
completa. Si no encuentra ninguna de las dos, avisa.

Uso:  python herramientas\\revisar_ajustes.py
"""
import io
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERCA = 12          # lineas arriba/abajo donde se acepta la actualizacion

fuente = io.open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read()
lineas = fuente.splitlines()

recargas = {i for i, l in enumerate(lineas, 1)
            if re.search(r"self\.prefs\s*=\s*prefs\.cargar\(\)", l)}

# self.prefs["clave"] = ...   y   self.prefs.update({...})
asignaciones = {}
for i, l in enumerate(lineas, 1):
    for clave in re.findall(r'self\.prefs\["([a-z_]+)"\]\s*=', l):
        asignaciones.setdefault(clave, set()).add(i)
    if "self.prefs.update(" in l:
        for clave in re.findall(r'"([a-z_]+)"', l):
            asignaciones.setdefault(clave, set()).add(i)

# Claves que la app LEE de la copia en memoria (si no la lee, da igual)
leidas = set()
for l in lineas:
    leidas |= set(re.findall(r'self\.prefs\.get\("([a-z_]+)"', l))
    leidas |= set(re.findall(r'self\.prefs\["([a-z_]+)"\]', l))

problemas = []
revisadas = 0

print("Cada ajuste que se guarda, ¿se refleja tambien en memoria?\n")
for i, l in enumerate(lineas, 1):
    for clave in re.findall(r'prefs\.guardar\(\{"([a-z_]+)"', l):
        revisadas += 1
        if clave not in leidas:
            print(f"  [n/a  ] {clave:28} linea {i}  (la app no lo lee de memoria)")
            continue
        cerca_asignacion = any(abs(j - i) <= CERCA for j in asignaciones.get(clave, ()))
        cerca_recarga = any(abs(j - i) <= CERCA for j in recargas)
        if cerca_asignacion or cerca_recarga:
            print(f"  [OK   ] {clave:28} linea {i}")
        else:
            print(f"  [FALLO] {clave:28} linea {i}  -> se guarda pero la app sigue leyendo lo viejo")
            problemas.append(f"{clave} (main.py:{i})")

print(f"\n  {revisadas} guardados revisados")
print("\nRESULTADO: " + ("sin fallos" if not problemas
                          else f"{len(problemas)} ajustes que no surten efecto hasta reiniciar"))
for p in problemas:
    print(f"    - {p}")
sys.exit(1 if problemas else 0)
