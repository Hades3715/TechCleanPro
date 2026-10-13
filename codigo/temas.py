"""
temas.py
Los temas de TechClean: colores, letra y forma de toda la interfaz.

Cerrado a propósito: los temas van DENTRO de la app. No se descargan, no se
leen de archivos sueltos y no se pueden editar desde fuera; en preferencias
solo se guarda el NOMBRE, y si ahí aparece cualquier cosa que no esté en
TEMAS, se usa el de fábrica (nombre_valido). Para cambiar un tema hay que
cambiar el propio .exe.

Las letras son todas de las que ya trae Windows (Segoe UI, Segoe UI
Variable, Bahnschrift, Consolas) o la que trae customtkinter (Roboto): no
se añade ningún archivo de fuentes.

Cómo se usa:
  * `aplicar(nombre)` ANTES de crear la ventana: fija los colores por
    defecto de cada tipo de widget de customtkinter (su ThemeManager) y el
    modo claro/oscuro.
  * `resolver_fuentes(raiz)` en cuanto existe la ventana: elige, de la
    lista de cada tema, la primera letra instalada (Segoe UI Variable no
    existe en Windows 10, por ejemplo).
  * `T.<ficha>` en cualquier sitio de la interfaz: el color o el valor del
    tema activo (T.panel, T.texto2, T.acento, T.radio_panel...). Se lee al
    crear cada widget, así que un tema nuevo se ve en lo que se dibuja
    después; main.py redibuja la pantalla al cambiarlo.
"""

import copy

import customtkinter as ctk

POR_DEFECTO = "pulido"

# Orden en que se enseñan en Ajustes. La clave de idiomas de cada uno es
# "tema_<nombre>" y su descripción "tema_<nombre>_desc".
ORDEN = ["original", "pulido", "telemetria", "claro", "oled", "bosque", "retro", "sakura", "alto_contraste"]

_SEGOE_TEXTO = ["Segoe UI Variable Text", "Segoe UI"]
_SEGOE_DISPLAY = ["Segoe UI Variable Display", "Segoe UI"]

