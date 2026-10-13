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

from idiomas import t

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
        return False, t("privmod_no_soportado"), ""

    if is_browser_running(nombre):
        return False, t("privmod_abierto_hist", navegador=nombre), ""

    datos = BROWSERS[nombre]

    try:
        if nombre == "Firefox":
            perfil_base = datos["perfil"]
            perfil_elegido = _elegir_perfil_firefox(perfil_base)
            if perfil_elegido is None:
                return False, t("privmod_sin_perfil_ff"), ""
            db_path = os.path.join(perfil_base, perfil_elegido, datos["history_file"])
            comando = f'DELETE FROM moz_places; -- sobre {db_path}'
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM moz_historyvisits")
                conn.execute("DELETE FROM moz_places WHERE id NOT IN (SELECT place_id FROM moz_bookmarks)")
                conn.commit()
                conn.close()
            return True, t("privmod_hist_ok", navegador=nombre), comando
        else:
            history_path = os.path.join(datos["perfil"], datos["history_file"])
            comando = f'DELETE FROM urls; DELETE FROM visits; -- sobre {history_path}'
            if os.path.exists(history_path):
                conn = sqlite3.connect(history_path)
                conn.execute("DELETE FROM visits")
                conn.execute("DELETE FROM urls")
                conn.commit()
                conn.close()
            return True, t("privmod_hist_ok", navegador=nombre), comando
    except sqlite3.OperationalError:
        return False, t("privmod_db_error", navegador=nombre), ""
    except Exception as e:
        return False, t("privmod_hist_error", navegador=nombre, error=e), ""


def clear_browser_cache(nombre):
    if nombre not in BROWSERS:
        return False, 0, t("privmod_no_soportado")

    if is_browser_running(nombre):
        return False, 0, t("privmod_abierto_cache", navegador=nombre)

    datos = BROWSERS[nombre]
    cache_dir_name = datos.get("cache_dir")
    if not cache_dir_name:
        return False, 0, t("privmod_sin_ruta", navegador=nombre)

    cache_path = os.path.join(datos["perfil"], cache_dir_name)
    if not os.path.isdir(cache_path):
        return True, 0, t("privmod_sin_cache", navegador=nombre)

    def _tamano_de(ruta):
        total = 0
        for carpeta, _sub, archivos in os.walk(ruta):
            for a in archivos:
                try:
                    total += os.path.getsize(os.path.join(carpeta, a))
                except OSError:
                    pass
        return total

    # BUG corregido: se medía el tamaño ANTES de borrar y se informaba ese
    # número como "espacio liberado", pasara lo que pasara después. Y
    # rmtree va con ignore_errors=True, que significa que NUNCA lanza
    # excepción: el except de abajo era código muerto y la función devolvía
    # siempre éxito.
    #
    # En la práctica un navegador deja archivos bloqueados aunque parezca
    # cerrado (Chrome se queda con procesos en segundo plano), así que se
    # borraba una parte y la app anunciaba haber liberado el total. Ahora
    # se vuelve a medir después y se informa lo que se liberó DE VERDAD.
    tamano_antes = _tamano_de(cache_path)
    try:
        shutil.rmtree(cache_path, ignore_errors=True)
    except Exception as e:
        return False, 0, t("privmod_cache_error", navegador=nombre, error=e)

    tamano_despues = _tamano_de(cache_path) if os.path.isdir(cache_path) else 0
    liberado = max(0, tamano_antes - tamano_despues)
    if tamano_despues == 0 or liberado > 0:
        return True, liberado, t("privmod_cache_ok", navegador=nombre, ruta=cache_path)
    # No se pudo borrar nada: casi siempre es el navegador todavía vivo.
    return False, 0, t("privmod_cache_bloqueada", navegador=nombre)


# ---------------- Quién usó la cámara, el micrófono y la ubicación ----------------
# Windows apunta, por cada app, la última vez que empezó y terminó de usar la
# cámara, el micrófono o la ubicación: es lo que enseña Configuración →
# Privacidad → "Actividad reciente". Está en el registro de tu usuario
# (ConsentStore), junto al permiso de cada app. Solo se lee.
_CONSENT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
TIPOS_USO = ("webcam", "microphone", "location")


def _filetime_a_epoch(valor):
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return None
    return valor / 10_000_000 - 11644473600 if valor > 0 else None


def nombre_de_app(clave, empaquetada):
    """Un nombre legible: "C:#Program Files#Google#Chrome#...#chrome.exe" ->
    ("chrome", ruta); "Microsoft.WindowsCamera_8wekyb3d8bbwe" -> ("Windows
    Camera", None)."""
    import re
    if not empaquetada:
        ruta = clave.replace("#", "\\")
        return os.path.splitext(os.path.basename(ruta))[0], ruta
    familia = clave.split("_", 1)[0]
    parte = familia.rsplit(".", 1)[-1] if "." in familia else familia
    # Las de Windows con nombre interno poco claro.
    conocidas = {"immersivecontrolpanel": "uso_app_configuracion", "BioEnrollment": "uso_app_hello"}
    if parte in conocidas:
        return t(conocidas[parte]), None
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", parte), None


def uso_de_permisos():
    """{tipo: [{nombre, ruta, inicio (epoch), fin (epoch o None), en_uso}]},
    de más reciente a más antiguo. Vacío fuera de Windows."""
    resultado = {tipo: [] for tipo in TIPOS_USO}
    if not IS_WINDOWS:
        return resultado
    import winreg

    def leer(clave_abierta, nombre_sub, empaquetada, lista):
        try:
            with winreg.OpenKey(clave_abierta, nombre_sub) as sub:
                try:
                    inicio = winreg.QueryValueEx(sub, "LastUsedTimeStart")[0]
                except OSError:
                    return
                try:
                    fin = winreg.QueryValueEx(sub, "LastUsedTimeStop")[0]
                except OSError:
                    fin = 0
        except OSError:
            return
        inicio_e = _filetime_a_epoch(inicio)
        if inicio_e is None:
            return
        fin_e = _filetime_a_epoch(fin)
        nombre, ruta = nombre_de_app(nombre_sub, empaquetada)
        lista.append({"nombre": nombre, "ruta": ruta, "inicio": inicio_e, "fin": fin_e,
                      # Empezó y no ha terminado: la está usando ahora mismo.
                      "en_uso": fin_e is None or fin_e < inicio_e})

    for tipo in TIPOS_USO:
        lista = resultado[tipo]
        try:
            raiz = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CONSENT + "\\" + tipo)
        except OSError:
            continue
        with raiz:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(raiz, i)
                except OSError:
                    break
                i += 1
                if sub == "NonPackaged":
                    try:
                        with winreg.OpenKey(raiz, sub) as no_empaquetadas:
                            j = 0
                            while True:
                                try:
                                    app = winreg.EnumKey(no_empaquetadas, j)
                                except OSError:
                                    break
                                j += 1
                                leer(no_empaquetadas, app, False, lista)
                    except OSError:
                        pass
                else:
                    leer(raiz, sub, True, lista)
        lista.sort(key=lambda a: a["inicio"], reverse=True)
    return resultado
