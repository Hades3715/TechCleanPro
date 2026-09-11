# -*- coding: utf-8 -*-
"""Comprueba que los botones de 'Probar error' salgan SOLO en admin.

Abre Ajustes en las dos ediciones y recorre los widgets buscando el texto
de cada boton, sin mostrar ninguna ventana.
"""
import os, sys, json, tempfile

perfil = tempfile.mkdtemp(prefix="tcp_ed_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import main
from idiomas import t

EDICION = sys.argv[1] if len(sys.argv) > 1 else "cliente"
main.EDICION = EDICION


def textos_de(widget, acumulador):
    """Recorre el arbol de widgets juntando todo el texto visible."""
    try:
        valor = widget.cget("text")
        if isinstance(valor, str) and valor:
            acumulador.append(valor)
    except Exception:
        pass
    for hijo in widget.winfo_children():
        textos_de(hijo, acumulador)


app = main.TechCleanApp()
app.withdraw()
app.update()
app.mostrar_ajustes()
app.update()

vistos = []
textos_de(app.contenido, vistos)

BUSCAR = [
    ("Probar error (directo)", t("ajustes_probar_error_directo"), EDICION == "admin"),
    ("Probar error (2do plano)", t("ajustes_probar_error_segundo_plano"), EDICION == "admin"),
    ("Diagnostico completo", t("ajustes_diagnostico_boton"), True),
    ("Abrir carpeta registros", t("ajustes_abrir_carpeta_registros"), True),
    ("Reporte de rendimiento", t("rend_btn_generar"), True),
    ("Apoyar en Ko-fi", t("ajustes_donar_boton"), True),
]

print(f"=== edicion: {EDICION} ===")
fallos = 0
for etiqueta, texto, esperado in BUSCAR:
    presente = texto in vistos
    ok = presente == esperado
    if not ok:
        fallos += 1
    marca = "OK " if ok else "MAL"
    estado = "visible" if presente else "oculto "
    print(f"  {marca}  {etiqueta:26} {estado}  (esperado: {'visible' if esperado else 'oculto'})")

app.destroy()
print(f"RESULTADO: {'sin fallos' if fallos == 0 else str(fallos) + ' FALLOS'}")
sys.exit(1 if fallos else 0)
