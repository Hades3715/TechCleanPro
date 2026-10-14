# -*- coding: utf-8 -*-
"""Reportar un problema (1.8.0): el texto que un usuario le manda al
desarrollador cuando algo falla, con el error y cómo es su equipo.

Nada se envía solo. La app abre la página de "nuevo issue" de GitHub con el
texto ya puesto, y la persona lo lee, lo cambia si quiere y lo publica ella
(o lo copia y lo manda por donde quiera). Así TechClean sigue sin conectarse
a nada por su cuenta y sin un servidor que mantener (ver PRIVACIDAD.md).

Antes de enseñarlo se quita lo que identifica a la persona: la carpeta de
usuario (C:\\Users\\Ana\\...), el nombre de usuario y el del equipo.

Todo aquí es puro (sin Tk ni sistema) para poder probarlo."""
import re
from urllib.parse import quote

REPO = "Hades3715/TechCleanPro"
# GitHub rechaza las direcciones de más de ~8 KB; se deja margen.
MAX_URL = 7000
# Lo que se escribe a mano tampoco puede llenar la dirección entera.
MAX_DESCRIPCION = 1500


def limpiar(texto, usuario="", carpeta_usuario="", equipo=""):
    """Quita la carpeta de usuario (en sus tres formas: C:\\Users\\Ana,
    C:/Users/Ana y la escapada C:\\\\Users\\\\Ana de un repr), el nombre de
    usuario y el del equipo. Los nombres, solo como palabra suelta y de tres
    letras o más: "ed" no puede comerse media palabra de un error."""
    if not texto:
        return ""
    if carpeta_usuario:
        normal = carpeta_usuario.rstrip("\\/")
        for forma in sorted({normal.replace("\\", "\\\\"), normal, normal.replace("\\", "/")}, key=len, reverse=True):
            texto = re.sub(re.escape(forma), "%USERPROFILE%", texto, flags=re.IGNORECASE)
    # El más largo primero: con el usuario "Ana" y el equipo "ANA-PC", quitar
    # antes el usuario dejaba "<usuario>-PC" y el equipo ya no se reconocía.
    for nombre, cambio in sorted(((usuario, "<usuario>"), (equipo, "<equipo>")), key=lambda p: -len(p[0] or "")):
        if nombre and len(nombre) >= 3:
            texto = re.sub(r"(?<!\w)" + re.escape(nombre) + r"(?!\w)", cambio, texto, flags=re.IGNORECASE)
    return texto


def titulo(t, error, version):
    """La última línea del error (la que dice qué pasó) o uno genérico."""
    lineas = [linea.strip() for linea in (error or "").strip().splitlines() if linea.strip()]
    if lineas:
        return t("reporte_titulo_error", version=version, error=lineas[-1][:90])
    return t("reporte_titulo_problema", version=version)


def recortar_error(t, error, ultimas):
    """Las 2 primeras líneas y las `ultimas`: en un error de Python lo que
    dice qué pasó y dónde está al FINAL, y el principio dice desde dónde."""
    lineas = (error or "").strip().splitlines()
    if len(lineas) <= ultimas + 3:
        return "\n".join(lineas)
    quitadas = len(lineas) - ultimas - 2
    return "\n".join(lineas[:2] + [t("reporte_md_recortado", n=quitadas)] + lineas[len(lineas) - ultimas:])


def _titulo_md(texto):
    # Aparte, y no "### " + t(...) en la misma línea: verificar_idiomas
    # quita lo que va detrás de un # como si fuera un comentario, y la clave
    # salía como "definida sin usar".
    return "#" * 3 + " " + texto


def armar(t, error="", descripcion="", equipo=(), acciones=(), aviso=""):
    """El texto del reporte, en Markdown (GitHub lo enseña ordenado)."""
    partes = [_titulo_md(t("reporte_md_que_paso")),
              (descripcion or "").strip() or t("reporte_md_sin_descripcion"), ""]
    if (error or "").strip():
        partes += [_titulo_md(t("reporte_md_error")), "```", error.strip(), "```", ""]
    if acciones:
        partes += [_titulo_md(t("reporte_md_acciones"))] + [f"- {a}" for a in acciones] + [""]
    partes += [_titulo_md(t("reporte_md_equipo"))] + [f"- {k}: {v}" for k, v in equipo if v]
    if aviso:
        partes += ["", f"_{aviso}_"]
    return "\n".join(partes)


def preparar(t, version, error="", descripcion="", equipo=(), acciones=(), repo=REPO, maximo=MAX_URL):
    """Devuelve (texto completo, dirección de GitHub, recortado). Si el
    texto no cabe en la dirección, se recorta el error por el medio y se
    avisa en el propio reporte; el completo es el que se copia."""
    completo = armar(t, error, descripcion, equipo, acciones)
    base = f"https://github.com/{repo}/issues/new?title={quote(titulo(t, error, version))}&body="
    url = base + quote(completo)
    if len(url) <= maximo:
        return completo, url, False
    corta = (descripcion or "").strip()
    if len(corta) > MAX_DESCRIPCION:
        corta = corta[:MAX_DESCRIPCION].rstrip() + " …"
    for ultimas in (40, 25, 15, 8, 4, 0):
        cuerpo = armar(t, recortar_error(t, error, ultimas), corta, equipo, acciones[-3:], t("reporte_md_recortado_aviso"))
        url = base + quote(cuerpo)
        if len(url) <= maximo:
            return completo, url, True
    return completo, base + quote(armar(t, "", "", equipo, (), t("reporte_md_recortado_aviso"))), True
