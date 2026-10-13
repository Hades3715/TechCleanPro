"""
informe.py
El informe de TechClean (1.8.0): cómo está el equipo, qué problemas se le
ven y qué hizo la app, en un PDF con la cara de TechClean (su franja de
color, su logo, cada problema con su nivel y qué hacer).

Se arma en HTML (generar_html: pura, la prueba le pasa datos inventados) y
Edge, que viene con Windows 10 y 11, lo imprime a PDF sin abrir ninguna
ventana (a_pdf). Sin librerías nuevas: si no hay Edge, se guarda el HTML,
que cualquier navegador pasa a PDF con Ctrl+P.

Los colores del papel van aquí escritos a mano a propósito: el informe se
imprime, y tiene que verse igual con cualquier tema de la app (con el tema
Negro puro, un PDF negro sería tinta tirada).
"""

import base64
import io
import os
import subprocess
import tempfile
from html import escape

IS_WINDOWS = os.name == "nt"

# Colores del papel (ver arriba).
MARCA = "#2563eb"
NIVELES = ("critico", "atencion", "info", "bien")


def logo_data_uri(ruta_ico, tam=96):
    """El icono de la app como imagen PNG dentro del HTML (data URI), para
    que el informe no dependa de ningún archivo suelto. None si no está."""
    try:
        from PIL import Image
        with Image.open(ruta_ico) as img:
            # Un .ico lleva varios tamaños: el más grande, para que se vea
            # nítido al imprimir.
            if hasattr(img, "ico"):
                imagen = img.ico.getimage(max(img.ico.sizes())).convert("RGBA")
            else:
                imagen = img.convert("RGBA")
            imagen.thumbnail((tam, tam))
            salida = io.BytesIO()
            imagen.save(salida, "PNG")
        return "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode("ascii")
    except Exception:
        return None


def _anillo(puntaje, color):
    """El anillo de la salud (el mismo que en Inicio), en SVG."""
    r = 34
    largo = 2 * 3.14159 * r
    lleno = largo * max(0, min(100, puntaje or 0)) / 100
    return (f"<svg width='92' height='92' viewBox='0 0 92 92'>"
            f"<circle cx='46' cy='46' r='{r}' fill='none' stroke='#e6e9ef' stroke-width='9'/>"
            f"<circle cx='46' cy='46' r='{r}' fill='none' stroke='{color}' stroke-width='9' stroke-linecap='round' "
            f"stroke-dasharray='{lleno:.1f} {largo:.1f}' transform='rotate(-90 46 46)'/>"
            f"<text x='46' y='53' text-anchor='middle' font-size='22' font-weight='700' fill='#1d2330' "
            f"font-family='Segoe UI, Arial'>{'' if puntaje is None else int(puntaje)}</text></svg>")


COLORES = {"critico": "#c0392b", "atencion": "#b7791f", "info": "#5b6475", "bien": "#1e8e4e"}

