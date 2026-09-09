"""
widget.py
Barra de rendimiento flotante, siempre encima, con diseño de tarjetas
(inspirado en overlays tipo Xbox Game Bar / utilidades de fabricante:
tarjetas separadas para Rendimiento, Atajos y Sistema). Arrastrable,
expandible, y de bajo consumo: los datos "baratos" (CPU/RAM/red) se
actualizan cada 1s con psutil (muy ligero); la GPU y la temperatura, más
costosas de consultar, se refrescan cada 4s en un hilo aparte.

Todo en tkinter plano (no customtkinter) a propósito: customtkinter valida
sus argumentos de forma estricta (aprendido de la mala experiencia con la
clase Sparkline del panel principal) y este widget no necesita nada de lo
que customtkinter ofrece — con tk.Frame/tk.Label/tk.Canvas alcanza y sobra.

Lo que se rehízo en el repaso estético:

  * ESQUINAS REDONDEADAS de verdad, no simuladas. Una ventana sin barra de
    título de Windows es un rectángulo duro, y encima de un juego o del
    escritorio se notaba como un recorte de cartón pegado a la pantalla.
    Se consiguen con un color clave transparente: ver
    _preparar_ventana_redondeada.
  * LOS NÚMEROS YA NO TIEMBLAN. Las etiquetas de la barra compacta se
    medían por su texto, así que al pasar de "CPU 9%" a "CPU 10%" la
    etiqueta crecía un carácter y empujaba a las de su derecha: la barra
    entera se recolocaba sola cada segundo. Ahora van en ancho fijo y con
    tipografía de ancho fijo, que es lo que hace falta para que un número
    que cambia no mueva lo que tiene al lado.
  * LA RED SE LEE. Iba siempre en K: a 5 MB/s ponía "5120K", cinco cifras
    que hay que dividir a mano. Ahora escala a M.
  * MINIGRÁFICA con el último medio minuto de cada métrica. Un número dice
    dónde estás; la forma dice si vas subiendo o si fue un pico y ya pasó.
  * RESPUESTA AL RATÓN en los atajos y en los botones del encabezado.
    Antes no pasaba nada al pasar por encima y no parecían pulsables.
"""

import time
import threading
import tkinter as tk

import psutil
import system_monitor as sysmon
from idiomas import t
import optimizer as opt
import preferences as prefs

COLOR_BG = "#14161c"
COLOR_CARD = "#1c1f29"
COLOR_CARD_ALT = "#22262f"
COLOR_OK = "#2ecc71"
COLOR_WARN = "#f1c40f"
COLOR_CRIT = "#e74c3c"
COLOR_ACCENT = "#3d8bfd"
COLOR_TXT = "#e8e8e8"
COLOR_TXT_DIM = "#8a8f99"

# Tonos que trajo el repaso estético.
COLOR_HOVER = "#2d3340"      # atajo bajo el cursor
COLOR_PISTA = "#2a2d38"      # canal por el que corre la barrita
COLOR_BORDE = "#262a33"      # separadores finísimos y el filo de la ventana

# Color clave para las esquinas redondeadas: Windows lo trata como "aquí no
# hay ventana". Tiene que ser un color que NO aparezca en ningún otro sitio
# del widget, o se abrirían agujeros donde no toca. Este magenta no está en
# la paleta ni por casualidad.
COLOR_CLAVE = "#ff00fe"
RADIO_VENTANA = 12


def _color(valor):
    """Color para un PORCENTAJE de uso (CPU, RAM, disco, GPU)."""
    if valor is None:
        return "#777777"
    if valor < 60:
        return COLOR_OK
    if valor < 85:
        return COLOR_WARN
    return COLOR_CRIT


def _color_temp(grados):
    """Color para una TEMPERATURA en °C.

    BUG corregido: la temperatura se pintaba con _color(), pensada para
    porcentajes. Con esos umbrales, un procesador a 62 °C —absolutamente
    normal, casi frío para un portátil— salía en ámbar como si algo fuera
    mal. Los umbrales de verdad para temperatura son otros: por debajo de
    65 va sobrado, hasta 80 va caliente pero bien, y de ahí para arriba sí
    conviene mirarlo."""
    if grados is None:
        return COLOR_TXT_DIM
    if grados < 65:
        return COLOR_OK
    if grados < 80:
        return COLOR_WARN
    return COLOR_CRIT


def _mezclar(color_a, color_b, proporcion):
    """Mezcla dos colores hex.

    El canvas de Tk no tiene transparencia, así que un relleno "al 30%" se
    consigue mezclando con el color del fondo — el mismo apaño que
    mezclar_color() en el panel principal. Si le llega algo que no es un
    color, devuelve el segundo en vez de reventar: esto se llama dentro del
    bucle de repintado y una excepción aquí dejaría el widget en blanco."""
    try:
        a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, IndexError, TypeError):
        return color_b
    p = max(0.0, min(1.0, proporcion))
    return "#" + "".join(f"{int(round(x + (y - x) * p)):02x}" for x, y in zip(a, b))


