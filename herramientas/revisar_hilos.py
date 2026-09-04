# -*- coding: utf-8 -*-
"""Busca llamadas a la interfaz hechas DESDE UN HILO de fondo.

Por que existe esta herramienta
-------------------------------
Tkinter no es seguro fuera del hilo principal. Tocar un widget desde un
hilo de trabajo no falla siempre — falla a veces, y cuando falla lo hace
lejos del sitio del problema. Es la causa de fallos intermitentes mas
tipica de esta app, y ya se corrigio dos veces (el autopiloto, y despues
la prueba de velocidad de internet) sin que nadie se acordara de revisar
si quedaban mas sitios iguales. Quedaban cuatro.

Ademas del problema de hilos, esos mismos sitios suelen olvidarse de
comprobar que el widget siga vivo: un trabajo de fondo puede terminar
DESPUES de que el usuario cambio de pantalla, y para entonces la etiqueta
ya no existe.

La regla del proyecto es siempre la misma:

    def worker():
        resultado = algo_lento()
        self.after(0, lambda: self._actualizar_label("mi_etiqueta", resultado))

Que hace
--------
Lee el codigo sin ejecutarlo (AST):
  1. Busca las funciones que se pasan a threading.Thread(target=...)
  2. Dentro de ellas, busca llamadas a metodos tipicos de widget
     (.configure, .insert, .set, .destroy, ...)
  3. Descarta las que ya estan dentro de algo pasado a after()

Lo que reporta hay que mirarlo a mano: puede haber falsos positivos (un
.set() sobre un objeto que no es un widget, por ejemplo). Lo importante
es que no aparezcan sitios NUEVOS sin justificacion.

Uso:  python herramientas\\revisar_hilos.py
"""
import ast
import io
import os
import sys

MODULOS = ["main.py", "widget.py", "tray.py", "autopilot.py"]

# Metodos que casi siempre son de un widget de Tkinter/customtkinter.
METODOS_INTERFAZ = {
    "configure", "insert", "delete", "set", "pack", "grid", "destroy",
    "grab_set", "focus_set", "select", "deselect", "see", "state",
    "pack_forget", "grid_forget", "deiconify", "withdraw", "geometry",
}


def revisar(ruta):
    src = io.open(ruta, encoding="utf-8").read()
    arbol = ast.parse(src)
    lineas = src.splitlines()

    # 1) funciones que arrancan en un hilo
    en_hilo = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call):
            nombre = getattr(n.func, "attr", getattr(n.func, "id", ""))
            if nombre == "Thread":
                for kw in n.keywords:
                    if kw.arg == "target":
                        destino = kw.value
                        if isinstance(destino, ast.Name):
                            en_hilo.add(destino.id)
                        elif isinstance(destino, ast.Attribute):
                            en_hilo.add(destino.attr)

    # 2) tramos de codigo que YA van por after(): son los correctos
    seguros = []
    nombres_en_after = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "after":
            for arg in n.args:
                if isinstance(arg, ast.Name):
                    nombres_en_after.add(arg.id)
                elif isinstance(arg, ast.Lambda):
                    seguros.append((arg.lineno, getattr(arg, "end_lineno", arg.lineno)))
    for n in ast.walk(arbol):
        if isinstance(n, ast.FunctionDef) and n.name in nombres_en_after:
            seguros.append((n.lineno, getattr(n, "end_lineno", n.lineno)))

    def va_por_after(linea):
        return any(a <= linea <= b for a, b in seguros)

    # 3) llamadas sospechosas
    hallazgos = set()
    for n in ast.walk(arbol):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in en_hilo:
            for sub in ast.walk(n):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in METODOS_INTERFAZ and not va_por_after(sub.lineno)):
                    hallazgos.add((sub.lineno, lineas[sub.lineno - 1].strip()[:95]))
    return sorted(hallazgos), len(en_hilo)


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    total = 0
    for modulo in MODULOS:
        ruta = os.path.join(base, modulo)
        if not os.path.exists(ruta):
            continue
        hallazgos, cuantos_hilos = revisar(ruta)
        total += len(hallazgos)
        estado = "limpio" if not hallazgos else f"{len(hallazgos)} POR REVISAR"
        print(f"{modulo:14} {cuantos_hilos:2} funciones en hilo  ->  {estado}")
        for linea, texto in hallazgos:
            print(f"    {modulo}:{linea}  {texto}")

    print()
    print("RESULTADO: " + ("sin sitios pendientes" if total == 0
                           else f"{total} sitio(s) tocan la interfaz desde un hilo"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
