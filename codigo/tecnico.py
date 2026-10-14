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

# PowerShell escribe por una tubería en la página de códigos OEM (cp850 en un
# Windows en español) y Python lee con la ANSI (cp1252): "Optimización" salía
# "Optimizaci¢n" en Servicios, Drivers, Tareas... (BUG corregido en la 1.8.0).
# Las llamadas que leen texto le piden UTF-8 a PowerShell con esto delante del
# script, y lo leen con encoding="utf-8".
PS_UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"

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
        foto["apps_inicio_activas"] = opt.contar_inicio_activo()
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
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_UTF8 + script],
                            capture_output=True, encoding="utf-8", errors="replace",
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

# ---- NVMe directo (1.8.0) ----
# Se le pide al disco su registro de salud (el "log 0x02" de la norma NVMe)
# con IOCTL_STORAGE_QUERY_PROPERTY, como CrystalDiskInfo. Probado en el
# equipo del desarrollador: funciona SIN administrador (abriendo el disco sin
# permisos de lectura ni escritura) y tarda milisegundos, frente a los 8 s de
# Get-StorageReliabilityCounter con WMI lento, que además sin administrador
# no rellena nada. Para discos SATA o USB no hay equivalente sin
# administrador: esos siguen por PowerShell.
_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
_BUS = {7: "USB", 11: "SATA", 17: "NVMe", 3: "ATA", 8: "RAID", 10: "SAS", 12: "SD", 13: "MMC"}


def _abrir_disco(numero):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    # Acceso 0: solo para preguntar al dispositivo, sin leer el disco. Así
    # no hace falta administrador. Compartido lectura/escritura, OPEN_EXISTING.
    manejador = k32.CreateFileW(rf"\\.\PhysicalDrive{int(numero)}", 0, 3, None, 3, 0, None)
    if manejador in (None, wintypes.HANDLE(-1).value):
        return None, k32
    return manejador, k32


def _consulta_disco(k32, manejador, entrada, tamano_salida):
    import ctypes
    from ctypes import wintypes
    salida = ctypes.create_string_buffer(tamano_salida)
    devueltos = wintypes.DWORD()
    ok = k32.DeviceIoControl(wintypes.HANDLE(manejador), _IOCTL_STORAGE_QUERY_PROPERTY, entrada, len(entrada),
                             salida, tamano_salida, ctypes.byref(devueltos), None)
    return salida.raw[:devueltos.value] if ok else None


def leer_registro_nvme(crudo):
    """El registro de salud NVMe (512 bytes) en un diccionario. Pura, para
    probarla con registros inventados."""
    def entero(desde, largo):
        return int.from_bytes(crudo[desde:desde + largo], "little")
    kelvin = entero(1, 2)
    return {
        "aviso_critico": crudo[0],
        "temperatura": kelvin - 273 if kelvin else None,
        "repuesto": crudo[3], "repuesto_minimo": crudo[4],
        "desgaste": crudo[5],
        # "Unidades de datos": miles de bloques de 512 bytes.
        "escritos_bytes": entero(48, 16) * 512000, "leidos_bytes": entero(32, 16) * 512000,
        "ciclos": entero(112, 16), "horas": entero(128, 16),
        "apagados_inseguros": entero(144, 16), "errores_medio": entero(160, 16),
    }


