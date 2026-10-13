"""
iconos.py
Iconos de línea de la interfaz, dibujados con Pillow (que la app ya usa
para la bandeja). Sustituyen a los emojis de la barra lateral: un emoji se
ve distinto en cada versión de Windows, no toma el color del tema y a
tamaño pequeño queda borroso.

No hay archivos de imagen: cada icono es una lista de trazos sobre una
cuadrícula de 24x24 (como los iconos de línea habituales), y se dibuja al
pedirlo, del color que toque, a 3 veces su tamaño para que se vea nítido
con el escalado de Windows. Se guardan en caché por (nombre, color, tamaño).
"""

from PIL import Image, ImageDraw

import customtkinter as ctk

_SUPER = 3          # se dibuja a 3x y customtkinter lo reduce: bordes suaves
_GROSOR = 1.9       # grosor del trazo, en unidades de la cuadrícula de 24


def _estrella(cx, cy, r, ri):
    return [(cx, cy - r), (cx + ri, cy - ri), (cx + r, cy), (cx + ri, cy + ri),
            (cx, cy + r), (cx - ri, cy + ri), (cx - r, cy), (cx - ri, cy - ri)]


# Cada trazo: ("linea", [(x, y), ...]) | ("rect", x, y, w, h, radio) |
# ("circulo", cx, cy, r) | ("punto", cx, cy, r) | ("poligono", [(x, y), ...]) |
# ("arco", x0, y0, x1, y1, inicio, fin)
TRAZOS = {
    "inicio": [("rect", 3, 3, 7, 9, 1.5), ("rect", 14, 3, 7, 5, 1.5), ("rect", 14, 12, 7, 9, 1.5),
               ("rect", 3, 16, 7, 5, 1.5)],
    "componentes": [("rect", 6, 6, 12, 12, 2)] + [("linea", p) for p in (
        [(9, 2), (9, 6)], [(15, 2), (15, 6)], [(9, 18), (9, 22)], [(15, 18), (15, 22)],
        [(2, 9), (6, 9)], [(2, 15), (6, 15)], [(18, 9), (22, 9)], [(18, 15), (22, 15)])],
    "optimizar": [("poligono", _estrella(12, 9, 6, 1.8)), ("poligono", _estrella(19, 17.5, 2.5, 0.8))],
    # Llave inglesa: anillo abierto arriba a la derecha (la boca) y mango.
    "reparar": [("arco", 10.5, 3.5, 20.5, 13.5, 0, 290), ("linea", [(12.3, 11.7), (4, 20)])],
    "energia": [("poligono", [(13, 2), (4, 14), (11, 14), (10, 22), (19, 10), (12, 10)])],
    "seguridad": [("poligono", [(12, 3), (20, 6), (20, 12), (18.5, 16.5), (12, 21), (5.5, 16.5), (4, 12), (4, 6)]),
                  ("linea", [(9, 12), (11, 14), (15, 10)])],
    "privacidad": [("rect", 5, 11, 14, 10, 2), ("arco", 8, 4, 16, 12, 180, 360),
                   ("linea", [(8, 8), (8, 11)]), ("linea", [(16, 8), (16, 11)])],
    "aplicaciones": [("rect", 3, 3, 7, 7, 1.5), ("rect", 14, 3, 7, 7, 1.5), ("rect", 3, 14, 7, 7, 1.5),
                     ("linea", [(17.5, 14), (17.5, 21)]), ("linea", [(14, 17.5), (21, 17.5)])],
    "gaming": [("rect", 2, 7, 20, 11, 5), ("linea", [(7, 10.5), (7, 14.5)]), ("linea", [(5, 12.5), (9, 12.5)]),
               ("punto", 15.5, 11.5, 1.1), ("punto", 18, 14, 1.1)],
    "segundo_plano": [("poligono", [(12, 3), (21, 8), (12, 13), (3, 8)]), ("linea", [(3, 13), (12, 18), (21, 13)])],
    "historial": [("circulo", 12, 12, 9), ("linea", [(12, 7), (12, 12), (15, 14)])],
    "ajustes": [("circulo", 12, 12, 3.2)] + [("linea", p) for p in (
        [(12, 2), (12, 5)], [(12, 19), (12, 22)], [(2, 12), (5, 12)], [(19, 12), (22, 12)],
        [(4.9, 4.9), (7, 7)], [(17, 17), (19.1, 19.1)], [(4.9, 19.1), (7, 17)], [(17, 7), (19.1, 4.9)])],
    "buscar": [("circulo", 11, 11, 7), ("linea", [(16.2, 16.2), (20.5, 20.5)])],
    "bandeja": [("linea", [(4, 15), (4, 20), (20, 20), (20, 15)]), ("linea", [(12, 3), (12, 14)]),
                ("linea", [(8, 10), (12, 14), (16, 10)])],
    "desbloquear": [("rect", 5, 11, 14, 10, 2), ("arco", 8, 4, 16, 12, 180, 330), ("linea", [(8, 8), (8, 11)])],
    "tecnico": [("rect", 3, 8, 18, 12, 2), ("linea", [(9, 8), (9, 5), (15, 5), (15, 8)]),
                ("linea", [(3, 13), (21, 13)])],
    "consola": [("rect", 2, 4, 20, 16, 2), ("linea", [(6, 9), (9, 12), (6, 15)]), ("linea", [(11, 15), (16, 15)])],
    "papelera": [("linea", [(4, 7), (20, 7)]), ("linea", [(9, 7), (9, 4), (15, 4), (15, 7)]),
                 ("linea", [(6, 7), (7, 20), (17, 20), (18, 7)])],
    "memoria": [("rect", 3, 7, 18, 10, 1.5), ("linea", [(7, 11), (7, 13)]), ("linea", [(11, 11), (11, 13)]),
                ("linea", [(15, 11), (15, 13)]), ("linea", [(6, 17), (6, 20)]), ("linea", [(18, 17), (18, 20)])],
    "disco": [("rect", 3, 13, 18, 7, 2), ("linea", [(5, 13), (7.5, 5), (16.5, 5), (19, 13)]),
              ("punto", 17, 16.5, 1)],
    "gpu": [("rect", 2, 6, 20, 11, 2), ("circulo", 9, 11.5, 3), ("linea", [(15, 9.5), (19, 9.5)]),
            ("linea", [(15, 13.5), (19, 13.5)]), ("linea", [(6, 17), (6, 20)])],
    "calendario": [("rect", 3, 5, 18, 16, 2), ("linea", [(3, 10), (21, 10)]), ("linea", [(8, 3), (8, 7)]),
                   ("linea", [(16, 3), (16, 7)])],
    "archivo": [("poligono", [(6, 3), (14, 3), (18, 7), (18, 21), (6, 21)]), ("linea", [(14, 3), (14, 7), (18, 7)])],
    "globo": [("circulo", 12, 12, 9), ("linea", [(3, 12), (21, 12)]), ("arco", 8, 3, 16, 21, 0, 360)],
    # 1.8.0
    "altavoz": [("poligono", [(4, 9.5), (8, 9.5), (13, 5), (13, 19), (8, 14.5), (4, 14.5)]),
                ("arco", 12, 8, 18, 16, -60, 60), ("arco", 12, 4.5, 21.5, 19.5, -60, 60)],
    "monitor": [("rect", 3, 4, 18, 12, 2), ("linea", [(9, 20), (15, 20)]), ("linea", [(12, 16), (12, 20)])],
    "imagen": [("rect", 3, 4, 18, 16, 2), ("circulo", 9, 10, 2), ("linea", [(21, 16), (16, 11), (7, 20)])],
    "correcto": [("circulo", 12, 12, 9), ("linea", [(8, 12), (11, 15), (16, 9)])],
    "marca": [("poligono", _estrella(12, 10.5, 7.5, 2.2)), ("poligono", _estrella(19.5, 18.5, 2.6, 0.8))],
    "carpeta": [("poligono", [(3, 6), (9.5, 6), (11.5, 8.5), (21, 8.5), (21, 19), (3, 19)])],
    "subir": [("linea", [(12, 19), (12, 5)]), ("linea", [(6, 11), (12, 5), (18, 11)])],
    "flecha": [("linea", [(9, 5), (16, 12), (9, 19)])],
    "fallo": [("circulo", 12, 12, 9), ("linea", [(9, 9), (15, 15)]), ("linea", [(15, 9), (9, 15)])],
    "campana": [("arco", 6, 4, 18, 18, 180, 360),
                ("linea", [(6, 11), (6, 16), (4, 17.5), (20, 17.5), (18, 16), (18, 11)]), ("punto", 12, 20.3, 1.4)],
}


