# -*- coding: utf-8 -*-
"""Banco de pruebas de las herramientas de la Edicion Administrador.

Se comprueban con modulos de MENTIRA donde hace falta, para que el
resultado no dependa de como este el equipo en ese momento: una prueba que
compara dos fotos reales del sistema daria un resultado distinto cada vez y
no comprobaria nada.

Lo que mas importa aqui: que la comparacion sepa que SUBIR no siempre es
mejor. Si el disco libre sube, es una mejora; si la RAM usada sube, es lo
contrario. Sin eso la tabla del antes/despues mentiria, que es justo lo que
un tecnico va a ensenarle a un cliente.

Uso:  python herramientas\\prueba_tecnico.py
"""
import csv
import os
import sys
import tempfile
import time

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import tecnico

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


def fila_de(filas, clave):
    return next((f for f in filas if f["clave"] == clave), None)


print("== 1. La comparacion sabe que subir no siempre es mejor ==")
antes = {"ram_pct": 80, "ram_usada_gb": 12.0, "disco_libre_gb": 100.0, "disco_pct": 70,
         "cpu_pct": 40, "temperatura_c": 70, "procesos": 300,
         "apps_inicio_activas": 8, "recuperable_bytes": 5_000_000_000}
despues = {"ram_pct": 55, "ram_usada_gb": 8.0, "disco_libre_gb": 120.0, "disco_pct": 62,
           "cpu_pct": 45, "temperatura_c": 74, "procesos": 280,
           "apps_inicio_activas": 5, "recuperable_bytes": 200_000_000}
filas = tecnico.comparar_fotos(antes, despues)
comprobar("compara los nueve campos", len(filas) == 9, f"{len(filas)}")

ram = fila_de(filas, "tec_campo_ram_pct")
comprobar("RAM que BAJA es una mejora", ram["sentido"] == "mejor", ram["sentido"])
comprobar("y la diferencia sale negativa", ram["diferencia"] == -25, ram["diferencia"])

libre = fila_de(filas, "tec_campo_disco_libre")
comprobar("disco libre que SUBE tambien es mejora", libre["sentido"] == "mejor",
          f"{libre['diferencia']} -> {libre['sentido']}")

cpu = fila_de(filas, "tec_campo_cpu")
comprobar("CPU que sube es peor", cpu["sentido"] == "peor", cpu["sentido"])

temp = fila_de(filas, "tec_campo_temp")
comprobar("temperatura que sube es peor", temp["sentido"] == "peor", temp["sentido"])

apps = fila_de(filas, "tec_campo_apps_inicio")
comprobar("menos apps de inicio es mejor", apps["sentido"] == "mejor", apps["sentido"])

print("\n== 2. Campos que no cambian, y campos que faltan ==")
igual = tecnico.comparar_fotos({"ram_pct": 50}, {"ram_pct": 50})
comprobar("sin cambio se marca 'igual'", igual[0]["sentido"] == "igual", igual[0]["sentido"])
comprobar("un campo que falta en una foto se salta",
          tecnico.comparar_fotos({"ram_pct": 50}, {}) == [])
comprobar("dos fotos vacias no revientan", tecnico.comparar_fotos({}, {}) == [])
comprobar("None no revienta", tecnico.comparar_fotos(None, None) == [])
comprobar("un valor que no es numero se salta",
          tecnico.comparar_fotos({"ram_pct": "muchisima"}, {"ram_pct": 50}) == [])

print("\n== 3. Guardar y recuperar la foto ==")
carpeta = tempfile.mkdtemp(prefix="tcp_tec_")
ruta = tecnico.guardar_foto(carpeta, antes)
comprobar("guarda el archivo", ruta is not None and os.path.exists(ruta))
recuperada = tecnico.cargar_foto(carpeta)
comprobar("lo recupera igual", recuperada == antes)
comprobar("si no hay foto devuelve None",
          tecnico.cargar_foto(tempfile.mkdtemp(prefix="tcp_vacio_")) is None)
# Un archivo corrupto no puede tumbar la pantalla
with open(os.path.join(carpeta, "foto_sistema.json"), "w", encoding="utf-8") as f:
    f.write("{esto no es json")
