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

Desde la 1.6.0, además:

  4. SALUD DE DISCOS — estado, desgaste, temperatura y errores, para
     avisar al cliente ANTES de que el disco falle.
  5. SALUD DE BATERÍA — capacidad original contra la actual.
  6. PANTALLAZOS AZULES — cuándo, qué código, y por dónde empezar a mirar.
  7. RESPALDO DE CONTROLADORES — exportarlos antes de formatear y
     reinstalarlos después. Restaurar SÍ cambia el sistema (instala).
  8. INFORME PARA EL CLIENTE — el antes/después y el trabajo hecho, en HTML
     para imprimir o guardar como PDF.

Ninguna añade dependencias: todo sale de herramientas que Windows ya trae
(PowerShell, powercfg, pnputil) y de la librería estándar de Python.
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


# ============================================================
#  4. Salud de discos (SMART, vía los contadores de Windows)
# ============================================================

def salud_discos():
    """Estado de cada disco físico. Devuelve una lista de diccionarios, o
    None si no se pudo preguntar.

    Los contadores de fiabilidad (desgaste, temperatura, horas, errores)
    salen de Get-StorageReliabilityCounter, que necesita administrador y
    que algunos controladores no rellenan: un None ahí significa "Windows
    no lo sabe", y se enseña así, nunca como un cero.
    """
    script = (
        "Get-PhysicalDisk | ForEach-Object { $r = $null; "
        "try { $r = $_ | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}; "
        "[pscustomobject]@{ nombre = $_.FriendlyName; tipo = [string]$_.MediaType; bus = [string]$_.BusType; "
        "salud = [string]$_.HealthStatus; tamano = [int64]$_.Size; "
        "desgaste = $r.Wear; temperatura = $r.Temperature; horas = $r.PowerOnHours; "
        "errores_lectura = $r.ReadErrorsUncorrected; errores_escritura = $r.WriteErrorsUncorrected } "
        "} | ConvertTo-Json -Compress"
    )
    salida = _run_ps(script, timeout=60).strip()
    if not salida:
        return None
    try:
        datos = json.loads(salida)
    except ValueError:
        return None
    if isinstance(datos, dict):
        datos = [datos]
    discos = []
    for d in datos if isinstance(datos, list) else []:
        disco = {k: d.get(k) for k in ("nombre", "tipo", "bus", "salud", "tamano", "desgaste",
                                        "temperatura", "horas", "errores_lectura", "errores_escritura")}
        disco["veredicto"], disco["motivos"] = veredicto_disco(disco)
        discos.append(disco)
    return discos


def veredicto_disco(d):
    """("bien" | "atencion" | "critico", [claves de idiomas con el motivo]).
    Función pura, para probarla con discos inventados."""
    motivos = []
    nivel = "bien"

    def subir(a):
        nonlocal nivel
        orden = ["bien", "atencion", "critico"]
        if orden.index(a) > orden.index(nivel):
            nivel = a

    salud = str(d.get("salud") or "")
    if salud and salud not in ("Healthy", "0"):
        subir("critico")
        motivos.append("salud_motivo_windows")
    desgaste = d.get("desgaste")
    if isinstance(desgaste, (int, float)):
        if desgaste >= 90:
            subir("critico")
            motivos.append("salud_motivo_desgaste_alto")
        elif desgaste >= 70:
            subir("atencion")
            motivos.append("salud_motivo_desgaste")
    errores = sum(v for v in (d.get("errores_lectura"), d.get("errores_escritura"))
                  if isinstance(v, (int, float)))
    if errores > 0:
        subir("atencion")
        motivos.append("salud_motivo_errores")
    temperatura = d.get("temperatura")
    limite = 55 if str(d.get("tipo")).upper() == "HDD" else 70
    if isinstance(temperatura, (int, float)) and temperatura >= limite:
        subir("atencion")
        motivos.append("salud_motivo_temperatura")
    return nivel, motivos


# ============================================================
#  5. Salud de la batería
# ============================================================

