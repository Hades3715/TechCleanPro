# -*- coding: utf-8 -*-
"""Comprueba la liberacion de RAM (optimizer.liberar_memoria).

Por que importa
---------------
Desde la 1.6.0 la RAM se libera con NtSetSystemInformation, como Mem
Reduct, y no solo proceso por proceso. Esa API no esta en MSDN: las
constantes y la estructura salen de las cabeceras de System Informer. Si
una estuviera mal, Windows no se queja: devuelve un codigo de error y la
app seguiria diciendo "liberado" con el numero del metodo viejo. Una
funcion que no da error no es una funcion que funcione.

Lo que se comprueba
-------------------
Siempre (con o sin administrador):
  * Que las estructuras midan lo que mide la de Windows en 64 bits.
  * Que nunca lance y devuelva todas las claves.
  * Que con un proceso EXCLUIDO (el juego del Modo Juego) NO se use ninguna
    orden de sistema: esas vacian todos los procesos sin excepcion.
  * Que trim_process_memory conserve su firma de tres valores, porque la
    usan ocho sitios de la app.

Solo como administrador (sin admin no hay privilegios que probar):
  * Que los dos privilegios se activen de verdad.
  * Que la lectura de listas cuadre: libre + en espera tiene que parecerse
    a la memoria DISPONIBLE de GlobalMemoryStatusEx. Si la estructura
    estuviera mal declarada, saldrian numeros absurdos.
  * Que el nivel normal llegue a la memoria del sistema y cada paso mire
    su NTSTATUS.
  * Con --profunda: que la cache en espera baje de verdad. No va en el
    banco normal porque vacia la cache de disco del equipo.

Uso:  python herramientas/prueba_memoria.py [--profunda]
      (como administrador para la parte completa)
"""
import ctypes
import struct
import sys

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


if not opt.IS_WINDOWS:
    print("Solo tiene sentido en Windows.")
    sys.exit(0)

print("== Estructuras ==")
if struct.calcsize("P") == 8:
    comprobar(ctypes.sizeof(opt._ListasMemoria) == 176,
              f"SYSTEM_MEMORY_LIST_INFORMATION mide 176 bytes ({ctypes.sizeof(opt._ListasMemoria)})")
    comprobar(ctypes.sizeof(opt._CombinarMemoria) == 24,
              f"MEMORY_COMBINE_INFORMATION_EX mide 24 bytes ({ctypes.sizeof(opt._CombinarMemoria)})")
else:
    print("  (Python de 32 bits: se salta la medida de estructuras)")

print("== Con un proceso excluido ==")
r = opt.liberar_memoria(exclude_pids={4})
claves = {"nivel", "liberado", "procesos", "pasos", "completo", "espera_antes",
          "espera_despues", "uso_antes", "uso_despues", "comando"}
comprobar(claves <= set(r), "devuelve todas las claves")
nombres = {p for p, _ in r["pasos"]}
comprobar(nombres == {"working_sets_procesos"},
          f"solo usa el metodo por proceso, nada de ordenes de sistema ({sorted(nombres)})")
comprobar(not r["completo"], "no se da por completa")

tupla = opt.trim_process_memory(exclude_pids={4})
comprobar(isinstance(tupla, tuple) and len(tupla) == 3, "trim_process_memory devuelve 3 valores")

if not opt.is_admin():
    print("== Sin administrador ==")
    r = opt.liberar_memoria()
    comprobar(not r["completo"], "sin admin no presume de liberacion completa")
    comprobar(opt.estado_listas_memoria() is None, "sin admin no inventa el estado de las listas")
    print("\n(Para la parte completa, abre una terminal como administrador y repite.)")
else:
    print("== Como administrador ==")
    comprobar(opt._activar_privilegio("SeProfileSingleProcessPrivilege"), "SeProfileSingleProcessPrivilege activo")
    comprobar(opt._activar_privilegio("SeIncreaseQuotaPrivilege"), "SeIncreaseQuotaPrivilege activo")

    listas = opt.estado_listas_memoria()
    comprobar(listas is not None, "se leen las listas de memoria")
    if listas:
        import psutil
        disponible = psutil.virtual_memory().available
        suma = listas["libre"] + listas["en_espera"]
        desvio = abs(suma - disponible) / max(disponible, 1)
        comprobar(desvio < 0.15,
                  f"libre + en espera ({opt.format_bytes(suma)}) cuadra con disponible "
                  f"({opt.format_bytes(disponible)}), desvio {desvio:.0%}")

    r = opt.liberar_memoria()
    print(f"  normal: {r['uso_antes']:.0f}% -> {r['uso_despues']:.0f}%, "
          f"{opt.format_bytes(r['liberado'])}, pasos {r['pasos']}")
    comprobar(r["completo"], "el nivel normal llega a la memoria del sistema")
    for paso, ok in r["pasos"]:
        comprobar(ok, f"paso {paso}")

    if "--profunda" in sys.argv:
        r = opt.liberar_memoria(nivel="profunda")
        print(f"  profunda: {r['uso_antes']:.0f}% -> {r['uso_despues']:.0f}%, "
              f"{opt.format_bytes(r['liberado'])}, pasos {r['pasos']}")
        comprobar(r["espera_antes"] is not None and r["espera_despues"] is not None,
                  "mide la cache en espera antes y despues")
        if r["espera_antes"] is not None and r["espera_despues"] is not None:
            comprobar(r["espera_despues"] < r["espera_antes"],
                      f"la cache en espera baja ({opt.format_bytes(r['espera_antes'])} -> "
                      f"{opt.format_bytes(r['espera_despues'])})")
        pasos = dict(r["pasos"])
        comprobar(pasos.get("lista_espera"), "paso lista_espera")
        # Combinar paginas no existe antes de Windows 10: se informa, no falla.
        print(f"  (combinar paginas: {'si' if pasos.get('combinar_paginas') else 'no disponible'})")

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
