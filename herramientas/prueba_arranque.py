# -*- coding: utf-8 -*-
"""Prueba de arranque real: construye la ventana entera y recorre todas las
pantallas, en los dos idiomas, sin mostrar nada y sin tocar las preferencias
reales del usuario (APPDATA apunta a una carpeta temporal)."""
import os, sys, json, tempfile, traceback

perfil = tempfile.mkdtemp(prefix="tcp_smoke_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)

IDIOMA = sys.argv[1] if len(sys.argv) > 1 else "es"
# idioma ya elegido: si no, el dialogo de primer arranque bloquea con wait_window
json.dump({"idioma": IDIOMA, "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import main

fallos = []
app = None
try:
    app = main.TechCleanApp()
    app.withdraw()
    app.update()
    print(f"[{IDIOMA}] ventana construida: {app.title()!r}")

    pantallas = [n for n in dir(app) if n.startswith("mostrar_") and callable(getattr(app, n))]
    for nombre in sorted(pantallas):
        try:
            getattr(app, nombre)()
            app.update()
            print(f"[{IDIOMA}]   OK  {nombre}")
        except Exception as e:
            fallos.append((nombre, repr(e)))
            print(f"[{IDIOMA}]  FALLO {nombre}: {e!r}")
            traceback.print_exc(limit=3)
except Exception as e:
    fallos.append(("__init__", repr(e)))
    print(f"[{IDIOMA}] FALLO al construir la ventana: {e!r}")
    traceback.print_exc(limit=6)
finally:
    try:
        if app is not None:
            app.destroy()
    except Exception:
        pass

print(f"[{IDIOMA}] RESULTADO: {'FALLOS: ' + str(fallos) if fallos else 'sin fallos'}")
sys.exit(1 if fallos else 0)