ESTILO = """
:root { --marca: %(marca)s; }
@page {
  size: A4; margin: 16mm 14mm 18mm 10mm;
  @bottom-left { content: "%(pie_pagina)s"; font: 8pt "Segoe UI", Arial; color: #8a92a3; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt "Segoe UI", Arial; color: #8a92a3; }
}
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", Arial, sans-serif; color: #1d2330; font-size: 10.5pt; line-height: 1.45; margin: 0; }
.franja { position: fixed; left: 0; top: 0; bottom: 0; width: 2.2mm; border-radius: 2mm;
  background: var(--marca); }
.hoja { padding-left: 11mm; }
.cabecera { display: flex; align-items: center; justify-content: space-between; padding-bottom: 10px;
  border-bottom: 2px solid var(--marca); margin-bottom: 18px; }
.marca { display: flex; align-items: center; gap: 10px; font-size: 17pt; font-weight: 700; color: var(--marca); }
.marca img { width: 34px; height: 34px; }
.cab-der { text-align: right; color: #5b6475; font-size: 9pt; }
h1 { font-size: 21pt; margin: 0 0 2px; }
.sub { color: #5b6475; font-size: 10pt; margin-bottom: 16px; }
h2 { font-size: 13pt; margin: 24px 0 10px; padding-left: 10px; border-left: 4px solid var(--marca);
  break-after: avoid; }
.resumen { display: flex; gap: 18px; align-items: center; background: #f4f7fd; border: 1px solid #dfe6f5;
  border-radius: 12px; padding: 14px 18px; break-inside: avoid; }
.resumen .estado { font-size: 14pt; font-weight: 700; }
.resumen p { margin: 4px 0 0; color: #3b4456; }
.cifras { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.cifra { border: 1px solid #e3e6ec; border-radius: 10px; padding: 8px 12px; min-width: 120px; break-inside: avoid; }
.cifra b { display: block; font-size: 15pt; }
.cifra span { color: #5b6475; font-size: 9pt; }
.problema { display: flex; gap: 12px; border: 1px solid #e3e6ec; border-left: 5px solid #5b6475;
  border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; break-inside: avoid; }
.problema .nivel { font-weight: 700; font-size: 8.5pt; text-transform: uppercase; letter-spacing: .4px;
  min-width: 70px; padding-top: 2px; }
.problema b { font-size: 11pt; }
.problema p { margin: 3px 0 0; color: #3b4456; white-space: pre-line; }
.problema .consejo { color: #1d2330; }
.problema .consejo:before { content: "%(que_hacer)s "; font-weight: 700; }
%(niveles)s
.nada { border: 1px solid #cfe9d9; background: #f0faf4; color: #1e8e4e; border-radius: 10px; padding: 12px 14px;
  font-weight: 600; }
table { width: 100%%; border-collapse: collapse; font-size: 9.5pt; }
th { text-align: left; color: #5b6475; font-weight: 600; border-bottom: 2px solid #e3e6ec; padding: 6px 8px; }
td { padding: 6px 8px; border-bottom: 1px solid #eef0f4; vertical-align: top; }
tr { break-inside: avoid; }
.equipo td:first-child { color: #5b6475; width: 34%%; }
.ok { color: #1e8e4e; font-weight: 700; } .mal { color: #c0392b; font-weight: 700; }
.mejor { color: #1e8e4e; font-weight: 600; } .peor { color: #c0392b; font-weight: 600; }
.nota { color: #5b6475; font-size: 9pt; margin-top: 6px; }
.final { margin-top: 26px; padding-top: 10px; border-top: 1px solid #e3e6ec; color: #8a92a3; font-size: 8.5pt; }
@media screen {
  body { max-width: 900px; margin: 24px auto; padding: 0 28px; }
}
"""


