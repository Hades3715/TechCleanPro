"""
tecnico.py
Herramientas exclusivas de la Edición Administrador.

Por qué existen y por qué son ESTAS
-----------------------------------
El código de esta app es público, así que cualquiera puede compilar la
edición admin. Esconder funciones no es posible, y fingir que sí sería
engañarse. Lo que sí tiene sentido es que la edición admin sea de verdad
OTRA COSA, no la misma app con un botón más: herramientas que solo le
sirven a quien arregla computadoras ajenas.

De ahí las tres:

  1. FOTO DEL SISTEMA — un antes y un después. Se guarda cómo estaba el
     equipo, se optimiza, se vuelve a mirar, y sale la diferencia. Es lo
     que un técnico necesita para enseñarle al cliente qué hizo, en vez de
     decir "quedó mejor".

  2. INSPECTOR DE ARRANQUE — todo lo que se inicia con Windows en una sola
     lista: registro (del usuario y de la máquina), carpetas de Inicio y
     tareas programadas. Hoy están repartidos en cuatro sitios distintos y
     nadie los mira todos.

  3. REGISTRO A CSV — apunta las métricas cada pocos segundos a un archivo.
     Para el caso de "a veces se pone lento": se deja corriendo, se usa el
     equipo, y después se mira dónde estuvo el pico.

Ninguna cambia nada del sistema: las tres solo miran y escriben archivos
en donde se les diga.
"""

import csv
import json
import os
import platform
import subprocess
import time
from datetime import datetime

IS_WINDOWS = platform.system() == "Windows"


# ============================================================
#  1. Foto del sistema (comparador antes / después)
# ============================================================

def tomar_foto(sysmon, opt):
    """Retrato del estado del equipo en este instante.

    Se le pasan los módulos como parámetros en vez de importarlos arriba
    para que el banco de pruebas pueda darles un doble y comprobar la
    comparación sin depender de cómo esté el equipo real en ese momento.
    """
    foto = {
        "momento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ram_pct": None, "ram_usada_gb": None,
        "disco_pct": None, "disco_libre_gb": None,
        "cpu_pct": None, "temperatura_c": None,
        "procesos": None, "apps_inicio_activas": None,
        "recuperable_bytes": None,
    }
    try:
        ram = sysmon.get_ram_info()
        foto["ram_pct"] = ram.get("porcentaje")
        foto["ram_usada_gb"] = ram.get("usado_gb")
    except Exception:
        pass
    try:
        disco = sysmon.get_disk_info()
        foto["disco_pct"] = disco.get("porcentaje")
        foto["disco_libre_gb"] = disco.get("libre_gb")
    except Exception:
        pass
    try:
        foto["cpu_pct"] = sysmon.get_cpu_info().get("porcentaje")
    except Exception:
        pass
    try:
        foto["temperatura_c"] = sysmon.get_cpu_temperature()
    except Exception:
        pass
    try:
        foto["procesos"] = sysmon.get_process_count()
    except Exception:
        pass
    try:
        foto["apps_inicio_activas"] = sum(1 for a in opt.listar_apps_inicio() if a.get("activo"))
    except Exception:
        pass
    try:
        _detalle, total = opt.estimate_reclaimable_space()
        foto["recuperable_bytes"] = total
    except Exception:
        pass
    return foto


# Qué campos se comparan, y si SUBIR es bueno o malo. Sin esto, la tabla
# diría que subir la RAM usada es una mejora.
CAMPOS_COMPARABLES = [
    ("ram_pct",            "tec_campo_ram_pct",      "%",   "bajar"),
    ("ram_usada_gb",       "tec_campo_ram_usada",    " GB", "bajar"),
    ("disco_libre_gb",     "tec_campo_disco_libre",  " GB", "subir"),
    ("disco_pct",          "tec_campo_disco_pct",    "%",   "bajar"),
    ("cpu_pct",            "tec_campo_cpu",          "%",   "bajar"),
    ("temperatura_c",      "tec_campo_temp",         " °C", "bajar"),
    ("procesos",           "tec_campo_procesos",     "",    "bajar"),
    ("apps_inicio_activas", "tec_campo_apps_inicio",  "",    "bajar"),
    ("recuperable_bytes",  "tec_campo_recuperable",  " B",  "bajar"),
]


