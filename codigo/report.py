"""
report.py
Registro estructurado y 100% transparente de cada acción ejecutada. El
objetivo es que el usuario pueda verificar exactamente qué se ejecutó, con
qué comando y con qué resultado — sin ambigüedades.

Guarda dos cosas a la vez:

  * La SESIÓN actual, en memoria. Es lo que alimenta los totales de la
    pantalla de Historial ("liberaste X en esta sesión").

  * El HISTORIAL completo, en un archivo dentro de %APPDATA%\\TechClean.
    Antes todo se perdía al cerrar la app, así que era imposible responder
    a la pregunta que de verdad importa: "¿mi equipo va peor que hace tres
    meses?". Ahora se puede mirar hacia atrás.

El archivo es JSON por líneas (una acción por línea) a propósito, no un
JSON grande: así cada acción se añade al final sin releer ni reescribir
nada, y si una línea se corrompiera —un apagón a mitad de escritura— se
descarta esa y el resto del historial se sigue leyendo. Con un único JSON
grande, un byte malo se llevaría por delante el archivo entero.
"""

import json
import os
from datetime import datetime

# Cuántas acciones se conservan. Al pasarse, se recorta dejando las más
# recientes: el historial sirve para ver tendencias, no para guardar todo
# desde el principio de los tiempos, y un archivo que crece sin freno en la
# carpeta del usuario es exactamente lo que esta app le critica a otras.
LIMITE_ENTRADAS = 3000

NOMBRE_ARCHIVO = "historial.jsonl"


