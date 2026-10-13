"""
gpu.py
La tarjeta gráfica en vivo, de CUALQUIER marca, con lo mismo que usa el
Administrador de tareas de Windows (1.8.0).

Hasta la 1.7.0 el uso, la VRAM y la temperatura solo salían con NVIDIA
(nvidia-smi); en AMD e Intel la app decía "no disponible". Windows los da
para todas desde Windows 10 (WDDM 2.4+), por dos caminos:

- **Contadores de rendimiento** (PDH): "GPU Engine" es el uso de cada motor
  de la gráfica (3D, vídeo, copia...) por proceso; "GPU Adapter Memory", la
  memoria usada. El % de una gráfica es, como en el Administrador de tareas,
  el del motor más ocupado (sumando todos los procesos).
- **El núcleo gráfico** (D3DKMT, gdi32.dll): nombre de cada adaptador, su
  memoria dedicada y compartida, y temperatura, ventilador y consumo cuando
  el driver los publica.

No necesita administrador, ni instala nada, ni toca la gráfica: solo lee.
Probado en una AMD Radeon integrada (680M): 47 °C, 5 % de uso 3D, 430 MB.

Se llama desde un hilo (las consultas tardan unos milisegundos).
"""

import ctypes
import re
import sys
import threading
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

# ---------------- Núcleo gráfico (D3DKMT) ----------------
# Valores de KMTQUERYADAPTERINFOTYPE (d3dkmthk.h).
_KMTQAITYPE_ADAPTERREGISTRYINFO = 8
_KMTQAITYPE_GETSEGMENTSIZE = 3
_KMTQAITYPE_ADAPTERPERFDATA = 62
_MAX_PATH = 260


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _ADAPTERINFO(ctypes.Structure):
    _fields_ = [("hAdapter", wintypes.UINT), ("AdapterLuid", _LUID), ("NumOfSources", wintypes.ULONG),
                ("bPrecisePresentRegionsPreferred", wintypes.BOOL)]


class _ENUMADAPTERS2(ctypes.Structure):
    _fields_ = [("NumAdapters", wintypes.ULONG), ("pAdapters", ctypes.POINTER(_ADAPTERINFO))]


class _QUERYADAPTERINFO(ctypes.Structure):
    _fields_ = [("hAdapter", wintypes.UINT), ("Type", ctypes.c_int), ("pPrivateDriverData", ctypes.c_void_p),
                ("PrivateDriverDataSize", wintypes.UINT)]


class _CLOSEADAPTER(ctypes.Structure):
    _fields_ = [("hAdapter", wintypes.UINT)]


class _REGISTRYINFO(ctypes.Structure):
    _fields_ = [("AdapterString", ctypes.c_wchar * _MAX_PATH), ("BiosString", ctypes.c_wchar * _MAX_PATH),
                ("DacType", ctypes.c_wchar * _MAX_PATH), ("ChipType", ctypes.c_wchar * _MAX_PATH)]


class _SEGMENTSIZE(ctypes.Structure):
    _fields_ = [("DedicatedVideoMemorySize", ctypes.c_uint64), ("DedicatedSystemMemorySize", ctypes.c_uint64),
                ("SharedSystemMemorySize", ctypes.c_uint64)]


class _PERFDATA(ctypes.Structure):
    _fields_ = [("PhysicalAdapterIndex", ctypes.c_uint32), ("MemoryFrequency", ctypes.c_uint64),
                ("MaxMemoryFrequency", ctypes.c_uint64), ("MaxMemoryFrequencyOC", ctypes.c_uint64),
                ("MemoryBandwidth", ctypes.c_uint64), ("PCIEBandwidth", ctypes.c_uint64),
                ("FanRPM", ctypes.c_ulong), ("Power", ctypes.c_ulong), ("Temperature", ctypes.c_ulong),
                ("PowerStateOverride", ctypes.c_ubyte)]


def _clave_luid(luid_alto, luid_bajo):
    """Como lo escriben los contadores: "luid_0x00000000_0x0000D1E5"."""
    return f"luid_0x{luid_alto & 0xFFFFFFFF:08x}_0x{luid_bajo & 0xFFFFFFFF:08x}"