def _disco_directo(numero):
    """Modelo, bus y, si es NVMe, su registro de salud. None si no hay
    disco con ese número."""
    import struct
    manejador, k32 = _abrir_disco(numero)
    if manejador is None:
        return None
    try:
        # StorageDeviceProperty (0), PropertyStandardQuery (0).
        desc = _consulta_disco(k32, manejador, struct.pack("<II4x", 0, 0), 1024)
        if not desc or len(desc) < 32:
            return None

        def cadena(offset):
            if not offset or offset >= len(desc):
                return ""
            return desc[offset:desc.index(b"\0", offset)].decode("ascii", "replace").strip()
        vendor_off, producto_off = struct.unpack_from("<II", desc, 12)
        bus = struct.unpack_from("<I", desc, 28)[0]
        nombre = " ".join(x for x in (cadena(vendor_off), cadena(producto_off)) if x)
        disco = {"numero": numero, "nombre": nombre, "bus": _BUS.get(bus, ""), "tipo": "SSD" if bus == 17 else ""}
        if bus == 17:
            # StorageDeviceProtocolSpecificProperty (50), NVMe (3), página de
            # registro (2), registro 0x02; los datos van detrás de la cabecera
            # de 40 bytes que describe la petición.
            peticion = struct.pack("<II10I", 50, 0, 3, 2, 2, 0, 40, 512, 0, 0, 0, 0) + bytes(512)
            respuesta = _consulta_disco(k32, manejador, peticion, len(peticion))
            if respuesta and len(respuesta) >= 8 + 40 + 512:
                disco.update(leer_registro_nvme(respuesta[8 + 40:8 + 40 + 512]))
        return disco
    finally:
        k32.CloseHandle(manejador)


def discos_directos(maximo=16):
    """Los discos físicos que responden a una consulta directa."""
    if not IS_WINDOWS:
        return []
    encontrados = []
    for n in range(maximo):
        try:
            d = _disco_directo(n)
        except Exception:
            d = None
        if d:
            encontrados.append(d)
    return encontrados


def salud_discos():
    """Estado de cada disco físico. Devuelve una lista de diccionarios, o
    None si no se pudo preguntar.

    1.8.0: primero la consulta directa (NVMe: milisegundos y sin
    administrador). Solo si queda algún disco sin datos (SATA, USB) se pasa
    por Get-StorageReliabilityCounter, que necesita administrador y que
    algunos controladores no rellenan: un None ahí significa "Windows no lo
    sabe", y se enseña así, nunca como un cero.
    """
    directos = discos_directos()
    if directos and all(d.get("horas") is not None for d in directos):
        for d in directos:
            d["salud"] = "Healthy" if not d.get("aviso_critico") else "Warning"
            d["errores_lectura"] = d.get("errores_medio")
            d["veredicto"], d["motivos"] = veredicto_disco(d)
        return directos
    return _salud_discos_powershell(directos)