def comparar_fotos(antes, despues):
    """Diferencia entre dos fotos, campo por campo.

    Cada fila trae: clave de idiomas, valores, diferencia, unidad, y si esa
    diferencia es una mejora, un empeoramiento o nada. Un campo que falte
    en cualquiera de las dos fotos se salta: mejor no enseñar una fila que
    enseñarla con datos inventados.
    """
    filas = []
    for campo, clave, unidad, bueno_si in CAMPOS_COMPARABLES:
        v1 = (antes or {}).get(campo)
        v2 = (despues or {}).get(campo)
        if v1 is None or v2 is None:
            continue
        try:
            diferencia = round(float(v2) - float(v1), 2)
        except (TypeError, ValueError):
            continue
        if abs(diferencia) < 0.01:
            sentido = "igual"
        elif (diferencia < 0 and bueno_si == "bajar") or (diferencia > 0 and bueno_si == "subir"):
            sentido = "mejor"
        else:
            sentido = "peor"
        filas.append({
            "clave": clave, "antes": v1, "despues": v2,
            "diferencia": diferencia, "unidad": unidad, "sentido": sentido,
        })
    return filas


def guardar_foto(carpeta, foto, nombre="foto_sistema.json"):
    try:
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(foto, f, ensure_ascii=False, indent=2)
        return ruta
    except Exception:
        return None


def cargar_foto(carpeta, nombre="foto_sistema.json"):
    try:
        ruta = os.path.join(carpeta, nombre)
        if not os.path.exists(ruta):
            return None
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else None
    except Exception:
        return None


# ============================================================
#  2. Inspector de arranque profundo
# ============================================================

def _run_ps(script, timeout=20):
    if not IS_WINDOWS:
        return ""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout)
        return r.stdout or ""
    except Exception:
        return ""


def _entradas_registro():
    """Las cuatro claves Run de Windows: usuario y máquina, 64 y 32 bits.

    La de 32 bits (WOW6432Node) se mira aparte a propósito: en un Windows
    de 64 bits, un programa de 32 bits que se registra para arrancar acaba
    ahí, y quien solo mira la clave normal no lo ve nunca.
    """
    if not IS_WINDOWS:
        return []
    import winreg
    claves = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
         "HKCU\\...\\Run", 0),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run",
         "HKLM\\...\\Run", 0),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
         "HKLM\\...\\Run (32 bits)", 0),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
         "HKCU\\...\\RunOnce", 0),
    ]
    encontradas = []
    for raiz, ruta, etiqueta, _ in claves:
        try:
            with winreg.OpenKey(raiz, ruta) as clave:
                indice = 0
                while True:
                    try:
                        nombre, valor, _tipo = winreg.EnumValue(clave, indice)
                    except OSError:
                        break
                    encontradas.append({
                        "nombre": nombre, "comando": str(valor),
                        "origen": etiqueta, "tipo": "registro",
                    })
                    indice += 1
        except OSError:
            continue
    return encontradas


def _entradas_carpetas_inicio():
    """Las carpetas Inicio, la del usuario y la de todos los usuarios."""
    if not IS_WINDOWS:
        return []
    carpetas = [
        (os.path.join(os.environ.get("APPDATA", ""),
                      r"Microsoft\Windows\Start Menu\Programs\Startup"), "Carpeta Inicio (usuario)"),
        (os.path.join(os.environ.get("PROGRAMDATA", ""),
                      r"Microsoft\Windows\Start Menu\Programs\Startup"), "Carpeta Inicio (todos)"),
    ]
    encontradas = []
    for carpeta, etiqueta in carpetas:
        if not carpeta or not os.path.isdir(carpeta):
            continue
        try:
            for nombre in os.listdir(carpeta):
                if nombre.lower() == "desktop.ini":
                    continue
                encontradas.append({
                    "nombre": nombre, "comando": os.path.join(carpeta, nombre),
                    "origen": etiqueta, "tipo": "carpeta",
                })
        except OSError:
            continue
    return encontradas


def _entradas_tareas_al_iniciar():
    """Tareas programadas que se disparan al iniciar sesión o al encender.

    Se filtran las de Microsoft: en un Windows normal hay cientos y son
    todas del sistema. Lo que interesa aquí es lo que instaló alguien.
    """
    salida = _run_ps(
        "Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' -and "
        "($_.Triggers | Where-Object { $_.CimClass.CimClassName -match 'LogonTrigger|BootTrigger' }) } | "
        "Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' } | "
        "Select-Object TaskName, TaskPath | ConvertTo-Json -Compress", timeout=40)
    if not salida.strip():
        return []
    try:
        datos = json.loads(salida)
    except ValueError:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    encontradas = []
    for d in datos:
        nombre = (d or {}).get("TaskName")
        if not nombre:
            continue
        encontradas.append({
            "nombre": nombre,
            "comando": (d.get("TaskPath") or "") + str(nombre),
            "origen": "Tarea programada", "tipo": "tarea",
        })
    return encontradas