def generar_html(datos, t):
    """El informe en HTML. `datos` (todo opcional, ya traducido salvo los
    títulos de las secciones, que salen de `t`):

      version, fecha, equipo_nombre, tecnico, cliente, logo (data URI)
      salud: {"puntaje", "nivel" (bien/atencion/critico), "texto"}
      problemas: [{"nivel", "titulo", "detalle", "consejo"}]  (None = no se miró)
      equipo: [(etiqueta, valor)]
      antes_despues: {"momentos", "filas": [(medida, antes, después, cambio, sentido)]}
      totales: [(etiqueta, valor)]
      acciones: [{"fecha", "seccion", "accion", "resultado", "exito"}], acciones_mas (int)
      notas
    """
    e = escape
    fecha = datos.get("fecha") or ""
    version = datos.get("version") or ""
    niveles_css = "\n".join(
        f".problema.{n} {{ border-left-color: {c}; }} .problema.{n} .nivel {{ color: {c}; }}"
        for n, c in COLORES.items())
    # Lo que va en el pie de cada página es CSS: sin comillas ni barras.
    pie = t("informe_pie_pagina", version=version, fecha=fecha).replace("\\", "").replace('"', "'")
    estilo = ESTILO % {"marca": MARCA, "pie_pagina": pie, "niveles": niveles_css,
                       "que_hacer": t("informe_que_hacer").replace('"', "'")}

    partes = ["<!doctype html><html><head><meta charset='utf-8'>",
              f"<title>{e(t('informe_titulo'))} · {e(datos.get('equipo_nombre') or '')}</title>",
              f"<style>{estilo}</style></head><body><div class='franja'></div><div class='hoja'>"]

    # ---- Cabecera ----
    logo = f"<img src='{datos['logo']}' alt=''>" if datos.get("logo") else ""
    partes.append(f"<div class='cabecera'><div class='marca'>{logo}TechClean</div>"
                  f"<div class='cab-der'>{e(t('informe_cabecera', version=version))}<br>{e(fecha)}</div></div>")
    partes.append(f"<h1>{e(datos.get('titulo') or t('informe_titulo'))}</h1>")
    sub = [x for x in (datos.get("equipo_nombre"),
                       t("inf_tecnico", nombre=datos["tecnico"]) if datos.get("tecnico") else "",
                       t("inf_cliente", nombre=datos["cliente"]) if datos.get("cliente") else "") if x]
    partes.append(f"<div class='sub'>{e(' · '.join(sub))}</div>")

    # ---- Resumen: la salud y las cifras ----
    salud = datos.get("salud")
    problemas = datos.get("problemas")
    if salud:
        color = COLORES.get(salud.get("nivel"), MARCA)
        partes.append(f"<div class='resumen'>{_anillo(salud.get('puntaje'), color)}<div>"
                      f"<div class='estado' style='color:{color}'>{e(salud.get('estado') or '')}</div>"
                      f"<p>{e(salud.get('texto') or '')}</p></div></div>")
    cifras = []
    if problemas is not None:
        graves = sum(1 for p in problemas if p.get("nivel") == "critico")
        revisar = sum(1 for p in problemas if p.get("nivel") == "atencion")
        cifras += [(graves, t("informe_cifra_graves")), (revisar, t("informe_cifra_revisar"))]
    cifras += list(datos.get("totales") or [])
    if cifras:
        partes.append("<div class='cifras'>" + "".join(
            f"<div class='cifra'><b>{e(str(v))}</b><span>{e(str(k))}</span></div>" for v, k in cifras) + "</div>")

    # ---- Lo que conviene revisar ----
    if problemas is not None:
        partes.append(f"<h2>{e(t('informe_sec_problemas'))}</h2>")
        if not problemas:
            partes.append(f"<div class='nada'>{e(t('informe_sin_problemas'))}</div>")
        textos_nivel = {"critico": t("informe_nivel_critico"), "atencion": t("informe_nivel_atencion"),
                        "info": t("informe_nivel_info"), "bien": t("informe_nivel_bien")}
        orden = {n: i for i, n in enumerate(NIVELES)}
        for p in sorted(problemas, key=lambda p: orden.get(p.get("nivel"), 9)):
            nivel = p.get("nivel") if p.get("nivel") in COLORES else "info"
            partes.append(f"<div class='problema {nivel}'><div class='nivel'>{e(textos_nivel[nivel])}</div><div>"
                          f"<b>{e(p.get('titulo') or '')}</b>")
            if p.get("detalle"):
                partes.append(f"<p>{e(p['detalle'])}</p>")
            if p.get("consejo"):
                partes.append(f"<p class='consejo'>{e(p['consejo'])}</p>")
            partes.append("</div></div>")

    # ---- El equipo ----
    equipo = datos.get("equipo") or []
    if equipo:
        partes.append(f"<h2>{e(t('informe_sec_equipo'))}</h2><table class='equipo'>")
        partes += [f"<tr><td>{e(str(k))}</td><td>{e(str(v))}</td></tr>" for k, v in equipo]
        partes.append("</table>")

    # ---- Antes y después ----
    antes_despues = datos.get("antes_despues")
    if antes_despues and antes_despues.get("filas"):
        partes.append(f"<h2>{e(t('inf_antes_despues'))}</h2>")
        if antes_despues.get("momentos"):
            partes.append(f"<div class='nota'>{e(antes_despues['momentos'])}</div>")
        partes.append(f"<table><tr><th>{e(t('inf_col_medida'))}</th><th>{e(t('inf_col_antes'))}</th>"
                      f"<th>{e(t('inf_col_despues'))}</th><th>{e(t('inf_col_cambio'))}</th></tr>")
        for medida, antes, despues, cambio, sentido in antes_despues["filas"]:
            clase = sentido if sentido in ("mejor", "peor") else ""
            partes.append(f"<tr><td>{e(str(medida))}</td><td>{e(str(antes))}</td><td>{e(str(despues))}</td>"
                          f"<td class='{clase}'>{e(str(cambio))}</td></tr>")
        partes.append("</table>")

    # ---- Lo que hizo TechClean ----
    acciones = datos.get("acciones")
    if acciones is not None:
        partes.append(f"<h2>{e(t('informe_sec_trabajo'))}</h2>")
        if not acciones:
            partes.append(f"<div class='nota'>{e(t('informe_sin_acciones'))}</div>")
        else:
            partes.append(f"<table><tr><th></th><th>{e(t('informe_col_cuando'))}</th>"
                          f"<th>{e(t('informe_col_que'))}</th><th>{e(t('informe_col_resultado'))}</th></tr>")
            for a in acciones:
                marca = "<span class='ok'>✓</span>" if a.get("exito") else "<span class='mal'>✗</span>"
                que = e(a.get("accion") or "") + (f"<div class='nota'>{e(a['seccion'])}</div>" if a.get("seccion") else "")
                resultado = str(a.get("resultado") or "")
                if len(resultado) > 240:
                    resultado = resultado[:239] + "…"
                partes.append(f"<tr><td>{marca}</td><td>{e(a.get('fecha') or '')}</td><td>{que}</td>"
                              f"<td>{e(resultado)}</td></tr>")
            partes.append("</table>")
            if datos.get("acciones_mas"):
                partes.append(f"<div class='nota'>{e(t('informe_acciones_mas', n=datos['acciones_mas']))}</div>")

    if datos.get("notas"):
        partes.append(f"<h2>{e(t('inf_notas'))}</h2><p>{e(datos['notas'])}</p>")

    partes.append(f"<div class='final'>{e(t('informe_final', version=version))}</div></div></body></html>")
    return "".join(partes)