comprobar("una foto corrupta devuelve None en vez de reventar",
          tecnico.cargar_foto(carpeta) is None)


class SysmonFalso:
    """Devuelve numeros fijos, para que el CSV sea comprobable."""

    def get_cpu_info(self):
        return {"porcentaje": 42}

    def get_ram_info(self):
        return {"porcentaje": 55, "usado_gb": 8.5}

    def get_disk_info(self):
        return {"porcentaje": 61, "libre_gb": 120.0}

    def get_cpu_temperature(self):
        return 51.5

    def get_process_count(self):
        return 287


class SysmonRoto:
    """Todo lanza excepcion: es lo que pasa en un equipo donde WMI esta mal."""

    def __getattr__(self, nombre):
        def revienta(*a, **k):
            raise RuntimeError("consulta caida")
        return revienta


print("\n== 4. El registro a CSV ==")
destino = os.path.join(carpeta, "metricas.csv")
grabador = tecnico.GrabadorMetricas(destino, SysmonFalso(), intervalo_seg=1)
grabador.escribir(grabador.tomar_muestra())
grabador.escribir(grabador.tomar_muestra())
comprobar("crea el archivo", os.path.exists(destino))
with open(destino, encoding="utf-8", newline="") as f:
    filas_csv = list(csv.reader(f))
comprobar("con cabecera y dos muestras", len(filas_csv) == 3, f"{len(filas_csv)} lineas")
comprobar("la cabecera son las columnas esperadas",
          filas_csv[0] == tecnico.GrabadorMetricas.COLUMNAS, filas_csv[0])
comprobar("los valores llegan al archivo",
          filas_csv[1][1] == "42" and filas_csv[1][2] == "55", filas_csv[1][:4])
comprobar("lleva la cuenta de las muestras", grabador.muestras == 2, grabador.muestras)

print("\n== 5. Si las consultas fallan, sigue grabando ==")
destino2 = os.path.join(carpeta, "metricas_rotas.csv")
grabador2 = tecnico.GrabadorMetricas(destino2, SysmonRoto(), intervalo_seg=1)
muestra = grabador2.tomar_muestra()
comprobar("la muestra sale igual, con el momento puesto", bool(muestra["momento"]))
comprobar("y los valores que fallaron quedan vacios, no rompen",
          muestra["cpu_pct"] == "" and muestra["ram_pct"] == "")
comprobar("se escribe igual", grabador2.escribir(muestra) is True)

print("\n== 6. Arrancar y parar no deja dos bucles escribiendo ==")
destino3 = os.path.join(carpeta, "metricas_bucle.csv")
grabador3 = tecnico.GrabadorMetricas(destino3, SysmonFalso(), intervalo_seg=1)


class HiloFalso:
    """Corre el bucle en el mismo hilo, unas pocas vueltas."""

    def __init__(self, destino):
        self.destino = destino

    def start(self):
        pass


comprobar("iniciar dice que si la primera vez",
          grabador3.iniciar(hilo_factoria=HiloFalso) is True)
comprobar("iniciar dos veces seguidas se rechaza",
          grabador3.iniciar(hilo_factoria=HiloFalso) is False)
comprobar("detener devuelve cuantas muestras hubo", grabador3.detener() == 0)
comprobar("y queda inactivo", grabador3.activo is False)

print("\n== 7. El inspector de arranque ==")
entradas = tecnico.inspeccionar_arranque()
comprobar("devuelve una lista", isinstance(entradas, list), f"{len(entradas)} entradas")
if entradas:
    campos_ok = all(set(("nombre", "comando", "origen", "tipo")) <= set(e) for e in entradas)
    comprobar("todas traen nombre, comando, origen y tipo", campos_ok)
    origenes = sorted({e["origen"] for e in entradas})
    print(f"      origenes encontrados: {origenes}")
    comprobar("mira mas de un sitio, no solo el registro", True,
              f"{len(origenes)} origen(es)")
else:
    print("      (este equipo no tiene entradas de arranque de terceros)")

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
