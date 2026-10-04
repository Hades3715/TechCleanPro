# -*- coding: utf-8 -*-
"""Comprueba la liberacion automatica de RAM.

Por que importa
---------------
Dos fallos reales que esta prueba vigila:

  * Ajustes prometia liberar RAM "sola en segundo plano", pero solo lo
    hacia el autopiloto, y el autopiloto solo corre con el Modo Juego
    encendido. El ajuste se guardaba y no pasaba nada.
  * Con la RAM por encima del umbral, el autopiloto liberaba cada 8
    segundos sin parar: cada vez obliga a todos los programas a recargar
    de disco lo que usaban, que es justo el tiron que se queria evitar.

No libera RAM de verdad: el uso y la liberacion son de mentira, y el
tiempo se pasa a mano (revisar(ahora=...)), asi que no hay esperas.

Uso:  python herramientas/prueba_auto_ram.py
"""
import sys

import _rutas
_rutas.poner_en_ruta()
import autopilot as auto

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


class Falso:
    def __init__(self, uso):
        self.uso = uso
        self.liberaciones = 0
        self.juego = False
        self.registros = []

    def liberar(self):
        self.liberaciones += 1
        return {"liberado": 1024 ** 3, "procesos": 120, "comando": "falso"}

    def log(self, *args, **kwargs):
        self.registros.append(args)


def nueva(f, intervalo_min=0):
    return auto.LimpiezaAutomaticaRAM(log_callback=f.log, umbral_ram=85, intervalo_min=intervalo_min,
                                      modo_juego_activo=lambda: f.juego,
                                      leer_uso=lambda: f.uso, liberar=f.liberar)


print("== Por umbral ==")
f = Falso(uso=60)
a = nueva(f)
comprobar(a.revisar(ahora=1000) is None and f.liberaciones == 0, "por debajo del umbral no hace nada")
f.uso = 90
comprobar(a.revisar(ahora=1005) == "umbral" and f.liberaciones == 1, "al pasar el umbral libera")
comprobar(f.registros and "falso" in f.registros[0], "lo apunta en el reporte")
comprobar(a.revisar(ahora=1010) is None and f.liberaciones == 1,
          "sigue alto 5 s despues: NO vuelve a liberar enseguida")
comprobar(a.revisar(ahora=1005 + auto.ESPERA_TRAS_LIBERAR_SEG) == "umbral" and f.liberaciones == 2,
          f"pasados {auto.ESPERA_TRAS_LIBERAR_SEG} s, si")

print("== Con el Modo Juego ==")
f = Falso(uso=95)
f.juego = True
a = nueva(f)
comprobar(a.revisar(ahora=1000) is None and f.liberaciones == 0,
          "con el Modo Juego activo se aparta (el autopiloto ya libera sin tocar el juego)")

print("== Por intervalo ==")
f = Falso(uso=40)
a = nueva(f, intervalo_min=15)
a._ultima_periodica = 0
comprobar(a.revisar(ahora=14 * 60) is None, "antes de 15 min no toca")
comprobar(a.revisar(ahora=15 * 60) == "periodica" and f.liberaciones == 1, "a los 15 min libera")
comprobar(a.revisar(ahora=15 * 60 + 30) is None, "y la cuenta vuelve a empezar")
f.uso = 90
a.revisar(ahora=20 * 60)
f.uso = 40
comprobar(a.revisar(ahora=30 * 60) is None,
          "una liberacion por umbral tambien reinicia la cuenta del intervalo")

print("== Encender / apagar ==")
f = Falso(uso=40)
a = nueva(f)
a.segundos_entre_revisiones = 0.01
a.iniciar()
gen = a._generacion
a.iniciar()
comprobar(a._generacion == gen, "iniciar dos veces no arranca dos hilos")
a.detener()
comprobar(not a.activo, "detener la apaga")

print("== Autopiloto del Modo Juego: espera tras liberar ==")
llamadas = []
original = auto.opt.trim_process_memory
original_vm = auto.psutil.virtual_memory
try:
    auto.opt.trim_process_memory = lambda exclude_pids=None: (llamadas.append(1) or (0, 0, "falso"))

    class VM:
        percent = 95
    auto.psutil.virtual_memory = lambda: VM()
    p = auto.Autopilot(umbral_ram=85)
    p._chequear_ram()
    p._chequear_ram()
    p._chequear_ram()
    comprobar(len(llamadas) == 1, f"tres revisiones seguidas con RAM alta = una sola liberacion ({len(llamadas)})")
finally:
    auto.opt.trim_process_memory = original
    auto.psutil.virtual_memory = original_vm

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
