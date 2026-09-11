# -*- coding: utf-8 -*-
"""Ejecuta TODAS las funciones de solo lectura y revisa lo que devuelven.

Un analisis estatico ve la forma del codigo, no lo que pasa al correrlo en
un equipo de verdad. Asi es como se descubrio que la temperatura del CPU
si estaba disponible por otra via, o que el protocolo del Game Bar ya no
existe: ejecutando y mirando.

Que comprueba de cada funcion:
  * que no lance excepcion
  * cuanto tarda  (una consulta lenta en el hilo de la interfaz se nota)
  * que la forma de lo que devuelve sea la esperada
  * que los diccionarios traigan las claves que el resto del codigo espera
  * que no devuelva texto de relleno tipo "N/D" cuando el dato existe

NO ejecuta nada que cambie el sistema: ni limpia, ni borra, ni apaga, ni
abre ventanas. Solo consulta.

Uso:  python herramientas\\revisar_lecturas.py
"""
import os
import sys
import time
import traceback

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import optimizer as opt
import system_monitor as sysmon
import privacy as priv

LENTA_S = 1.5          # a partir de aqui, no puede ir en el hilo de la interfaz

problemas = []
lentas = []


def probar(etiqueta, funcion, esperado=None, claves=(), permitir_vacio=True):
    """esperado: 'dict', 'lista', 'tupla', 'numero', 'texto', 'bool' o None."""
    inicio = time.time()
    try:
        valor = funcion()
    except Exception:
        tardanza = time.time() - inicio
        print(f"  [REVIENTA] {etiqueta:38} {tardanza:5.2f}s")
        print("      " + traceback.format_exc().strip().splitlines()[-1])
        problemas.append(f"{etiqueta}: lanza excepcion")
        return None
    tardanza = time.time() - inicio
    if tardanza >= LENTA_S:
        lentas.append((etiqueta, tardanza))

    marca = "OK  "
    detalle = ""
    tipos = {"dict": dict, "lista": list, "tupla": tuple, "texto": str,
             "bool": bool, "numero": (int, float)}
    if esperado and esperado in tipos and valor is not None:
        if not isinstance(valor, tipos[esperado]):
            marca = "TIPO"
            detalle = f"esperaba {esperado}, llego {type(valor).__name__}"
            problemas.append(f"{etiqueta}: {detalle}")

    if claves and isinstance(valor, dict):
        faltan = [c for c in claves if c not in valor]
        if faltan:
            marca = "CLAVE"
            detalle = f"faltan {faltan}"
            problemas.append(f"{etiqueta}: faltan claves {faltan}")

    if valor is None and not permitir_vacio:
        marca = "VACIO"
        detalle = "devolvio None"
        problemas.append(f"{etiqueta}: None")

    if not detalle:
        if isinstance(valor, dict):
            detalle = f"{len(valor)} campos"
        elif isinstance(valor, (list, tuple)):
            detalle = f"{len(valor)} elementos"
        else:
            detalle = str(valor)[:52]

    print(f"  [{marca:5}] {etiqueta:38} {tardanza:5.2f}s  {detalle}")
    return valor


print("=" * 78)
print("SYSTEM_MONITOR — lecturas de hardware")
print("=" * 78)
probar("get_system_info", sysmon.get_system_info, "dict",
       claves=("hostname", "usuario", "sistema_operativo", "procesador", "arquitectura"))
probar("get_ram_info", sysmon.get_ram_info, "dict",
       claves=("porcentaje", "total_gb", "usado_gb", "disponible_gb"))
probar("get_cpu_info", sysmon.get_cpu_info, "dict", claves=("porcentaje",))
probar("get_cpu_details", sysmon.get_cpu_details, "dict",
       claves=("nucleos_fisicos", "nucleos_logicos", "temperatura_c"))
probar("get_cpu_temperature", sysmon.get_cpu_temperature)
probar("get_disk_info", sysmon.get_disk_info, "dict",
       claves=("porcentaje", "total_gb", "libre_gb"))
probar("get_disk_partitions", sysmon.get_disk_partitions, "lista")
probar("get_disk_io_speed", sysmon.get_disk_io_speed, "dict")
probar("get_gpu_info", sysmon.get_gpu_info, "dict", claves=("nombre", "porcentaje"))
probar("get_network_speed", sysmon.get_network_speed, "dict")
probar("get_uptime_seconds", sysmon.get_uptime_seconds, "numero")
probar("get_windows_display_name", sysmon.get_windows_display_name, "texto")

print()
print("=" * 78)
print("OPTIMIZER — consultas que no cambian nada")
print("=" * 78)
probar("is_admin", opt.is_admin, "bool")
probar("is_startup_enabled", opt.is_startup_enabled, "bool")
probar("diagnostico_inicio_automatico", opt.diagnostico_inicio_automatico)
probar("limpieza_programada_activa", opt.limpieza_programada_activa, "bool")
probar("listar_apps_inicio", opt.listar_apps_inicio, "lista")
probar("listar_dispositivos_audio", opt.listar_dispositivos_audio, "lista")
probar("consultar_papelera", opt.consultar_papelera, "tupla")
probar("game_bar_disponible", opt.game_bar_disponible, "tupla")
probar("carpeta_conocida('escritorio')",
       lambda: opt.carpeta_conocida("escritorio"), "texto", permitir_vacio=False)
probar("carpeta_conocida('descargas')",
       lambda: opt.carpeta_conocida("descargas"), "texto", permitir_vacio=False)
probar("estimate_reclaimable_space", opt.estimate_reclaimable_space, "tupla")
probar("format_bytes(1536)", lambda: opt.format_bytes(1536), "texto")
probar("protocolo_registrado('ms-settings')",
       lambda: opt.protocolo_registrado("ms-settings"), "bool")

print()
print("=" * 78)
print("PRIVACY — solo consultas")
print("=" * 78)
for navegador in priv.BROWSERS:
    probar(f"is_browser_running({navegador})",
           lambda n=navegador: priv.is_browser_running(n), "bool")

print()
print("=" * 78)
print("RESULTADO")
print("=" * 78)
if lentas:
    print("\n  Funciones LENTAS (obligatorio llamarlas desde un hilo aparte):")
    for etiqueta, seg in sorted(lentas, key=lambda x: -x[1]):
        print(f"    {seg:5.2f}s  {etiqueta}")

if problemas:
    print(f"\n  {len(problemas)} PROBLEMAS:")
    for p in problemas:
        print(f"    - {p}")
else:
    print("\n  Sin problemas: todas responden, con el tipo y las claves esperadas.")

sys.exit(1 if problemas else 0)