def _salud_discos_powershell(directos=()):
    """Get-PhysicalDisk + Get-StorageReliabilityCounter. Lo que ya se leyó
    directo (un NVMe en un equipo que además tiene un SATA) se respeta."""
    script = (
        "Get-PhysicalDisk | ForEach-Object { $r = $null; "
        "try { $r = $_ | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}; "
        "[pscustomobject]@{ numero = [string]$_.DeviceId; nombre = $_.FriendlyName; "
        "tipo = [string]$_.MediaType; bus = [string]$_.BusType; "
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
    por_numero = {str(d["numero"]): d for d in directos}
    discos = []
    for d in datos if isinstance(datos, list) else []:
        disco = {k: d.get(k) for k in ("nombre", "tipo", "bus", "salud", "tamano", "desgaste",
                                        "temperatura", "horas", "errores_lectura", "errores_escritura")}
        directo = por_numero.get(str(d.get("numero")))
        if directo:
            for clave, valor in directo.items():
                if valor is not None and disco.get(clave) in (None, ""):
                    disco[clave] = valor
            if disco.get("errores_lectura") is None:
                disco["errores_lectura"] = directo.get("errores_medio")
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
    # NVMe (1.8.0): el propio disco avisa (repuesto por debajo del mínimo,
    # temperatura, fiabilidad degradada, solo lectura...).
    if d.get("aviso_critico"):
        subir("critico")
        motivos.append("salud_motivo_aviso_nvme")
    repuesto, minimo = d.get("repuesto"), d.get("repuesto_minimo")
    if isinstance(repuesto, int) and isinstance(minimo, int) and minimo and repuesto <= minimo:
        subir("critico")
        motivos.append("salud_motivo_repuesto")
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


def nombre_app_srum(app):
    r""""\Device\HarddiskVolume3\Program Files\Google\Chrome\chrome.exe" ->
    "chrome"; "Microsoft.WindowsTerminal_8wekyb3d8bbwe!App" -> "Windows
    Terminal"."""
    import re
    app = (app or "").strip()
    if "\\" in app or app.lower().endswith(".exe"):
        return os.path.splitext(app.replace("/", "\\").rsplit("\\", 1)[-1])[0] or app
    familia = app.split("!", 1)[0].split("_", 1)[0]
    parte = familia.rsplit(".", 1)[-1] if "." in familia else familia
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", parte) or app


def leer_srum_csv(texto):
    """El CSV de powercfg /srumutil -> [{app, nombre, energia, pct,
    con_bateria}] de más a menos gasto, o None si no se reconoce.

    Microsoft no documenta las columnas, así que se buscan por el nombre:
    la de la app (AppId), la de energía total (TotalEnergyConsumption) o, si
    no la hay, la suma de las de cada parte (CPU, pantalla, disco, red...:
    las que acaban en EnergyConsumption, sin las de "WorkOnBehalf", que
    repiten lo que hizo un proceso por otro), y OnBattery. Pura: la prueba
    le pasa un CSV inventado."""
    import csv
    import io
    filas = list(csv.reader(io.StringIO(texto or "")))
    for i, fila in enumerate(filas):
        bajos = [c.strip().lower() for c in fila]
        col_app = next((j for j, c in enumerate(bajos) if c in ("appid", "appname", "app")), None)
        if col_app is not None:
            break
    else:
        return None
    total = [j for j, c in enumerate(bajos) if c == "totalenergyconsumption"]
    energia = total or [j for j, c in enumerate(bajos) if c.endswith("energyconsumption")
                        and "workonbehalf" not in c and "loss" not in c]
    if not energia:
        return None
    col_bateria = next((j for j, c in enumerate(bajos) if c == "onbattery"), None)
    por_app, con_bateria = {}, {}
    necesarias = max(energia + [col_app] + ([col_bateria] if col_bateria is not None else []))
    for fila in filas[i + 1:]:
        if len(fila) <= necesarias:
            continue
        app = fila[col_app].strip()
        try:
            gasto = sum(float(fila[j] or 0) for j in energia)
        except ValueError:
            continue
        if not app or gasto <= 0:
            continue
        por_app[app] = por_app.get(app, 0.0) + gasto
        if col_bateria is not None and fila[col_bateria].strip().lower() in ("1", "true"):
            con_bateria[app] = con_bateria.get(app, 0.0) + gasto
    suma = sum(por_app.values())
    if not suma:
        return []
    # Varias entradas pueden ser el mismo programa (rutas distintas): por nombre.
    juntas = {}
    for app, gasto in por_app.items():
        nombre = nombre_app_srum(app)
        dato = juntas.setdefault(nombre.lower(), {"app": app, "nombre": nombre, "energia": 0.0, "con_bateria": 0.0})
        dato["energia"] += gasto
        dato["con_bateria"] += con_bateria.get(app, 0.0)
    apps = sorted(juntas.values(), key=lambda a: a["energia"], reverse=True)
    for a in apps:
        a["pct"] = round(a["energia"] * 100 / suma, 1)
    return apps


def consumo_energia_apps():
    """Qué apps gastaron más energía (últimos 7 días, la estimación de
    Windows). {"apps": [...]} o {"error": "admin" | "fallo"}: powercfg
    /srumutil solo funciona como administrador (sin él: "SruUpdateStats
    failed", estado 5)."""
    if not IS_WINDOWS:
        return {"error": "fallo"}
    import ctypes
    import tempfile
    ruta = os.path.join(tempfile.gettempdir(), f"techclean_srum_{os.getpid()}.csv")
    try:
        r = subprocess.run(["powercfg", "/srumutil", "/output", ruta, "/csv"], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
        if r.returncode != 0 or not os.path.exists(ruta):
            return {"error": "admin" if not ctypes.windll.shell32.IsUserAnAdmin() else "fallo"}
        with open(ruta, "rb") as f:
            crudo = f.read()
    except Exception:
        return {"error": "fallo"}
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    for codificacion in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            apps = leer_srum_csv(crudo.decode(codificacion))
        except UnicodeDecodeError:
            continue
        if apps is not None:
            return {"apps": apps}
    return {"error": "fallo"}


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


def diagnostico_fallos(dias=30):
    """Lo que el registro de eventos de Windows dice de los últimos `dias`,
    para Reparar → Diagnóstico de fallos (1.8.0). None si no se pudo leer.

    - apagados: cada evento 41 de Kernel-Power (el equipo se apagó sin un
      apagado normal), con su código de pantallazo si lo hubo. Hasta la
      1.7.0 los pantallazos se contaban solo por el evento 1001, que Windows
      escribe al volver a arrancar SI llegó a guardar el informe: en el
      equipo del desarrollador había un 0x9F el 28/09 que solo constaba en
      el 41. También si pasó durante la suspensión.
    - apps: las que se cerraron solas (evento 1000 de "Application Error").
    - hardware: errores WHEA (la CPU, la RAM o el bus avisando de fallos).
    - disco: avisos de los drivers de disco y del sistema de archivos.
      SIEMPRE filtrando por proveedor: los números de evento se repiten
      entre proveedores (el 153 de Kernel-Boot es un aviso de arranque; el 7
      de BTHUSB, del Bluetooth). Contando solo por número salían 39 "errores
      de disco" que no lo eran. Y aun por proveedor hay que leerlos: los 161
      de volmgr dicen que no se pudo GUARDAR el volcado de un pantallazo
      (por eso no hubo informe 1001), no que el disco falle.
    """
    script = (
        f"$desde = (Get-Date).AddDays(-{int(dias)}); "
        "function D($e, $n) { (([xml]$e.ToXml()).Event.EventData.Data | Where-Object { $_.Name -eq $n }).'#text' }; "
        "$ap = @(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; "
        "Id=41; StartTime=$desde} -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ "
        "fecha = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); codigo = [string](D $_ 'BugcheckCode'); "
        "suspension = [string](D $_ 'SleepInProgress'); boton = [string](D $_ 'PowerButtonTimestamp') } }); "
        "$bs = @(Get-WinEvent -FilterHashtable @{LogName='System'; "
        "ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; Id=1001; StartTime=$desde} "
        "-ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ "
        "fecha = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); codigo = [string]$_.Properties[0].Value } }); "
        "$apps = @(Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'; "
        "Id=1000; StartTime=$desde} -ErrorAction SilentlyContinue | ForEach-Object { [string]$_.Properties[0].Value } "
        "| Group-Object | Sort-Object Count -Descending | Select-Object -First 5 | "
        "ForEach-Object { [pscustomobject]@{ nombre = $_.Name; veces = $_.Count } }); "
        "$hw = @(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; "
        "StartTime=$desde} -ErrorAction SilentlyContinue).Count; "
        "$dk = @(Get-WinEvent -FilterHashtable @{LogName='System'; "
        "ProviderName='disk','Ntfs','stornvme','storahci','iaStorA','iaStorAC','volmgr'; Level=1,2,3; "
        "StartTime=$desde} -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ "
        "fecha = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); proveedor = $_.ProviderName; id = $_.Id; "
        "unidad = [string](D $_ 'DriveName') } }); "
        "[pscustomobject]@{ apagados = $ap; pantallazos = $bs; apps = $apps; hardware = $hw; disco = $dk } "
        "| ConvertTo-Json -Compress -Depth 3"
    )
    salida = _run_ps(script, timeout=90).strip()
    if not salida:
        return None
    try:
        datos = json.loads(salida)
    except ValueError:
        return None
    if not isinstance(datos, dict):
        return None
    return leer_diagnostico(datos, dias)


def _lista(valor):
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def leer_diagnostico(datos, dias=30):
    """El JSON de diagnostico_fallos, ordenado y con cada código explicado.
    Pura: la prueba le pasa datos inventados."""
    def numero(texto):
        try:
            return int(str(texto).strip(), 0) if str(texto).strip() else 0
        except ValueError:
            return 0

    apagados = []
    for a in _lista(datos.get("apagados")):
        if not isinstance(a, dict):
            continue
        codigo = numero(a.get("codigo"))
        base, nombre, causa = interpretar_codigo_parada(hex(codigo)) if codigo else (None, None, None)
        apagados.append({
            "fecha": a.get("fecha") or "", "codigo": base, "nombre": nombre, "causa": causa,
            "suspension": numero(a.get("suspension")) != 0,
            "boton": numero(a.get("boton")) != 0,
        })
    # Un pantallazo con informe (1001) suele tener su apagado (41) unos
    # minutos antes: se cuentan una vez, por el código y el día.
    con_codigo = {(a["codigo"], a["fecha"][:10]) for a in apagados if a["codigo"]}
    pantallazos = [dict(a, origen="apagado") for a in apagados if a["codigo"]]
    for p in _lista(datos.get("pantallazos")):
        if not isinstance(p, dict):
            continue
        base, nombre, causa = interpretar_codigo_parada(p.get("codigo"))
        if (base, (p.get("fecha") or "")[:10]) in con_codigo:
            continue
        pantallazos.append({"fecha": p.get("fecha") or "", "codigo": base, "nombre": nombre, "causa": causa,
                            "origen": "informe"})
    pantallazos.sort(key=lambda p: p["fecha"], reverse=True)
    apagados.sort(key=lambda a: a["fecha"], reverse=True)
    # "bad_module_info" es lo que pone Windows cuando no sabe qué programa era.
    apps = [{"nombre": a.get("nombre") if a.get("nombre") not in (None, "", "bad_module_info") else None,
             "veces": int(a.get("veces") or 0)}
            for a in _lista(datos.get("apps")) if isinstance(a, dict)]

    def entero(valor):
        try:
            return int(valor or 0)
        except (TypeError, ValueError):
            return 0
    # Los avisos de disco, por lo que de verdad dicen.
    sistema_archivos = {}
    disco = []
    volcado_fallido = False
    for e in _lista(datos.get("disco")):
        if not isinstance(e, dict):
            continue
        proveedor, ident = str(e.get("proveedor") or ""), entero(e.get("id"))
        if proveedor.lower() == "volmgr" and ident in (45, 46, 161):
            volcado_fallido = True
        elif proveedor.lower() == "ntfs":
            unidad = (e.get("unidad") or "").strip() or "?"
            sistema_archivos.setdefault(unidad, e.get("fecha") or "")
        else:
            disco.append({"fecha": e.get("fecha") or "", "proveedor": proveedor, "id": ident})
    return {"dias": int(dias), "apagados": apagados, "pantallazos": pantallazos, "apps": apps,
            "hardware": entero(datos.get("hardware")), "disco": len(disco), "disco_eventos": disco,
            "sistema_archivos": [{"unidad": u, "fecha": f} for u, f in sorted(sistema_archivos.items())],
            "volcado_fallido": volcado_fallido}


def veredicto_fallos(diag):
    """("bien" | "atencion" | "critico", [claves de idiomas]) para el
    resumen. Pura."""
    motivos = []
    nivel = "bien"
    orden = ["bien", "atencion", "critico"]

    def subir(a):
        nonlocal nivel
        if orden.index(a) > orden.index(nivel):
            nivel = a
    if diag["hardware"]:
        subir("critico")
        motivos.append("fallos_motivo_hardware")
    if diag["disco"]:
        subir("atencion")
        motivos.append("fallos_motivo_disco")
    if diag.get("sistema_archivos"):
        subir("atencion")
        motivos.append("fallos_motivo_ntfs")
    if len(diag["pantallazos"]) >= 2:
        subir("critico")
        motivos.append("fallos_motivo_pantallazos")
    elif diag["pantallazos"]:
        subir("atencion")
        motivos.append("fallos_motivo_pantallazo")
    sin_codigo = [a for a in diag["apagados"] if not a["codigo"]]
    if len(sin_codigo) >= 3:
        subir("atencion")
        motivos.append("fallos_motivo_apagados")
    if any(a["suspension"] for a in diag["apagados"]):
        subir("atencion")
        motivos.append("fallos_motivo_suspension")
    if sum(a["veces"] for a in diag["apps"]) >= 5:
        subir("atencion")
        motivos.append("fallos_motivo_apps")
    return nivel, motivos


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
    web del fabricante. Devuelve (exito, cantidad, bytes, resumen, esperados,
    exportados).

    BUG corregido (1.8.0): con una carpeta no válida devolvía solo 4 valores;
    el mensaje de error de la interfaz lee el 5.º y el 6.º, el hilo moría y
    la pantalla se quedaba en "Trabajando..." para siempre."""
    carpeta = _ruta_segura(carpeta)
    if carpeta is None:
        return False, 0, 0, "", None, None
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
    """El informe que el técnico le entrega al cliente: el antes y el
    después, el trabajo hecho y la salud del equipo. Desde la 1.8.0 con la
    cara de TechClean (informe.generar_html) y en PDF (lo imprime main con
    informe.a_pdf); si no hay Edge, este HTML se imprime desde el navegador.

    `datos`: {"equipo", "tecnico", "cliente", "antes", "despues", "filas",
    "acciones", "discos", "baterias", "fallos", "notas"}; todo opcional.
    `t` se pasa como parámetro para poder probarlo sin la app.
    """
    import informe

    equipo = datos.get("equipo") or {}
    filas_equipo = [(t(etiqueta), equipo[clave]) for clave, etiqueta in (
        ("hostname", "inf_eq_nombre"), ("sistema_operativo", "inf_eq_so"), ("procesador", "inf_eq_cpu"),
        ("ram", "inf_eq_ram"), ("placa_madre", "inf_eq_placa")) if equipo.get(clave)]

    problemas = []
    for d in datos.get("discos") or []:
        nombre = t("inf_disco", nombre=d.get("nombre") or "?")
        filas_equipo.append((nombre, t(NIVELES_SALUD.get(d.get("veredicto"), "salud_nivel_bien"))))
        if d.get("veredicto") in ("atencion", "critico"):
            problemas.append({"nivel": d["veredicto"], "titulo": nombre,
                              "detalle": ", ".join(t(m) for m in d.get("motivos") or [])})
    for b in datos.get("baterias") or []:
        resumen = t("bat_resumen", porcentaje=b.get("porcentaje"), ciclos=b.get("ciclos") or "?")
        filas_equipo.append((t("inf_bateria"), resumen))
        if b.get("veredicto") in ("atencion", "critico"):
            problemas.append({"nivel": b["veredicto"], "titulo": t("inf_bateria"), "detalle": resumen})
    fallos = datos.get("fallos")
    if fallos:
        n = len(fallos.get("pantallazos") or [])
        valor = t("inf_estabilidad_valor", pantallazos=n, apagados=fallos.get("apagados", 0),
                  dias=fallos.get("dias", 90))
        filas_equipo.append((t("inf_estabilidad"), valor))
        if n or fallos.get("apagados"):
            problemas.append({"nivel": "atencion", "titulo": t("inf_estabilidad"), "detalle": valor})

    filas = datos.get("filas") or []
    antes = datos.get("antes") or {}
    despues = datos.get("despues") or {}
    antes_despues = None
    if filas:
        antes_despues = {
            "momentos": t("inf_momentos", antes=antes.get("momento", ""), despues=despues.get("momento", "")),
            "filas": [(t(f["clave"]), _formatear_valor(f["antes"], f["unidad"]),
                       _formatear_valor(f["despues"], f["unidad"]),
                       ("+" if f["diferencia"] > 0 else "") + _formatear_valor(f["diferencia"], f["unidad"]),
                       f["sentido"]) for f in filas]}
    acciones = [{"fecha": (a.get("timestamp") or "")[:16], "accion": a.get("accion", ""),
                 "resultado": a.get("resultado", ""), "exito": a.get("exito")} for a in datos.get("acciones") or []]
    return informe.generar_html({
        "titulo": t("inf_titulo"), "version": datos.get("version") or "",
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "equipo_nombre": equipo.get("hostname") or "",
        "tecnico": datos.get("tecnico"), "cliente": datos.get("cliente"), "logo": datos.get("logo"),
        "problemas": problemas if (datos.get("discos") or datos.get("baterias") or fallos) else None,
        "equipo": filas_equipo, "antes_despues": antes_despues,
        "acciones": acciones if datos.get("acciones") is not None else None, "notas": datos.get("notas"),
    }, t)