class SessionReport:
    def __init__(self, carpeta_datos=None):
        """`carpeta_datos`: dónde guardar el historial. Si es None no se
        escribe nada en disco — así el banco de pruebas no ensucia el
        historial real del usuario."""
        self.entries = []
        self.carpeta_datos = carpeta_datos
        # Identifica esta ejecución, para poder separar "lo de ahora" de
        # "lo de antes" al releer el archivo.
        #
        # Lleva un trozo al azar además de la hora y el PID: con solo esos
        # dos, dos informes creados en el MISMO segundo y el mismo proceso
        # salían con el mismo identificador — y entonces el historial los
        # cuenta como una sola sesión y "excluir lo de ahora" excluye
        # también lo de antes. Lo encontró el banco de pruebas, pero en un
        # equipo real pasaría igual si Windows reutiliza un PID.
        self.sesion_id = (f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
                          f"-{os.getpid()}-{os.urandom(3).hex()}")

    # ---------------- Sesión actual ----------------
    def add(self, seccion, accion, comando, exito, resultado,
             bytes_liberados=0, archivos_afectados=0):
        entrada = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seccion": seccion,
            "accion": accion,
            "comando": comando,
            "exito": bool(exito),
            "resultado": resultado,
            "bytes_liberados": bytes_liberados or 0,
            "archivos_afectados": archivos_afectados or 0,
            "sesion": self.sesion_id,
        }
        self.entries.append(entrada)
        self._anotar_en_disco(entrada)

    def total_bytes_liberados(self):
        return sum(e["bytes_liberados"] for e in self.entries)

    def total_archivos_afectados(self):
        return sum(e["archivos_afectados"] for e in self.entries)

    def total_acciones(self):
        return len(self.entries)

    def total_exitosas(self):
        return sum(1 for e in self.entries if e["exito"])

    def total_fallidas(self):
        return sum(1 for e in self.entries if not e["exito"])

    def entradas_recientes_primero(self):
        return list(reversed(self.entries))

    # ---------------- Historial en disco ----------------
    def _ruta_historial(self):
        if not self.carpeta_datos:
            return None
        return os.path.join(self.carpeta_datos, NOMBRE_ARCHIVO)

    def _anotar_en_disco(self, entrada):
        ruta = self._ruta_historial()
        if not ruta:
            return
        try:
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        except Exception:
            # Que no se pueda escribir el historial no puede impedir que la
            # acción se haga ni romper la pantalla: es un extra, no el
            # cometido de la app.
            pass

    def historial_completo(self, limite=None, solo_anteriores=False):
        """Todo lo guardado, de lo más reciente a lo más viejo.

        `solo_anteriores=True` deja fuera lo de esta ejecución, para poder
        mostrar "antes" y "ahora" sin repetir nada.
        """
        ruta = self._ruta_historial()
        if not ruta or not os.path.exists(ruta):
            return []
        entradas = []
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        entrada = json.loads(linea)
                    except ValueError:
                        continue          # línea corrupta: se salta, el resto vale
                    if not isinstance(entrada, dict):
                        continue
                    if solo_anteriores and entrada.get("sesion") == self.sesion_id:
                        continue
                    entradas.append(entrada)
        except OSError:
            return []
        entradas.reverse()
        return entradas[:limite] if limite else entradas

    def resumen_historial(self):
        """Números del historial ENTERO, para la cabecera de la pantalla."""
        entradas = self.historial_completo()
        if not entradas:
            return {"acciones": 0, "bytes": 0, "archivos": 0, "sesiones": 0, "desde": None}
        return {
            "acciones": len(entradas),
            "bytes": sum(e.get("bytes_liberados", 0) or 0 for e in entradas),
            "archivos": sum(e.get("archivos_afectados", 0) or 0 for e in entradas),
            "sesiones": len({e.get("sesion") for e in entradas if e.get("sesion")}),
            # `entradas` va de lo más nuevo a lo más viejo: la última es la
            # primera vez que se registró algo.
            "desde": entradas[-1].get("timestamp"),
        }

    def recortar_historial(self, limite=LIMITE_ENTRADAS):
        """Deja solo las `limite` acciones más recientes.

        Se escribe a un archivo temporal y se reemplaza al final: si se
        cortara la luz a mitad, el historial original sigue entero en vez de
        quedarse partido por la mitad.
        """
        ruta = self._ruta_historial()
        if not ruta or not os.path.exists(ruta):
            return 0
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                lineas = [l for l in f if l.strip()]
            if len(lineas) <= limite:
                return 0
            sobran = len(lineas) - limite
            temporal = ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                f.writelines(lineas[-limite:])
            os.replace(temporal, ruta)
            return sobran
        except OSError:
            return 0

    def borrar_historial(self):
        """Borra el historial guardado. Lo de la sesión actual se queda en
        memoria: el usuario está mirando esa pantalla ahora mismo."""
        ruta = self._ruta_historial()
        if not ruta:
            return False
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
            return True
        except OSError:
            return False

    # ---------------- Exportar ----------------
    def export_txt(self, path, incluir_comando=True, incluir_historial=False):
        entradas = self.historial_completo() if incluir_historial else self.entries
        if incluir_historial:
            entradas = list(reversed(entradas))     # en el archivo, de viejo a nuevo
        acciones = len(entradas)
        exitosas = sum(1 for e in entradas if e.get("exito"))
        bytes_totales = sum(e.get("bytes_liberados", 0) or 0 for e in entradas)

        with open(path, "w", encoding="utf-8") as f:
            f.write(("HISTORIAL COMPLETO" if incluir_historial else "REPORTE DE SESION")
                    + " - TechClean\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Acciones totales: {acciones}  "
                    f"(OK: {exitosas}, Fallidas: {acciones - exitosas})\n")
            f.write(f"Espacio total liberado: {bytes_totales} bytes\n")
            f.write("=" * 60 + "\n\n")
            for e in entradas:
                estado = "OK" if e.get("exito") else "FALLO"
                f.write(f'[{e.get("timestamp")}] ({estado}) {e.get("seccion")} > {e.get("accion")}\n')
                if incluir_comando:
                    f.write(f'   Comando ejecutado : {e.get("comando")}\n')
                f.write(f'   Resultado         : {e.get("resultado")}\n')
                if e.get("bytes_liberados"):
                    f.write(f'   Bytes liberados   : {e["bytes_liberados"]}\n')
                if e.get("archivos_afectados"):
                    f.write(f'   Archivos afectados: {e["archivos_afectados"]}\n')
                f.write("\n")
        return path
