"""
system_monitor.py
Recolecta información real de hardware y del sistema operativo.

Compatible con Windows 10 y Windows 11 (incluidas las versiones que ya no
traen wmic.exe, como 24H2/25H2 en adelante: Microsoft lo declaró obsoleto
en 2021 y lo está retirando de Windows por completo). Todo lo que antes
usaba `wmic` ahora usa PowerShell + CIM (Get-CimInstance), el reemplazo
oficial recomendado por Microsoft, que funciona igual en ambas versiones.

En sistemas que no son Windows, cada función degrada elegantemente
mostrando "No disponible" en vez de fallar.
"""

import json
import platform
import socket
import getpass
import subprocess
import time
import psutil

IS_WINDOWS = platform.system() == "Windows"


def _run(cmd, timeout=5):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
        )
        return result.stdout.strip()
    except Exception:
        return None


def _cim(clase, propiedades, namespace="root/cimv2", timeout=8):
    """
    Consulta WMI a través de PowerShell (Get-CimInstance) — el reemplazo
    oficial de wmic. Funciona igual en Windows 10 y 11, incluidas las
    versiones que ya no incluyen wmic.exe por defecto.
    Devuelve una lista de diccionarios (uno por objeto encontrado), o
    lista vacía si algo falla — nunca lanza una excepción hacia afuera.

    timeout: algunas clases WMI (como Win32_PnPSignedDriver, que puede
    enumerar cientos de dispositivos) son bastante más pesadas que el
    resto — en equipos justos de recursos, el timeout por defecto de 8s
    no siempre alcanza, y antes eso devolvía una lista vacía en silencio
    en vez de avisar que se agotó el tiempo. Las consultas pesadas piden
    un timeout más largo explícitamente.
    """
    if not IS_WINDOWS:
        return []
    props = ",".join(propiedades)
    ps_cmd = (
        f"Get-CimInstance -Namespace {namespace} -ClassName {clase} "
        f"-ErrorAction SilentlyContinue | Select-Object {props} | ConvertTo-Json -Compress"
    )
    salida = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], timeout=timeout)
    if not salida:
        return []
    try:
        datos = json.loads(salida)
    except Exception:
        return []
    if isinstance(datos, dict):
        datos = [datos]
    return datos if isinstance(datos, list) else []


# ---------------- Sistema operativo ----------------

def get_windows_display_name():
    """
    Nombre amigable y correcto del sistema operativo.
    Corrige un problema real y conocido: el registro de Windows sigue
    reportando 'Windows 10' en ProductName incluso en equipos que ya
    corren Windows 11 (Microsoft no actualizó ese valor). Aquí se corrige
    comparando contra el número de build real (Windows 11 empieza en 22000).
    """
    if not IS_WINDOWS:
        return f"{platform.system()} {platform.release()}"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            product_name, _ = winreg.QueryValueEx(key, "ProductName")
            try:
                build_str, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
                build_num = int(build_str)
            except Exception:
                build_num = 0
            try:
                display_version, _ = winreg.QueryValueEx(key, "DisplayVersion")
            except Exception:
                display_version = ""

        if build_num >= 22000 and "Windows 10" in product_name:
            product_name = product_name.replace("Windows 10", "Windows 11")
        if display_version:
            product_name = f"{product_name} ({display_version}, build {build_num})"
        return product_name
    except Exception:
        return f"{platform.system()} {platform.release()}"


