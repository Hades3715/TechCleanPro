# -*- coding: utf-8 -*-
"""Comprueba el vigilante: fugas de memoria y disco casi lleno.

Por que importa
---------------
Un aviso falso es peor que ninguno: ensena a ignorar los verdaderos. Por
eso lo primero que se prueba es que NO avise de lo que no es una fuga (un
programa que crece y luego suelta, uno que crece poco, uno observado poco
rato) ni de un disco una y otra vez.

Y la lectura de procesos: se hace con NtQuerySystemInformation en vez de
psutil porque psutil tardaba 1.6 s por muestra. Esa estructura no esta
documentada entera, asi que se compara contra psutil: si estuviera mal
declarada, los PID o las horas de creacion no coincidirian.

No notifica nada de verdad: la notificacion es de mentira.

Uso:  python herramientas/prueba_vigilante.py
"""
import os
import sys
import time

import _rutas
_rutas.poner_en_ruta()
import autopilot as auto
import psutil

fallos = []
MB = 1024 * 1024


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def serie(inicio_mb, fin_mb, minutos=40, ruido=False):
    """Una muestra por minuto subiendo de inicio a fin."""
    muestras = []
    for i in range(minutos + 1):
        v = inicio_mb + (fin_mb - inicio_mb) * i / minutos
        if ruido and i % 3 == 0:
            v -= 30
        muestras.append((i * 60, int(v * MB)))
    return muestras


print("== Que es y que no es una fuga ==")
comprobar(auto.es_fuga(serie(400, 1400)), "400 MB -> 1.4 GB en 40 min: fuga")
comprobar(auto.es_fuga(serie(400, 1400, ruido=True)), "con algo de ruido sigue siendo fuga")
comprobar(not auto.es_fuga(serie(400, 1400, minutos=20)), "solo 20 min observado: todavia no")
comprobar(not auto.es_fuga(serie(2000, 2400)), "crece 400 MB: por debajo del minimo")
comprobar(not auto.es_fuga(serie(3000, 3600)), "crece 600 MB pero solo un 20 %: un navegador grande, no fuga")
subir_y_bajar = serie(400, 1400)[:-5] + [(t, 500 * MB) for t, _ in serie(400, 1400)[-5:]]
comprobar(not auto.es_fuga(subir_y_bajar), "crece y luego suelta la memoria: no es fuga")
plano = [(i * 60, 800 * MB) for i in range(41)]
comprobar(not auto.es_fuga(plano), "estable: no es fuga")


class Falso:
    def __init__(self):
        self.procesos = []
        self.discos = []
        self.notificaciones = []
        self.fugas_on = True
        self.disco_on = True

    def notificar(self, titulo, mensaje):
        self.notificaciones.append((titulo, mensaje))
        return True


def vigilante(f):
    return auto.Vigilante(notificar=f.notificar, avisar_fugas=lambda: f.fugas_on,
                          avisar_disco=lambda: f.disco_on, umbral_disco=lambda: 85,
                          leer_procesos=lambda: f.procesos, leer_discos=lambda: f.discos)


print("== Vigilante: fugas ==")
f = Falso()
v = vigilante(f)
for i, (_, bytes_) in enumerate(serie(300, 1500)):
    f.procesos = [(1234, 111, "chrome.exe", bytes_), (4, 0, "System", 9000 * MB),
                  (900, 222, "Memory Compression", (300 + i * 100) * MB)]
    v.revisar_fugas(ahora=i * 60)
comprobar(len(f.notificaciones) == 1 and "chrome.exe" in f.notificaciones[0][1],
          f"avisa una sola vez, de chrome.exe ({len(f.notificaciones)})")
comprobar(1234 in v.fugas and 900 not in v.fugas, "Memory Compression no se vigila (crecer es su trabajo)")
for i in range(41, 45):
    v.revisar_fugas(ahora=i * 60)
comprobar(len(f.notificaciones) == 1, "no repite el aviso del mismo programa")

