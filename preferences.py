"""
preferences.py
Guarda preferencias del usuario entre sesiones — solo estado de la
interfaz (nada sensible: sin nombres, sin rutas de archivos personales,
sin datos de navegación) — en un archivo JSON local por usuario.
"""

import copy
import json
import os
import platform
import threading

IS_WINDOWS = platform.system() == "Windows"

# Candado para que dos hilos no se pisen al guardar: guardar() lee, mezcla
# y escribe, y sin candado dos hilos podrían perder cambios del otro. El
# widget flotante consulta desde su hilo de GPU mientras el hilo principal
# guarda, así que esto no es hipotético.
_candado = threading.Lock()

# Caché de lo último leído, con la "firma" del archivo (fecha de
# modificación + tamaño) para saber si sigue vigente.
_cache = {"datos": None, "firma": None, "ruta": None}

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


# Carpetas cuya creación ya se intentó en esta ejecución.
_carpetas_listas = set()


def carpeta_datos():
    """
    Carpeta persistente por usuario (%APPDATA%\\TechCleanPro) — a diferencia
    de la carpeta de la app, esta SÍ sobrevive entre ejecuciones incluso en
    la versión compilada (.exe): la carpeta de la app compilada es una
    carpeta temporal que Windows borra al cerrarla. Se usa para
    preferencias.json y para el registro de errores internos.

    BUG de rendimiento corregido: aquí se llamaba a os.makedirs en CADA
    consulta. Medido en el equipo de pruebas son ~245 microsegundos por
    llamada — el 65% de lo que costaba leer una preferencia, y para nada:
    la carpeta ya existe desde la primera vez. Ahora se intenta una sola
    vez por ejecución, y quien vaya a ESCRIBIR se asegura por su cuenta
    (que es cuando de verdad importa que exista).
    """
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~")
    carpeta = os.path.join(base, "TechCleanPro")
    if carpeta not in _carpetas_listas:
        try:
            os.makedirs(carpeta, exist_ok=True)
        except Exception:
            pass
        _carpetas_listas.add(carpeta)
    return carpeta


def _ruta_config():
    return os.path.join(carpeta_datos(), "preferencias.json")


def _firma(ruta):
    """Fecha de modificación + tamaño del archivo. Sirve para saber si lo
    que hay en caché sigue valiendo sin tener que leerlo entero."""
    try:
        st = os.stat(ruta)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def cargar():
    """Devuelve las preferencias guardadas, rellenando con los valores por
    defecto cualquier clave que falte (primera vez, archivo dañado, etc.).

    BUG de rendimiento corregido: esto abría y parseaba el JSON en CADA
    llamada, y el widget flotante lo llama en su tick — o sea, una lectura
    de disco por segundo, para siempre, en el hilo de la interfaz. En una
    app cuyo propósito es que el equipo vaya más suelto, eso era justo lo
    contrario. Ahora se guarda en caché y solo se relee si el archivo
    cambió de verdad (un `stat` es muchísimo más barato que abrir, leer y
    parsear).

    Se devuelve una copia profunda a propósito: hay valores que son listas
    (`widget_metricas`, `widget_pos`) y si se devolviera la referencia de
    la caché, cualquiera que las modificara estaría corrompiendo lo que
    ven todos los demás."""
    ruta = _ruta_config()
    firma = _firma(ruta)
    en_cache = _cache["datos"]
    # La ruta forma parte de la clave: el banco de pruebas cambia %APPDATA%
    # en caliente para no tocar las preferencias reales, y sin esto la caché
    # de una carpeta podría contestar por la otra.
    if en_cache is not None and _cache["ruta"] == ruta and _cache["firma"] == firma:
        return copy.deepcopy(en_cache)

    datos = dict(_DEFAULTS)
    try:
        if firma is not None:
            with open(ruta, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                datos.update(guardado)
    except Exception:
        pass

    _cache["datos"] = datos
    _cache["firma"] = firma
    _cache["ruta"] = ruta
    return copy.deepcopy(datos)


def _escribir(datos):
    """Escribe el JSON de forma atómica: primero a un archivo temporal al
    lado, y recién cuando está completo se reemplaza el bueno.

    BUG corregido: antes se abría el archivo real en modo "w", que lo VACÍA
    antes de escribir nada. Si el equipo se apagaba, la app moría o el
    antivirus se metía en ese instante, preferencias.json quedaba a medias;
    y como cargar() se traga cualquier error y devuelve los valores de
    fábrica, el usuario perdía TODA su configuración sin un solo aviso.
    Con os.replace el cambio es de todo o nada."""
    ruta = _ruta_config()
    # Escribir es raro (un clic del usuario), así que aquí sí vale la pena
    # asegurarse de que la carpeta exista aunque alguien la haya borrado a
    # mitad de la sesión — carpeta_datos() ya no lo comprueba cada vez.
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
    except Exception:
        pass
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)
    _cache["datos"] = copy.deepcopy(datos)
    _cache["firma"] = _firma(ruta)
    _cache["ruta"] = ruta


def guardar(cambios):
    """Actualiza solo las claves indicadas en `cambios`, conservando el
    resto de lo ya guardado. Devuelve True/False según si pudo escribir."""
    with _candado:
        try:
            actual = cargar()
            actual.update(cambios)
            _escribir(actual)
            return True
        except Exception:
            return False


def restablecer():
    """Vuelve toda la configuración a los valores de fábrica."""
    with _candado:
        try:
            _escribir(dict(_DEFAULTS))
            return True
        except Exception:
            return False
