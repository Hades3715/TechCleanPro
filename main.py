"""
main.py
TechClean Pro — Panel de Optimización y Diagnóstico de Sistema
Aplicación de escritorio para Windows con monitoreo real de hardware,
optimización de RAM/disco, limpieza de privacidad, consola de desarrollador,
reporte transparente de sesión, widget flotante y modo automático en
segundo plano (bandeja del sistema).

Ejecutar:  python main.py
Requiere:  pip install -r requirements.txt
"""

import os
import sys
import time
import json
import socket
import getpass
import platform
import threading
import webbrowser
from datetime import datetime

import customtkinter as ctk
import tkinter as tk
import psutil

import system_monitor as sysmon
import optimizer as opt
import privacy as priv
import idiomas
from idiomas import t
import report as rep
import widget as widget_mod
import tray as tray_mod
import autopilot as autopilot_mod
import preferences as prefs

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_OK = "#2ecc71"
COLOR_WARN = "#f1c40f"
COLOR_CRIT = "#e74c3c"
COLOR_BG_PANEL = "#1c1f26"
COLOR_ACCENT = "#3d8bfd"
COLOR_DONAR = "#ff5e5b"   # calido, para que la tarjeta de apoyo no se pierda entre paneles grises

DEV_NAME = "Edwin Javier Cortez Cardoza"
DEV_ALIAS = "Hades"
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# EDICIÓN: "cliente" (por defecto) oculta todo lo administrativo/técnico y
# en su lugar ofrece un panel de comandos oculto y amigable. "admin" muestra
# la Consola Dev, comandos técnicos exactos y el lenguaje de administrador
# de forma normal, sin ocultar nada. Ambas ediciones comparten el mismo
# código — main.py es la edición cliente; main_admin.py es un punto de
# entrada aparte que activa la edición admin antes de arrancar la app.
# ---------------------------------------------------------------------------
EDICION = "cliente"

# Referencia a la instancia de la app en ejecución — la usa el manejador
# global de errores de hilos de fondo (threading.excepthook, más abajo),
# que no puede simplemente recibir "self" porque Python lo llama fuera de
# cualquier método. Se asigna en TechCleanApp.__init__.
_instancia_app = None


def _manejar_excepcion_de_hilo(args):
    """
    Por defecto, cuando un hilo de fondo (worker) revienta con un error no
    atrapado, Python no muestra NADA visible — en la app compilada no hay
    ni siquiera una consola donde se imprimiría. Un bug ahí se sentía como
    "esto no hace nada" sin ninguna pista. Enganchado aquí, cualquier
    error de un hilo de fondo pasa por el mismo aviso visible que un error
    de la interfaz (ver TechCleanApp.report_callback_exception).
    """
    import traceback
    texto_error = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    if _instancia_app is not None:
        try:
            _instancia_app.after(0, lambda: _instancia_app._reportar_error_interno(texto_error))
        except Exception:
            pass


threading.excepthook = _manejar_excepcion_de_hilo

# Referencia a la instancia de la app en ejecución — la usa el manejador
# global de errores de hilos de fondo (threading.excepthook, más abajo),
# que no puede simplemente recibir "self" porque Python lo llama fuera de
# cualquier método. Se asigna en TechCleanApp.__init__.
_instancia_app = None