f.procesos = [(1234, 999, "otro.exe", 300 * MB)]
v.revisar_fugas(ahora=46 * 60)
comprobar(1234 not in v.fugas and len(v._historial) == 1,
          "PID reutilizado por otro programa: no hereda la historia del anterior")

f.fugas_on = False
v.revisar_fugas(ahora=47 * 60)
comprobar(v._historial == {} and v.fugas == {}, "apagado: olvida todo")

print("== Vigilante: disco ==")
f = Falso()
v = vigilante(f)
f.discos = [("C:", 90.0, 20 * 1024 * MB), ("D:", 40.0, 500 * 1024 * MB)]
comprobar(v.revisar_discos(ahora=0) == ["C:"], "avisa de C: (90 %) y no de D: (40 %)")
comprobar(v.revisar_discos(ahora=3600) == [], "una hora despues no repite")
comprobar(v.revisar_discos(ahora=25 * 3600) == ["C:"], "al dia siguiente, si sigue lleno, si")
f.discos = [("C:", 78.0, 0)]
v.revisar_discos(ahora=26 * 3600)
f.discos = [("C:", 88.0, 0)]
comprobar(v.revisar_discos(ahora=27 * 3600) == ["C:"],
          "si se limpio por debajo del umbral y se volvio a llenar, avisa aunque no haya pasado un dia")
f.disco_on = False
f.discos = [("C:", 99.0, 0)]
comprobar(v.revisar_discos(ahora=60 * 3600) == [], "apagado: no avisa")

print("== Disco: el aviso sobrevive a reiniciar la app ==")
guardado = {}
f = Falso()
f.discos = [("C:", 92.0, 0)]
v = auto.Vigilante(notificar=f.notificar, umbral_disco=lambda: 85, leer_discos=lambda: f.discos,
                   leer_procesos=lambda: [], guardar_avisos_disco=guardado.update)
v.revisar_discos(ahora=1000)
comprobar(guardado.get("C:") == 1000, "al avisar, guarda la hora")
# "Reinicio": un vigilante nuevo con lo guardado.
f2 = Falso()
f2.discos = f.discos
v2 = auto.Vigilante(notificar=f2.notificar, umbral_disco=lambda: 85, leer_discos=lambda: f2.discos,
                    leer_procesos=lambda: [], avisos_disco_guardados=dict(guardado))
comprobar(v2.revisar_discos(ahora=1000 + 3 * 3600) == [] and not f2.notificaciones,
          "tras reiniciar 3 h despues no vuelve a avisar")
comprobar(v2.revisar_discos(ahora=1000 + 25 * 3600) == ["C:"], "al dia siguiente si")

print("== Dias sin reiniciar (1.7.0) ==")
DIA = 86400
avisos = []
guardado = {}
arranque = [1_000_000.0]
v3 = auto.Vigilante(notificar=lambda titulo, texto: avisos.append(texto) or True,
                    leer_arranque=lambda: arranque[0], dias_reinicio=lambda: 7,
                    guardar_aviso_reinicio=lambda a: guardado.update(a))
comprobar(not v3.revisar_reinicio(ahora=arranque[0] + 6 * DIA), "6 dias encendido: no avisa")
comprobar(v3.revisar_reinicio(ahora=arranque[0] + 8 * DIA) and len(avisos) == 1, "8 dias: avisa")
comprobar("8" in avisos[-1], f"el aviso dice cuantos dias ({avisos[-1][:40]}...)")
comprobar(not v3.revisar_reinicio(ahora=arranque[0] + 9 * DIA), "un dia despues, sin reiniciar: no repite")
comprobar(v3.revisar_reinicio(ahora=arranque[0] + 11.5 * DIA), "a los 3 dias del aviso, si lo repite")
comprobar(guardado.get("arranque") == int(arranque[0]), "lo guarda para no repetir al abrir la app de nuevo")
v4 = auto.Vigilante(notificar=lambda *a: avisos.append("x") or True, leer_arranque=lambda: arranque[0],
                    aviso_reinicio_guardado=dict(guardado))
