# -*- coding: utf-8 -*-
"""Comprueba el analisis de Wi-Fi y la prueba de velocidad del disco (1.7.0).

Por que importa
---------------
  * Wi-Fi: se lee con la API nativa (wlanapi.dll) declarando sus
    estructuras a mano. Si un campo estuviera mal declarado, los numeros
    saldrian corridos (una senal de 3000 %, un canal 0). Aqui se comprueba
    el tamano de las estructuras contra el de la documentacion de Windows
    y que lo leido tenga sentido. Y el veredicto: que no culpe al Wi-Fi de
    algo que esta bien, ni lo de por bueno cuando no lo esta.
  * Disco: la prueba anterior leia desde la cache de la RAM y daba miles
    de MB/s en cualquier disco. Ahora usa FILE_FLAG_NO_BUFFERING. Se
    comprueba que no deje el archivo de prueba, que los numeros sean de un
    disco y no de la RAM, y que un error se diga en vez de reventar.

Escribe 64 MB en %TEMP% (y los borra). No cambia nada del Wi-Fi.

Uso:  python herramientas/prueba_wifi_disco.py
"""
import ctypes
import glob
import os
import sys
import tempfile

import _rutas
_rutas.poner_en_ruta()
import idiomas
idiomas.establecer_idioma("es")
import system_monitor as sysmon
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== Wi-Fi: estructuras de la API de Windows ==")
if sysmon.IS_WINDOWS:
    # Tamanos de wlanapi.h en 64 bits. Si no cuadran, todo lo que viene
    # detras de un campo mal puesto se lee corrido.
    for estructura, esperado in ((sysmon._WLAN_BSS_ENTRY, 360), (sysmon._WLAN_INTERFACE_INFO, 532),
                                 (sysmon._WLAN_CONNECTION_ATTRIBUTES, 604)):
        tam = ctypes.sizeof(estructura)
        comprobar(tam == esperado, f"{estructura.__name__}: {tam} bytes (esperado {esperado})")

print("== Wi-Fi: bandas y canales ==")
for args, esperado in (((1, None), "2.4"), ((11, None), "2.4"), ((36, None), "5"), ((157, None), "5"),
                       ((None, 2437), "2.4"), ((None, 5785), "5"), ((5, 5975), "6"), ((None, None), None)):
    comprobar(sysmon.banda_wifi(*args) == esperado, f"banda_wifi{args} -> {esperado}")
for mhz, canal in ((2412, 1), (2437, 6), (2462, 11), (2484, 14), (5180, 36), (5785, 157), (5975, 5), (0, None)):
    comprobar(sysmon.canal_wifi(mhz) == canal, f"{mhz} MHz -> canal {canal}")

print("== Wi-Fi: veredicto ==")
bien = {"rssi": -50, "senal": 90, "banda": "5", "redes_mismo_canal": 1, "velocidad_mbps": 866}
comprobar(sysmon.veredicto_wifi(bien) == ("bien", []), "buena senal en 5 GHz: bien, sin motivos")
nivel, motivos = sysmon.veredicto_wifi(dict(bien, rssi=-80))
comprobar(nivel == "mal" and "wifi_mot_senal_mala" in motivos, "-80 dBm: mal, por la senal")
nivel, motivos = sysmon.veredicto_wifi(dict(bien, rssi=-70))
comprobar(nivel == "regular" and motivos == ["wifi_mot_senal_regular"], "-70 dBm: regular")
nivel, motivos = sysmon.veredicto_wifi(dict(bien, banda="2.4", redes_mismo_canal=6))
comprobar(nivel == "regular" and "wifi_mot_banda_24" in motivos and "wifi_mot_canal_lleno" in motivos,
          "2.4 GHz con 6 redes en el canal: lo dice las dos cosas")
nivel, motivos = sysmon.veredicto_wifi(dict(bien, banda="2.4", redes_mismo_canal=None))
comprobar("wifi_mot_canal_lleno" not in motivos, "si Windows no dio la lista de redes, no inventa un canal lleno")
nivel, motivos = sysmon.veredicto_wifi({"rssi": None, "senal": 35})
comprobar(nivel == "mal", "sin RSSI usa el porcentaje (35 %: mal)")
nivel, motivos = sysmon.veredicto_wifi(dict(bien, velocidad_mbps=24))
comprobar("wifi_mot_enlace_lento" in motivos, "enlace de 24 Mbps: lo avisa")

print("== Wi-Fi: lo que lee de verdad este equipo ==")
datos = sysmon.leer_wifi()
if datos is None:
    print("  (este equipo no tiene Wi-Fi o el servicio esta apagado: se prueba solo que no reviente)")
