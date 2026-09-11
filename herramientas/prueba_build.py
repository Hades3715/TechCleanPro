# -*- coding: utf-8 -*-
"""El cliente arranca en el idioma de la build e ignora las preferencias."""
import os, sys, json, tempfile

perfil = tempfile.mkdtemp(prefix="tcp_build_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
# preferencia GUARDADA en el idioma CONTRARIO, a proposito: el cliente
# debe ignorarla y usar el de la build; el admin debe respetarla.
json.dump({"idioma": "en", "idioma_preguntado": True},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import build_config
build_config.IDIOMA = sys.argv[2] if len(sys.argv) > 2 else "es"
import main
main.IDIOMA_BUILD = build_config.IDIOMA
main.EDICION = sys.argv[1]
import idiomas
from idiomas import t

app = main.TechCleanApp()
app.withdraw(); app.update()
app.mostrar_ajustes(); app.update()

def textos(w, acc):
    try:
        v = w.cget("text")
        if isinstance(v, str) and v: acc.append(v)
    except Exception: pass
    for h in w.winfo_children(): textos(h, acc)

vistos = []
textos(app.contenido, vistos)
selector = any(x in vistos for x in idiomas.IDIOMAS_DISPONIBLES.values()) or \
           idiomas.TEXTOS[idiomas.IDIOMA_ACTUAL].get("ajustes_idioma_titulo") in vistos

print(f"  edicion={main.EDICION:8} build={build_config.IDIOMA}  prefs=en")
print(f"     idioma en uso : {idiomas.IDIOMA_ACTUAL}")
print(f"     titulo Inicio : {t('nav_inicio')}")
print(f"     selector visible: {selector}")
app.destroy()
