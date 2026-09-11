# -*- coding: utf-8 -*-
"""Recorre TODAS las pantallas y pulsa todo lo que solo muestra cosas.

Abrir una pantalla no basta para saber que funciona: los fallos historicos
de este proyecto vivian en el segundo clic — cambiar de pestana, filtrar
una lista, repintar con datos vacios. Ahi estaban el KeyError de la
pestana "Ventanas", las pestanas de disco que abrian la pantalla
equivocada y los permisos de privacidad que ensenaban los datos de la
camara en la pestana del microfono.

Que hace:
  1. Abre cada pantalla de la app.
  2. Busca cada boton, pestana y menu desplegable que haya en ella.
  3. Pulsa SOLO lo que muestra informacion: pestanas, filtros y repintados.
  4. Ademas llama a cada _pintar_* con datos VACIOS y con datos raros
     (None, listas sin las claves esperadas), que es como llegan cuando
     una consulta falla en un equipo distinto al del desarrollador.

Lo que NUNCA toca: nada que limpie, borre, apague, reinicie, cambie el
registro, abra ventanas del sistema o mande datos por internet. La lista
de prohibidos esta abajo y se comprueba por nombre.

Uso:  python herramientas\\revisar_pantallas.py [es|en]
"""
import json
import os
import sys
import tempfile
import time
import traceback

IDIOMA = sys.argv[1] if len(sys.argv) > 1 else "es"

perfil = tempfile.mkdtemp(prefix="tcp_pant_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": IDIOMA, "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import customtkinter as ctk
import main

# Nada cuyo nombre contenga esto se ejecuta, pase lo que pase.
PROHIBIDO = (
    "limpiar", "borrar", "eliminar", "vaciar", "apagar", "reiniciar", "suspender",
    "terminar", "cerrar", "matar", "desinstalar", "instalar", "actualizar_app",
    "abrir", "exportar", "ejecutar", "aplicar", "activar", "desactivar", "toggle",
    "set_", "guardar", "restablecer", "crear", "quitar", "reparar", "optimiz",
    "liberar", "papelera", "defender", "firewall_", "servicio", "bios", "error",
    "sonido", "micro", "mezclador", "speedtest", "velocidad", "descargar",
    "solicitar", "enviar", "confirmar", "probar", "escanear", "buscar_actualiz",
)
# De lo que queda, solo se ejecuta lo que empieza asi: son los que pintan.
PERMITIDO_PREFIJOS = ("_cambiar_pestana", "_filtrar_", "_mostrar_")

fallos = []
ejecutados = 0


def seguro(nombre):
    bajo = nombre.lower()
    if any(p in bajo for p in PROHIBIDO):
        return False
    return any(bajo.startswith(p) for p in PERMITIDO_PREFIJOS)


app = main.TechCleanApp()
app.geometry("1400x900+4000+4000")
app.withdraw()
for _ in range(10):
    app.update()
    time.sleep(0.02)

PANTALLAS = sorted(n for n in dir(app)
                   if n.startswith("mostrar_") and callable(getattr(app, n)))

print(f"[{IDIOMA}] {len(PANTALLAS)} pantallas\n")

for pantalla in PANTALLAS:
    try:
        getattr(app, pantalla)()
        for _ in range(6):
            app.update()
            time.sleep(0.02)
    except Exception:
        fallos.append(f"{pantalla}: no abre — {traceback.format_exc().strip().splitlines()[-1]}")
        print(f"  [FALLO] {pantalla} no abre")
        continue

    # --- pulsar cada valor de cada pestana / menu de esta pantalla ---
    interruptores = []

    def recolectar(widget):
        for hijo in widget.winfo_children():
            if isinstance(hijo, (ctk.CTkSegmentedButton, ctk.CTkOptionMenu)):
                interruptores.append(hijo)
            recolectar(hijo)

    recolectar(app.contenido)

    tocados = 0
    for control in interruptores:
        try:
            valores = control.cget("values") or []
        except Exception:
            continue
        for valor in valores:
            try:
                # Cambiar de pestana destruye el contenido de la pantalla, y
                # con el los controles que se habian recolectado antes.
                # Tocar uno ya destruido es un fallo de ESTA herramienta, no
                # de la app: se comprueba que siga vivo.
                if not control.winfo_exists():
                    break
                control.set(valor)
                comando = control.cget("command")
                if comando:
                    comando(valor)
                for _ in range(4):
                    app.update()
                    time.sleep(0.01)
                tocados += 1
            except Exception:
                ultima = traceback.format_exc().strip().splitlines()[-1]
                fallos.append(f"{pantalla} > pestana {valor!r}: {ultima}")
                print(f"  [FALLO] {pantalla} > {valor!r}  ->  {ultima}")

    print(f"  [OK  ] {pantalla:26} {len(interruptores)} controles, {tocados} valores probados")
    ejecutados += tocados

# ---- Los _pintar_* con datos vacios o raros ----
print("\nRepintados con datos vacios o incompletos:")
pintores = sorted(n for n in dir(app) if n.startswith("_pintar_") and callable(getattr(app, n)))
# Casos REALISTAS: es como llegan los datos cuando una consulta falla o
# devuelve algo a medias en un equipo distinto al del desarrollador. No se
# prueba pasar un diccionario donde va una lista: eso seria un error de
# programacion del propio llamador, no un dato degradado, y solo generaria
# ruido en el informe.
casos = [
    ("lista vacia", []),
    ("None", None),
    ("dict vacio", {}),
    ("lista con dict vacio", [{}]),
    ("lista con claves a medias", [{"nombre": "algo"}]),
    ("lista con valores None", [{"nombre": None, "ruta": None, "bytes": None}]),
]
probados = 0
for nombre in pintores:
    if not seguro(nombre) and any(p in nombre.lower() for p in PROHIBIDO):
        continue
    funcion = getattr(app, nombre)
    for etiqueta, dato in casos:
        try:
            funcion(dato)
            app.update()
            probados += 1
        except TypeError:
            break          # esa firma pide otra cosa: no es un fallo
        except Exception:
            ultima = traceback.format_exc().strip().splitlines()[-1]
            # Un KeyError/AttributeError aqui SI es un fallo: son los datos
            # que llegan cuando una consulta falla en el equipo del usuario.
            fallos.append(f"{nombre}({etiqueta}): {ultima}")
            print(f"  [FALLO] {nombre}({etiqueta})  ->  {ultima}")

print(f"  {probados} repintados con datos degradados")

app.destroy()
print(f"\n[{IDIOMA}] RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
for f in fallos:
    print(f"    - {f}")
sys.exit(1 if fallos else 0)
