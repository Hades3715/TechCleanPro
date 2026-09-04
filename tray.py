"""
tray.py
Icono en la bandeja del sistema (system tray) para que TechClean pueda
seguir corriendo en segundo plano sin ocupar espacio en la barra de tareas.
Los callbacks de pystray corren en su PROPIO hilo — por eso, quien use esta
clase debe reenviar las llamadas al hilo principal de Tkinter (con
`root.after(0, ...)`), nunca tocar widgets directamente desde aquí.
"""

import os
import threading

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from idiomas import t

ICON_PATH = os.path.join(BASE_DIR, "assets", "icono.ico")

COLOR_OK = (46, 204, 113, 255)
COLOR_WARN = (241, 196, 15, 255)
COLOR_CRIT = (231, 76, 60, 255)


def _crear_icono_imagen():
    """Usa el ícono real de la app (assets/icono.ico) si está disponible;
    si no (por ejemplo corriendo fuera de la carpeta del proyecto), genera
    uno simple en memoria como respaldo, para que la bandeja nunca se quede
    sin ícono."""
    if HAS_PIL and os.path.exists(ICON_PATH):
        try:
            # El .ico trae varios tamaños incrustados (16 a 256px); sin
            # especificarlo, Pillow abre el más grande (256px), que algunos
            # backends de pystray no escalan bien para la bandeja. Se
            # redimensiona explícito a un tamaño típico de bandeja.
            return Image.open(ICON_PATH).convert("RGBA").resize((64, 64))
        except Exception:
            pass
    tam = 64
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, tam - 4, tam - 4), fill=(61, 139, 253, 255))
    draw.text((16, 22), "TC", fill="white")
    return img


def _color_por_valor(valor):
    if valor is None:
        return (119, 119, 119, 255)
    if valor < 60:
        return COLOR_OK
    if valor < 85:
        return COLOR_WARN
    return COLOR_CRIT


def generar_icono_con_valor(valor, etiqueta=""):
    """
    Genera un ícono de bandeja con el número en grande (estilo Core Temp /
    NetSpeedMonitor) — alternativa discreta al widget flotante, para quien
    prefiera no tener nada ocupando espacio en pantalla y solo mirar la
    barra de tareas. `valor` es 0-100 (redondeado); `etiqueta` es opcional
    (ej. 'C' para CPU, 'R' para RAM) y se dibuja chiquita debajo.
    """
    tam = 64
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _color_por_valor(valor)
    draw.rounded_rectangle((2, 2, tam - 2, tam - 2), radius=14, fill=(20, 22, 28, 255))

    texto = str(int(valor)) if valor is not None else "--"
    try:
        fuente = ImageFont.truetype("segoeuib.ttf", 30)
    except Exception:
        fuente = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    ancho_txt, alto_txt = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((tam - ancho_txt) / 2 - bbox[0], (tam - alto_txt) / 2 - bbox[1] - 4),
              texto, fill=color, font=fuente)

    if etiqueta:
        try:
            fuente_chica = ImageFont.truetype("segoeui.ttf", 12)
        except Exception:
            fuente_chica = ImageFont.load_default()
        bbox2 = draw.textbbox((0, 0), etiqueta, font=fuente_chica)
        ancho2 = bbox2[2] - bbox2[0]
        draw.text(((tam - ancho2) / 2 - bbox2[0], tam - 18), etiqueta, fill="gray70", font=fuente_chica)

    return img


class TrayIcon:
    """
    on_mostrar_panel, on_toggle_widget, on_toggle_auto, on_salir:
    callbacks SIN argumentos, ya envueltos por quien los pase (usa
    root.after(0, tu_funcion) para que se ejecuten de forma segura
    en el hilo principal de Tkinter).
    """
    def __init__(self, on_mostrar_panel, on_toggle_widget, on_toggle_auto, on_salir):
        self.on_mostrar_panel = on_mostrar_panel
        self.on_toggle_widget = on_toggle_widget
        self.on_toggle_auto = on_toggle_auto
        self.on_salir = on_salir
        self.icon = None
        self.disponible = HAS_PYSTRAY and HAS_PIL

    def iniciar(self):
        if not self.disponible:
            return False
        menu = pystray.Menu(
            # BUG corregido: ningún ítem estaba marcado como "default", así
            # que el clic IZQUIERDO en el ícono no hacía nada — solo el
            # clic derecho (que muestra el menú completo) funcionaba. Ahora
            # el clic izquierdo abre el panel directo, como se espera.
            pystray.MenuItem(t("tray_abrir_panel"), lambda: self.on_mostrar_panel(), default=True),
            pystray.MenuItem(t("tray_toggle_widget"), lambda: self.on_toggle_widget()),
            pystray.MenuItem(t("tray_modo_juego"), lambda: self.on_toggle_auto()),
            pystray.MenuItem(t("tray_salir"), lambda: self._salir()),
        )
        self.icon = pystray.Icon("TechClean", _crear_icono_imagen(), "TechClean", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()
        return True

    def _salir(self):
        if self.icon:
            self.icon.stop()
        self.on_salir()

    def detener(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def actualizar_valor_en_icono(self, valor, etiqueta=""):
        """Redibuja el ícono de la bandeja con un número en vivo (CPU/RAM %).
        Se ignora en silencio si la bandeja no está disponible — nunca debe
        interrumpir el resto de la app."""
        if not self.disponible or self.icon is None:
            return
        try:
            self.icon.icon = generar_icono_con_valor(valor, etiqueta)
        except Exception:
            pass

    def restaurar_icono_normal(self):
        if not self.disponible or self.icon is None:
            return
        try:
            self.icon.icon = _crear_icono_imagen()
        except Exception:
            pass