# Fichas de cada tema. Todas las claves son obligatorias (prueba_temas.py lo
# comprueba) y los textos sobre su fondo pasan el contraste 4.5:1.
TEMAS = {
    # Los colores que tenía la app hasta la 1.7.0.
    "original": dict(
        modo="dark", lateral_estilo="lista", escala=1.0, fuente=["Roboto", "Segoe UI"], fuente_num=["Roboto", "Segoe UI"],
        fondo="#242424", lateral="#2b2b2b", panel="#1c1f26", fila="#141720", borde="#2a2d36", hover="#2a2d36",
        boton2="#2a2d36", boton2_hover="#3a3e4a", texto="#dce4ee", texto2="#a3a3a3", texto3="#8f8f8f",
        # El azul de siempre (#1f6aa5), un pelo más claro: el original no
        # llegaba al contraste mínimo como color de línea sobre los paneles.
        acento="#2070ab", acento_hover="#144870", sobre_acento="#ffffff",
        nav_activo_bg="#2a2d36", nav_activo_tx="#ffffff", ok="#2ecc71", aviso="#f1c40f", sobre_aviso="#000000",
        critico="#e74c3c", peligro="#c0392b", pista="#33363f", entrada="#343638",
        radio_panel=16, radio_fila=10, radio_boton=6, borde_ancho=0),
    "pulido": dict(
        modo="dark", lateral_estilo="lista", escala=1.0, fuente=_SEGOE_TEXTO, fuente_num=_SEGOE_DISPLAY,
        fondo="#0f1115", lateral="#12151b", panel="#171b22", fila="#1b2029", borde="#262c38", hover="#1e232d",
        boton2="#252b37", boton2_hover="#2f3644", texto="#e9ecf2", texto2="#a6afbf", texto3="#8b94a5",
        acento="#2563eb", acento_hover="#1d4fc4", sobre_acento="#ffffff",
        nav_activo_bg="#1e232d", nav_activo_tx="#ffffff", ok="#34c47c", aviso="#f0a83a", sobre_aviso="#1a1206",
        critico="#f06565", peligro="#b4232c", pista="#252b36", entrada="#181c24",
        radio_panel=12, radio_fila=10, radio_boton=8, borde_ancho=1),
    "telemetria": dict(
        modo="dark", lateral_estilo="rail", escala=1.0, fuente=["Bahnschrift", "Segoe UI"], fuente_num=["Consolas"],
        fondo="#07090c", lateral="#0a0d12", panel="#0c1016", fila="#0a0d12", borde="#1a222c", hover="#121a22",
        boton2="#121820", boton2_hover="#1a2430", texto="#e6eef2", texto2="#93a3ad", texto3="#7f8f99",
        acento="#2ee6d6", acento_hover="#25bfb2", sobre_acento="#041417",
        nav_activo_bg="#0f2a2a", nav_activo_tx="#2ee6d6", ok="#3ddc84", aviso="#ffb347", sobre_aviso="#1a0f00",
        critico="#ff5f6d", peligro="#c2353f", pista="#16202a", entrada="#0a0d12",
        radio_panel=8, radio_fila=6, radio_boton=6, borde_ancho=1),
    "claro": dict(
        modo="light", lateral_estilo="lista", escala=1.0, fuente=_SEGOE_DISPLAY, fuente_num=_SEGOE_DISPLAY,
        fondo="#f3f4f6", lateral="#fbfbfc", panel="#ffffff", fila="#f6f7f9", borde="#e2e5ea", hover="#eef0f4",
        boton2="#eef0f3", boton2_hover="#e2e5ea", texto="#111418", texto2="#4b5563", texto3="#5f6673",
        acento="#1d4ed8", acento_hover="#1e40af", sobre_acento="#ffffff",
        nav_activo_bg="#e8efff", nav_activo_tx="#1e3a8a", ok="#15803d", aviso="#b45309", sobre_aviso="#ffffff",
        critico="#b91c1c", peligro="#b91c1c", pista="#eef0f3", entrada="#ffffff",
        radio_panel=18, radio_fila=12, radio_boton=12, borde_ancho=1),
    "oled": dict(
        modo="dark", lateral_estilo="lista", escala=1.0, fuente=_SEGOE_TEXTO, fuente_num=_SEGOE_DISPLAY,
        fondo="#000000", lateral="#000000", panel="#0b0b0b", fila="#111111", borde="#262626", hover="#161616",
        boton2="#1a1a1a", boton2_hover="#262626", texto="#f5f5f5", texto2="#a3a3a3", texto3="#8f8f8f",
        acento="#4d9bff", acento_hover="#2f86f5", sobre_acento="#00122b",
        nav_activo_bg="#0f1a2c", nav_activo_tx="#8ab8ff", ok="#34d27b", aviso="#f5b041", sobre_aviso="#1a1000",
        critico="#ff6b6b", peligro="#c62828", pista="#1c1c1c", entrada="#0b0b0b",
        radio_panel=10, radio_fila=8, radio_boton=8, borde_ancho=1),
    "bosque": dict(
        modo="dark", lateral_estilo="lista", escala=1.0, fuente=_SEGOE_TEXTO, fuente_num=_SEGOE_DISPLAY,
        fondo="#0e1512", lateral="#101a16", panel="#15211c", fila="#1a2822", borde="#22332b", hover="#1b2b24",
        boton2="#1f3029", boton2_hover="#294036", texto="#e7f0ea", texto2="#9db3a6", texto3="#8ba596",
        acento="#3fbf86", acento_hover="#33a171", sobre_acento="#04140c",
        nav_activo_bg="#183527", nav_activo_tx="#7fe0b0", ok="#3fbf86", aviso="#e3b341", sobre_aviso="#1a1300",
        critico="#f07167", peligro="#b23a3a", pista="#1d2c25", entrada="#101a16",
        radio_panel=12, radio_fila=10, radio_boton=10, borde_ancho=1),
    "retro": dict(
        modo="dark", lateral_estilo="lista", escala=1.0, fuente=["Consolas"], fuente_num=["Consolas"],
        fondo="#050a05", lateral="#040804", panel="#081208", fila="#0a170a", borde="#1d4a1d", hover="#0d220d",
        boton2="#0d220d", boton2_hover="#133313", texto="#b8ffb8", texto2="#7acc7a", texto3="#66b366",
        acento="#33ff66", acento_hover="#2bd957", sobre_acento="#002a0a",
        nav_activo_bg="#0d2a0d", nav_activo_tx="#33ff66", ok="#33ff66", aviso="#e8e85a", sobre_aviso="#141400",
        critico="#ff5555", peligro="#a12222", pista="#0f220f", entrada="#081208",
        radio_panel=2, radio_fila=2, radio_boton=2, borde_ancho=1),
    "sakura": dict(
        modo="light", lateral_estilo="lista", escala=1.0, fuente=_SEGOE_DISPLAY, fuente_num=_SEGOE_DISPLAY,
        fondo="#fbf4f7", lateral="#fffafc", panel="#ffffff", fila="#fdf6f9", borde="#f0dbe4", hover="#fbe9f0",
        boton2="#f8e8ef", boton2_hover="#f0d6e1", texto="#2a1820", texto2="#6e5560", texto3="#765d69",
        acento="#c2185b", acento_hover="#a3134c", sobre_acento="#ffffff",
        nav_activo_bg="#fde4ee", nav_activo_tx="#8a0f41", ok="#2e7d4f", aviso="#a15c00", sobre_aviso="#ffffff",
        critico="#b3261e", peligro="#b3261e", pista="#f6e6ed", entrada="#ffffff",
        radio_panel=18, radio_fila=14, radio_boton=14, borde_ancho=1),
    # Para ver mejor o usar el equipo al sol: todo un 12 % más grande.
    "alto_contraste": dict(
        modo="dark", lateral_estilo="lista", escala=1.12, fuente=["Segoe UI"], fuente_num=["Segoe UI"],
        fondo="#000000", lateral="#000000", panel="#000000", fila="#000000", borde="#ffffff", hover="#262626",
        boton2="#000000", boton2_hover="#333333", texto="#ffffff", texto2="#ffffff", texto3="#e6e6e6",
        acento="#ffd400", acento_hover="#e6c000", sobre_acento="#000000",
        nav_activo_bg="#ffd400", nav_activo_tx="#000000", ok="#3dff8b", aviso="#ffd400", sobre_aviso="#000000",
        critico="#ff6b6b", peligro="#c40000", pista="#3a3a3a", entrada="#000000",
        radio_panel=4, radio_fila=4, radio_boton=4, borde_ancho=2),
}