def _formato_red(kbps):
    """Velocidad de red en cinco caracteres como máximo.

    Antes se imprimía siempre en K, así que una descarga a 5 MB/s ponía
    "5120K": cinco cifras que hay que dividir a mano para saber qué son, y
    además ensanchaban la etiqueta y movían la barra entera."""
    if kbps is None or kbps < 0:
        return "--"
    if kbps < 1000:
        return f"{kbps:.0f}K"
    if kbps < 10240:
        return f"{kbps / 1024:.1f}M"
    return f"{kbps / 1024:.0f}M"


def _puntos_redondeados(x1, y1, x2, y2, radio):
    """Los vértices de un rectángulo de esquinas redondeadas, para
    pasárselos a create_polygon con smooth=True.

    El canvas de Tk no sabe dibujar un rectángulo redondeado, pero sí un
    polígono suavizado: repitiendo los puntos de los lados rectos y dejando
    sueltos los de las esquinas, el suavizado curva solo las esquinas. Es la
    misma clase de apaño que mezclar_color() — Tk no trae la primitiva, así
    que se construye."""
    radio = max(0, min(radio, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    return [
        x1 + radio, y1,  x2 - radio, y1,  x2 - radio, y1,
        x2, y1,          x2, y1 + radio,  x2, y1 + radio,
        x2, y2 - radio,  x2, y2 - radio,  x2, y2,
        x2 - radio, y2,  x2 - radio, y2,  x1 + radio, y2,
        x1 + radio, y2,  x1, y2,          x1, y2 - radio,
        x1, y2 - radio,  x1, y1 + radio,  x1, y1 + radio,
        x1, y1,          x1 + radio, y1,  x1 + radio, y1,
    ]


# main.py lo pone en False cuando Modo Ligero esta activo.
ANIMAR_BARRAS = True


class _MiniBarra(tk.Canvas):
    """La minigráfica de una métrica: el último medio minuto dibujado como
    área, y debajo una barrita con el valor actual.

    Antes solo estaba la barrita. Una barrita dice lo mismo que el número
    que tiene encima —dónde estás ahora— y nada más; con la historia detrás
    se ve si el 70% que estás leyendo viene subiendo o si fue un pico que ya
    pasó, que es la pregunta que uno se hace de verdad mirando un overlay
    mientras juega.

    El relleno de la barrita sigue deslizándose hasta el valor nuevo en vez
    de saltar: misma interpolacion con ease-out que el medidor de Inicio,
    pero mas corta porque la barra es chica y un recorrido largo se
    sentiria lento."""

    DURACION_MS = 260
    PASO_MS = 20
    MUESTRAS = 40          # a un tick por segundo, algo más de medio minuto
    ALTO_BARRA = 4

    def __init__(self, master, ancho=70, alto=26, **kwargs):
        super().__init__(master, width=ancho, height=alto, bg=COLOR_CARD,
                          highlightthickness=0, **kwargs)
        self.ancho = ancho
        self.alto = alto
        self._valor_mostrado = 0.0
        self._historia = []
        self._anim_id = None
        self.set_valor(0)

    def _cancelar_animacion(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def set_valor(self, porcentaje, color=None):
        destino = max(0.0, min(100.0, float(porcentaje or 0)))
        # La historia se apunta con el valor de DESTINO, no con los pasos
        # intermedios de la animacion: si no, la grafica dibujaria la
        # animacion en lugar de lo que midio el sistema.
        self._historia.append(destino)
        del self._historia[:-self.MUESTRAS]
        self._cancelar_animacion()

        if not ANIMAR_BARRAS or abs(destino - self._valor_mostrado) < 0.5:
            self._valor_mostrado = destino
            self._dibujar(destino, color)
            return

        inicio = self._valor_mostrado
        pasos = max(1, self.DURACION_MS // self.PASO_MS)

        def paso(i):
            self._anim_id = None
            if not self.winfo_exists():
                return
            avance = i / pasos
            suave = 1 - (1 - avance) ** 3
            valor = inicio + (destino - inicio) * suave
            self._valor_mostrado = valor
            self._dibujar(valor, color)
            if i < pasos:
                self._anim_id = self.after(self.PASO_MS, paso, i + 1)

        paso(1)

    def _dibujar(self, porcentaje, color=None):
        self.delete("all")
        color = color or _color(porcentaje)
        alto_grafica = max(2, self.alto - self.ALTO_BARRA - 3)

        # ---- El área de historia ----
        if len(self._historia) >= 2:
            paso_x = self.ancho / max(1, len(self._historia) - 1)
            puntos = []
            for i, valor in enumerate(self._historia):
                x = i * paso_x
                y = alto_grafica - (valor / 100.0) * (alto_grafica - 1)
                puntos.extend((x, y))
            # Se cierra hacia abajo para poder rellenarlo: una línea de 1 px
            # en 20 px de alto no se ve a esa escala; el área sí.
            relleno = puntos + [self.ancho, alto_grafica, 0.0, alto_grafica]
            self.create_polygon(relleno, fill=_mezclar(color, COLOR_CARD, 0.62),
                                outline="")
            self.create_line(puntos, fill=color, width=1)
        else:
            self.create_line(0, alto_grafica - 1, self.ancho, alto_grafica - 1,
                             fill=COLOR_PISTA)

        # ---- La barrita del valor actual ----
        arriba = self.alto - self.ALTO_BARRA
        self.create_polygon(
            _puntos_redondeados(0, arriba, self.ancho, self.alto, self.ALTO_BARRA / 2),
            fill=COLOR_PISTA, outline="", smooth=True)
        ancho_lleno = self.ancho * (porcentaje / 100)
        if ancho_lleno > self.ALTO_BARRA:
            self.create_polygon(
                _puntos_redondeados(0, arriba, ancho_lleno, self.alto,
                                    self.ALTO_BARRA / 2),
                fill=color, outline="", smooth=True)
        elif ancho_lleno > 0:
            # Por debajo del diámetro no cabe una punta redonda: se pinta
            # recto, que se ve mejor que no pintar nada.
            self.create_rectangle(0, arriba, ancho_lleno, self.alto,
                                  fill=color, outline="")


class PerformanceWidget(tk.Toplevel):
    def __init__(self, master, on_cerrar=None):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        self.on_cerrar = on_cerrar
        self._expandido = False
        self._activo = True
        self._visible = True
        self._tooltips = []
        self._gpu_cache = {"nombre": "N/D", "porcentaje": None}
        self._cpu_temp_cache = None
        self._net_prev = psutil.net_io_counters()
        self._net_prev_time = time.time()
        self._botones_atajos = {}
        self._barras = {}
        self._fondo = None

        self._preparar_ventana_redondeada()
        self._construir_ui()
        self._posicionar_esquina()
        self._bind_arrastre()
        self._sincronizar_boton_modo_juego()

        self._actualizar_loop()
        threading.Thread(target=self._loop_gpu, daemon=True).start()

    # ---------- Forma de la ventana ----------
    def _preparar_ventana_redondeada(self):
        """Esquinas redondeadas en una ventana sin barra de título.

        Windows no redondea una ventana overrideredirect: es un rectángulo
        duro, y encima del escritorio o de un juego se notaba como un
        recorte de cartón pegado a la pantalla.

        El truco es "-transparentcolor": Windows deja pasar todo lo que esté
        pintado de ese color exacto, como si ahí no hubiera ventana. Así que
        el fondo de la ventana se pone de ese color y encima se dibuja, en
        un lienzo, un rectángulo redondeado del color de verdad. Lo que
        queda fuera de la curva —las cuatro esquinas— es color clave, o sea
        nada.

        Si el sistema no lo admite se vuelve al rectángulo de siempre: es un
        detalle de presentación y no vale arriesgar que el widget no abra
        por él.
        """
        self._redondeada = False
        try:
            self.configure(bg=COLOR_CLAVE)
            self.wm_attributes("-transparentcolor", COLOR_CLAVE)
            self._redondeada = True
        except Exception:
            self.configure(bg=COLOR_BG)
        # La transparencia general se pide DESPUÉS del color clave: las dos
        # se apoyan en la misma ventana en capas de Windows, y pedirlas al
        # revés deja sin efecto a la primera.
        try:
            self.attributes("-alpha", 0.96)
        except Exception:
            pass

        if not self._redondeada:
            return

        self._fondo = tk.Canvas(self, bg=COLOR_CLAVE, highlightthickness=0)
        self._fondo.place(x=0, y=0, relwidth=1, relheight=1)
        # place() no contribuye al tamaño pedido por la ventana, así que el
        # lienzo llena lo que midan las tarjetas sin estirarla.
        #
        # Y hay que bajarlo por debajo de lo que se empaquete encima. Ojo con
        # el metodo: Canvas.lower() NO es el de apilar ventanas, es
        # tag_lower(), que baja un DIBUJO dentro del lienzo y pide el nombre
        # de ese dibujo — llamarlo sin argumentos revienta con "wrong # args"
        # y el widget no abre. El de apilar es el de Misc.
        tk.Misc.lower(self._fondo)
        self.bind("<Configure>", self._repintar_fondo, add="+")

    def _repintar_fondo(self, event=None):
        if self._fondo is None or not self._fondo.winfo_exists():
            return
        ancho, alto = self.winfo_width(), self.winfo_height()
        if ancho <= 1 or alto <= 1:
            return
        self._fondo.delete("all")
        self._fondo.create_polygon(
            _puntos_redondeados(0, 0, ancho - 1, alto - 1, RADIO_VENTANA),
            fill=COLOR_BG, outline=COLOR_BORDE, smooth=True)

    # ---------- UI ----------
    def _tarjeta(self, master, titulo=None):
        """Contenedor tipo 'card': fondo un tono más claro que la ventana,
        con esquinas rectas pero espaciado generoso — el efecto de tarjeta
        separada viene del contraste de color, no de bordes redondeados
        (tkinter plano no los soporta sin dependencias extra).

        El título lleva delante una marca del color de acento. Sin ella los
        tres títulos eran tres líneas grises iguales y las tarjetas se leían
        como una sola lista larga."""
        tarjeta = tk.Frame(master, bg=COLOR_CARD)
        tarjeta.pack(fill="x", padx=10, pady=(0, 6))
        if titulo:
            fila = tk.Frame(tarjeta, bg=COLOR_CARD)
            fila.pack(fill="x", padx=10, pady=(9, 3))
            tk.Frame(fila, bg=COLOR_ACCENT, width=3, height=10).pack(
                side="left", padx=(0, 6))
            tk.Label(fila, text=titulo, bg=COLOR_CARD, fg=COLOR_TXT_DIM,
                      font=("Segoe UI", 8, "bold")).pack(side="left")
        return tarjeta

    def _hover(self, widget, normal, encima):
        """Cambia el fondo al pasar el ratón. Los atajos eran etiquetas
        muertas: nada indicaba que se pudieran pulsar."""
        widget.bind("<Enter>", lambda e: widget.configure(bg=encima), add="+")
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal), add="+")

    def _construir_ui(self):
        # ---- Encabezado: título + arrastre + expandir + cerrar ----
        self.frame_header = tk.Frame(self, bg=COLOR_BG)
        self.frame_header.pack(fill="x", padx=14, pady=(9, 4))
        tk.Label(self.frame_header, text="⚙", bg=COLOR_BG, fg=COLOR_ACCENT,
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))
        tk.Label(self.frame_header, text="TechClean", bg=COLOR_BG, fg=COLOR_TXT_DIM,
                  font=("Segoe UI", 8, "bold")).pack(side="left")
        self.btn_cerrar = tk.Label(self.frame_header, text="✕", bg=COLOR_BG, fg="gray50",
                                    font=("Segoe UI", 9), cursor="hand2", padx=4)
        self.btn_cerrar.pack(side="right")
        self.btn_cerrar.bind("<Button-1>", lambda e: self._cerrar_desde_boton())
        # El de cerrar se pone rojo al apuntarlo: de los dos botones del
        # encabezado es el único que hace algo que hay que volver a deshacer,
        # y conviene que no se confunda con el de plegar.
        self.btn_cerrar.bind("<Enter>", lambda e: self.btn_cerrar.configure(fg=COLOR_CRIT), add="+")
        self.btn_cerrar.bind("<Leave>", lambda e: self.btn_cerrar.configure(fg="gray50"), add="+")
        self.btn_expandir = tk.Label(self.frame_header, text="▾", bg=COLOR_BG, fg=COLOR_TXT,
                                      font=("Segoe UI", 10), cursor="hand2", padx=4)
        self.btn_expandir.pack(side="right", padx=(0, 6))
        self.btn_expandir.bind("<Button-1>", lambda e: self._toggle_expandir())
        self.btn_expandir.bind("<Enter>", lambda e: self.btn_expandir.configure(fg=COLOR_ACCENT), add="+")
        self.btn_expandir.bind("<Leave>", lambda e: self.btn_expandir.configure(fg=COLOR_TXT), add="+")

        # ---- Barra compacta (siempre visible) ----
        self.frame_compacto = tk.Frame(self, bg=COLOR_CARD)
        self.frame_compacto.pack(fill="x", padx=10, pady=(0, 6))
        metricas = prefs.cargar().get("widget_metricas") or ["cpu", "ram", "red", "gpu"]
        # El orden en que se crean es el orden en que salen (side="left").
        # Va CPU, RAM, GPU para que coincida con la tarjeta de Rendimiento:
        # antes la GPU quedaba en medio de las dos que uno mira juntas.
        self.lbl_cpu = self._crear_metric_label(self.frame_compacto) if "cpu" in metricas else None
        self.lbl_ram = self._crear_metric_label(self.frame_compacto) if "ram" in metricas else None
        self.lbl_gpu = self._crear_metric_label(self.frame_compacto) if "gpu" in metricas else None
        if "red" in metricas:
            # Separador antes de la red: la red no es un porcentaje como las
            # otras tres, y pegada a ellas se leía como si lo fuera.
            tk.Frame(self.frame_compacto, bg=COLOR_BORDE, width=1).pack(
                side="left", fill="y", pady=6, padx=4)
        self.lbl_net_down = (self._crear_metric_label(self.frame_compacto, ancho=6)
                             if "red" in metricas else None)
        self.lbl_net_up = (self._crear_metric_label(self.frame_compacto, ancho=6)
                           if "red" in metricas else None)

        # ---- Panel expandido: tarjetas de Rendimiento / Atajos / Sistema ----
        self.frame_expandido = tk.Frame(self, bg=COLOR_BG)

        tarjeta_rend = self._tarjeta(self.frame_expandido, t("wid_card_rendimiento"))
        fila_rend = tk.Frame(tarjeta_rend, bg=COLOR_CARD)
        fila_rend.pack(fill="x", padx=10, pady=(0, 10))
        self._metricas_grandes = {}
        for clave, etiqueta in [("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU")]:
            col = tk.Frame(fila_rend, bg=COLOR_CARD)
            col.pack(side="left", padx=(0, 14))
            tk.Label(col, text=etiqueta, bg=COLOR_CARD, fg=COLOR_TXT_DIM,
                      font=("Segoe UI", 8)).pack(anchor="w")
            # Ancho fijo y dígitos de ancho fijo: si no, al pasar de 9% a 10%
            # el número ensancha su columna y las tres se recolocan.
            lbl_num = tk.Label(col, text="--%", bg=COLOR_CARD, fg=COLOR_TXT,
                                 font=("Consolas", 15, "bold"), width=5, anchor="w")
            lbl_num.pack(anchor="w")
            barra = _MiniBarra(col, ancho=76, alto=26)
            barra.pack(anchor="w", pady=(3, 0))
            self._metricas_grandes[clave] = lbl_num
            self._barras[clave] = barra

        # ---- Atajos: cuadrícula de íconos, estilo panel de utilidades ----
        tarjeta_atajos = self._tarjeta(self.frame_expandido, t("wid_card_atajos"))
        fila_atajos = tk.Frame(tarjeta_atajos, bg=COLOR_CARD)
        fila_atajos.pack(padx=10, pady=(0, 10), anchor="w")
        # Cada atajo lleva una CLAVE interna ademas del tooltip traducido: el
        # boton de Modo Juego se guarda aparte para poder pintarlo despues, y
        # antes eso se decidia comparando el tooltip contra el literal
        # "Modo Juego" — al traducirlo, esa comparacion habria fallado y el
        # boton nunca se habria coloreado al activar el modo.
        atajos = [
            ("🧹", "ram", t("wid_atajo_ram"), self._liberar_ram_manual),
            ("🗑", "papelera", t("wid_atajo_papelera"), self._vaciar_papelera_manual),
            ("🎮", "modo_juego", t("wid_atajo_modo_juego"), self._toggle_modo_juego_manual),
            ("🎯", "fps", t("wid_atajo_fps"), self._abrir_fps_manual),
            ("🖥", "panel", t("wid_atajo_panel"), self._abrir_panel_completo),
        ]
        for icono, clave_atajo, tooltip, accion in atajos:
            # "Segoe UI Emoji" y no "Segoe UI": con la fuente normal Windows
            # dibuja estos simbolos en blanco y negro y quedaban como un
            # contorno lavado. Con la de emoji salen en color.
            btn = tk.Label(fila_atajos, text=icono, bg=COLOR_CARD_ALT, fg=COLOR_TXT,
                            font=("Segoe UI Emoji", 12), cursor="hand2", width=3, height=1)
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, fn=accion: fn())
            self._crear_tooltip(btn, tooltip)
            if clave_atajo == "modo_juego":
                # El de Modo Juego no lleva hover a proposito: su fondo YA
                # dice si el modo esta encendido, y pintarlo al pasar el
                # raton haria dudar de si esta activo o solo apuntado.
                self._botones_atajos["modo_juego"] = btn
            else:
                self._hover(btn, COLOR_CARD_ALT, COLOR_HOVER)

        # ---- Sistema: filas con su propio icono + texto ----
        tarjeta_sistema = self._tarjeta(self.frame_expandido, t("wid_card_sistema"))
        self.filas_sistema = {}
        # Antes las cuatro filas empezaban con el mismo punto: para saber
        # cual era cual habia que leerlas enteras. Cada una con su icono se
        # distingue de un vistazo, que es de lo que va un overlay.
        iconos = {"disco": "▤", "bateria": "▮", "temp": "▲", "uptime": "◷"}
        for clave in ("disco", "bateria", "temp", "uptime"):
            fila = tk.Frame(tarjeta_sistema, bg=COLOR_CARD)
            fila.pack(fill="x", padx=10, pady=2)
            punto = tk.Label(fila, text=iconos[clave], bg=COLOR_CARD, fg=COLOR_TXT_DIM,
                              font=("Segoe UI", 8), width=2)
            punto.pack(side="left")
            texto = tk.Label(fila, text="--", bg=COLOR_CARD, fg=COLOR_TXT,
                               font=("Segoe UI", 9), anchor="w")
            texto.pack(side="left", padx=(2, 0))
            self.filas_sistema[clave] = (punto, texto)
        tk.Frame(tarjeta_sistema, bg=COLOR_CARD, height=8).pack()  # respiro final

    def _crear_tooltip(self, widget, texto):
        """Tooltip simple (sin dependencias): aparece al pasar el mouse encima."""
        globo = {"win": None}
        # Se apuntan todos para poder cerrarlos de golpe: un tooltip es una
        # ventana APARTE, así que si el widget se ocultaba con uno abierto,
        # el globito negro se quedaba flotando solo en el escritorio, sin
        # nada a lo que pertenecer y sin forma de quitarlo.
        self._tooltips.append(globo)

        def mostrar(_e):
            if globo["win"] is not None or not self._visible:
                return
            win = tk.Toplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            tk.Label(win, text=texto, bg="#0b0d12", fg=COLOR_TXT,
                     font=("Segoe UI", 8), padx=7, pady=3,
                     highlightbackground=COLOR_BORDE, highlightthickness=1).pack()
            win.update_idletasks()
            # Se coloca debajo del atajo, pero sin salirse por la derecha:
            # el widget vive pegado al borde de la pantalla y el globo de
            # los ultimos atajos se cortaba.
            x = widget.winfo_rootx()
            x = min(x, widget.winfo_screenwidth() - win.winfo_width() - 6)
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            win.geometry(f"+{max(0, x)}+{y}")
            globo["win"] = win

        def ocultar(_e=None):
            if globo["win"] is not None:
                globo["win"].destroy()
                globo["win"] = None

        widget.bind("<Enter>", mostrar, add="+")
        widget.bind("<Leave>", ocultar, add="+")
        # Se guardan las dos funciones junto al globo para que el banco de
        # pruebas pueda ejercitarlas directamente: los eventos <Enter> y
        # <Leave> los genera el gestor de ventanas y no se pueden simular
        # de forma fiable en una ventana que está fuera de la pantalla, que
        # es donde corren las pruebas para no molestar al usuario.
        globo["mostrar"] = mostrar
        globo["ocultar"] = ocultar

    def _crear_metric_label(self, parent, ancho=8):
        """Una métrica de la barra compacta.

        BUG corregido — la barra temblaba. Sin `width`, una etiqueta de Tk
        se mide por su texto: al pasar de "CPU 9%" a "CPU 10%" crecía un
        carácter y empujaba a todas las de su derecha, así que la barra
        entera se recolocaba una o dos veces por segundo mientras la
        mirabas. Con ancho fijo en caracteres y una tipografía donde todos
        los dígitos miden lo mismo, el texto cambia y nada se mueve."""
        lbl = tk.Label(parent, text="--", bg=COLOR_CARD, fg=COLOR_TXT,
                        font=("Consolas", 10, "bold"), padx=5, pady=7,
                        width=ancho, anchor="w")
        lbl.pack(side="left")
        return lbl

    def _toggle_expandir(self):
        self._expandido = not self._expandido
        if self._expandido:
            self.frame_expandido.pack(fill="x", pady=(0, 6))
            self.btn_expandir.configure(text="▴")
        else:
            self.frame_expandido.pack_forget()
            self.btn_expandir.configure(text="▾")
        # La ventana cambia de alto: el fondo redondeado hay que redibujarlo
        # con la medida nueva o la curva de abajo se queda donde estaba.
        self.after_idle(self._repintar_fondo)

    def _liberar_ram_manual(self):
        threading.Thread(target=opt.trim_process_memory, daemon=True).start()

    def _abrir_fps_manual(self):
        threading.Thread(target=opt.abrir_contador_fps_windows, daemon=True).start()

    def _vaciar_papelera_manual(self):
        threading.Thread(target=opt.empty_recycle_bin, daemon=True).start()

    def _toggle_modo_juego_manual(self):
        """Usa la misma lógica de Modo Juego del panel principal (self.master
        es la instancia de TechCleanApp) — no duplica el comportamiento."""
        try:
            self.master._toggle_autopilot()
            activo = self.master.autopilot.activo
            btn = self._botones_atajos.get("modo_juego")
            if btn is not None:
                btn.configure(bg=COLOR_OK if activo else COLOR_CARD_ALT)
        except Exception:
            pass

    def _abrir_panel_completo(self):
        try:
            self.master._mostrar_ventana()
        except Exception:
            pass

    def _sincronizar_boton_modo_juego(self):
        try:
            activo = self.master.autopilot.activo
            btn = self._botones_atajos.get("modo_juego")
            if btn is not None:
                btn.configure(bg=COLOR_OK if activo else COLOR_CARD_ALT)
        except Exception:
            pass

    # ---------- Posición / arrastre ----------
    def _posicionar_esquina(self):
        self.update_idletasks()
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        pos_guardada = prefs.cargar().get("widget_pos")
        if (isinstance(pos_guardada, list) and len(pos_guardada) == 2
                and 0 <= pos_guardada[0] < ancho_pantalla and 0 <= pos_guardada[1] < alto_pantalla):
            self.geometry(f"+{pos_guardada[0]}+{pos_guardada[1]}")
        else:
            self.geometry(f"+{max(0, ancho_pantalla - 380)}+10")

    def _bind_arrastre(self):
        self._drag_x = 0
        self._drag_y = 0
        self._pos_al_agarrar = None
        for widget in (self, self.frame_header, self.frame_compacto):
            widget.bind("<ButtonPress-1>", self._iniciar_arrastre)
            widget.bind("<B1-Motion>", self._arrastrar)
            widget.bind("<ButtonRelease-1>", self._terminar_arrastre)

    def _iniciar_arrastre(self, event):
        """BUG corregido — el salto al arrastrar.

        Se guardaba `event.x`, que es la posición del clic DENTRO del widget
        que recibió el evento. Y en Tk, una vinculación puesta sobre la
        ventana raíz salta con los eventos de todos sus hijos (el toplevel
        está en los bindtags de cada descendiente). Así que al agarrar el
        widget por cualquier sitio que no fuera el borde —un botón de
        atajo, una etiqueta, la tarjeta de Sistema— ese `event.x` valía
        unos pocos píxeles en vez de los 300 reales, y la ventana pegaba un
        brinco hasta colocar su esquina junto al cursor.

        Lo que hace falta es el desfase respecto a la VENTANA, y eso se
        calcula igual venga el evento de donde venga."""
        self._drag_x = self.winfo_pointerx() - self.winfo_x()
        self._drag_y = self.winfo_pointery() - self.winfo_y()
        self._pos_al_agarrar = (self.winfo_x(), self.winfo_y())

    def _arrastrar(self, event):
        x = self.winfo_pointerx() - self._drag_x
        y = self.winfo_pointery() - self._drag_y
        # Sin límites se podía empujar el widget fuera de la pantalla, y como
        # no tiene barra de título de Windows (overrideredirect) no había
        # forma de traerlo de vuelta: solo cerrarlo y volver a abrirlo. Se
        # deja siempre un trozo agarrable a la vista.
        margen = 60
        max_x = self.winfo_screenwidth() - margen
        max_y = self.winfo_screenheight() - margen
        x = max(margen - self.winfo_width(), min(x, max_x))
        y = max(0, min(y, max_y))
        self.geometry(f"+{int(x)}+{int(y)}")

    def _terminar_arrastre(self, event):
        """Guarda la posición actual para la próxima vez que se abra el widget.

        Solo si de verdad se movió: antes se escribía preferencias.json en
        CADA clic sobre el widget, aunque no se hubiera arrastrado nada."""
        try:
            actual = (self.winfo_x(), self.winfo_y())
            if actual == self._pos_al_agarrar:
                return
            self._pos_al_agarrar = actual
            prefs.guardar({"widget_pos": [actual[0], actual[1]]})
        except Exception:
            pass

    # ---------- Actualización ----------
    def _loop_gpu(self):
        """Datos 'caros' de consultar (GPU y temperatura de CPU): se piden
        cada 4s en este hilo aparte (8s con Modo Ligero), no en el tick de
        1s, para no afectar el rendimiento mientras juegas."""
        while self._activo:
            # Estas dos son las consultas CARAS del widget (WMI, nvidia-smi):
            # hacerlas con el widget oculto era gasto puro. El usuario cerró
            # la barra justamente para que dejara de molestar.
            if self._visible:
                try:
                    self._gpu_cache = sysmon.get_gpu_info()
                    self._cpu_temp_cache = sysmon.get_cpu_temperature()
                except Exception:
                    pass
            segundos = 8 if prefs.cargar().get("modo_ligero") else 4
            time.sleep(segundos)

    def _actualizar_loop(self):
        if not self._activo:
            return
        if not self._visible:
            # Oculto no hay nada que pintar. El bucle sigue vivo, pero
            # despacio, solo para poder retomar el ritmo cuando vuelva.
            self.after(2000, self._actualizar_loop)
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            gpu = self._gpu_cache.get("porcentaje")

            ahora = time.time()
            net_ahora = psutil.net_io_counters()
            delta_t = max(0.001, ahora - self._net_prev_time)
            subida_kbps = (net_ahora.bytes_sent - self._net_prev.bytes_sent) / 1024 / delta_t
            bajada_kbps = (net_ahora.bytes_recv - self._net_prev.bytes_recv) / 1024 / delta_t
            self._net_prev = net_ahora
            self._net_prev_time = ahora

            if self.lbl_cpu:
                self.lbl_cpu.configure(text=t("wid_cpu", pct=f"{cpu:.0f}"), fg=_color(cpu))
            if self.lbl_ram:
                self.lbl_ram.configure(text=t("wid_ram", pct=f"{ram:.0f}"), fg=_color(ram))
            gpu_txt = t("wid_gpu", pct=f"{gpu:.0f}") if gpu is not None else t("wid_gpu_nd")
            if self.lbl_gpu:
                self.lbl_gpu.configure(text=gpu_txt, fg=_color(gpu))
            if self.lbl_net_down:
                self.lbl_net_down.configure(text="↓" + _formato_red(bajada_kbps))
            if self.lbl_net_up:
                self.lbl_net_up.configure(text="↑" + _formato_red(subida_kbps))

            if self._expandido:
                # Tarjeta Rendimiento: números grandes + minigráficas
                for clave, valor in (("cpu", cpu), ("ram", ram), ("gpu", gpu)):
                    lbl = self._metricas_grandes.get(clave)
                    barra = self._barras.get(clave)
                    if lbl is not None:
                        lbl.configure(text=(f"{valor:.0f}%" if valor is not None else "N/D"),
                                      fg=_color(valor))
                    if barra is not None:
                        barra.set_valor(valor)

                # Tarjeta Sistema
                disco = sysmon.get_disk_info()
                bateria = psutil.sensors_battery()
                if bateria:
                    bateria_txt = (t("wid_bateria", pct=f"{bateria.percent:.0f}")
                                   + (t("wid_bateria_cargando") if bateria.power_plugged else ""))
                    color_bateria = COLOR_OK if (bateria.power_plugged or bateria.percent > 30) else COLOR_WARN
                else:
                    bateria_txt = t("wid_bateria_escritorio")
                    color_bateria = COLOR_TXT_DIM

                temp_cpu_txt = (t("wid_temp", temp=f"{self._cpu_temp_cache:.0f}")
                                if self._cpu_temp_cache is not None else t("wid_temp_nd"))
                color_temp = _color_temp(self._cpu_temp_cache)

                uptime = sysmon.get_uptime_seconds()
                horas, minutos = int(uptime // 3600), int((uptime % 3600) // 60)

                filas_valores = {
                    "disco": (t("wid_disco", pct=f'{disco["porcentaje"]:.0f}',
                                libres=disco["libre_gb"]),
                              _color(disco["porcentaje"])),
                    "bateria": (bateria_txt, color_bateria),
                    "temp": (temp_cpu_txt, color_temp),
                    "uptime": (t("wid_uptime", horas=horas, minutos=minutos), COLOR_TXT_DIM),
                }
                for clave, (texto, color) in filas_valores.items():
                    punto, lbl_texto = self.filas_sistema[clave]
                    punto.configure(fg=color)
                    lbl_texto.configure(text=texto)
        except Exception:
            pass

        # Con Modo Ligero, hasta el tick "barato" de 1s se espacia a 2s —
        # sigue siendo psutil (liviano), pero un poco menos seguido.
        milisegundos = 2000 if prefs.cargar().get("modo_ligero") else 1000
        self.after(milisegundos, self._actualizar_loop)

    def _cerrar_tooltips(self):
        for globo in self._tooltips:
            win = globo.get("win")
            if win is not None:
                try:
                    win.destroy()
                except Exception:
                    pass
                globo["win"] = None

    def ocultar(self):
        self._visible = False
        self._cerrar_tooltips()
        self.withdraw()

    def _cerrar_desde_boton(self):
        """Cerrar con el botón ✕ del propio widget: además de ocultarlo,
        avisa a la app principal (si dio un callback) para que el switch
        de 'Widget flotante' en Segundo Plano se ponga en OFF también —
        antes quedaban desincronizados."""
        self.ocultar()
        if self.on_cerrar is not None:
            try:
                self.on_cerrar()
            except Exception:
                pass

    def mostrar(self):
        # Los contadores de red se ponen a cero al volver: si no, el primer
        # tick dividiría todo el tráfico acumulado mientras el widget estuvo
        # oculto entre un segundo, y saldría un pico absurdo de varios miles
        # de KB/s que no ocurrió nunca.
        self._net_prev = psutil.net_io_counters()
        self._net_prev_time = time.time()
        self._visible = True
        self.deiconify()

    def destruir(self):
        self._activo = False
        self._cerrar_tooltips()
        try:
            self.destroy()
        except Exception:
            pass