def _consultar(gdi, adaptador, tipo, estructura):
    q = _QUERYADAPTERINFO(adaptador, tipo, ctypes.cast(ctypes.byref(estructura), ctypes.c_void_p),
                          ctypes.sizeof(estructura))
    return gdi.D3DKMTQueryAdapterInfo(ctypes.byref(q)) == 0


def leer_adaptadores():
    """Las gráficas de verdad del equipo (sin el adaptador de software de
    Microsoft), con su memoria y, si el driver los da, temperatura,
    ventilador y consumo. Lista de diccionarios; vacía si no se pudo."""
    if not IS_WINDOWS:
        return []
    try:
        gdi = ctypes.WinDLL("gdi32")
    except OSError:
        return []
    enum = _ENUMADAPTERS2()
    if gdi.D3DKMTEnumAdapters2(ctypes.byref(enum)) != 0 or enum.NumAdapters == 0:
        return []
    lista = (_ADAPTERINFO * enum.NumAdapters)()
    enum.pAdapters = lista
    if gdi.D3DKMTEnumAdapters2(ctypes.byref(enum)) != 0:
        return []
    adaptadores = []
    vistos = set()
    for i in range(enum.NumAdapters):
        info = lista[i]
        try:
            clave = _clave_luid(info.AdapterLuid.HighPart, info.AdapterLuid.LowPart)
            registro = _REGISTRYINFO()
            nombre = registro.AdapterString.strip() if _consultar(
                gdi, info.hAdapter, _KMTQAITYPE_ADAPTERREGISTRYINFO, registro) else ""
            segmentos = _SEGMENTSIZE()
            tiene_segmentos = _consultar(gdi, info.hAdapter, _KMTQAITYPE_GETSEGMENTSIZE, segmentos)
            # El "Microsoft Basic Render Driver" es la gráfica de software
            # (sin memoria propia): no es una tarjeta.
            if (not nombre or clave in vistos or not tiene_segmentos
                    or (segmentos.DedicatedVideoMemorySize == 0 and segmentos.SharedSystemMemorySize == 0)
                    or "basic render" in nombre.lower()):
                continue
            vistos.add(clave)
            perf = _PERFDATA()
            perf.PhysicalAdapterIndex = 0
            con_perf = _consultar(gdi, info.hAdapter, _KMTQAITYPE_ADAPTERPERFDATA, perf)
            adaptadores.append({
                "luid": clave,
                "nombre": nombre,
                "vram_dedicada_bytes": int(segmentos.DedicatedVideoMemorySize),
                "memoria_compartida_bytes": int(segmentos.SharedSystemMemorySize),
                # La temperatura viene en décimas de grado; 0 = el driver no
                # la da (ninguna gráfica funcionando está a 0 °C).
                "temperatura_c": round(perf.Temperature / 10, 1) if con_perf and perf.Temperature else None,
                "ventilador_rpm": int(perf.FanRPM) if con_perf and perf.FanRPM else None,
            })
        finally:
            gdi.D3DKMTCloseAdapter(ctypes.byref(_CLOSEADAPTER(info.hAdapter)))
    return adaptadores


# ---------------- Contadores de rendimiento (PDH) ----------------
_PDH_FMT_DOUBLE = 0x00000200
_PDH_FMT_NOCAP100 = 0x00008000
_PDH_MORE_DATA = 0x800007D2