else:
    comprobar(isinstance(datos, list), f"devuelve una lista ({len(datos)} adaptadores)")
    for w in datos:
        claves = {"adaptador", "conectado", "ssid", "senal", "rssi", "canal", "banda", "estandar",
                  "velocidad_mbps", "redes_mismo_canal", "redes_misma_banda"}
        comprobar(claves <= set(w), f"{w['adaptador']}: trae todas las claves")
        if w["conectado"]:
            comprobar(w["senal"] is None or 0 <= w["senal"] <= 100, f"senal razonable ({w['senal']} %)")
            comprobar(w["rssi"] is None or -100 <= w["rssi"] < 0, f"RSSI razonable ({w['rssi']} dBm)")
            comprobar(w["canal"] is None or 1 <= w["canal"] <= 233, f"canal razonable ({w['canal']})")
            comprobar(w["banda"] in ("2.4", "5", "6", None), f"banda conocida ({w['banda']})")

print("== Wi-Fi: el texto que se ensena ==")
import main
texto, nivel = main.texto_wifi(None)
comprobar(nivel == "info" and texto, "sin adaptador: lo dice")
texto, nivel = main.texto_wifi([{"adaptador": "x", "conectado": False}])
comprobar(nivel == "info" and texto, "sin conexion: lo dice")
w = dict(bien, adaptador="Realtek", conectado=True, ssid=None, canal=None, estandar=None, redes_misma_banda=3)
texto, nivel = main.texto_wifi([w])
comprobar(nivel == "bien" and "(red oculta)" in texto, "red sin nombre: '(red oculta)', no 'None'")
comprobar("None" not in texto, "ningun dato que falte sale como 'None'")
texto, nivel = main.texto_wifi([{"adaptador": "x", "conectado": True}])
comprobar(nivel == "info" and "veredicto" in texto,
          "conectado pero sin datos de senal: no dice 'esta bien' (no lo sabe)")
texto, _ = main.texto_wifi([dict(w, banda="2.4", rssi=-79, redes_mismo_canal=5, canal=6)])
comprobar("2,4 GHz" in texto and "-79" in texto and "5 redes" in texto, "con problemas, el texto los explica")

print("== Disco: velocidad real, sin cache ==")
for lectura, aleatoria, clase in ((120, 0.8, "hdd"), (180, 1.5, "hdd"), (480, 30, "ssd"), (230, 12, "ssd"),
                                  (2400, 45, "nvme")):
    comprobar(opt.clase_disco(lectura, aleatoria) == clase, f"{lectura} MB/s y {aleatoria} MB/s en 4 KB -> {clase}")

restos_antes = set(glob.glob(os.path.join(tempfile.gettempdir(), "techclean_prueba_disco*")))
fases = []
r = opt.prueba_velocidad_disco(tamano_mb=64, callback_progreso=fases.append, segundos_aleatoria=1)
comprobar(r is not None and "error" not in r, f"la prueba termina ({r})")
if r and "error" not in r:
    comprobar(r["escritura_mbs"] > 0 and r["lectura_mbs"] > 0 and r["aleatoria_mbs"] > 0, "las tres velocidades dan numero")
    # Una lectura desde la RAM pasa de 10 GB/s; ningun disco de consumo
    # llega a eso con un pedido a la vez.
    comprobar(r["lectura_mbs"] < 10000, f"la lectura es de un disco y no de la RAM ({r['lectura_mbs']} MB/s)")
    comprobar(r["clase"] in ("hdd", "ssd", "nvme"), f"clasifica el disco ({r['clase']})")
    comprobar(r["unidad"].endswith(":"), f"dice que unidad probo ({r['unidad']})")
comprobar(len(fases) >= 4, f"avisa de cada fase ({len(fases)} avisos)")
restos = set(glob.glob(os.path.join(tempfile.gettempdir(), "techclean_prueba_disco*"))) - restos_antes
comprobar(not restos, f"no deja el archivo de prueba ({restos or 'nada'})")

r = opt.prueba_velocidad_disco(tamano_mb=8, carpeta=os.path.join(tempfile.gettempdir(), "no_existe_tc_7f3"))
comprobar(r is not None and "error" in r, "en una carpeta que no existe: devuelve el error, no revienta")
r = opt.prueba_velocidad_disco(tamano_mb=10 ** 9)
comprobar(r is not None and "error" in r and "espacio" in r["error"].lower(),
          "si no cabe, lo dice antes de llenar el disco")

texto = main.texto_disco({"escritura_mbs": 90, "lectura_mbs": 110, "aleatoria_mbs": 0.9, "clase": "hdd"}, "SSD")
comprobar("SSD" in texto and "mecánico" in texto, "un SSD que rinde como HDD: avisa")
texto = main.texto_disco({"escritura_mbs": 900, "lectura_mbs": 2000, "aleatoria_mbs": 50, "clase": "nvme"}, None)
comprobar("NVMe" in texto and "⚠" not in texto, "un NVMe normal: sin avisos")

print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
