# -*- coding: utf-8 -*-
"""Comprueba la limpieza a fondo del disco y el borrado de cachés.

Por que importa
---------------
Borrar es lo unico de la app que no tiene vuelta atras. Y esta app ya
mintio dos veces sobre lo que borraba (cache del navegador, caches de
apps): media antes, borraba con ignore_errors y anunciaba el total aunque
la mitad estuviera bloqueada.

Lo que se comprueba, todo en una carpeta temporal propia:
  * Que NUNCA se entre en una union (junction) ni enlace: una union dentro
    de una cache puede apuntar a cualquier sitio del disco, y seguirla
    convertiria "vaciar la cache" en "vaciar lo que haya al otro lado".
  * Que un archivo abierto (bloqueado) no se cuente como liberado.
  * Que el filtro se respete (por edad, por nombre).
  * Que la carpeta en si se quede en su sitio.
  * Que limpiar_sistema ignore claves que no conoce.
  * Que la salida de sfc (UTF-16) y de DISM (OEM) se lea bien.
  * Que un comando con mucha salida no se quede colgado (el PIPE de 64 KB).

No toca ninguna carpeta del sistema.

Uso:  python herramientas/prueba_limpieza_fondo.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def escribir(ruta, kb):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(b"x" * kb * 1024)


base = tempfile.mkdtemp(prefix="techclean_prueba_fondo_")
try:
    cache = os.path.join(base, "cache")
    fuera = os.path.join(base, "fuera")
    escribir(os.path.join(cache, "a.bin"), 100)
    escribir(os.path.join(cache, "sub", "b.bin"), 50)
    escribir(os.path.join(cache, "bloqueado.bin"), 30)
    escribir(os.path.join(fuera, "importante.txt"), 10)

    print("== Uniones (junctions) ==")
    union = os.path.join(cache, "union")
    r = subprocess.run(["cmd", "/c", "mklink", "/J", union, fuera], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    hay_union = r.returncode == 0 and os.path.isdir(union)
    if not hay_union:
        print("  (no se pudo crear la union de prueba; se salta esta parte)")
    else:
        comprobar(opt._es_enlace(union), "la union se reconoce como enlace")
        comprobar(opt._medir(cache) == 180 * 1024, "medir no cuenta lo que hay al otro lado de la union")

    print("== Vaciar con un archivo bloqueado ==")
    bloqueo = open(os.path.join(cache, "bloqueado.bin"), "rb")
    try:
        liberado, borrados = opt._vaciar_contenido(cache)
    finally:
        bloqueo.close()
    comprobar(liberado == 150 * 1024, f"liberado = solo lo borrado de verdad ({liberado // 1024} KB, esperado 150)")
    comprobar(borrados == 2, f"archivos borrados = 2 ({borrados})")
    comprobar(os.path.isdir(cache), "la carpeta de la cache sigue en su sitio")
    comprobar(not os.path.exists(os.path.join(cache, "sub")), "la subcarpeta vacia se quito")
    comprobar(os.path.exists(os.path.join(fuera, "importante.txt")),
              "lo que hay al otro lado de la union NO se toco")

    print("== Filtros ==")
    viejos = os.path.join(base, "viejos")
    escribir(os.path.join(viejos, "viejo.bin"), 20)
    escribir(os.path.join(viejos, "nuevo.bin"), 20)
    hace_10_dias = time.time() - 10 * 86400
    os.utime(os.path.join(viejos, "viejo.bin"), (hace_10_dias, hace_10_dias))
    liberado, _ = opt._vaciar_contenido(viejos, opt._mas_viejo_que(3))
    comprobar(liberado == 20 * 1024 and os.path.exists(os.path.join(viejos, "nuevo.bin")),
              "el filtro por edad deja lo reciente")

    suelto = os.path.join(base, "MEMORY.DMP")
    escribir(suelto, 40)
    liberado, borrados = opt._vaciar_contenido(suelto)
    comprobar(liberado == 40 * 1024 and borrados == 1 and not os.path.exists(suelto),
              "un archivo suelto (MEMORY.DMP) tambien se limpia")

    print("== Limpiar temporales con una union dentro de %TEMP% ==")
    temp_falso = os.path.join(base, "temp_falso")
    afuera = os.path.join(base, "afuera_de_temp")
    escribir(os.path.join(temp_falso, "basura.tmp"), 10)
    escribir(os.path.join(afuera, "documento.docx"), 10)
    union_temp = os.path.join(temp_falso, "union_de_un_instalador")
    r = subprocess.run(["cmd", "/c", "mklink", "/J", union_temp, afuera], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode == 0:
        original_temp, original_win = opt.tempfile.gettempdir, opt._carpeta_windows
        opt.tempfile.gettempdir = lambda: temp_falso
        opt._carpeta_windows = lambda: os.path.join(base, "no_existe")
        try:
            liberado, borrados, _ = opt.clear_temp_files()
        finally:
            opt.tempfile.gettempdir, opt._carpeta_windows = original_temp, original_win
            os.rmdir(union_temp)
        comprobar(not os.path.exists(os.path.join(temp_falso, "basura.tmp")), "borra lo de %TEMP%")
        comprobar(os.path.exists(os.path.join(afuera, "documento.docx")),
                  "y NO lo que hay al otro lado de una union (antes si lo borraba)")
        comprobar(borrados == 1 and liberado == 10 * 1024, f"cuenta solo lo borrado ({borrados}, {liberado})")
    else:
        print("  (no se pudo crear la union de prueba; se salta esta parte)")

    print("== Categorias ==")
    claves = [c["clave"] for c in opt._categorias_limpieza_sistema()]
    comprobar(len(claves) == len(set(claves)), "las claves de categoria no se repiten")
    comprobar(opt.limpiar_sistema(["no_existe"])[:2] == (0, 0), "una clave desconocida no borra nada")
    filtro_cbs = next(c["filtro"] for c in opt._categorias_limpieza_sistema() if c["clave"] == "registros")
    comprobar(not filtro_cbs(r"C:\Windows\Logs\CBS\CBS.log") and filtro_cbs(r"C:\x\CbsPersist_2024.cab"),
              "en registros se borra CbsPersist y se respeta CBS.log")

    print("== Cache de apps ==")
    app = os.path.join(base, "app_cache")
    escribir(os.path.join(app, "x.bin"), 60)
    bloqueo = open(os.path.join(app, "x.bin"), "rb")
    try:
        liberado, _ = opt.limpiar_cache_app(app)
    finally:
        bloqueo.close()
    comprobar(liberado == 0, f"con todo bloqueado, no anuncia nada liberado ({liberado})")

    print("== Salida de consola ==")
    comprobar(opt._decodificar_salida_consola("Verificación 100%".encode("utf-16-le")) == "Verificación 100%",
              "salida UTF-16 (sfc)")
    oem = "cp%d" % __import__("ctypes").windll.kernel32.GetOEMCP()
    comprobar(opt._decodificar_salida_consola("Versión 10".encode(oem)) == "Versión 10", f"salida OEM ({oem})")
    inicio = time.time()
    exito, resumen, cancelado = opt._ejecutar_reparacion_cancelable(
        ["cmd", "/c", "for /l %i in (1,1,5000) do @echo linea de relleno para pasar de 64 KB %i"], timeout_seg=60)
    comprobar(exito and not cancelado and "5000" in resumen,
              f"200 KB de salida no cuelgan el comando ({time.time() - inicio:.1f} s)")
finally:
    # rmtree sobre la union borraria lo de fuera en Pythons viejos: se
    # quita la union primero, con rmdir, que solo quita el enlace.
    union = os.path.join(base, "cache", "union")
    if os.path.isdir(union):
        try:
            os.rmdir(union)
        except OSError:
            pass
    shutil.rmtree(base, ignore_errors=True)

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