# Un panel con un toque cálido (la tarjeta de apoyo al proyecto, el aviso de
# funciones por desbloquear), para que no se pierda entre los demás.
_CALIDO = {"original": "#241f1a", "pulido": "#1b1812", "telemetria": "#15110a", "claro": "#fff7ea",
           "oled": "#140f08", "bosque": "#1f1d14", "retro": "#141405", "sakura": "#fff1f4",
           "alto_contraste": "#000000"}
for _nombre, _fichas in TEMAS.items():
    _fichas["calido"] = _CALIDO[_nombre]
    # Los botones de peligro (apagar, terminar, cerrar) llevan siempre un
    # rojo oscuro de fondo: el texto blanco se lee en todos los temas.
    _fichas["sobre_peligro"] = "#ffffff"

FICHAS = ("modo", "lateral_estilo", "escala", "fuente", "fuente_num", "fondo", "lateral", "panel", "fila", "borde",
          "hover", "boton2", "boton2_hover", "texto", "texto2", "texto3", "acento", "acento_hover", "sobre_acento",
          "nav_activo_bg", "nav_activo_tx", "ok", "aviso", "sobre_aviso", "critico", "peligro", "sobre_peligro",
          "pista", "entrada", "calido", "radio_panel", "radio_fila", "radio_boton", "borde_ancho")