def get_system_info():
    """Datos generales del equipo, SO, placa madre y BIOS. Es costosa
    (usa PowerShell/CIM en Windows) — llámala una sola vez y cachea el
    resultado, no en cada refresco del dashboard."""
    info = {
        "hostname": socket.gethostname(),
        "usuario": getpass.getuser(),
        "sistema_operativo": get_windows_display_name() if IS_WINDOWS else platform.system(),
        "version_so": platform.version(),
        "release_so": platform.release(),
        "arquitectura": platform.machine(),
        "procesador": platform.processor() or "No disponible",
        "placa_madre": "No disponible",
        "bios": "No disponible",
    }

    if IS_WINDOWS:
        cpu_rows = _cim("Win32_Processor", ["Name"])
        if cpu_rows and cpu_rows[0].get("Name"):
            info["procesador"] = cpu_rows[0]["Name"].strip()

        board_rows = _cim("Win32_BaseBoard", ["Manufacturer", "Product"])
        if board_rows:
            fab = (board_rows[0].get("Manufacturer") or "").strip()
            modelo = (board_rows[0].get("Product") or "").strip()
            texto = f"{fab} {modelo}".strip()
            if texto:
                info["placa_madre"] = texto

        bios_rows = _cim("Win32_BIOS", ["SMBIOSBIOSVersion", "Manufacturer"])
        if bios_rows:
            fab = (bios_rows[0].get("Manufacturer") or "").strip()
            ver = (bios_rows[0].get("SMBIOSBIOSVersion") or "").strip()
            texto = f"{fab} {ver}".strip()
            if texto:
                info["bios"] = texto

    return info


# ---------------- RAM ----------------

def get_ram_info():
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024 ** 3), 2),
        "usado_gb": round(vm.used / (1024 ** 3), 2),
        "disponible_gb": round(vm.available / (1024 ** 3), 2),
        "porcentaje": vm.percent,
    }


def get_ram_sticks():
    """Detalle físico de cada módulo de RAM instalado (capacidad, velocidad,
    fabricante, ranura). Relativamente lenta — cachear el resultado."""
    if not IS_WINDOWS:
        return []
    filas = _cim("Win32_PhysicalMemory", ["Capacity", "Speed", "Manufacturer", "DeviceLocator"])
    modulos = []
    for f in filas:
        try:
            capacidad_gb = round(int(f.get("Capacity") or 0) / (1024 ** 3), 1)
        except Exception:
            capacidad_gb = None
        modulos.append({
            "ranura": f.get("DeviceLocator") or "N/D",
            "capacidad_gb": capacidad_gb,
            "velocidad_mhz": f.get("Speed"),
            "fabricante": (f.get("Manufacturer") or "N/D").strip() or "N/D",
        })
    return modulos


def estimar_canal_ram(modulos):
    """
    IMPORTANTE — esto es un ESTIMADO, no una confirmación certera: WMI no
    expone de forma confiable si la RAM está corriendo en canal dual o
    simple (confirmado al investigarlo — ni siquiera herramientas como
    CPU-Z lo logran siempre sin acceso más profundo al hardware; la BIOS
    es la única fuente 100% segura). Esto solo mira cuántos módulos hay y
    si coinciden en capacidad, que es el patrón típico de canal dual,
    pero no revisa en qué ranura física quedó cada uno — eso también
    importa y esto no lo puede ver.
    """
    if not modulos:
        return None
    if len(modulos) == 1:
        return {
            "modo": "Canal simple",
            "explicacion": "Solo hay un módulo instalado — con uno solo, el canal dual no es posible sin "
                            "importar la placa madre. Agregar un segundo módulo idéntico puede mejorar el "
                            "rendimiento notablemente, sobre todo con gráficos integrados.",
        }
    capacidades = [m["capacidad_gb"] for m in modulos if m["capacidad_gb"] is not None]
    if len(modulos) % 2 == 0 and len(set(capacidades)) == 1:
        return {
            "modo": "Probablemente canal dual",
            "explicacion": f"{len(modulos)} módulos instalados, todos de {capacidades[0]} GB — es el patrón "
                            "típico de canal dual. No se puede confirmar con 100% de certeza desde software "
                            "(la ranura exacta de cada módulo también importa), pero es una buena señal.",
        }
    return {
        "modo": "Probablemente canal simple o asimétrico",
        "explicacion": f"{len(modulos)} módulos de capacidades distintas ({', '.join(str(c) + ' GB' for c in capacidades)}) "
                        "— es probable que no se esté aprovechando el canal dual completo. Revisa el manual de "
                        "tu equipo para la combinación correcta de ranuras si quieres confirmarlo o mejorarlo.",
    }


# ---------------- CPU ----------------