def inspeccionar_arranque():
    """Todo lo que arranca con Windows, junto y ordenado por origen.

    Es lento (la consulta de tareas programadas tarda lo suyo): llamarla
    siempre desde un hilo.
    """
    entradas = []
    entradas.extend(_entradas_registro())
    entradas.extend(_entradas_carpetas_inicio())
    entradas.extend(_entradas_tareas_al_iniciar())
    entradas.sort(key=lambda e: (e.get("origen", ""), (e.get("nombre") or "").lower()))
    return entradas


# ============================================================
#  3. Registro de métricas a CSV
# ============================================================

class GrabadorMetricas:
    """Apunta CPU, RAM, disco y temperatura a un CSV cada pocos segundos.

    Para el caso clásico de "a veces se pone lento y no sé por qué": se
    deja grabando, se usa el equipo con normalidad, y después se abre el
    CSV con cualquier hoja de cálculo y se busca el pico.

    El archivo se abre y se cierra en CADA muestra, a propósito. Es un pelo
    menos eficiente, pero si el equipo se cuelga —que es justo lo que se
    está intentando diagnosticar— lo grabado hasta ese momento ya está en
    disco. Con el archivo abierto, lo último se habría quedado en el búfer
    y se perdería precisamente la parte interesante.
    """

    COLUMNAS = ["momento", "cpu_pct", "ram_pct", "ram_usada_gb",
                "disco_pct", "temperatura_c", "procesos"]

    def __init__(self, ruta, sysmon, intervalo_seg=5):
        self.ruta = ruta
        self.sysmon = sysmon
        self.intervalo_seg = max(1, int(intervalo_seg))
        self.activo = False
        self.muestras = 0
        self._hilo = None
        self._generacion = 0

    def _cabecera_si_hace_falta(self):
        if os.path.exists(self.ruta) and os.path.getsize(self.ruta) > 0:
            return
        with open(self.ruta, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(self.COLUMNAS)

    def tomar_muestra(self):
        fila = {c: "" for c in self.COLUMNAS}
        fila["momento"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            fila["cpu_pct"] = self.sysmon.get_cpu_info().get("porcentaje")
        except Exception:
            pass
        try:
            ram = self.sysmon.get_ram_info()
            fila["ram_pct"] = ram.get("porcentaje")
            fila["ram_usada_gb"] = ram.get("usado_gb")
        except Exception:
            pass
        try:
            fila["disco_pct"] = self.sysmon.get_disk_info().get("porcentaje")
        except Exception:
            pass
        try:
            fila["temperatura_c"] = self.sysmon.get_cpu_temperature()
        except Exception:
            pass
        try:
            fila["procesos"] = self.sysmon.get_process_count()
        except Exception:
            pass
        return fila

    def escribir(self, fila):
        try:
            self._cabecera_si_hace_falta()
            with open(self.ruta, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([fila.get(c, "") for c in self.COLUMNAS])
            self.muestras += 1
            return True
        except Exception:
            return False

    def iniciar(self, hilo_factoria=None):
        """`hilo_factoria` existe para las pruebas: permite ejecutar el
        bucle sin lanzar un hilo de verdad."""
        if self.activo:
            return False
        self.activo = True
        self._generacion += 1
        mi_generacion = self._generacion
        if hilo_factoria is None:
            import threading
            hilo_factoria = lambda destino: threading.Thread(target=destino, daemon=True)
        self._hilo = hilo_factoria(lambda: self._bucle(mi_generacion))
        self._hilo.start()
        return True

    def _bucle(self, mi_generacion):
        # Mismo patrón de generación que el resto de la app: parar y volver
        # a arrancar deprisa no puede dejar dos bucles escribiendo el mismo
        # archivo, que saldría con las filas entremezcladas.
        while self.activo and mi_generacion == self._generacion:
            self.escribir(self.tomar_muestra())
            for _ in range(self.intervalo_seg * 10):
                if not self.activo or mi_generacion != self._generacion:
                    return
                time.sleep(0.1)

    def detener(self):
        self.activo = False
        return self.muestras