class _Fichas:
    """Las fichas del tema activo como atributos: T.panel, T.acento..."""
    nombre = POR_DEFECTO
    familia = "Segoe UI"
    familia_num = "Segoe UI"


T = _Fichas()


def nombre_valido(nombre):
    return nombre if nombre in TEMAS else POR_DEFECTO


def _tema_ctk(f):
    """El diccionario de colores por defecto de customtkinter para este
    tema. Se parte del tema "blue" que trae la librería (así no falta
    ninguna clave que espere) y se pisan los colores. El mismo color para
    los modos claro y oscuro: el modo solo se usa para la barra de título."""
    base = _base_ctk()

    def par(color):
        return [color, color]

    base["CTk"]["fg_color"] = par(f["fondo"])
    base["CTkToplevel"]["fg_color"] = par(f["fondo"])
    base["CTkFrame"].update(fg_color=par(f["panel"]), top_fg_color=par(f["fila"]), border_color=par(f["borde"]),
                            corner_radius=f["radio_fila"])
    base["CTkButton"].update(fg_color=par(f["acento"]), hover_color=par(f["acento_hover"]),
                             text_color=par(f["sobre_acento"]), border_color=par(f["borde"]),
                             text_color_disabled=par(f["texto3"]), corner_radius=f["radio_boton"],
                             border_width=2 if f["borde_ancho"] >= 2 else 0)
    base["CTkLabel"]["text_color"] = par(f["texto"])
    base["CTkEntry"].update(fg_color=par(f["entrada"]), border_color=par(f["borde"]), text_color=par(f["texto"]),
                            placeholder_text_color=par(f["texto3"]), corner_radius=f["radio_boton"])
    base["CTkCheckBox"].update(fg_color=par(f["acento"]), hover_color=par(f["acento_hover"]),
                               border_color=par(f["texto3"]), checkmark_color=par(f["sobre_acento"]),
                               text_color=par(f["texto"]), text_color_disabled=par(f["texto3"]))
    base["CTkSwitch"].update(fg_color=par(f["pista"]), progress_color=par(f["acento"]),
                             button_color=par(f["texto"]), button_hover_color=par(f["texto2"]),
                             text_color=par(f["texto"]), text_color_disabled=par(f["texto3"]))
    base["CTkRadioButton"].update(fg_color=par(f["acento"]), border_color=par(f["texto3"]),
                                  hover_color=par(f["acento_hover"]), text_color=par(f["texto"]),
                                  text_color_disabled=par(f["texto3"]))
    base["CTkProgressBar"].update(fg_color=par(f["pista"]), progress_color=par(f["acento"]))
    base["CTkSlider"].update(fg_color=par(f["pista"]), progress_color=par(f["texto2"]),
                             button_color=par(f["acento"]), button_hover_color=par(f["acento_hover"]))
    base["CTkOptionMenu"].update(fg_color=par(f["boton2"]), button_color=par(f["boton2_hover"]),
                                 button_hover_color=par(f["hover"]), text_color=par(f["texto"]),
                                 text_color_disabled=par(f["texto3"]), corner_radius=f["radio_boton"])
    base["CTkComboBox"].update(fg_color=par(f["entrada"]), border_color=par(f["borde"]),
                               button_color=par(f["boton2_hover"]), button_hover_color=par(f["hover"]),
                               text_color=par(f["texto"]), text_color_disabled=par(f["texto3"]))
    base["CTkScrollbar"].update(button_color=par(f["boton2_hover"]), button_hover_color=par(f["texto3"]))
    base["CTkSegmentedButton"].update(fg_color=par(f["boton2"]), selected_color=par(f["acento"]),
                                      selected_hover_color=par(f["acento_hover"]),
                                      unselected_color=par(f["boton2"]), unselected_hover_color=par(f["boton2_hover"]),
                                      text_color=par(f["texto"]), text_color_disabled=par(f["texto3"]),
                                      corner_radius=f["radio_boton"])
    base["CTkTextbox"].update(fg_color=par(f["fila"]), border_color=par(f["borde"]), text_color=par(f["texto"]),
                              scrollbar_button_color=par(f["boton2_hover"]),
                              scrollbar_button_hover_color=par(f["texto3"]))
    base["CTkScrollableFrame"]["label_fg_color"] = par(f["fila"])
    base["DropdownMenu"].update(fg_color=par(f["panel"]), hover_color=par(f["hover"]), text_color=par(f["texto"]))
    return base


