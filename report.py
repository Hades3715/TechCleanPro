"""
report.py
Registro estructurado y 100% transparente de cada acción ejecutada en la
sesión. El objetivo es que el usuario pueda verificar exactamente qué se
ejecutó, con qué comando y con qué resultado — sin ambigüedades.
"""

from datetime import datetime


class SessionReport:
    def __init__(self):
        self.entries = []

    def add(self, seccion, accion, comando, exito, resultado,
             bytes_liberados=0, archivos_afectados=0):
        self.entries.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seccion": seccion,
            "accion": accion,
            "comando": comando,
            "exito": bool(exito),
            "resultado": resultado,
            "bytes_liberados": bytes_liberados or 0,
            "archivos_afectados": archivos_afectados or 0,
        })

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

    def export_txt(self, path, incluir_comando=True):
        with open(path, "w", encoding="utf-8") as f:
            f.write("REPORTE DE SESION - TechClean\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Acciones totales: {self.total_acciones()}  "
                    f"(OK: {self.total_exitosas()}, Fallidas: {self.total_fallidas()})\n")
            f.write(f"Espacio total liberado: {self.total_bytes_liberados()} bytes\n")
            f.write("=" * 60 + "\n\n")
            for e in self.entries:
                estado = "OK" if e["exito"] else "FALLO"
                f.write(f'[{e["timestamp"]}] ({estado}) {e["seccion"]} > {e["accion"]}\n')
                if incluir_comando:
                    f.write(f'   Comando ejecutado : {e["comando"]}\n')
                f.write(f'   Resultado         : {e["resultado"]}\n')
                if e["bytes_liberados"]:
                    f.write(f'   Bytes liberados   : {e["bytes_liberados"]}\n')
                if e["archivos_afectados"]:
                    f.write(f'   Archivos afectados: {e["archivos_afectados"]}\n')
                f.write("\n")
        return path