def buscar_edge():
    """La ruta de Microsoft Edge (viene con Windows 10 y 11), o None."""
    if not IS_WINDOWS:
        return None
    candidatos = []
    try:
        import winreg
        for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(raiz, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                    candidatos.append(winreg.QueryValueEx(k, "")[0])
            except OSError:
                pass
    except ImportError:
        pass
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidatos.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
    return next((c for c in candidatos if c and os.path.isfile(c)), None)


def a_pdf(html, ruta_pdf, timeout=90):
    """Imprime el HTML a PDF con Edge, sin ventana. Devuelve True solo si el
    PDF quedó escrito de verdad (existe y no está vacío): el código de salida
    de Edge no dice nada fiable.

    Con su propio perfil temporal (--user-data-dir): con el perfil normal,
    si el usuario tiene Edge abierto, la orden se le pasa a esa ventana y no
    imprime nada."""
    edge = buscar_edge()
    if not edge:
        return False
    with tempfile.TemporaryDirectory(prefix="tc_informe_", ignore_cleanup_errors=True) as carpeta:
        ruta_html = os.path.join(carpeta, "informe.html")
        with open(ruta_html, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            if os.path.exists(ruta_pdf):
                os.remove(ruta_pdf)
        except OSError:
            return False
        try:
            subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            "--disable-extensions", f"--user-data-dir={os.path.join(carpeta, 'perfil')}",
                            "--no-pdf-header-footer", f"--print-to-pdf={ruta_pdf}",
                            "file:///" + ruta_html.replace("\\", "/")],
                           capture_output=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            return False
    return os.path.isfile(ruta_pdf) and os.path.getsize(ruta_pdf) > 1000