def get_cpu_info():
    freq = psutil.cpu_freq()
    return {
        "porcentaje": psutil.cpu_percent(interval=0.3),
        "nucleos_fisicos": psutil.cpu_count(logical=False),
        "nucleos_logicos": psutil.cpu_count(logical=True),
        "frecuencia_mhz": round(freq.current, 0) if freq else None,
    }


def get_cpu_details(incluir_temperatura=True):
    """Versión ampliada: uso por núcleo, frecuencia actual/máxima y
    temperatura (si el equipo la expone). Un poco más costosa que
    get_cpu_info(); pensada para la pantalla de Componentes, no para
    refrescos cada 1-2 segundos.

    incluir_temperatura=False: se salta la consulta de temperatura (la
    parte lenta, depende de WMI, puede tardar segundos en equipos donde
    WMI está degradado) — para refrescos frecuentes donde se prefiere
    tener el resto de los datos (uso, frecuencia) rápido y de forma
    independiente, cacheando la temperatura aparte con su propio ritmo."""
    por_nucleo = psutil.cpu_percent(interval=0.3, percpu=True)
    freq = psutil.cpu_freq()
    return {
        "porcentaje_total": round(sum(por_nucleo) / len(por_nucleo), 1) if por_nucleo else None,
        "porcentaje_por_nucleo": [round(v, 0) for v in por_nucleo],
        "nucleos_fisicos": psutil.cpu_count(logical=False),
        "nucleos_logicos": psutil.cpu_count(logical=True),
        "frecuencia_actual_mhz": round(freq.current, 0) if freq else None,
        "frecuencia_max_mhz": round(freq.max, 0) if freq and freq.max else None,
        "temperatura_c": get_cpu_temperature() if incluir_temperatura else None,
    }


def get_cpu_temperature():
    """
    Temperatura del procesador, cuando el equipo la expone.
    Aviso honesto: Windows no tiene una API pública y universal para esto.
    Cada fabricante la expone distinto (o no la expone en absoluto sin un
    driver adicional de terceros). Se intenta vía el sensor ACPI estándar
    (root/wmi, MSAcpi_ThermalZoneTemperature), que funciona en varias
    laptops pero no en todos los equipos ni en la mayoría de PCs de
    escritorio. Si no está disponible, se devuelve None (la interfaz
    muestra "No disponible en este equipo" en vez de inventar un dato).
    """
    if not IS_WINDOWS:
        if hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                for entradas in temps.values():
                    if entradas:
                        return round(entradas[0].current, 1)
            except Exception:
                pass
        return None

    filas = _cim("MSAcpi_ThermalZoneTemperature", ["CurrentTemperature"], namespace="root/wmi")
    if filas:
        try:
            decikelvin = float(filas[0]["CurrentTemperature"])
            celsius = (decikelvin / 10) - 273.15
            if -20 < celsius < 130:
                return round(celsius, 1)
        except Exception:
            pass
    return None


# ---------------- Disco ----------------

def get_disk_info(path="C:\\" if IS_WINDOWS else "/"):
    try:
        du = psutil.disk_usage(path)
        return {
            "unidad": path,
            "total_gb": round(du.total / (1024 ** 3), 2),
            "usado_gb": round(du.used / (1024 ** 3), 2),
            "libre_gb": round(du.free / (1024 ** 3), 2),
            "porcentaje": du.percent,
        }
    except Exception:
        return {"unidad": path, "total_gb": 0, "usado_gb": 0, "libre_gb": 0, "porcentaje": 0}


def get_disk_partitions():
    """Uso de espacio en TODAS las unidades/particiones del equipo, no
    solo C:\\."""
    particiones = []
    try:
        lista = psutil.disk_partitions(all=False)
    except Exception:
        lista = []
    for p in lista:
        try:
            du = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        particiones.append({
            "unidad": p.device,
            "punto_montaje": p.mountpoint,
            "sistema_archivos": p.fstype,
            "total_gb": round(du.total / (1024 ** 3), 2),
            "usado_gb": round(du.used / (1024 ** 3), 2),
            "libre_gb": round(du.free / (1024 ** 3), 2),
            "porcentaje": du.percent,
        })
    return particiones