class _ITEM(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _Contadores:
    """Una consulta PDH abierta durante toda la sesión. El uso de un motor
    es un contador de "velocidad": necesita DOS lecturas, y lo que da es la
    media entre una y otra. Por eso la consulta no se cierra: cada llamada
    mide desde la anterior, y la primera devuelve None."""

    def __init__(self):
        self._pdh = ctypes.WinDLL("pdh")
        self._consulta = ctypes.c_void_p()
        self._motores = ctypes.c_void_p()
        self._memoria = ctypes.c_void_p()
        self._listo = False
        if self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._consulta)) != 0:
            raise OSError("PdhOpenQuery")
        anadir = self._pdh.PdhAddEnglishCounterW
        if (anadir(self._consulta, r"\GPU Engine(*)\Utilization Percentage", 0, ctypes.byref(self._motores)) != 0
                or anadir(self._consulta, r"\GPU Adapter Memory(*)\Dedicated Usage", 0,
                          ctypes.byref(self._memoria)) != 0):
            raise OSError("este Windows no tiene los contadores de la gráfica")
        self._pdh.PdhCollectQueryData(self._consulta)

    def _valores(self, contador):
        tamano = wintypes.DWORD(0)
        cuantos = wintypes.DWORD(0)
        r = self._pdh.PdhGetFormattedCounterArrayW(contador, _PDH_FMT_DOUBLE | _PDH_FMT_NOCAP100,
                                                   ctypes.byref(tamano), ctypes.byref(cuantos), None)
        if (r & 0xFFFFFFFF) != _PDH_MORE_DATA or not tamano.value:
            return []
        buffer = ctypes.create_string_buffer(tamano.value)
        r = self._pdh.PdhGetFormattedCounterArrayW(contador, _PDH_FMT_DOUBLE | _PDH_FMT_NOCAP100,
                                                   ctypes.byref(tamano), ctypes.byref(cuantos), buffer)
        if r != 0:
            return []
        items = ctypes.cast(buffer, ctypes.POINTER(_ITEM))
        return [(items[i].szName or "", items[i].doubleValue) for i in range(cuantos.value)
                if items[i].CStatus in (0, 1)]

    def leer(self):
        """{luid: {"uso": %, "vram_usada": bytes}}. El uso es None en la
        primera lectura."""
        self._pdh.PdhCollectQueryData(self._consulta)
        por_luid = {}
        # Instancias: "pid_1234_luid_0x..._0x..._phys_0_eng_3_engtype_3D".
        # Se suma por motor (todos los procesos) y el % de la gráfica es el
        # del motor más ocupado, como en el Administrador de tareas.
        motores = {}
        for nombre, valor in self._valores(self._motores):
            m = re.search(r"(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)_eng_(\d+)", nombre, re.I)
            if m:
                clave = (m.group(1).lower(), m.group(2), m.group(3))
                motores[clave] = motores.get(clave, 0.0) + valor
        for (luid, _, _), suma in motores.items():
            dato = por_luid.setdefault(luid, {"uso": 0.0, "vram_usada": None})
            dato["uso"] = max(dato["uso"], min(100.0, suma))
        for nombre, valor in self._valores(self._memoria):
            m = re.search(r"(luid_0x[0-9a-f]+_0x[0-9a-f]+)", nombre, re.I)
            if m:
                dato = por_luid.setdefault(m.group(1).lower(), {"uso": None, "vram_usada": None})
                dato["vram_usada"] = (dato["vram_usada"] or 0) + valor
        if not self._listo:
            self._listo = True
            for dato in por_luid.values():
                dato["uso"] = None
        return por_luid


_contadores = None
_cerrojo = threading.Lock()
_adaptadores_cache = None


def leer_en_vivo():
    """La gráfica principal en vivo, o None si este Windows no da nada.

    {"nombre", "uso_pct", "vram_usada_gb", "vram_total_gb", "compartida_gb",
     "temperatura_c", "ventilador_rpm", "otras": [nombres]}

    "Principal" = la que más memoria dedicada tiene (en un portátil con dos,
    la dedicada; en uno con integrada sola, esa). uso_pct es None la primera
    vez (el contador necesita dos lecturas)."""
    global _contadores, _adaptadores_cache
    if not IS_WINDOWS:
        return None
    with _cerrojo:
        try:
            adaptadores = leer_adaptadores()
        except Exception:
            adaptadores = []
        if not adaptadores:
            return None
        _adaptadores_cache = adaptadores
        try:
            if _contadores is None:
                _contadores = _Contadores()
            vivos = _contadores.leer()
        except Exception:
            vivos = {}
    principal = max(adaptadores, key=lambda a: a["vram_dedicada_bytes"])
    vivo = vivos.get(principal["luid"], {})
    gb = 1024 ** 3
    usada = vivo.get("vram_usada")
    return {
        "nombre": principal["nombre"],
        "uso_pct": round(vivo["uso"], 1) if vivo.get("uso") is not None else None,
        "vram_usada_gb": round(usada / gb, 2) if usada is not None else None,
        "vram_total_gb": round(principal["vram_dedicada_bytes"] / gb, 2),
        "compartida_gb": round(principal["memoria_compartida_bytes"] / gb, 1),
        "temperatura_c": principal["temperatura_c"],
        "ventilador_rpm": principal["ventilador_rpm"],
        "otras": [a["nombre"] for a in adaptadores if a is not principal],
    }
