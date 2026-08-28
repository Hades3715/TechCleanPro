"""
preferences.py
Guarda preferencias del usuario entre sesiones — solo estado de la
interfaz (nada sensible: sin nombres, sin rutas de archivos personales,
sin datos de navegación) — en un archivo JSON local por usuario.
"""

import json
import os
import platform

IS_WINDOWS = platform.system() == "Windows"

_DEFAULTS = {
    "widget_visible": False,
    "perfil_energia": "equilibrado",
    "alerta_temp_cpu": None,              # None = desactivada, o un número en °C
    "crear_punto_restauracion": True,      # antes de sfc/DISM en Reparar
    "icono_bandeja_metrica": None,          # None, "cpu" o "ram"
    "bateria_ahorro_automatico": False,      # cambiar a plan Silencioso con batería baja
    "bateria_umbral_ahorro": 20,              # % de batería para activar el ahorro
    "limpieza_hora": "09:00",                  # hora de la limpieza programada
    "widget_pos": None,                         # [x, y] — última posición del widget flotante
    "widget_metricas": ["cpu", "ram", "red", "gpu"],  # qué paneles mostrar en el widget expandido
    "modo_ligero": False,                          # intervalos de actualización más espaciados
    "modo_ligero_preguntado": False,                # para sugerirlo solo una vez, no cada arranque
    "ultima_revision_actualizacion": 0,                # timestamp — para revisar como máximo 1 vez al día
    "idioma": "es",                                       # "es" o "en" — se aplica al reiniciar la app
    "idioma_preguntado": False,                              # para preguntarlo solo la primera vez
    "umbral_ram_auto": 85,                                   # % de RAM al que se libera memoria sola en segundo plano
    "umbral_salud_ram": 75,                                  # % de RAM al que el semáforo de salud (Inicio) empieza a avisar
    "umbral_salud_disco": 85,                                # % de disco lleno al que el semáforo de salud empieza a avisar
}


def carpeta_datos():
    """
    Carpeta persistente por usuario (%APPDATA%\\TechCleanPro) — a diferencia
    de la carpeta de la app, esta SÍ sobrevive entre ejecuciones incluso en
    la versión compilada (.exe): la carpeta de la app compilada es una
    carpeta temporal que Windows borra al cerrarla. Se usa para
    preferencias.json y para el registro de errores internos.
    """
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~")
    carpeta = os.path.join(base, "TechCleanPro")
    try:
        os.makedirs(carpeta, exist_ok=True)
    except Exception:
        pass
    return carpeta


def _ruta_config():
    return os.path.join(carpeta_datos(), "preferencias.json")


def cargar():
    """Devuelve las preferencias guardadas, rellenando con los valores por
    defecto cualquier clave que falte (primera vez, archivo dañado, etc.)."""
    datos = dict(_DEFAULTS)
    ruta = _ruta_config()
    try:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                datos.update(guardado)
    except Exception:
        pass
    return datos


def guardar(cambios):
    """Actualiza solo las claves indicadas en `cambios`, conservando el
    resto de lo ya guardado. Devuelve True/False según si pudo escribir."""
    ruta = _ruta_config()
    try:
        actual = cargar()
        actual.update(cambios)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def restablecer():
    """Vuelve toda la configuración a los valores de fábrica."""
    ruta = _ruta_config()
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(dict(_DEFAULTS), f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