_disk_io_estado = {"valores": None, "tiempo": None}


def get_disk_io_speed():
    """Velocidad real de lectura/escritura de disco en MB/s, calculada
    como delta entre dos llamadas consecutivas. Llama a esta función
    periódicamente (p. ej. cada 2s) desde el mismo temporizador para que
    el delta tenga sentido; la primera llamada siempre devuelve 0."""
    ahora = time.time()
    try:
        actual = psutil.disk_io_counters()
    except Exception:
        actual = None
    anterior = _disk_io_estado["valores"]
    t_anterior = _disk_io_estado["tiempo"]
    _disk_io_estado["valores"] = actual
    _disk_io_estado["tiempo"] = ahora

    if not actual or not anterior or not t_anterior:
        return {"lectura_mbps": 0.0, "escritura_mbps": 0.0}

    delta_t = max(ahora - t_anterior, 0.001)
    lectura = (actual.read_bytes - anterior.read_bytes) / (1024 ** 2) / delta_t
    escritura = (actual.write_bytes - anterior.write_bytes) / (1024 ** 2) / delta_t
    return {"lectura_mbps": round(max(lectura, 0), 2), "escritura_mbps": round(max(escritura, 0), 2)}


# ---------------- Red ----------------

_net_io_estado = {"valores": None, "tiempo": None}


def get_network_speed():
    """Velocidad real de subida/bajada en MB/s (delta entre llamadas)."""
    ahora = time.time()
    try:
        actual = psutil.net_io_counters()
    except Exception:
        actual = None
    anterior = _net_io_estado["valores"]
    t_anterior = _net_io_estado["tiempo"]
    _net_io_estado["valores"] = actual
    _net_io_estado["tiempo"] = ahora

    if not actual or not anterior or not t_anterior:
        return {"bajada_mbps": 0.0, "subida_mbps": 0.0}

    delta_t = max(ahora - t_anterior, 0.001)
    bajada = (actual.bytes_recv - anterior.bytes_recv) / (1024 ** 2) / delta_t
    subida = (actual.bytes_sent - anterior.bytes_sent) / (1024 ** 2) / delta_t
    return {"bajada_mbps": round(max(bajada, 0), 2), "subida_mbps": round(max(subida, 0), 2)}


# ---------------- GPU ----------------

def get_gpu_info():
    """
    Consulta completa de GPU: nombre, uso, memoria, temperatura y
    velocidad del ventilador. Las métricas en vivo (uso/temp/mem/fan)
    solo están disponibles para GPUs NVIDIA vía nvidia-smi. En GPUs
    AMD/Intel se muestra el nombre (vía CIM) pero sin métricas en vivo:
    no existe un equivalente universal sin drivers adicionales de terceros.
    No la llames en un bucle rápido; para refrescos frecuentes usa
    get_gpu_utilization().
    """
    salida = _run(["nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed",
                    "--format=csv,noheader,nounits"])
    if salida:
        try:
            partes = [p.strip() for p in salida.split(",")]
            nombre, util, mem_usada, mem_total, temp, fan = partes
            return {
                "nombre": nombre,
                "porcentaje": float(util),
                "vram_usada_gb": round(float(mem_usada) / 1024, 2),
                "vram_total_gb": round(float(mem_total) / 1024, 2),
                "temperatura_c": float(temp) if temp not in ("[Not Supported]", "N/A") else None,
                "ventilador_pct": float(fan) if fan not in ("[Not Supported]", "N/A") else None,
                "fuente": "nvidia-smi",
            }
        except Exception:
            pass

    if IS_WINDOWS:
        filas = _cim("Win32_VideoController", ["Name"])
        if filas and filas[0].get("Name"):
            return {
                "nombre": filas[0]["Name"].strip(),
                "porcentaje": None, "vram_usada_gb": None, "vram_total_gb": None,
                "temperatura_c": None, "ventilador_pct": None, "fuente": "cim",
            }

    return {"nombre": "No detectada", "porcentaje": None, "vram_usada_gb": None,
            "vram_total_gb": None, "temperatura_c": None, "ventilador_pct": None, "fuente": None}