def dibujar(nombre, color, tam=18):
    """Imagen RGBA del icono, a _SUPER veces `tam`. Un nombre desconocido
    da una imagen vacía: un icono que falta no debe tumbar una pantalla."""
    px = tam * _SUPER
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = px / 24
    g = max(1, round(_GROSOR * k))

    def P(x, y):
        return (x * k, y * k)

    for trazo in TRAZOS.get(nombre, []):
        tipo = trazo[0]
        if tipo == "linea":
            puntos = [P(*p) for p in trazo[1]]
            d.line(puntos, fill=color, width=g, joint="curve")
            for p in (puntos[0], puntos[-1]):       # remates redondos
                d.ellipse((p[0] - g / 2, p[1] - g / 2, p[0] + g / 2, p[1] + g / 2), fill=color)
        elif tipo == "rect":
            _, x, y, w, h, r = trazo
            d.rounded_rectangle((*P(x, y), *P(x + w, y + h)), radius=r * k, outline=color, width=g)
        elif tipo == "circulo":
            _, cx, cy, r = trazo
            d.ellipse((*P(cx - r, cy - r), *P(cx + r, cy + r)), outline=color, width=g)
        elif tipo == "punto":
            _, cx, cy, r = trazo
            d.ellipse((*P(cx - r, cy - r), *P(cx + r, cy + r)), fill=color)
        elif tipo == "poligono":
            d.polygon([P(*p) for p in trazo[1]], outline=color, width=g)
        elif tipo == "arco":
            _, x0, y0, x1, y1, ini, fin = trazo
            d.arc((*P(x0, y0), *P(x1, y1)), ini, fin, fill=color, width=g)
    return img


