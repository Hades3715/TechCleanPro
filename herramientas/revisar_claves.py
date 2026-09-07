# -*- coding: utf-8 -*-
"""Compara las claves que LEE la interfaz con las que ESCRIBE cada consulta.

Por que
-------
La interfaz accede a los datos con corchetes: entrada["nombre"],
disco["porcentaje"], cpu["temperatura_c"]... 130 sitios en total. Si una
funcion de optimizer.py o system_monitor.py deja de poner una clave, o la
escribe con otro nombre, la pantalla revienta con un KeyError en el equipo
del usuario — y solo en la pantalla concreta que la usa, que puede tardar
semanas en abrirse.

No hace falta reescribir los 130 accesos a .get(): basta con comprobar que
lo que se lee coincide con lo que se escribe. Eso es lo que hace esto.

Como
----
1. Recorre optimizer.py y system_monitor.py y apunta, por cada funcion,
   que claves literales mete en los diccionarios que devuelve.
2. Recorre main.py y apunta que claves literales lee.
3. Avisa de las que se leen y nadie escribe nunca.

Los falsos positivos son posibles (claves de diccionarios internos de la
propia interfaz), asi que lo que importa es que la lista no CREZCA.

Uso:  python herramientas\\revisar_claves.py
"""
import ast
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTORES = ["optimizer.py", "system_monitor.py", "privacy.py", "report.py",
               "preferences.py", "deshacer.py", "tecnico.py"]
CONSUMIDOR = "main.py"


def claves_escritas(rutas):
    """Todas las claves literales que aparecen construyendo diccionarios."""
    escritas = set()
    for nombre in rutas:
        ruta = os.path.join(BASE, nombre)
        if not os.path.exists(ruta):
            continue
        arbol = ast.parse(io.open(ruta, encoding="utf-8").read())
        for n in ast.walk(arbol):
            # {"clave": valor}
            if isinstance(n, ast.Dict):
                for k in n.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        escritas.add(k.value)
            # d["clave"] = valor
            elif isinstance(n, ast.Assign):
                for destino in n.targets:
                    if (isinstance(destino, ast.Subscript)
                            and isinstance(destino.slice, ast.Constant)
                            and isinstance(destino.slice.value, str)):
                        escritas.add(destino.slice.value)
            # dict(clave=valor)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "dict":
                for kw in n.keywords:
                    if kw.arg:
                        escritas.add(kw.arg)
            # .get("clave") / .setdefault("clave")
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in ("get", "setdefault") and n.args
                  and isinstance(n.args[0], ast.Constant)
                  and isinstance(n.args[0].value, str)):
                escritas.add(n.args[0].value)
    return escritas


def claves_leidas(nombre):
    """Claves literales que la interfaz lee con corchetes, y donde."""
    ruta = os.path.join(BASE, nombre)
    fuente = io.open(ruta, encoding="utf-8").read()
    arbol = ast.parse(fuente)
    lineas = fuente.splitlines()
    leidas = {}
    for n in ast.walk(arbol):
        if (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, str)):
            # Solo lecturas sobre algo que parece un dato (no self.algo["x"]
            # de estructuras internas de la propia ventana).
            base = n.value
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                    and base.value.id == "self":
                continue
            leidas.setdefault(n.slice.value, []).append(
                (n.lineno, lineas[n.lineno - 1].strip()[:80]))
    return leidas


escritas = claves_escritas(PRODUCTORES)
# La propia interfaz tambien construye diccionarios que luego lee.
escritas |= claves_escritas([CONSUMIDOR])
leidas = claves_leidas(CONSUMIDOR)

print(f"claves que escriben los modulos de datos : {len(escritas)}")
print(f"claves que lee la interfaz               : {len(leidas)}")

huerfanas = {k: v for k, v in leidas.items() if k not in escritas}

print()
if not huerfanas:
    print("RESULTADO: sin claves huerfanas — todo lo que la interfaz lee, alguien lo escribe.")
else:
    print(f"{len(huerfanas)} CLAVES QUE SE LEEN Y NADIE ESCRIBE:")
    for clave, sitios in sorted(huerfanas.items()):
        print(f"\n  {clave!r}")
        for ln, texto in sitios[:3]:
            print(f"      main.py:{ln}  {texto}")

sys.exit(1 if huerfanas else 0)