def get_gpu_utilization():
    """Versión ligera y rápida: solo el % de uso (NVIDIA únicamente).
    Segura para llamar cada 1-4 segundos sin impactar el rendimiento."""
    salida = _run(["nvidia-smi", "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits"])
    if salida:
        try:
            return float(salida.strip())
        except Exception:
            return None
    return None


# ---------------- Batería, tiempo encendido, procesos ----------------

def get_battery_info():
    """None en equipos de escritorio sin batería (no es un error)."""
    if not hasattr(psutil, "sensors_battery"):
        return None
    try:
        bateria = psutil.sensors_battery()
    except Exception:
        return None
    if bateria is None:
        return None
    minutos = None
    if bateria.secsleft and bateria.secsleft > 0:
        minutos = round(bateria.secsleft / 60)
    return {
        "porcentaje": round(bateria.percent, 0),
        "cargando": bool(bateria.power_plugged),
        "minutos_restantes": minutos,
    }


def get_uptime_seconds():
    try:
        return max(0, time.time() - psutil.boot_time())
    except Exception:
        return 0


def get_process_count():
    try:
        return len(psutil.pids())
    except Exception:
        return 0


def get_top_processes(limit=8):
    procesos = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mem_mb = p.info["memory_info"].rss / (1024 ** 2)
            procesos.append({"pid": p.info["pid"], "nombre": p.info["name"], "ram_mb": round(mem_mb, 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procesos.sort(key=lambda x: x["ram_mb"], reverse=True)
    return procesos[:limit]


# ---------------- Drivers ----------------

def listar_drivers():
    """
    Lista los drivers firmados instalados (Win32_PnPSignedDriver): nombre
    del dispositivo, fabricante, versión y fecha. Es informativo — para
    saber qué tan viejo está cada uno; la actualización real se hace vía
    Windows Update (ver optimizer.buscar_actualizaciones_drivers) o desde
    la página oficial del fabricante, nunca reemplazando archivos a mano.
    """
    if not IS_WINDOWS:
        return []
    filas = _cim("Win32_PnPSignedDriver",
                 ["DeviceName", "Manufacturer", "DriverVersion", "DriverDate", "DeviceClass"],
                 timeout=30)
    drivers = []
    for f in filas:
        nombre = (f.get("DeviceName") or "").strip()
        if not nombre:
            continue
        fecha = f.get("DriverDate")
        fecha_legible = None
        if fecha and isinstance(fecha, str) and len(fecha) >= 8:
            # CIM devuelve fechas como '20190614000000.000000+000' o WMI datetime;
            # Get-CimInstance normalmente ya lo convierte a ISO ('2019-06-14T00:00:00').
            fecha_legible = fecha[:10]
        drivers.append({
            "nombre": nombre,
            "fabricante": (f.get("Manufacturer") or "N/D").strip(),
            "version": f.get("DriverVersion") or "N/D",
            "fecha": fecha_legible or "N/D",
            "clase": f.get("DeviceClass") or "N/D",
        })
    drivers.sort(key=lambda d: d["fecha"] or "", reverse=False)
    return drivers


# ---------------- Modo Ligero: detección de equipo modesto ----------------

def es_equipo_modesto():
    """
    Heurística simple para saber si el equipo es de gama baja: 2 núcleos
    físicos o menos, o 4 GB de RAM total o menos. Se usa SOLO para sugerir
    el Modo Ligero la primera vez que se abre la app — nunca para limitar
    funciones, solo la frecuencia de actualización de la propia app (que
    un optimizador consuma recursos de más en un equipo débil sería
    justo lo contrario de para qué sirve).
    """
    try:
        nucleos = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 4
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        return nucleos <= 2 or ram_gb <= 4
    except Exception:
        return False


def get_memoria_virtual():
    """Info del archivo de paginación (memoria virtual) — más relevante
    cuanto menos RAM física tenga el equipo, ya que Windows depende más
    de esto para no quedarse sin memoria utilizable."""
    try:
        swap = psutil.swap_memory()
        return {
            "total_gb": round(swap.total / (1024 ** 3), 2),
            "usado_gb": round(swap.used / (1024 ** 3), 2),
            "porcentaje": swap.percent,
        }
    except Exception:
        return None


CODIGOS_ERROR_DISPOSITIVO = {
    1: "Windows no reconoce este dispositivo correctamente.",
    3: "El driver instalado podría estar dañado.",
    10: "El dispositivo no puede iniciar.",
    18: "Windows sugiere reinstalar los drivers de este dispositivo.",
    22: "El dispositivo está deshabilitado.",
    24: "El dispositivo no está presente, no funciona, o le faltan los drivers.",
    28: "No tiene los drivers instalados — este es el caso más común después de una instalación limpia.",
    29: "El dispositivo está deshabilitado por firmware (BIOS/UEFI).",
    31: "Windows no puede hacerlo funcionar bien — driver faltante o incompatible.",
    32: "El driver de este dispositivo está deshabilitado.",
    37: "El driver devolvió un error al iniciar.",
    39: "El driver está dañado o falta.",
    43: "Windows detuvo el dispositivo porque reportó un problema.",
}


def listar_dispositivos_con_problemas():
    """
    Dispositivos que Windows detecta pero para los que no tiene un driver
    funcionando — el símbolo de exclamación amarillo del Administrador de
    dispositivos, o "Unknown device". Justo lo que hace falta saber
    después de una instalación limpia de Windows: no qué YA está
    instalado (eso es listar_drivers), sino qué le falta reconocer
    todavía. Usa el código de error de ConfigManager: 0 significa "sin
    problemas", cualquier otro valor indica algo que revisar.
    """
    if not IS_WINDOWS:
        return []
    filas = _cim("Win32_PnPEntity", ["Name", "DeviceID", "ConfigManagerErrorCode"], timeout=30)
    problemas = []
    for f in filas:
        codigo = f.get("ConfigManagerErrorCode")
        if not codigo:  # None o 0 = sin problema
            continue
        problemas.append({
            "nombre": f.get("Name") or "Dispositivo desconocido",
            "device_id": f.get("DeviceID") or "",
            "codigo_error": codigo,
            "explicacion": CODIGOS_ERROR_DISPOSITIVO.get(
                codigo, f"Windows reporta un problema con este dispositivo (código {codigo})."),
        })
    return problemas


def listar_historial_arranques(limite=15):
    """
    Cuánto tardó cada arranque reciente, según lo que Windows mismo
    registra en su propio Visor de Eventos (Diagnósticos de Rendimiento,
    evento 100) — no es algo que esta app mida por su cuenta, es leer un
    registro que el sistema ya lleva automáticamente desde hace tiempo.

    Advertencia real, no un bug de esta app: en algunos equipos o
    configuraciones de Windows (documentado en foros de Microsoft) este
    evento simplemente no se registra — en ese caso la lista vuelve
    vacía, eso no significa que el equipo tenga un problema.
    """
    if not IS_WINDOWS:
        return []
    script = (
        "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; "
        "Id=100} -MaxEvents " + str(limite) + " -ErrorAction SilentlyContinue | ForEach-Object { "
        "$xml = [xml]$_.ToXml(); "
        "[PSCustomObject]@{ "
        "Fecha = $_.TimeCreated.ToString('o'); "
        "BootTimeMs = ($xml.Event.EventData.Data | Where-Object {$_.Name -eq 'BootTime'}).'#text' "
        "} } | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        if not r.stdout:
            return []
        datos = json.loads(r.stdout)
        if isinstance(datos, dict):
            datos = [datos]
    except Exception:
        return []

    resultado = []
    for d in datos:
        try:
            ms = int(d.get("BootTimeMs") or 0)
            if ms <= 0:
                continue
        except Exception:
            continue
        resultado.append({"fecha": d.get("Fecha"), "segundos": round(ms / 1000, 1)})
    return resultado
