"""
privacy.py
Detecta navegadores instalados y borra historial/caché de forma real.
Por seguridad, exige que el navegador esté cerrado antes de tocar sus
archivos (evita corromper perfiles en uso).
"""

import os
import shutil
import sqlite3
import platform
import psutil

IS_WINDOWS = platform.system() == "Windows"


def _local_appdata():
    return os.environ.get("LOCALAPPDATA", "")


def _appdata():
    return os.environ.get("APPDATA", "")


BROWSERS = {
    "Chrome": {
        "proceso": "chrome.exe",
        "perfil": os.path.join(_local_appdata(), "Google", "Chrome", "User Data", "Default"),
        "history_file": "History",
        "cache_dir": "Cache",
    },
    "Edge": {
        "proceso": "msedge.exe",
        "perfil": os.path.join(_local_appdata(), "Microsoft", "Edge", "User Data", "Default"),
        "history_file": "History",
        "cache_dir": "Cache",
    },
    "Brave": {
        "proceso": "brave.exe",
        "perfil": os.path.join(_local_appdata(), "BraveSoftware", "Brave-Browser", "User Data", "Default"),
        "history_file": "History",
        "cache_dir": "Cache",
    },
    "Opera GX": {
        # A diferencia de Chrome/Edge/Brave, Opera (y Opera GX) NO usa una
        # subcarpeta "Default" — History/Cache viven directo en la carpeta
        # del perfil. El proceso se llama "opera.exe" igual que el Opera
        # normal (Opera GX es una variante del mismo motor).
        "proceso": "opera.exe",
        "perfil": os.path.join(_appdata(), "Opera Software", "Opera GX Stable"),
        "history_file": "History",
        "cache_dir": "Cache",
    },
    "Firefox": {
        "proceso": "firefox.exe",
        "perfil": os.path.join(_appdata(), "Mozilla", "Firefox", "Profiles"),
        "history_file": "places.sqlite",
        "cache_dir": None,
    },
}


def detect_installed_browsers():
    encontrados = []
    for nombre, datos in BROWSERS.items():
        perfil = datos["perfil"]
        if nombre == "Firefox":
            if os.path.isdir(perfil):
                subperfiles = [d for d in os.listdir(perfil)] if os.path.isdir(perfil) else []
                if subperfiles:
                    encontrados.append(nombre)
        else:
            if os.path.isdir(perfil):
                encontrados.append(nombre)
    return encontrados


def is_browser_running(nombre):
    proceso = BROWSERS[nombre]["proceso"]
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"] and p.info["name"].lower() == proceso.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _elegir_perfil_firefox(perfil_base):
    """
    Elige qué carpeta de perfil de Firefox usar. Si hay varias (algo común:
    Firefox crea un perfil nuevo por cada instalación/actualización mayor,
    o el usuario tiene varios a propósito), prioriza la que Firefox marca
    como principal (termina en '.default-release' o '.default'); si no
    encuentra ninguna así, usa la primera en orden alfabético — NUNCA el
    orden que devuelve el sistema de archivos, que no es determinístico y
    podía hacer que se limpiara un perfil distinto cada vez.
    """
    subperfiles = sorted(d for d in os.listdir(perfil_base) if os.path.isdir(os.path.join(perfil_base, d)))
    if not subperfiles:
        return None
    for candidato in subperfiles:
        if candidato.endswith(".default-release") or candidato.endswith(".default"):
            return candidato
    return subperfiles[0]


def clear_browser_history(nombre):
    if nombre not in BROWSERS:
        return False, "Navegador no soportado", ""

    if is_browser_running(nombre):
        return False, f"{nombre} está abierto. Ciérralo antes de borrar su historial.", ""

    datos = BROWSERS[nombre]

    try:
        if nombre == "Firefox":
            perfil_base = datos["perfil"]
            perfil_elegido = _elegir_perfil_firefox(perfil_base)
            if perfil_elegido is None:
                return False, "No se encontró perfil de Firefox", ""
            db_path = os.path.join(perfil_base, perfil_elegido, datos["history_file"])
            comando = f'DELETE FROM moz_places; -- sobre {db_path}'
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM moz_historyvisits")
                conn.execute("DELETE FROM moz_places WHERE id NOT IN (SELECT place_id FROM moz_bookmarks)")
                conn.commit()
                conn.close()
            return True, f"Historial de {nombre} borrado correctamente.", comando
        else:
            history_path = os.path.join(datos["perfil"], datos["history_file"])
            comando = f'DELETE FROM urls; DELETE FROM visits; -- sobre {history_path}'
            if os.path.exists(history_path):
                conn = sqlite3.connect(history_path)
                conn.execute("DELETE FROM visits")
                conn.execute("DELETE FROM urls")
                conn.commit()
                conn.close()
            return True, f"Historial de {nombre} borrado correctamente.", comando
    except sqlite3.OperationalError:
        return False, f"No se pudo abrir la base de datos de {nombre} (¿sigue en uso?).", ""
    except Exception as e:
        return False, f"Error al borrar historial de {nombre}: {e}", ""


def clear_browser_cache(nombre):
    if nombre not in BROWSERS:
        return False, 0, "Navegador no soportado"

    if is_browser_running(nombre):
        return False, 0, f"{nombre} está abierto. Ciérralo antes de limpiar su caché."

    datos = BROWSERS[nombre]
    cache_dir_name = datos.get("cache_dir")
    if not cache_dir_name:
        return False, 0, f"{nombre} no tiene ruta de caché configurada en esta versión."

    cache_path = os.path.join(datos["perfil"], cache_dir_name)
    if not os.path.isdir(cache_path):
        return True, 0, f"{nombre} no tenía caché acumulado."

    liberado = 0
    for root, _, files in os.walk(cache_path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                liberado += os.path.getsize(fp)
            except OSError:
                pass
    try:
        shutil.rmtree(cache_path, ignore_errors=True)
        return True, liberado, f"Caché de {nombre} eliminado ({cache_path})"
    except Exception as e:
        return False, 0, f"Error al limpiar caché de {nombre}: {e}"