_BASE = {}


def _base_ctk():
    if not _BASE:
        ctk.ThemeManager.load_theme("blue")
        _BASE.update(copy.deepcopy(ctk.ThemeManager.theme))
    return copy.deepcopy(_BASE)


def aplicar(nombre):
    """Activa un tema. Devuelve el nombre que quedó (el de fábrica si el
    pedido no existe). Lo que ya está dibujado no cambia solo: hay que
    redibujarlo."""
    nombre = nombre_valido(nombre)
    fichas = TEMAS[nombre]
    for clave in FICHAS:
        setattr(T, clave, fichas[clave])
    T.nombre = nombre
    tema = _tema_ctk(fichas)
    tema["CTkFont"]["family"] = T.familia
    ctk.ThemeManager.theme = tema
    ctk.set_appearance_mode(fichas["modo"])
    return nombre


_familias = set()


def resolver_fuentes(raiz):
    """Elige la primera letra instalada de cada lista del tema. Necesita
    una ventana de Tk ya creada (es quien sabe qué letras hay)."""
    if not _familias:
        try:
            import tkinter.font as tkfont
            _familias.update(tkfont.families(raiz))
        except Exception:
            pass
    # Roboto la carga customtkinter por su cuenta y Tk no siempre la lista.
    disponibles = _familias | {"Roboto"}
    T.familia = next((f for f in T.fuente if f in disponibles), "Segoe UI")
    T.familia_num = next((f for f in T.fuente_num if f in disponibles), T.familia)
    ctk.ThemeManager.theme["CTkFont"]["family"] = T.familia
    return T.familia


# ---------------- Contraste (lo usa prueba_temas.py) ----------------
def _luminancia(hex_color):
    h = hex_color.lstrip("#")
    canales = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        canales.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2]


def serie(n):
    """n colores bien distintos para un gráfico por partes (el espacio por
    tipo de archivo, 1.8.0), sacados del acento del tema girando el tono:
    cambian con el tema y todos se distinguen del panel (contraste de 3:1
    o más, el mínimo para gráficos)."""
    import colorsys
    h = T.acento.lstrip("#")
    tono, luz, sat = colorsys.rgb_to_hls(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))
    sat = max(sat, 0.5)
    oscuro = _luminancia(T.panel) < 0.2
    colores = []
    for i in range(n):
        claro = luz
        while True:
            r, g, b = colorsys.hls_to_rgb((tono + i / max(1, n)) % 1.0, claro, sat)
            color = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
            if contraste(color, T.panel) >= 3 or not 0.05 < claro < 0.95:
                break
            claro += 0.04 if oscuro else -0.04
        colores.append(color)
    return colores


def contraste(a, b):
    """Relación de contraste WCAG entre dos colores hex (1 a 21)."""
    la, lb = _luminancia(a), _luminancia(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


aplicar(POR_DEFECTO)