_cache = {}


def _clave_ventana():
    """Las imágenes de Tk pertenecen a la ventana principal que existía al
    crearlas. Si se cierra y se abre otra en el mismo proceso (el banco de
    pruebas lo hace), las de la caché vieja ya no existen para la nueva
    ("image pyimage1 doesn't exist"): la caché va por ventana."""
    import tkinter
    return id(getattr(tkinter, "_default_root", None))


def miniatura_tema(fichas, ancho=200, alto=104):
    """La miniatura como CTkImage (para un CTkLabel)."""
    clave = ("miniatura", id(fichas), ancho, alto, _clave_ventana())
    if clave not in _cache:
        img = miniatura_pil(fichas, ancho, alto)
        _cache[clave] = ctk.CTkImage(light_image=img, dark_image=img, size=(ancho, alto))
    return _cache[clave]


def tarjeta_tema(lienzo, fichas, ancho, alto, escala, relleno, borde, grosor, radio, fondo):
    """Fondo de una tarjeta de Ajustes → Apariencia con la miniatura del
    tema arriba, en píxeles reales (`ancho`, `alto`, `radio` y `grosor` ya
    escalados). Devuelve una PhotoImage para un tk.Canvas: quien la usa
    tiene que guardarla, o Tk la borra.

    En caché (1.8.0): dibujarlas a 3x y reducirlas costaba ~0,2 s CADA vez
    que se abría Ajustes (9 temas, y otra al pasar el ratón)."""
    from PIL import ImageTk
    clave = ("tarjeta_tema", id(fichas), ancho, alto, escala, relleno, borde, grosor, radio, fondo, _clave_ventana())
    if clave in _cache:
        return _cache[clave]
    k = _SUPER
    img = Image.new("RGB", (ancho * k, alto * k), fondo)
    ImageDraw.Draw(img).rounded_rectangle((0, 0, ancho * k - 1, alto * k - 1), radius=radio * k, fill=relleno,
                                          outline=borde, width=max(1, grosor) * k)
    img = img.resize((ancho, alto), Image.LANCZOS)
    ancho_mini, alto_mini = round(200 * escala), round(104 * escala)
    mini = miniatura_pil(fichas).resize((ancho_mini, alto_mini), Image.LANCZOS)
    img.paste(mini, ((ancho - ancho_mini) // 2, round(10 * escala)), mini)
    _cache[clave] = ImageTk.PhotoImage(img, master=lienzo)
    return _cache[clave]


def miniatura_pil(fichas, ancho=200, alto=104):
    """Vista previa de un tema: una ventanita con su barra lateral, un
    título, dos tarjetas y el botón de acento, con los colores de ESE tema
    (no del activo). Imagen de Pillow al doble de tamaño (se reduce al
    usarla, y así queda nítida)."""
    clave = ("miniatura_pil", id(fichas), ancho, alto)
    if clave in _cache:
        return _cache[clave]
    k = 2
    w, h = ancho * k, alto * k
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = max(2, min(fichas["radio_fila"], 12)) * k
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=fichas["fondo"], outline=fichas["borde"], width=k)
    rail = fichas["lateral_estilo"] == "rail"
    lat = int(w * (0.14 if rail else 0.3))
    d.rounded_rectangle((k, k, lat, h - k - 1), radius=r, fill=fichas["lateral"])
    d.rectangle((lat - r, k, lat, h - k - 1), fill=fichas["lateral"])
    d.line((lat, k, lat, h - k), fill=fichas["borde"], width=1)
    if rail:
        y = 12 * k
        for i in range(5):
            color = fichas["nav_activo_tx"] if i == 0 else fichas["texto3"]
            d.rounded_rectangle((lat / 2 - 5 * k, y, lat / 2 + 5 * k, y + 10 * k), radius=2 * k, outline=color, width=k)
            y += 17 * k
    else:
        d.rounded_rectangle((8 * k, 9 * k, lat - 14 * k, 14 * k), radius=2 * k, fill=fichas["texto"])
        y = 24 * k
        for i in range(4):
            if i == 0:
                d.rounded_rectangle((5 * k, y - 3 * k, lat - 5 * k, y + 7 * k), radius=3 * k,
                                    fill=fichas["nav_activo_bg"])
                d.rectangle((5 * k, y - 2 * k, 6 * k, y + 6 * k), fill=fichas["acento"])
            color = fichas["nav_activo_tx"] if i == 0 else fichas["texto3"]
            d.rounded_rectangle((10 * k, y, lat - (16 + 4 * i) * k, y + 4 * k), radius=2 * k, fill=color)
            y += 15 * k
    x0 = lat + 10 * k
    d.rounded_rectangle((x0, 10 * k, x0 + (w - x0) * 0.5, 16 * k), radius=2 * k, fill=fichas["texto"])
    ancho_t = (w - x0 - 10 * k - 6 * k) / 2
    for i in range(2):
        xa = x0 + i * (ancho_t + 6 * k)
        d.rounded_rectangle((xa, 26 * k, xa + ancho_t, 62 * k), radius=min(r, 8 * k), fill=fichas["panel"],
                            outline=fichas["borde"], width=1)
        d.rounded_rectangle((xa + 5 * k, 34 * k, xa + ancho_t * 0.45, 42 * k), radius=2 * k, fill=fichas["texto"])
        d.rounded_rectangle((xa + 5 * k, 52 * k, xa + ancho_t - 5 * k, 55 * k), radius=2 * k, fill=fichas["pista"])
        d.rounded_rectangle((xa + 5 * k, 52 * k, xa + 5 * k + (ancho_t - 10 * k) * (0.48, 0.37)[i], 55 * k),
                            radius=2 * k, fill=fichas["acento"])
    d.rounded_rectangle((x0, 72 * k, x0 + (w - x0) * 0.55, 86 * k), radius=min(fichas["radio_boton"], 7) * k,
                        fill=fichas["acento"])
    _cache[clave] = img
    return img


def esquinas(radio, grosor, relleno, borde, fuera, master):
    """Las cuatro esquinas redondeadas de una Tarjeta (1.8.0), como
    PhotoImage: un círculo dibujado a 4x y reducido (bordes suaves), partido
    en cuartos. Cada cuarto lleva por fuera el color de lo que hay detrás,
    el anillo del borde y por dentro el del panel. En caché por tema."""
    from PIL import ImageTk
    clave = ("esquinas", radio, grosor, relleno, borde, fuera, _clave_ventana())
    if clave not in _cache:
        k = 4
        d = 2 * radio
        img = Image.new("RGB", (d * k, d * k), fuera)
        pincel = ImageDraw.Draw(img)
        if grosor:
            pincel.ellipse((0, 0, d * k - 1, d * k - 1), fill=borde)
            pincel.ellipse((grosor * k, grosor * k, (d - grosor) * k - 1, (d - grosor) * k - 1), fill=relleno)
        else:
            pincel.ellipse((0, 0, d * k - 1, d * k - 1), fill=relleno)
        img = img.resize((d, d), Image.LANCZOS)
        cuartos = (img.crop((0, 0, radio, radio)), img.crop((radio, 0, d, radio)),
                   img.crop((0, radio, radio, d)), img.crop((radio, radio, d, d)))
        _cache[clave] = [ImageTk.PhotoImage(c, master=master) for c in cuartos]
    return _cache[clave]


def barra_reparto(ancho, alto, partes, pista, fondo, master):
    """La barra partida por colores de Espacio en disco (1.8.0), como
    PhotoImage: los trozos y las puntas redondas dibujados a 4x y reducidos.
    partes: [(fracción, color)]. Sin caché: cambia con cada análisis."""
    from PIL import ImageTk
    k = 4
    w, h = ancho * k, alto * k
    tiras = Image.new("RGB", (w, h), pista)
    pincel = ImageDraw.Draw(tiras)
    x = 0.0
    for fraccion, color in partes:
        largo = fraccion * w
        if largo >= 1:
            pincel.rectangle((round(x), 0, round(x + largo), h), fill=color)
            # Una raya fina del fondo entre trozo y trozo, si caben los dos.
            if x > 0 and largo > 3 * k:
                pincel.rectangle((round(x), 0, round(x) + k * 1.5, h), fill=fondo)
        x += largo
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radius=h / 2, fill=255)
    img = Image.new("RGB", (w, h), fondo)
    img.paste(tiras, (0, 0), mascara)
    return ImageTk.PhotoImage(img.resize((ancho, alto), Image.LANCZOS), master=master)


