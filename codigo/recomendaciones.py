# -*- coding: utf-8 -*-
"""Ajustar TechClean a este equipo (1.8.0): qué funciones de la app
conviene tener encendidas o apagadas según cómo es el equipo.

Lo pidió el desarrollador: "un botón que analice el PC y le indique o
active qué funciones tener encendidas y apagadas para el mejor
rendimiento". La app propone y el usuario aprueba (solo cambia lo que se
le pide), y lo que se propone son ajustes de la propia app, que se cambian
de vuelta en Ajustes, Gaming y Segundo plano.

Todo aquí es puro: recibe lo leído del equipo y el estado de la app, y
devuelve las propuestas. Así se prueba con equipos inventados (un portátil
de 4 GB, un PC de juegos de 32 GB...)."""
import os

# Un equipo "modesto": lo mismo que system_monitor.es_equipo_modesto.
NUCLEOS_MODESTO = 2
RAM_MODESTA_GB = 4
# Con esto o más, el Modo Ligero no hace falta.
NUCLEOS_SOBRADO = 4
RAM_SOBRADA_GB = 8
# A partir de qué uso de RAM se libera sola, según la RAM que haya.
UMBRAL_RAM_POCA = 80          # 8 GB o menos: se llena antes
UMBRAL_RAM_NORMAL = 85
UMBRAL_BATERIA = 20
MAX_JUEGOS_EN_TEXTO = 3

ORDEN = ("ligero_on", "ligero_off", "ram_on", "bateria_on", "juegos_auto", "frenar_on", "limpieza_on",
         "inicio_on")


def carpeta_juego(ruta):
    """La forma en que Gaming guarda la carpeta de un juego marcado
    (main._toggle_juego_auto): sin esto, el mismo juego saldría dos veces."""
    return os.path.normcase(os.path.normpath(ruta)) + os.sep


def recomendar(equipo, estado):
    """equipo: {"ram_gb", "nucleos", "portatil", "juegos": [{"nombre", "ruta"}]}
    estado: {"modo_ligero", "auto_ram_activa", "bateria_ahorro_automatico",
             "juegos_modo_auto", "frenar_acaparadores", "limpieza_activa",
             "inicio_activo", "limpieza_hora"}
    Devuelve solo lo que CAMBIA: [{"clave", "params", "aplicar"}], en el
    orden de ORDEN. `aplicar` dice qué poner (lo usa main.py)."""
    ram = float(equipo.get("ram_gb") or 0)
    nucleos = int(equipo.get("nucleos") or 0)
    juegos = [j for j in (equipo.get("juegos") or []) if j.get("ruta")]
    props = []

    def proponer(clave, aplicar, **params):
        params.setdefault("ram", f"{ram:.0f} GB")
        params.setdefault("nucleos", nucleos)
        props.append({"clave": clave, "params": params, "aplicar": aplicar})

    modesto = nucleos <= NUCLEOS_MODESTO or ram <= RAM_MODESTA_GB
    sobrado = nucleos >= NUCLEOS_SOBRADO and ram >= RAM_SOBRADA_GB
    if modesto and not estado.get("modo_ligero"):
        proponer("ligero_on", {"modo_ligero": True})
    elif sobrado and estado.get("modo_ligero"):
        proponer("ligero_off", {"modo_ligero": False})

    # Liberar RAM solo actúa cuando la memoria se llena: no estorba en un
    # equipo sobrado, y en uno justo es lo que más se nota.
    umbral = UMBRAL_RAM_POCA if ram <= 8 else UMBRAL_RAM_NORMAL
    if not estado.get("auto_ram_activa"):
        proponer("ram_on", {"auto_ram_activa": True, "umbral_ram_auto": umbral}, umbral=umbral)

    if equipo.get("portatil") and not estado.get("bateria_ahorro_automatico"):
        proponer("bateria_on", {"bateria_ahorro_automatico": True, "bateria_umbral_ahorro": UMBRAL_BATERIA},
                 umbral=UMBRAL_BATERIA)

    if juegos and not estado.get("juegos_modo_auto"):
        nombres = ", ".join(j["nombre"] for j in juegos[:MAX_JUEGOS_EN_TEXTO] if j.get("nombre"))
        if len(juegos) > MAX_JUEGOS_EN_TEXTO:
            nombres += "…"
        proponer("juegos_auto", {"juegos_modo_auto": [carpeta_juego(j["ruta"]) for j in juegos]},
                 n=len(juegos), juegos=nombres)
    if juegos and not estado.get("frenar_acaparadores", True):
        proponer("frenar_on", {"frenar_acaparadores": True})

    if not estado.get("limpieza_activa"):
        proponer("limpieza_on", {"limpieza_programada": True}, hora=estado.get("limpieza_hora") or "09:00")

    # Lo automático solo funciona con la app abierta (en la bandeja).
    automatico = (estado.get("auto_ram_activa") or estado.get("bateria_ahorro_automatico")
                  or estado.get("juegos_modo_auto")
                  or any(p["clave"] in ("ram_on", "bateria_on", "juegos_auto") for p in props))
    if automatico and not estado.get("inicio_activo"):
        proponer("inicio_on", {"inicio_automatico": True})

    return sorted(props, key=lambda p: ORDEN.index(p["clave"]))