comprobar(not v4.revisar_reinicio(ahora=arranque[0] + 12 * DIA),
          "tras cerrar y abrir la app el mismo arranque: no repite el aviso de hace un rato")
arranque[0] += 20 * DIA      # reinició y ha pasado poco
comprobar(not v3.revisar_reinicio(ahora=arranque[0] + DIA), "despues de reiniciar: no avisa")
v5 = auto.Vigilante(notificar=lambda *a: avisos.append("x") or True, leer_arranque=lambda: arranque[0],
                    avisar_reinicio=lambda: False)
comprobar(not v5.revisar_reinicio(ahora=arranque[0] + 30 * DIA), "apagado en Ajustes: no avisa nunca")
comprobar(v3.dias_encendido(ahora=arranque[0] + 2.5 * DIA) == 2.5, "dias_encendido cuenta bien")

print("== Limite de carga de la bateria (1.7.0) ==")
avisos_carga = []
bateria = [(70, True)]
v6 = auto.Vigilante(notificar=lambda titulo, texto: avisos_carga.append(texto) or True,
                    avisar_carga=lambda: True, limite_carga=lambda: 80, leer_bateria=lambda: bateria[0])
pasos = [((70, True), False, "cargando al 70 %: nada"),
         ((80, True), True, "llega al 80 % enchufada: avisa"),
         ((84, True), False, "sigue cargando: no repite"),
         ((100, True), False, "ni al 100 %"),
         ((78, True), False, "baja un poco sin desenchufar: no rearma todavia"),
         ((81, True), False, "y por eso no vuelve a avisar"),
         ((81, False), False, "desenchufa: rearma"),
         ((82, True), True, "vuelve a enchufar por encima del limite: avisa otra vez")]
for estado, espera, texto in pasos:
    bateria[0] = estado
    comprobar(v6.revisar_carga() == espera, texto)
v7 = auto.Vigilante(notificar=lambda *a: avisos_carga.append("x") or True, avisar_carga=lambda: True,
                    leer_bateria=lambda: None)
comprobar(not v7.revisar_carga(), "sin bateria (sobremesa): no hace nada")
v8 = auto.Vigilante(notificar=lambda *a: avisos_carga.append("x") or True, leer_bateria=lambda: (95, True))
comprobar(not v8.revisar_carga(), "de fabrica viene apagado")
real = auto._leer_bateria()
comprobar(real is None or (0 <= real[0] <= 100 and isinstance(real[1], bool)),
          f"la lectura real tiene buena forma ({real})")

print("== Lectura rapida de procesos (contra psutil) ==")
if auto.IS_WINDOWS:
    inicio = time.perf_counter()
    rapidos = auto._leer_procesos_nt()
    ms = (time.perf_counter() - inicio) * 1000
    comprobar(rapidos is not None and len(rapidos) > 20, f"lee {len(rapidos or [])} procesos")
    comprobar(ms < 300, f"tarda poco ({ms:.0f} ms; psutil tardaba ~1600)")
    if rapidos:
        pids_nt = {p[0] for p in rapidos}
        pids_ps = set(psutil.pids())
        comun = len(pids_nt & pids_ps) / max(len(pids_ps), 1)
        comprobar(comun > 0.9, f"los PID coinciden con psutil ({comun:.0%})")
        yo = next((p for p in rapidos if p[0] == os.getpid()), None)
        comprobar(yo is not None and yo[2].lower() == "python.exe" or (yo and yo[2]),
                  f"se encuentra a si mismo con nombre ({yo[2] if yo else None})")
        if yo:
            # CreateTime es FILETIME: centenas de ns desde 1601.
            creacion = yo[1] / 1e7 - 11644473600
            comprobar(abs(creacion - psutil.Process().create_time()) < 1,
                      "la hora de creacion coincide con psutil (la estructura esta bien declarada)")
            privada_ps = psutil.Process().memory_info().private
            comprobar(abs(yo[3] - privada_ps) < 64 * MB,
                      f"memoria privada parecida a psutil ({yo[3] // MB} MB vs {privada_ps // MB} MB)")

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