def icono_cuadro(nombre, color, relleno, fondo, lado, radio, tam_icono, escala, master):
    """El icono de una fila de acción sobre su cuadrito redondeado, todo en
    una imagen (1.8.0): antes era una CTkLabel con fondo y esquinas por fila,
    lo que más costaba de cada fila. En caché por tema."""
    from PIL import ImageTk
    px, r, pi = round(lado * escala), round(radio * escala), round(tam_icono * escala)
    clave = ("cuadro", nombre, color, relleno, fondo, px, r, pi, _clave_ventana())
    if clave not in _cache:
        k = 4
        img = Image.new("RGB", (px * k, px * k), fondo)
        ImageDraw.Draw(img).rounded_rectangle((0, 0, px * k - 1, px * k - 1), radius=r * k, fill=relleno)
        img = img.resize((px, px), Image.LANCZOS)
        ico = dibujar(nombre, color, tam_icono).resize((pi, pi), Image.LANCZOS)
        img.paste(ico, ((px - pi) // 2, (px - pi) // 2), ico)
        _cache[clave] = ImageTk.PhotoImage(img, master=master)
    return _cache[clave]


def foto(nombre, color, tam, escala, master):
    """El icono como PhotoImage de Tk, ya a su tamaño en píxeles (1.8.0):
    para un tk.Label en vez de una CTkLabel con CTkImage, que es un lienzo
    entero para enseñar 18 píxeles. Se guarda en caché (Tk borra las
    imágenes que nadie guarda)."""
    from PIL import ImageTk
    px = max(8, round(tam * escala))
    clave = ("foto", nombre, color, px, _clave_ventana())
    if clave not in _cache:
        img = dibujar(nombre, color, tam).resize((px, px), Image.LANCZOS)
        _cache[clave] = ImageTk.PhotoImage(img, master=master)
    return _cache[clave]


def icono(nombre, color, tam=18):
    """CTkImage lista para un CTkButton o CTkLabel (image=...)."""
    clave = (nombre, color, tam, _clave_ventana())
    if clave not in _cache:
        img = dibujar(nombre, color, tam)
        _cache[clave] = ctk.CTkImage(light_image=img, dark_image=img, size=(tam, tam))
    return _cache[clave]