def salud_bateria(carpeta_temporal=None):
    """Capacidad de diseño contra la actual, de powercfg /batteryreport.
    Devuelve una lista (vacía si el equipo no tiene batería) o None si
    powercfg falló.

    Se lee el XML y no el HTML: el HTML cambia de formato entre versiones de
    Windows y está traducido; el XML no.
    """
    if not IS_WINDOWS:
        return None
    import tempfile
    import xml.etree.ElementTree as ET
    carpeta = carpeta_temporal or tempfile.gettempdir()
    ruta = os.path.join(carpeta, f"techclean_bateria_{os.getpid()}.xml")
    try:
        r = subprocess.run(["powercfg", "/batteryreport", "/xml", "/output", ruta], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        if r.returncode != 0 or not os.path.exists(ruta):
            return None
        raiz = ET.parse(ruta).getroot()
    except Exception:
        return None
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    return leer_baterias_xml(raiz)


def leer_baterias_xml(raiz):
    """Separado de salud_bateria para poder probarlo con un XML inventado."""
    def sin_ns(etiqueta):
        return etiqueta.split("}", 1)[-1]

    def entero(texto):
        try:
            return int(float(texto))
        except (TypeError, ValueError):
            return None

    baterias = []
    for nodo in raiz.iter():
        if sin_ns(nodo.tag) != "Battery":
            continue
        campos = {sin_ns(h.tag): (h.text or "").strip() for h in nodo}
        diseno = entero(campos.get("DesignCapacity"))
        actual = entero(campos.get("FullChargeCapacity"))
        if not diseno:
            continue
        porcentaje = round(actual * 100 / diseno) if actual is not None else None
        if porcentaje is None:
            veredicto = "atencion"
        elif porcentaje >= 80:
            veredicto = "bien"
        elif porcentaje >= 60:
            veredicto = "atencion"
        else:
            veredicto = "critico"
        baterias.append({
            "nombre": campos.get("Id") or "", "fabricante": campos.get("Manufacturer") or "",
            "quimica": campos.get("Chemistry") or "", "diseno_mwh": diseno, "actual_mwh": actual,
            "ciclos": entero(campos.get("CycleCount")), "porcentaje": porcentaje, "veredicto": veredicto,
        })
    return baterias


def abrir_informe_bateria_windows(carpeta):
    """El informe completo de Windows (HTML), para quien quiera el detalle
    de cada carga. Devuelve la ruta o None."""
    ruta = os.path.join(carpeta, "informe_bateria_windows.html")
    try:
        r = subprocess.run(["powercfg", "/batteryreport", "/output", ruta], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        if r.returncode == 0 and os.path.exists(ruta):
            os.startfile(ruta)
            return ruta
    except Exception:
        pass
    return None


# ============================================================
#  6. Pantallazos azules y apagados inesperados
# ============================================================

# Los códigos de parada más comunes, con su nombre oficial y QUÉ SUELE
# estar detrás. Es una pista para empezar a buscar, no un diagnóstico: el
# mismo código puede tener varias causas, y la interfaz lo dice.
CODIGOS_PARADA = {
    0x0A: ("IRQL_NOT_LESS_OR_EQUAL", "bsod_causa_driver"),
    0x19: ("BAD_POOL_HEADER", "bsod_causa_driver"),
    0x1A: ("MEMORY_MANAGEMENT", "bsod_causa_ram"),
    0x1E: ("KMODE_EXCEPTION_NOT_HANDLED", "bsod_causa_driver"),
    0x24: ("NTFS_FILE_SYSTEM", "bsod_causa_disco"),
    0x3B: ("SYSTEM_SERVICE_EXCEPTION", "bsod_causa_driver"),
    0x50: ("PAGE_FAULT_IN_NONPAGED_AREA", "bsod_causa_ram"),
    0x7A: ("KERNEL_DATA_INPAGE_ERROR", "bsod_causa_disco"),
    0x7B: ("INACCESSIBLE_BOOT_DEVICE", "bsod_causa_disco"),
    0x7E: ("SYSTEM_THREAD_EXCEPTION_NOT_HANDLED", "bsod_causa_driver"),
    0x9F: ("DRIVER_POWER_STATE_FAILURE", "bsod_causa_energia"),
    0xC2: ("BAD_POOL_CALLER", "bsod_causa_driver"),
    0xD1: ("DRIVER_IRQL_NOT_LESS_OR_EQUAL", "bsod_causa_driver"),
    0xEF: ("CRITICAL_PROCESS_DIED", "bsod_causa_sistema"),
    0xF4: ("CRITICAL_OBJECT_TERMINATION", "bsod_causa_disco"),
    0x101: ("CLOCK_WATCHDOG_TIMEOUT", "bsod_causa_hardware"),
    0x116: ("VIDEO_TDR_FAILURE", "bsod_causa_grafica"),
    0x117: ("VIDEO_TDR_TIMEOUT_DETECTED", "bsod_causa_grafica"),
    0x124: ("WHEA_UNCORRECTABLE_ERROR", "bsod_causa_hardware"),
    0x133: ("DPC_WATCHDOG_VIOLATION", "bsod_causa_driver"),
    0x139: ("KERNEL_SECURITY_CHECK_FAILURE", "bsod_causa_driver"),
    0x154: ("UNEXPECTED_STORE_EXCEPTION", "bsod_causa_disco"),
    0x1E0: ("ATTEMPTED_WRITE_TO_READONLY_MEMORY", "bsod_causa_driver"),
}


def interpretar_codigo_parada(texto):
    """De "0x0000009f (0x3, ...)" saca (codigo, nombre, clave_de_causa).
    Los códigos 0x1000xxxx son la variante del mismo error con más
    parámetros: se normalizan al código base."""
    import re
    m = re.search(r"0x([0-9a-fA-F]+)", str(texto or ""))
    if not m:
        return None, None, "bsod_causa_desconocida"
    codigo = int(m.group(1), 16)
    base = codigo & ~0x10000000 if codigo & 0x10000000 else codigo
    nombre, causa = CODIGOS_PARADA.get(base, (None, "bsod_causa_desconocida"))
    return base, nombre, causa


def historial_fallos(dias_apagados=90):
    """{"pantallazos": [...], "apagados": n} o None.

    pantallazos: el evento 1001 de WER (lo escribe Windows al reiniciar
    después de un pantallazo azul). apagados: el evento 41 de Kernel-Power
    (el equipo se apagó sin pasar por un apagado normal: corte de luz,
    botón mantenido, cuelgue). Muchos 41 sin pantallazos suelen ser
    energía o temperatura, no software.
    """
    script = (
        "$p = Get-WinEvent -FilterHashtable @{LogName='System'; "
        "ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; Id=1001} -MaxEvents 50 "
        "-ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ "
        "fecha = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); codigo = [string]$_.Properties[0].Value } }; "
        "$a = (Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; "
        f"Id=41; StartTime=(Get-Date).AddDays(-{int(dias_apagados)})}} -ErrorAction SilentlyContinue "
        "| Measure-Object).Count; "
        "[pscustomobject]@{ pantallazos = @($p); apagados = $a } | ConvertTo-Json -Compress -Depth 3"
    )
    salida = _run_ps(script, timeout=60).strip()
    if not salida:
        return None
    try:
        datos = json.loads(salida)
    except ValueError:
        return None
    pantallazos = []
    for p in datos.get("pantallazos") or []:
        if not isinstance(p, dict):
            continue
        codigo, nombre, causa = interpretar_codigo_parada(p.get("codigo"))
        pantallazos.append({"fecha": p.get("fecha") or "", "codigo": codigo, "nombre": nombre, "causa": causa})
    try:
        apagados = int(datos.get("apagados") or 0)
    except (TypeError, ValueError):
        apagados = 0
    return {"pantallazos": pantallazos, "apagados": apagados, "dias": int(dias_apagados)}


# ============================================================
#  7. Respaldo de controladores
# ============================================================

def _ruta_segura(carpeta):
    """La carpeta va a un comando de pnputil: tiene que existir y no puede
    llevar comillas (las listas de subprocess ya escapan los espacios)."""
    carpeta = os.path.abspath(str(carpeta or ""))
    if '"' in carpeta or not os.path.isdir(carpeta):
        return None
    return carpeta


def contar_drivers(carpeta):
    """(cantidad de .inf, bytes totales) dentro de una carpeta."""
    infs = 0
    total = 0
    for raiz, _, archivos in os.walk(carpeta):
        for a in archivos:
            if a.lower().endswith(".inf"):
                infs += 1
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return infs, total


def exportar_drivers(carpeta, opt, callback_progreso=None, evento_cancelar=None):
    """pnputil /export-driver * — copia TODOS los controladores de terceros
    (los que no vienen con Windows) a una carpeta. Es lo que hay que hacer
    antes de formatear: después se reinstalan sin buscar uno por uno en la
    web del fabricante. Devuelve (exito, cantidad, bytes, resumen)."""
    carpeta = _ruta_segura(carpeta)
    if carpeta is None:
        return False, 0, 0, ""
    exito, resumen, cancelado = opt._ejecutar_reparacion_cancelable(
        ["pnputil", "/export-driver", "*", carpeta], timeout_seg=1800,
        callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    cantidad, total = contar_drivers(carpeta)
    esperados, exportados = contar_exportados(resumen)
    # "Éxito" es que estén TODOS. Probado de verdad: con una ruta de destino
    # larga, pnputil se cortó en 54 de 91 ("nombre de archivo demasiado
    # largo") y, mirando solo si había .inf en la carpeta, se daba por bueno.
    completo = esperados is None or exportados == esperados
    exito_real = exito and not cancelado and cantidad > 0 and completo
    return exito_real, cantidad, total, resumen, esperados, exportados


def contar_exportados(resumen):
    """Las dos últimas líneas de pnputil /export-driver son los paquetes
    totales y los exportados ("...totales: 91", "...exportados: 54"). Están
    traducidas, así que se leen solo los números del final de línea.
    Devuelve (totales, exportados) o (None, None)."""
    import re
    numeros = [int(m.group(1)) for m in re.finditer(r":\s*(\d+)\s*$", resumen or "", re.M)]
    if len(numeros) < 2:
        return None, None
    return numeros[-2], numeros[-1]


def restaurar_drivers(carpeta, opt, callback_progreso=None, evento_cancelar=None):
    """pnputil /add-driver *.inf /subdirs /install — instala todo lo que
    haya en una carpeta exportada antes. Devuelve (exito, resumen)."""
    carpeta = _ruta_segura(carpeta)
    if carpeta is None or contar_drivers(carpeta)[0] == 0:
        return False, ""
    exito, resumen, cancelado = opt._ejecutar_reparacion_cancelable(
        ["pnputil", "/add-driver", os.path.join(carpeta, "*.inf"), "/subdirs", "/install"],
        timeout_seg=3600, callback_progreso=callback_progreso, evento_cancelar=evento_cancelar)
    return exito and not cancelado, resumen


# ============================================================
#  8. Informe para el cliente
# ============================================================

def _formatear_valor(valor, unidad):
    if unidad == " B" and isinstance(valor, (int, float)):
        for u in ("B", "KB", "MB", "GB", "TB"):
            if abs(valor) < 1024:
                return f"{valor:.1f} {u}" if u != "B" else f"{int(valor)} B"
            valor /= 1024
        return f"{valor:.1f} PB"
    return f"{valor}{unidad}"


# Clave de idiomas de cada nivel de salud (completa, no armada con "+":
# verificar_idiomas tiene que poder ver que se usan).
NIVELES_SALUD = {"bien": "salud_nivel_bien", "atencion": "salud_nivel_atencion", "critico": "salud_nivel_critico"}


def generar_informe_html(datos, t):
    """El informe que el técnico le entrega al cliente, en HTML listo para
    imprimir o guardar como PDF desde el navegador (Ctrl+P). HTML y no PDF
    a propósito: generar PDF exigiría una librería más dentro del .exe, y
    cualquier navegador ya sabe imprimir a PDF.

    `datos`: {"equipo", "tecnico", "cliente", "antes", "despues", "filas",
    "acciones", "discos", "baterias", "fallos", "notas"}; todo opcional.
    `t` se pasa como parámetro para poder probarlo sin la app.
    """
    from html import escape as e

    def fila(*celdas, clase=""):
        return f'<tr class="{clase}">' + "".join(f"<td>{c}</td>" for c in celdas) + "</tr>"

    equipo = datos.get("equipo") or {}
    partes = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{e(t('inf_titulo'))}</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:32px auto;color:#1d2330;"
        "padding:0 16px}h1{margin:0 0 4px;font-size:24px}h2{font-size:16px;margin:28px 0 8px;"
        "border-bottom:2px solid #e3e6ec;padding-bottom:4px}table{width:100%;border-collapse:collapse;"
        "font-size:13px}td{padding:6px 8px;border-bottom:1px solid #eef0f4;vertical-align:top}"
        ".meta{color:#5b6475;font-size:13px}.mejor{color:#1e8e4e;font-weight:600}"
        ".peor{color:#c0392b;font-weight:600}.atencion{color:#b7791f;font-weight:600}"
        ".critico{color:#c0392b;font-weight:600}.bien{color:#1e8e4e;font-weight:600}"
        ".pie{margin-top:36px;font-size:11px;color:#8a92a3}@media print{body{margin:0}}</style>",
        "</head><body>",
        f"<h1>{e(t('inf_titulo'))}</h1>",
        f"<div class='meta'>{e(t('inf_fecha', fecha=datetime.now().strftime('%Y-%m-%d %H:%M')))}",
    ]
    if datos.get("tecnico"):
        partes.append(" · " + e(t("inf_tecnico", nombre=datos["tecnico"])))
    if datos.get("cliente"):
        partes.append(" · " + e(t("inf_cliente", nombre=datos["cliente"])))
    partes.append("</div>")

    partes.append(f"<h2>{e(t('inf_equipo'))}</h2><table>")
    for clave, etiqueta in (("hostname", "inf_eq_nombre"), ("sistema_operativo", "inf_eq_so"),
                            ("procesador", "inf_eq_cpu"), ("ram", "inf_eq_ram"),
                            ("placa_madre", "inf_eq_placa")):
        if equipo.get(clave):
            partes.append(fila(e(t(etiqueta)), e(str(equipo[clave]))))
    partes.append("</table>")

    filas = datos.get("filas") or []
    if filas:
        antes = datos.get("antes") or {}
        despues = datos.get("despues") or {}
        partes.append(f"<h2>{e(t('inf_antes_despues'))}</h2>")
        partes.append(f"<div class='meta'>{e(t('inf_momentos', antes=antes.get('momento', ''), despues=despues.get('momento', '')))}</div><table>")
        partes.append(fila(f"<b>{e(t('inf_col_medida'))}</b>", f"<b>{e(t('inf_col_antes'))}</b>",
                           f"<b>{e(t('inf_col_despues'))}</b>", f"<b>{e(t('inf_col_cambio'))}</b>"))
        for f in filas:
            signo = "+" if f["diferencia"] > 0 else ""
            cambio = f"{signo}{_formatear_valor(f['diferencia'], f['unidad'])}"
            partes.append(fila(e(t(f["clave"])), e(_formatear_valor(f["antes"], f["unidad"])),
                               e(_formatear_valor(f["despues"], f["unidad"])),
                               f"<span class='{f['sentido']}'>{e(cambio)}</span>"))
        partes.append("</table>")

    acciones = datos.get("acciones") or []
    if acciones:
        partes.append(f"<h2>{e(t('inf_trabajo'))}</h2><table>")
        for a in acciones:
            marca = "✓" if a.get("exito") else "✗"
            partes.append(fila(e(a.get("timestamp", "")[11:16]), f"{marca} {e(a.get('accion', ''))}",
                               e(str(a.get("resultado", ""))[:220])))
        partes.append("</table>")

    discos = datos.get("discos") or []
    baterias = datos.get("baterias") or []
    fallos = datos.get("fallos")
    if discos or baterias or fallos:
        partes.append(f"<h2>{e(t('inf_salud'))}</h2><table>")
        for d in discos:
            detalle = ", ".join(t(m) for m in d.get("motivos") or []) or t("salud_sin_problemas")
            partes.append(fila(e(t("inf_disco", nombre=d.get("nombre") or "?")),
                               f"<span class='{d['veredicto']}'>{e(t(NIVELES_SALUD[d['veredicto']]))}</span>",
                               e(detalle)))
        for b in baterias:
            partes.append(fila(e(t("inf_bateria")),
                               f"<span class='{b['veredicto']}'>{e(t(NIVELES_SALUD[b['veredicto']]))}</span>",
                               e(t("bat_resumen", porcentaje=b.get("porcentaje"), ciclos=b.get("ciclos") or "?"))))
        if fallos:
            n = len(fallos.get("pantallazos") or [])
            partes.append(fila(e(t("inf_estabilidad")),
                               f"<span class='{'atencion' if n or fallos.get('apagados') else 'bien'}'>"
                               f"{e(t('inf_estabilidad_valor', pantallazos=n, apagados=fallos.get('apagados', 0), dias=fallos.get('dias', 90)))}</span>",
                               ""))
        partes.append("</table>")

    if datos.get("notas"):
        partes.append(f"<h2>{e(t('inf_notas'))}</h2><p>{e(datos['notas'])}</p>")

    partes.append(f"<div class='pie'>{e(t('inf_pie'))}</div></body></html>")
    return "".join(partes)
