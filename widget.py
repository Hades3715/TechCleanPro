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


# main.py lo pone en False cuando Modo Ligero esta activo.
ANIMAR_BARRAS = True


class _MiniBarra(tk.Canvas):
    """Barrita de progreso horizontal simple, sin dependencias — para que
    cada métrica de la tarjeta de Rendimiento se vea "viva", no solo texto.

    El relleno se desliza hasta el valor nuevo en vez de saltar: misma
    interpolacion con ease-out que el medidor de Inicio, pero mas corta
    porque la barra es chica y un recorrido largo se sentiria lento."""

    DURACION_MS = 260
    PASO_MS = 20

    def __init__(self, master, ancho=70, alto=6, **kwargs):
        super().__init__(master, width=ancho, height=alto, bg=COLOR_CARD,
                          highlightthickness=0, **kwargs)
        self.ancho = ancho
        self.alto = alto
        self._valor_mostrado = 0.0
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
        self.create_rectangle(0, 0, self.ancho, self.alto, fill="#2a2d38", outline="")
        ancho_lleno = self.ancho * (porcentaje / 100)
        if ancho_lleno > 0:
            self.create_rectangle(0, 0, ancho_lleno, self.alto, fill=color, outline="")


class PerformanceWidget(tk.Toplevel):
    def __init__(self, master, on_cerrar=None):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.96)
        except Exception:
            pass
        self.configure(bg=COLOR_BG)

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

        self._construir_ui()
        self._posicionar_esquina()
        self._bind_arrastre()
        self._sincronizar_boton_modo_juego()

        self._actualizar_loop()
        threading.Thread(target=self._loop_gpu, daemon=True).start()

    # ---------- UI ----------
    def _tarjeta(self, master, titulo=None):
        """Contenedor tipo 'card': fondo un tono más claro que la ventana,
        con esquinas rectas pero espaciado generoso — el efecto de tarjeta
        separada viene del contraste de color, no de bordes redondeados
        (tkinter plano no los soporta sin dependencias extra)."""
        tarjeta = tk.Frame(master, bg=COLOR_CARD)
        tarjeta.pack(fill="x", padx=8, pady=(0, 6))
        if titulo:
            tk.Label(tarjeta, text=titulo, bg=COLOR_CARD, fg=COLOR_TXT_DIM,
                      font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        return tarjeta

    def _construir_ui(self):
        # ---- Encabezado: título + arrastre + expandir + cerrar ----
        self.frame_header = tk.Frame(self, bg=COLOR_BG)
        self.frame_header.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(self.frame_header, text="⚙ TechClean Pro", bg=COLOR_BG, fg=COLOR_TXT_DIM,
                  font=("Segoe UI", 8, "bold")).pack(side="left")
        self.btn_cerrar = tk.Label(self.frame_header, text="✕", bg=COLOR_BG, fg="gray50",
                                    font=("Segoe UI", 9), cursor="hand2")
        self.btn_cerrar.pack(side="right")
        self.btn_cerrar.bind("<Button-1>", lambda e: self._cerrar_desde_boton())
        self.btn_expandir = tk.Label(self.frame_header, text="▾", bg=COLOR_BG, fg=COLOR_TXT,
                                      font=("Segoe UI", 10), cursor="hand2")
        self.btn_expandir.pack(side="right", padx=(0, 8))
        self.btn_expandir.bind("<Button-1>", lambda e: self._toggle_expandir())

        # ---- Barra compacta (siempre visible) ----
        self.frame_compacto = tk.Frame(self, bg=COLOR_CARD)
        self.frame_compacto.pack(fill="x", padx=8, pady=(0, 6))
        metricas = prefs.cargar().get("widget_metricas") or ["cpu", "ram", "red", "gpu"]
        self.lbl_cpu = self._crear_metric_label(self.frame_compacto) if "cpu" in metricas else None
        self.lbl_gpu = self._crear_metric_label(self.frame_compacto) if "gpu" in metricas else None
        self.lbl_ram = self._crear_metric_label(self.frame_compacto) if "ram" in metricas else None
        self.lbl_net_up = self._crear_metric_label(self.frame_compacto) if "red" in metricas else None
        self.lbl_net_down = self._crear_metric_label(self.frame_compacto) if "red" in metricas else None

        # ---- Panel expandido: tarjetas de Rendimiento / Atajos / Sistema ----
        self.frame_expandido = tk.Frame(self, bg=COLOR_BG)

        tarjeta_rend = self._tarjeta(self.frame_expandido, t("wid_card_rendimiento"))
        fila_rend = tk.Frame(tarjeta_rend, bg=COLOR_CARD)
        fila_rend.pack(fill="x", padx=10, pady=(0, 10))
        self._metricas_grandes = {}
        for clave, etiqueta in [("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU")]:
            col = tk.Frame(fila_rend, bg=COLOR_CARD)
            col.pack(side="left", padx=(0, 16))
            tk.Label(col, text=etiqueta, bg=COLOR_CARD, fg=COLOR_TXT_DIM,
                      font=("Segoe UI", 8)).pack(anchor="w")
            lbl_num = tk.Label(col, text="--%", bg=COLOR_CARD, fg=COLOR_TXT,
                                 font=("Segoe UI", 15, "bold"))
            lbl_num.pack(anchor="w")
            barra = _MiniBarra(col, ancho=64)
            barra.pack(anchor="w", pady=(2, 0))
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
            btn = tk.Label(fila_atajos, text=icono, bg=COLOR_CARD_ALT, fg=COLOR_TXT,
                            font=("Segoe UI", 13), cursor="hand2", width=3, height=1)
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, fn=accion: fn())
            self._crear_tooltip(btn, tooltip)
            if clave_atajo == "modo_juego":
                self._botones_atajos["modo_juego"] = btn

        # ---- Sistema: filas con puntito de color + texto ----
        tarjeta_sistema = self._tarjeta(self.frame_expandido, t("wid_card_sistema"))
        self.filas_sistema = {}
        for clave in ("disco", "bateria", "temp", "uptime"):
            fila = tk.Frame(tarjeta_sistema, bg=COLOR_CARD)
            fila.pack(fill="x", padx=10, pady=2)
            punto = tk.Label(fila, text="●", bg=COLOR_CARD, fg=COLOR_TXT_DIM, font=("Segoe UI", 8))
            punto.pack(side="left")
            texto = tk.Label(fila, text="--", bg=COLOR_CARD, fg=COLOR_TXT,
                               font=("Segoe UI", 9), anchor="w")
            texto.pack(side="left", padx=(4, 0))
            self.filas_sistema[clave] = (punto, texto)
        tk.Frame(tarjeta_sistema, bg=COLOR_CARD, height=6).pack()  # respiro final

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
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            win = tk.Toplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            tk.Label(win, text=texto, bg="#000000", fg="white", font=("Segoe UI", 8),
                     padx=6, pady=2).pack()
            win.geometry(f"+{x}+{y}")
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

    def _crear_metric_label(self, parent):
        lbl = tk.Label(parent, text="--", bg=COLOR_CARD, fg=COLOR_TXT,
                        font=("Segoe UI", 10, "bold"), padx=6, pady=6)
        lbl.pack(side="left")
        return lbl

    def _toggle_expandir(self):
        self._expandido = not self._expandido
        if self._expandido:
            self.frame_expandido.pack(fill="x")
            self.btn_expandir.configure(text="▴")
        else:
            self.frame_expandido.pack_forget()
            self.btn_expandir.configure(text="▾")

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
            if self.lbl_net_up:
                self.lbl_net_up.configure(text=f"↑{subida_kbps:.0f}K")
            if self.lbl_net_down:
                self.lbl_net_down.configure(text=f"↓{bajada_kbps:.0f}K")

            if self._expandido:
                # Tarjeta Rendimiento: números grandes + barritas
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