# Se construye AL IMPORTAR el modulo, antes de que establecer_idioma() haya
# corrido, asi que guarda el NOMBRE de la clave y no el texto: t() se llama al
# imprimir la ayuda, ya con el idioma fijado.
COMANDOS_DISPONIBLES = {
    "/ram": "cmd_ram",
    "/temporales": "cmd_temporales",
    "/papelera": "cmd_papelera",
    "/dns": "cmd_dns",
    "/rapido": "cmd_rapido",
    "/inicio": "cmd_inicio",
    "/componentes": "cmd_componentes",
    "/optimizar": "cmd_optimizar",
    "/reparar": "cmd_reparar",
    "/seguridad": "cmd_seguridad",
    "/gaming": "cmd_gaming",
    "/apps": "cmd_apps",
    "/privacidad": "cmd_privacidad",
    "/historial": "cmd_historial",
    "/widget": "cmd_widget",
    "/auto": "cmd_auto",
    "/fps": "cmd_fps",
    "/bios": "cmd_bios",
    "/ajustes": "cmd_ajustes",
    "/salir": "cmd_salir",
    "/help": "cmd_help",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HONK_PATH = os.path.join(BASE_DIR, "assets", "honk.wav")
ICON_PATH = os.path.join(BASE_DIR, "assets", "icono.ico")


def color_por_porcentaje(p):
    if p is None:
        return "#666666"
    if p < 60:
        return COLOR_OK
    if p < 85:
        return COLOR_WARN
    return COLOR_CRIT


def oscurecer_color(hex_color, factor=0.75):
    """Devuelve una versión más oscura de un color hex — usada para el
    efecto hover de los botones de acceso rápido de Gaming, en vez de
    dejar el mismo color en reposo y en hover (sin ningún feedback visual)."""
    try:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


# Con Modo Ligero activo las animaciones se apagan: en un equipo justo de
# recursos, redibujar el arco 16 veces por cada cambio de numero es
# exactamente el tipo de gasto que ese modo existe para evitar.
ANIMAR_BARRAS = True


class Gauge(ctk.CTkFrame):
    """Medidor circular. El valor NO salta de golpe: se interpola desde el
    valor que ya se estaba mostrando hasta el nuevo, con una curva que
    arranca rapido y frena al final (ease-out), asi que el arco y el numero
    se mueven juntos en vez de dar un tiron."""

    DURACION_MS = 320   # lo que tarda el recorrido completo
    PASO_MS = 20        # ~16 cuadros; mas fino no se nota y cuesta mas

    def __init__(self, master, titulo, unidad="%", size=150, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=16, **kwargs)
        self.titulo = titulo
        self.unidad = unidad
        self.size = size
        self._valor_mostrado = 0.0
        self._anim_id = None

        self.canvas = tk.Canvas(self, width=size, height=size, bg=COLOR_BG_PANEL, highlightthickness=0)
        self.canvas.pack(pady=(14, 4))

        self.lbl_titulo = ctk.CTkLabel(self, text=titulo, font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_titulo.pack(pady=(0, 2))

        self.lbl_detalle = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11), text_color="gray70")
        self.lbl_detalle.pack(pady=(0, 12))

        self.set_value(0, t("comun_cargando"))

    def _cancelar_animacion(self):
        """Una animacion en curso se descarta en cuanto llega un valor nuevo:
        si no, dos recorridos se pisarian y el arco temblaria."""
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def set_value(self, porcentaje, detalle=""):
        self.lbl_detalle.configure(text=detalle)

        if porcentaje is None:
            self._cancelar_animacion()
            self._valor_mostrado = None
            self._dibujar(None)
            return

        destino = max(0.0, min(100.0, float(porcentaje)))
        # Sin animacion cuando esta apagada, o cuando se viene de "N/D" (no
        # hay desde donde interpolar).
        if not ANIMAR_BARRAS or self._valor_mostrado is None:
            self._cancelar_animacion()
            self._valor_mostrado = destino
            self._dibujar(destino)
            return

        self._cancelar_animacion()
        inicio = self._valor_mostrado
        if abs(destino - inicio) < 0.5:      # cambio imperceptible: no vale animar
            self._valor_mostrado = destino
            self._dibujar(destino)
            return

        pasos = max(1, self.DURACION_MS // self.PASO_MS)

        def paso(i):
            self._anim_id = None
            # El usuario pudo cambiar de pantalla a media animacion: el gauge
            # ya no existe y tocarlo reventaria.
            if not self.winfo_exists():
                return
            avance = i / pasos
            suave = 1 - (1 - avance) ** 3    # ease-out cubico
            valor = inicio + (destino - inicio) * suave
            self._valor_mostrado = valor
            self._dibujar(valor)
            if i < pasos:
                self._anim_id = self.after(self.PASO_MS, paso, i + 1)

        paso(1)

    def _dibujar(self, porcentaje):
        self.canvas.delete("all")
        pad = 12
        color = color_por_porcentaje(porcentaje)

        self.canvas.create_arc(pad, pad, self.size - pad, self.size - pad,
                                start=90, extent=359.999, style="arc",
                                outline="#33363f", width=12)
        extent = -3.6 * (porcentaje or 0)
        if abs(extent) > 0.01:
            self.canvas.create_arc(pad, pad, self.size - pad, self.size - pad,
                                    start=90, extent=extent, style="arc",
                                    outline=color, width=12)
        texto = f"{porcentaje:.0f}{self.unidad}" if porcentaje is not None else "N/D"
        self.canvas.create_text(self.size / 2, self.size / 2, text=texto,
                                 fill="white", font=("Segoe UI", 20, "bold"))


class Sparkline(ctk.CTkFrame):
    """
    Mini gráfica de línea de tiempo (los últimos N valores), tipo las que
    trae HWiNFO/Task Manager — reutilizable para RAM, CPU o temperatura.
    Liviana a propósito: dibuja sobre un tk.Canvas normal, sin ninguna
    librería de gráficos nueva.

    NOTA: el constructor solo acepta master/titulo/unidad (igual que la
    clase Gauge, que sabemos que funciona bien). Cualquier otro ajuste
    (color de línea, máximo, tamaño) se hace DESPUÉS de crear el objeto,
    llamando a .configurar(...) — nunca por el constructor. Así se evita
    de raíz el problema de argumentos rechazados por customtkinter, sin
    depender de adivinar qué nombre específico le molesta.
    """
    def __init__(self, master, titulo, unidad="%", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=12, **kwargs)
        self.titulo = titulo
        self.unidad = unidad
        self.maximo = 100
        self.ancho = 260
        self.alto = 70
        self.tono = COLOR_OK
        self.max_puntos = 60
        self.valores = []

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(fila, text=titulo, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.lbl_actual = ctk.CTkLabel(fila, text="--", font=ctk.CTkFont(size=12), text_color="gray70")
        self.lbl_actual.pack(side="right")

        self.canvas = tk.Canvas(self, width=self.ancho, height=self.alto, bg=COLOR_BG_PANEL, highlightthickness=0)
        self.canvas.pack(padx=10, pady=(0, 10))

    def configurar(self, tono=None, maximo=None, ancho=None, alto=None, max_puntos=None):
        """Ajusta la apariencia después de construido — ver nota de la clase."""
        if tono is not None:
            self.tono = tono
        if maximo is not None:
            self.maximo = maximo
        if ancho is not None:
            self.ancho = ancho
            self.canvas.configure(width=ancho)
        if alto is not None:
            self.alto = alto
            self.canvas.configure(height=alto)
        if max_puntos is not None:
            self.max_puntos = max_puntos

    def agregar_valor(self, valor):
        if valor is None:
            return
        self.valores.append(valor)
        if len(self.valores) > self.max_puntos:
            self.valores = self.valores[-self.max_puntos:]
        self.lbl_actual.configure(text=f"{valor:.0f}{self.unidad}")
        self._dibujar()

    def _dibujar(self):
        self.canvas.delete("all")
        if len(self.valores) < 2:
            return
        maximo_local = max(max(self.valores), 1) if self.maximo is None else self.maximo
        n = len(self.valores)
        paso_x = self.ancho / max(self.max_puntos - 1, 1)
        offset_x = self.ancho - (n - 1) * paso_x
        puntos = []
        for i, v in enumerate(self.valores):
            x = offset_x + i * paso_x
            y = self.alto - (min(v, maximo_local) / maximo_local) * (self.alto - 6) - 3
            puntos.append((x, y))
        # Área sombreada bajo la línea
        poligono = [(offset_x, self.alto)] + puntos + [(puntos[-1][0], self.alto)]
        poligono_flat = [c for p in poligono for c in p]
        self.canvas.create_polygon(*poligono_flat, fill=self.tono, stipple="gray25", outline="")
        # Línea
        linea_flat = [c for p in puntos for c in p]
        self.canvas.create_line(*linea_flat, fill=self.tono, width=2, smooth=True)



class DevConsole(ctk.CTkFrame):
    """
    Consola de Desarrollador (Edición Administrador). Muestra el registro
    técnico en vivo de cada acción Y permite escribir comandos — usa el
    mismo motor de comandos del panel oculto del cliente (self._ejecutar_comando),
    así que el admin puede disparar cualquier función escribiendo, además
    de verla en botones normales por toda la app.
    """
    def __init__(self, master, on_comando=None, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=16, **kwargs)
        self.on_comando = on_comando

        header = ctk.CTkLabel(self, text="  Consola de Desarrollador — Registro de comandos",
                               font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        header.pack(fill="x", padx=12, pady=(12, 4))

        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12),
                                       fg_color="#0d0f13", text_color="#7CFC7C")
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.textbox.insert("end", t("consola_lista") + "\n")
        self.textbox.configure(state="disabled")

        if self.on_comando is not None:
            fila = ctk.CTkFrame(self, fg_color="transparent")
            fila.pack(fill="x", padx=12, pady=(0, 12))
            self.entry = ctk.CTkEntry(fila, placeholder_text=t("consola_placeholder"),
                                       font=ctk.CTkFont(family="Consolas", size=12))
            self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.entry.bind("<Return>", self._enviar)
            ctk.CTkButton(fila, text=t("consola_ejecutar"), width=90,
                          command=self._enviar).pack(side="left")
            self.entry.focus_set()

    def _enviar(self, event=None):
        texto = self.entry.get().strip()
        if not texto:
            return
        self.entry.delete(0, "end")
        self.imprimir(f"$ {texto}")
        if self.on_comando is not None:
            self.on_comando(texto)

    def imprimir(self, texto):
        if not self.textbox.winfo_exists():
            return
        self.textbox.configure(state="normal")
        self.textbox.insert("end", texto + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def log(self, accion, comando, resultado):
        if not self.textbox.winfo_exists():
            return
        self.textbox.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.textbox.insert("end", f'[{ts}] {t("consola_accion")}: {accion}\n')
        self.textbox.insert("end", f"          CMD:    {comando}\n")
        self.textbox.insert("end", f"          RESULT: {resultado}\n\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class ComandoConsole(ctk.CTkFrame):
    """
    Panel de comandos oculto (edición cliente). Deja que el usuario ejecute,
    escribiendo, las mismas funciones que ya existen como botones en el
    resto de la app — no expone comandos ni rutas técnicas del sistema,
    solo un atajo con estilo de terminal para quien lo descubre.
    """
    def __init__(self, master, on_comando, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=16, **kwargs)
        self.on_comando = on_comando

        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12),
                                       fg_color="#0d0f13", text_color="#9fd3ff")
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.textbox.insert("end", t("consola_ayuda") + "\n")
        self.textbox.configure(state="disabled")

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(0, 12))
        self.entry = ctk.CTkEntry(fila, placeholder_text="Escribe un comando y presiona Enter...")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._enviar)
        ctk.CTkButton(fila, text="Enviar", width=80, command=self._enviar).pack(side="left")
        self.entry.focus_set()

    def _enviar(self, event=None):
        texto = self.entry.get().strip()
        if not texto:
            return
        self.entry.delete(0, "end")
        self.imprimir(f"> {texto}")
        self.on_comando(texto)

    def imprimir(self, texto):
        if not self.textbox.winfo_exists():
            return
        self.textbox.configure(state="normal")
        self.textbox.insert("end", texto + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class TechCleanApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        global _instancia_app
        _instancia_app = self
        self._ultimo_aviso_error = 0.0

        self.title("TechClean Pro" + (t("app_edicion_admin") if EDICION == "admin" else ""))
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass  # en Linux/Mac (o si falta el archivo) simplemente no hay ícono — no es crítico
        self.geometry("1180x780")
        self.minsize(1000, 640)

        self.modo_desarrollador = tk.BooleanVar(value=False)
        self.dev_console = None
        self.reporte = rep.SessionReport()

        self._easter_clicks = 0
        self._easter_last_click = 0
        self._dev_clicks = 0
        self._dev_last_click = 0

        # Preferencias del usuario (widget visible, perfil de energía, alerta
        # de temperatura, punto de restauración) — persisten entre sesiones.
        self.prefs = prefs.cargar()
        idiomas.establecer_idioma(self.prefs.get("idioma", "es"))
        # Modo Ligero apaga las animaciones de las barras (aqui y en el widget).
        self._aplicar_preferencia_animaciones()
        if not self.prefs.get("idioma_preguntado", False):
            self._preguntar_idioma_primera_vez()
        self._ultima_alerta_temp = 0.0
        self._cpu_temp_cache = None
        self._modo_ahorro_bateria_activo = False

        # Info del equipo: lo rápido (hostname, usuario, arquitectura) se
        # muestra de inmediato; lo lento (procesador exacto, placa madre,
        # BIOS — usa PowerShell/CIM) se completa en un hilo aparte, para que
        # la ventana no tarde varios segundos en siquiera aparecer.
        self._system_info_cache = {
            "hostname": socket.gethostname(),
            "usuario": getpass.getuser(),
            "sistema_operativo": "Cargando...",
            "version_so": "", "release_so": "",
            "arquitectura": platform.machine(),
            "procesador": platform.processor() or "Cargando...",
            "placa_madre": "Cargando...", "bios": "Cargando...",
        }
        threading.Thread(target=self._cargar_info_sistema_completa, daemon=True).start()

        # ---- Segundo plano: widget flotante, bandeja del sistema, autopiloto ----
        self.performance_widget = None
        self.autopilot = autopilot_mod.Autopilot(log_callback=self._log_dev, intervalo_seg=8,
                                                   umbral_ram=self.prefs.get("umbral_ram_auto", 85))

        self.tray = tray_mod.TrayIcon(
            on_mostrar_panel=lambda: self.after(0, self._mostrar_ventana),
            on_toggle_widget=lambda: self.after(0, self._toggle_widget),
            on_toggle_auto=lambda: self.after(0, self._toggle_autopilot),
            on_salir=lambda: self.after(0, self._salir_definitivo),
        )
        self.tray.iniciar()

        # Cerrar la ventana minimiza a la bandeja en vez de cerrar la app
        self.protocol("WM_DELETE_WINDOW", self._minimizar_a_bandeja)

        self._build_layout()

        # Restaurar estado guardado de la sesión anterior (con un pequeño
        # retraso para que la ventana termine de dibujarse primero).
        self.after(400, self._restaurar_preferencias)
        self.after(self._intervalo(20000), self._chequear_alerta_temperatura)
        self.after(self._intervalo(2500), self._actualizar_icono_bandeja)
        self.after(self._intervalo(30000), self._chequear_bateria_automatica)
        self.after(5000, self._chequear_actualizacion_app)

    # ---------------- Layout general ----------------
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkScrollableFrame(self, width=210, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nswe")

        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.grid(row=0, column=1, sticky="nswe", padx=20, pady=20)
        self.contenido.grid_columnconfigure((0, 1, 2), weight=1)

        self._construir_sidebar()
        self.mostrar_dashboard()
        self._tick_dashboard()

    def _construir_sidebar(self):
        """Dibuja la barra lateral. Se vuelve a llamar cuando cambia el
        panel oculto (cliente), ya que solo entonces aparece esa entrada.

        NOTA: la limpieza usa una lista propia de widgets (self._sidebar_widgets)
        en vez de winfo_children(), porque self.sidebar es un CTkScrollableFrame:
        sus hijos reales viven dentro de un frame interno propio de customtkinter,
        así que winfo_children() sobre el contenedor NO devuelve los botones que
        agregamos (y podría incluso borrar el canvas interno del scroll)."""
        for w in getattr(self, "_sidebar_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self._sidebar_widgets = []

        def _add(widget):
            self._sidebar_widgets.append(widget)
            return widget

        self.sidebar.grid_rowconfigure(20, weight=1)

        _add(ctk.CTkLabel(self.sidebar, text="⚙ TechClean Pro", font=ctk.CTkFont(size=18, weight="bold"))).grid(
            row=0, column=0, padx=20, pady=(24, 4), sticky="w")

        if EDICION == "admin":
            admin_txt = t("sidebar_admin_estado_si") if opt.is_admin() else t("sidebar_admin_estado_no")
            admin_color = COLOR_OK if opt.is_admin() else COLOR_WARN
            texto_boton_admin = t("sidebar_boton_reiniciar_admin")
        else:
            admin_txt = t("sidebar_cliente_estado_si") if opt.is_admin() else t("sidebar_cliente_estado_no")
            admin_color = COLOR_OK if opt.is_admin() else COLOR_WARN
            texto_boton_admin = t("sidebar_boton_desbloquear")
        self.lbl_admin = _add(ctk.CTkLabel(self.sidebar, text=admin_txt, text_color=admin_color,
                                            font=ctk.CTkFont(size=12)))
        self.lbl_admin.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        botones = [
            (t("nav_inicio"), self.mostrar_dashboard),
            (t("nav_componentes"), self.mostrar_componentes),
            (t("nav_optimizar"), self.mostrar_optimizador),
            (t("nav_reparar"), self.mostrar_reparar),
            (t("nav_aplicaciones"), self.mostrar_aplicaciones),
            (t("nav_privacidad"), self.mostrar_privacidad),
            (t("nav_seguridad"), self.mostrar_seguridad),
            (t("nav_gaming"), self.mostrar_gaming),
            (t("nav_segundo_plano"), self.mostrar_segundo_plano),
            (t("nav_historial"), self.mostrar_reporte),
            (t("nav_energia"), self.mostrar_bios),
        ]
        if EDICION == "admin":
            botones.append((t("nav_consola_dev"), self.mostrar_consola))
        elif self.modo_desarrollador.get():
            botones.append((t("nav_panel_oculto"), self.mostrar_panel_oculto))
        botones.append((t("nav_ajustes"), self.mostrar_ajustes))

        for i, (texto, comando) in enumerate(botones, start=2):
            b = _add(ctk.CTkButton(self.sidebar, text=texto, anchor="w", fg_color="transparent",
                                    hover_color="#2a2d36", command=comando))
            b.grid(row=i, column=0, padx=10, pady=4, sticky="we")

        fila_sig = 2 + len(botones)
        if not opt.is_admin():
            _add(ctk.CTkButton(self.sidebar, text=texto_boton_admin, fg_color=COLOR_WARN,
                                text_color="black", command=self.solicitar_admin)).grid(
                row=fila_sig, column=0, padx=10, pady=(16, 6), sticky="we")
            fila_sig += 1

        _add(ctk.CTkButton(self.sidebar, text=t("nav_minimizar_bandeja"), fg_color="transparent",
                            hover_color="#2a2d36", command=self._minimizar_a_bandeja)).grid(
            row=fila_sig, column=0, padx=10, pady=(4, 6), sticky="we")

        if EDICION == "cliente" and self.modo_desarrollador.get():
            _add(ctk.CTkLabel(self.sidebar, text="🔓 Panel oculto activo", text_color="gray50",
                               font=ctk.CTkFont(size=10))).grid(
                row=fila_sig + 1, column=0, padx=20, pady=(10, 4), sticky="w")

    def _limpiar_contenido(self):
        """Destruye todo lo que hubiera en la pantalla anterior antes de
        dibujar la nueva. Si UN widget falla al destruirse (estado
        corrupto, poco probable pero no imposible), no debe dejar a los
        demás sin destruir — de ahí el try/except por widget en vez de uno
        solo para todo el bucle.

        BUG corregido: self.contenido es un widget COMPARTIDO entre TODAS
        las pantallas — si una pantalla cambiaba el ancho de alguna
        columna o fila para su propio diseño (como hacía antes
        Componentes, angostando la columna 2), esa configuración se
        quedaba así para la SIGUIENTE pantalla que se abriera, sin
        importar cuál fuera, dejando espacio real sin usar y una barra de
        scroll que no debería estar ahí. Se restaura a un estado base
        conocido cada vez que se cambia de pantalla, para que ninguna
        quede "contaminada" por configuraciones de la anterior."""
        for w in self.contenido.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        for col in range(3):
            self.contenido.grid_columnconfigure(col, weight=1)
        for fila in range(8):
            self.contenido.grid_rowconfigure(fila, weight=0)

    def solicitar_admin(self):
        opt.relaunch_as_admin()

    def _boton_ver_reporte(self, panel):
        ctk.CTkButton(panel, text=t("comun_ver_reporte"),
                      fg_color="#2a2d36", hover_color="#3a3e4a",
                      command=self.mostrar_reporte).pack(padx=16, pady=(0, 16), anchor="w")

    # ---------------- Ventana / bandeja ----------------
    def _minimizar_a_bandeja(self):
        self.withdraw()

    def _mostrar_ventana(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _salir_definitivo(self):
        """Cierre TOTAL de la app (desde el menú de la bandeja), no solo minimizar."""
        try:
            self.autopilot.detener()
        except Exception:
            pass
        try:
            if self.performance_widget:
                self.performance_widget.destruir()
        except Exception:
            pass
        try:
            self.tray.detener()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)

    # ---------------- Dashboard ----------------
    def mostrar_dashboard(self):
        self._limpiar_contenido()

        ctk.CTkLabel(self.contenido, text=t("dash_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        # ---- Acción rápida: un clic, sin tecnicismos ----
        panel_rapido = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_rapido.grid(row=1, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 12))
        fila_rapida = ctk.CTkFrame(panel_rapido, fg_color="transparent")
        fila_rapida.pack(fill="x", padx=16, pady=14)
        ctk.CTkButton(fila_rapida, text=t("dash_boton_optimizar_clic"), height=44,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._accion_optimizacion_rapida).pack(side="left", padx=(0, 10))
        ctk.CTkButton(fila_rapida, text=t("dash_boton_vaciar_papelera"), height=44,
                      fg_color="#2a2d36", hover_color="#3a3e4a",
                      command=self._accion_vaciar_papelera_user).pack(side="left")
        self.lbl_resultado_user = ctk.CTkLabel(panel_rapido, text=t("dash_resultado_inicial"),
                                                font=ctk.CTkFont(size=12), text_color="gray70",
                                                wraplength=900, justify="left")
        self.lbl_resultado_user.pack(fill="x", padx=16, pady=(0, 14), anchor="w")

        # ---- Salud del sistema (semáforo) ----
        panel_salud = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_salud.grid(row=2, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 12))
        self._panel_salud_actual = panel_salud
        fila_salud = ctk.CTkFrame(panel_salud, fg_color="transparent")
        fila_salud.pack(fill="x", padx=16, pady=14)
        self.lbl_salud_punto = ctk.CTkLabel(fila_salud, text="🩺", font=ctk.CTkFont(size=28))
        self.lbl_salud_punto.pack(side="left", padx=(0, 12))
        self.btn_arreglar_todo = ctk.CTkButton(fila_salud, text=t("dash_arreglar_todo"), width=140,
                                                state="disabled", command=self._accion_arreglar_todo)
        self.btn_arreglar_todo.pack(side="right")
        col_salud = ctk.CTkFrame(fila_salud, fg_color="transparent")
        col_salud.pack(side="left", fill="x", expand=True)
        self.lbl_salud_titulo = ctk.CTkLabel(col_salud, text=t("dash_salud_calculando"),
                                              font=ctk.CTkFont(size=15, weight="bold"), anchor="w")
        self.lbl_salud_titulo.pack(fill="x", anchor="w")
        self.lbl_salud_detalle = ctk.CTkLabel(col_salud, text=t("dash_salud_revisando"),
                                               font=ctk.CTkFont(size=12), text_color="gray60", anchor="w",
                                               wraplength=800, justify="left")
        self.lbl_salud_detalle.pack(fill="x", anchor="w")

        # BUG corregido: opt.limpieza_programada_activa() llama a
        # schtasks /query (subprocess) — se consultaba directo en el hilo
        # principal cada vez que se abría Inicio, la primera pantalla que
        # ves al abrir la app. Ahora se consulta en un hilo aparte.
        self.lbl_limpieza_programada_info = None

        def worker_limpieza():
            if opt.limpieza_programada_activa():
                self.after(0, self._mostrar_aviso_limpieza_programada)
        threading.Thread(target=worker_limpieza, daemon=True).start()

        self.gauge_ram = Gauge(self.contenido, t("dash_gauge_ram"))
        self.gauge_ram.grid(row=3, column=0, padx=8, pady=8, sticky="we")
        self.gauge_cpu = Gauge(self.contenido, t("dash_gauge_cpu"))
        self.gauge_cpu.grid(row=3, column=1, padx=8, pady=8, sticky="we")
        self.gauge_disco = Gauge(self.contenido, t("dash_gauge_disco"))
        self.gauge_disco.grid(row=3, column=2, padx=8, pady=8, sticky="we")

        self.gauge_gpu = Gauge(self.contenido, t("dash_gauge_gpu"))
        self.gauge_gpu.grid(row=4, column=0, padx=8, pady=8, sticky="we")

        info_frame = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        info_frame.grid(row=4, column=1, columnspan=2, padx=8, pady=8, sticky="nswe")
        ctk.CTkLabel(info_frame, text=t("dash_info_equipo_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x", padx=12, pady=(12, 6))
        info = self._system_info_cache
        texto = t("dash_info_equipo_texto", hostname=info["hostname"], usuario=info["usuario"],
                  so=info["sistema_operativo"], procesador=info["procesador"], arquitectura=info["arquitectura"])
        self.lbl_info_equipo = ctk.CTkLabel(info_frame, text=texto, justify="left", anchor="w",
                                             font=ctk.CTkFont(size=12))
        self.lbl_info_equipo.pack(fill="x", padx=12, pady=(0, 12))

        self.spark_ram = Sparkline(self.contenido, t("dash_spark_ram"))
        self.spark_ram.configurar(tono=COLOR_OK)
        self.spark_ram.grid(row=5, column=0, columnspan=2, padx=8, pady=8, sticky="we")
        self.spark_cpu = Sparkline(self.contenido, t("dash_spark_cpu"))
        self.spark_cpu.configurar(tono="#3d8bfd")
        self.spark_cpu.grid(row=5, column=2, padx=8, pady=8, sticky="we")

        self._refrescar_gauges()
        self._calcular_salud_sistema()

    def _mostrar_aviso_limpieza_programada(self):
        if not (hasattr(self, "_panel_salud_actual") and self._panel_salud_actual.winfo_exists()):
            return
        hora_guardada = self.prefs.get("limpieza_hora", "09:00")
        ctk.CTkLabel(self._panel_salud_actual,
                     text=t("dash_limpieza_programada_aviso", hora=hora_guardada),
                     font=ctk.CTkFont(size=11), text_color="gray50").pack(padx=16, pady=(0, 12), anchor="w")

    def _accion_arreglar_todo(self):
        self.lbl_salud_detalle.configure(text=t("dash_arreglando"))
        self.btn_arreglar_todo.configure(state="disabled")

        def worker():
            liberado_ram, procesos, cmd1 = opt.trim_process_memory()
            liberado_disco, archivos, cmd2 = opt.clear_temp_files()
            msg = t("dash_arreglo_listo", procesos=procesos, archivos=archivos,
                    total=opt.format_bytes(liberado_ram + liberado_disco))
            self._log_dev("Arreglar todo (Inicio)", f"{cmd1} + {cmd2}", msg, seccion=t("seccion_inicio"),
                          exito=True, bytes_liberados=liberado_ram + liberado_disco,
                          archivos_afectados=procesos + archivos)
            if hasattr(self, "lbl_salud_detalle") and self.lbl_salud_detalle.winfo_exists():
                self.after(0, lambda: self.lbl_salud_detalle.configure(text=msg))
                self.after(800, self._calcular_salud_sistema)
        threading.Thread(target=worker, daemon=True).start()

    def _cargar_info_sistema_completa(self):
        """Corre en un hilo aparte apenas arranca la app: pide el detalle
        completo del equipo (procesador exacto, placa madre, BIOS — usa
        PowerShell/CIM) y actualiza la caché + la pantalla si el Dashboard
        ya está abierto. El Dashboard mientras tanto ya se ve con los datos
        rápidos (hostname, usuario, arquitectura)."""
        info_completa = sysmon.get_system_info()
        self._system_info_cache = info_completa
        self.after(0, self._refrescar_info_equipo_visible)

    def _refrescar_info_equipo_visible(self):
        if not (hasattr(self, "lbl_info_equipo") and self.lbl_info_equipo.winfo_exists()):
            return
        info = self._system_info_cache
        texto = t("dash_info_equipo_texto", hostname=info["hostname"], usuario=info["usuario"],
                  so=info["sistema_operativo"], procesador=info["procesador"], arquitectura=info["arquitectura"])
        self.lbl_info_equipo.configure(text=texto)

    def _calcular_salud_sistema(self):
        """Puntaje 0-100 a partir de datos que ya recolectamos en otras
        partes de la app (RAM, disco, apps de inicio, temporales
        estimados) — se calcula en un hilo aparte porque estimar el
        espacio recuperable implica leer carpetas."""
        def worker():
            try:
                ram_pct = sysmon.get_ram_info()["porcentaje"]
            except Exception:
                ram_pct = None
            try:
                disco_pct = sysmon.get_disk_info()["porcentaje"]
            except Exception:
                disco_pct = None
            try:
                apps_activas = sum(1 for a in opt.listar_apps_inicio() if a["activo"])
            except Exception:
                apps_activas = 0
            try:
                _, total_recuperable = opt.estimate_reclaimable_space()
                mb_recuperable = total_recuperable / (1024 ** 2)
            except Exception:
                mb_recuperable = 0

            umbral_ram = self.prefs.get("umbral_salud_ram", 75)
            umbral_disco = self.prefs.get("umbral_salud_disco", 85)
            puntaje = 100
            motivos = []
            if ram_pct is not None:
                if ram_pct > umbral_ram + 15:
                    puntaje -= 25
                    motivos.append(t("dash_motivo_ram_muy_alta", pct=f"{ram_pct:.0f}"))
                elif ram_pct > umbral_ram:
                    puntaje -= 10
                    motivos.append(t("dash_motivo_ram_alta", pct=f"{ram_pct:.0f}"))
            if disco_pct is not None:
                if disco_pct > umbral_disco + 10:
                    puntaje -= 25
                    motivos.append(t("dash_motivo_disco_casi_lleno", pct=f"{disco_pct:.0f}"))
                elif disco_pct > umbral_disco:
                    puntaje -= 10
                    motivos.append(t("dash_motivo_disco_poco_espacio", pct=f"{disco_pct:.0f}"))
            if apps_activas > 15:
                puntaje -= 15
                motivos.append(t("dash_motivo_apps_inicio", n=apps_activas))
            elif apps_activas > 8:
                puntaje -= 5
                motivos.append(t("dash_motivo_apps_inicio", n=apps_activas))
            if mb_recuperable > 5000:
                puntaje -= 15
                motivos.append(t("dash_motivo_temporales_gb", gb=f"{mb_recuperable / 1024:.1f}"))
            elif mb_recuperable > 1500:
                puntaje -= 5
                motivos.append(t("dash_motivo_temporales_mb", mb=f"{mb_recuperable:.0f}"))
            puntaje = max(0, min(100, puntaje))

            if puntaje >= 80:
                emoji, nivel, color = "🟢", t("dash_nivel_verde"), COLOR_OK
            elif puntaje >= 50:
                emoji, nivel, color = "🟡", t("dash_nivel_amarillo"), COLOR_WARN
            else:
                emoji, nivel, color = "🔴", t("dash_nivel_rojo"), COLOR_CRIT

            if motivos:
                detalle = t("dash_salud_motivos_prefijo") + ", ".join(motivos) + "."
            else:
                detalle = t("dash_salud_sin_motivos")

            self.after(0, lambda: self._pintar_salud_sistema(puntaje, emoji, nivel, color, detalle))

        threading.Thread(target=worker, daemon=True).start()

    def _pintar_salud_sistema(self, puntaje, emoji, nivel, color, detalle):
        if not (hasattr(self, "lbl_salud_titulo") and self.lbl_salud_titulo.winfo_exists()):
            return
        self.lbl_salud_punto.configure(text=emoji)
        self.lbl_salud_titulo.configure(text=t("dash_salud_titulo", nivel=nivel, puntaje=puntaje), text_color=color)
        self.lbl_salud_detalle.configure(text=detalle)
        if hasattr(self, "btn_arreglar_todo") and self.btn_arreglar_todo.winfo_exists():
            self.btn_arreglar_todo.configure(state="normal" if puntaje < 100 else "disabled")

    def _refrescar_gauges(self):
        """Solo lee valores en vivo (RAM/CPU/disco/GPU) — la info estática
        del equipo ya está cacheada y no se vuelve a pedir aquí."""
        try:
            if not (hasattr(self, "gauge_ram") and self.gauge_ram.winfo_exists()):
                return
            ram = sysmon.get_ram_info()
            self.gauge_ram.set_value(ram["porcentaje"], f'{ram["usado_gb"]} / {ram["total_gb"]} GB')

            cpu = sysmon.get_cpu_info()
            self.gauge_cpu.set_value(cpu["porcentaje"],
                                     t("dash_nucleos_fisicos", n=cpu["nucleos_fisicos"]))

            disco = sysmon.get_disk_info()
            self.gauge_disco.set_value(disco["porcentaje"], f'{disco["libre_gb"]} GB libres')

            gpu_pct = sysmon.get_gpu_utilization()
            self.gauge_gpu.set_value(gpu_pct, "GPU NVIDIA" if gpu_pct is not None else "No disponible en vivo")

            if hasattr(self, "spark_ram") and self.spark_ram.winfo_exists():
                self.spark_ram.agregar_valor(ram["porcentaje"])
            if hasattr(self, "spark_cpu") and self.spark_cpu.winfo_exists():
                self.spark_cpu.agregar_valor(cpu["porcentaje"])
        except Exception:
            pass

    def _tick_dashboard(self):
        """Refresco programado en el hilo principal de Tkinter (seguro),
        en vez de un hilo aparte tocando widgets directamente."""
        self._refrescar_gauges()
        self.after(self._intervalo(2000), self._tick_dashboard)

    # ---------------- Componentes (monitoreo extendido de hardware) ----------------
    def mostrar_componentes(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("comp_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ctk.CTkLabel(self.contenido,
                     text=t("comp_subtitulo"),
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # BUG corregido: self.contenido es un widget COMPARTIDO entre todas
        # las pantallas — poner la columna 2 en ancho cero aquí (como
        # estaba antes) se quedaba así para TODAS las pantallas que se
        # abrieran después, sin importar cuál, dejando espacio real sin
        # usar y forzando scroll donde no hacía falta. _limpiar_contenido()
        # ahora restaura las columnas al cambiar de pantalla, así que esto
        # ya no hace falta — se elimina en vez de solo parcharlo.
        self.contenido.grid_rowconfigure(2, weight=1)
        scroll = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        scroll.grid(row=2, column=0, columnspan=3, sticky="nswe")
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.panel_cpu = self._crear_tarjeta_componente(scroll, t("comp_card_cpu"), 0, 0)
        self.panel_gpu = self._crear_tarjeta_componente(scroll, t("comp_card_gpu"), 0, 1)
        self.panel_ram = self._crear_tarjeta_componente(scroll, t("comp_card_ram"), 1, 0)
        self.lbl_canal_ram = ctk.CTkLabel(self.panel_ram.master, text="", font=ctk.CTkFont(size=10),
                                            text_color="gray50", wraplength=420, justify="left", anchor="w")
        self.lbl_canal_ram.pack(fill="x", padx=14, pady=(0, 14))
        self.panel_disco = self._crear_tarjeta_componente(scroll, t("comp_card_disco"), 1, 1)
        fila_disco = ctk.CTkFrame(self.panel_disco.master, fg_color="transparent")
        fila_disco.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(fila_disco, text=t("comp_btn_probar_disco"), width=170, height=28,
                      font=ctk.CTkFont(size=11), command=self._accion_probar_disco).pack(side="left")
        self.lbl_resultado_disco = ctk.CTkLabel(fila_disco, text="", font=ctk.CTkFont(size=11),
                                                  text_color="gray60")
        self.lbl_resultado_disco.pack(side="left", padx=10)
        self.panel_red = self._crear_tarjeta_componente(scroll, t("comp_card_red"), 2, 0)
        self.panel_bateria = self._crear_tarjeta_componente(scroll, t("comp_card_bateria"), 2, 1)
        self.panel_sistema = self._crear_tarjeta_componente(scroll, t("comp_card_equipo"), 3, 0)
        self.panel_audio = self._crear_tarjeta_componente(scroll, t("comp_card_audio"), 3, 1)
        fila_audio = ctk.CTkFrame(self.panel_audio.master, fg_color="transparent")
        fila_audio.pack(padx=14, pady=(0, 14), anchor="w")
        ctk.CTkButton(fila_audio, text=t("comp_btn_probar_sonido"), width=110,
                      command=self._accion_probar_sonido).pack(side="left", padx=(0, 6))
        ctk.CTkButton(fila_audio, text=t("comp_btn_probar_micro"), width=130, fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_prueba_microfono).pack(side="left", padx=(0, 6))
        ctk.CTkButton(fila_audio, text=t("comp_btn_mezclador"), width=100, fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_mezclador).pack(side="left")

        def worker_audio():
            dispositivos = opt.listar_dispositivos_audio()
            self.after(0, lambda: self._pintar_dispositivos_audio(dispositivos))
        threading.Thread(target=worker_audio, daemon=True).start()

        self.spark_temp_cpu = Sparkline(scroll, t("comp_spark_temp"), unidad="°C")
        self.spark_temp_cpu.configurar(maximo=100, tono=COLOR_CRIT)
        self.spark_temp_cpu.grid(row=4, column=0, columnspan=2, padx=8, pady=8, sticky="we")

        # ---- Historial de arranques (tendencia en el tiempo) ----
        panel_arranques = ctk.CTkFrame(scroll, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_arranques.grid(row=5, column=0, columnspan=2, padx=8, pady=8, sticky="we")
        ctk.CTkLabel(panel_arranques, text=t("comp_arranques_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(panel_arranques,
                     text=t("comp_arranques_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=14, pady=(0, 10))
        self.lista_arranques = ctk.CTkScrollableFrame(panel_arranques, fg_color="#141720",
                                                        corner_radius=10, height=140)
        self.lista_arranques.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(self.lista_arranques, text=t("comp_leyendo"),
                     text_color="gray60").pack(padx=8, pady=8)

        def worker_arranques():
            historial = sysmon.listar_historial_arranques(limite=15)
            self.after(0, lambda: self._pintar_historial_arranques(historial))
        threading.Thread(target=worker_arranques, daemon=True).start()

        ctk.CTkButton(self.panel_red.master, text=t("comp_btn_speedtest"), height=28,
                      command=self._abrir_ventana_speedtest).pack(padx=14, pady=(0, 14), anchor="w")

        ctk.CTkButton(self.contenido, text=t("comp_btn_export_hw"),
                      command=self._exportar_reporte_hardware).grid(row=3, column=0, sticky="w", padx=8, pady=(8, 0))
        ctk.CTkButton(self.contenido, text=t("comp_btn_drivers"),
                      command=self.mostrar_drivers).grid(row=3, column=1, sticky="w", padx=8, pady=(8, 0))

        self._refrescar_componentes()
        # Sin esto, la temperatura tardaría hasta 20s en aparecer la
        # primera vez (esperando el próximo ciclo de _chequear_alerta_temperatura)
        # — se dispara una consulta inmediata al abrir la pantalla.
        self._actualizar_temperatura_cpu()

    def _pintar_historial_arranques(self, historial):
        if not (hasattr(self, "lista_arranques") and self.lista_arranques.winfo_exists()):
            return
        for w in self.lista_arranques.winfo_children():
            w.destroy()
        if not historial:
            ctk.CTkLabel(self.lista_arranques,
                         text=t("comp_sin_arranques"),
                         text_color="gray60", wraplength=800, justify="left").pack(padx=8, pady=8, anchor="w")
            return
        for entrada in historial:
            fila = ctk.CTkFrame(self.lista_arranques, fg_color="transparent")
            fila.pack(fill="x", padx=4, pady=2)
            try:
                fecha_legible = datetime.fromisoformat(entrada["fecha"].replace("Z", "+00:00")).strftime(
                    "%d/%m/%Y %H:%M")
            except Exception:
                fecha_legible = entrada["fecha"] or "?"
            color = COLOR_CRIT if entrada["segundos"] > 60 else (COLOR_WARN if entrada["segundos"] > 30 else COLOR_OK)
            ctk.CTkLabel(fila, text=fecha_legible, font=ctk.CTkFont(size=11), text_color="gray60").pack(
                side="left")
            ctk.CTkLabel(fila, text=t("comp_segundos", segundos=f'{entrada["segundos"]:.0f}'),
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).pack(side="right")

    def _pintar_dispositivos_audio(self, dispositivos):
        if not (hasattr(self, "panel_audio") and self.panel_audio.winfo_exists()):
            return
        if not dispositivos:
            self.panel_audio.configure(text=t("comp_sin_audio"))
            return
        texto = "\n".join(t("comp_audio_detalle", nombre=d["nombre"], estado=d["estado"])
                          for d in dispositivos)
        self.panel_audio.configure(text=texto)

    def _accion_probar_sonido(self):
        threading.Thread(target=opt.reproducir_sonido_prueba, daemon=True).start()
        self._log_dev(t("comp_log_sonido"), "winsound.Beep(880, 300)",
                      t("comp_sonido_ok"), seccion=t("seccion_componentes"), exito=True)

    def _accion_probar_disco(self):
        self.lbl_resultado_disco.configure(text=t("comp_preparando"))

        def progreso(texto):
            if hasattr(self, "lbl_resultado_disco") and self.lbl_resultado_disco.winfo_exists():
                self.after(0, lambda: self.lbl_resultado_disco.configure(text=texto))

        def worker():
            resultado = opt.prueba_velocidad_disco(tamano_mb=256, callback_progreso=progreso)
            if not resultado or "error" in resultado:
                msg = (t("comp_disco_error",
                         error=resultado.get("error", t("comp_error_desconocido"))) if resultado
                       else t("comp_disco_error_simple"))
                exito = False
            else:
                msg = t("comp_disco_resultado", escritura=resultado["escritura_mbs"],
                        lectura=resultado["lectura_mbs"])
                exito = True
            self._log_dev(t("comp_log_disco"), t("comp_log_disco_cmd"), msg,
                          seccion=t("seccion_componentes"), exito=exito)
            if hasattr(self, "lbl_resultado_disco") and self.lbl_resultado_disco.winfo_exists():
                self.after(0, lambda: self.lbl_resultado_disco.configure(text=msg))
        threading.Thread(target=worker, daemon=True).start()

    def _accion_abrir_prueba_microfono(self):
        exito, comando = opt.abrir_prueba_microfono()
        self._log_dev(t("comp_log_micro"), comando,
                      t("comp_micro_ok") if exito else t("comp_no_abrir"),
                      seccion=t("seccion_componentes"), exito=exito)

    def _accion_abrir_mezclador(self):
        exito, comando = opt.abrir_mezclador_volumen()
        self._log_dev(t("comp_log_mezclador"), comando,
                      t("comp_mezclador_ok") if exito else t("comp_no_abrir"),
                      seccion=t("seccion_componentes"), exito=exito)

    def _crear_tarjeta_componente(self, parent, titulo, row, col):
        tarjeta = ctk.CTkFrame(parent, fg_color=COLOR_BG_PANEL, corner_radius=16)
        tarjeta.grid(row=row, column=col, padx=8, pady=8, sticky="nswe")
        ctk.CTkLabel(tarjeta, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(
            fill="x", padx=14, pady=(12, 4))
        etiqueta = ctk.CTkLabel(tarjeta, text=t("comp_leyendo"),
                                font=ctk.CTkFont(size=12, family="Consolas"),
                                 justify="left", anchor="w", wraplength=420)
        etiqueta.pack(fill="x", padx=14, pady=(0, 14))
        return etiqueta

    def _refrescar_componentes(self):
        if not (hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists()):
            return

        def worker():
            # BUG corregido: antes no había ningún try/except alrededor de
            # todo este bloque — si UNA sola de estas 9 consultas fallaba
            # por cualquier motivo, el hilo entero moría en silencio y la
            # pantalla se quedaba en "Leyendo..." para siempre, sin
            # reintentar ni avisar nada. Ahora un fallo puntual no mata el
            # refresco: se muestra el error y se reintenta en el siguiente ciclo.
            try:
                if not hasattr(self, "_ram_sticks_cache"):
                    self._ram_sticks_cache = sysmon.get_ram_sticks()
                # BUG de rendimiento corregido: si la GPU no da datos en
                # vivo (no es NVIDIA — como gráficos AMD/Intel integrados),
                # su nombre nunca cambia durante la sesión, así que no
                # tenía sentido volver a preguntarlo por WMI/PowerShell
                # cada 3 segundos — cada consulta así tarda bastante,
                # sobre todo en equipos justos de recursos, y era la mitad
                # de por qué Componentes se sentía lento. Se cachea una
                # sola vez. Si SÍ hay datos en vivo (GPU NVIDIA vía
                # nvidia-smi), se sigue consultando cada vez, porque ahí
                # el uso/temperatura/VRAM sí cambian de verdad.
                if not hasattr(self, "_gpu_info_cache") or self._gpu_info_cache.get("fuente") == "nvidia-smi":
                    self._gpu_info_cache = sysmon.get_gpu_info()
                # BUG de rendimiento corregido: get_cpu_details() traía la
                # temperatura incluida por defecto — otra consulta WMI, la
                # más lenta de todas cuando WMI está degradado (hasta 8s).
                # Se pide SIN temperatura aquí (datos rápidos de psutil
                # nada más) y se rellena con self._cpu_temp_cache, que se
                # actualiza aparte, con su propio ritmo — así lo rápido no
                # espera a lo lento.
                cpu = sysmon.get_cpu_details(incluir_temperatura=False)
                cpu["temperatura_c"] = self._cpu_temp_cache
                datos = {
                    "cpu": cpu,
                    "gpu": self._gpu_info_cache,
                    "ram_sticks": self._ram_sticks_cache,
                    "memoria_virtual": sysmon.get_memoria_virtual(),
                    "particiones": sysmon.get_disk_partitions(),
                    "io_disco": sysmon.get_disk_io_speed(),
                    "red": sysmon.get_network_speed(),
                    "bateria": sysmon.get_battery_info(),
                    "uptime": sysmon.get_uptime_seconds(),
                    "procesos": sysmon.get_process_count(),
                }
                error = None
            except Exception as e:
                datos = None
                error = str(e)

            def _terminar():
                if datos is not None:
                    self._pintar_componentes(datos)
                elif hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists():
                    self.panel_cpu.configure(text=t("comp_reintentando", error=error))
                self.after(self._intervalo(3000), self._refrescar_componentes)
            self.after(0, _terminar)

        threading.Thread(target=worker, daemon=True).start()

    def _pintar_componentes(self, datos):
        if not (hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists()):
            return

        cpu = datos["cpu"]
        nucleos_txt = "  ".join(f'N{i}:{v:.0f}%' for i, v in enumerate(cpu["porcentaje_por_nucleo"]))
        temp_cpu = (f'{cpu["temperatura_c"]:.0f}°C' if cpu["temperatura_c"] is not None
                    else t("comp_no_disponible_equipo"))

        # Heurística de throttling térmico: CPU bajo carga significativa pero
        # corriendo muy por debajo de su frecuencia máxima — indicio (no
        # certeza absoluta, un plan de energía Silencioso también reduce el
        # clock a propósito) de que se está limitando por temperatura.
        throttling = False
        if (cpu.get("frecuencia_actual_mhz") and cpu.get("frecuencia_max_mhz")
                and cpu.get("porcentaje_total") and cpu["porcentaje_total"] > 50
                and cpu["frecuencia_actual_mhz"] < cpu["frecuencia_max_mhz"] * 0.7):
            throttling = True

        texto_cpu = t("comp_cpu_texto",
                      uso=f'{cpu["porcentaje_total"]:.0f}',
                      fisicos=cpu["nucleos_fisicos"], logicos=cpu["nucleos_logicos"],
                      frec=cpu["frecuencia_actual_mhz"] or t("comp_nd"),
                      frec_max=cpu["frecuencia_max_mhz"] or t("comp_nd"),
                      temp=temp_cpu, nucleos=nucleos_txt)
        if throttling:
            texto_cpu += t("comp_throttling")
        self.panel_cpu.configure(text=texto_cpu)
        if hasattr(self, "spark_temp_cpu") and self.spark_temp_cpu.winfo_exists():
            self.spark_temp_cpu.agregar_valor(cpu.get("temperatura_c"))

        gpu = datos["gpu"]
        if gpu.get("porcentaje") is not None:
            temp_gpu = (f'{gpu["temperatura_c"]:.0f}°C' if gpu.get("temperatura_c") is not None
                        else t("comp_no_disponible"))
            fan_gpu = (f'{gpu["ventilador_pct"]:.0f}%' if gpu.get("ventilador_pct") is not None
                       else t("comp_no_disponible"))
            texto_gpu = t("comp_gpu_texto", nombre=gpu["nombre"],
                          uso=f'{gpu["porcentaje"]:.0f}',
                          vram_usada=gpu["vram_usada_gb"], vram_total=gpu["vram_total_gb"],
                          temp=temp_gpu, ventilador=fan_gpu)
        else:
            texto_gpu = t("comp_gpu_sin_datos", nombre=gpu["nombre"])
        self.panel_gpu.configure(text=texto_gpu)

        ram_sticks = datos["ram_sticks"]
        if ram_sticks:
            texto_ram = "\n".join(
                t("comp_ram_modulo", ranura=m["ranura"], capacidad=m["capacidad_gb"],
                  velocidad=m["velocidad_mhz"] or t("comp_nd"), fabricante=m["fabricante"])
                for m in ram_sticks)
            canal = sysmon.estimar_canal_ram(ram_sticks)
            if canal:
                texto_ram += t("comp_ram_canal", modo=canal["modo"])
        else:
            texto_ram = t("comp_ram_sin_detalle")
            canal = None
        mv = datos.get("memoria_virtual")
        if mv:
            texto_ram += t("comp_ram_virtual", usado=mv["usado_gb"], total=mv["total_gb"],
                           pct=f'{mv["porcentaje"]:.0f}')
        self.panel_ram.configure(text=texto_ram)
        if hasattr(self, "lbl_canal_ram") and self.lbl_canal_ram.winfo_exists():
            self.lbl_canal_ram.configure(text=canal["explicacion"] if canal else "")

        particiones = datos["particiones"]
        io_disco = datos["io_disco"]
        if particiones:
            texto_disco = "\n".join(
                t("comp_disco_particion", unidad=p["unidad"], usado=p["usado_gb"],
                  total=p["total_gb"], pct=f'{p["porcentaje"]:.0f}')
                for p in particiones)
            texto_disco += t("comp_disco_velocidad", lectura=io_disco["lectura_mbps"],
                             escritura=io_disco["escritura_mbps"])
        else:
            texto_disco = t("comp_sin_unidades")
        self.panel_disco.configure(text=texto_disco)

        red = datos["red"]
        self.panel_red.configure(text=t("comp_red_texto", bajada=red["bajada_mbps"],
                                        subida=red["subida_mbps"]))

        bateria = datos["bateria"]
        if bateria:
            estado = (t("comp_bateria_cargando") if bateria["cargando"]
                      else t("comp_bateria_descargando"))
            restante = (t("comp_bateria_restante", minutos=bateria["minutos_restantes"])
                        if bateria["minutos_restantes"] else "")
            texto_bateria = t("comp_bateria_texto", pct=f'{bateria["porcentaje"]:.0f}',
                              estado=estado, restante=restante)
        else:
            texto_bateria = t("comp_sin_bateria")
        self.panel_bateria.configure(text=texto_bateria)

        uptime = datos["uptime"]
        horas = int(uptime // 3600)
        minutos = int((uptime % 3600) // 60)
        info = self._system_info_cache
        self.panel_sistema.configure(text=t("comp_sistema_texto",
            placa=info.get("placa_madre", t("comp_no_disponible")),
            bios=info.get("bios", t("comp_no_disponible")),
            horas=horas, minutos=minutos, procesos=datos["procesos"]))

    def _abrir_ventana_speedtest(self):
        """Ventana dedicada para el test de velocidad — antes era solo una
        etiqueta apretada dentro de la tarjeta de Red; ahora tiene su
        propia ventana con progreso en vivo, resultado grande y un botón
        de reintentar, sin depender de que la pantalla Componentes siga
        abierta (evita que un resultado tardío intente pintar sobre un
        widget de una visita anterior ya destruido)."""
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comp_st_ventana"))
        dialogo.geometry("380x300")
        dialogo.resizable(False, False)
        dialogo.grab_set()

        ctk.CTkLabel(dialogo, text=t("comp_st_titulo"),
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("comp_preparando"), font=ctk.CTkFont(size=12),
                                   text_color="gray60", wraplength=320, justify="center")
        lbl_estado.pack(pady=(0, 2))
        ctk.CTkLabel(dialogo, text=t("comp_st_datos"), font=ctk.CTkFont(size=10),
                     text_color="gray50", wraplength=320, justify="center").pack(pady=(0, 10))

        barra = ctk.CTkProgressBar(dialogo, width=280)
        barra.set(0)
        barra.pack(pady=(0, 20))

        lbl_bajada = ctk.CTkLabel(dialogo, text="", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_bajada.pack()
        lbl_subida = ctk.CTkLabel(dialogo, text="", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_subida.pack()

        fila_botones = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila_botones.pack(side="bottom", pady=16)
        ctk.CTkButton(fila_botones, text=t("comun_cerrar"), fg_color="gray40",
                      command=dialogo.destroy).pack(
            side="left", padx=6)
        btn_reintentar = ctk.CTkButton(fila_botones, text=t("comp_btn_reintentar"), width=110,
                                       state="disabled")
        btn_reintentar.pack(side="left", padx=6)
        btn_reintentar.configure(
            command=lambda: self._ejecutar_speedtest(dialogo, lbl_estado, barra, lbl_bajada, lbl_subida, btn_reintentar))

        self._ejecutar_speedtest(dialogo, lbl_estado, barra, lbl_bajada, lbl_subida, btn_reintentar)

    def _ejecutar_speedtest(self, dialogo, lbl_estado, barra, lbl_bajada, lbl_subida, btn_reintentar):
        if not dialogo.winfo_exists():
            return
        # opt.test_velocidad_internet avisa la fase con un CODIGO estable, no
        # con texto: antes este mapa estaba indexado por las frases en espanol
        # que producia el optimizador, asi que en cuanto ese texto cambiara de
        # idioma el .get() habria caido siempre en el 0.5 por defecto y la
        # barra de progreso habria dejado de avanzar.
        FASES = {
            "conexion": (t("comp_st_fase_conexion"), 0.15),
            "bajada": (t("comp_st_fase_bajada"), 0.45),
            "subida": (t("comp_st_fase_subida"), 0.80),
            "listo": (t("comp_st_fase_listo"), 1.0),
        }
        btn_reintentar.configure(state="disabled")
        lbl_bajada.configure(text="")
        lbl_subida.configure(text="")
        lbl_estado.configure(text=t("comp_preparando"), text_color="gray60")
        barra.set(0)

        # BUG corregido: si la conexión se quedaba a medias (por ejemplo,
        # la resolución de DNS de Windows puede tardar más de lo que
        # cualquier "timeout" de Python alcanza a cubrir en ciertas redes
        # con firewall/antivirus/VPN), la ventana se quedaba cargando para
        # siempre, sin ningún mensaje ni forma de reintentar. Ahora hay un
        # límite de tiempo total: si en 35 segundos no terminó, se avisa y
        # se reactiva "Reintentar", sin importar en qué paso se haya
        # atascado el intento anterior (que sigue en su hilo, abandonado).
        estado_interno = {"completado": False}

        def progreso(codigo):
            if dialogo.winfo_exists():
                texto, avance = FASES.get(codigo, (codigo, 0.5))
                self.after(0, lambda: (lbl_estado.configure(text=texto),
                                        barra.set(avance)))

        def worker():
            resultado = opt.test_velocidad_internet(callback_progreso=progreso)

            def pintar():
                estado_interno["completado"] = True
                if not dialogo.winfo_exists():
                    return
                barra.set(1.0)
                btn_reintentar.configure(state="normal")
                if resultado["bajada_mbps"] is None:
                    lbl_estado.configure(text=resultado["error"], text_color=COLOR_CRIT)
                    return
                lbl_bajada.configure(text=t("comp_st_bajada", mbps=resultado["bajada_mbps"]),
                                     text_color=COLOR_OK)
                if resultado["subida_mbps"] is not None:
                    lbl_subida.configure(text=t("comp_st_subida", mbps=resultado["subida_mbps"]),
                                         text_color=COLOR_OK)
                    lbl_estado.configure(text=t("comp_st_aproximado"), text_color="gray60")
                else:
                    lbl_estado.configure(text=resultado["error"], text_color=COLOR_WARN)
            self.after(0, pintar)

            resumen = (t("comp_st_resumen", bajada=resultado["bajada_mbps"],
                         subida=resultado["subida_mbps"])
                       if resultado["bajada_mbps"] is not None else resultado["error"])
            self._log_dev(t("comp_log_speedtest"), "Descarga/subida de prueba a speed.cloudflare.com",
                          resumen, seccion=t("seccion_componentes"), exito=resultado["bajada_mbps"] is not None)
        threading.Thread(target=worker, daemon=True).start()

        def watchdog():
            if not dialogo.winfo_exists() or estado_interno["completado"]:
                return
            lbl_estado.configure(text=t("comp_st_timeout"), text_color=COLOR_CRIT)
            btn_reintentar.configure(state="normal")
        self.after(35000, watchdog)

    def _exportar_reporte_hardware(self):
        def worker():
            info = self._system_info_cache
            cpu = sysmon.get_cpu_details()
            gpu = sysmon.get_gpu_info()
            ram = sysmon.get_ram_info()
            ram_sticks = sysmon.get_ram_sticks()
            particiones = sysmon.get_disk_partitions()
            bateria = sysmon.get_battery_info()

            lineas = [
                t("comp_hw_titulo"),
                "=" * 60,
                t("comp_hw_generado", fecha=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                "",
                t("comp_hw_sec_sistema"),
                t("comp_hw_equipo", valor=info["hostname"]),
                t("comp_hw_so", valor=info["sistema_operativo"]),
                t("comp_hw_placa", valor=info.get("placa_madre", t("comp_no_disponible"))),
                t("comp_hw_bios", valor=info.get("bios", t("comp_no_disponible"))),
                "",
                t("comp_hw_sec_cpu"),
                t("comp_hw_modelo", valor=info["procesador"]),
                t("comp_hw_nucleos", fisicos=cpu["nucleos_fisicos"], logicos=cpu["nucleos_logicos"]),
                t("comp_hw_frec_max", valor=cpu["frecuencia_max_mhz"] or t("comp_nd")),
                "",
                t("comp_hw_sec_ram"),
                t("comp_hw_total", valor=ram["total_gb"]),
            ]
            for m in ram_sticks:
                lineas.append("  " + t("comp_ram_modulo", ranura=m["ranura"],
                                       capacidad=m["capacidad_gb"],
                                       velocidad=m["velocidad_mhz"] or t("comp_nd"),
                                       fabricante=m["fabricante"]))
            lineas += ["", t("comp_hw_sec_gpu"), t("comp_hw_modelo", valor=gpu["nombre"])]
            if gpu.get("vram_total_gb"):
                lineas.append(t("comp_hw_vram", valor=gpu["vram_total_gb"]))
            lineas += ["", t("comp_hw_sec_disco")]
            for p in particiones:
                lineas.append(t("comp_hw_particion", unidad=p["unidad"], total=p["total_gb"],
                                libre=p["libre_gb"]))
            if bateria:
                lineas += ["", t("comp_hw_sec_bateria"), f'{bateria["porcentaje"]:.0f}%']

            # El respaldo ya no es BASE_DIR: en la build --onefile de
            # PyInstaller esa es la carpeta temporal donde se descomprime
            # el .exe y Windows la borra al cerrar la app, asi que el
            # archivo se "guardaba" y desaparecia solo. carpeta_datos()
            # apunta a %APPDATA% + TechCleanPro, que si persiste.
            carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
            destino = os.path.join(carpeta, "reporte_hardware_techclean.txt")
            try:
                with open(destino, "w", encoding="utf-8") as f:
                    f.write("\n".join(lineas))
            except Exception:
                destino = os.path.join(prefs.carpeta_datos(), "reporte_hardware_techclean.txt")
                with open(destino, "w", encoding="utf-8") as f:
                    f.write("\n".join(lineas))

            self.after(0, lambda: self._mostrar_popup_info(
                t("hist_hardware_exportado_titulo"), t("hist_exportado_msg", ruta=destino)))
            self._log_dev("Exportar reporte de hardware", "N/A", f"Guardado en {destino}",
                          seccion=t("seccion_componentes"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Drivers (informativo + canales oficiales) ----------------
    def mostrar_drivers(self):
        self._limpiar_contenido()
        ctk.CTkButton(self.contenido, text=t("drv_volver"), fg_color="transparent",
                      hover_color="#2a2d36", width=160, command=self.mostrar_componentes).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        ctk.CTkLabel(self.contenido, text=t("drv_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self.contenido,
                     text=t("drv_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        panel_top = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_top.grid(row=3, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 8))
        self.fila_fab = ctk.CTkFrame(panel_top, fg_color="transparent")
        self.fila_fab.pack(fill="x", padx=16, pady=14)
        self.lbl_fabricante = ctk.CTkLabel(self.fila_fab, text=t("drv_leyendo_fabricante"),
                                            font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_fabricante.pack(side="left")
        ctk.CTkButton(self.fila_fab, text=t("drv_btn_admin_disp"), width=200, fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_admin_dispositivos).pack(
            side="right", padx=(0, 8))

        def worker_fab():
            info_fab = opt.obtener_fabricante_soporte()
            self.after(0, lambda: self._pintar_fabricante(info_fab))
        threading.Thread(target=worker_fab, daemon=True).start()

        # ---- Dispositivos sin driver o con problemas ----
        # Justo lo que hace falta después de una instalación limpia de
        # Windows: no "qué drivers ya están instalados" (eso es la lista
        # de abajo), sino "qué le falta a Windows por reconocer todavía".
        panel_problemas = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_problemas.grid(row=4, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 8))
        ctk.CTkLabel(panel_problemas, text=t("drv_problemas_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(panel_problemas,
                     text=t("drv_problemas_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=900, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10))
        fila_escanear = ctk.CTkFrame(panel_problemas, fg_color="transparent")
        fila_escanear.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(fila_escanear, text=t("drv_btn_escanear"), width=200,
                      command=self._accion_escanear_hardware).pack(side="left")
        self.lbl_escanear_hardware = ctk.CTkLabel(fila_escanear, text="", font=ctk.CTkFont(size=11),
                                                    text_color="gray60")
        self.lbl_escanear_hardware.pack(side="left", padx=12)
        self.lista_dispositivos_problema = ctk.CTkScrollableFrame(panel_problemas, fg_color="#141720",
                                                                     corner_radius=10, height=160)
        self.lista_dispositivos_problema.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(self.lista_dispositivos_problema, text=t("drv_revisando"),
                     text_color="gray60").pack(
            padx=8, pady=8)

        def worker_problemas():
            problemas = sysmon.listar_dispositivos_con_problemas()
            self.after(0, lambda: self._pintar_dispositivos_problema(problemas))
        threading.Thread(target=worker_problemas, daemon=True).start()

        fila_buscar = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_buscar.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ctk.CTkButton(fila_buscar, text=t("drv_btn_buscar_update"),
                      command=self._accion_buscar_drivers_update).pack(side="left")
        self.lbl_drivers_update = ctk.CTkLabel(fila_buscar, text="", font=ctk.CTkFont(size=12), text_color="gray60")
        self.lbl_drivers_update.pack(side="left", padx=12)

        fila_inicio_rapido = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_inicio_rapido.grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 10))
        ctk.CTkLabel(fila_inicio_rapido, text=t("drv_inicio_rapido_label"),
                     font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(0, 8))
        self.lbl_estado_inicio_rapido = ctk.CTkLabel(fila_inicio_rapido, text=t("drv_leyendo_minus"),
                                                       font=ctk.CTkFont(size=12), text_color="gray60")
        self.lbl_estado_inicio_rapido.pack(side="left", padx=(0, 10))
        self.switch_inicio_rapido = ctk.CTkSwitch(fila_inicio_rapido, text="",
                                                    command=self._toggle_inicio_rapido)
        self.switch_inicio_rapido.pack(side="left")
        ctk.CTkLabel(self.contenido,
                     text=t("drv_inicio_rapido_nota"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=900, justify="left").grid(
            row=7, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 10))

        def worker_inicio_rapido():
            estado = opt.obtener_estado_inicio_rapido()
            self.after(0, lambda: self._pintar_estado_inicio_rapido(estado))
        threading.Thread(target=worker_inicio_rapido, daemon=True).start()

        self.entry_buscar_driver = ctk.CTkEntry(self.contenido,
                                                placeholder_text=t("drv_buscar_placeholder"))
        self.entry_buscar_driver.grid(row=8, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 6))
        self.entry_buscar_driver.bind("<KeyRelease>", lambda e: self._filtrar_drivers())

        self.contenido.grid_rowconfigure(9, weight=1)
        self.lista_drivers = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_drivers.grid(row=9, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)
        ctk.CTkLabel(self.lista_drivers,
                     text=t("drv_leyendo_drivers_largo"),
                     text_color="gray60", wraplength=850, justify="left").pack(padx=16, pady=16)
        self._drivers_cache = None

        def worker():
            drivers = sysmon.listar_drivers()
            self._drivers_cache = drivers
            self.after(0, self._filtrar_drivers)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_dispositivos_problema(self, problemas):
        if not (hasattr(self, "lista_dispositivos_problema") and self.lista_dispositivos_problema.winfo_exists()):
            return
        for w in self.lista_dispositivos_problema.winfo_children():
            w.destroy()
        if not problemas:
            ctk.CTkLabel(self.lista_dispositivos_problema,
                         text=t("drv_sin_problemas"),
                         text_color=COLOR_OK).pack(padx=8, pady=8, anchor="w")
            return
        for d in problemas:
            fila = ctk.CTkFrame(self.lista_dispositivos_problema, fg_color=COLOR_BG_PANEL, corner_radius=8)
            fila.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(fila, text=t("drv_dispositivo_problema", nombre=d["nombre"]),
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").pack(fill="x", padx=10, pady=(8, 0), anchor="w")
            ctk.CTkLabel(fila, text=d["explicacion"], font=ctk.CTkFont(size=11), text_color="gray60",
                         anchor="w", wraplength=820, justify="left").pack(fill="x", padx=10, pady=(0, 4), anchor="w")
            if d["device_id"]:
                fila_id = ctk.CTkFrame(fila, fg_color="transparent")
                fila_id.pack(fill="x", padx=10, pady=(0, 8))
                entry_id = ctk.CTkEntry(fila_id, font=ctk.CTkFont(size=10, family="Consolas"))
                entry_id.insert(0, d["device_id"])
                entry_id.configure(state="readonly")
                entry_id.pack(side="left", fill="x", expand=True, padx=(0, 8))
                ctk.CTkButton(fila_id, text=t("drv_btn_copiar_id"), width=90,
                              command=lambda v=d["device_id"]: self._copiar_al_portapapeles(v)).pack(side="left")

    def _accion_escanear_hardware(self):
        self.lbl_escanear_hardware.configure(text=t("drv_buscando_hardware"))

        def worker():
            exito, comando = opt.escanear_hardware_nuevo()
            msg = t("drv_escaneo_ok") if exito else t("drv_escaneo_error")
            self._log_dev(t("drv_log_escanear"), comando, msg,
                          seccion=t("seccion_drivers"), exito=exito)
            if hasattr(self, "lbl_escanear_hardware") and self.lbl_escanear_hardware.winfo_exists():
                self.after(0, lambda: self.lbl_escanear_hardware.configure(text=msg))
            # Refrescar la lista de problemas después del escaneo, ya que
            # pudo haber resuelto alguno.
            def worker_refrescar():
                problemas = sysmon.listar_dispositivos_con_problemas()
                self.after(0, lambda: self._pintar_dispositivos_problema(problemas))
            threading.Thread(target=worker_refrescar, daemon=True).start()
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_estado_inicio_rapido(self, estado):
        if not (hasattr(self, "lbl_estado_inicio_rapido") and self.lbl_estado_inicio_rapido.winfo_exists()):
            return
        if estado is None:
            self.lbl_estado_inicio_rapido.configure(text=t("drv_ir_no_disponible"))
            self.switch_inicio_rapido.configure(state="disabled")
            return
        self.lbl_estado_inicio_rapido.configure(
            text=t("drv_ir_activado") if estado else t("drv_ir_desactivado"))
        if estado:
            self.switch_inicio_rapido.select()
        else:
            self.switch_inicio_rapido.deselect()

    def _toggle_inicio_rapido(self):
        activar = bool(self.switch_inicio_rapido.get())
        self.lbl_estado_inicio_rapido.configure(text=t("drv_ir_aplicando"))

        def worker():
            exito, comando = opt.set_inicio_rapido(activar)
            texto = ((t("drv_ir_activado") if activar else t("drv_ir_desactivado")) if exito
                     else t("drv_ir_error"))
            self._log_dev(t("drv_log_inicio_rapido"), comando,
                          t("drv_ir_resultado", estado=texto),
                          seccion=t("seccion_drivers"), exito=exito)
            if hasattr(self, "lbl_estado_inicio_rapido") and self.lbl_estado_inicio_rapido.winfo_exists():
                self.after(0, lambda: self.lbl_estado_inicio_rapido.configure(text=texto))
        threading.Thread(target=worker, daemon=True).start()

    def _filtrar_drivers(self):
        if not (hasattr(self, "lista_drivers") and self.lista_drivers.winfo_exists()):
            return
        for w in self.lista_drivers.winfo_children():
            w.destroy()

        drivers = self._drivers_cache
        if drivers is None:
            ctk.CTkLabel(self.lista_drivers, text=t("drv_leyendo_drivers"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        if not drivers:
            ctk.CTkLabel(self.lista_drivers, text=t("drv_sin_drivers"),
                         text_color="gray60").pack(padx=16, pady=16)
            return

        termino = self.entry_buscar_driver.get().strip().lower() if hasattr(self, "entry_buscar_driver") else ""
        if termino:
            drivers = [d for d in drivers if termino in d["nombre"].lower() or termino in d["fabricante"].lower()]

        for d in drivers[:300]:
            fila = ctk.CTkFrame(self.lista_drivers, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            texto = t("drv_detalle", nombre=d["nombre"], fabricante=d["fabricante"],
                      version=d["version"], fecha=d["fecha"])
            ctk.CTkLabel(fila, text=texto, font=ctk.CTkFont(size=12), anchor="w",
                         wraplength=900, justify="left").pack(padx=12, pady=8, fill="x", expand=True, anchor="w")

    def _accion_buscar_drivers_update(self):
        self.lbl_drivers_update.configure(text=t("drv_buscando_update"))

        def worker():
            exito, titulos, comando = opt.buscar_actualizaciones_drivers()
            if not exito:
                texto = t("drv_update_error")
            elif not titulos:
                texto = t("drv_update_ninguna")
            else:
                texto = t("drv_update_disponibles", cantidad=len(titulos),
                          lista="; ".join(titulos[:5]))
            if hasattr(self, "lbl_drivers_update") and self.lbl_drivers_update.winfo_exists():
                self.after(0, lambda: self.lbl_drivers_update.configure(text=texto))
            self._log_dev(t("drv_log_buscar_update"), comando, texto,
                          seccion=t("seccion_componentes"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_fabricante(self, info_fab):
        if not (hasattr(self, "lbl_fabricante") and self.lbl_fabricante.winfo_exists()):
            return
        self.lbl_fabricante.configure(text=t("drv_fabricante_modelo",
                                             fabricante=info_fab["fabricante"],
                                             modelo=info_fab["modelo"]))
        if info_fab["url_soporte"] and hasattr(self, "fila_fab") and self.fila_fab.winfo_exists():
            # webbrowser.open lanza un proceso del sistema: va en un hilo, igual
            # que el boton de donacion, para no congelar la ventana si el
            # navegador esta frio.
            ctk.CTkButton(self.fila_fab, text=t("drv_btn_soporte"), width=200,
                          command=lambda u=info_fab["url_soporte"]: threading.Thread(
                              target=lambda: webbrowser.open(u), daemon=True).start()).pack(side="right")

    def _accion_abrir_admin_dispositivos(self):
        exito, comando = opt.abrir_administrador_dispositivos()
        self._log_dev(t("drv_log_admin_disp"), comando,
                      t("drv_admin_disp_ok") if exito else t("comp_no_abrir"),
                      seccion=t("seccion_componentes"), exito=exito)

    # ---------------- Optimizador ----------------
    def mostrar_optimizador(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("opt_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        # Con perfiles de energía + analizador de disco agregados, ya no
        # cabía todo en pantalla sin scroll — un solo contenedor con scroll
        # envuelve los tres paneles en vez de que cada uno viva suelto en
        # self.contenido (que no tiene scroll propio).
        self.contenido.grid_rowconfigure(1, weight=1)
        contenedor = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        contenedor.grid(row=1, column=0, columnspan=3, sticky="nswe")

        panel = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.pack(fill="x", padx=8, pady=8)

        self.lbl_resultado_opt = ctk.CTkLabel(panel, text=t("opt_selecciona"),
                                               font=ctk.CTkFont(size=13), wraplength=800, justify="left")
        self.lbl_resultado_opt.pack(padx=16, pady=16, anchor="w")

        botones = [
            (t("opt_btn_ram"), self._accion_liberar_ram),
            (t("opt_btn_estimar"), self._accion_estimar_espacio),
            (t("opt_btn_temp"), self._accion_limpiar_temp),
            (t("opt_btn_papelera"), self._accion_vaciar_papelera),
            (t("opt_btn_dns"), self._accion_flush_dns),
            (t("opt_btn_miniaturas"), self._accion_limpiar_miniaturas),
        ]
        fila_botones = ctk.CTkFrame(panel, fg_color="transparent")
        fila_botones.pack(padx=16, pady=(0, 8), fill="x")
        for texto, cmd in botones:
            ctk.CTkButton(fila_botones, text=texto, command=cmd).pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(panel,
                     text=t("opt_tip_estimar"),
                     font=ctk.CTkFont(size=11), text_color="gray50", wraplength=800, justify="left").pack(
            padx=16, pady=(0, 8), anchor="w")

        fila_unica = ctk.CTkFrame(panel, fg_color="transparent")
        fila_unica.pack(padx=16, pady=(0, 8), fill="x")
        ctk.CTkLabel(fila_unica, text=t("opt_limpieza_unica_label"),
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.combo_minutos_unica = ctk.CTkOptionMenu(fila_unica, values=["5 min", "15 min", "30 min", "60 min"], width=90)
        self.combo_minutos_unica.pack(side="left", padx=8)
        ctk.CTkButton(fila_unica, text=t("opt_btn_programar"), width=100,
                      command=self._accion_limpieza_unica).pack(side="left")

        self._boton_ver_reporte(panel)

        # ---- Perfiles de energía ----
        panel_perfiles = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_perfiles.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(panel_perfiles, text=t("opt_perfiles_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        self.lbl_perfil_actual = ctk.CTkLabel(
            panel_perfiles, text=t("opt_plan_cargando"),
            font=ctk.CTkFont(size=12), text_color="gray70")
        self.lbl_perfil_actual.pack(anchor="w", padx=16, pady=(0, 8))
        self._actualizar_lbl_perfil_actual()

        fila_perfiles = ctk.CTkFrame(panel_perfiles, fg_color="transparent")
        fila_perfiles.pack(padx=16, pady=(0, 16), fill="x")
        # La clave ("silencioso"/"equilibrado"/"rendimiento") es interna y NO se
        # traduce: es lo que entiende opt.set_power_plan() y lo que se guarda en
        # preferencias. Solo se traduce la etiqueta visible, que ahora se pasa
        # aparte para que los mensajes no muestren la clave interna al usuario.
        perfiles = [
            (t("opt_perfil_silencioso"), "silencioso"),
            (t("opt_perfil_equilibrado"), "equilibrado"),
            (t("opt_perfil_rendimiento"), "rendimiento"),
        ]
        for texto, clave in perfiles:
            ctk.CTkButton(fila_perfiles, text=texto,
                          command=lambda c=clave, n=texto: self._accion_cambiar_perfil(c, n)).pack(
                side="left", padx=6, pady=6)

        # ---- Analizador de espacio en disco ----
        panel_disco = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_disco.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(panel_disco, text=t("opt_disco_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(panel_disco,
                     text=t("opt_disco_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10))
        ctk.CTkButton(panel_disco, text=t("opt_btn_analizar"),
                      command=self.mostrar_espacio_disco).pack(anchor="w", padx=16, pady=(0, 16))

        # ---- Qué está usando la RAM o el CPU, y qué apps tienes abiertas ----
        panel_ram_procesos = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_ram_procesos.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(panel_ram_procesos, text=t("opt_procesos_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(panel_ram_procesos,
                     text=t("opt_procesos_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10))
        fila_modo_procesos = ctk.CTkFrame(panel_ram_procesos, fg_color="transparent")
        fila_modo_procesos.pack(fill="x", padx=16, pady=(0, 8))
        self.pestana_procesos = ctk.CTkSegmentedButton(
            fila_modo_procesos,
            values=[t("opt_tab_ram"), t("opt_tab_cpu"), t("opt_tab_ventanas")],
            command=self._cambiar_modo_procesos)
        self.pestana_procesos.set(t("opt_tab_ram"))
        self.pestana_procesos.pack(side="left", padx=(0, 10))
        ctk.CTkButton(fila_modo_procesos, text=t("opt_btn_actualizar"),
                      command=lambda: self._mostrar_procesos_recursos(
                          self._modo_procesos_actual())).pack(
            side="left")
        self.lista_procesos_ram = ctk.CTkScrollableFrame(panel_ram_procesos, fg_color="#141720",
                                                           corner_radius=10, height=260)
        self.lista_procesos_ram.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(self.lista_procesos_ram, text=t("opt_presiona_actualizar"),
                     text_color="gray60").pack(padx=8, pady=8)

    def _codigo_modo_procesos(self, valor):
        """Traduce el texto visible de la pestaña a un código interno estable.

        BUG evitado: antes el resto del código comparaba el valor de la
        pestaña contra los literales "RAM"/"CPU"/"Ventanas". Al traducir la
        pestaña, "Ventanas" pasa a ser "Windows" en la build en inglés y esas
        comparaciones fallaban: _pintar_procesos_recursos se iba por la rama
        de procesos con datos de ventanas y reventaba con KeyError. Ahora el
        texto visible se convierte a código UNA vez, aquí, y todo lo demás
        trabaja con "ram"/"cpu"/"ventanas", que nunca se traducen."""
        if valor == t("opt_tab_cpu"):
            return "cpu"
        if valor == t("opt_tab_ventanas"):
            return "ventanas"
        return "ram"

    def _modo_procesos_actual(self):
        """Código del modo seleccionado ahora mismo (o "ram" si aún no hay)."""
        if hasattr(self, "pestana_procesos") and self.pestana_procesos.winfo_exists():
            return self._codigo_modo_procesos(self.pestana_procesos.get())
        return "ram"

    def _cambiar_modo_procesos(self, valor):
        self._mostrar_procesos_recursos(self._codigo_modo_procesos(valor))

    def _accion_cambiar_perfil(self, clave, nombre=None):
        # BUG corregido: antes se mostraba la CLAVE INTERNA ("silencioso") en
        # los mensajes. En la build en inglés eso habría dicho "Switching to
        # the 'silencioso' profile...". Ahora se muestra el nombre traducido
        # y la clave se usa solo para hablar con powercfg y guardar prefs.
        nombre = nombre or clave
        self.lbl_resultado_opt.configure(text=t("opt_cambiando_perfil", perfil=nombre))

        def worker():
            exito, comando = opt.set_power_plan(clave)
            msg = (t("opt_perfil_cambiado", perfil=nombre) if exito
                   else t("opt_perfil_error"))
            self.after(0, lambda: self.lbl_resultado_opt.configure(text=msg))
            self._log_dev(t("opt_log_perfil", perfil=nombre), comando, msg,
                          seccion=t("seccion_optimizador"), exito=exito)
            if exito:
                self.prefs["perfil_energia"] = clave
                prefs.guardar({"perfil_energia": clave})
            self.after(0, self._actualizar_lbl_perfil_actual)
        threading.Thread(target=worker, daemon=True).start()

    def _actualizar_lbl_perfil_actual(self):
        """Consulta el plan de energía activo en un hilo aparte (powercfg es
        rápido, pero sigue siendo un subproceso — nunca directo en el hilo
        de la interfaz) y actualiza la etiqueta cuando termina."""
        # BUG corregido: winfo_exists() es una llamada a Tk y se estaba
        # haciendo desde este hilo de fondo, no desde el principal — además
        # de que entre esa comprobación y el after() el widget podía morir.
        # Ahora el hilo solo consulta powercfg y la comprobación ocurre ya
        # dentro del hilo principal, justo antes de tocar el widget.
        def pintar(actual):
            if hasattr(self, "lbl_perfil_actual") and self.lbl_perfil_actual.winfo_exists():
                self.lbl_perfil_actual.configure(
                    text=t("opt_plan_activo", plan=actual or t("opt_plan_no_leido")))

        def worker():
            actual = opt.get_active_power_plan_name()
            self.after(0, lambda: pintar(actual))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Analizador de espacio en disco ----------------
    def mostrar_espacio_disco(self):
        self._limpiar_contenido()
        ctk.CTkButton(self.contenido, text=t("opt_volver"), fg_color="transparent",
                      hover_color="#2a2d36", width=140, command=self.mostrar_optimizador).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        ctk.CTkLabel(self.contenido, text=t("disco_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.pestana_disco = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("disco_tab_carpetas"), t("disco_tab_archivos"),
                    t("disco_tab_instaladores"), t("disco_tab_cache")],
            command=self._cambiar_pestana_disco)
        self.pestana_disco.set(t("disco_tab_carpetas"))
        self.pestana_disco.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(3, weight=1)
        self.contenedor_disco = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.contenedor_disco.grid(row=3, column=0, columnspan=3, sticky="nswe")
        self.contenedor_disco.grid_columnconfigure(0, weight=1)
        self.contenedor_disco.grid_rowconfigure(0, weight=1)

        self._mostrar_carpetas_pesadas()

    def _cambiar_pestana_disco(self, valor):
        """Cambia de pestaña a partir del TEXTO VISIBLE del botón segmentado.

        El texto está traducido, así que no se compara contra literales en
        español: se resuelve contra las mismas claves con las que se
        construyó el botón. Si no coincide ninguna, cae en Carpetas pesadas,
        que es la pestaña por defecto — nunca en una rama equivocada."""
        if valor == t("disco_tab_archivos"):
            self._mostrar_archivos_grandes()
        elif valor == t("disco_tab_instaladores"):
            self._mostrar_instaladores_viejos()
        elif valor == t("disco_tab_cache"):
            self._mostrar_cache_apps()
        else:
            self._mostrar_carpetas_pesadas()

    def _limpiar_contenedor_disco(self):
        for w in self.contenedor_disco.winfo_children():
            w.destroy()

    # ---- Pestaña: Carpetas pesadas ----
    def _mostrar_carpetas_pesadas(self):
        self._limpiar_contenedor_disco()
        fila = ctk.CTkFrame(self.contenedor_disco, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        unidades = [p["unidad"] for p in sysmon.get_disk_partitions()] or ["C:\\"]
        self.combo_unidad_disco = ctk.CTkOptionMenu(fila, values=unidades, width=100)
        self.combo_unidad_disco.pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila, text=t("disco_btn_analizar"),
                      command=self._accion_analizar_disco).pack(side="left")

        self.lista_espacio_disco = ctk.CTkScrollableFrame(self.contenedor_disco, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_espacio_disco.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_espacio_disco,
                     text=t("disco_elige_unidad"),
                     text_color="gray60").pack(padx=16, pady=16)

    def _accion_analizar_disco(self):
        unidad = self.combo_unidad_disco.get()
        for w in self.lista_espacio_disco.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_espacio_disco, text=t("disco_analizando", unidad=unidad),
                     text_color="gray60").pack(padx=16, pady=16)

        def worker():
            carpetas = opt.listar_carpetas_pesadas(unidad, top_n=15, max_profundidad=2)
            self.after(0, lambda: self._pintar_espacio_disco(unidad, carpetas))
            self._log_dev(t("disco_log_analizar", unidad=unidad),
                          t("disco_log_analizar_cmd", unidad=unidad),
                          t("disco_carpetas_encontradas", cantidad=len(carpetas)),
                          seccion=t("seccion_optimizador"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_espacio_disco(self, unidad, carpetas):
        if not (hasattr(self, "lista_espacio_disco") and self.lista_espacio_disco.winfo_exists()):
            return
        for w in self.lista_espacio_disco.winfo_children():
            w.destroy()

        if not carpetas:
            ctk.CTkLabel(self.lista_espacio_disco,
                         text=t("disco_unidad_vacia"), text_color="gray60").pack(
                padx=16, pady=16)
            return

        maximo = max(c["bytes"] for c in carpetas) or 1
        for c in carpetas:
            fila = ctk.CTkFrame(self.lista_espacio_disco, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=4)
            ctk.CTkLabel(fila, text=c["ruta"], font=ctk.CTkFont(size=12), anchor="w",
                         wraplength=550, justify="left").pack(side="left", padx=12, pady=10, fill="x", expand=True)
            barra = ctk.CTkProgressBar(fila, width=120)
            barra.set(c["bytes"] / maximo)
            barra.pack(side="left", padx=8)
            ctk.CTkLabel(fila, text=opt.format_bytes(c["bytes"]), font=ctk.CTkFont(size=12, weight="bold"),
                         width=90).pack(side="left", padx=(8, 12))

    # ---- Pestaña: Archivos grandes individuales ----
    def _mostrar_archivos_grandes(self):
        self._limpiar_contenedor_disco()
        fila = ctk.CTkFrame(self.contenedor_disco, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        unidades = [p["unidad"] for p in sysmon.get_disk_partitions()] or ["C:\\"]
        self.combo_unidad_archivos = ctk.CTkOptionMenu(fila, values=unidades, width=100)
        self.combo_unidad_archivos.pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila, text=t("disco_btn_buscar_grandes"),
                      command=self._accion_buscar_archivos_grandes).pack(side="left")

        self.lista_archivos_grandes = ctk.CTkScrollableFrame(self.contenedor_disco, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_archivos_grandes.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_archivos_grandes,
                     text=t("disco_archivos_intro"),
                     text_color="gray60").pack(padx=16, pady=16)

    def _accion_buscar_archivos_grandes(self):
        unidad = self.combo_unidad_archivos.get()
        for w in self.lista_archivos_grandes.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_archivos_grandes, text=t("disco_buscando_en", unidad=unidad),
                     text_color="gray60").pack(
            padx=16, pady=16)

        def worker():
            archivos = opt.listar_archivos_grandes(unidad, min_mb=100, limite=30)
            self.after(0, lambda: self._pintar_archivos_grandes(archivos))
            self._log_dev(t("disco_log_buscar_grandes", unidad=unidad), t("disco_log_buscar_cmd"),
                          t("disco_archivos_encontrados", cantidad=len(archivos)),
                          seccion=t("seccion_optimizador"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_archivos_grandes(self, archivos):
        if not (hasattr(self, "lista_archivos_grandes") and self.lista_archivos_grandes.winfo_exists()):
            return
        for w in self.lista_archivos_grandes.winfo_children():
            w.destroy()
        if not archivos:
            ctk.CTkLabel(self.lista_archivos_grandes,
                         text=t("disco_sin_archivos_grandes"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        for a in archivos:
            fila = ctk.CTkFrame(self.lista_archivos_grandes, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=4)
            ctk.CTkLabel(fila, text=a["ruta"], font=ctk.CTkFont(size=11), anchor="w",
                         wraplength=520, justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            ctk.CTkLabel(fila, text=opt.format_bytes(a["bytes"]), font=ctk.CTkFont(size=12, weight="bold"),
                         width=80).pack(side="left", padx=4)
            ctk.CTkButton(fila, text=t("disco_btn_papelera_uno"), width=110, fg_color="#2a2d36",
                          hover_color="#3a3e4a",
                          command=lambda r=a["ruta"]: self._confirmar_borrar_archivos([r])).pack(
                side="left", padx=(4, 12), pady=8)

    # ---- Pestaña: Instaladores viejos ----
    def _mostrar_instaladores_viejos(self):
        self._limpiar_contenedor_disco()
        ctk.CTkLabel(self.contenedor_disco,
                     text=t("disco_instaladores_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        self.lista_instaladores = ctk.CTkScrollableFrame(self.contenedor_disco, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_instaladores.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_instaladores, text=t("disco_buscando"),
                     text_color="gray60").pack(padx=16, pady=16)

        def worker():
            instaladores = opt.listar_instaladores_viejos(dias=30)
            self.after(0, lambda: self._pintar_instaladores_viejos(instaladores))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_instaladores_viejos(self, instaladores):
        if not (hasattr(self, "lista_instaladores") and self.lista_instaladores.winfo_exists()):
            return
        for w in self.lista_instaladores.winfo_children():
            w.destroy()
        if not instaladores:
            ctk.CTkLabel(self.lista_instaladores, text=t("disco_sin_instaladores"),
                         text_color="gray60").pack(padx=16, pady=16)
            return

        fila_top = ctk.CTkFrame(self.lista_instaladores, fg_color="transparent")
        fila_top.pack(fill="x", padx=8, pady=8)
        total = sum(i["bytes"] for i in instaladores)
        ctk.CTkLabel(fila_top, text=t("disco_instaladores_total", cantidad=len(instaladores),
                                      tamano=opt.format_bytes(total)),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(fila_top, text=t("disco_btn_papelera_todos"), fg_color=COLOR_WARN, text_color="black",
                      command=lambda: self._confirmar_borrar_archivos([i["ruta"] for i in instaladores])).pack(
            side="right")

        for i in instaladores:
            fila = ctk.CTkFrame(self.lista_instaladores, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=4)
            nombre = os.path.basename(i["ruta"])
            dias = int((time.time() - i["mtime"]) / 86400)
            ctk.CTkLabel(fila, text=t("disco_archivo_dias", nombre=nombre, dias=dias),
                         font=ctk.CTkFont(size=12), anchor="w",
                         wraplength=520, justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            ctk.CTkLabel(fila, text=opt.format_bytes(i["bytes"]), font=ctk.CTkFont(size=12, weight="bold"),
                         width=80).pack(side="left", padx=4)
            ctk.CTkButton(fila, text="🗑", width=36, fg_color="#2a2d36", hover_color="#3a3e4a",
                          command=lambda r=i["ruta"]: self._confirmar_borrar_archivos([r])).pack(
                side="left", padx=(4, 12), pady=8)

    # ---- Pestaña: Caché de apps comunes ----
    def _mostrar_cache_apps(self):
        self._limpiar_contenedor_disco()
        ctk.CTkLabel(self.contenedor_disco,
                     text=t("disco_cache_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        self.lista_cache_apps = ctk.CTkScrollableFrame(self.contenedor_disco, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_cache_apps.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_cache_apps, text=t("disco_buscando"),
                     text_color="gray60").pack(padx=16, pady=16)

        def worker():
            items = opt.listar_cache_apps_comunes()
            self.after(0, lambda: self._pintar_cache_apps(items))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_cache_apps(self, items):
        if not (hasattr(self, "lista_cache_apps") and self.lista_cache_apps.winfo_exists()):
            return
        for w in self.lista_cache_apps.winfo_children():
            w.destroy()
        if not items:
            ctk.CTkLabel(self.lista_cache_apps,
                         text=t("disco_sin_cache"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        for it in items:
            fila = ctk.CTkFrame(self.lista_cache_apps, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=4)
            ctk.CTkLabel(fila, text=it["nombre"], font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(
                side="left", padx=12, pady=10, fill="x", expand=True)
            ctk.CTkLabel(fila, text=opt.format_bytes(it["bytes"]), font=ctk.CTkFont(size=12), width=90).pack(
                side="left", padx=4)
            ctk.CTkButton(fila, text=t("disco_btn_limpiar"), width=90,
                          command=lambda r=it["ruta"], n=it["nombre"]: self._accion_limpiar_cache_app(r, n)).pack(
                side="left", padx=(4, 12), pady=8)

    def _accion_limpiar_cache_app(self, ruta, nombre):
        def worker():
            liberado, comando = opt.limpiar_cache_app(ruta)
            msg = t("disco_cache_liberado", tamano=opt.format_bytes(liberado), nombre=nombre)
            self._log_dev(t("disco_log_limpiar_cache", nombre=nombre), comando, msg,
                          seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado)
            self.after(0, lambda: self._mostrar_cache_apps())
        threading.Thread(target=worker, daemon=True).start()

    # ---- Confirmación compartida para borrar archivos (envía a la papelera) ----
    def _confirmar_borrar_archivos(self, rutas):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar")
        dialogo.geometry("420x180")
        dialogo.grab_set()
        texto = (t("disco_conf_papelera_varios", cantidad=len(rutas)) if len(rutas) > 1
                 else t("disco_conf_papelera_uno", nombre=os.path.basename(rutas[0])))
        ctk.CTkLabel(dialogo, text=texto, font=ctk.CTkFont(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            def worker():
                eliminados, liberado, errores = opt.enviar_a_papelera(rutas)
                msg = (t("disco_papelera_ok", cantidad=eliminados, tamano=opt.format_bytes(liberado))
                       if eliminados else
                       t("disco_papelera_error",
                         errores="; ".join(errores) if errores else t("disco_error_desconocido")))
                self._log_dev(t("disco_log_papelera"), "SHFileOperationW (FO_DELETE, FOF_ALLOWUNDO)",
                              msg, seccion=t("seccion_optimizador"), exito=eliminados > 0, bytes_liberados=liberado)
                if hasattr(self, "pestana_disco") and self.pestana_disco.winfo_exists():
                    self.after(0, lambda: self._cambiar_pestana_disco(self.pestana_disco.get()))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("disco_btn_enviar_papelera"), fg_color=COLOR_WARN, text_color="black",
                      command=confirmar).pack(side="left", padx=8)

    def _accion_liberar_ram(self):
        def worker():
            liberado, afectados, comando = opt.trim_process_memory()
            msg = t("opt_ram_ok", procesos=afectados, tamano=opt.format_bytes(liberado))
            self.lbl_resultado_opt.configure(text=msg)
            self._log_dev(t("opt_log_ram"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado, archivos_afectados=afectados)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_liberando_ram"))

    def _mostrar_procesos_recursos(self, modo):
        for w in self.lista_procesos_ram.winfo_children():
            w.destroy()
        if modo == "ram":
            texto_espera = t("opt_leyendo_procesos")
        elif modo == "cpu":
            texto_espera = t("opt_midiendo_cpu")
        else:
            texto_espera = t("opt_leyendo_ventanas")
        ctk.CTkLabel(self.lista_procesos_ram, text=texto_espera, text_color="gray60").pack(padx=8, pady=8)

        def worker():
            if modo == "ram":
                procesos = opt.listar_procesos_por_ram(limite=15)
            elif modo == "cpu":
                procesos = opt.listar_procesos_por_cpu(limite=15)
            else:
                procesos = opt.listar_ventanas_abiertas()
            self.after(0, lambda: self._pintar_procesos_recursos(procesos, modo))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_procesos_recursos(self, procesos, modo):
        if not (hasattr(self, "lista_procesos_ram") and self.lista_procesos_ram.winfo_exists()):
            return
        for w in self.lista_procesos_ram.winfo_children():
            w.destroy()
        if not procesos:
            texto_vacio = (t("opt_sin_ventanas") if modo == "ventanas"
                            else t("opt_sin_procesos"))
            ctk.CTkLabel(self.lista_procesos_ram, text=texto_vacio, text_color="gray60").pack(padx=8, pady=8)
            return

        if modo == "ventanas":
            for v in procesos:
                riesgo, _ = opt.evaluar_riesgo_proceso(v["proceso"])
                fila = ctk.CTkFrame(self.lista_procesos_ram, fg_color=COLOR_BG_PANEL, corner_radius=8)
                fila.pack(fill="x", padx=4, pady=3)
                col_texto = ctk.CTkFrame(fila, fg_color="transparent")
                col_texto.pack(side="left", padx=10, pady=8, fill="x", expand=True)
                ctk.CTkLabel(col_texto, text=v["titulo"], font=ctk.CTkFont(size=12, weight="bold"),
                             anchor="w", wraplength=520).pack(fill="x", anchor="w")
                ctk.CTkLabel(col_texto, text=v["proceso"], font=ctk.CTkFont(size=11),
                             text_color="gray60", anchor="w").pack(fill="x", anchor="w")
                if riesgo == "bloqueado":
                    ctk.CTkButton(fila, text=t("opt_protegido"), width=90, fg_color="gray30",
                                  hover_color="gray30", state="disabled").pack(side="right", padx=10, pady=6)
                else:
                    ctk.CTkButton(fila, text=t("comun_cerrar"), width=80, fg_color=COLOR_CRIT,
                                  hover_color="#c0392b",
                                  command=lambda hwnd=v["hwnd"], titulo=v["titulo"]:
                                  self._confirmar_cerrar_ventana(hwnd, titulo)).pack(side="right", padx=10, pady=6)
            return

        for p in procesos:
            riesgo, _ = opt.evaluar_riesgo_proceso(p["nombre"])
            fila = ctk.CTkFrame(self.lista_procesos_ram, fg_color=COLOR_BG_PANEL, corner_radius=8)
            fila.pack(fill="x", padx=4, pady=3)
            nombre_mostrado = p["nombre"] + ("  🔒" if riesgo == "bloqueado" else "")
            ctk.CTkLabel(fila, text=nombre_mostrado, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(
                side="left", padx=10, pady=8, fill="x", expand=True)
            texto_valor = (opt.format_bytes(p["bytes_ram"]) if modo == "ram"
                           else t("opt_cpu_pct", pct=f'{p["cpu_pct"]:.0f}'))
            ctk.CTkLabel(fila, text=texto_valor, font=ctk.CTkFont(size=11),
                         text_color="gray60").pack(side="left", padx=(0, 10))
            if riesgo == "bloqueado":
                ctk.CTkButton(fila, text="Protegido", width=90, fg_color="gray30",
                              hover_color="gray30", state="disabled").pack(side="right", padx=10, pady=6)
            else:
                ctk.CTkButton(fila, text="Terminar", width=80, fg_color=COLOR_CRIT, hover_color="#c0392b",
                              command=lambda pid=p["pid"], nombre=p["nombre"]:
                              self._confirmar_terminar_proceso(pid, nombre)).pack(side="right", padx=10, pady=6)

    def _confirmar_cerrar_ventana(self, hwnd, titulo):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar")
        dialogo.geometry("440x200")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("opt_conf_cerrar_titulo", titulo=titulo),
                     font=ctk.CTkFont(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))
        ctk.CTkLabel(dialogo,
                     text=t("opt_conf_cerrar_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=400, justify="center").pack(
            padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            exito = opt.cerrar_ventana(hwnd)
            msg = (t("opt_cerrar_ok", titulo=titulo) if exito
                   else t("opt_cerrar_error", titulo=titulo))
            self._log_dev(t("opt_log_cerrar_ventana", titulo=titulo),
                          "PostMessageW(hwnd, WM_CLOSE, 0, 0)",
                          msg, seccion=t("seccion_optimizador"), exito=exito)
            modo_actual = self._modo_procesos_actual()
            self.after(800, lambda: self._mostrar_procesos_recursos(modo_actual))

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text="Cerrar", fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=confirmar).pack(side="left", padx=8)

    def _confirmar_terminar_proceso(self, pid, nombre):
        riesgo, motivo = opt.evaluar_riesgo_proceso(nombre)
        if riesgo == "bloqueado":
            self._mostrar_popup_info(
                t("proc_protegido_titulo"),
                t("proc_protegido_msg", nombre=nombre, motivo=motivo))
            return

        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar")
        dialogo.geometry("440x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("proc_conf_titulo", nombre=nombre, pid=pid),
                     font=ctk.CTkFont(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))

        if riesgo == "recuperable":
            ctk.CTkLabel(dialogo, text=t("proc_aviso_riesgo", motivo=motivo),
                         font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_WARN,
                         wraplength=400, justify="center").pack(padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(dialogo,
                         text=t("proc_aviso_normal"),
                         font=ctk.CTkFont(size=11), text_color=COLOR_WARN, wraplength=400, justify="center").pack(
                padx=20, pady=(0, 10))
        ctk.CTkLabel(dialogo,
                     text=t("proc_consejo"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=400, justify="center").pack(
            padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            def worker():
                exito, resultado = opt.terminar_proceso(pid)
                msg = (t("proc_terminado", nombre=nombre) if exito
                       else t("proc_error", nombre=nombre, error=resultado))
                self._log_dev(t("proc_log_terminar", nombre=nombre, pid=pid),
                              f"psutil.Process({pid}).terminate()",
                              msg, seccion=t("seccion_optimizador"), exito=exito)
                modo_actual = self._modo_procesos_actual()
                self.after(500, lambda: self._mostrar_procesos_recursos(modo_actual))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("proc_btn_terminar"), fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=confirmar).pack(side="left", padx=8)

    def _accion_estimar_espacio(self):
        def worker():
            resultados, total = opt.estimate_reclaimable_space()
            detalle = "\n".join(t("opt_espacio_detalle", categoria=r["categoria"],
                                   tamano=opt.format_bytes(r["bytes"])) for r in resultados)
            msg = t("opt_espacio_estimado", total=opt.format_bytes(total), detalle=detalle)
            self.lbl_resultado_opt.configure(text=msg)
            self._log_dev(t("opt_log_estimar"), t("opt_log_estimar_cmd"),
                          msg, seccion=t("seccion_optimizador"), exito=True)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_escaneando"))

    def _accion_limpiar_temp(self):
        def worker():
            liberado, borrados, comando = opt.clear_temp_files()
            msg = t("opt_temp_ok", archivos=borrados, tamano=opt.format_bytes(liberado))
            self.lbl_resultado_opt.configure(text=msg)
            self._log_dev(t("opt_log_temp"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado, archivos_afectados=borrados)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_limpiando_temp"))

    def _accion_vaciar_papelera(self):
        exito, comando = opt.empty_recycle_bin()
        msg = t("opt_papelera_ok") if exito else t("opt_papelera_error")
        self.lbl_resultado_opt.configure(text=msg)
        self._log_dev(t("opt_log_papelera"), comando, msg, seccion=t("seccion_optimizador"), exito=exito)

    def _accion_flush_dns(self):
        exito, comando = opt.flush_dns()
        msg = t("opt_dns_ok") if exito else t("opt_dns_error")
        self.lbl_resultado_opt.configure(text=msg)
        self._log_dev(t("opt_log_dns"), comando, msg, seccion=t("seccion_optimizador"), exito=exito)

    def _accion_limpiar_miniaturas(self):
        self.lbl_resultado_opt.configure(text=t("opt_limpiando_miniaturas"))

        def worker():
            borrados, liberado, comando = opt.limpiar_cache_miniaturas()
            msg = (t("opt_miniaturas_ok", archivos=borrados, tamano=opt.format_bytes(liberado))
                   if borrados else t("opt_miniaturas_vacio"))
            self.after(0, lambda: self.lbl_resultado_opt.configure(text=msg))
            self._log_dev(t("opt_log_miniaturas"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado, archivos_afectados=borrados)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_limpieza_unica(self):
        texto_minutos = self.combo_minutos_unica.get()
        minutos = int(texto_minutos.split()[0])

        def worker():
            exito, comando = opt.crear_limpieza_unica(minutos_desde_ahora=minutos)
            msg = (t("opt_limpieza_unica_ok", minutos=minutos) if exito
                   else t("opt_limpieza_unica_error"))
            self.after(0, lambda: self.lbl_resultado_opt.configure(text=msg))
            self._log_dev(t("opt_log_limpieza_unica"), comando, msg,
                          seccion=t("seccion_optimizador"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Privacidad ----------------
    def mostrar_privacidad(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("priv_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(1, weight=1)
        contenedor = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        contenedor.grid(row=1, column=0, columnspan=3, sticky="nswe")

        panel = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.pack(fill="x", padx=8, pady=8)

        navegadores = priv.detect_installed_browsers()
        if not navegadores:
            ctk.CTkLabel(panel, text=t("priv_sin_navegadores")).pack(
                padx=16, pady=16)
        else:
            self.lbl_resultado_priv = ctk.CTkLabel(panel, text=t("priv_cierra_navegador"),
                                                    font=ctk.CTkFont(size=13), wraplength=800, justify="left")
            self.lbl_resultado_priv.pack(padx=16, pady=16, anchor="w")

            for nombre in navegadores:
                fila = ctk.CTkFrame(panel, fg_color="transparent")
                fila.pack(fill="x", padx=16, pady=6)
                ctk.CTkLabel(fila, text=nombre, width=100, anchor="w",
                             font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
                ctk.CTkButton(fila, text=t("priv_btn_historial"), width=140,
                              command=lambda n=nombre: self._accion_borrar_historial(n)).pack(side="left", padx=6)
                ctk.CTkButton(fila, text=t("priv_btn_cache"), width=140,
                              command=lambda n=nombre: self._accion_borrar_cache(n)).pack(side="left", padx=6)

            self._boton_ver_reporte(panel)

        # ---- Otras huellas de actividad (independiente de navegadores) ----
        panel_otros = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_otros.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(panel_otros, text=t("priv_otras_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        self.lbl_resultado_otros_priv = ctk.CTkLabel(panel_otros, text="", font=ctk.CTkFont(size=12),
                                                       text_color="gray70")
        self.lbl_resultado_otros_priv.pack(anchor="w", padx=16, pady=(0, 8))
        fila_otros = ctk.CTkFrame(panel_otros, fg_color="transparent")
        fila_otros.pack(padx=16, pady=(0, 16), fill="x")
        ctk.CTkButton(fila_otros, text=t("priv_btn_recientes"), command=self._accion_limpiar_recientes).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(fila_otros, text=t("priv_btn_portapapeles"), command=self._accion_limpiar_portapapeles).pack(
            side="left")
        ctk.CTkLabel(panel_otros,
                     text=t("priv_otras_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            padx=16, pady=(0, 16), anchor="w")

    def _accion_limpiar_recientes(self):
        def worker():
            borrados, comando = opt.limpiar_accesos_recientes()
            msg = (t("priv_recientes_ok", cantidad=borrados) if borrados
                   else t("priv_recientes_vacio"))
            self.after(0, lambda: self.lbl_resultado_otros_priv.configure(text=msg))
            self._log_dev(t("priv_btn_recientes"), comando, msg, seccion=t("seccion_privacidad"),
                          exito=True, archivos_afectados=borrados)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_limpiar_portapapeles(self):
        exito, comando = opt.limpiar_portapapeles()
        msg = t("priv_portapapeles_ok") if exito else t("priv_portapapeles_error")
        self.lbl_resultado_otros_priv.configure(text=msg)
        self._log_dev(t("priv_btn_portapapeles"), comando, msg,
                      seccion=t("seccion_privacidad"), exito=exito)

    def _accion_borrar_historial(self, nombre):
        exito, msg, comando = priv.clear_browser_history(nombre)
        self.lbl_resultado_priv.configure(text=msg)
        self._log_dev(t("priv_log_historial", navegador=nombre), comando or "N/A", msg,
                      seccion=t("seccion_privacidad"), exito=exito)

    def _accion_borrar_cache(self, nombre):
        exito, liberado, msg = priv.clear_browser_cache(nombre)
        texto = (t("priv_cache_liberado", mensaje=msg, tamano=opt.format_bytes(liberado))
                 if exito else msg)
        self.lbl_resultado_priv.configure(text=texto)
        self._log_dev(t("priv_log_cache", navegador=nombre), t("priv_log_cache_cmd"), texto,
                      seccion=t("seccion_privacidad"), exito=exito, bytes_liberados=liberado)

    # ---------------- Acción rápida (usada desde el Dashboard) ----------------
    def _accion_optimizacion_rapida(self):
        def worker():
            liberado_ram, procesos, cmd1 = opt.trim_process_memory()
            liberado_disco, archivos, cmd2 = opt.clear_temp_files()
            msg = t("dash_optimizacion_lista", procesos=procesos, ram=opt.format_bytes(liberado_ram),
                    archivos=archivos, disco=opt.format_bytes(liberado_disco))
            self.lbl_resultado_user.configure(text=msg)
            self._log_dev(t("dash_log_optimizacion"), f"{cmd1} + {cmd2}", msg, seccion=t("seccion_inicio"),
                          exito=True, bytes_liberados=liberado_ram + liberado_disco,
                          archivos_afectados=procesos + archivos)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_user.configure(text=t("dash_optimizando"))

    def _accion_vaciar_papelera_user(self):
        exito, comando = opt.empty_recycle_bin()
        msg = t("dash_papelera_vaciada") if exito else t("dash_papelera_error")
        self.lbl_resultado_user.configure(text=msg)
        self._log_dev(t("dash_log_papelera"), comando, msg, seccion=t("seccion_inicio"), exito=exito)

    # ---------------- Seguridad ----------------
    def mostrar_seguridad(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("seg_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.pestana_seguridad = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("seg_tab_antivirus"), t("seg_tab_permisos"),
                    t("seg_tab_firewall"), t("seg_tab_usuarios")],
            command=self._cambiar_pestana_seguridad)
        self.pestana_seguridad.set(t("seg_tab_antivirus"))
        self.pestana_seguridad.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.contenedor_seguridad = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.contenedor_seguridad.grid(row=2, column=0, columnspan=3, sticky="nswe")
        self.contenedor_seguridad.grid_columnconfigure(0, weight=1)
        self.contenedor_seguridad.grid_rowconfigure(1, weight=1)

        self._mostrar_antivirus()

    def _cambiar_pestana_seguridad(self, valor):
        """El texto de la pestaña está traducido: se resuelve contra las
        mismas claves con las que se construyó, y el `else` cae en Antivirus,
        que es la pestaña por defecto — nunca en una rama arbitraria."""
        if valor == t("seg_tab_permisos"):
            self._mostrar_permisos_privacidad()
        elif valor == t("seg_tab_firewall"):
            self._mostrar_firewall()
        elif valor == t("seg_tab_usuarios"):
            self._mostrar_usuarios_sistema()
        else:
            self._mostrar_antivirus()

    def _limpiar_contenedor_seguridad(self):
        for w in self.contenedor_seguridad.winfo_children():
            w.destroy()

    # ---- Antivirus (Windows Defender) ----
    def _mostrar_antivirus(self):
        self._limpiar_contenedor_seguridad()
        panel = ctk.CTkFrame(self.contenedor_seguridad, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(panel, text=t("seg_defender_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        self.lbl_estado_defender = ctk.CTkLabel(panel, text=t("seg_leyendo_estado"), font=ctk.CTkFont(size=12),
                                                 text_color="gray70", justify="left", anchor="w")
        self.lbl_estado_defender.pack(anchor="w", padx=16, pady=(0, 12))

        fila = ctk.CTkFrame(panel, fg_color="transparent")
        fila.pack(padx=16, pady=(0, 16), fill="x")
        ctk.CTkButton(fila, text=t("seg_btn_escaneo_rapido"),
                      command=lambda: self._accion_escanear_defender("rapido")).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(fila, text=t("seg_btn_escaneo_completo"), fg_color="#2a2d36", hover_color="#3a3e4a",
                      command=lambda: self._accion_escanear_defender("completo")).pack(side="left")
        ctk.CTkLabel(panel,
                     text=t("seg_escaneo_nota"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            padx=16, pady=(0, 16), anchor="w")

        def worker():
            estado = opt.obtener_estado_defender()
            self.after(0, lambda: self._pintar_estado_defender(estado))
        threading.Thread(target=worker, daemon=True).start()

        # ---- BitLocker y Windows Hello (informativo) ----
        panel2 = ctk.CTkFrame(self.contenedor_seguridad, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel2.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(panel2, text=t("seg_cifrado_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        self.lbl_estado_bitlocker_hello = ctk.CTkLabel(panel2, text=t("seg_leyendo_estado"),
                                                        font=ctk.CTkFont(size=12),
                                                        text_color="gray70", justify="left", anchor="w")
        self.lbl_estado_bitlocker_hello.pack(anchor="w", padx=16, pady=(0, 16))

        def worker2():
            bitlocker = opt.obtener_estado_bitlocker()
            hello = opt.obtener_estado_windows_hello()
            self.after(0, lambda: self._pintar_bitlocker_hello(bitlocker, hello))
        threading.Thread(target=worker2, daemon=True).start()

    def _pintar_bitlocker_hello(self, bitlocker, hello):
        if not (hasattr(self, "lbl_estado_bitlocker_hello") and self.lbl_estado_bitlocker_hello.winfo_exists()):
            return
        if bitlocker is None:
            texto_bl = t("seg_bitlocker_error")
        else:
            estado_txt = (t("seg_bitlocker_activo") if bitlocker["proteccion_activa"]
                          else t("seg_bitlocker_inactivo"))
            texto_bl = t("seg_bitlocker_texto", estado=estado_txt,
                         volumen=bitlocker["estado_volumen"])
        texto_hello = (t("seg_hello_si") if hello and hello["configurado"]
                       else t("seg_hello_no"))
        self.lbl_estado_bitlocker_hello.configure(text=f"{texto_bl}\n{texto_hello}")

    def _pintar_estado_defender(self, estado):
        if not (hasattr(self, "lbl_estado_defender") and self.lbl_estado_defender.winfo_exists()):
            return
        if estado is None:
            self.lbl_estado_defender.configure(text=t("seg_defender_error"))
            return
        texto = t("seg_defender_estado",
                  activo=t("seg_si") if estado["activo"] else t("seg_no"),
                  tiempo_real=t("seg_si") if estado["tiempo_real"] else t("seg_no"),
                  ultimo_rapido=self._fmt_dias(estado["dias_desde_ultimo_rapido"]),
                  ultimo_completo=self._fmt_dias(estado["dias_desde_ultimo_completo"]))
        self.lbl_estado_defender.configure(text=texto)

    def _fmt_dias(self, valor):
        if valor is None:
            return t("seg_dias_nunca")
        return t("seg_dias_hace", dias=valor)

    def _accion_escanear_defender(self, tipo):
        # "tipo" es la clave interna que entiende opt.iniciar_escaneo_defender.
        # BUG corregido: se interpolaba tal cual en el mensaje, así que la
        # build en inglés habría dicho "rapido scan started". Ahora se traduce
        # aparte para mostrar y la clave viaja sola hacia el optimizador.
        exito, comando = opt.iniciar_escaneo_defender(tipo)
        tipo_txt = t("seg_tipo_completo") if tipo == "completo" else t("seg_tipo_rapido")
        msg = t("seg_escaneo_iniciado", tipo=tipo_txt) if exito else t("seg_escaneo_error")
        self._mostrar_popup_info("Windows Defender", msg)
        self._log_dev(t("seg_log_escaneo", tipo=tipo_txt), comando, msg,
                      seccion=t("seccion_seguridad"), exito=exito)

    # ---- Permisos de privacidad (cámara/micrófono/ubicación) ----
    def _mostrar_permisos_privacidad(self):
        self._limpiar_contenedor_seguridad()
        self.pestana_permiso = ctk.CTkSegmentedButton(
            self.contenedor_seguridad,
            values=[t("seg_perm_camara"), t("seg_perm_microfono"), t("seg_perm_ubicacion")],
            command=lambda v: self._cargar_permisos_privacidad())
        self.pestana_permiso.set(t("seg_perm_camara"))
        self.pestana_permiso.pack(anchor="w", pady=(0, 8))

        self.lista_permisos = ctk.CTkScrollableFrame(self.contenedor_seguridad, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_permisos.pack(fill="both", expand=True)
        self._cargar_permisos_privacidad()

    def _cargar_permisos_privacidad(self):
        for w in self.lista_permisos.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_permisos, text=t("seg_leyendo_permisos"),
                     text_color="gray60").pack(padx=16, pady=16)

        # BUG corregido: el mapa tenía las etiquetas en español como claves y
        # caía en "webcam" por defecto. Traducidas las pestañas, en inglés
        # ninguna coincidía y Micrófono y Ubicación mostraban los permisos de
        # la CÁMARA — datos incorrectos sin ningún error visible. Ahora se
        # arma con las mismas claves con las que se construyó la pestaña.
        mapa = {
            t("seg_perm_camara"): "webcam",
            t("seg_perm_microfono"): "microphone",
            t("seg_perm_ubicacion"): "location",
        }
        tipo = mapa.get(self.pestana_permiso.get(), "webcam")

        def worker():
            permisos = opt.listar_permisos_privacidad(tipo)
            self.after(0, lambda: self._pintar_permisos_privacidad(permisos))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_permisos_privacidad(self, permisos):
        if not (hasattr(self, "lista_permisos") and self.lista_permisos.winfo_exists()):
            return
        for w in self.lista_permisos.winfo_children():
            w.destroy()
        if not permisos:
            ctk.CTkLabel(self.lista_permisos, text=t("seg_sin_permisos"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        for p in permisos:
            fila = ctk.CTkFrame(self.lista_permisos, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            # opt devuelve un codigo estable ("permitido"/"bloqueado"/otro);
            # el color y el texto visible se derivan aqui.
            estado_txt = {
                "permitido": t("seg_permiso_permitido"),
                "bloqueado": t("seg_permiso_bloqueado"),
            }.get(p["estado"], t("seg_permiso_desconocido"))
            color = COLOR_OK if p["estado"] == "permitido" else (
                COLOR_CRIT if p["estado"] == "bloqueado" else "gray60")
            ctk.CTkLabel(fila, text=p["app"], font=ctk.CTkFont(size=12), anchor="w", wraplength=650,
                         justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            ctk.CTkLabel(fila, text=estado_txt, font=ctk.CTkFont(size=12, weight="bold"), text_color=color).pack(
                side="right", padx=12, pady=8)
        ctk.CTkLabel(self.lista_permisos,
                     text=t("seg_permisos_nota"),
                     font=ctk.CTkFont(size=11), text_color="gray50", wraplength=850, justify="left").pack(
            padx=12, pady=12, anchor="w")

    # ---- Firewall ----
    def _mostrar_firewall(self):
        self._limpiar_contenedor_seguridad()
        ctk.CTkLabel(self.contenedor_seguridad,
                     text=t("seg_firewall_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        fila = ctk.CTkFrame(self.contenedor_seguridad, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(fila, text=t("seg_btn_bloquear"), command=self._accion_elegir_bloquear_app).pack(
            side="left")

        self.lista_firewall = ctk.CTkScrollableFrame(self.contenedor_seguridad, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_firewall.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_firewall, text=t("seg_leyendo_reglas"), text_color="gray60").pack(
            padx=16, pady=16)

        def worker():
            reglas = opt.listar_reglas_firewall_bloqueadas()
            self.after(0, lambda: self._pintar_firewall(reglas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_firewall(self, reglas):
        if not (hasattr(self, "lista_firewall") and self.lista_firewall.winfo_exists()):
            return
        for w in self.lista_firewall.winfo_children():
            w.destroy()
        if not reglas:
            ctk.CTkLabel(self.lista_firewall, text=t("seg_sin_reglas"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        for r in reglas:
            fila = ctk.CTkFrame(self.lista_firewall, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(fila, text=t("seg_regla_detalle", nombre=r["nombre"], direccion=r["direccion"]),
                         font=ctk.CTkFont(size=12), anchor="w",
                         wraplength=650, justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            if str(r["nombre"]).startswith("TechCleanPro-Bloqueo-"):
                ctk.CTkButton(fila, text=t("seg_btn_desbloquear"), width=100, fg_color="#2a2d36",
                              hover_color="#3a3e4a",
                              command=lambda n=r["nombre"]: self._accion_desbloquear_app(n)).pack(
                    side="right", padx=12, pady=8)

    def _accion_elegir_bloquear_app(self):
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(title=t("seg_dialogo_elegir"),
                                           filetypes=[(t("seg_filtro_programas"), "*.exe")])
        if not ruta:
            return

        def worker():
            exito, nombre_regla, comando = opt.bloquear_app_firewall(ruta)
            msg = (t("seg_bloqueado_ok", nombre=os.path.basename(ruta))
                   if exito else t("seg_bloqueado_error"))
            self._log_dev(t("seg_log_bloquear", nombre=os.path.basename(ruta)), comando, msg,
                          seccion=t("seccion_seguridad"), exito=exito)
            self.after(0, lambda: self._mostrar_popup_info("Firewall", msg))
            self.after(0, self._mostrar_firewall)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_desbloquear_app(self, nombre_regla):
        def worker():
            exito, comando = opt.desbloquear_app_firewall(nombre_regla)
            msg = t("seg_desbloqueo_ok") if exito else t("seg_desbloqueo_error")
            self._log_dev(t("seg_log_desbloquear", regla=nombre_regla), comando, msg,
                          seccion=t("seccion_seguridad"), exito=exito)
            self.after(0, self._mostrar_firewall)
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_usuarios_sistema(self):
        self._limpiar_contenedor_seguridad()
        ctk.CTkLabel(self.contenedor_seguridad,
                     text=t("seg_usuarios_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        self.lista_usuarios = ctk.CTkScrollableFrame(self.contenedor_seguridad, fg_color=COLOR_BG_PANEL,
                                                       corner_radius=16)
        self.lista_usuarios.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_usuarios, text=t("seg_leyendo_usuarios"), text_color="gray60").pack(
            padx=16, pady=16)

        def worker():
            usuarios = opt.listar_usuarios_sistema()
            self.after(0, lambda: self._pintar_usuarios_sistema(usuarios))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_usuarios_sistema(self, usuarios):
        if not (hasattr(self, "lista_usuarios") and self.lista_usuarios.winfo_exists()):
            return
        for w in self.lista_usuarios.winfo_children():
            w.destroy()
        if not usuarios:
            ctk.CTkLabel(self.lista_usuarios, text=t("seg_sin_usuarios"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        for u in usuarios:
            fila = ctk.CTkFrame(self.lista_usuarios, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            nombre_mostrado = u["nombre"] + (t("seg_usuario_tu") if u["es_actual"] else "")
            ctk.CTkLabel(fila, text=nombre_mostrado, font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(
                side="left", padx=12, pady=10, fill="x", expand=True)
            etiquetas = []
            etiquetas.append(t("seg_admin") if u["es_admin"] else t("seg_estandar"))
            etiquetas.append(t("seg_habilitada") if u["habilitada"] else t("seg_deshabilitada"))
            color_estado = COLOR_OK if u["habilitada"] else "gray50"
            ctk.CTkLabel(fila, text="  ·  ".join(etiquetas), font=ctk.CTkFont(size=11),
                         text_color=color_estado).pack(side="right", padx=12, pady=10)

    # ---------------- Reparar ----------------
    def mostrar_reparar(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("rep_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ctk.CTkLabel(self.contenido,
                     text=t("rep_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        panel = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.grid(row=2, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        self.lbl_resultado_reparar = ctk.CTkLabel(panel, text=t("rep_selecciona"),
                                                    font=ctk.CTkFont(size=13), wraplength=850, justify="left")
        self.lbl_resultado_reparar.pack(padx=16, pady=16, anchor="w")

        acciones = [
            (t("rep_btn_sfc"), self._accion_reparar_sfc, t("rep_desc_sfc")),
            (t("rep_btn_scanhealth"), self._accion_revisar_salud_imagen, t("rep_desc_scanhealth")),
            (t("rep_btn_dism"), self._accion_reparar_dism, t("rep_desc_dism")),
            (t("rep_btn_red"), self._accion_reparar_red, t("rep_desc_red")),
            (t("rep_btn_adaptador"), self._accion_elegir_adaptador, t("rep_desc_adaptador")),
            (t("rep_btn_store"), self._accion_reparar_store, t("rep_desc_store")),
            (t("rep_btn_disco"), self._accion_revisar_disco, t("rep_desc_disco")),
            (t("rep_btn_updates"), self._accion_buscar_actualizaciones, t("rep_desc_updates")),
            (t("rep_btn_explorador"), self._accion_reiniciar_explorador, t("rep_desc_explorador")),
        ]
        for texto, cmd, descripcion in acciones:
            fila = ctk.CTkFrame(panel, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=16, pady=6)
            ctk.CTkButton(fila, text=texto, width=260, command=cmd).pack(side="left", padx=10, pady=10)
            ctk.CTkLabel(fila, text=descripcion, font=ctk.CTkFont(size=11), text_color="gray60",
                         wraplength=560, justify="left", anchor="w").pack(side="left", padx=10, pady=10)

        sep_rend = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_rend.pack(fill="x", padx=16, pady=8)

        # ---- Rendimiento para equipos justos de recursos ----
        panel_rend = ctk.CTkFrame(panel, fg_color="#141720", corner_radius=10)
        panel_rend.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(panel_rend, text=t("rep_rend_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(panel_rend,
                     text=t("rep_rend_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10))

        fila_visual = ctk.CTkFrame(panel_rend, fg_color="transparent")
        fila_visual.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkButton(fila_visual, text=t("rep_btn_efectos"), width=260,
                      command=self._accion_abrir_efectos_visuales).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(fila_visual,
                     text=t("rep_desc_efectos"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=560, justify="left").pack(
            side="left")

        fila_visual_rapido = ctk.CTkFrame(panel_rend, fg_color="transparent")
        fila_visual_rapido.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(fila_visual_rapido, text=t("rep_btn_animaciones"), width=260,
                      fg_color="#2a2d36", hover_color="#3a3e4a",
                      command=self._accion_reducir_animaciones).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(fila_visual_rapido,
                     text=t("rep_desc_animaciones"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=560, justify="left").pack(
            side="left")

        fila_indexacion = ctk.CTkFrame(panel_rend, fg_color="transparent")
        fila_indexacion.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(fila_indexacion, text=t("rep_indexacion_label"), font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(0, 8))
        self.lbl_estado_indexacion = ctk.CTkLabel(fila_indexacion, text=t("rep_leyendo_minus"),
                                                    font=ctk.CTkFont(size=12), text_color="gray60")
        self.lbl_estado_indexacion.pack(side="left", padx=(0, 10))
        self.switch_indexacion = ctk.CTkSwitch(fila_indexacion, text="",
                                                command=self._toggle_indexacion_busqueda)
        self.switch_indexacion.pack(side="left")
        ctk.CTkLabel(panel_rend,
                     text=t("rep_indexacion_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=16, pady=(0, 14))

        def worker_indexacion():
            estado = opt.obtener_estado_indexacion()
            self.after(0, lambda: self._pintar_estado_indexacion(estado))
        threading.Thread(target=worker_indexacion, daemon=True).start()

        sep = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep.pack(fill="x", padx=16, pady=8)

        fila_restauracion = ctk.CTkFrame(panel, fg_color="transparent")
        fila_restauracion.pack(fill="x", padx=16, pady=(4, 16))
        self.switch_punto_restauracion = ctk.CTkSwitch(
            fila_restauracion, text=t("rep_switch_punto"),
            command=self._toggle_punto_restauracion)
        if self.prefs.get("crear_punto_restauracion", True):
            self.switch_punto_restauracion.select()
        self.switch_punto_restauracion.pack(anchor="w")
        ctk.CTkLabel(panel,
                     text=t("rep_punto_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=(28, 16), pady=(0, 4))

        self._boton_ver_reporte(panel)

    def _toggle_punto_restauracion(self):
        valor = self.switch_punto_restauracion.get()
        self.prefs["crear_punto_restauracion"] = valor
        prefs.guardar({"crear_punto_restauracion": valor})

    def _actualizar_resultado_reparar(self, texto):
        """Callback seguro para hilos de reparación: si el usuario ya salió
        de la pantalla Reparar (estas acciones pueden tardar varios
        minutos), no toca un widget destruido."""
        if hasattr(self, "lbl_resultado_reparar") and self.lbl_resultado_reparar.winfo_exists():
            self.lbl_resultado_reparar.configure(text=texto)

    def _crear_punto_restauracion_si_corresponde(self):
        """Se llama antes de sfc/DISM si el switch de la sección está
        activo. Best-effort: si falla (System Restore desactivado, límite
        de 24h de Windows, etc.) se registra pero NO bloquea la reparación
        — es una red de seguridad extra, no un requisito."""
        if not self.prefs.get("crear_punto_restauracion", True):
            return
        exito, comando = opt.crear_punto_restauracion(t("rep_punto_nombre"))
        msg = t("rep_punto_ok") if exito else t("rep_punto_error")
        self._log_dev(t("rep_log_punto"), comando, msg, seccion=t("seccion_reparar"), exito=exito)

    def _accion_reparar_sfc(self):
        def ejecutar(callback_progreso, evento_cancelar):
            self._crear_punto_restauracion_si_corresponde()
            return opt.reparar_archivos_sistema(callback_progreso=callback_progreso,
                                                 evento_cancelar=evento_cancelar)
        self._iniciar_reparacion_larga(t("rep_titulo_sfc"), ejecutar, t("rep_log_sfc"))

    def _accion_reparar_dism(self):
        def ejecutar(callback_progreso, evento_cancelar):
            self._crear_punto_restauracion_si_corresponde()
            return opt.reparar_imagen_windows(callback_progreso=callback_progreso,
                                               evento_cancelar=evento_cancelar)
        self._iniciar_reparacion_larga(t("rep_titulo_dism"), ejecutar, t("rep_log_dism"))

    def _accion_revisar_salud_imagen(self):
        # Solo revisa, no cambia nada — a diferencia de la reparación
        # completa, no hace falta punto de restauración aquí.
        def ejecutar(callback_progreso, evento_cancelar):
            return opt.revisar_salud_imagen_windows(callback_progreso=callback_progreso,
                                                      evento_cancelar=evento_cancelar)
        self._iniciar_reparacion_larga(t("rep_titulo_scanhealth"), ejecutar, t("rep_log_scanhealth"))

    def _iniciar_reparacion_larga(self, titulo, funcion_reparacion, nombre_para_historial):
        """
        Ventana común para reparaciones largas (sfc, DISM) que de verdad se
        pueden cancelar desde la interfaz, con reloj de tiempo transcurrido
        — antes solo había un límite fijo de 30 min sin ninguna forma de
        interrumpirlo antes, así que la única opción para no esperar era
        cerrar toda la app a la fuerza.
        """
        evento_cancelar = threading.Event()

        dialogo = ctk.CTkToplevel(self)
        dialogo.title(titulo)
        dialogo.geometry("440x230")
        dialogo.grab_set()
        # BUG corregido: sin grab_set(), si hacías clic en el menú lateral
        # mientras esto corría, la ventana quedaba DETRÁS de la principal
        # — seguía trabajando igual, pero parecía haberse cancelado. Ahora
        # el resto de la app queda bloqueado hasta que termine o canceles,
        # como el resto de ventanas de confirmación de la app.
        ctk.CTkLabel(dialogo, text=titulo, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(24, 8))
        lbl_tiempo = ctk.CTkLabel(dialogo, text=t("rep_tiempo", minutos=0, segundos="00"),
                                    font=ctk.CTkFont(size=20, weight="bold"))
        lbl_tiempo.pack(pady=(0, 6))
        ctk.CTkLabel(dialogo,
                     text=t("rep_larga_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=380, justify="center").pack(
            padx=20, pady=(0, 16))

        def cancelar():
            evento_cancelar.set()
            btn_cancelar.configure(state="disabled", text=t("rep_cancelando"))

        # La "X" de la ventana también cancela en vez de no hacer nada —
        # cerrar la ventana sin más dejaría el proceso corriendo sin
        # forma de volver a verlo ni de detenerlo.
        dialogo.protocol("WM_DELETE_WINDOW", cancelar)

        btn_cancelar = ctk.CTkButton(dialogo, text=t("comun_cancelar"), fg_color=COLOR_CRIT, hover_color="#c0392b",
                                      command=cancelar)
        btn_cancelar.pack(pady=(0, 20))

        def progreso(segundos):
            if not dialogo.winfo_exists():
                return
            minutos, seg = divmod(int(segundos), 60)
            self.after(0, lambda: lbl_tiempo.configure(
                text=t("rep_tiempo", minutos=minutos, segundos=f"{seg:02d}")))

        def worker():
            exito, resumen, comando = funcion_reparacion(progreso, evento_cancelar)
            cancelado = evento_cancelar.is_set()
            msg = (t("rep_cancelado") if cancelado else
                   (t("rep_listo", resumen=resumen) if exito
                    else t("rep_problema", resumen=resumen)))
            self._log_dev(nombre_para_historial, comando, msg, seccion=t("seccion_reparar"), exito=exito and not cancelado)

            def cerrar():
                if dialogo.winfo_exists():
                    dialogo.destroy()
                self._actualizar_resultado_reparar(msg)
            self.after(0, cerrar)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_reparar_red(self):
        self.lbl_resultado_reparar.configure(text=t("rep_red_reiniciando"))

        def worker():
            exito, comando = opt.reparar_red()
            msg = t("rep_red_ok") if exito else t("rep_red_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_red"), comando, msg, seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_elegir_adaptador(self):
        self.lbl_resultado_reparar.configure(text=t("rep_leyendo_adaptadores"))

        def worker():
            adaptadores = opt.listar_adaptadores_red()
            self.after(0, lambda: self._mostrar_selector_adaptador(adaptadores))
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_selector_adaptador(self, adaptadores):
        if not adaptadores:
            self._actualizar_resultado_reparar(t("rep_sin_adaptadores"))
            return
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("rep_elegir_adaptador"))
        dialogo.geometry("420x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("rep_que_adaptador"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8))
        lista = ctk.CTkScrollableFrame(dialogo, fg_color=COLOR_BG_PANEL)
        lista.pack(fill="both", expand=True, padx=16, pady=8)
        for a in adaptadores:
            fila = ctk.CTkFrame(lista, fg_color="#141720", corner_radius=8)
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(fila, text=t("rep_adaptador_detalle", nombre=a["nombre"],
                                      descripcion=a["descripcion"]), font=ctk.CTkFont(size=11),
                         anchor="w", wraplength=300, justify="left").pack(side="left", padx=8, pady=8, fill="x", expand=True)
            ctk.CTkButton(fila, text=t("rep_btn_reiniciar"), width=90,
                          command=lambda n=a["nombre"]: (dialogo.destroy(), self._accion_reiniciar_adaptador(n))).pack(
                side="right", padx=8, pady=6)
        ctk.CTkButton(dialogo, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(pady=(0, 12))

    def _accion_reiniciar_adaptador(self, nombre):
        self.lbl_resultado_reparar.configure(text=t("rep_adaptador_reiniciando", nombre=nombre))

        def worker():
            exito, comando = opt.reiniciar_adaptador_red(nombre)
            msg = (t("rep_adaptador_ok", nombre=nombre) if exito
                   else t("rep_adaptador_error", nombre=nombre))
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_adaptador", nombre=nombre), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_reparar_store(self):
        exito, comando = opt.reparar_windows_store()
        msg = t("rep_store_ok") if exito else t("rep_store_error")
        self.lbl_resultado_reparar.configure(text=msg)
        self._log_dev(t("rep_log_store"), comando, msg, seccion=t("seccion_reparar"), exito=exito)

    def _accion_reiniciar_explorador(self):
        self.lbl_resultado_reparar.configure(text=t("rep_explorador_reiniciando"))

        def worker():
            exito, comando = opt.reiniciar_explorador()
            msg = t("rep_explorador_ok") if exito else t("rep_explorador_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_explorador"), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_abrir_efectos_visuales(self):
        exito, comando = opt.abrir_opciones_rendimiento_visual()
        msg = t("rep_efectos_ok") if exito else t("rep_efectos_error")
        self.lbl_resultado_reparar.configure(text=msg)
        self._log_dev(t("rep_log_efectos"), comando, msg, seccion=t("seccion_reparar"), exito=exito)

    def _accion_reducir_animaciones(self):
        exito, comando = opt.reducir_animaciones_ahora(activar_reduccion=True)
        msg = t("rep_animaciones_ok") if exito else t("rep_animaciones_error")
        self.lbl_resultado_reparar.configure(text=msg)
        self._log_dev(t("rep_log_animaciones"), comando, msg, seccion=t("seccion_reparar"), exito=exito)

    def _pintar_estado_indexacion(self, estado):
        if not (hasattr(self, "lbl_estado_indexacion") and self.lbl_estado_indexacion.winfo_exists()):
            return
        if estado is None:
            self.lbl_estado_indexacion.configure(text=t("rep_idx_no_leido"))
            return
        self.lbl_estado_indexacion.configure(
            text=t("rep_idx_activa") if estado else t("rep_idx_pausada"))
        if hasattr(self, "switch_indexacion") and self.switch_indexacion.winfo_exists():
            if estado:
                self.switch_indexacion.select()
            else:
                self.switch_indexacion.deselect()

    def _toggle_indexacion_busqueda(self):
        activar = bool(self.switch_indexacion.get())  # switch ON = indexación activa
        self.lbl_estado_indexacion.configure(text=t("rep_idx_aplicando"))

        def worker():
            exito, comando = opt.pausar_indexacion_busqueda(pausar=not activar)
            msg = ((t("rep_idx_reanudada") if activar else t("rep_idx_pausada_msg")) if exito
                   else t("rep_idx_error"))
            if hasattr(self, "lbl_estado_indexacion") and self.lbl_estado_indexacion.winfo_exists():
                self.after(0, lambda: self.lbl_estado_indexacion.configure(
                    text=t("rep_idx_activa") if activar else t("rep_idx_pausada")))
            self._log_dev(t("rep_log_idx_reanudada") if activar else t("rep_log_idx_pausada"),
                          comando, msg, seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_revisar_disco(self):
        self.lbl_resultado_reparar.configure(text=t("rep_programando"))

        def worker():
            exito, comando = opt.revisar_disco_en_reinicio("C:")
            msg = t("rep_disco_ok") if exito else t("rep_disco_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_disco"), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_buscar_actualizaciones(self):
        self.lbl_resultado_reparar.configure(text=t("rep_buscando_updates"))

        def worker():
            exito, titulos, comando = opt.buscar_actualizaciones_pendientes()
            if not exito:
                msg = t("rep_updates_error")
            elif not titulos:
                msg = t("rep_updates_al_dia")
            else:
                lista = "\n".join(f"• {titulo}" for titulo in titulos[:10])
                extra = (t("rep_updates_extra", cantidad=len(titulos) - 10)
                         if len(titulos) > 10 else "")
                msg = t("rep_updates_lista", cantidad=len(titulos), lista=lista, extra=extra)
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_updates"), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Aplicaciones: inicio de Windows + desinstalador ----------------
    def mostrar_aplicaciones(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("apps_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.pestana_apps = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("apps_tab_inicio"), t("apps_tab_desinstalar"), t("apps_tab_servicios"),
                    t("apps_tab_actualizar"), t("apps_tab_tareas")],
            command=self._cambiar_pestana_apps)
        self.pestana_apps.set(t("apps_tab_inicio"))
        self.pestana_apps.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.contenedor_apps = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.contenedor_apps.grid(row=2, column=0, columnspan=3, sticky="nswe")
        self.contenedor_apps.grid_columnconfigure(0, weight=1)
        self.contenedor_apps.grid_rowconfigure(0, weight=1)

        self._mostrar_inicio_windows()

    def _cambiar_pestana_apps(self, valor):
        """El texto de la pestaña está traducido: se resuelve contra las
        mismas claves con las que se construyó, y el `else` cae en Inicio de
        Windows, que es la pestaña por defecto."""
        if valor == t("apps_tab_desinstalar"):
            self._mostrar_desinstalador()
        elif valor == t("apps_tab_servicios"):
            self._mostrar_servicios()
        elif valor == t("apps_tab_actualizar"):
            self._mostrar_actualizar_apps()
        elif valor == t("apps_tab_tareas"):
            self._mostrar_tareas_programadas()
        else:
            self._mostrar_inicio_windows()

    def _limpiar_contenedor_apps(self):
        for w in self.contenedor_apps.winfo_children():
            w.destroy()

    def _mostrar_inicio_windows(self):
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_inicio_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        lista.pack(fill="both", expand=True)
        ctk.CTkLabel(lista, text=t("apps_cargando_inicio"), text_color="gray60").pack(padx=16, pady=16)
        self.lista_inicio_frame = lista

        # BUG corregido: opt.listar_apps_inicio() lee el registro con winreg y
        # se llamaba aqui mismo, en el hilo principal de Tkinter — justo lo que
        # la regla de threading del CONTEXTO prohibe. Con muchas entradas la
        # ventana se quedaba congelada al abrir la pestana. Ahora va en un hilo.
        def worker():
            apps = opt.listar_apps_inicio()
            self.after(0, lambda: self._pintar_apps_inicio(apps))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_apps_inicio(self, apps):
        if not (hasattr(self, "lista_inicio_frame") and self.lista_inicio_frame.winfo_exists()):
            return
        for w in self.lista_inicio_frame.winfo_children():
            w.destroy()
        if not apps:
            ctk.CTkLabel(self.lista_inicio_frame, text=t("apps_sin_inicio"),
                         text_color="gray60").pack(padx=16, pady=16)
            return

        for app in apps:
            fila = ctk.CTkFrame(self.lista_inicio_frame, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=5)
            ctk.CTkLabel(fila, text=app["nombre"], font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w").pack(side="left", padx=12, pady=10)
            switch = ctk.CTkSwitch(fila, text=t("apps_activo") if app["activo"] else t("apps_inactivo"),
                                    command=lambda a=app: self._toggle_app_inicio(a))
            if app["activo"]:
                switch.select()
            switch.pack(side="right", padx=12, pady=10)

    def _toggle_app_inicio(self, app):
        activar = not app["activo"]
        exito = opt.set_app_inicio_activa(app["nombre"], app["comando"], activar)
        msg = (t("apps_inicio_cambiado", nombre=app["nombre"],
                 estado=t("apps_activado") if activar else t("apps_desactivado"))
               if exito else t("apps_inicio_error", nombre=app["nombre"]))
        self._log_dev(t("apps_log_activar_inicio") if activar else t("apps_log_desactivar_inicio"),
                      "N/A", msg,
                      seccion=t("seccion_aplicaciones"), exito=exito)
        self._mostrar_inicio_windows()

    def _mostrar_desinstalador(self):
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_desinst_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        lista.pack(fill="both", expand=True)
        ctk.CTkLabel(lista, text=t("apps_cargando_programas"), text_color="gray60").pack(padx=16, pady=16)

        def worker():
            programas = opt.listar_programas_instalados()
            self.after(0, lambda: self._pintar_desinstalador(programas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_desinstalador(self, programas):
        # Si el usuario ya salió de esta pantalla (o cambió de pestaña)
        # mientras cargaba en segundo plano, no tocar widgets destruidos.
        if not (hasattr(self, "pestana_apps") and self.pestana_apps.winfo_exists()):
            return
        if self.pestana_apps.get() != t("apps_tab_desinstalar"):
            return
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_desinst_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        lista.pack(fill="both", expand=True)

        if not programas:
            ctk.CTkLabel(lista, text=t("apps_sin_programas"),
                         text_color="gray60").pack(padx=16, pady=16)
            return

        for prog in programas:
            fila = ctk.CTkFrame(lista, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=5)
            info = t("apps_prog_info", nombre=prog["nombre"], editor=prog["editor"],
                     version=prog["version"])
            if prog["tamano_mb"]:
                info += t("apps_prog_tamano", mb=prog["tamano_mb"])
            ctk.CTkLabel(fila, text=info, font=ctk.CTkFont(size=12), anchor="w", wraplength=650,
                         justify="left").pack(side="left", padx=12, pady=10, fill="x", expand=True)
            ctk.CTkButton(fila, text="Desinstalar", fg_color=COLOR_CRIT, hover_color="#c0392b", width=110,
                          command=lambda p=prog: self._confirmar_desinstalar(p)).pack(side="right", padx=12, pady=10)

    def _confirmar_desinstalar(self, programa):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("apps_conf_desinst_titulo"))
        dialogo.geometry("440x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("apps_conf_desinst_msg", nombre=programa["nombre"]),
                     font=ctk.CTkFont(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            exito, comando = opt.desinstalar_programa(programa["desinstalar_cmd"])
            msg = (t("apps_desinst_ok", nombre=programa["nombre"]) if exito
                   else t("apps_desinst_error", nombre=programa["nombre"]))
            self._log_dev(t("apps_log_desinstalar", nombre=programa["nombre"]), comando, msg,
                          seccion=t("seccion_aplicaciones"), exito=exito)

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("apps_btn_desinstalar"), fg_color=COLOR_CRIT,
                      command=confirmar).pack(side="left", padx=8)

    # ---------------- Servicios de Windows ----------------
    def _mostrar_servicios(self):
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_serv_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        panel_consumo = ctk.CTkFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_consumo.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(panel_consumo, text=t("apps_serv_consumo_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(panel_consumo,
                     text=t("apps_serv_consumo_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=900, justify="left").pack(
            anchor="w", padx=14, pady=(0, 10))
        self.lista_servicios_consumo = ctk.CTkScrollableFrame(panel_consumo, fg_color="#141720",
                                                                corner_radius=10, height=160)
        self.lista_servicios_consumo.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(self.lista_servicios_consumo, text=t("apps_leyendo"),
                     text_color="gray60").pack(padx=8, pady=8)

        def worker_consumo():
            top = opt.listar_servicios_por_consumo(limite=12)
            self.after(0, lambda: self._pintar_servicios_consumo(top))
        threading.Thread(target=worker_consumo, daemon=True).start()

        fila_busqueda = ctk.CTkFrame(self.contenedor_apps, fg_color="transparent")
        fila_busqueda.pack(fill="x", pady=(0, 8))
        self.entry_buscar_servicio = ctk.CTkEntry(fila_busqueda,
                                                  placeholder_text=t("apps_buscar_servicio"))
        self.entry_buscar_servicio.pack(side="left", fill="x", expand=True)
        self.entry_buscar_servicio.bind("<KeyRelease>", lambda e: self._filtrar_servicios())

        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        lista.pack(fill="both", expand=True)
        ctk.CTkLabel(lista, text=t("apps_cargando_servicios"), text_color="gray60").pack(padx=16, pady=16)
        self.lista_servicios_frame = lista
        self._servicios_cache = None

        def worker():
            servicios = opt.listar_servicios_windows()
            self._servicios_cache = servicios
            self.after(0, self._filtrar_servicios)
            self._log_dev(t("apps_log_listar_servicios"), "Get-Service",
                          t("apps_servicios_encontrados", cantidad=len(servicios)),
                          seccion=t("seccion_aplicaciones"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_servicios_consumo(self, top):
        if not (hasattr(self, "lista_servicios_consumo") and self.lista_servicios_consumo.winfo_exists()):
            return
        for w in self.lista_servicios_consumo.winfo_children():
            w.destroy()
        if not top:
            ctk.CTkLabel(self.lista_servicios_consumo, text=t("apps_serv_consumo_error"),
                         text_color="gray60").pack(padx=8, pady=8)
            return
        for item in top:
            fila = ctk.CTkFrame(self.lista_servicios_consumo, fg_color=COLOR_BG_PANEL, corner_radius=8)
            fila.pack(fill="x", padx=4, pady=3)
            nombres_texto = ", ".join(item["servicios"][:4])
            if len(item["servicios"]) > 4:
                nombres_texto += t("apps_serv_mas", cantidad=len(item["servicios"]) - 4)
            ctk.CTkLabel(fila, text=nombres_texto, font=ctk.CTkFont(size=12), anchor="w",
                         wraplength=650, justify="left").pack(side="left", padx=10, pady=8, fill="x", expand=True)
            ctk.CTkLabel(fila, text=opt.format_bytes(item["bytes_ram"]), font=ctk.CTkFont(size=11),
                         text_color="gray60").pack(side="right", padx=10)

    def _filtrar_servicios(self):
        if not (hasattr(self, "pestana_apps") and self.pestana_apps.winfo_exists()):
            return
        if self.pestana_apps.get() != t("apps_tab_servicios"):
            return
        if not (hasattr(self, "lista_servicios_frame") and self.lista_servicios_frame.winfo_exists()):
            return

        for w in self.lista_servicios_frame.winfo_children():
            w.destroy()

        servicios = self._servicios_cache
        if servicios is None:
            ctk.CTkLabel(self.lista_servicios_frame, text=t("apps_cargando_servicios"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        if not servicios:
            ctk.CTkLabel(self.lista_servicios_frame, text=t("apps_sin_servicios"),
                         text_color="gray60").pack(padx=16, pady=16)
            return

        termino = self.entry_buscar_servicio.get().strip().lower() if hasattr(self, "entry_buscar_servicio") else ""
        if termino:
            servicios = [s for s in servicios if termino in (s["nombre"] or "").lower()
                         or termino in (s["nombre_visible"] or "").lower()]

        for s in servicios[:200]:  # límite razonable para no saturar la interfaz
            riesgo, _ = opt.evaluar_riesgo_servicio(s["nombre"])
            fila = ctk.CTkFrame(self.lista_servicios_frame, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            # "Running" es el valor que devuelve Get-Service, no texto para
            # mostrar: se compara contra el, pero al usuario se le ensena la
            # version traducida.
            corriendo = s["estado"] == "Running"
            color_estado = COLOR_OK if corriendo else "gray60"
            texto = t("apps_serv_detalle",
                      visible=s["nombre_visible"] or s["nombre"], nombre=s["nombre"],
                      estado=t("apps_serv_en_ejecucion") if corriendo else t("apps_serv_detenido"))
            texto += "  🔒" if riesgo == "bloqueado" else ""
            ctk.CTkLabel(fila, text=texto, font=ctk.CTkFont(size=12), text_color=color_estado, anchor="w",
                         wraplength=560, justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            if riesgo == "bloqueado" and corriendo:
                ctk.CTkButton(fila, text=t("apps_btn_protegido"), width=90, fg_color="gray30",
                              hover_color="gray30", state="disabled").pack(side="right", padx=12, pady=8)
            elif corriendo:
                ctk.CTkButton(fila, text=t("apps_btn_detener"), width=90, fg_color=COLOR_WARN,
                              text_color="black",
                              command=lambda sv=s: self._confirmar_servicio(sv, "detener")).pack(
                    side="right", padx=12, pady=8)
            else:
                ctk.CTkButton(fila, text=t("apps_btn_iniciar"), width=90,
                              command=lambda sv=s: self._confirmar_servicio(sv, "iniciar")).pack(
                    side="right", padx=12, pady=8)

    def _confirmar_servicio(self, servicio, accion):
        nombre_mostrar = servicio["nombre_visible"] or servicio["nombre"]
        if accion == "detener":
            riesgo, motivo = opt.evaluar_riesgo_servicio(servicio["nombre"])
            if riesgo == "bloqueado":
                self._mostrar_popup_info(
                    t("apps_serv_protegido_titulo"),
                    t("apps_serv_protegido_msg", nombre=nombre_mostrar, motivo=motivo))
                return
        else:
            riesgo, motivo = "normal", None

        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("apps_conf_serv_titulo"))
        dialogo.geometry("460x240")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo,
                     text=(t("apps_conf_serv_detener", nombre=nombre_mostrar) if accion == "detener"
                           else t("apps_conf_serv_iniciar", nombre=nombre_mostrar)),
                     font=ctk.CTkFont(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))
        if riesgo == "advertencia":
            ctk.CTkLabel(dialogo, text=t("apps_serv_advertencia", motivo=motivo),
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=COLOR_WARN, wraplength=400, justify="center").pack(padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(dialogo, text=t("apps_serv_nota"),
                         font=ctk.CTkFont(size=11), text_color="gray60", wraplength=400, justify="center").pack(
                padx=20, pady=(0, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            def worker():
                exito, comando = opt.set_servicio_windows(servicio["nombre"], accion)
                # "accion" es la clave interna que entiende opt.set_servicio_windows;
                # antes se interpolaba tal cual en el mensaje de error, asi que la
                # build en ingles habria dicho: No se pudo detener -> "detener".
                detener = accion == "detener"
                if exito:
                    msg = (t("apps_serv_detenido_ok", nombre=nombre_mostrar) if detener
                           else t("apps_serv_iniciado_ok", nombre=nombre_mostrar))
                else:
                    msg = (t("apps_serv_detener_error", nombre=nombre_mostrar) if detener
                           else t("apps_serv_iniciar_error", nombre=nombre_mostrar))
                self._log_dev(t("apps_log_detener_serv", nombre=nombre_mostrar) if detener
                              else t("apps_log_iniciar_serv", nombre=nombre_mostrar),
                              comando, msg, seccion=t("seccion_aplicaciones"), exito=exito)
                self._servicios_cache = None
                self.after(0, self._mostrar_servicios)
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("apps_btn_confirmar"), fg_color=COLOR_WARN, text_color="black",
                      command=confirmar).pack(side="left", padx=8)

    # ---- Actualizar apps (winget — catálogo oficial de Microsoft) ----
    def _mostrar_actualizar_apps(self):
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_winget_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        fila = ctk.CTkFrame(self.contenedor_apps, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(fila, text=t("apps_btn_buscar_act"),
                      command=self._accion_buscar_winget).pack(side="left")

        self.lista_winget = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_winget.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_winget, text=t("apps_winget_presiona"),
                     text_color="gray60").pack(padx=16, pady=16)

    def _accion_buscar_winget(self):
        for w in self.lista_winget.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_winget, text=t("apps_winget_buscando"),
                     text_color="gray60").pack(padx=16, pady=16)

        def worker():
            if not opt.winget_disponible():
                self.after(0, lambda: self._pintar_winget(None, disponible=False))
                return
            exito, apps, comando = opt.listar_actualizaciones_winget()
            self._log_dev(t("apps_log_winget"), comando,
                          t("apps_winget_encontradas", cantidad=len(apps)) if exito
                          else t("apps_winget_fallo"),
                          seccion=t("seccion_aplicaciones"), exito=exito)
            self.after(0, lambda: self._pintar_winget(apps if exito else None, disponible=True))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_winget(self, apps, disponible):
        if not (hasattr(self, "lista_winget") and self.lista_winget.winfo_exists()):
            return
        for w in self.lista_winget.winfo_children():
            w.destroy()
        if not disponible:
            ctk.CTkLabel(self.lista_winget,
                         text=t("apps_winget_no_disponible"),
                         text_color="gray60", wraplength=850, justify="left").pack(padx=16, pady=16)
            return
        if apps is None:
            ctk.CTkLabel(self.lista_winget, text=t("apps_winget_error"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        if not apps:
            ctk.CTkLabel(self.lista_winget, text=t("apps_winget_al_dia"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        ctk.CTkLabel(self.lista_winget,
                     text=t("apps_winget_nota"),
                     font=ctk.CTkFont(size=11), text_color="gray50", wraplength=850, justify="left").pack(
            padx=12, pady=(8, 8), anchor="w")
        for linea in apps:
            fila = ctk.CTkFrame(self.lista_winget, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(fila, text=linea, font=ctk.CTkFont(family="Consolas", size=11), anchor="w",
                         wraplength=750, justify="left").pack(side="left", padx=12, pady=8, fill="x", expand=True)

    # ---- Tareas programadas (de terceros, no la nuestra) ----
    def _mostrar_tareas_programadas(self):
        self._limpiar_contenedor_apps()
        ctk.CTkLabel(self.contenedor_apps,
                     text=t("apps_tareas_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").pack(
            fill="x", pady=(0, 10), anchor="w")

        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color=COLOR_BG_PANEL, corner_radius=16)
        lista.pack(fill="both", expand=True)
        ctk.CTkLabel(lista, text=t("apps_leyendo_tareas"), text_color="gray60").pack(padx=16, pady=16)
        self.lista_tareas_frame = lista

        def worker():
            tareas = opt.listar_tareas_programadas_terceros()
            self.after(0, lambda: self._pintar_tareas_programadas(tareas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_tareas_programadas(self, tareas):
        if not (hasattr(self, "lista_tareas_frame") and self.lista_tareas_frame.winfo_exists()):
            return
        for w in self.lista_tareas_frame.winfo_children():
            w.destroy()
        if not tareas:
            ctk.CTkLabel(self.lista_tareas_frame, text=t("apps_sin_tareas"),
                         text_color="gray60").pack(padx=16, pady=16)
            return
        # La variable del bucle se llamaba "t" y pisaba la funcion t() de
        # traduccion dentro de esta funcion: cualquier llamada a t() aqui
        # habria reventado con "dict object is not callable".
        for tarea in tareas[:200]:
            fila = ctk.CTkFrame(self.lista_tareas_frame, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(fila, text=t("apps_tarea_detalle", nombre=tarea["nombre"], ruta=tarea["ruta"]),
                         font=ctk.CTkFont(size=11), anchor="w",
                         wraplength=850, justify="left").pack(padx=12, pady=6, fill="x", expand=True, anchor="w")

    # ---------------- Segundo plano: widget + Modo Juego ----------------
    def mostrar_segundo_plano(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("segplano_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ctk.CTkLabel(self.contenido,
                     text=t("segplano_subtitulo"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=900, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(2, weight=1)
        panel = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.grid(row=2, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        fila1 = ctk.CTkFrame(panel, fg_color="transparent")
        fila1.pack(fill="x", padx=20, pady=(20, 6))
        ctk.CTkLabel(fila1, text=t("segplano_widget_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.switch_widget = ctk.CTkSwitch(fila1, text="", command=self._toggle_widget)
        self.switch_widget.pack(side="right")
        ctk.CTkLabel(panel, text=t("segplano_widget_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            fill="x", padx=20, pady=(0, 16), anchor="w")

        sep2 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep2.pack(fill="x", padx=20, pady=4)

        fila3 = ctk.CTkFrame(panel, fg_color="transparent")
        fila3.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(fila3, text=t("segplano_limpieza_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.switch_limpieza = ctk.CTkSwitch(fila3, text="", command=self._toggle_limpieza_programada)
        self.switch_limpieza.pack(side="right")
        self.combo_frecuencia = ctk.CTkOptionMenu(
            fila3, values=[t("segplano_frec_diaria"), t("segplano_frec_semanal")], width=110)
        self.combo_frecuencia.pack(side="right", padx=(0, 8))
        horas_disponibles = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "22:00"]
        self.combo_hora_limpieza = ctk.CTkOptionMenu(fila3, values=horas_disponibles, width=90)
        self.combo_hora_limpieza.set(self.prefs.get("limpieza_hora", "09:00"))
        self.combo_hora_limpieza.pack(side="right", padx=(0, 8))

        # BUG corregido: opt.limpieza_programada_activa() llama a
        # schtasks /query (subprocess, hasta 15s de timeout) — se
        # consultaba directo en el hilo principal cada vez que se abría
        # esta pantalla. Ahora se consulta en un hilo aparte.
        def worker_estado_limpieza():
            if opt.limpieza_programada_activa():
                if hasattr(self, "switch_limpieza") and self.switch_limpieza.winfo_exists():
                    self.after(0, self.switch_limpieza.select)
        threading.Thread(target=worker_estado_limpieza, daemon=True).start()

        ctk.CTkLabel(panel,
                     text=t("segplano_limpieza_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            fill="x", padx=20, pady=(0, 20), anchor="w")

        self._boton_ver_reporte(panel)

    def _toggle_widget(self):
        """
        BUG corregido: antes esta función SIEMPRE mostraba el widget y
        forzaba el switch a encendido sin importar su estado — no había
        forma de apagarlo ni desde el switch ni desde la bandeja del
        sistema. Ahora decide según si el widget está realmente visible
        ahora mismo (no según el switch, para que también funcione
        correctamente cuando se llama desde el menú de la bandeja).
        """
        esta_visible = (self.performance_widget is not None
                         and self.performance_widget.state() != "withdrawn")
        if esta_visible:
            self.performance_widget.ocultar()
            encender = False
        else:
            if self.performance_widget is None:
                self.performance_widget = widget_mod.PerformanceWidget(self, on_cerrar=self._widget_cerrado_manualmente)
                self._log_dev(t("gaming_log_widget"), t("gaming_widget_cmd"),
                              t("gaming_widget_mostrado"),
                              seccion=t("seccion_segundo_plano"), exito=True)
            else:
                self.performance_widget.mostrar()
            encender = True

        if hasattr(self, "switch_widget") and self.switch_widget.winfo_exists():
            (self.switch_widget.select() if encender else self.switch_widget.deselect())
        self.prefs["widget_visible"] = encender
        prefs.guardar({"widget_visible": encender})

    def _widget_cerrado_manualmente(self):
        """El usuario cerró el widget con su propio botón ✕ (no desde el
        switch del panel) — sincroniza el switch y la preferencia guardada."""
        if hasattr(self, "switch_widget") and self.switch_widget.winfo_exists():
            self.switch_widget.deselect()
        self.prefs["widget_visible"] = False
        prefs.guardar({"widget_visible": False})

    # ---------------- Gaming ----------------
    def mostrar_gaming(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("gaming_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ctk.CTkLabel(self.contenido, text=t("gaming_subtitulo"),
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(2, weight=1)
        contenedor = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        contenedor.grid(row=2, column=0, columnspan=3, sticky="nswe")

        # ---- Tarjeta principal: Modo Juego ----
        panel_modo = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_modo.pack(fill="x", padx=8, pady=8)
        fila_modo = ctk.CTkFrame(panel_modo, fg_color="transparent")
        fila_modo.pack(fill="x", padx=20, pady=(20, 6))
        self.lbl_estado_gaming = ctk.CTkLabel(fila_modo, text=t("gaming_modo_juego"),
                                               font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_estado_gaming.pack(side="left")
        self.switch_gaming = ctk.CTkSwitch(fila_modo, text="", command=self._toggle_autopilot)
        self.switch_gaming.pack(side="right")
        if self.autopilot.activo:
            self.switch_gaming.select()
        ctk.CTkLabel(panel_modo,
                     text=t("gaming_modo_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            fill="x", padx=20, pady=(0, 16), anchor="w")

        fila_botones_gaming = ctk.CTkFrame(panel_modo, fg_color="transparent")
        fila_botones_gaming.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(fila_botones_gaming, text=t("gaming_btn_antes"),
                      command=self._accion_antes_de_jugar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila_botones_gaming, text=t("gaming_btn_fps"), fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_fps).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila_botones_gaming, text=t("gaming_btn_enfoque"), fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_enfoque_asistido).pack(side="left")
        self.lbl_resultado_gaming = ctk.CTkLabel(panel_modo, text="", font=ctk.CTkFont(size=11),
                                                   text_color="gray70", wraplength=850, justify="left")
        self.lbl_resultado_gaming.pack(fill="x", padx=20, pady=(8, 4), anchor="w")

        ctk.CTkLabel(panel_modo,
                     text=t("gaming_nota_overlay"),
                     font=ctk.CTkFont(size=11), text_color="gray50", wraplength=850, justify="left").pack(
            fill="x", padx=20, pady=(0, 16), anchor="w")

        # ---- Tarjeta: biblioteca de juegos ----
        panel_biblioteca = ctk.CTkFrame(contenedor, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel_biblioteca.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(panel_biblioteca, text=t("gaming_biblioteca_titulo"),
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(panel_biblioteca,
                     text=t("gaming_biblioteca_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=850, justify="left").pack(
            anchor="w", padx=16, pady=(0, 10))
        self.lista_juegos = ctk.CTkScrollableFrame(panel_biblioteca, fg_color="#141720", corner_radius=10, height=220)
        self.lista_juegos.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(self.lista_juegos, text=t("gaming_buscando_juegos"), text_color="gray60").pack(
            padx=8, pady=8)

        def worker():
            juegos = opt.listar_juegos_instalados()
            self.after(0, lambda: self._pintar_juegos(juegos))
        threading.Thread(target=worker, daemon=True).start()

        self._actualizar_tarjeta_gaming()

    def _actualizar_tarjeta_gaming(self):
        if not (hasattr(self, "lbl_estado_gaming") and self.lbl_estado_gaming.winfo_exists()):
            return
        if self.autopilot.activo:
            self.lbl_estado_gaming.configure(text=t("gaming_modo_activado"), text_color=COLOR_OK)
        else:
            self.lbl_estado_gaming.configure(text=t("gaming_modo_apagado"), text_color=COLOR_WARN)

    def _pintar_juegos(self, juegos):
        if not (hasattr(self, "lista_juegos") and self.lista_juegos.winfo_exists()):
            return
        for w in self.lista_juegos.winfo_children():
            w.destroy()
        if not juegos:
            ctk.CTkLabel(self.lista_juegos,
                         text=t("gaming_sin_juegos"),
                         text_color="gray60").pack(padx=8, pady=8)
            return
        for j in juegos:
            fila = ctk.CTkFrame(self.lista_juegos, fg_color=COLOR_BG_PANEL, corner_radius=8)
            fila.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(fila, text=j["nombre"], font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(
                side="left", padx=10, pady=8, fill="x", expand=True)
            tamano_txt = opt.format_bytes(j["bytes"]) if j["bytes"] else t("gaming_tamano_nd")
            ctk.CTkLabel(fila, text=t("gaming_juego_detalle", plataforma=j["plataforma"], tamano=tamano_txt),
                         font=ctk.CTkFont(size=11),
                         text_color="gray60").pack(side="right", padx=10, pady=8)

    def _accion_antes_de_jugar(self):
        """Un clic que encadena: liberar RAM + activar Modo Juego (si no
        estaba activo) + abrir el contador de FPS — pensado para justo
        antes de sentarte a jugar, sin tener que ir sección por sección."""
        if hasattr(self, "lbl_resultado_gaming") and self.lbl_resultado_gaming.winfo_exists():
            self.lbl_resultado_gaming.configure(text=t("gaming_preparando"))

        def worker():
            liberado, procesos, cmd = opt.trim_process_memory()
            self._log_dev(t("gaming_log_antes_ram"), cmd,
                          t("gaming_ram_compactada", procesos=procesos,
                            tamano=opt.format_bytes(liberado)),
                          seccion=t("seccion_gaming"), exito=True, bytes_liberados=liberado, archivos_afectados=procesos)

            if not self.autopilot.activo:
                self.after(0, self._toggle_autopilot)

            exito_fps, comando_fps = opt.abrir_contador_fps_windows()
            self._log_dev(t("gaming_log_antes_fps"), comando_fps,
                          t("gaming_fps_abierto") if exito_fps else t("gaming_fps_no_abierto"),
                          seccion=t("seccion_gaming"), exito=exito_fps)

            msg = (t("gaming_listo_con_fps", tamano=opt.format_bytes(liberado)) if exito_fps
                   else t("gaming_listo_sin_fps", tamano=opt.format_bytes(liberado)))
            if hasattr(self, "lbl_resultado_gaming") and self.lbl_resultado_gaming.winfo_exists():
                self.after(0, lambda: self.lbl_resultado_gaming.configure(text=msg))
        threading.Thread(target=worker, daemon=True).start()

    def _toggle_autopilot(self):
        if not self.autopilot.activo:
            self.autopilot.iniciar()
            # BUG corregido: hasattr() solo confirma que el atributo existe,
            # no que el widget siga vivo. Si visitabas Gaming y luego
            # cambiabas de pantalla, ese switch se destruía pero la
            # referencia seguía ahí — tocarla (.select()) truena con un
            # widget destruido, y como esto se llama también desde el
            # atajo del widget flotante (que traga errores en silencio),
            # el resultado era "no pasa nada" sin ninguna pista de por qué.
            if hasattr(self, "switch_gaming") and self.switch_gaming.winfo_exists():
                self.switch_gaming.select()
            self._actualizar_tarjeta_gaming()

            def worker():
                exito_plan, comando_plan = opt.set_power_plan("rendimiento")
                self._log_dev(
                    t("gaming_log_activado"), comando_plan,
                    t("gaming_activado_ok") if exito_plan else t("gaming_activado_sin_plan"),
                    seccion=t("seccion_gaming"), exito=True)
            threading.Thread(target=worker, daemon=True).start()
        else:
            self.autopilot.detener()
            if hasattr(self, "switch_gaming") and self.switch_gaming.winfo_exists():
                self.switch_gaming.deselect()
            self._actualizar_tarjeta_gaming()

            def worker():
                # Se restaura siempre a "Equilibrado" (el plan por defecto de
                # la gran mayoría de equipos) en vez de intentar recordar el
                # plan exacto de antes, para mantenerlo simple y predecible.
                exito_plan, comando_plan = opt.set_power_plan("equilibrado")
                self._log_dev(
                    t("gaming_log_desactivado"), comando_plan,
                    t("gaming_desactivado_ok"),
                    seccion=t("seccion_gaming"), exito=True)
            threading.Thread(target=worker, daemon=True).start()

    def _accion_abrir_fps(self):
        exito, comando = opt.abrir_contador_fps_windows()
        msg = t("gaming_fps_ok") if exito else t("gaming_fps_error")
        self._log_dev(t("gaming_log_fps"), comando, msg,
                      seccion=t("seccion_gaming"), exito=exito)
        if not exito:
            self._mostrar_popup_info("Xbox Game Bar", msg)

    def _accion_abrir_enfoque_asistido(self):
        exito, comando = opt.abrir_configuracion_enfoque_asistido()
        msg = t("gaming_enfoque_ok") if exito else t("gaming_enfoque_error")
        self._log_dev(t("gaming_log_enfoque"), comando, msg,
                      seccion=t("seccion_gaming"), exito=exito)

    def _toggle_limpieza_programada(self):
        encender = bool(self.switch_limpieza.get())
        # Leer los valores de los widgets AQUÍ, en el hilo principal — Tkinter
        # no garantiza que .get() sea seguro de llamar desde un hilo aparte.
        # El valor del combo está traducido, así que NO se puede comparar contra
        # el literal "Diaria" — en la build en inglés diría "Daily" y esto habría
        # programado siempre WEEKLY sin dar ningún error. Se compara contra la
        # misma clave traducida que se usó para construir el combo.
        frecuencia = "DAILY" if self.combo_frecuencia.get() == t("segplano_frec_diaria") else "WEEKLY"
        hora = self.combo_hora_limpieza.get()
        etiqueta_frecuencia = self.combo_frecuencia.get().lower()

        def worker():
            if encender:
                exito, comando = opt.crear_limpieza_programada(frecuencia=frecuencia, hora=hora)
                msg = (t("segplano_programada_ok", frecuencia=etiqueta_frecuencia, hora=hora)
                       if exito else t("segplano_programada_error"))
                self._log_dev("Limpieza programada activada", comando, msg, seccion=t("seccion_segundo_plano"), exito=exito)
                if exito:
                    self.prefs["limpieza_hora"] = hora
                    prefs.guardar({"limpieza_hora": hora})
                elif hasattr(self, "switch_limpieza") and self.switch_limpieza.winfo_exists():
                    self.after(0, self.switch_limpieza.deselect)
            else:
                exito, comando = opt.quitar_limpieza_programada()
                self._log_dev("Limpieza programada desactivada", comando,
                              t("segplano_quitada_ok") if exito else t("segplano_quitada_error"),
                              seccion=t("seccion_segundo_plano"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Preferencias entre sesiones ----------------
    def _restaurar_preferencias(self):
        """Se llama una sola vez, poco después de abrir la app, para
        recuperar el estado de la sesión anterior (widget visible, perfil
        de energía). No fuerza nada si el equipo ya está en otro estado."""
        if self.prefs.get("widget_visible"):
            if self.performance_widget is None:
                self.performance_widget = widget_mod.PerformanceWidget(self, on_cerrar=self._widget_cerrado_manualmente)
            else:
                self.performance_widget.mostrar()
            if hasattr(self, "switch_widget") and self.switch_widget.winfo_exists():
                self.switch_widget.select()

        perfil_guardado = self.prefs.get("perfil_energia")
        if perfil_guardado and perfil_guardado in opt.POWER_PLANS:
            threading.Thread(target=lambda: opt.set_power_plan(perfil_guardado), daemon=True).start()

        # Modo Ligero: si nunca se preguntó y el equipo parece modesto
        # (pocos núcleos o poca RAM), sugerirlo UNA sola vez — nunca se
        # vuelve a insistir, sin importar la respuesta.
        if not self.prefs.get("modo_ligero_preguntado"):
            self.prefs["modo_ligero_preguntado"] = True
            prefs.guardar({"modo_ligero_preguntado": True})

            def worker():
                modesto = sysmon.es_equipo_modesto()
                if modesto:
                    self.after(0, self._sugerir_modo_ligero)
            threading.Thread(target=worker, daemon=True).start()

    def _sugerir_modo_ligero(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("ligero_titulo_ventana"))
        dialogo.geometry("420x220")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("ligero_titulo"),
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 6))
        ctk.CTkLabel(dialogo,
                     text=t("ligero_texto"),
                     font=ctk.CTkFont(size=12), wraplength=380, justify="left").pack(padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def activar():
            dialogo.destroy()
            self.prefs["modo_ligero"] = True
            prefs.guardar({"modo_ligero": True})
            self._aplicar_preferencia_animaciones()

        ctk.CTkButton(fila, text=t("ligero_no"), fg_color="gray40", command=dialogo.destroy).pack(
            side="left", padx=8)
        ctk.CTkButton(fila, text=t("ligero_si"), command=activar).pack(side="left", padx=8)

    def _intervalo(self, base_ms):
        """Todos los temporizadores recurrentes de la app pasan por aquí:
        con Modo Ligero activo, se espacian (multiplican) para consumir
        menos en equipos modestos — mismo comportamiento, menos frecuencia."""
        return base_ms * 3 if self.prefs.get("modo_ligero") else base_ms

    def _actualizar_temperatura_cpu(self):
        """Consulta la temperatura de CPU una vez y actualiza la caché
        compartida (self._cpu_temp_cache) — usado tanto por el chequeo
        periódico de alerta como al abrir Componentes por primera vez,
        para no esperar hasta 20s a que aparezca."""
        def worker():
            temp = sysmon.get_cpu_temperature()
            self._cpu_temp_cache = temp
            umbral = self.prefs.get("alerta_temp_cpu")
            if umbral and temp is not None and temp >= umbral:
                ahora = time.time()
                if ahora - self._ultima_alerta_temp > 600:
                    self._ultima_alerta_temp = ahora
                    opt.notificar_windows(
                        t("alerta_temp_titulo"),
                        t("alerta_temp_msg", temp=f"{temp:.0f}", umbral=f"{umbral:.0f}"))
        threading.Thread(target=worker, daemon=True).start()

    def _chequear_alerta_temperatura(self):
        """
        Revisa cada 20s (no más seguido: la lectura de temperatura no es
        gratis, y en equipos donde WMI está degradado puede tardar varios
        segundos) si la CPU pasó el umbral que el usuario definió en
        Ajustes. Si lo pasó, notifica — con un enfriamiento de 10 minutos
        entre avisos para no llenar de notificaciones repetidas.

        Optimización: esta misma consulta alimenta self._cpu_temp_cache,
        que también usa Componentes para mostrar la temperatura — así hay
        UNA sola consulta de temperatura por ciclo, no dos por separado.
        Y solo se consulta si de verdad hace falta (Componentes abierto,
        o alguna alerta configurada) — nunca en segundo plano sin que a
        nadie le importe el dato en ese momento, para no sumar carga
        constante de la nada.
        """
        umbral = self.prefs.get("alerta_temp_cpu")
        componentes_abierto = hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists()
        if umbral or componentes_abierto:
            self._actualizar_temperatura_cpu()
        self.after(self._intervalo(20000), self._chequear_alerta_temperatura)

    def _actualizar_icono_bandeja(self):
        """Si el usuario activó 'mostrar métrica en el ícono de la bandeja'
        (Ajustes), redibuja el ícono cada 2.5s con el valor actual — usa
        psutil directo (barato), nunca las consultas de CIM/PowerShell."""
        metrica = self.prefs.get("icono_bandeja_metrica")
        if metrica == "cpu":
            valor = psutil.cpu_percent(interval=None)
            self.tray.actualizar_valor_en_icono(valor, "C")
        elif metrica == "ram":
            valor = psutil.virtual_memory().percent
            self.tray.actualizar_valor_en_icono(valor, "R")
        self.after(self._intervalo(2500), self._actualizar_icono_bandeja)

    def _chequear_bateria_automatica(self):
        """
        Revisa cada 30s (equipos de escritorio sin batería: la llamada es
        gratis y sale de inmediato) si hay que activar el plan Silencioso
        por batería baja. Usa un margen de 10 puntos al restaurar (si el
        umbral es 20%, no vuelve a Equilibrado hasta pasar el 30% o
        empezar a cargar) para no estar cambiando de plan a cada rato
        cuando la batería ronda justo el umbral."""
        if self.prefs.get("bateria_ahorro_automatico"):
            umbral = self.prefs.get("bateria_umbral_ahorro", 20)

            def worker():
                info = sysmon.get_battery_info()
                if not info:
                    return
                if not info["cargando"] and info["porcentaje"] <= umbral and not self._modo_ahorro_bateria_activo:
                    self._modo_ahorro_bateria_activo = True
                    exito, comando = opt.set_power_plan("silencioso")
                    msg = t("bateria_msg", pct=f"{info['porcentaje']:.0f}")
                    self._log_dev(t("bateria_log_on"), comando, msg,
                                  seccion=t("seccion_automatico"), exito=exito)
                    opt.notificar_windows(t("bateria_titulo"), msg)
                elif self._modo_ahorro_bateria_activo and (info["cargando"] or info["porcentaje"] > umbral + 10):
                    self._modo_ahorro_bateria_activo = False
                    exito, comando = opt.set_power_plan("equilibrado")
                    self._log_dev(t("bateria_log_off"), comando,
                                  t("bateria_restaurado"), seccion=t("seccion_automatico"), exito=exito)
            threading.Thread(target=worker, daemon=True).start()
        self.after(self._intervalo(30000), self._chequear_bateria_automatica)

    # ---------------- Historial de actividad (transparencia) ----------------
    def mostrar_reporte(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("hist_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ctk.CTkLabel(self.contenido,
                     text=t("hist_subtitulo"),
                     font=ctk.CTkFont(size=12), text_color="gray60").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        resumen = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        resumen.grid(row=2, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 8))
        texto_resumen = t("hist_resumen",
                          total=self.reporte.total_acciones(),
                          exitosas=self.reporte.total_exitosas(),
                          fallidas=self.reporte.total_fallidas(),
                          espacio=opt.format_bytes(self.reporte.total_bytes_liberados()))
        ctk.CTkLabel(resumen, text=texto_resumen, font=ctk.CTkFont(size=13, weight="bold")).pack(
            padx=16, pady=12, anchor="w")

        fila_busqueda = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_busqueda.grid(row=3, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 6))
        self.entry_buscar_historial = ctk.CTkEntry(
            fila_busqueda, placeholder_text=t("hist_buscar_placeholder"))
        self.entry_buscar_historial.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_buscar_historial.bind("<KeyRelease>", lambda e: self._filtrar_historial())

        secciones = sorted({e["seccion"] for e in self.reporte.entries}) or []
        self.combo_seccion_historial = ctk.CTkOptionMenu(
            fila_busqueda, values=[t("hist_todas_secciones")] + secciones, width=180,
            command=lambda v: self._filtrar_historial())
        self.combo_seccion_historial.set(t("hist_todas_secciones"))
        self.combo_seccion_historial.pack(side="left")

        self.contenido.grid_rowconfigure(4, weight=1)
        self.lista_historial = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        self.lista_historial.grid(row=4, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        self._filtrar_historial()

        ctk.CTkButton(self.contenido, text=t("hist_exportar"),
                      command=self._exportar_reporte).grid(row=5, column=0, sticky="w", padx=8, pady=8)

    def _filtrar_historial(self):
        if not (hasattr(self, "lista_historial") and self.lista_historial.winfo_exists()):
            return
        for w in self.lista_historial.winfo_children():
            w.destroy()

        termino = self.entry_buscar_historial.get().strip().lower() if hasattr(self, "entry_buscar_historial") else ""
        seccion_elegida = (self.combo_seccion_historial.get()
                           if hasattr(self, "combo_seccion_historial") else t("hist_todas_secciones"))
        entradas = self.reporte.entradas_recientes_primero()
        if termino:
            entradas = [e for e in entradas if termino in e["accion"].lower()
                        or termino in e["seccion"].lower()
                        or termino in e["resultado"].lower()]
        if seccion_elegida and seccion_elegida != t("hist_todas_secciones"):
            entradas = [e for e in entradas if e["seccion"] == seccion_elegida]

        if not entradas:
            texto = (t("hist_vacio")
                     if not termino and seccion_elegida == t("hist_todas_secciones")
                     else t("hist_sin_resultados"))
            ctk.CTkLabel(self.lista_historial, text=texto, text_color="gray60").pack(padx=16, pady=16)
        else:
            for e in entradas:
                self._crear_tarjeta_reporte(self.lista_historial, e)

    def _crear_tarjeta_reporte(self, parent, entrada):
        tarjeta = ctk.CTkFrame(parent, fg_color="#141720", corner_radius=10)
        tarjeta.pack(fill="x", padx=8, pady=5)

        icono = "✅" if entrada["exito"] else "❌"
        color = COLOR_OK if entrada["exito"] else COLOR_CRIT

        titulo = (f'{icono}  [{entrada["timestamp"]}]  {entrada["seccion"]} → {entrada["accion"]}')
        ctk.CTkLabel(tarjeta, text=titulo, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=color, anchor="w").pack(fill="x", padx=12, pady=(10, 2))

        # El comando técnico exacto solo se muestra en la Edición Administrador.
        if EDICION == "admin":
            ctk.CTkLabel(tarjeta, text=t("hist_comando", comando=entrada["comando"]),
                         font=ctk.CTkFont(family="Consolas", size=11),
                         text_color="gray60", anchor="w", wraplength=900, justify="left").pack(
                fill="x", padx=12, pady=1)

        ctk.CTkLabel(tarjeta, text=t("hist_resultado", resultado=entrada["resultado"]),
                     font=ctk.CTkFont(size=12),
                     anchor="w", wraplength=900, justify="left").pack(fill="x", padx=12, pady=(1, 10))

    def _exportar_reporte(self):
        carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
        destino = os.path.join(carpeta, "reporte_techclean.txt")
        incluir_comando = (EDICION == "admin")
        try:
            ruta = self.reporte.export_txt(destino, incluir_comando=incluir_comando)
        except Exception:
            ruta = self.reporte.export_txt(os.path.join(prefs.carpeta_datos(), "reporte_techclean.txt"),
                                            incluir_comando=incluir_comando)
        self._mostrar_popup_info(t("hist_exportado_titulo"), t("hist_exportado_msg", ruta=ruta))

    def _mostrar_popup_info(self, titulo, mensaje):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(titulo)
        dialogo.geometry("420x150")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=mensaje, wraplength=380, justify="center").pack(pady=30, padx=20)
        ctk.CTkButton(dialogo, text=t("comun_ok"), command=dialogo.destroy).pack(pady=10)

    # ---------------- Manejo global de errores ----------------
    def report_callback_exception(self, exc, val, tb):
        """
        Tkinter llama a este método automáticamente cada vez que un clic,
        un evento o un temporizador lanza un error que nadie atrapó — por
        defecto Windows no muestra nada (ni siquiera hay una consola en la
        app compilada), así que un bug se sentía como "esto no hace nada"
        sin ninguna pista de qué falló. Ahora se ve, se guarda, y queda en
        el Historial — la próxima vez que algo falle, hay un texto exacto
        para copiar y pegar en vez de tener que describir qué se vio raro.
        """
        import traceback
        texto_error = "".join(traceback.format_exception(exc, val, tb))
        self._reportar_error_interno(texto_error)

    def _reportar_error_interno(self, texto_error):
        # Se registra SIEMPRE, pase lo que pase con el resto de este método.
        try:
            ultima_linea = texto_error.strip().splitlines()[-1][:250]
            self.reporte.add(t("seccion_sistema"), t("hist_error_interno_accion"), ultima_linea,
                              False, t("hist_error_interno_resultado"), 0, 0)
        except Exception:
            pass
        try:
            ruta = os.path.join(prefs.carpeta_datos(), "ultimo_error.txt")
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n{texto_error}\n")
        except Exception:
            pass

        # No spamear: si ya se mostró un aviso hace menos de 5 segundos
        # (por ejemplo, un temporizador que falla cada 2s), esta vez solo
        # se registra arriba — no se abren ventanas encima de ventanas.
        ahora = time.time()
        if ahora - self._ultimo_aviso_error < 5:
            return
        self._ultimo_aviso_error = ahora
        try:
            self._mostrar_ventana_error(texto_error)
        except Exception:
            pass

    def _mostrar_ventana_error(self, texto_error):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("error_titulo_ventana"))
        dialogo.geometry("580x380")
        # Deliberadamente SIN grab_set(): un error puede ocurrir mientras
        # ya hay otra ventana modal abierta (como la de reparación), y
        # forzar un grab ahí podría chocar con el que ya existe. En vez de
        # eso, se marca "siempre encima" — sigue siendo visible sin correr
        # ese riesgo.
        try:
            dialogo.attributes("-topmost", True)
        except Exception:
            pass
        ctk.CTkLabel(dialogo, text=t("error_encabezado"),
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_CRIT).pack(pady=(16, 4))
        ctk.CTkLabel(dialogo,
                     text=t("error_explicacion"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=520, justify="left").pack(
            padx=20, pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=ctk.CTkFont(family="Consolas", size=10))
        caja.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        caja.insert("1.0", texto_error)
        caja.configure(state="disabled")
        ctk.CTkButton(dialogo, text=t("comun_cerrar"), command=dialogo.destroy).pack(pady=(0, 16))

    # ---------------- Consola de desarrollador (solo Edición Administrador) ----------------
    def mostrar_consola(self):
        if EDICION != "admin":
            self.mostrar_dashboard()
            return
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text="Panel de Desarrollador",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(1, weight=1)
        self.dev_console = DevConsole(
            self.contenido,
            on_comando=lambda texto: self._ejecutar_comando(texto, consola=self.dev_console))
        self.dev_console.grid(row=1, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        referencia = (
            "Comandos de referencia que esta app puede ejecutar:\n"
            "  • EmptyWorkingSet (psapi.dll) — compactar RAM de procesos\n"
            "  • del /s /q %TEMP%\\* — limpiar temporales\n"
            "  • SHEmptyRecycleBinW (shell32.dll) — vaciar papelera\n"
            "  • ipconfig /flushdns — limpiar caché DNS\n"
            "  • DELETE FROM urls/visits — borrar historial de navegador (SQLite)\n"
            "  • shutdown /r /fw /t 5 — reiniciar directo a BIOS/UEFI\n"
            "  • SetPriorityClass(HIGH_PRIORITY_CLASS) — impulsar un juego en primer plano\n"
            "  • reg add HKCU\\...\\Run — activar inicio automático con Windows"
        )
        ctk.CTkLabel(self.contenido, text=referencia, justify="left", anchor="w",
                     font=ctk.CTkFont(family="Consolas", size=11), text_color="gray60").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

    def _log_dev(self, accion, comando, resultado, seccion=None, exito=True,
                 bytes_liberados=0, archivos_afectados=0):
        """
        Punto único de registro: alimenta la consola dev Y el historial.

        BUG corregido: el autopiloto llama a _log_dev desde su propio hilo
        de fondo (no el hilo principal de Tkinter). Tocar un widget desde
        un hilo que no es el principal es inseguro en Tkinter y puede
        causar fallos intermitentes. Por eso el trabajo real se agenda
        siempre con self.after(0, ...), que es seguro de llamar desde
        cualquier hilo — la función interna solo se ejecuta en el hilo
        principal, sin importar desde dónde se llamó a _log_dev.
        """
        # seccion se resuelve AQUI y no como valor por defecto en la firma:
        # un t(...) en la firma se evaluaria al importar el modulo, antes de
        # que establecer_idioma() corra, y quedaria congelado en el idioma
        # que tuviera idiomas.py por defecto.
        if seccion is None:
            seccion = t("seccion_general")

        def _hacer():
            if self.dev_console is not None:
                try:
                    self.dev_console.log(accion, comando, resultado)
                except Exception:
                    pass
            self.reporte.add(seccion, accion, comando, exito, resultado,
                              bytes_liberados, archivos_afectados)
        self.after(0, _hacer)

    # ---------------- Panel de comandos oculto (solo Edición Cliente) ----------------
    def mostrar_panel_oculto(self):
        if EDICION != "cliente" or not self.modo_desarrollador.get():
            self.mostrar_dashboard()
            return
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text="Panel de comandos",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(1, weight=1)
        self.consola_comandos = ComandoConsole(self.contenido, on_comando=self._ejecutar_comando)
        self.consola_comandos.grid(row=1, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

    def _ejecutar_comando(self, texto, consola=None):
        comando = texto.strip().lower()
        consola = consola if consola is not None else self.consola_comandos
        # El mismo motor de comandos alimenta el panel oculto del cliente Y
        # la Consola Dev del admin — se etiqueta el origen correcto en el Historial.
        seccion_origen = t("consola_seccion_dev") if EDICION == "admin" else t("consola_seccion_oculto")

        if comando in ("/help", "/ayuda", "ayuda", "help", "?"):
            lineas = [f'{c}  —  {t(clave)}' for c, clave in COMANDOS_DISPONIBLES.items()]
            consola.imprimir("\n".join(lineas))
            return

        if comando == "/ram":
            consola.imprimir(t("consola_liberando_ram"))

            def worker():
                liberado, afectados, _ = opt.trim_process_memory()
                msg = t("consola_ram_ok", procesos=afectados, tamano=opt.format_bytes(liberado))
                self.after(0, lambda: consola.imprimir(msg))
                self._log_dev(t("consola_log_ram", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_liberados=liberado, archivos_afectados=afectados)
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/temporales":
            consola.imprimir(t("consola_limpiando_temp"))

            def worker():
                liberado, borrados, _ = opt.clear_temp_files()
                msg = t("consola_temp_ok", archivos=borrados, tamano=opt.format_bytes(liberado))
                self.after(0, lambda: consola.imprimir(msg))
                self._log_dev(t("consola_log_temp", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_liberados=liberado, archivos_afectados=borrados)
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/papelera":
            exito, _ = opt.empty_recycle_bin()
            msg = t("consola_papelera_ok") if exito else t("consola_papelera_error")
            consola.imprimir(msg)
            self._log_dev(t("consola_log_papelera", origen=seccion_origen), "N/A", msg,
                          seccion=seccion_origen, exito=exito)
            return

        if comando == "/dns":
            exito, _ = opt.flush_dns()
            msg = t("consola_dns_ok") if exito else t("consola_dns_error")
            consola.imprimir(msg)
            self._log_dev(t("consola_log_dns", origen=seccion_origen), "N/A", msg,
                          seccion=seccion_origen, exito=exito)
            return

        if comando == "/rapido":
            consola.imprimir(t("consola_rapido"))

            def worker():
                liberado_ram, procesos, _ = opt.trim_process_memory()
                liberado_disco, archivos, _ = opt.clear_temp_files()
                msg = t("consola_rapido_ok", procesos=procesos,
                        ram=opt.format_bytes(liberado_ram), archivos=archivos,
                        disco=opt.format_bytes(liberado_disco))
                self.after(0, lambda: consola.imprimir(msg))
                self._log_dev(t("consola_log_rapido", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_liberados=liberado_ram + liberado_disco,
                              archivos_afectados=procesos + archivos)
            threading.Thread(target=worker, daemon=True).start()
            return

        navegacion = {
            "/inicio": self.mostrar_dashboard,
            "/componentes": self.mostrar_componentes,
            "/optimizar": self.mostrar_optimizador,
            "/reparar": self.mostrar_reparar,
            "/seguridad": self.mostrar_seguridad,
            "/gaming": self.mostrar_gaming,
            "/apps": self.mostrar_aplicaciones,
            "/privacidad": self.mostrar_privacidad,
            "/historial": self.mostrar_reporte,
            "/bios": self.mostrar_bios,
            "/ajustes": self.mostrar_ajustes,
            "/salir": self.mostrar_dashboard,
        }
        if comando in navegacion:
            consola.imprimir(t("consola_abriendo"))
            self.after(300, navegacion[comando])
            return

        if comando == "/widget":
            self._toggle_widget()
            consola.imprimir(t("consola_widget_ok") if self.performance_widget
                             else t("consola_widget_error"))
            return

        if comando == "/auto":
            self._toggle_autopilot()
            consola.imprimir(t("consola_modo_juego",
                                estado=t("consola_activado") if self.autopilot.activo
                                else t("consola_desactivado")))
            return

        if comando == "/fps":
            exito, _ = opt.abrir_contador_fps_windows()
            consola.imprimir(t("consola_fps_ok") if exito else t("consola_fps_error"))
            return

        consola.imprimir(t("consola_no_reconocido", comando=texto))

    # ---------------- BIOS / UEFI ----------------
    def mostrar_bios(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("energia_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        self.contenido.grid_rowconfigure(1, weight=1)
        panel = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.grid(row=1, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        ctk.CTkLabel(panel,
                     text=t("energia_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=850, justify="left").pack(
            padx=20, pady=(20, 16), anchor="w")

        acciones = [
            (t("energia_apagar"), t("energia_apagar_desc"), self._confirmar_apagar, COLOR_CRIT, "white"),
            (t("energia_reiniciar"), t("energia_reiniciar_desc"),
             self._confirmar_reiniciar, COLOR_CRIT, "white"),
            (t("energia_suspender"), t("energia_suspender_desc"),
             self._accion_suspender, "#2a2d36", "white"),
            (t("energia_hibernar"), t("energia_hibernar_desc"),
             self._accion_hibernar, "#2a2d36", "white"),
            (t("energia_bios"), t("energia_bios_desc"),
             self._confirmar_reinicio_bios, COLOR_WARN, "black"),
        ]
        for texto, descripcion, cmd, color, color_texto in acciones:
            fila = ctk.CTkFrame(panel, fg_color="#141720", corner_radius=10)
            fila.pack(fill="x", padx=20, pady=6)
            ctk.CTkButton(fila, text=texto, width=220, height=44, fg_color=color, text_color=color_texto,
                          command=cmd).pack(side="left", padx=12, pady=12)
            ctk.CTkLabel(fila, text=descripcion, font=ctk.CTkFont(size=11), text_color="gray60",
                         wraplength=560, justify="left", anchor="w").pack(side="left", padx=10, fill="x")

        ctk.CTkLabel(panel, text="", font=ctk.CTkFont(size=1)).pack(pady=6)

    def _confirmar_apagar(self):
        self._confirmar_accion_energia(
            t("energia_conf_apagar_tit"), t("energia_conf_apagar_msg"),
            t("energia_conf_apagar_btn"),
            lambda: self._ejecutar_accion_energia(opt.apagar_equipo, t("energia_log_apagar")))

    def _confirmar_reiniciar(self):
        self._confirmar_accion_energia(
            t("energia_conf_reiniciar_tit"), t("energia_conf_reiniciar_msg"),
            t("energia_conf_reiniciar_btn"),
            lambda: self._ejecutar_accion_energia(opt.reiniciar_equipo, t("energia_log_reiniciar")))

    def _confirmar_reinicio_bios(self):
        self._confirmar_accion_energia(
            t("energia_conf_bios_tit"), t("energia_conf_bios_msg"),
            t("energia_conf_bios_btn"),
            lambda: self._ejecutar_accion_energia(opt.restart_to_uefi, t("energia_log_bios")))

    def _confirmar_accion_energia(self, titulo, mensaje, texto_boton, accion_confirmada):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("420x200")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=titulo, font=ctk.CTkFont(size=15, weight="bold"),
                     wraplength=380, justify="center").pack(pady=(20, 6))
        ctk.CTkLabel(dialogo, text=mensaje, font=ctk.CTkFont(size=12), text_color="gray60",
                     wraplength=380, justify="center").pack(padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            accion_confirmada()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=texto_boton, fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=confirmar).pack(side="left", padx=8)

    def _ejecutar_accion_energia(self, funcion, nombre_para_historial):
        exito, comando = funcion()
        resultado = t("energia_log_ok") if exito else t("energia_log_error")
        self._log_dev(nombre_para_historial, comando, resultado, seccion=t("seccion_energia"), exito=exito)

    def _accion_suspender(self):
        def worker():
            exito, comando = opt.suspender_equipo()
            self._log_dev(t("energia_log_suspender"), comando,
                          t("energia_log_suspendido") if exito else t("energia_log_suspender_error"),
                          seccion=t("seccion_energia"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_hibernar(self):
        def worker():
            exito, comando = opt.hibernar_equipo()
            self._log_dev(t("energia_log_hibernar"), comando,
                          t("energia_log_hibernado") if exito else t("energia_log_hibernar_error"),
                          seccion=t("seccion_energia"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Ajustes (créditos + easter egg + inicio automático) ----------------
    def mostrar_ajustes(self):
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("ajustes_titulo"),
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        # BUG corregido: "panel" era un CTkFrame normal (sin scroll). Con
        # todo lo que se le fue agregando (inicio automático, alerta de
        # temperatura, ícono de bandeja, batería, métricas del widget,
        # exportar/importar/restablecer...) el contenido ya no cabía en
        # pantalla y no había forma de bajar para ver el resto — quedaba
        # cortado. Ahora es un CTkScrollableFrame.
        self.contenido.grid_rowconfigure(1, weight=1)
        panel = ctk.CTkScrollableFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=16)
        panel.grid(row=1, column=0, columnspan=3, sticky="nswe", padx=8, pady=8)

        self.lbl_version = ctk.CTkLabel(
            panel, text=t("ajustes_version", version=APP_VERSION),
            font=ctk.CTkFont(size=15, weight="bold"),
            cursor="hand2" if EDICION == "cliente" else "arrow")
        self.lbl_version.pack(padx=20, pady=(20, 4), anchor="w")
        if EDICION == "cliente":
            self.lbl_version.bind("<Button-1>", self._click_dev_unlock)

        self.lbl_credito = ctk.CTkLabel(
            panel, text=t("ajustes_desarrollado_por", nombre=DEV_NAME, alias=DEV_ALIAS),
            font=ctk.CTkFont(size=13), text_color="gray70", cursor="hand2")
        self.lbl_credito.pack(padx=20, pady=(0, 4), anchor="w")
        self.lbl_credito.bind("<Button-1>", self._click_easter_egg)

        ctk.CTkLabel(panel, text=t("ajustes_descripcion_app"),
                     font=ctk.CTkFont(size=12), text_color="gray60").pack(padx=20, pady=(0, 8), anchor="w")

        # La tarjeta de apoyo va deliberadamente distinta al resto de filas de
        # Ajustes: antes era un boton gris "#2a2d36" identico al de Buscar
        # actualizaciones justo debajo, y se perdia entre las demas opciones.
        # Ahora tiene fondo calido propio, borde de acento y su propio titulo,
        # para que se distinga sin volverse un anuncio molesto.
        tarjeta_donar = ctk.CTkFrame(panel, fg_color="#241f1a", corner_radius=12,
                                     border_width=1, border_color=COLOR_DONAR)
        tarjeta_donar.pack(fill="x", padx=20, pady=(4, 12))

        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_titulo"),
                     font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_DONAR).pack(
            padx=16, pady=(14, 2), anchor="w")
        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_desc"),
                     font=ctk.CTkFont(size=12), text_color="gray70",
                     wraplength=620, justify="left").pack(padx=16, pady=(0, 2), anchor="w")
        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_nota"),
                     font=ctk.CTkFont(size=11), text_color="gray50",
                     wraplength=620, justify="left").pack(padx=16, pady=(0, 10), anchor="w")
        ctk.CTkButton(tarjeta_donar, text=t("ajustes_donar_boton"), width=200, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=COLOR_DONAR, hover_color="#e0524f", text_color="white",
                      command=self._accion_abrir_donacion).pack(padx=16, pady=(0, 16), anchor="w")

        fila_actualizacion = ctk.CTkFrame(panel, fg_color="transparent")
        fila_actualizacion.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(fila_actualizacion, text=t("ajustes_buscar_actualizaciones"), width=180, fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_buscar_actualizacion_manual).pack(side="left")
        self.lbl_resultado_actualizacion = ctk.CTkLabel(fila_actualizacion, text="",
                                                          font=ctk.CTkFont(size=11), text_color="gray60")
        self.lbl_resultado_actualizacion.pack(side="left", padx=10)
        ctk.CTkLabel(panel, text="", font=ctk.CTkFont(size=1)).pack(pady=(0, 12))

        sep_idioma = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_idioma.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(panel, text=t("ajustes_idioma_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        ctk.CTkLabel(panel, text=t("ajustes_idioma_descripcion"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 8), anchor="w")
        fila_idioma = ctk.CTkFrame(panel, fg_color="transparent")
        fila_idioma.pack(fill="x", padx=20, pady=(0, 20))
        self.combo_idioma = ctk.CTkOptionMenu(fila_idioma, values=list(idiomas.IDIOMAS_DISPONIBLES.values()),
                                               command=self._cambiar_idioma, width=140)
        self.combo_idioma.set(idiomas.IDIOMAS_DISPONIBLES.get(self.prefs.get("idioma", "es"), "Español"))
        self.combo_idioma.pack(side="left")

        sep = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep.pack(fill="x", padx=20, pady=10)

        fila_inicio = ctk.CTkFrame(panel, fg_color="transparent")
        fila_inicio.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_inicio, text=t("ajustes_inicio_windows_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.switch_inicio = ctk.CTkSwitch(fila_inicio, text="", command=self._toggle_inicio_automatico)
        self.switch_inicio.pack(side="right")
        if opt.is_startup_enabled():
            self.switch_inicio.select()
        ctk.CTkLabel(panel, text=t("ajustes_inicio_windows_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep2 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep2.pack(fill="x", padx=20, pady=10)

        fila_temp = ctk.CTkFrame(panel, fg_color="transparent")
        fila_temp.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_temp, text=t("ajustes_alerta_temp_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.entry_alerta_temp = ctk.CTkEntry(fila_temp, width=70, placeholder_text=t("ajustes_temp_placeholder"))
        umbral_actual = self.prefs.get("alerta_temp_cpu")
        if umbral_actual:
            self.entry_alerta_temp.insert(0, str(int(umbral_actual)))
        self.entry_alerta_temp.pack(side="right")
        ctk.CTkButton(fila_temp, text=t("ajustes_guardar"), width=80, command=self._guardar_alerta_temp).pack(
            side="right", padx=(0, 8))
        ctk.CTkLabel(panel, text=t("ajustes_alerta_temp_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep3 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep3.pack(fill="x", padx=20, pady=10)

        fila_ligero = ctk.CTkFrame(panel, fg_color="transparent")
        fila_ligero.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_ligero, text=t("ajustes_modo_ligero_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.switch_modo_ligero = ctk.CTkSwitch(fila_ligero, text="", command=self._toggle_modo_ligero)
        self.switch_modo_ligero.pack(side="right")
        if self.prefs.get("modo_ligero"):
            self.switch_modo_ligero.select()
        ctk.CTkLabel(panel, text=t("ajustes_modo_ligero_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep_umbral_ram = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_umbral_ram.pack(fill="x", padx=20, pady=10)

        fila_umbral_ram = ctk.CTkFrame(panel, fg_color="transparent")
        fila_umbral_ram.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_umbral_ram, text=t("ajustes_umbral_ram_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.combo_umbral_ram = ctk.CTkOptionMenu(
            fila_umbral_ram, values=["50%", "60%", "70%", "75%", "80%", "85%", "90%"], width=90,
            command=lambda v: self._guardar_umbral_ram(int(v.replace("%", ""))))
        self.combo_umbral_ram.set(f'{self.prefs.get("umbral_ram_auto", 85)}%')
        self.combo_umbral_ram.pack(side="right")
        ctk.CTkLabel(panel, text=t("ajustes_umbral_ram_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep_umbral_salud = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_umbral_salud.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(panel, text=t("ajustes_umbral_salud_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        fila_salud_ram = ctk.CTkFrame(panel, fg_color="transparent")
        fila_salud_ram.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(fila_salud_ram, text=t("ajustes_umbral_salud_ram"), font=ctk.CTkFont(size=12)).pack(
            side="left")
        self.combo_umbral_salud_ram = ctk.CTkOptionMenu(
            fila_salud_ram, values=["60%", "65%", "70%", "75%", "80%", "85%"], width=90,
            command=lambda v: self._guardar_umbral_salud("ram", int(v.replace("%", ""))))
        self.combo_umbral_salud_ram.set(f'{self.prefs.get("umbral_salud_ram", 75)}%')
        self.combo_umbral_salud_ram.pack(side="right")
        fila_salud_disco = ctk.CTkFrame(panel, fg_color="transparent")
        fila_salud_disco.pack(fill="x", padx=20, pady=(4, 4))
        ctk.CTkLabel(fila_salud_disco, text=t("ajustes_umbral_salud_disco"), font=ctk.CTkFont(size=12)).pack(
            side="left")
        self.combo_umbral_salud_disco = ctk.CTkOptionMenu(
            fila_salud_disco, values=["70%", "75%", "80%", "85%", "90%", "95%"], width=90,
            command=lambda v: self._guardar_umbral_salud("disco", int(v.replace("%", ""))))
        self.combo_umbral_salud_disco.set(f'{self.prefs.get("umbral_salud_disco", 85)}%')
        self.combo_umbral_salud_disco.pack(side="right")
        ctk.CTkLabel(panel, text=t("ajustes_umbral_salud_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(4, 20), anchor="w")

        sep_ligero = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_ligero.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(panel, text=t("ajustes_errores_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        ctk.CTkLabel(panel, text=t("ajustes_errores_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 8), anchor="w")
        fila_diagnostico = ctk.CTkFrame(panel, fg_color="transparent")
        fila_diagnostico.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(fila_diagnostico, text=t("ajustes_diagnostico_boton"),
                      command=self._accion_diagnostico_completo, width=200).pack(side="left")
        fila_errores = ctk.CTkFrame(panel, fg_color="transparent")
        fila_errores.pack(fill="x", padx=20, pady=(0, 20))
        # Los dos botones de "Probar error" provocan un fallo A PROPOSITO para
        # comprobar que el aviso de errores funciona. Al usuario final no le
        # sirven de nada: su unico efecto visible es una ventana de error
        # alarmante sin que haya pasado nada malo. Solo en la edicion admin.
        # El resto de esta seccion (Diagnostico completo, Abrir carpeta de
        # registros) SI se queda en cliente: son justo las herramientas que se
        # le piden a alguien cuando reporta un problema.
        if EDICION == "admin":
            ctk.CTkButton(fila_errores, text=t("ajustes_probar_error_directo"), fg_color="#2a2d36",
                          hover_color="#3a3e4a", command=self._accion_probar_error).pack(
                side="left", padx=(0, 8))
            ctk.CTkButton(fila_errores, text=t("ajustes_probar_error_segundo_plano"), fg_color="#2a2d36",
                          hover_color="#3a3e4a", command=self._accion_probar_error_segundo_plano).pack(
                side="left", padx=(0, 8))
        ctk.CTkButton(fila_errores, text=t("ajustes_abrir_carpeta_registros"), fg_color="#2a2d36",
                      hover_color="#3a3e4a", command=self._accion_abrir_carpeta_datos).pack(side="left")

        sep_reporte_rendimiento = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_reporte_rendimiento.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(panel, text=t("rend_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        ctk.CTkLabel(panel,
                     text=t("rend_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 8), anchor="w")
        ctk.CTkButton(panel, text=t("rend_btn_generar"),
                      command=self._accion_reporte_rendimiento, width=240).pack(anchor="w", padx=20, pady=(0, 20))

        sep_icono_bandeja = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep_icono_bandeja.pack(fill="x", padx=20, pady=10)

        fila_icono_bandeja = ctk.CTkFrame(panel, fg_color="transparent")
        fila_icono_bandeja.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_icono_bandeja, text=t("ajustes_icono_bandeja_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        opciones_icono = {t("ajustes_icono_bandeja_nada"): None, t("ajustes_icono_bandeja_cpu"): "cpu",
                           t("ajustes_icono_bandeja_ram"): "ram"}
        valor_guardado = self.prefs.get("icono_bandeja_metrica")
        texto_inicial = next((k for k, v in opciones_icono.items() if v == valor_guardado),
                              t("ajustes_icono_bandeja_nada"))
        self.combo_icono_bandeja = ctk.CTkOptionMenu(
            fila_icono_bandeja, values=list(opciones_icono.keys()), width=170,
            command=lambda seleccion: self._guardar_icono_bandeja(opciones_icono[seleccion]))
        self.combo_icono_bandeja.set(texto_inicial)
        self.combo_icono_bandeja.pack(side="right")
        ctk.CTkLabel(panel, text=t("ajustes_icono_bandeja_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep4 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep4.pack(fill="x", padx=20, pady=10)

        fila_bateria = ctk.CTkFrame(panel, fg_color="transparent")
        fila_bateria.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_bateria, text=t("ajustes_bateria_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.switch_bateria = ctk.CTkSwitch(fila_bateria, text="", command=self._toggle_ahorro_bateria)
        self.switch_bateria.pack(side="right")
        self.combo_umbral_bateria = ctk.CTkOptionMenu(
            fila_bateria, values=["10%", "15%", "20%", "25%", "30%"], width=80,
            command=lambda v: self._guardar_umbral_bateria(int(v.replace("%", ""))))
        self.combo_umbral_bateria.set(f'{self.prefs.get("bateria_umbral_ahorro", 20)}%')
        self.combo_umbral_bateria.pack(side="right", padx=(0, 12))
        if self.prefs.get("bateria_ahorro_automatico"):
            self.switch_bateria.select()
        ctk.CTkLabel(panel, text=t("ajustes_bateria_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep5 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep5.pack(fill="x", padx=20, pady=10)

        # ---- Métricas del widget flotante ----
        ctk.CTkLabel(panel, text=t("ajustes_widget_metricas_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        metricas_guardadas = self.prefs.get("widget_metricas") or ["cpu", "ram", "red", "gpu"]
        self.check_widget_metricas = {}
        fila_checks = ctk.CTkFrame(panel, fg_color="transparent")
        fila_checks.pack(fill="x", padx=20, pady=(0, 4))
        for clave, etiqueta in [("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU"),
                                 ("red", t("ajustes_widget_metrica_red"))]:
            var = tk.BooleanVar(value=clave in metricas_guardadas)
            ctk.CTkCheckBox(fila_checks, text=etiqueta, variable=var,
                            command=self._guardar_widget_metricas).pack(side="left", padx=(0, 16))
            self.check_widget_metricas[clave] = var
        ctk.CTkLabel(panel, text=t("ajustes_widget_metricas_desc"),
                     font=ctk.CTkFont(size=11), text_color="gray60", wraplength=800, justify="left").pack(
            padx=20, pady=(0, 20), anchor="w")

        sep6 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep6.pack(fill="x", padx=20, pady=10)

        # ---- Exportar / importar / restablecer configuración ----
        ctk.CTkLabel(panel, text=t("ajustes_config_titulo"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 4))
        fila_config = ctk.CTkFrame(panel, fg_color="transparent")
        fila_config.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(fila_config, text=t("ajustes_exportar"), width=110,
                      command=self._accion_exportar_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila_config, text=t("ajustes_importar"), width=110,
                      command=self._accion_importar_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila_config, text=t("ajustes_restablecer"), fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=self._accion_restablecer_config).pack(side="left")
        self.lbl_resultado_config = ctk.CTkLabel(panel, text="", font=ctk.CTkFont(size=11),
                                                   text_color="gray60", wraplength=800, justify="left")
        self.lbl_resultado_config.pack(padx=20, pady=(0, 20), anchor="w")

        sep7 = ctk.CTkFrame(panel, height=1, fg_color="#2a2d36")
        sep7.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(panel, text=t("ajustes_historial_nota"),
                     font=ctk.CTkFont(size=12), text_color="gray60", wraplength=700, justify="left").pack(
            padx=20, pady=(10, 4), anchor="w")

    def _guardar_widget_metricas(self):
        seleccion = [clave for clave, var in self.check_widget_metricas.items() if var.get()]
        self.prefs["widget_metricas"] = seleccion
        prefs.guardar({"widget_metricas": seleccion})

    def _accion_exportar_config(self):
        from tkinter import filedialog
        destino = filedialog.asksaveasfilename(
            title=t("ajustes_exportar_dialogo_titulo"), defaultextension=".json",
            filetypes=[("JSON", "*.json")], initialfile="techclean_config.json")
        if not destino:
            return
        try:
            with open(destino, "w", encoding="utf-8") as f:
                json.dump(self.prefs, f, ensure_ascii=False, indent=2)
            self.lbl_resultado_config.configure(text=t("ajustes_exportar_exito", destino=destino))
            self._log_dev(t("ajustes_log_exportar"), "N/A",
                          t("ajustes_exportar_guardada", destino=destino),
                          seccion=t("seccion_ajustes"), exito=True)
        except Exception as e:
            self.lbl_resultado_config.configure(text=t("ajustes_exportar_error", error=e))

    def _accion_importar_config(self):
        from tkinter import filedialog
        origen = filedialog.askopenfilename(title=t("ajustes_importar_dialogo_titulo"),
                                             filetypes=[("JSON", "*.json")])
        if not origen:
            return
        try:
            with open(origen, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict):
                raise ValueError(t("ajustes_importar_formato_invalido"))
            prefs.guardar(datos)
            self.prefs = prefs.cargar()
            self.lbl_resultado_config.configure(text=t("ajustes_importar_exito"))
            self._log_dev(t("ajustes_log_importar"), "N/A",
                          t("ajustes_importar_desde", origen=origen),
                          seccion=t("seccion_ajustes"), exito=True)
        except Exception as e:
            self.lbl_resultado_config.configure(text=t("ajustes_importar_error", error=e))

    def _accion_restablecer_config(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar")
        dialogo.geometry("420x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("ajustes_restablecer_confirmar"),
                     font=ctk.CTkFont(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            prefs.restablecer()
            self.prefs = prefs.cargar()
            self.lbl_resultado_config.configure(text=t("ajustes_restablecer_exito"))
            self._log_dev(t("ajustes_log_restablecer"), "N/A",
                          t("ajustes_restablecida"), seccion=t("seccion_ajustes"), exito=True)

        ctk.CTkButton(fila, text=t("ajustes_cancelar"), fg_color="gray40", command=dialogo.destroy).pack(
            side="left", padx=8)
        ctk.CTkButton(fila, text=t("ajustes_restablecer_boton"), fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=confirmar).pack(side="left", padx=8)

    def _toggle_ahorro_bateria(self):
        activo = bool(self.switch_bateria.get())
        self.prefs["bateria_ahorro_automatico"] = activo
        prefs.guardar({"bateria_ahorro_automatico": activo})

    def _guardar_umbral_bateria(self, valor):
        self.prefs["bateria_umbral_ahorro"] = valor
        prefs.guardar({"bateria_umbral_ahorro": valor})

    def _chequear_actualizacion_app(self):
        """Revisa como máximo 1 vez al día (para no gastar ni molestar) si
        hay una versión nueva publicada. Silencioso si no hay internet o
        el desarrollador todavía no configuró un repositorio — no es un
        error, simplemente no hay nada que avisar todavía."""
        ahora = time.time()
        ultima = self.prefs.get("ultima_revision_actualizacion", 0)
        if ahora - ultima < 86400:
            return

        def worker():
            resultado = opt.buscar_actualizacion_app(APP_VERSION)
            self.prefs["ultima_revision_actualizacion"] = ahora
            prefs.guardar({"ultima_revision_actualizacion": ahora})
            if resultado["hay_nueva"]:
                self.after(0, lambda: self._mostrar_aviso_actualizacion(resultado))
        threading.Thread(target=worker, daemon=True).start()

    def _accion_abrir_donacion(self):
        # Antes esto comparaba el segundo valor de retorno contra el texto
        # exacto "URL_DONACION vacía" para detectar que no hay link. Ese
        # centinela por string se rompe en silencio si alguien reescribe el
        # mensaje en optimizer.py: dejaría de salir el aviso y en su lugar
        # se registraría un fallo. Se consulta la constante directamente.
        if not opt.URL_DONACION:
            self._mostrar_popup_info(t("ajustes_donar_no_configurado_titulo"),
                                     t("ajustes_donar_no_configurado_msg"))
            return

        # webbrowser.open() lanza un proceso del sistema: si el navegador
        # está frío puede tardar y congelar la ventana. Va en un hilo, como
        # el resto de llamadas que salen al sistema operativo.
        def worker():
            exito, comando = opt.abrir_pagina_donacion()
            self._log_dev(t("ajustes_donar_log_accion"), comando,
                          t("ajustes_donar_log_ok") if exito else t("ajustes_donar_log_error"),
                          seccion=t("seccion_ajustes"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_buscar_actualizacion_manual(self):
        self.lbl_resultado_actualizacion.configure(text=t("ajustes_buscando"))

        def worker():
            resultado = opt.buscar_actualizacion_app(APP_VERSION)
            self.prefs["ultima_revision_actualizacion"] = time.time()
            prefs.guardar({"ultima_revision_actualizacion": self.prefs["ultima_revision_actualizacion"]})
            if resultado["hay_nueva"]:
                texto = t("ajustes_hay_version_nueva", version=resultado["version"], actual=APP_VERSION)
            elif resultado["version"]:
                texto = t("ajustes_version_al_dia", actual=APP_VERSION)
            else:
                texto = t("ajustes_no_se_pudo_consultar")
            if hasattr(self, "lbl_resultado_actualizacion") and self.lbl_resultado_actualizacion.winfo_exists():
                self.after(0, lambda: self.lbl_resultado_actualizacion.configure(text=texto))
            if resultado["hay_nueva"]:
                self.after(0, lambda: self._mostrar_aviso_actualizacion(resultado))
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_aviso_actualizacion(self, resultado):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("upd_titulo_ventana"))
        dialogo.geometry("420x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("upd_disponible", version=resultado["version"]),
                     font=ctk.CTkFont(size=15, weight="bold"), wraplength=380, justify="left").pack(
            padx=20, pady=(20, 6))
        ctk.CTkLabel(dialogo, text=t("upd_instalada", version=APP_VERSION),
                     font=ctk.CTkFont(size=12), text_color="gray60").pack(padx=20, anchor="w")
        if resultado["notas"]:
            caja = ctk.CTkTextbox(dialogo, height=80, font=ctk.CTkFont(size=11))
            caja.pack(fill="x", padx=20, pady=10)
            caja.insert("1.0", resultado["notas"])
            caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(side="bottom", pady=16)
        ctk.CTkButton(fila, text=t("upd_ahora_no"), fg_color="gray40",
                      command=dialogo.destroy).pack(side="left", padx=6)
        ctk.CTkButton(fila, text=t("upd_descargar"),
                      command=lambda u=resultado["url"]: threading.Thread(
                          target=lambda: webbrowser.open(u), daemon=True).start()).pack(side="left", padx=6)

    def _preguntar_idioma_primera_vez(self):
        """
        Se muestra SOLO la primera vez que se abre la app, nunca más — se
        marca idioma_preguntado=True sin importar qué elijas. Bilingüe a
        propósito: en este punto todavía no sabemos qué idioma habla quien
        la está abriendo, así que no se puede usar t() todavía (dependería
        de un idioma que aún no elegimos). Bloquea el resto de __init__
        hasta que se elija — así el menú lateral y el resto de la interfaz
        se construyen ya en el idioma correcto desde el primer cuadro, en
        vez de dibujarse una vez y tener que reconstruirse.
        """
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Idioma / Language")
        dialogo.geometry("420x260")
        dialogo.protocol("WM_DELETE_WINDOW", lambda: None)  # hay que elegir uno, no se puede cerrar sin más
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text="🌐", font=ctk.CTkFont(size=36)).pack(pady=(28, 6))
        ctk.CTkLabel(dialogo, text="Selecciona tu idioma\nSelect your language",
                     font=ctk.CTkFont(size=15, weight="bold"), justify="center").pack(pady=(0, 8))
        ctk.CTkLabel(dialogo, text="Se puede cambiar después en Ajustes.\nYou can change this later in Settings.",
                     font=ctk.CTkFont(size=11), text_color="gray60", justify="center").pack(pady=(0, 20))

        def elegir(codigo):
            self.prefs["idioma"] = codigo
            self.prefs["idioma_preguntado"] = True
            prefs.guardar({"idioma": codigo, "idioma_preguntado": True})
            idiomas.establecer_idioma(codigo)
            dialogo.destroy()

        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)
        ctk.CTkButton(fila, text="Español", width=140, command=lambda: elegir("es")).pack(side="left", padx=8)
        ctk.CTkButton(fila, text="English", width=140, command=lambda: elegir("en")).pack(side="left", padx=8)

        self.wait_window(dialogo)

    def _cambiar_idioma(self, valor_mostrado):
        codigo = next((c for c, nombre in idiomas.IDIOMAS_DISPONIBLES.items() if nombre == valor_mostrado), "es")
        self.prefs["idioma"] = codigo
        prefs.guardar({"idioma": codigo})
        self._log_dev(t("ajustes_log_idioma"), "N/A",
                      t("ajustes_idioma_guardado", idioma=valor_mostrado),
                      seccion=t("seccion_ajustes"), exito=True)

        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("ajustes_reiniciar_titulo"))
        dialogo.geometry("420x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("ajustes_idioma_reiniciar_aviso"),
                     font=ctk.CTkFont(size=13), wraplength=380, justify="center").pack(padx=20, pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)
        ctk.CTkButton(fila, text=t("ajustes_mas_tarde"), fg_color="gray40",
                      command=dialogo.destroy).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("ajustes_cerrar_ahora"), fg_color=COLOR_CRIT, hover_color="#c0392b",
                      command=self._salir_definitivo).pack(side="left", padx=8)

    def _aplicar_preferencia_animaciones(self):
        """Modo Ligero apaga la animacion de las barras, en la ventana
        principal y en el widget flotante, sin reiniciar la app."""
        global ANIMAR_BARRAS
        ANIMAR_BARRAS = not self.prefs.get("modo_ligero")
        widget_mod.ANIMAR_BARRAS = ANIMAR_BARRAS

    def _toggle_modo_ligero(self):
        activo = bool(self.switch_modo_ligero.get())
        self.prefs["modo_ligero"] = activo
        prefs.guardar({"modo_ligero": activo})
        self._aplicar_preferencia_animaciones()
        self._log_dev(t("ajustes_log_modo_ligero_on") if activo else t("ajustes_log_modo_ligero_off"),
                      "N/A", t("ajustes_modo_ligero_aplica"),
                      seccion=t("seccion_ajustes"), exito=True)

    def _guardar_umbral_ram(self, valor):
        self.prefs["umbral_ram_auto"] = valor
        prefs.guardar({"umbral_ram_auto": valor})
        # Se aplica de inmediato al autopilot que ya está corriendo, sin
        # tener que reiniciar la app — es un atributo simple, no hace
        # falta recrear el objeto entero.
        self.autopilot.umbral_ram = valor
        self._log_dev(t("ajustes_log_umbral_ram"), "N/A",
                      t("ajustes_umbral_ram_msg", valor=valor),
                      seccion=t("seccion_ajustes"), exito=True)

    def _guardar_umbral_salud(self, tipo, valor):
        clave = "umbral_salud_ram" if tipo == "ram" else "umbral_salud_disco"
        self.prefs[clave] = valor
        prefs.guardar({clave: valor})
        # No hace falta tocar nada en vivo: _calcular_salud_sistema lee
        # self.prefs cada vez que corre, así que el próximo refresco de
        # Inicio ya usa el valor nuevo solo.
        self._log_dev(t("ajustes_log_umbral_salud", tipo=tipo), "N/A",
                      t("ajustes_umbral_salud_msg", valor=valor),
                      seccion=t("seccion_ajustes"), exito=True)

    def _accion_probar_error(self):
        """Provoca un error A PROPÓSITO (dividir por cero) para que se vea
        el aviso completo funcionando, sin tener que esperar a que algo se
        rompa de verdad. El propio error queda registrado como cualquier
        otro, marcado igual en el Historial."""
        1 / 0  # noqa

    def _accion_probar_error_segundo_plano(self):
        """Igual que _accion_probar_error, pero el error se provoca DENTRO
        de un hilo de fondo — el mismo tipo de error que provocaría, por
        ejemplo, que Componentes se quede en 'Leyendo...' para siempre.
        Ese camino usa un mecanismo distinto (threading.excepthook, no
        report_callback_exception), así que es una prueba genuinamente
        distinta, no la misma repetida."""
        def worker():
            raise RuntimeError(t("ajustes_error_prueba_hilo"))
        threading.Thread(target=worker, daemon=True).start()

    def _accion_diagnostico_completo(self):
        """
        Recorre unas 35 funciones de SOLO LECTURA de la app, una por una,
        atrapando cualquier error por separado — a diferencia de los
        botones de "probar aviso de error" (que fuerzan un error ya
        conocido a propósito), esto encuentra errores REALES que ya
        existan, sin tener que navegar manualmente pantalla por pantalla
        esperando toparse con uno. Así se encontró después el bug de
        _cim(): esto lo habría mostrado de inmediato.

        Deliberadamente NO incluye ninguna función que actúe sobre el
        sistema (reparar, terminar procesos, apagar, bloquear firewall,
        etc.) ni ninguna que abra ventanas/reproduzca sonido — solo
        lectura, nada que pueda cambiar algo o sorprenderte mientras corre
        en segundo plano.
        """
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("diag_titulo_ventana"))
        dialogo.geometry("640x480")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("diag_titulo"),
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 4))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("diag_ejecutando"),
                                    font=ctk.CTkFont(size=11), text_color="gray60", wraplength=560,
                                    justify="center")
        lbl_estado.pack(padx=20, pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=ctk.CTkFont(family="Consolas", size=10))
        caja.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        caja.insert("1.0", t("diag_iniciando") + "\n")
        caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=(0, 16))
        btn_copiar = ctk.CTkButton(fila, text=t("comun_copiar_todo"), state="disabled")
        btn_copiar.pack(side="left", padx=6)
        ctk.CTkButton(fila, text=t("comun_cerrar"), fg_color="gray40",
                      command=dialogo.destroy).pack(side="left", padx=6)

        def _actualizar_caja(texto):
            if not dialogo.winfo_exists():
                return
            caja.configure(state="normal")
            caja.delete("1.0", "end")
            caja.insert("1.0", texto)
            caja.configure(state="disabled")
            caja.see("end")

        def _finalizar(texto_final, exitos, fallos):
            if not dialogo.winfo_exists():
                return
            _actualizar_caja(texto_final)
            lbl_estado.configure(
                text=t("diag_listo", exitos=exitos, total=exitos + fallos, fallos=fallos),
                text_color=(COLOR_OK if fallos == 0 else COLOR_CRIT))
            btn_copiar.configure(state="normal", command=lambda: self._copiar_al_portapapeles(texto_final))

        def worker():
            pruebas = [
                (t("diagp_cpu_detalle"), lambda: sysmon.get_cpu_details()),
                (t("diagp_gpu"), lambda: sysmon.get_gpu_info()),
                (t("diagp_ram_modulos"), lambda: sysmon.get_ram_sticks()),
                (t("diagp_memoria_virtual"), lambda: sysmon.get_memoria_virtual()),
                (t("diagp_particiones"), lambda: sysmon.get_disk_partitions()),
                (t("diagp_vel_disco"), lambda: sysmon.get_disk_io_speed()),
                (t("diagp_vel_red"), lambda: sysmon.get_network_speed()),
                (t("diagp_bateria"), lambda: sysmon.get_battery_info()),
                (t("diagp_uptime"), lambda: sysmon.get_uptime_seconds()),
                (t("diagp_procesos_conteo"), lambda: sysmon.get_process_count()),
                (t("diagp_info_sistema"), lambda: sysmon.get_system_info()),
                (t("diagp_equipo_modesto"), lambda: sysmon.es_equipo_modesto()),
                (t("diagp_drivers"), lambda: sysmon.listar_drivers()),
                (t("diagp_admin"), lambda: opt.is_admin()),
                (t("diagp_limpieza_prog"), lambda: opt.limpieza_programada_activa()),
                (t("diagp_espacio_recuperable"), lambda: opt.estimate_reclaimable_space()),
                (t("diagp_fabricante"), lambda: opt.obtener_fabricante_soporte()),
                (t("diagp_plan_energia"), lambda: opt.get_active_power_plan_name()),
                (t("diagp_carpetas_pesadas"), lambda: opt.listar_carpetas_pesadas("C:\\")),
                (t("diagp_archivos_grandes"), lambda: opt.listar_archivos_grandes("C:\\")),
                (t("diagp_instaladores"), lambda: opt.listar_instaladores_viejos()),
                (t("diagp_cache_apps"), lambda: opt.listar_cache_apps_comunes()),
                (t("diagp_defender"), lambda: opt.obtener_estado_defender()),
                (t("diagp_bitlocker"), lambda: opt.obtener_estado_bitlocker()),
                (t("diagp_hello"), lambda: opt.obtener_estado_windows_hello()),
                (t("diagp_permisos_camara"), lambda: opt.listar_permisos_privacidad("webcam")),
                (t("diagp_firewall"), lambda: opt.listar_reglas_firewall_bloqueadas()),
                (t("diagp_adaptadores"), lambda: opt.listar_adaptadores_red()),
                (t("diagp_programas"), lambda: opt.listar_programas_instalados()),
                (t("diagp_servicios"), lambda: opt.listar_servicios_windows()),
                (t("diagp_winget"), lambda: opt.winget_disponible()),
                (t("diagp_tareas"), lambda: opt.listar_tareas_programadas_terceros()),
                (t("diagp_juegos"), lambda: opt.listar_juegos_instalados()),
                (t("diagp_audio"), lambda: opt.listar_dispositivos_audio()),
                (t("diagp_proc_ram"), lambda: opt.listar_procesos_por_ram()),
                (t("diagp_proc_cpu"), lambda: opt.listar_procesos_por_cpu()),
                (t("diagp_indexacion"), lambda: opt.obtener_estado_indexacion()),
                (t("diagp_inicio_registro"), lambda: opt.is_startup_enabled()),
                (t("diagp_apps_inicio"), lambda: opt.listar_apps_inicio()),
                (t("diagp_navegadores"), lambda: priv.detect_installed_browsers()),
            ]

            lineas = [
                t("diag_encabezado"),
                t("diag_fecha", fecha=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                t("diag_version", version=APP_VERSION, edicion=EDICION),
                "",
            ]
            exitos, fallos = 0, 0
            for etiqueta, fn in pruebas:
                inicio = time.time()
                try:
                    resultado = fn()
                    duracion = time.time() - inicio
                    if isinstance(resultado, list):
                        detalle = t("diag_ok_elementos", cantidad=len(resultado))
                    elif resultado is None:
                        detalle = t("diag_ok_sin_dato")
                    else:
                        detalle = t("diag_ok")
                    lineas.append(t("diag_linea_ok", etiqueta=etiqueta, detalle=detalle,
                                    duracion=f"{duracion:.2f}"))
                    exitos += 1
                except Exception as e:
                    duracion = time.time() - inicio
                    lineas.append(t("diag_linea_error", etiqueta=etiqueta,
                                    tipo=type(e).__name__, error=e,
                                    duracion=f"{duracion:.2f}"))
                    fallos += 1
                self.after(0, lambda texto="\n".join(lineas): _actualizar_caja(texto))

            lineas += ["", t("diag_resumen", exitos=exitos, total=exitos + fallos, fallos=fallos)]
            texto_final = "\n".join(lineas)

            try:
                ruta = os.path.join(prefs.carpeta_datos(), "diagnostico.txt")
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(texto_final)
            except Exception:
                pass

            self._log_dev(t("diag_titulo_ventana"), "N/A",
                          t("diag_log_resultado", exitos=exitos, fallos=fallos),
                          seccion=t("seccion_sistema"), exito=(fallos == 0))
            self.after(0, lambda: _finalizar(texto_final, exitos, fallos))

        threading.Thread(target=worker, daemon=True).start()

    def _accion_reporte_rendimiento(self):
        """
        Junta en un solo texto todo lo relacionado a qué tan rápido va el
        equipo — pensado para copiar y compartir, no para diagnosticar
        errores (eso es Diagnóstico completo, que es distinto a
        propósito: ese busca fallas de código, este junta datos de
        rendimiento).
        """
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("rend_titulo_ventana"))
        dialogo.geometry("640x480")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("rend_titulo"),
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 4))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("rend_reuniendo"), font=ctk.CTkFont(size=11),
                                    text_color="gray60")
        lbl_estado.pack(pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=ctk.CTkFont(family="Consolas", size=10))
        caja.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=(0, 16))
        btn_copiar = ctk.CTkButton(fila, text=t("comun_copiar_todo"), state="disabled")
        btn_copiar.pack(side="left", padx=6)
        ctk.CTkButton(fila, text=t("comun_cerrar"), fg_color="gray40",
                      command=dialogo.destroy).pack(side="left", padx=6)

        def worker():
            cpu = sysmon.get_cpu_details(incluir_temperatura=True)
            ram = sysmon.get_ram_info()
            ram_sticks = sysmon.get_ram_sticks()
            canal = sysmon.estimar_canal_ram(ram_sticks) if ram_sticks else None
            disco = sysmon.get_disk_info()
            gpu = sysmon.get_gpu_info()
            try:
                apps_activas = sum(1 for a in opt.listar_apps_inicio() if a["activo"])
            except Exception:
                apps_activas = None
            try:
                servicios_top = opt.listar_servicios_por_consumo(limite=5)
            except Exception:
                servicios_top = []
            try:
                arranques = sysmon.listar_historial_arranques(limite=5)
            except Exception:
                arranques = []

            lineas = [
                t("rend_encabezado"),
                t("diag_fecha", fecha=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                t("rend_version", version=APP_VERSION),
                "",
                t("rend_sec_cpu"),
                t("rend_uso_total", pct=cpu.get("porcentaje_total")),
                t("rend_nucleos", fisicos=cpu.get("nucleos_fisicos"),
                  logicos=cpu.get("nucleos_logicos")),
                t("rend_frecuencia", actual=cpu.get("frecuencia_actual_mhz"),
                  maxima=cpu.get("frecuencia_max_mhz")),
                (t("rend_temperatura", temp=cpu.get("temperatura_c"))
                 if cpu.get("temperatura_c") is not None else t("rend_temp_nd")),
                "",
                t("rend_sec_ram"),
                t("rend_uso", pct=ram.get("porcentaje"), usado=ram.get("usado_gb"),
                  total=ram.get("total_gb")),
                (t("rend_canal", modo=canal["modo"]) if canal else t("rend_canal_nd")),
                "",
                t("rend_sec_disco"),
                t("rend_uso", pct=disco.get("porcentaje"), usado=disco.get("usado_gb"),
                  total=disco.get("total_gb")),
                "",
                t("rend_sec_gpu"),
                f"{gpu.get('nombre', t('comp_nd'))}",
                "",
                t("rend_apps_inicio",
                  cantidad=apps_activas if apps_activas is not None else t("comp_nd")),
                "",
                t("rend_sec_servicios"),
            ]
            if servicios_top:
                for s in servicios_top[:5]:
                    lineas.append(t("rend_servicio", nombres=", ".join(s["servicios"][:3]),
                                    tamano=opt.format_bytes(s["bytes_ram"])))
            else:
                lineas.append(t("rend_servicios_nd"))
            lineas.append("")
            lineas.append(t("rend_sec_arranques"))
            if arranques:
                for a in arranques[:5]:
                    lineas.append(t("rend_arranque", fecha=a["fecha"],
                                    segundos=f"{a['segundos']:.0f}"))
            else:
                lineas.append(t("rend_arranques_nd"))

            texto_final = "\n".join(lineas)

            def _mostrar():
                if not dialogo.winfo_exists():
                    return
                caja.configure(state="normal")
                caja.delete("1.0", "end")
                caja.insert("1.0", texto_final)
                caja.configure(state="disabled")
                lbl_estado.configure(text="Listo.")
                btn_copiar.configure(state="normal", command=lambda: self._copiar_al_portapapeles(texto_final))
            self.after(0, _mostrar)
            self._log_dev("Reporte de rendimiento", "N/A", "Generado correctamente", seccion=t("seccion_ajustes"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    def _copiar_al_portapapeles(self, texto):
        try:
            self.clipboard_clear()
            self.clipboard_append(texto)
        except Exception:
            pass

    def _accion_abrir_carpeta_datos(self):
        try:
            os.startfile(prefs.carpeta_datos())
        except Exception as e:
            self._mostrar_popup_info(t("ajustes_no_abrir_titulo"),
                                     t("ajustes_no_abrir_carpeta", error=e))

    def _guardar_icono_bandeja(self, valor):
        self.prefs["icono_bandeja_metrica"] = valor
        prefs.guardar({"icono_bandeja_metrica": valor})
        if valor is None:
            self.tray.restaurar_icono_normal()

    def _guardar_alerta_temp(self):
        texto = self.entry_alerta_temp.get().strip()
        if not texto:
            self.prefs["alerta_temp_cpu"] = None
            prefs.guardar({"alerta_temp_cpu": None})
            self._mostrar_popup_info(t("ajustes_alerta_desactivada_titulo"), t("ajustes_alerta_desactivada_msg"))
            return
        try:
            valor = float(texto)
        except ValueError:
            self._mostrar_popup_info(t("ajustes_valor_invalido_titulo"), t("ajustes_valor_invalido_msg"))
            return
        self.prefs["alerta_temp_cpu"] = valor
        prefs.guardar({"alerta_temp_cpu": valor})
        self._mostrar_popup_info(t("ajustes_alerta_guardada_titulo"),
                                  t("ajustes_alerta_guardada_msg", valor=f"{valor:.0f}"))

    def _toggle_inicio_automatico(self):
        habilitar = bool(self.switch_inicio.get())
        exito, comando = opt.set_startup(habilitar)
        resultado = (t("ajustes_inicio_agregado") if habilitar else t("ajustes_inicio_quitado")) \
            if exito else t("ajustes_inicio_error")
        self._log_dev(t("ajustes_log_inicio_auto"), comando, resultado,
                      seccion=t("seccion_ajustes"), exito=exito)
        if not exito:
            if habilitar:
                self.switch_inicio.deselect()
            else:
                self.switch_inicio.select()

    def _click_easter_egg(self, event=None):
        ahora = time.time()
        if ahora - self._easter_last_click > 2.5:
            self._easter_clicks = 0
        self._easter_clicks += 1
        self._easter_last_click = ahora

        if self._easter_clicks >= 5:
            self._easter_clicks = 0
            self._activar_easter_egg()

    # ---------------- Modo Desarrollador (oculto) ----------------
    def _click_dev_unlock(self, event=None):
        ahora = time.time()
        if ahora - self._dev_last_click > 2.5:
            self._dev_clicks = 0
        self._dev_clicks += 1
        self._dev_last_click = ahora

        if self._dev_clicks >= 7:
            self._dev_clicks = 0
            self._toggle_modo_desarrollador()

    def _toggle_modo_desarrollador(self):
        nuevo_estado = not self.modo_desarrollador.get()
        self.modo_desarrollador.set(nuevo_estado)
        self._construir_sidebar()

        if nuevo_estado:
            titulo, mensaje = t("oculto_desbloqueado_titulo"), t("oculto_desbloqueado_msg")
        else:
            titulo, mensaje = t("oculto_ocultado_titulo"), t("oculto_ocultado_msg")
            self.mostrar_dashboard()
        self._mostrar_popup_info(titulo, mensaje)

    def _activar_easter_egg(self):
        def reproducir():
            if HAS_WINSOUND and os.path.exists(HONK_PATH):
                try:
                    winsound.PlaySound(HONK_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
                except Exception:
                    pass
        threading.Thread(target=reproducir, daemon=True).start()

        dialogo = ctk.CTkToplevel(self)
        dialogo.title("¿?")
        dialogo.geometry("360x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text="🪿 HONK!", font=ctk.CTkFont(size=32, weight="bold")).pack(pady=(24, 6))
        ctk.CTkLabel(dialogo, text=t("huevo_texto"),
                     font=ctk.CTkFont(size=12), justify="center").pack(pady=6)
        ctk.CTkButton(dialogo, text=t("huevo_ok"), command=dialogo.destroy).pack(pady=10)


if __name__ == "__main__":
    if "--limpieza-programada" in sys.argv:
        # Tarea programada (Task Scheduler): limpieza silenciosa, sin
        # abrir ninguna ventana ni icono de bandeja — solo hace el trabajo
        # y termina. Así no interrumpe al usuario si está usando el equipo.
        opt.trim_process_memory()
        opt.clear_temp_files()
        sys.exit(0)

    app = TechCleanApp()
    if "--minimizado" in sys.argv:
        app.after(50, app._minimizar_a_bandeja)
    app.mainloop()
