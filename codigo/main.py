"""
main.py
TechClean — Panel de Optimización y Diagnóstico de Sistema
Aplicación de escritorio para Windows con monitoreo real de hardware,
optimización de RAM/disco, limpieza de privacidad, consola de desarrollador,
reporte transparente de sesión, widget flotante y modo automático en
segundo plano (bandeja del sistema).

Ejecutar:  python main.py
Requiere:  pip install -r requirements.txt
"""

import os
import sys
import subprocess
import time
import json
import math
import difflib
import queue
import socket
import getpass
import platform
import shutil
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
import deshacer as desh
import tecnico as tec
import disco
import informe
import seguridad as seg
import widget as widget_mod
import tray as tray_mod
import temas
from temas import T
import iconos
import atajos
import autopilot as autopilot_mod
import preferences as prefs
import rutas

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Los colores, la letra y el modo claro/oscuro los pone temas.py (ver
# TechCleanApp.__init__ y _aplicar_tema). Al importarlo se activa el de
# fábrica, por si algo crea widgets antes de que se lean las preferencias.


def _sin_redibujo_forzado(clase):
    """BUG de rendimiento corregido (de customtkinter 6.0, no nuestro):
    CTkScrollbar y CTkOptionMenu llaman a update_idletasks() al final de
    CADA _draw. Eso recalcula la disposición de la ventana ENTERA, y al
    recalcularla las barras se vuelven a mover y a dibujar: una cascada.
    Medido: cerca del 30 % del tiempo de abrir una pantalla, y la mitad de
    Ajustes. Tk redibuja igual en cuanto el hilo queda libre, así que
    forzarlo no aporta nada que se vea. Se anula solo en el canvas de esos
    dos controles, no en el resto de la app."""
    original = clase._draw

    def _draw(self, *args, **kwargs):
        canvas = getattr(self, "_canvas", None)
        if canvas is not None and "update_idletasks" not in canvas.__dict__:
            canvas.update_idletasks = lambda: None
        return original(self, *args, **kwargs)
    clase._draw = _draw


for _clase in (ctk.CTkScrollbar, ctk.CTkOptionMenu):
    _sin_redibujo_forzado(_clase)

# Colores de estado y de panel. Desde la 1.8.0 los pone el tema activo
# (_sincronizar_colores): son variables del módulo, y las funciones las leen
# al ejecutarse, así que cambiar de tema basta para que lo nuevo salga bien.
COLOR_OK = T.ok
COLOR_WARN = T.aviso
COLOR_CRIT = T.critico
COLOR_BG_PANEL = T.panel
COLOR_ACCENT = T.acento
COLOR_DONAR = "#ff5e5b"   # calido, para que la tarjeta de apoyo no se pierda entre paneles grises


def _sincronizar_colores():
    """Copia los colores del tema activo a las variables COLOR_* de arriba."""
    global COLOR_OK, COLOR_WARN, COLOR_CRIT, COLOR_BG_PANEL, COLOR_ACCENT
    COLOR_OK, COLOR_WARN, COLOR_CRIT = T.ok, T.aviso, T.critico
    COLOR_BG_PANEL, COLOR_ACCENT = T.panel, T.acento

DEV_NAME = "Edwin Javier Cortez Cardoza"
DEV_ALIAS = "Hades"
APP_VERSION = "1.8.0"

# ---------------------------------------------------------------------------
# EDICIÓN: "cliente" (por defecto) oculta todo lo administrativo/técnico y
# en su lugar ofrece un panel de comandos oculto y amigable. "admin" muestra
# la Consola Dev, comandos técnicos exactos y el lenguaje de administrador
# de forma normal, sin ocultar nada. Ambas ediciones comparten el mismo
# código — main.py es la edición cliente; main_admin.py es un punto de
# entrada aparte que activa la edición admin antes de arrancar la app.
# ---------------------------------------------------------------------------
EDICION = "cliente"

# Idioma de ESTA build (ver build_config.py). La edicion cliente no lleva
# selector: se publican dos ejecutables, uno por idioma. El try/except es a
# proposito — si por lo que sea el archivo no esta, la app arranca en espanol
# en vez de negarse a abrir.
try:
    from build_config import IDIOMA as IDIOMA_BUILD
except Exception:
    IDIOMA_BUILD = "es"

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
    "/estado": "cmd_estado",
    "/version": "cmd_version",
    "/limpiar": "cmd_limpiar",
    "/guardar": "cmd_guardar",
    "/salir": "cmd_salir",
    "/help": "cmd_help",
    # 1.6.0
    "/ramprofunda": "cmd_ramprofunda",
    "/autoram": "cmd_autoram",
    "/fondo": "cmd_fondo",
    "/fugas": "cmd_fugas",
    "/procesos": "cmd_procesos",
    "/discos": "cmd_discos",
    "/bateria": "cmd_bateria",
    "/pantallazos": "cmd_pantallazos",
    "/unidades": "cmd_unidades",
    "/medirdns": "cmd_medirdns",
    "/plan": "cmd_plan",
    "/red": "cmd_red",
    "/tecnico": "cmd_tecnico",
    # 1.7.0
    "/wifi": "cmd_wifi",
    "/disco": "cmd_disco",
    "/extensiones": "cmd_extensiones",
    "/accesos": "cmd_accesos",
    "/encendido": "cmd_encendido",
    "/buscar": "cmd_buscar",
}

# Nombre y descripción de cada tema (claves de idiomas.py). Literal a
# propósito: así verificar_idiomas ve que cada clave se usa.
NOMBRES_TEMA = {
    "original": ("tema_original", "tema_original_desc"),
    "pulido": ("tema_pulido", "tema_pulido_desc"),
    "telemetria": ("tema_telemetria", "tema_telemetria_desc"),
    "claro": ("tema_claro", "tema_claro_desc"),
    "oled": ("tema_oled", "tema_oled_desc"),
    "bosque": ("tema_bosque", "tema_bosque_desc"),
    "retro": ("tema_retro", "tema_retro_desc"),
    "sakura": ("tema_sakura", "tema_sakura_desc"),
    "alto_contraste": ("tema_alto_contraste", "tema_alto_contraste_desc"),
}

# Lo que enseña la ventana de novedades al actualizar (claves de idiomas.py).
NOVEDADES = ("nov_180_temas", "nov_180_rediseno", "nov_180_informe", "nov_180_disco", "nov_180_fallos",
             "nov_180_componentes_salud", "nov_180_inicio_windows", "nov_180_proteccion", "nov_180_privacidad",
             "nov_180_gaming", "nov_180_energia", "nov_180_drivers", "nov_180_segundo_plano",
             "nov_180_rapida", "nov_180_privacidad_app", "nov_180_cerrados", "nov_180_ligera", "nov_180_arreglos",
             "nov_180_textos", "nov_180_componentes")


def _sin_emoji(texto):
    """Quita el emoji y los espacios del principio de un texto ("📊  Inicio"
    -> "Inicio"). Los textos de idiomas.py llevan emoji delante para las
    pantallas que aún no se rediseñaron; donde ya hay un icono de línea, el
    emoji sobra. Se quitan también los del final (" ✅")."""
    import re
    texto = re.sub(r"^[^\w¿¡(\"'«]+", "", str(texto))
    return re.sub(r"[\s☀-➿\U0001f000-\U0001faff️]+$", "", texto)


def _sin_acentos(texto):
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def buscar_en_paleta(entradas, consulta):
    """Filtra y ordena las entradas del buscador de funciones (Ctrl+K).

    entradas: [(título, dónde, palabras extra, acción)]. Cada palabra de la
    consulta tiene que aparecer en el título, en el dónde o en las palabras
    extra, sin mirar mayúsculas ni tildes ("dns" encuentra "DNS", "energia"
    encuentra "Energía"). Primero lo que EMPIEZA por lo escrito, luego lo
    que lo contiene en el título, y al final lo que solo coincide en los
    sinónimos. Si no hay nada, se prueba con faltas de ortografía
    ("memroia")."""
    palabras = _sin_acentos(consulta).split()
    if not palabras:
        return list(entradas)
    puntuadas = []
    for orden, e in enumerate(entradas):
        titulo = _sin_acentos(e[0])
        resto = _sin_acentos(f"{e[1]} {e[2]}")
        if all(p in titulo or p in resto for p in palabras):
            if titulo.startswith(palabras[0]):
                nota = 0
            elif all(p in titulo for p in palabras):
                nota = 1
            else:
                nota = 2
            puntuadas.append((nota, orden, e))
    if not puntuadas:
        consulta_limpia = " ".join(palabras)
        for orden, e in enumerate(entradas):
            candidatas = _sin_acentos(f"{e[0]} {e[2]}").split()
            if difflib.get_close_matches(consulta_limpia, candidatas, n=1, cutoff=0.75):
                puntuadas.append((3, orden, e))
    puntuadas.sort(key=lambda x: (x[0], x[1]))
    return [e for _, _, e in puntuadas]


_BANDAS_WIFI = {"2.4": "wifi_banda_24", "5": "wifi_banda_5", "6": "wifi_banda_6"}
_VEREDICTOS_WIFI = {"bien": "wifi_v_bien", "regular": "wifi_v_regular", "mal": "wifi_v_mal"}


def texto_wifi(datos):
    """(texto, nivel) para enseñar lo que devuelve sysmon.leer_wifi().
    nivel: "bien" | "regular" | "mal" | "info" (sin Wi-Fi o sin conexión)."""
    if datos is None:
        return t("wifi_sin_adaptador"), "info"
    conectado = next((w for w in datos if w.get("conectado")), None)
    if conectado is None:
        return t("wifi_sin_conexion"), "info"
    w = conectado
    nd = t("comp_nd")
    lineas = [
        t("wifi_red", ssid=w.get("ssid") or t("wifi_ssid_oculto"), adaptador=w.get("adaptador") or nd),
        t("wifi_senal", senal=w["senal"] if w.get("senal") is not None else nd,
          rssi=w["rssi"] if w.get("rssi") is not None else nd),
        t("wifi_banda_canal", banda=t(_BANDAS_WIFI[w["banda"]]) if w.get("banda") in _BANDAS_WIFI else nd,
          canal=w.get("canal") or nd),
        t("wifi_estandar", estandar=w.get("estandar") or nd, velocidad=w.get("velocidad_mbps") or nd),
    ]
    if w.get("redes_mismo_canal") is not None:
        lineas.append(t("wifi_vecinas", mismo=w["redes_mismo_canal"], banda=w.get("redes_misma_banda") or 0))
    if w.get("rssi") is None and w.get("senal") is None:
        # Sin la señal no hay veredicto honesto: decir "está bien" sería inventarlo.
        return "\n".join(lineas + ["", t("wifi_sin_datos")]), "info"
    nivel, motivos = sysmon.veredicto_wifi(w)
    lineas += ["", t(_VEREDICTOS_WIFI[nivel])]
    for m in motivos:
        lineas.append("• " + t(m, redes=w.get("redes_mismo_canal") or 0, velocidad=w.get("velocidad_mbps") or 0,
                               rssi=w.get("rssi") if w.get("rssi") is not None else nd))
    return "\n".join(lineas), nivel


_CLASES_DISCO = {"hdd": "comp_disco_clase_hdd", "ssd": "comp_disco_clase_ssd", "nvme": "comp_disco_clase_nvme"}


def texto_disco(r, tipo_windows=None):
    """Resultado de opt.prueba_velocidad_disco en palabras. tipo_windows:
    lo que Windows dice que es la unidad ("SSD"/"HDD"), si se sabe."""
    lineas = [t("comp_disco_resultado", escritura=r["escritura_mbs"], lectura=r["lectura_mbs"],
                aleatoria=r.get("aleatoria_mbs", "?")),
              t(_CLASES_DISCO.get(r.get("clase"), "comp_disco_clase_ssd"))]
    if tipo_windows == "SSD" and r.get("clase") == "hdd":
        lineas.append(t("comp_disco_ssd_lento"))
    return "\n".join(lineas)

# Las rutas de assets/ salen de rutas.py y no de dirname(__file__).
# Con el codigo en codigo/ y assets/ en la raiz, dirname(__file__) apunta a
# codigo/assets, que no existe — y la app abriria sin icono y sin sonido,
# pero SOLO desde el codigo: compilada seguiria bien porque PyInstaller
# descomprime todo junto. O sea, un fallo invisible en lo que se reparte.
BASE_DIR = rutas.CARPETA_CODIGO
HONK_PATH = rutas.recurso("honk.wav")
ICON_PATH = rutas.recurso("icono.ico")


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


def mezclar_color(color_a, color_b, proporcion):
    """Mezcla dos colores hex: proporcion=0 devuelve `color_a`, proporcion=1
    devuelve `color_b`.

    Tkinter no sabe de transparencia (un Canvas clasico no tiene canal
    alfa), asi que un degradado se finge mezclando cada tono contra el
    color de fondo real del panel. Es lo que usa la Sparkline para que el
    area bajo la linea se desvanezca hacia abajo en vez de quedar como un
    bloque plano de un solo color."""
    try:
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        f = max(0.0, min(1.0, proporcion))
        canales = []
        for i in (0, 2, 4):
            ca = int(a[i:i + 2], 16)
            cb = int(b[i:i + 2], 16)
            canales.append(int(round(ca + (cb - ca) * f)))
        return "#{:02x}{:02x}{:02x}".format(*canales)
    except Exception:
        return color_a


# Con Modo Ligero activo las animaciones se apagan: en un equipo justo de
# recursos, redibujar el arco 16 veces por cada cambio de numero es
# exactamente el tipo de gasto que ese modo existe para evitar.
ANIMAR_BARRAS = True


class _ValorAnimado:
    """Un porcentaje que NO salta de golpe: se interpola desde el valor que
    ya se estaba mostrando hasta el nuevo, con una curva que arranca rapido
    y frena al final (ease-out), asi que la barra y el numero se mueven
    juntos en vez de dar un tiron.

    La usa TarjetaMetrica (las tarjetas de Inicio; hasta la 1.7.0, el
    medidor circular Gauge, que el rediseño de la 1.8.0 sustituyó). Quien la
    usa pone self._valor_mostrado, self._anim_id y self.lbl_detalle, y
    define _dibujar(valor)."""

    DURACION_MS = 320   # lo que tarda el recorrido completo
    PASO_MS = 20        # ~16 cuadros; mas fino no se nota y cuesta mas

    def _dibujar(self, porcentaje):
        """Lo pone cada clase que usa la mezcla (TarjetaMetrica)."""
        raise NotImplementedError

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
        # Solo si cambia: reconfigurar una CTkLabel la vuelve a medir y dibujar.
        if detalle != getattr(self, "_detalle", None):
            self._detalle = detalle
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



def fuente(size=13, weight="normal", family=None):
    """Una letra de customtkinter COMPARTIDA: la misma para todos los
    textos de igual tamaño y grosor.

    Rendimiento (1.8.0): cada `ctk.CTkFont(...)` crea una fuente nueva en Tk,
    y la app creaba una por etiqueta (390 sitios): crear y dibujar una
    etiqueta costaba ~1.3 ms más que con una fuente compartida. La caché va
    en la ventana principal: las fuentes son de su intérprete de Tcl (las
    pruebas abren y cierran varias). La familia, si no se da, es la del tema
    activo, así que al cambiar de tema salen fuentes nuevas."""
    familia = family or T.familia      # la misma que el tema le da a customtkinter
    raiz = tk._default_root
    if raiz is None:
        return ctk.CTkFont(family=familia, size=size, weight=weight)
    cache = raiz.__dict__.setdefault("_fuentes_compartidas", {})
    clave = (familia, size, weight)
    letra = cache.get(clave)
    if letra is None:
        letra = cache[clave] = ctk.CTkFont(family=familia, size=size, weight=weight)
    return letra


def color_uso(porcentaje):
    """Color de una barra de uso: el acento del tema mientras va bien, y
    aviso o crítico cuando se llena."""
    if porcentaje is None or porcentaje < 60:
        return T.acento
    return T.aviso if porcentaje < 85 else T.critico


ESPERA_TEXTOS_MS = 60


def texto_fluido(etiqueta, contenedor, margen, tope=None):
    """Hace que el texto de `etiqueta` se parta al ancho REAL de `contenedor`
    y no a un número fijo: con la letra más grande (Alto contraste), el zoom
    de Windows o una ventana estrecha, un wraplength fijo dejaba el final
    del texto cortado. `margen` es lo que la caja deja a los lados, en
    unidades sin escalar; `tope`, el ancho del que no se pasa (si se da).

    Rendimiento (1.8.0): NO se ajusta en cada <Configure>. Mientras una
    pantalla se coloca, su caja pasa por anchos intermedios (en Ajustes,
    800 → 234 → 729 → 800 px) y cada cambio de wraplength obligaba a volver
    a colocar y dibujar el panel entero, tres o cuatro veces. Ahora cada
    <Configure> solo anota la caja, y el ajuste se hace UNA vez, cuando la
    pantalla lleva ESPERA_TEXTOS_MS sin moverse."""
    etiqueta._al_ancho = (margen, tope)
    textos = getattr(contenedor, "_textos_fluidos", None)
    if textos is None:
        textos = contenedor._textos_fluidos = []
        contenedor.bind("<Configure>", lambda _evento, c=contenedor: _anotar_caja_textos(c), add="+")
    textos.append(etiqueta)
    return etiqueta


def _anotar_caja_textos(caja):
    # Sin cancelar y volver a pedir el temporizador en cada <Configure> (son
    # cientos al abrir una pantalla): se apunta la hora, y el temporizador,
    # al vencer, mira si hubo movimiento después y espera lo que falte.
    raiz = caja._root()
    raiz.__dict__.setdefault("_cajas_textos", set()).add(caja)
    raiz._ultimo_cambio_textos = time.monotonic()
    if getattr(raiz, "_temporizador_textos", None) is None:
        raiz._temporizador_textos = raiz.after(ESPERA_TEXTOS_MS, _ajustar_textos_pendientes, raiz)


def _caja_asentada(caja):
    """¿Tiene ya la caja el ancho que va a tener? Tk atiende los
    temporizadores antes que su propio trabajo de colocar ventanas, así que
    el ajuste puede llegar con la pantalla a medio colocar: la pantalla aún
    sin mostrarse, o el interior de un CTkScrollableFrame con el ancho que
    PIDE (el de los textos largos) y no el de su lienzo, que se lo fija
    después. Una caja así se deja para cuando se mueva otra vez."""
    if not caja.winfo_viewable():
        return False
    w = caja
    while w is not None:
        if isinstance(w, ctk.CTkScrollableFrame) and w._orientation == "vertical"                 and w.winfo_width() != w._parent_canvas.winfo_width():
            return False
        w = w.master
    return True


def _ajustar_textos_pendientes(raiz, marca=None, turnos=0):
    falta = ESPERA_TEXTOS_MS / 1000 - (time.monotonic() - raiz._ultimo_cambio_textos)
    if falta > 0.005:
        raiz._temporizador_textos = raiz.after(int(falta * 1000) + 1, _ajustar_textos_pendientes, raiz)
        return
    # Tk coloca las ventanas en sus ratos libres, por tandas (el lienzo de un
    # CTkScrollableFrame fija el ancho de su interior, y solo en la tanda
    # siguiente el interior recoloca lo suyo). Se esperan tres ratos libres
    # seguidos sin que ninguna caja cambie; si cambia alguna, vuelta a esperar.
    if marca is not None and marca != raiz._ultimo_cambio_textos:
        raiz._temporizador_textos = raiz.after(ESPERA_TEXTOS_MS, _ajustar_textos_pendientes, raiz)
        return
    if turnos < 3:
        raiz._temporizador_textos = raiz.after_idle(_ajustar_textos_pendientes, raiz,
                                                    raiz._ultimo_cambio_textos, turnos + 1)
        return
    raiz._temporizador_textos = None
    cajas, raiz._cajas_textos = raiz._cajas_textos, set()
    for caja in cajas:
        try:
            if not caja.winfo_exists():
                continue
            if not _caja_asentada(caja):
                raiz._cajas_textos.add(caja)
                continue
            ancho_caja = caja.winfo_width() / ctk.ScalingTracker.get_widget_scaling(caja)
            vivas = [e for e in caja._textos_fluidos if e.winfo_exists()]
            caja._textos_fluidos = vivas
            for etiqueta in vivas:
                margen, tope = etiqueta._al_ancho
                ancho = int(ancho_caja) - margen
                if tope:
                    ancho = min(tope, ancho)
                if ancho > 40 and ancho != etiqueta.cget("wraplength"):
                    etiqueta.configure(wraplength=ancho)
        except Exception:
            continue


def fondo_de(widget):
    """El color que se ve dentro de `widget`."""
    if isinstance(widget, ctk.CTkBaseClass):
        try:
            color = widget.cget("fg_color")
            if color and color != "transparent":
                return widget._apply_appearance_mode(color)
        except Exception:
            pass
    # Un CTkFrame transparente, la ventana o un CTkScrollableFrame ponen en
    # el "bg" de Tk justo el color que se ve.
    return tk.Misc.cget(widget, "bg")


_EscalaCTk = ctk.windows.widgets.scaling.CTkScalingBaseClass


class _Escalable(ctk.windows.widgets.scaling.CTkScalingBaseClass):
    """Lo que un widget de Tk necesita para seguir el zoom de Windows como
    los de customtkinter: márgenes de pack/grid escalados, y volver a
    colocarse si la escala cambia (se apunta en el ScalingTracker de
    customtkinter; destroy lo borra de ahí, o lo retendría vivo).

    La colocación se guarda en `_last_geometry_manager_call`, el mismo
    nombre que usa customtkinter: _textos_al_ancho la lee igual en unos y
    otros. Cada clase pone en `_clase_tk` su widget de Tk."""

    _clase_tk = None

    def _iniciar_escala(self):
        _EscalaCTk.__init__(self, scaling_type="widget")
        self._last_geometry_manager_call = None

    def destroy(self):
        _EscalaCTk.destroy(self)
        self._clase_tk.destroy(self)

    def _set_scaling(self, escala_widget, escala_ventana):
        _EscalaCTk._set_scaling(self, escala_widget, escala_ventana)
        llamada = self._last_geometry_manager_call
        if llamada is not None:
            llamada["function"](self, **self._apply_argument_scaling(llamada["kwargs"]))

    def pack(self, **kwargs):
        self._last_geometry_manager_call = {"function": self._clase_tk.pack_configure, "kwargs": kwargs}
        return self._clase_tk.pack_configure(self, **self._apply_argument_scaling(kwargs))

    def grid(self, **kwargs):
        self._last_geometry_manager_call = {"function": self._clase_tk.grid_configure, "kwargs": kwargs}
        return self._clase_tk.grid_configure(self, **self._apply_argument_scaling(kwargs))

    def pack_forget(self):
        self._last_geometry_manager_call = None
        return self._clase_tk.pack_forget(self)

    def grid_forget(self):
        self._last_geometry_manager_call = None
        return self._clase_tk.grid_forget(self)


class Caja(_Escalable, tk.Frame):
    """Contenedor invisible para ordenar widgets (filas, cabeceras, columnas
    de texto), en lugar de un CTkFrame(fg_color="transparent").

    Rendimiento (1.8.0): un CTkFrame es un lienzo que dibuja un rectángulo
    redondeado aunque sea transparente, y lo vuelve a dibujar CADA vez que
    cambia de tamaño (unas cuatro veces mientras se coloca una pantalla).
    El rediseño de Inicio y Optimizar llenó las pantallas de esas cajas y
    cambiar de pantalla pasó a tardar el doble. Un tk.Frame no dibuja nada.
    Sin width/height escalados: para eso, un CTkFrame."""

    _clase_tk = tk.Frame

    def __init__(self, padre, **kwargs):
        tk.Frame.__init__(self, padre, bg=fondo_de(padre), bd=0, highlightthickness=0, **kwargs)
        self._iniciar_escala()


class Texto(_Escalable, tk.Label):
    """Etiqueta ligera (1.8.0): un tk.Label con la letra del tema, escalada
    con el zoom de Windows. Para el texto corriente de las pantallas (datos,
    descripciones, títulos) en lugar de una CTkLabel, que es un lienzo con
    un rectángulo redondeado más una etiqueta, y cuesta unas tres veces más
    crearla y dibujarla (ver CONTEXTO, "El rediseño hizo la app el DOBLE de
    lenta"). Para un texto con fondo y esquinas, una CTkLabel.

    Entiende `text_color` y `wraplength` (sin escalar) como una CTkLabel,
    así que texto_fluido y _actualizar_label le valen igual."""

    _clase_tk = tk.Label

    def __init__(self, padre, text="", size=12, weight="normal", color=None, family=None, wraplength=0,
                 anchor="w", justify="left", **kwargs):
        self._tam, self._peso, self._familia, self._wrap = size, weight, family, wraplength
        tk.Label.__init__(self, padre, text=text, fg=color or T.texto, bg=fondo_de(padre), anchor=anchor,
                          justify=justify, bd=0, highlightthickness=0, padx=0, pady=0, **kwargs)
        self._iniciar_escala()
        self._poner_letra()

    def _poner_letra(self):
        escala = self._get_widget_scaling()
        tk.Label.configure(self, font=(self._familia or T.familia, -round(self._tam * escala), self._peso),
                           wraplength=round(self._wrap * escala) if self._wrap else 0)

    def _set_scaling(self, escala_widget, escala_ventana):
        super()._set_scaling(escala_widget, escala_ventana)
        self._poner_letra()

    def configure(self, cnf=None, **kwargs):
        if "text_color" in kwargs:
            kwargs["fg"] = kwargs.pop("text_color")
        nuevo_ancho = "wraplength" in kwargs
        if nuevo_ancho:
            self._wrap = kwargs.pop("wraplength") or 0
        resultado = tk.Label.configure(self, cnf, **kwargs) if (cnf or kwargs) else None
        if nuevo_ancho:
            self._poner_letra()
        return resultado

    config = configure

    def cget(self, clave):
        if clave == "wraplength":
            return self._wrap
        if clave == "text_color":
            return tk.Label.cget(self, "fg")
        return tk.Label.cget(self, clave)


def miles(n):
    """12345 -> "12.345" en español, "12,345" en inglés."""
    texto = f"{int(n):,}"
    return texto.replace(",", ".") if idiomas.IDIOMA_ACTUAL == "es" else texto


def porcentaje(fraccion):
    """0.237 -> "24". Lo que no llega al 1 % sale "<1": un "0 %" mentiría."""
    if 0 < fraccion < 0.01:
        return "<1"
    return str(round(fraccion * 100))


def puede_ir_a_papelera(ruta):
    """¿Se ofrece mandar este archivo a la papelera desde Espacio en disco?
    Solo lo que es del usuario. Lo de Windows (pagefile.sys, hiberfil.sys),
    lo de los programas y los juegos (borrar un .pak rompe el juego), los
    datos de las apps (AppData) y lo de otras cuentas se quita desinstalando
    o desde su pestaña, no a mano de uno en uno."""
    r = os.path.normcase(os.path.abspath(ruta))
    casa = os.path.normcase(os.path.expanduser("~"))
    prohibidas = [os.environ.get(v) for v in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
                                              "ProgramData", "LOCALAPPDATA", "APPDATA")]
    prohibidas.append(os.path.join(casa, "AppData"))
    for carpeta in prohibidas:
        if carpeta and r.startswith(os.path.normcase(os.path.abspath(carpeta)) + os.sep):
            return False
    partes = r.split(os.sep)
    if len(partes) == 2 and r.endswith(".sys"):
        return False
    if len(partes) > 2 and partes[1] in ("windows", "program files", "program files (x86)", "programdata"):
        return False
    if any(p in ("steamapps", "windowsapps", "xboxgames", "system volume information") or p.startswith("$")
           for p in partes[1:-1]):
        return False
    usuarios = os.path.dirname(casa)
    if r.startswith(usuarios + os.sep) and not r.startswith(casa + os.sep):
        return False
    return True


def linea(padre):
    """Separador de 1 px del color del borde (un CTkFrame de alto 1 dibujaba
    un rectángulo redondeado entero para eso). 1 px no se escala."""
    separador = Caja(padre, height=1)
    separador.configure(bg=T.borde)
    return separador


class Tarjeta(_Escalable, tk.Canvas):
    """Un panel redondeado con borde, mucho más barato que un CTkFrame (1.8.0).

    Un CTkFrame con borde vuelve a dibujar su rectángulo redondeado con unas
    50 llamadas a Tk cada vez que cambia de tamaño (y al colocarse una
    pantalla cambia varias veces): con una pantalla llena de tarjetas, era
    lo que más hacía tardar el rediseño. Aquí el fondo ES el color del
    lienzo, las esquinas son cuatro imágenes suavizadas que se generan una
    vez por tema (iconos.esquinas) y el borde, cuatro rectángulos: al
    cambiar de tamaño se mueven 8 cosas, sin redibujar nada.

    Lo de dentro va con pack/grid como en cualquier caja, con un margen al
    menos igual al radio para no tapar las esquinas."""

    _clase_tk = tk.Canvas

    def __init__(self, padre, relleno=None, borde=None, radio=None, grosor=None):
        escala = ctk.ScalingTracker.get_widget_scaling(padre)
        self._relleno = relleno or T.panel
        self._borde = borde or T.borde
        self._r = max(0, round((T.radio_panel if radio is None else radio) * escala))
        self._b = max(0, round((T.borde_ancho if grosor is None else grosor) * escala))
        fuera = fondo_de(padre)
        tk.Canvas.__init__(self, padre, bg=self._relleno, highlightthickness=0, bd=0, width=1, height=1)
        self._iniciar_escala()
        self._piezas = []
        if self._r:
            for imagen, ancla in zip(iconos.esquinas(self._r, self._b, self._relleno, self._borde, fuera, self),
                                     ("nw", "ne", "sw", "se")):
                self._piezas.append(self.create_image(0, 0, image=imagen, anchor=ancla))
        if self._b:
            self._piezas += [self.create_rectangle(0, 0, 0, 0, width=0, fill=self._borde) for _ in range(4)]
        tk.Canvas.bind(self, "<Configure>", self._colocar, "+")

    def _colocar(self, evento):
        ancho, alto, r, b = evento.width, evento.height, self._r, self._b
        i = 0
        if r:
            for x, y in ((0, 0), (ancho, 0), (0, alto), (ancho, alto)):
                self.coords(self._piezas[i], x, y)
                i += 1
        if b:
            for caja in ((r, 0, ancho - r, b), (r, alto - b, ancho - r, alto),
                         (0, r, b, alto - r), (ancho - b, r, ancho, alto - r)):
                self.coords(self._piezas[i], *caja)
                i += 1


def tarjeta(padre, **kwargs):
    """Un panel con el aspecto del tema: fondo, borde y esquinas."""
    return Tarjeta(padre, **kwargs)


def tarjeta_seccion(padre, titulo, icono=None, descripcion=None):
    """Un panel con su cabecera: icono, título y, a la derecha, lo que el
    que llama quiera poner (una píldora, un botón). Devuelve
    (panel, derecha). La descripción, si la hay, se parte al ancho real."""
    panel = tarjeta(padre)
    cabecera = Caja(panel)
    cabecera.pack(fill="x", padx=18, pady=(16, 4 if descripcion else 10))
    if icono:
        escala = ctk.ScalingTracker.get_widget_scaling(cabecera)
        Texto(cabecera, image=iconos.foto(icono, T.acento, 18, escala, cabecera)).pack(side="left", padx=(0, 10))
    Texto(cabecera, _sin_emoji(titulo), size=15, weight="bold").pack(side="left")
    derecha = Caja(cabecera)
    derecha.pack(side="right")
    if descripcion:
        texto_fluido(Texto(panel, descripcion, size=12, color=T.texto2, wraplength=760), panel, 36).pack(
            fill="x", padx=18, pady=(0, 12))
    return panel, derecha


def pildora(padre, texto="", nivel="info"):
    """Una etiqueta corta con fondo redondeado: el estado de algo ("Bien",
    "23 %"). nivel: bien / atencion / critico / info. Sin texto no se ve
    (si no, un fondo redondeado vacío parecía una mancha)."""
    color = {"bien": T.ok, "atencion": T.aviso, "critico": T.critico}.get(nivel, T.texto2)
    return ctk.CTkLabel(padre, text=texto, font=fuente(size=12, weight="bold"),
                        fg_color=T.fila if texto else "transparent", corner_radius=10, text_color=color,
                        height=24)


def poner_pildora(etiqueta, texto, nivel="info"):
    color = {"bien": T.ok, "atencion": T.aviso, "critico": T.critico}.get(nivel, T.texto2)
    if etiqueta.cget("text") != texto or etiqueta.cget("text_color") != color:
        etiqueta.configure(text=texto, text_color=color, fg_color=T.fila if texto else "transparent")


def hace_cuanto(segundos):
    """"hace 5 min", "hace 3 h", "hace 2 días"."""
    segundos = max(0, segundos)
    if segundos < 3600:
        return t("uso_hace_min", n=max(1, int(segundos // 60)))
    if segundos < 86400:
        return t("uso_hace_h", n=int(segundos // 3600))
    dias = int(segundos // 86400)
    return t("uso_hace_1d") if dias == 1 else t("uso_hace_d", n=dias)


def fila(padre, icono, titulo, descripcion, primera=False, margen=20, color_icono=None):
    """Una fila de las pantallas rediseñadas: el icono en su cuadrito, el
    título y qué hace (partido al ancho real). Devuelve la Caja de la
    derecha, para el botón, el interruptor o lo que toque. Entre fila y fila,
    una línea fina."""
    if not primera:
        linea(padre).pack(fill="x", padx=margen)
    caja = Caja(padre)
    caja.pack(fill="x", padx=margen, pady=12)
    escala = ctk.ScalingTracker.get_widget_scaling(padre)
    Texto(caja, image=iconos.icono_cuadro(icono, color_icono or T.acento, T.fila, fondo_de(caja), 38,
                                          T.radio_boton, 18, escala, caja)).pack(side="left", anchor="n",
                                                                                padx=(0, 14))
    derecha = Caja(caja)
    derecha.pack(side="right", padx=(12, 0))
    textos = Caja(caja)
    textos.pack(side="left", fill="x", expand=True)
    Texto(textos, _sin_emoji(titulo), size=14, weight="bold").pack(fill="x")
    derecha.textos = textos      # por si quien llama quiere añadir notas debajo
    if descripcion:
        texto_fluido(Texto(textos, descripcion, size=12, color=T.texto2, wraplength=620), textos, 4).pack(fill="x")
    return derecha


def fila_accion(padre, icono, titulo, descripcion, texto_boton, comando, primera=False, margen=20):
    """Una fila con su botón (secundario) a la derecha. Devuelve el botón."""
    boton = boton_secundario(fila(padre, icono, titulo, descripcion, primera, margen), texto_boton, comando,
                             width=110, height=34)
    boton.pack()
    return boton


def casilla(padre, marcada=False, **kwargs):
    """Una CTkCheckBox SIN variable de Tk: ella misma guarda si está marcada
    y .get() da 1 o 0, igual que la variable. Con una BooleanVar por casilla,
    al cerrar la pantalla el recolector de Python a veces las liberaba desde
    un hilo de fondo: Tk avisaba "main thread is not in main loop" y la
    variable se quedaba sin borrar en Tcl (1.8.0, visto al medir)."""
    c = ctk.CTkCheckBox(padre, **kwargs)
    if marcada:
        c.select()
    return c


def fila_interruptor(padre, icono, titulo, descripcion, encendido, comando, primera=False, margen=20):
    """Una fila con un interruptor a la derecha. Devuelve (interruptor,
    Caja de la derecha) por si se quiere poner un estado al lado."""
    derecha = fila(padre, icono, titulo, descripcion, primera, margen)
    interruptor = ctk.CTkSwitch(derecha, text="", width=46, command=comando)
    if encendido:
        interruptor.select()
    interruptor.pack(side="right")
    return interruptor, derecha


class ListaDatos(Caja):
    """Filas "dato: valor" (Componentes, salud del disco...). Cada fila se
    crea la primera vez que se pone y después solo cambia su texto, y solo
    si cambió: Componentes la refresca cada 3 segundos."""

    def __init__(self, padre):
        super().__init__(padre)
        self.grid_columnconfigure(1, weight=1)
        self._filas = {}

    def poner(self, clave, etiqueta, valor, color=None):
        valor = "" if valor is None else str(valor)
        color = color or T.texto
        fila = self._filas.get(clave)
        if fila is None:
            n = len(self._filas)
            k = Texto(self, etiqueta, size=12, color=T.texto2)
            k.grid(row=n, column=0, sticky="nw", pady=2, padx=(0, 16))
            v = Texto(self, valor, size=12, color=color, wraplength=300)
            v.grid(row=n, column=1, sticky="w", pady=2)
            self._filas[clave] = [k, v, valor, color]
            return
        if fila[2] != valor or fila[3] != color:
            fila[1].configure(text=valor, fg=color)
            fila[2], fila[3] = valor, color

    def quitar(self, clave):
        fila = self._filas.pop(clave, None)
        if fila:
            fila[0].destroy()
            fila[1].destroy()


class ListaLienzo(_Escalable, tk.Canvas):
    """Una lista de filas dibujada en UN lienzo (1.8.0): icono, título, una
    barra o un detalle debajo, el valor a la derecha y, según la fila, una
    flecha para entrar o acciones de texto ("Mostrar", "A la papelera").

    Por qué: en Windows cada widget de Tk es una ventana del sistema. Las
    40 carpetas de Espacio en disco con un widget por pieza eran ~450
    ventanas, y colocarlas tardaba 0,6-0,9 s cada vez que se entraba en una
    carpeta. Un lienzo es una sola ventana: lo mismo, en unos milisegundos.

    filas: diccionarios con titulo y, si se quiere, icono, color_icono,
    negrita (sí por defecto), color_titulo, detalle, recorte ("fin" o
    "inicio": por dónde se corta el detalle si no cabe; "inicio" para
    rutas), fraccion (dibuja una barra), color_barra, valor, color_valor,
    entrar (función: toda la fila se pulsa, con una flecha), pulsar (igual,
    sin flecha: para ver el detalle) y acciones [(texto, función)].

    Interruptor (1.8.0): con "interruptor" (True/False) y "al_cambiar"
    (función(nuevo, listo)), la fila lleva uno dibujado como el de Windows.
    Al pulsarlo cambia al momento y queda en espera; quien lo gestiona
    llama a listo(exito) desde el hilo de la interfaz, y si no se pudo,
    vuelve a donde estaba (no mentir con el interruptor). Un CTkSwitch por
    fila eran ~12 ventanas de Windows más por fila: Inicio de Windows
    tardaba el doble que en la 1.7.0."""

    _clase_tk = tk.Canvas
    ALTO = 58

    def __init__(self, padre, margen=20):
        tk.Canvas.__init__(self, padre, bg=fondo_de(padre), highlightthickness=0, bd=0, width=1, height=1)
        self._iniciar_escala()
        self._margen = margen
        self._filas = []
        self._zonas = []        # (x0, y0, x1, y1, función, texto de la acción o None)
        self._ancho = 0
        self._encima = None
        self._resalte = None
        self._pendiente = None
        self._geo_interruptores = {}
        tk.Canvas.bind(self, "<Configure>", self._al_cambiar, "+")
        tk.Canvas.bind(self, "<Motion>", self._mover, "+")
        tk.Canvas.bind(self, "<Leave>", lambda _e: self._resaltar(None), "+")
        tk.Canvas.bind(self, "<Button-1>", self._pulsar, "+")

    def poner(self, filas):
        self._filas = list(filas)
        alto = round(self.ALTO * self._get_widget_scaling())
        tk.Canvas.configure(self, height=max(1, len(self._filas) * alto))
        self._pedir_dibujo()

    def _pedir_dibujo(self):
        """Se dibuja una vez, cuando Tk queda libre: al colocarse, el ancho
        cambia varias veces seguidas y cada dibujo completo cuesta."""
        if self._pendiente is None:
            self._pendiente = self.after_idle(self._dibujar)

    def _set_scaling(self, escala_widget, escala_ventana):
        super()._set_scaling(escala_widget, escala_ventana)
        self._pedir_dibujo()

    def _letra(self, tam, peso="normal"):
        return (T.familia, -round(tam * self._get_widget_scaling()), peso)

    _medidas = {}

    def _medir(self, letra, texto):
        """Ancho en píxeles de un texto. Cada medida es una llamada a Tk
        (~0,2 ms) y recortar un texto pide varias: se guardan."""
        clave = (letra, texto)
        medida = self._medidas.get(clave)
        if medida is None:
            if len(self._medidas) > 20000:
                self._medidas.clear()
            medida = self._medidas[clave] = int(self.tk.call("font", "measure", letra, texto))
        return medida

    def _recortar(self, texto, letra, ancho, por="fin"):
        """El texto entero si cabe; si no, cortado con "…" (al final, o al
        principio para que de una ruta se vea el final)."""
        if self._medir(letra, texto) <= ancho:
            return texto
        bajo, alto = 0, len(texto)
        while bajo < alto:
            medio = (bajo + alto + 1) // 2
            prueba = "…" + texto[-medio:] if por == "inicio" else texto[:medio] + "…"
            if self._medir(letra, prueba) <= ancho:
                bajo = medio
            else:
                alto = medio - 1
        if not bajo:
            return "…"
        return "…" + texto[-bajo:] if por == "inicio" else texto[:bajo] + "…"

    def _al_cambiar(self, evento):
        if evento.width != self._ancho:
            self._ancho = evento.width
            self._pedir_dibujo()

    def _dibujar(self):
        self._pendiente = None
        if not self.winfo_exists():
            return
        self.delete("all")
        self._zonas = []
        self._encima = None
        self._geo_interruptores = {}
        e = self._get_widget_scaling()
        alto = round(self.ALTO * e)
        tk.Canvas.configure(self, height=max(1, len(self._filas) * alto))
        ancho = self.winfo_width()
        if ancho < 60:
            return      # se dibuja al colocarse, cuando ya tiene ancho
        m = round(self._margen * e)
        self._resalte = self.create_rectangle(0, 0, 0, 0, fill=T.hover, width=0, state="hidden")
        letra_titulo, letra_fina = self._letra(13, "bold"), self._letra(13)
        letra_detalle, letra_accion = self._letra(11), self._letra(12, "bold")
        hueco = round(16 * e)
        # Columnas del mismo ancho en todas las filas: así las barras, los
        # valores y los detalles quedan alineados.
        flecha = round(26 * e) if any(f.get("entrar") for f in self._filas) else 0
        interruptor = round(52 * e) if any("interruptor" in f for f in self._filas) else 0
        ancho_acciones = max((sum(self._medir(letra_accion, texto) for texto, _ in f["acciones"])
                              + hueco * (len(f["acciones"]) - 1) for f in self._filas if f.get("acciones")),
                             default=0)
        ancho_valor = max((self._medir(letra_titulo, f["valor"]) for f in self._filas if f.get("valor")), default=0)
        ancho_detalle = max((self._medir(letra_detalle, f["detalle"]) for f in self._filas
                             if f.get("fraccion") is not None and f.get("detalle")), default=0)
        for i, f in enumerate(self._filas):
            y0 = i * alto
            centro = y0 + alto / 2
            if i:
                self.create_line(m, y0, ancho - m, y0, fill=T.borde)
            x = m
            if f.get("icono"):
                self.create_image(x, centro, anchor="w",
                                  image=iconos.foto(f["icono"], f.get("color_icono") or T.acento, 18, e, self))
                x += round(30 * e)
            derecha = ancho - m
            if "interruptor" in f:
                self._geo_interruptores[i] = (derecha, centro)
                self._pintar_interruptor(i)
                ancho_sw = round(36 * e)
                self._zonas.append((derecha - ancho_sw - 6, y0, derecha + 6, y0 + alto,
                                    lambda f=f: self._alternar(f), -1))
            derecha -= interruptor
            if f.get("entrar"):
                self.create_image(derecha, centro, anchor="e", image=iconos.foto("flecha", T.texto3, 14, e, self))
            derecha -= flecha
            borde_acciones = derecha
            for texto, funcion in reversed(f.get("acciones") or []):
                item = self.create_text(borde_acciones, centro, text=texto, anchor="e", fill=T.acento,
                                        font=letra_accion)
                x0 = self.bbox(item)[0]
                self._zonas.append((x0 - 6, y0, borde_acciones + 6, y0 + alto, funcion, item))
                borde_acciones = x0 - hueco
            if ancho_acciones:
                derecha -= ancho_acciones + round(22 * e)
            if f.get("valor"):
                self.create_text(derecha, centro, text=f["valor"], anchor="e", font=letra_titulo,
                                 fill=f.get("color_valor") or T.texto)
            if ancho_valor:
                derecha -= ancho_valor + hueco
            cabe = max(20, derecha - x)
            doble = bool(f.get("detalle")) or f.get("fraccion") is not None
            letra = letra_titulo if f.get("negrita", True) else letra_fina
            self.create_text(x, y0 + alto * (0.34 if doble else 0.5), anchor="w", font=letra,
                             text=self._recortar(f.get("titulo", ""), letra, cabe),
                             fill=f.get("color_titulo") or T.texto)
            if doble:
                y2 = y0 + alto * 0.7
                detalle = f.get("detalle") or ""
                if f.get("fraccion") is not None:
                    fin_barra = derecha
                    if ancho_detalle:
                        self.create_text(derecha - ancho_detalle, y2, text=detalle, anchor="w", font=letra_detalle,
                                         fill=T.texto2)
                        fin_barra = derecha - ancho_detalle - round(12 * e)
                    grosor = max(3, round(5 * e))
                    inicio, fin = x + grosor / 2, max(x + grosor / 2, fin_barra - grosor / 2)
                    self.create_line(inicio, y2, fin, y2, width=grosor, fill=T.pista, capstyle="round")
                    largo = (fin - inicio) * max(0.0, min(1.0, f["fraccion"]))
                    if largo >= 1:
                        self.create_line(inicio, y2, inicio + largo, y2, width=grosor, capstyle="round",
                                         fill=f.get("color_barra") or T.acento)
                else:
                    self.create_text(x, y2, anchor="w", font=letra_detalle, fill=T.texto2,
                                     text=self._recortar(detalle, letra_detalle, cabe, f.get("recorte", "fin")))
            if f.get("entrar") or f.get("pulsar"):
                self._zonas.append((0, y0, ancho, y0 + alto, f.get("entrar") or f.get("pulsar"), None))

    def _pintar_interruptor(self, i):
        """El interruptor de la fila i: pista de punta redonda y el botón,
        como el de customtkinter (los mismos colores del tema)."""
        geo = self._geo_interruptores.get(i)
        if geo is None:
            return
        f = self._filas[i]
        x1, cy = geo
        e = self._get_widget_scaling()
        alto, ancho = round(18 * e), round(36 * e)
        r = alto / 2
        x0 = x1 - ancho
        etiqueta = f"sw{i}"
        self.delete(etiqueta)
        encendido, ocupado = bool(f["interruptor"]), f.get("ocupado")
        self.create_line(x0 + r, cy, x1 - r, cy, width=alto, capstyle="round", tags=(etiqueta,),
                         fill=T.acento if encendido else T.pista)
        cx = x1 - r if encendido else x0 + r
        rb = r - max(2, round(3 * e))
        self.create_oval(cx - rb, cy - rb, cx + rb, cy + rb, width=0, tags=(etiqueta,),
                         fill=T.texto3 if ocupado else T.texto)

    def _alternar(self, fila):
        if fila.get("ocupado") or fila.get("al_cambiar") is None:
            return
        nuevo = not fila["interruptor"]
        fila["interruptor"], fila["ocupado"] = nuevo, True
        self._repintar_interruptor(fila)

        def listo(exito):
            fila["ocupado"] = False
            if not exito:
                fila["interruptor"] = not nuevo
            if self.winfo_exists():
                self._repintar_interruptor(fila)
        fila["al_cambiar"](nuevo, listo)

    def _repintar_interruptor(self, fila):
        i = next((n for n, f in enumerate(self._filas) if f is fila), None)
        if i is not None:
            self._pintar_interruptor(i)

    def _zona(self, evento):
        return next((z for z in self._zonas if z[0] <= evento.x <= z[2] and z[1] <= evento.y < z[3]), None)

    def _mover(self, evento):
        self._resaltar(self._zona(evento))

    def _resaltar(self, zona):
        if zona is self._encima or self._resalte is None:
            return
        # zona[5]: el texto de una acción (se resalta), None si es la fila
        # entera, -1 si es un interruptor.
        if self._encima is not None and self._encima[5] is not None and self._encima[5] > 0:
            self.itemconfigure(self._encima[5], fill=T.acento)
        self._encima = zona
        if zona is None:
            self.itemconfigure(self._resalte, state="hidden")
            tk.Canvas.configure(self, cursor="")
            return
        tk.Canvas.configure(self, cursor="hand2")
        if zona[5] is not None:
            if zona[5] > 0:
                self.itemconfigure(zona[5], fill=T.texto)
            self.itemconfigure(self._resalte, state="hidden")
        else:
            m = round(self._margen * self._get_widget_scaling()) // 2
            self.coords(self._resalte, m, zona[1] + 1, zona[2] - m, zona[3])
            self.itemconfigure(self._resalte, state="normal")
            self.tag_lower(self._resalte)

    def _pulsar(self, evento):
        zona = self._zona(evento)
        if zona is not None:
            zona[4]()


class BarraReparto(tk.Canvas):
    """Una barra partida en trozos de colores (el espacio por tipo de
    archivo), con las puntas redondas: una imagen (iconos.barra_reparto)
    sobre un lienzo. Solo se vuelve a dibujar si cambia el ancho."""

    def __init__(self, padre, grosor=14):
        escala = ctk.ScalingTracker.get_widget_scaling(padre)
        self._alto = max(6, round(grosor * escala))
        super().__init__(padre, height=self._alto, bg=fondo_de(padre), highlightthickness=0, bd=0)
        self._partes, self._ancho, self._foto = [], 0, None
        self._imagen = self.create_image(0, 0, anchor="nw")
        self.bind("<Configure>", lambda e: self._dibujar(e.width))

    def poner(self, partes):
        """partes: [(fracción, color)], en orden."""
        self._partes = list(partes)
        self._ancho = 0
        self._dibujar(self.winfo_width())

    def _dibujar(self, ancho):
        if ancho < self._alto * 2 or ancho == self._ancho:
            return
        self._ancho = ancho
        self._foto = iconos.barra_reparto(ancho, self._alto, self._partes, T.pista, self.cget("bg"), self)
        self.itemconfigure(self._imagen, image=self._foto)


class BarraFina(tk.Canvas):
    """Una barra de uso de punta redonda (lo lleno de un disco, de la
    batería...). Dos líneas de un lienzo: mucho más barata que una
    CTkProgressBar (~10 ms cada una)."""

    def __init__(self, padre, grosor=6):
        escala = ctk.ScalingTracker.get_widget_scaling(padre)
        self._grosor = max(3, round(grosor * escala))
        super().__init__(padre, height=self._grosor + 2, bg=fondo_de(padre), highlightthickness=0, bd=0)
        y = self._grosor / 2 + 1
        estilo = {"width": self._grosor, "capstyle": "round"}
        self._pista = self.create_line(0, y, 1, y, fill=T.pista, **estilo)
        self._lleno = self.create_line(0, y, 1, y, fill=T.acento, state="hidden", **estilo)
        self._fraccion = 0.0
        self.bind("<Configure>", lambda _e: self._colocar())

    def poner(self, fraccion, color=None):
        self._fraccion = max(0.0, min(1.0, fraccion or 0.0))
        if color:
            self.itemconfigure(self._lleno, fill=color)
        self._colocar()

    def _colocar(self):
        ancho = self.winfo_width()
        borde = self._grosor / 2
        largo = max(0.0, ancho - 2 * borde)
        y = self._grosor / 2 + 1
        self.coords(self._pista, borde, y, borde + largo, y)
        lleno = largo * self._fraccion
        self.coords(self._lleno, borde, y, borde + lleno, y)
        self.itemconfigure(self._lleno, state="normal" if lleno >= 1 else "hidden")


class BarrasNucleos(tk.Canvas):
    """El uso de cada núcleo del procesador como columnas (antes era una
    línea de texto: "N0:43% N1:45% N2:58%..."). Un lienzo con un rectángulo
    por núcleo; cada refresco solo mueve los rectángulos."""

    ALTO = 46

    def __init__(self, padre):
        escala = ctk.ScalingTracker.get_widget_scaling(padre)
        self._alto = round(self.ALTO * escala)
        super().__init__(padre, height=self._alto, bg=fondo_de(padre), highlightthickness=0, bd=0)
        self._valores = []
        self._fondos = []
        self._barras = []
        self.bind("<Configure>", lambda _e: self._colocar())

    def poner(self, valores):
        valores = list(valores or [])
        if len(valores) != len(self._barras):
            self.delete("all")
            self._fondos = [self.create_rectangle(0, 0, 0, 0, width=0, fill=T.pista) for _ in valores]
            self._barras = [self.create_rectangle(0, 0, 0, 0, width=0, fill=T.acento) for _ in valores]
        self._valores = valores
        for barra, valor in zip(self._barras, valores):
            self.itemconfigure(barra, fill=color_uso(valor))
        self._colocar()

    def _colocar(self):
        n = len(self._valores)
        if not n:
            return
        ancho = self.winfo_width()
        hueco = max(2, ancho // (n * 6))
        columna = max(2, (ancho - hueco * (n - 1)) / n)
        for i, valor in enumerate(self._valores):
            x0 = i * (columna + hueco)
            alto = max(2, self._alto * min(100, valor) / 100)
            self.coords(self._fondos[i], x0, 0, x0 + columna, self._alto)
            self.coords(self._barras[i], x0, self._alto - alto, x0 + columna, self._alto)


def boton_secundario(padre, texto, comando, icono=None, **kwargs):
    """Botón de acción secundaria con los colores del tema (el principal es
    un CTkButton normal: el tema ya le pone el acento)."""
    extra = {"image": iconos.icono(icono, T.texto, 16), "compound": "left"} if icono else {}
    return ctk.CTkButton(padre, text=texto, command=comando, fg_color=T.boton2, hover_color=T.boton2_hover,
                         text_color=T.texto, border_width=1 if T.borde_ancho else 0, border_color=T.borde,
                         **extra, **kwargs)


class TarjetaMetrica(_ValorAnimado, ctk.CTkFrame):
    """Tarjeta de Inicio (1.8.0): icono y nombre, el porcentaje en grande,
    una barra y el detalle. Misma interfaz que el Gauge que sustituye
    (set_value), así que _refrescar_gauges no cambió; la animación es la de _ValorAnimado.

    Rendimiento: el número y la barra van en un tk.Canvas (un texto y dos
    líneas de punta redonda), no en una CTkLabel y una CTkProgressBar. La
    barra de customtkinter tardaba ~10 ms en crearse y dibujarse y se
    redibujaba entera en cada paso de la animación (16 por refresco y por
    tarjeta, también con Inicio quieto). Aquí cada paso son dos llamadas."""

    def __init__(self, master, titulo, icono, **kwargs):
        super().__init__(master, fg_color=T.panel, corner_radius=T.radio_panel, border_width=T.borde_ancho,
                         border_color=T.borde, **kwargs)
        self._valor_mostrado = 0.0
        self._anim_id = None
        self._pintado = (None, None)     # (color del número, color de la barra)
        self._detalle = None
        ctk.CTkLabel(self, text=f"  {titulo}", image=iconos.icono(icono, T.texto2, 16), compound="left",
                     font=fuente(size=13), text_color=T.texto2, anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        # tk.Canvas no sigue el zoom de Windows: medidas escaladas a mano.
        e = ctk.ScalingTracker.get_widget_scaling(self)
        self.lienzo = tk.Canvas(self, height=1, bg=T.panel, highlightthickness=0, bd=0)
        self.lienzo.pack(fill="x", padx=round(16 * e), pady=(0, round(8 * e)))
        self._texto = self.lienzo.create_text(0, 0, anchor="nw", text="--", fill=T.texto,
                                              font=(T.familia_num, -round(30 * e), "bold"))
        self._grosor = max(4, round(6 * e))
        alto_texto = self.lienzo.bbox(self._texto)[3]
        self._y_barra = alto_texto + round(6 * e) + self._grosor // 2
        self.lienzo.configure(height=self._y_barra + self._grosor // 2 + 1)
        linea_barra = {"width": self._grosor, "capstyle": "round"}
        self._pista = self.lienzo.create_line(0, self._y_barra, 1, self._y_barra, fill=T.pista, **linea_barra)
        self._relleno = self.lienzo.create_line(0, self._y_barra, 1, self._y_barra, fill=T.acento,
                                                state="hidden", **linea_barra)
        self._fraccion = 0.0
        self.lienzo.bind("<Configure>", lambda _evento: self._colocar_barra())
        self.lbl_detalle = ctk.CTkLabel(self, text="", font=fuente(size=12), text_color=T.texto2, anchor="w")
        self.lbl_detalle.pack(fill="x", padx=16, pady=(0, 14))
        self.set_value(0, t("comun_cargando"))

    def _colocar_barra(self):
        ancho = self.lienzo.winfo_width()
        borde = self._grosor / 2           # la punta redonda sobresale media línea
        largo = max(0.0, ancho - 2 * borde)
        self.lienzo.coords(self._pista, borde, self._y_barra, borde + largo, self._y_barra)
        lleno = largo * self._fraccion
        self.lienzo.coords(self._relleno, borde, self._y_barra, borde + lleno, self._y_barra)
        # Vacía del todo: con 0 una línea de punta redonda aún pinta un punto.
        self.lienzo.itemconfigure(self._relleno, state="normal" if lleno >= 1 else "hidden")

    def _dibujar(self, porcentaje):
        if porcentaje is None:
            texto, color_texto, color_barra, self._fraccion = "—", T.texto3, T.pista, 0.0
        else:
            texto, color_texto, color_barra = f"{porcentaje:.0f}%", T.texto, color_uso(porcentaje)
            self._fraccion = porcentaje / 100
        if self._pintado[0] != color_texto:
            self.lienzo.itemconfigure(self._texto, text=texto, fill=color_texto)
        else:
            self.lienzo.itemconfigure(self._texto, text=texto)
        if self._pintado[1] != color_barra:
            self.lienzo.itemconfigure(self._relleno, fill=color_barra)
        self._pintado = (color_texto, color_barra)
        self._colocar_barra()


class GaleriaTemas(tk.Canvas):
    """Ajustes → Apariencia: una tarjeta por tema (miniatura, nombre y
    descripción) que se elige con un clic.

    Rendimiento (1.8.0): con widgets eran 9 tarjetas × 4 (marco, miniatura,
    nombre y descripción), y la galería sola le sumaba ~0.8 s a abrir
    Ajustes. Aquí todo va en UN lienzo: cada tarjeta es una imagen de fondo
    (con la miniatura dentro) y dos textos. Las tarjetas tienen ancho fijo
    y se reparten en tantas columnas como quepan."""

    ANCHO = 224     # sin escalar, como el resto de medidas de la interfaz
    HUECO = 12

    def __init__(self, padre, al_elegir):
        self._fondo = fondo_de(padre)
        super().__init__(padre, height=1, bg=self._fondo, highlightthickness=0, bd=0, cursor="hand2")
        # tk.Canvas no sigue el zoom de Windows: medidas escaladas a mano.
        e = self._escala = ctk.ScalingTracker.get_widget_scaling(padre)
        self._ancho = round(self.ANCHO * e)
        self._hueco = round(self.HUECO * e)
        self._al_elegir = al_elegir
        self._fotos = {}         # (nombre, resaltada) -> PhotoImage; Tk borra las que nadie guarda
        self._tarjetas = []      # [nombre, fondo, ((id, x, y), ...)]
        self._columnas = None
        margen = round(12 * e)
        ancho_texto = self._ancho - 2 * margen
        y = round(10 * e) + round(104 * e) + round(8 * e)
        alto = 0
        for nombre in temas.ORDEN:
            clave_nombre, clave_desc = NOMBRES_TEMA[nombre]
            texto = t(clave_nombre) + (f"   ·   {t('apariencia_en_uso')}" if nombre == T.nombre else "")
            etiqueta = f"tema_{nombre}"
            id_nombre = self.create_text(margen, y, anchor="nw", text=texto, fill=T.texto, width=ancho_texto,
                                         font=(T.familia, -round(13 * e), "bold"), tags=(etiqueta,))
            y_desc = self.bbox(id_nombre)[3] + round(2 * e)
            id_desc = self.create_text(margen, y_desc, anchor="nw", text=t(clave_desc), fill=T.texto2,
                                       width=ancho_texto, font=(T.familia, -round(11 * e)), tags=(etiqueta,))
            alto = max(alto, self.bbox(id_desc)[3] + round(10 * e))
            self._tarjetas.append([nombre, None, ((id_nombre, margen, y), (id_desc, margen, y_desc))])
            self.tag_bind(etiqueta, "<Button-1>", lambda _e, n=nombre: self._al_elegir(n))
            self.tag_bind(etiqueta, "<Enter>", lambda _e, n=nombre: self._resaltar(n, True))
            self.tag_bind(etiqueta, "<Leave>", lambda _e, n=nombre: self._resaltar(n, False))
        self._alto = alto
        for tarjeta in self._tarjetas:
            tarjeta[1] = self.create_image(0, 0, anchor="nw", image=self._foto(tarjeta[0], False),
                                           tags=(f"tema_{tarjeta[0]}",))
            self.tag_lower(tarjeta[1])
        self.bind("<Configure>", self._colocar)

    def _foto(self, nombre, resaltada):
        clave = (nombre, resaltada)
        if clave not in self._fotos:
            elegido = nombre == T.nombre
            e = self._escala
            self._fotos[clave] = iconos.tarjeta_tema(
                self, temas.TEMAS[nombre], self._ancho, self._alto, e, relleno=T.fila,
                borde=T.acento if elegido else (T.texto3 if resaltada else T.borde),
                grosor=round((2 if elegido else 1) * e), radio=round(T.radio_fila * e), fondo=self._fondo)
        return self._fotos[clave]

    def _resaltar(self, nombre, si):
        # La que está en uso ya lleva el borde del acento.
        if nombre == T.nombre:
            return
        for tarjeta in self._tarjetas:
            if tarjeta[0] == nombre:
                self.itemconfigure(tarjeta[1], image=self._foto(nombre, si))

    def _colocar(self, evento):
        # Cuenta el ancho, no solo las columnas: con las mismas columnas el
        # sobrante cambia, y repartido para un ancho mayor la última columna
        # quedaba cortada (pasaba en Alto contraste, mientras Ajustes se
        # colocaba con un ancho provisional).
        columnas = max(1, (evento.width + self._hueco) // (self._ancho + self._hueco))
        if (columnas, evento.width) == self._columnas:
            return
        self._columnas = (columnas, evento.width)
        # El sobrante se reparte entre las columnas, para no dejar un hueco
        # grande a la derecha.
        hueco = self._hueco if columnas == 1 else (evento.width - columnas * self._ancho) // (columnas - 1)
        for i, (_, fondo, textos) in enumerate(self._tarjetas):
            x0 = (i % columnas) * (self._ancho + hueco)
            y0 = (i // columnas) * (self._alto + self._hueco)
            self.coords(fondo, x0, y0)
            for id_texto, x, y in textos:
                self.coords(id_texto, x0 + x, y0 + y)
        filas = -(-len(self._tarjetas) // columnas)
        self.configure(height=filas * self._alto + (filas - 1) * self._hueco)


class Sparkline(ctk.CTkFrame):
    """
    Mini gráfica de línea de tiempo (los últimos N valores), tipo las que
    trae HWiNFO/Task Manager — reutilizable para RAM, CPU o temperatura.
    Liviana a propósito: dibuja sobre un tk.Canvas normal, sin ninguna
    librería de gráficos nueva.

    NOTA: el constructor solo acepta master/titulo/unidad (como el antiguo
    Gauge, que sabemos que funcionaba bien). Cualquier otro ajuste
    (color de línea, máximo, tamaño) se hace DESPUÉS de crear el objeto,
    llamando a .configurar(...) — nunca por el constructor. Así se evita
    de raíz el problema de argumentos rechazados por customtkinter, sin
    depender de adivinar qué nombre específico le molesta.

    BUG corregido (el que se veía feo en pantallas anchas): el canvas tenía
    un ancho FIJO de 260 px, pero el panel que lo contiene se estira con la
    ventana (sticky="we"). Resultado: la gráfica quedaba como un bloquecito
    perdido en medio de un panel enorme y vacío. Ahora el canvas se estira
    con el panel y se vuelve a dibujar solo cuando cambia de tamaño.

    Además el valor nuevo ya no aparece de golpe: entra deslizándose por la
    derecha mientras sube o baja desde el valor anterior, con la misma
    curva que las tarjetas de Inicio.
    """

    DURACION_MS = 360    # lo que tarda el punto nuevo en terminar de entrar
    PASO_MS = 20
    MARGEN = 6           # aire arriba y abajo para que la línea no se corte
    BANDAS = 10          # franjas horizontales que fingen el degradado

    def __init__(self, master, titulo, unidad="%", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel,
                         border_width=T.borde_ancho, border_color=T.borde, **kwargs)
        self.titulo = titulo
        self.unidad = unidad
        self.maximo = 100
        self.ancho = 260
        self.alto = 70
        self.tono = COLOR_OK
        self.max_puntos = 60
        self.valores = []
        self._t = 1.0          # 0 = el punto nuevo aún está entrando, 1 = ya llegó
        self._anim_id = None

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(fila, text=titulo, font=fuente(size=12, weight="bold")).pack(side="left")
        self.lbl_actual = ctk.CTkLabel(fila, text="--", font=fuente(size=15, weight="bold"),
                                        text_color=self.tono)
        self.lbl_actual.pack(side="right")
        self.lbl_extremos = ctk.CTkLabel(fila, text="", font=fuente(size=10), text_color=T.texto3)
        self.lbl_extremos.pack(side="right", padx=(0, 10))

        self.canvas = tk.Canvas(self, height=self.alto, bg=COLOR_BG_PANEL, highlightthickness=0)
        self.canvas.pack(fill="x", expand=True, padx=12, pady=(0, 12))
        self.canvas.bind("<Configure>", self._al_redimensionar)

    def _al_redimensionar(self, event):
        nuevo = max(int(event.width), 10)
        if abs(nuevo - self.ancho) < 2:
            return
        self.ancho = nuevo
        self._dibujar()

    def configurar(self, tono=None, maximo=None, ancho=None, alto=None, max_puntos=None):
        """Ajusta la apariencia después de construido — ver nota de la clase."""
        if tono is not None:
            self.tono = tono
            self.lbl_actual.configure(text_color=tono)
        if maximo is not None:
            self.maximo = maximo
        if ancho is not None:
            # Ya no se fija el ancho del canvas: manda el del panel. Se guarda
            # solo como valor de arranque, hasta que llegue el primer <Configure>.
            self.ancho = ancho
        if alto is not None:
            self.alto = alto
            self.canvas.configure(height=alto)
        if max_puntos is not None:
            self.max_puntos = max_puntos

    def _cancelar_animacion(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def _pintar_valor(self, valor):
        try:
            if self.lbl_actual.winfo_exists():
                self.lbl_actual.configure(text=f"{valor:.0f}{self.unidad}")
        except Exception:
            pass

    def agregar_valor(self, valor):
        if valor is None:
            return
        valor = float(valor)
        self.valores.append(valor)
        # Se guarda UN punto más de los que se dibujan: mientras la serie se
        # desliza hacia la izquierda, ese punto extra es el que tapa el hueco
        # que si no quedaría en el borde izquierdo del canvas.
        tope = self.max_puntos + 1
        if len(self.valores) > tope:
            self.valores = self.valores[-tope:]

        self._cancelar_animacion()
        try:
            if self.lbl_extremos.winfo_exists():
                self.lbl_extremos.configure(
                    text=t("spark_extremos", minimo=f"{min(self.valores):.0f}",
                           maximo=f"{max(self.valores):.0f}", unidad=self.unidad)
                    if len(self.valores) > 3 else "")
        except Exception:
            pass

        if not ANIMAR_BARRAS or len(self.valores) < 3:
            self._t = 1.0
            self._pintar_valor(valor)
            self._dibujar()
            return

        anterior = self.valores[-2]
        pasos = max(1, self.DURACION_MS // self.PASO_MS)

        def paso(i):
            self._anim_id = None
            # El usuario pudo cambiar de pantalla a media animación: la
            # gráfica ya no existe y tocarla reventaría.
            if not self.winfo_exists():
                return
            avance = i / pasos
            self._t = 1 - (1 - avance) ** 3      # ease-out cúbico, como _ValorAnimado
            self._pintar_valor(anterior + (valor - anterior) * self._t)
            self._dibujar()
            if i < pasos:
                self._anim_id = self.after(self.PASO_MS, paso, i + 1)

        self._t = 0.0
        paso(1)

    def _dibujar(self):
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        ancho, alto = self.ancho, self.alto
        if ancho <= 10:
            return
        tope, piso = self.MARGEN, alto - self.MARGEN

        # Rejilla de fondo: tres guías para poder leer la altura de un
        # vistazo, más la línea de base. Antes no había ninguna referencia y
        # una línea plana no decía nada.
        for frac in (0.25, 0.5, 0.75):
            y = piso - (piso - tope) * frac
            self.canvas.create_line(0, y, ancho, y, fill=T.borde, dash=(2, 4))
        self.canvas.create_line(0, piso, ancho, piso, fill=T.pista)

        if len(self.valores) < 2:
            # Sin datos la gráfica quedaba como un recuadro vacío sin ninguna
            # explicación — pasa siempre en los equipos que no reportan
            # temperatura de CPU, que son muchos. Mejor decirlo.
            self.canvas.create_text(ancho / 2, alto / 2, text=t("spark_sin_datos"),
                                     fill=T.texto3, font=(T.familia, 10))
            return
        maximo = self.maximo if self.maximo else max(max(self.valores), 1)
        n = len(self.valores)
        paso_x = ancho / max(self.max_puntos - 1, 1)
        desplaz = (1.0 - self._t) * paso_x
        offset_x = ancho - (n - 1) * paso_x + desplaz

        valores = list(self.valores)
        if self._t < 1.0:
            valores[-1] = valores[-2] + (valores[-1] - valores[-2]) * self._t

        puntos = []
        for i, v in enumerate(valores):
            x = offset_x + i * paso_x
            y = piso - (min(max(v, 0), maximo) / maximo) * (piso - tope)
            puntos.append((x, y))

        # Degradado bajo la línea, en franjas horizontales. Un Canvas de
        # Tkinter no tiene transparencia, así que cada franja se pinta con el
        # tono ya mezclado contra el fondo del panel: mucho más denso arriba
        # que abajo. El "stipple" de antes daba un bloque plano y granulado.
        for b in range(self.BANDAS):
            y0 = tope + (piso - tope) * b / self.BANDAS
            y1 = tope + (piso - tope) * (b + 1) / self.BANDAS
            recorte = [(x, min(max(y, y0), y1)) for x, y in puntos]
            if all(abs(y - y1) < 0.01 for _, y in recorte):
                continue                       # franja entera por encima de la línea
            plano = [puntos[0][0], y1]
            for x, y in recorte:
                plano.extend((x, y))
            plano.extend((puntos[-1][0], y1))
            intensidad = 0.42 * (1 - b / self.BANDAS) + 0.05
            self.canvas.create_polygon(*plano, outline="",
                                        fill=mezclar_color(COLOR_BG_PANEL, self.tono, intensidad))

        linea = [c for p in puntos for c in p]
        self.canvas.create_line(*linea, fill=self.tono, width=2, smooth=True, capstyle="round")

        # Punto vivo en la punta, con un halo suave: marca de un vistazo
        # dónde está el "ahora" de la gráfica.
        cx, cy = puntos[-1]
        self.canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline="",
                                 fill=mezclar_color(COLOR_BG_PANEL, self.tono, 0.32))
        self.canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=self.tono, outline="")



def animar_progreso(barra, destino, estado, duracion_ms=300, paso_ms=20):
    """Lleva una CTkProgressBar hasta `destino` sin dar el tirón de .set().

    `estado` es un dict que el llamador conserva entre llamadas: ahí se
    guarda el valor que se está mostrando y el id de la animación en
    curso, para poder cancelarla si llega un destino nuevo antes de que
    la anterior termine (si no, las dos se pisan y la barra tiembla).
    """
    id_previo = estado.get("id")
    if id_previo is not None:
        try:
            barra.after_cancel(id_previo)
        except Exception:
            pass
        estado["id"] = None

    inicio = estado.get("valor", 0.0)
    destino = max(0.0, min(1.0, float(destino)))
    if not ANIMAR_BARRAS or abs(destino - inicio) < 0.005:
        estado["valor"] = destino
        try:
            barra.set(destino)
        except Exception:
            pass
        return

    pasos = max(1, duracion_ms // paso_ms)

    def paso(i):
        estado["id"] = None
        try:
            if not barra.winfo_exists():
                return
        except Exception:
            return
        suave = 1 - (1 - i / pasos) ** 3
        valor = inicio + (destino - inicio) * suave
        estado["valor"] = valor
        barra.set(valor)
        if i < pasos:
            estado["id"] = barra.after(paso_ms, paso, i + 1)

    paso(1)


class MedidorAguja(ctk.CTkFrame):
    """Velocímetro de aguja para la prueba de internet.

    La escala es LOGARÍTMICA a propósito. Con una escala lineal de 0 a
    1000 Mbps, una conexión de 6 Mbps —perfectamente normal en El
    Salvador— dejaría la aguja pegada al cero, sin poder distinguir 2 de
    8. En logarítmica cada multiplicación por diez ocupa el mismo tramo,
    así que se lee igual de bien una conexión lenta que una de fibra.
    """

    ANCHO = 290
    ALTO = 208
    INICIO = 190          # grados; 0 = las 3 en punto, sentido antihorario
    BARRIDO = 200         # recorrido total de la aguja
    TOPE = 1000.0         # Mbps al final de la escala
    DURACION_MS = 260
    PASO_MS = 20
    # El "0" no lleva rotulo: el arranque del arco ya se entiende solo, y
    # puesto ahi chocaba con el "1", que queda a un palmo en escala log.
    MARCAS = ((0, None), (1, "1"), (5, None), (10, "10"), (50, None),
              (100, "100"), (500, None), (1000, "1000"))

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel, **kwargs)
        self.canvas = tk.Canvas(self, width=self.ANCHO, height=self.ALTO,
                                 bg=COLOR_BG_PANEL, highlightthickness=0)
        self.canvas.pack(padx=6, pady=(6, 2))
        self._valor = 0.0
        self._tono = COLOR_ACCENT
        self._texto = "—"
        self._anim_id = None
        self._cx = self.ANCHO / 2
        # El eje de la aguja va arriba del centro del recuadro a proposito:
        # asi queda sitio LIBRE debajo para el numero grande. En la primera
        # version el numero iba dentro del arco y se le montaban encima la
        # aguja y el rotulo del "100".
        self._cy = self.ALTO - 80
        self._radio = 100
        self._dibujar()

    # -- geometría ---------------------------------------------------------
    def _fraccion(self, mbps):
        v = max(0.0, min(float(mbps), self.TOPE))
        return math.log10(1 + v) / math.log10(1 + self.TOPE)

    def _punto(self, fraccion, radio):
        grados = self.INICIO - self.BARRIDO * fraccion
        rad = math.radians(grados)
        return (self._cx + radio * math.cos(rad),
                self._cy - radio * math.sin(rad))

    # -- API ---------------------------------------------------------------
    def _cancelar(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def set_tono(self, tono):
        self._tono = tono
        self._dibujar()

    def set_texto(self, texto):
        """Cambia solo el rótulo del centro, sin tocar la aguja."""
        self._texto = texto
        self._dibujar()

    def set_valor(self, mbps, texto=None):
        destino = max(0.0, float(mbps or 0.0))
        self._texto = texto if texto is not None else f"{destino:.1f}"
        self._cancelar()
        if not ANIMAR_BARRAS:
            self._valor = destino
            self._dibujar()
            return
        inicio = self._valor
        pasos = max(1, self.DURACION_MS // self.PASO_MS)

        def paso(i):
            self._anim_id = None
            if not self.winfo_exists():
                return
            suave = 1 - (1 - i / pasos) ** 3
            self._valor = inicio + (destino - inicio) * suave
            self._dibujar()
            if i < pasos:
                self._anim_id = self.after(self.PASO_MS, paso, i + 1)

        paso(1)

    # -- dibujo ------------------------------------------------------------
    def _dibujar(self):
        if not self.canvas.winfo_exists():
            return
        c = self.canvas
        c.delete("all")
        caja = (self._cx - self._radio, self._cy - self._radio,
                self._cx + self._radio, self._cy + self._radio)

        c.create_arc(*caja, start=self.INICIO, extent=-self.BARRIDO, style="arc",
                     outline=T.pista, width=13)
        f = self._fraccion(self._valor)
        if f > 0.003:
            c.create_arc(*caja, start=self.INICIO, extent=-self.BARRIDO * f, style="arc",
                         outline=self._tono, width=13)

        for valor, etiqueta in self.MARCAS:
            fm = self._fraccion(valor)
            largo = 9 if etiqueta else 5
            x1, y1 = self._punto(fm, self._radio - 11)
            x2, y2 = self._punto(fm, self._radio - 11 - largo)
            c.create_line(x1, y1, x2, y2, fill=T.texto3, width=2)
            if etiqueta:
                ex, ey = self._punto(fm, self._radio - 30)
                c.create_text(ex, ey, text=etiqueta, fill=T.texto3,
                              font=(T.familia, 8))

        ax, ay = self._punto(f, self._radio - 24)
        c.create_line(self._cx, self._cy, ax, ay, fill=self._tono, width=3,
                      capstyle="round")
        c.create_oval(self._cx - 6, self._cy - 6, self._cx + 6, self._cy + 6,
                      fill=self._tono, outline=COLOR_BG_PANEL, width=2)

        c.create_text(self._cx, self._cy + 44, text=self._texto, fill=T.texto,
                      font=(T.familia_num, 27, "bold"))
        c.create_text(self._cx, self._cy + 68, text="Mbps", fill=T.texto3,
                      font=(T.familia, 10))


class TarjetaMedicion(ctk.CTkFrame):
    """Una de las tres cifras del resultado: latencia, bajada o subida.

    El número no aparece de golpe: sube desde cero, así que se nota que
    acaba de llegar un dato nuevo aunque no estés mirando esa esquina.
    """

    DURACION_MS = 520
    PASO_MS = 25

    def __init__(self, master, icono, titulo, unidad, tono, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel, **kwargs)
        self.unidad = unidad
        self.tono = tono
        self._anim_id = None
        ctk.CTkLabel(self, text=f"{icono}  {titulo}", font=fuente(size=11),
                     text_color=T.texto2).pack(pady=(10, 1))
        self.lbl_valor = ctk.CTkLabel(self, text="—", font=fuente(size=21, weight="bold"),
                                       text_color=T.texto3)
        self.lbl_valor.pack()
        ctk.CTkLabel(self, text=unidad, font=fuente(size=10),
                     text_color=T.texto3).pack(pady=(0, 10))

    def _cancelar(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def limpiar(self):
        self._cancelar()
        if self.lbl_valor.winfo_exists():
            self.lbl_valor.configure(text="—", text_color=T.texto3)

    def set_valor(self, valor, decimales=2):
        self._cancelar()
        if valor is None:
            self.limpiar()
            return
        destino = float(valor)
        if not ANIMAR_BARRAS:
            self.lbl_valor.configure(text=f"{destino:.{decimales}f}", text_color=self.tono)
            return
        pasos = max(1, self.DURACION_MS // self.PASO_MS)

        def paso(i):
            self._anim_id = None
            if not self.winfo_exists():
                return
            suave = 1 - (1 - i / pasos) ** 3
            self.lbl_valor.configure(text=f"{destino * suave:.{decimales}f}",
                                     text_color=self.tono)
            if i < pasos:
                self._anim_id = self.after(self.PASO_MS, paso, i + 1)
            else:
                self.lbl_valor.configure(text=f"{destino:.{decimales}f}")

        paso(1)


def _tooltip_ctk(widget, texto):
    """Globo de ayuda para un widget de customtkinter.

    El widget flotante ya tenía uno, pero vivía dentro de widget.py y
    trabajaba con tkinter plano. Este es el equivalente para el panel
    principal: hace falta porque los botones de icono de la consola (⧉ 🗑 💾)
    no tienen sitio para una etiqueta al lado, y un icono sin explicación es
    un icono que nadie pulsa.
    """
    estado = {"win": None}

    def mostrar(_e=None):
        if estado["win"] is not None or not widget.winfo_exists():
            return
        ventana = tk.Toplevel(widget)
        ventana.overrideredirect(True)
        ventana.attributes("-topmost", True)
        tk.Label(ventana, text=texto, bg="#0b0d12", fg="#e6edf3",
                 font=("Segoe UI", 9), padx=8, pady=3,
                 highlightbackground="#2a2f3a", highlightthickness=1).pack()
        ventana.update_idletasks()
        # Se coloca debajo del botón, pero sin salirse por la derecha de la
        # pantalla: los botones de la consola están pegados al borde
        # derecho del panel y el globo se cortaba.
        x = widget.winfo_rootx()
        x = min(x, widget.winfo_screenwidth() - ventana.winfo_width() - 8)
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        ventana.geometry(f"+{max(0, x)}+{y}")
        estado["win"] = ventana

    def ocultar(_e=None):
        if estado["win"] is not None:
            try:
                estado["win"].destroy()
            except Exception:
                pass
            estado["win"] = None

    widget.bind("<Enter>", mostrar)
    widget.bind("<Leave>", ocultar)
    # Al destruirse el botón (cambio de pantalla) el globo es una ventana
    # aparte y se quedaría flotando sola en el escritorio — el mismo fallo
    # que ya se había corregido en el widget flotante.
    widget.bind("<Destroy>", ocultar)
    return estado


class _ConsolaBase(ctk.CTkFrame):
    """
    El motor compartido de las dos consolas de la app: la Consola de
    Desarrollador (Edición Administrador) y el Panel de comandos oculto
    (Edición Cliente).

    Antes eran dos clases separadas que hacían casi lo mismo, y eso se
    notaba: a una le habían puesto el placeholder traducido y a la otra no,
    y el botón de la del cliente decía "Enviar" escrito a mano en el
    código, así que en la build en inglés salía en español. Un arreglo en
    una no llegaba nunca a la otra. Ahora el comportamiento está en un solo
    sitio y las subclases solo eligen color y título.

    Lo que aporta sobre la versión anterior, que era un cuadro de texto de
    un solo color con una caja de escribir debajo:

      * COLOR POR TIPO DE LÍNEA. Antes todo salía del mismo verde: un
        "Papelera vaciada" y un "No se pudo vaciar la papelera" se veían
        exactamente igual y había que leer la frase entera para saber cuál
        de los dos era.
      * HORA en cada línea. Sin ella no se sabía si lo que estabas leyendo
        acababa de pasar o llevaba diez minutos ahí.
      * HISTORIAL con ↑ y ↓, que es lo primero que uno intenta en una
        consola y aquí no hacía nada.
      * COMPLETAR con Tab.
      * FICHAS CLICABLES con los comandos más usados: antes había que saber
        que existía /help para descubrir que existía algo.
      * TOPE DE LÍNEAS. El cuadro crecía sin límite; con el autopiloto
        registrando, una sesión larga acaba con miles de líneas dentro, y
        un widget de texto de Tk con miles de líneas se repinta lento.
      * COPIAR, LIMPIAR y GUARDAR el registro a un archivo.
    """

    MAX_LINEAS = 400          # tope del buffer visible
    LINEAS_A_RECORTAR = 120   # cuánto se tira de golpe al llegar al tope
    MAX_HISTORIAL = 60        # comandos que recuerda ↑/↓

    # Un color por tipo de línea. La clave es el `tipo` que se le pasa a
    # imprimir(); si llega uno que no está aquí, se usa "info", así que una
    # llamada antigua de una sola cadena sigue funcionando igual.
    TONOS = {
        "orden":  "#8ab4ff",   # el eco de lo que escribió el usuario
        "ok":     "#5ee08a",
        "error":  "#ff7b72",
        "aviso":  "#f0c454",
        "info":   "#c9d1d9",
        "dim":    "#6b7280",
        "titulo": "#e6edf3",
    }
    FONDO_CAJA = "#0b0d12"
    COLOR_HORA = "#4d5461"

    # Fichas de acceso rápido. Son los que se usan de verdad; el resto
    # sigue estando en /help.
    FICHAS = ("/ram", "/temporales", "/papelera", "/dns", "/rapido",
              "/estado", "/limpiar", "/help")

    def __init__(self, master, on_comando=None, acento="#5ee08a", titulo="", **kwargs):
        super().__init__(master, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel, **kwargs)
        self.on_comando = on_comando
        self.acento = acento
        self._historial = []
        self._pos_historial = None      # None = escribiendo algo nuevo
        self._borrador = ""             # lo que había escrito antes de subir
        self._lineas = 0

        # ---- Encabezado: título a la izquierda, estado real a la derecha ----
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(cabecera, text=titulo, font=fuente(size=14, weight="bold"),
                     anchor="w").pack(side="left")
        ctk.CTkLabel(cabecera, text=self._texto_estado(), anchor="e",
                     font=fuente(family="Consolas", size=11),
                     text_color="gray55").pack(side="right")

        # Filito del color de la consola: separa el encabezado de la caja
        # negra sin gastar la altura de un separador de verdad.
        #
        # Es un tk.Frame y no un CTkFrame a proposito. Un CTkFrame pinta su
        # fondo dibujando un rectangulo en un lienzo interno, y con 2 px de
        # alto ahi no queda nada que dibujar: el widget medía sus 2 px
        # —comprobado— pero en la captura de pantalla no habia ni un pixel
        # del color. Un tk.Frame es un rectangulo de color y nada mas.
        tk.Frame(self, bg=acento, height=2).pack(fill="x", padx=14, pady=(6, 8))

        # ---- Fichas: los comandos a un clic ----
        if self.on_comando is not None:
            fichas = ctk.CTkFrame(self, fg_color="transparent")
            fichas.pack(fill="x", padx=14, pady=(0, 8))
            for comando in self.FICHAS:
                ctk.CTkButton(
                    fichas, text=comando, width=len(comando) * 8 + 16, height=24,
                    font=fuente(family="Consolas", size=11),
                    fg_color="#242832", hover_color=acento, text_color="#b9c2cf",
                    corner_radius=T.radio_panel,
                    command=lambda c=comando: self._lanzar_ficha(c),
                ).pack(side="left", padx=(0, 6))

        # ---- La caja negra ----
        self.textbox = ctk.CTkTextbox(
            self, font=fuente(family="Consolas", size=12),
            fg_color=self.FONDO_CAJA, text_color=self.TONOS["info"],
            border_width=0, corner_radius=T.radio_fila, wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        for nombre, color in self.TONOS.items():
            self.textbox.tag_config(nombre, foreground=color)
        self.textbox.tag_config("hora", foreground=self.COLOR_HORA)
        self.textbox.configure(state="disabled")

        # ---- Línea de escribir + botones del registro ----
        if self.on_comando is not None:
            fila = ctk.CTkFrame(self, fg_color="transparent")
            fila.pack(fill="x", padx=14, pady=(0, 4))
            ctk.CTkLabel(fila, text="❯", text_color=acento, width=14,
                         font=fuente(family="Consolas", size=15,
                                          weight="bold")).pack(side="left")
            self.entry = ctk.CTkEntry(
                fila, placeholder_text=t("consola_placeholder"),
                font=fuente(family="Consolas", size=12),
                fg_color="#11141a", border_color="#2a2f3a", border_width=1,
                corner_radius=T.radio_boton, height=34)
            self.entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
            self.entry.bind("<Return>", self._enviar)
            self.entry.bind("<Up>", self._historial_atras)
            self.entry.bind("<Down>", self._historial_adelante)
            self.entry.bind("<Tab>", self._completar)
            self.entry.bind("<Escape>", self._vaciar_entrada)
            self.entry.bind("<Control-l>", self._limpiar_atajo)

            ctk.CTkButton(fila, text=t("consola_ejecutar"), width=88, height=34,
                          corner_radius=T.radio_boton, command=self._enviar).pack(side="left")
            for etiqueta, clave, accion in (
                    ("⧉", "consola_btn_copiar", self.copiar),
                    ("🗑", "consola_btn_limpiar", self.limpiar),
                    ("💾", "consola_btn_guardar", self.guardar_log)):
                boton = ctk.CTkButton(fila, text=etiqueta, width=34, height=34,
                                      corner_radius=T.radio_boton, fg_color="#242832",
                                      hover_color="#333a47", command=accion)
                boton.pack(side="left", padx=(6, 0))
                _tooltip_ctk(boton, t(clave))

            ctk.CTkLabel(self, text=t("consola_pista"), anchor="w",
                         font=fuente(size=10), text_color="gray45").pack(
                fill="x", padx=18, pady=(0, 10))
            self.entry.focus_set()
        else:
            # Sin caja de escribir (una consola que solo registra): aun así
            # hace falta hueco abajo para que no quede pegada al borde.
            ctk.CTkFrame(self, fg_color="transparent", height=8).pack()

    # ---------- estado del encabezado ----------
    def _texto_estado(self):
        """Lo que en una consola de verdad se espera ver arriba: qué edición
        corre, con qué permisos y con qué PID. Antes había que adivinarlo —
        y "por qué no me deja" casi siempre es que no va como administrador."""
        permisos = t("consola_estado_admin") if opt.is_admin() else t("consola_estado_usuario")
        edicion = (t("consola_estado_edicion_admin") if EDICION == "admin"
                   else t("consola_estado_edicion_cliente"))
        return f"v{APP_VERSION} · {edicion} · {permisos} · PID {os.getpid()}"

    # ---------- entrada ----------
    def _lanzar_ficha(self, comando):
        self.imprimir(comando, "orden", prefijo="❯ ")
        self._recordar(comando)
        if self.on_comando is not None:
            self.on_comando(comando)

    def _enviar(self, event=None):
        texto = self.entry.get().strip()
        if not texto:
            return "break"
        self.entry.delete(0, "end")
        self._pos_historial = None
        self._borrador = ""
        self.imprimir(texto, "orden", prefijo="❯ ")
        self._recordar(texto)
        if self.on_comando is not None:
            self.on_comando(texto)
        return "break"

    def _recordar(self, texto):
        # No se guarda el mismo comando dos veces seguidas: subir con ↑
        # cinco veces para saltar cinco /ram idénticos es tiempo perdido.
        if not self._historial or self._historial[-1] != texto:
            self._historial.append(texto)
        del self._historial[:-self.MAX_HISTORIAL]

    def _historial_atras(self, event=None):
        if not self._historial:
            return "break"
        if self._pos_historial is None:
            self._borrador = self.entry.get()
            self._pos_historial = len(self._historial)
        self._pos_historial = max(0, self._pos_historial - 1)
        self._poner_en_entrada(self._historial[self._pos_historial])
        return "break"

    def _historial_adelante(self, event=None):
        if self._pos_historial is None:
            return "break"
        self._pos_historial += 1
        if self._pos_historial >= len(self._historial):
            # Pasado el final se recupera lo que estabas escribiendo antes
            # de empezar a subir, no una línea vacía.
            self._pos_historial = None
            self._poner_en_entrada(self._borrador)
        else:
            self._poner_en_entrada(self._historial[self._pos_historial])
        return "break"

    def _poner_en_entrada(self, texto):
        self.entry.delete(0, "end")
        self.entry.insert(0, texto)

    def _completar(self, event=None):
        """Tab completa el comando. Con varios candidatos completa la parte
        común y los enseña, que es lo que hace cualquier terminal."""
        escrito = self.entry.get().strip().lower()
        if not escrito:
            return "break"
        candidatos = sorted(c for c in COMANDOS_DISPONIBLES if c.startswith(escrito))
        if not candidatos:
            return "break"
        if len(candidatos) == 1:
            self._poner_en_entrada(candidatos[0])
            return "break"
        comun = os.path.commonprefix(candidatos)
        if len(comun) > len(escrito):
            self._poner_en_entrada(comun)
        self.imprimir("   ".join(candidatos), "dim")
        return "break"

    def _vaciar_entrada(self, event=None):
        self.entry.delete(0, "end")
        self._pos_historial = None
        return "break"

    def _limpiar_atajo(self, event=None):
        self.limpiar()
        return "break"

    # ---------- salida ----------
    def imprimir(self, texto, tipo="info", prefijo=""):
        """Escribe en la consola. `tipo` elige el color; si no se pasa
        ninguno queda en el neutro."""
        if not self.textbox.winfo_exists():
            return
        etiqueta = tipo if tipo in self.TONOS else "info"
        self.textbox.configure(state="normal")
        hora = datetime.now().strftime("%H:%M:%S")
        for i, linea in enumerate(str(texto).split("\n")):
            # La hora solo en la primera línea de un bloque: repetirla en
            # las veinte líneas de /help sería ruido.
            self.textbox.insert("end", (hora + "  ") if i == 0 else " " * 10, "hora")
            self.textbox.insert("end", prefijo + linea + "\n", etiqueta)
            self._lineas += 1
        self._recortar_si_hace_falta()
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def log(self, accion, comando, resultado):
        """Registro técnico de una acción (lo llama _log_dev). El comando y
        el resultado van en tonos distintos: en el bloque de tres líneas de
        antes, todo del mismo color, costaba ver dónde acababa uno."""
        if not self.textbox.winfo_exists():
            return
        self.textbox.configure(state="normal")
        self.textbox.insert("end", datetime.now().strftime("%H:%M:%S") + "  ", "hora")
        self.textbox.insert("end", f'{t("consola_accion")}: {accion}\n', "titulo")
        self.textbox.insert("end", " " * 10, "hora")
        self.textbox.insert("end", f"CMD     {comando}\n", "dim")
        self.textbox.insert("end", " " * 10, "hora")
        self.textbox.insert("end", f"RESULT  {resultado}\n\n", "ok")
        self._lineas += 4
        self._recortar_si_hace_falta()
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _recortar_si_hace_falta(self):
        """El cuadro de texto no soltaba nunca lo viejo. Se tira de las
        líneas de arriba, que son las que nadie va a volver a leer."""
        if self._lineas <= self.MAX_LINEAS:
            return
        self.textbox.delete("1.0", f"{self.LINEAS_A_RECORTAR + 1}.0")
        self._lineas -= self.LINEAS_A_RECORTAR
        self.textbox.insert("1.0", t("consola_recortado") + "\n", "dim")
        self._lineas += 1

    def texto_completo(self):
        return self.textbox.get("1.0", "end-1c")

    # ---------- botones del registro ----------
    def limpiar(self):
        if not self.textbox.winfo_exists():
            return
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        self._lineas = 0
        self.imprimir(t("consola_limpiado"), "dim")

    def copiar(self):
        contenido = self.texto_completo()
        try:
            self.clipboard_clear()
            self.clipboard_append(contenido)
            self.imprimir(t("consola_copiado", lineas=contenido.count("\n") + 1), "ok")
        except Exception as e:
            self.imprimir(t("consola_copiado_error", error=e), "error")

    def guardar_log(self):
        """Guarda el registro tal cual está, en la carpeta de datos de la app.

        No abre un diálogo de "Guardar como" a propósito: el diálogo de
        archivo de Tk bloquea el bucle de eventos, y con una consola que se
        va llenando eso significa que el registro se congela mientras
        eliges carpeta. Se guarda en un sitio conocido y se dice cuál es.
        """
        try:
            carpeta = os.path.join(prefs.carpeta_datos(), "registros")
            os.makedirs(carpeta, exist_ok=True)
            ruta = os.path.join(carpeta, "consola_"
                                + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.texto_completo())
            self.imprimir(t("consola_guardado", ruta=ruta), "ok")
        except Exception as e:
            self.imprimir(t("consola_guardado_error", error=e), "error")


class DevConsole(_ConsolaBase):
    """Consola de Desarrollador (Edición Administrador): además de aceptar
    comandos, recibe por log() el registro técnico en vivo de cada acción
    de la app."""

    def __init__(self, master, on_comando=None, **kwargs):
        super().__init__(master, on_comando=on_comando, acento="#5ee08a",
                         titulo=t("consola_titulo_dev"), **kwargs)
        self.imprimir(t("consola_lista"), "dim")


class ComandoConsole(_ConsolaBase):
    """Panel de comandos oculto (Edición Cliente): las mismas funciones que
    ya existen como botones por la app, pero escribiéndolas. No expone
    rutas ni comandos técnicos del sistema, solo el atajo."""

    def __init__(self, master, on_comando, **kwargs):
        super().__init__(master, on_comando=on_comando, acento="#5aa9ff",
                         titulo=t("consola_titulo_panel"), **kwargs)
        self.imprimir(t("consola_ayuda"), "dim")


class TechCleanApp(ctk.CTk):

    # Cada cuánto revisa el hilo principal si algún hilo de fondo dejó algo
    # pendiente. 40 ms no se nota y no cuesta prácticamente nada.
    PULSO_COLA_MS = 40

    def __init__(self):
        # El tema va ANTES de crear la ventana: customtkinter lee sus colores
        # al construir cada widget, y la propia ventana es el primero. Solo
        # se usa el nombre guardado si está en la lista cerrada de temas.
        temas.aplicar(prefs.cargar().get("tema", temas.POR_DEFECTO))
        _sincronizar_colores()
        ctk.set_widget_scaling(T.escala)
        super().__init__()
        # Las imágenes de customtkinter (los iconos) se crean contra la
        # ventana principal "por defecto" de tkinter. Con una sola ventana es
        # esta; si ya había otra viva en el proceso (el banco de pruebas lo
        # hace), los iconos acabarían en la otra y aquí no existirían.
        tk._default_root = self
        temas.resolver_fuentes(self)
        global _instancia_app
        _instancia_app = self
        self._ultimo_aviso_error = 0.0

        # ---- Puente seguro entre los hilos de fondo y la interfaz ----
        #
        # BUG corregido (el error que reportó un usuario al abrir la app):
        #
        #     RuntimeError: main thread is not in main loop
        #       File "main.py", line 1152, in worker_limpieza
        #       File "tkinter/__init__.py", in after
        #
        # En toda la app, el patrón para tocar la interfaz desde un hilo es
        # `self.after(0, ...)`. Es el patrón correcto y está bien... casi
        # siempre. Tkinter solo acepta llamadas desde otros hilos MIENTRAS
        # el hilo principal está dentro de mainloop(); si no lo está, revienta.
        #
        # Y hay dos momentos en que no lo está:
        #
        #   * AL ARRANCAR. La primera pantalla se construye dentro de
        #     __init__, o sea ANTES de que se llame a mainloop(). Los hilos
        #     que lanza esa pantalla ya están corriendo; si alguno termina
        #     rápido (schtasks devolviendo de la caché, por ejemplo) llama a
        #     after() cuando todavía no hay mainloop. Justo lo que pasó.
        #
        #   * AL CERRAR. Los hilos son daemon: siguen vivos un rato después
        #     de que la ventana se destruye.
        #
        # Había 89 llamadas así repartidas por el archivo. Arreglarlas una
        # por una es garantizar que la número 90 vuelva a estar mal, así que
        # se arregla en un solo sitio: `after` (más abajo) detecta si la
        # llamada viene de un hilo de fondo y, en ese caso, la mete en una
        # cola en vez de tocar Tk. Esta bomba la vacía el hilo principal.
        self._cola_ui = queue.Queue()
        self._pulso_cola_id = None
        # Se programa con el after DE VERDAD (el de Tk), no con el nuestro:
        # esto corre en el hilo principal, así que es seguro.
        self._pulso_cola_id = ctk.CTk.after(self, self.PULSO_COLA_MS, self._vaciar_cola_ui)

        self.title("TechClean" + (t("app_edicion_admin") if EDICION == "admin" else ""))
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass  # en Linux/Mac (o si falta el archivo) simplemente no hay ícono — no es crítico
        self.geometry("1180x780")
        self.minsize(1000, 640)

        self.modo_desarrollador = tk.BooleanVar(value=False)
        self.dev_console = None
        # El historial ahora sobrevive al cierre de la app: se guarda en
        # %APPDATA%\TechClean. Se recorta al arrancar para que el archivo no
        # engorde sin freno en la carpeta del usuario — un archivo que crece
        # solo es justo lo que esta app le critica a otros programas.
        self.reporte = rep.SessionReport(carpeta_datos=prefs.carpeta_datos())
        # Registro de cambios que se pueden deshacer. Guarda el estado
        # ANTERIOR de cada cosa que la app toca, para poder volver atrás.
        self.deshacer = desh.RegistroDeshacer(carpeta_datos=prefs.carpeta_datos())
        # Grabador de metricas de la edicion admin: vive en la app y no en la
        # pantalla, para que siga grabando aunque el tecnico se vaya a mirar
        # otra cosa mientras tanto.
        self._grabador = None
        threading.Thread(target=self.deshacer.recortar, daemon=True).start()
        threading.Thread(target=self.reporte.recortar_historial, daemon=True).start()

        self._easter_clicks = 0
        self._easter_last_click = 0
        self._dev_clicks = 0
        self._dev_last_click = 0

        # Preferencias del usuario (widget visible, perfil de energía, alerta
        # de temperatura, punto de restauración) — persisten entre sesiones.
        # ¿Ya se había usado la app en este equipo? Se mira ANTES de que nada
        # guarde preferencias: sirve para enseñar las novedades a quien
        # actualiza, y no a quien la abre por primera vez.
        self._habia_preferencias = os.path.exists(os.path.join(prefs.carpeta_datos(), "preferencias.json"))
        self.prefs = prefs.cargar()
        # En la edicion cliente el idioma NO se elige ni se guarda: es el de la
        # build. En admin se respeta lo que haya en preferencias y, si es la
        # primera vez, se pregunta.
        if EDICION == "cliente":
            idiomas.establecer_idioma(IDIOMA_BUILD)
        else:
            idiomas.establecer_idioma(self.prefs.get("idioma", IDIOMA_BUILD))
        # Modo Ligero apaga las animaciones de las barras (aqui y en el widget).
        self._aplicar_preferencia_animaciones()
        if EDICION != "cliente" and not self.prefs.get("idioma_preguntado", False):
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
            "sistema_operativo": t("comun_cargando"),
            "version_so": "", "release_so": "",
            "arquitectura": platform.machine(),
            "procesador": platform.processor() or t("comun_cargando"),
            "placa_madre": t("comun_cargando"), "bios": t("comun_cargando"),
        }
        threading.Thread(target=self._cargar_info_sistema_completa, daemon=True).start()

        # ---- Segundo plano: widget flotante, bandeja del sistema, autopiloto ----
        self.performance_widget = None
        self.autopilot = autopilot_mod.Autopilot(log_callback=self._log_dev, intervalo_seg=8,
                                                   umbral_ram=self.prefs.get("umbral_ram_auto", 85),
                                                   apps_cerrar=self._apps_a_cerrar_al_jugar,
                                                   carpetas_juegos=lambda: self._carpetas_juegos,
                                                   frenar_acaparadores=lambda: self.prefs.get(
                                                       "frenar_acaparadores", True))
        # 1.8.0: las carpetas de los juegos instalados (el Modo Juego los
        # reconoce aunque no estén a pantalla completa) se leen una vez, en
        # un hilo; y el vigía enciende el Modo Juego solo con los juegos que
        # el usuario marcó. Si no hay ninguno marcado, el vigía ni arranca.
        self._carpetas_juegos = []
        threading.Thread(target=self._leer_carpetas_juegos, daemon=True).start()
        self.vigia_juegos = autopilot_mod.VigiaJuegos(
            carpetas=lambda: list(self.prefs.get("juegos_modo_auto", [])),
            encender=lambda nombre: self.after(0, lambda: self._modo_juego_por_juego(nombre)),
            apagar=lambda: self.after(0, self._fin_modo_juego_por_juego))
        if self.prefs.get("juegos_modo_auto"):
            self.vigia_juegos.iniciar()
        # Liberación automática de RAM, con o sin Modo Juego. Cuando el Modo
        # Juego está encendido se aparta sola: el autopiloto ya libera RAM
        # excluyendo el juego.
        self.auto_ram = autopilot_mod.LimpiezaAutomaticaRAM(
            log_callback=self._log_dev,
            umbral_ram=self.prefs.get("umbral_ram_auto", 85),
            intervalo_min=self.prefs.get("auto_ram_intervalo_min", 0),
            modo_juego_activo=lambda: self.autopilot.activo)
        if self.prefs.get("auto_ram_activa", True):
            self.auto_ram.iniciar()
        # Vigilante: avisa de programas con fugas de memoria y de discos casi
        # llenos. Lee las preferencias cada vez, así los interruptores de
        # Ajustes surten efecto al momento.
        self.vigilante = autopilot_mod.Vigilante(
            log_callback=self._log_dev,
            avisar_fugas=lambda: self.prefs.get("avisar_fugas", True),
            avisar_disco=lambda: self.prefs.get("avisar_disco_lleno", True),
            umbral_disco=lambda: self.prefs.get("umbral_salud_disco", 85),
            avisos_disco_guardados=self.prefs.get("avisos_disco", {}),
            guardar_avisos_disco=self._guardar_avisos_disco,
            avisar_reinicio=lambda: self.prefs.get("avisar_reinicio", True),
            dias_reinicio=lambda: self.prefs.get("dias_reinicio", 7),
            aviso_reinicio_guardado=self.prefs.get("aviso_reinicio", {}),
            guardar_aviso_reinicio=self._guardar_aviso_reinicio,
            avisar_carga=lambda: self.prefs.get("avisar_carga_bateria", False),
            limite_carga=lambda: self.prefs.get("limite_carga_bateria", 80))
        self.vigilante.iniciar()

        self._ram_rapida_en_curso = False
        self.tray = tray_mod.TrayIcon(
            on_mostrar_panel=lambda: self.after(0, self._mostrar_ventana),
            on_toggle_widget=lambda: self.after(0, self._toggle_widget),
            on_toggle_auto=lambda: self.after(0, self._toggle_autopilot),
            on_salir=lambda: self.after(0, self._salir_definitivo),
            on_liberar_ram=lambda: self.after(0, lambda: self._liberar_ram_rapida("bandeja")),
            on_limpieza_rapida=lambda: self.after(0, self._limpieza_rapida_bandeja),
        )
        self.tray.iniciar()

        # Atajo de teclado global para liberar RAM (apagado de fábrica).
        self.atajo_ram = None
        self._estado_atajo = "apagado"        # "apagado" | "activo" | "ocupado"
        if self.prefs.get("atajo_ram_activo", False):
            self._aplicar_atajo_ram()

        # Buscador de funciones: Ctrl+K desde cualquier pantalla.
        self.bind_all("<Control-k>", lambda e: self._abrir_paleta())
        self.bind_all("<Control-K>", lambda e: self._abrir_paleta())
        self._novedades_pendientes = False

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
        self.after(1500, self._mostrar_novedades_si_toca)

    # ---------------- Layout general ----------------
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = None
        self.contenido = None          # lo crea _limpiar_contenido en cada pantalla
        self._pantalla_actual = "mostrar_dashboard"

        self._construir_sidebar()
        self.mostrar_dashboard()
        self._tick_dashboard()

    # Pantallas que se abren desde otra y comparten su entrada en la barra.
    NAV_DE_PANTALLA = {"mostrar_drivers": "mostrar_componentes", "mostrar_espacio_disco": "mostrar_optimizador"}

    def _secciones_nav(self):
        """[(clave del grupo, [(clave del texto, clave corta, icono, método)])]."""
        sistema = [("nav_inicio", "nav_corto_inicio", "inicio", "mostrar_dashboard"),
                   ("nav_componentes", "nav_corto_componentes", "componentes", "mostrar_componentes"),
                   ("nav_optimizar", "nav_corto_optimizar", "optimizar", "mostrar_optimizador"),
                   ("nav_reparar", "nav_corto_reparar", "reparar", "mostrar_reparar"),
                   ("nav_energia", "nav_corto_energia", "energia", "mostrar_bios")]
        proteccion = [("nav_seguridad", "nav_corto_seguridad", "seguridad", "mostrar_seguridad"),
                      ("nav_privacidad", "nav_corto_privacidad", "privacidad", "mostrar_privacidad")]
        herramientas = [("nav_aplicaciones", "nav_corto_aplicaciones", "aplicaciones", "mostrar_aplicaciones"),
                        ("nav_gaming", "nav_corto_gaming", "gaming", "mostrar_gaming"),
                        ("nav_segundo_plano", "nav_corto_segundo_plano", "segundo_plano", "mostrar_segundo_plano"),
                        ("nav_historial", "nav_corto_historial", "historial", "mostrar_reporte")]
        if EDICION == "admin":
            herramientas += [("nav_tecnico", "nav_corto_tecnico", "tecnico", "mostrar_tecnico"),
                             ("nav_consola_dev", "nav_corto_consola", "consola", "mostrar_consola")]
        elif self.modo_desarrollador.get():
            herramientas.append(("nav_panel_oculto", "nav_corto_panel_oculto", "desbloquear", "mostrar_panel_oculto"))
        return [("nav_grupo_sistema", sistema), ("nav_grupo_proteccion", proteccion),
                ("nav_grupo_herramientas", herramientas)]

    def _estado_admin_sidebar(self):
        """(texto del estado, color, texto del botón o None si ya es admin)."""
        admin = opt.is_admin()
        if EDICION == "admin":
            texto = t("sidebar_admin_estado_si") if admin else t("sidebar_admin_estado_no")
            boton = None if admin else t("sidebar_boton_reiniciar_admin")
        else:
            texto = t("sidebar_cliente_estado_si") if admin else t("sidebar_cliente_estado_no")
            boton = None if admin else t("sidebar_boton_desbloquear")
        return _sin_emoji(texto), COLOR_OK if admin else T.aviso, boton

    def _construir_sidebar(self):
        """Dibuja la barra lateral entera. Se vuelve a llamar al cambiar de
        tema (cambian colores, iconos y, en Telemetría, la forma) y al
        mostrar u ocultar el panel oculto (cliente).

        1.8.0: grupos con título, iconos de línea del color del tema en vez
        de emojis, y la sección en la que estás marcada (antes no había
        forma de saberlo mirando la barra). La parte de abajo (desbloquear,
        Ajustes, bandeja) queda fija aunque la lista tenga que desplazarse."""
        viejo = getattr(self, "sidebar", None)
        if viejo is not None:
            try:
                viejo.destroy()
            except Exception:
                pass
        rail = T.lateral_estilo == "rail"
        self.sidebar = ctk.CTkFrame(self, width=92 if rail else 240, corner_radius=0, fg_color=T.lateral)
        self.sidebar.grid(row=0, column=0, sticky="nswe")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)
        # Línea fina que separa la barra del contenido.
        ctk.CTkFrame(self.sidebar, width=1, corner_radius=0, fg_color=T.borde).place(
            relx=1.0, x=-1, rely=0, relheight=1)
        self._nav_botones = {}
        self._nav_marcado = None
        # Dos letras para todos los botones (normal y la del marcado), en vez
        # de una fuente nueva de Tk por botón y por cambio de pantalla.
        self._fuentes_nav = (fuente(size=14), fuente(size=14, weight="bold"))
        if rail:
            self._sidebar_rail()
        else:
            self._sidebar_lista()
        self._marcar_nav(self._pantalla_actual)

    def _boton_nav_lista(self, padre, texto, icono, metodo):
        caja = Caja(padre)
        caja.pack(fill="x", pady=1)
        indicador = ctk.CTkFrame(caja, width=3, height=20, corner_radius=2, fg_color="transparent")
        indicador.pack(side="left", padx=(0, 3))
        boton = ctk.CTkButton(caja, text=texto, anchor="w", height=38, corner_radius=T.radio_boton,
                              image=iconos.icono(icono, T.texto2), compound="left", border_width=0,
                              fg_color="transparent", hover_color=T.hover, text_color=T.texto2,
                              font=self._fuentes_nav[0], command=getattr(self, metodo))
        boton.pack(side="left", fill="x", expand=True)
        self._nav_botones[metodo] = {"boton": boton, "icono": icono, "indicador": indicador, "rail": False}

    def _sidebar_lista(self):
        cabecera = Caja(self.sidebar)
        cabecera.grid(row=0, column=0, sticky="we", padx=16, pady=(20, 12))
        ctk.CTkLabel(cabecera, text="", image=iconos.icono("marca", T.sobre_acento, 18), width=34, height=34,
                     fg_color=T.acento, corner_radius=T.radio_boton).pack(side="left")
        ctk.CTkLabel(cabecera, text="TechClean", font=fuente(size=17, weight="bold")).pack(side="left", padx=10)
        ctk.CTkLabel(cabecera, text=APP_VERSION.rsplit(".", 1)[0], font=fuente(size=11), text_color=T.texto2,
                     fg_color=T.boton2, corner_radius=10, width=34, height=20).pack(side="right")

        ctk.CTkButton(self.sidebar, text=_sin_emoji(t("sidebar_buscar")), anchor="w", height=38,
                      image=iconos.icono("buscar", T.texto2, 16), compound="left",
                      fg_color=T.entrada, hover_color=T.hover, border_width=1, border_color=T.borde,
                      text_color=T.texto2, corner_radius=T.radio_boton,
                      command=self._abrir_paleta).grid(row=1, column=0, sticky="we", padx=14, pady=(0, 8))

        lista = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        lista.grid(row=2, column=0, sticky="nswe", padx=(8, 6))
        for grupo, items in self._secciones_nav():
            ctk.CTkLabel(lista, text=t(grupo).upper(), anchor="w", text_color=T.texto3,
                         font=fuente(size=11, weight="bold")).pack(fill="x", padx=14, pady=(12, 4))
            for clave, _, icono, metodo in items:
                self._boton_nav_lista(lista, _sin_emoji(t(clave)), icono, metodo)

        pie = Caja(self.sidebar)
        pie.grid(row=3, column=0, sticky="we", padx=12, pady=(8, 14))
        estado, color, boton_admin = self._estado_admin_sidebar()
        if boton_admin:
            tarjeta = ctk.CTkFrame(pie, fg_color=T.calido, corner_radius=T.radio_fila, border_width=1,
                                   border_color=T.borde)
            tarjeta.pack(fill="x", pady=(0, 8))
            self.lbl_admin = ctk.CTkLabel(tarjeta, text=estado, text_color=color, font=fuente(size=12),
                                          wraplength=190, justify="left", anchor="w")
            self.lbl_admin.pack(fill="x", padx=12, pady=(10, 6))
            ctk.CTkButton(tarjeta, text=_sin_emoji(boton_admin), height=34, fg_color="transparent",
                          border_width=1, border_color=T.aviso, text_color=T.aviso, hover_color=T.hover,
                          image=iconos.icono("desbloquear", T.aviso, 16), compound="left",
                          command=self.solicitar_admin).pack(fill="x", padx=12, pady=(0, 12))
        else:
            self.lbl_admin = ctk.CTkLabel(pie, text=estado, text_color=color, font=fuente(size=12),
                                          anchor="w")
            self.lbl_admin.pack(fill="x", padx=8, pady=(0, 6))
        fila = Caja(pie)
        fila.pack(fill="x")
        caja = Caja(fila)
        caja.pack(side="left", fill="x", expand=True)
        self._boton_nav_lista(caja, _sin_emoji(t("nav_ajustes")), "ajustes", "mostrar_ajustes")
        boton_bandeja = ctk.CTkButton(fila, text="", width=38, height=38, image=iconos.icono("bandeja", T.texto2),
                                      fg_color="transparent", hover_color=T.hover, corner_radius=T.radio_boton,
                                      border_width=0,
                                      command=self._minimizar_a_bandeja)
        boton_bandeja.pack(side="right")
        _tooltip_ctk(boton_bandeja, _sin_emoji(t("nav_minimizar_bandeja")))
        if EDICION == "cliente" and self.modo_desarrollador.get():
            ctk.CTkLabel(pie, text=_sin_emoji(t("sidebar_panel_oculto_activo")), text_color=T.texto3,
                         font=fuente(size=10)).pack(anchor="w", padx=8, pady=(6, 0))

    def _boton_nav_rail(self, padre, texto, icono, metodo):
        boton = ctk.CTkButton(padre, text=texto, height=54, corner_radius=T.radio_boton,
                              image=iconos.icono(icono, T.texto2, 20), compound="top",
                              fg_color="transparent", hover_color=T.hover, text_color=T.texto2,
                              border_width=1, border_color=T.lateral,
                              font=fuente(size=10, weight="bold"), command=getattr(self, metodo))
        boton.pack(fill="x", pady=2)
        self._nav_botones[metodo] = {"boton": boton, "icono": icono, "indicador": None, "rail": True}
        return boton

    def _sidebar_rail(self):
        """Telemetría: una columna estrecha de iconos con su nombre corto
        debajo, para dejarle todo el ancho a los números."""
        ctk.CTkLabel(self.sidebar, text="", image=iconos.icono("marca", T.acento, 26), height=48).grid(
            row=0, column=0, pady=(16, 4))
        buscar = ctk.CTkButton(self.sidebar, text="", height=40, image=iconos.icono("buscar", T.texto2, 18),
                               fg_color=T.entrada, hover_color=T.hover, border_width=1, border_color=T.borde,
                               corner_radius=T.radio_boton, command=self._abrir_paleta)
        buscar.grid(row=1, column=0, sticky="we", padx=10, pady=(0, 6))
        _tooltip_ctk(buscar, _sin_emoji(t("sidebar_buscar")))
        lista = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        lista.grid(row=2, column=0, sticky="nswe", padx=(4, 2))
        for _, items in self._secciones_nav():
            for clave, corta, icono, metodo in items:
                _tooltip_ctk(self._boton_nav_rail(lista, t(corta), icono, metodo), _sin_emoji(t(clave)))
        pie = Caja(self.sidebar)
        pie.grid(row=3, column=0, sticky="we", padx=8, pady=(6, 12))
        estado, color, boton_admin = self._estado_admin_sidebar()
        self.lbl_admin = None
        if boton_admin:
            desbloquear = ctk.CTkButton(pie, text="", height=40, image=iconos.icono("desbloquear", T.aviso, 18),
                                        fg_color=T.calido, hover_color=T.hover, border_width=1,
                                        border_color=T.aviso, corner_radius=T.radio_boton,
                                        command=self.solicitar_admin)
            desbloquear.pack(fill="x", pady=(0, 6))
            _tooltip_ctk(desbloquear, f"{estado} · {_sin_emoji(boton_admin)}")
        _tooltip_ctk(self._boton_nav_rail(pie, t("nav_corto_ajustes"), "ajustes", "mostrar_ajustes"),
                 _sin_emoji(t("nav_ajustes")))
        bandeja = ctk.CTkButton(pie, text="", height=36, image=iconos.icono("bandeja", T.texto2, 18),
                                fg_color="transparent", hover_color=T.hover, corner_radius=T.radio_boton,
                                border_width=0,
                                command=self._minimizar_a_bandeja)
        bandeja.pack(fill="x")
        _tooltip_ctk(bandeja, _sin_emoji(t("nav_minimizar_bandeja")))

    def _marcar_nav(self, metodo):
        """Resalta en la barra la sección de la pantalla abierta."""
        metodo = self.NAV_DE_PANTALLA.get(metodo, metodo)
        botones = getattr(self, "_nav_botones", {})
        # Rendimiento: solo se tocan el botón que estaba marcado y el nuevo.
        # Reconfigurar los 15 en cada cambio de pantalla los redibujaba todos.
        # Los botones nacen sin marcar: al construir la barra, _nav_marcado
        # vuelve a None.
        marcado = getattr(self, "_nav_marcado", None)
        if marcado == metodo:
            return
        tocar = {n: botones[n] for n in (marcado, metodo) if n in botones}
        self._nav_marcado = metodo
        for nombre, b in tocar.items():
            activo = nombre == metodo
            boton = b["boton"]
            try:
                if not boton.winfo_exists():
                    continue
                color = T.nav_activo_tx if activo else T.texto2
                tam = 20 if b["rail"] else 18
                boton.configure(fg_color=T.nav_activo_bg if activo else "transparent", text_color=color,
                                image=iconos.icono(b["icono"], color, tam))
                if b["rail"]:
                    boton.configure(border_color=T.acento if activo else T.lateral)
                else:
                    boton.configure(font=self._fuentes_nav[1 if activo else 0])
                    b["indicador"].configure(fg_color=T.acento if activo else "transparent")
            except Exception:
                continue

    def _limpiar_contenido(self):
        """Deja un marco vacío para la pantalla nueva.

        Rendimiento (1.7.0): antes se destruían aquí, uno por uno, los
        widgets de la pantalla anterior, y eso era el 20-30 % de lo que
        tardaba cambiar de pantalla (hasta 0.3 s en Gaming) ANTES de empezar
        a dibujar la nueva. Ahora la pantalla vieja se oculta al instante en
        su propio marco y se destruye cuando la nueva ya está dibujada.

        Que cada pantalla estrene marco resuelve además un BUG antiguo: si
        una pantalla cambiaba el peso de alguna fila o columna (Componentes
        angostaba la columna 2), eso se quedaba para la siguiente, con
        espacio sin usar y un scroll que no tocaba. Un marco nuevo empieza
        siempre igual."""
        # Qué pantalla se está abriendo: la función que llamó aquí (todas las
        # mostrar_* empiezan llamando a _limpiar_contenido). Sirve para
        # marcarla en la barra lateral y para volver a dibujarla si se
        # cambia de tema, sin tener que tocar cada pantalla.
        llamador = sys._getframe(1).f_code.co_name
        if llamador.startswith("mostrar_"):
            self._pantalla_actual = llamador
            self._marcar_nav(llamador)
        viejo = getattr(self, "contenido", None)
        # Una Caja y no un CTkFrame: es invisible y se redibujaba con cada
        # cambio de tamaño de la pantalla entera (ver Caja).
        nuevo = Caja(self)
        nuevo.grid_columnconfigure((0, 1, 2), weight=1)
        self.contenido = nuevo
        if viejo is not None:
            viejo.grid_forget()
            # after_idle y no after(ms): un temporizador vencido se atiende
            # ANTES que el dibujado pendiente, y destruiría la vieja justo
            # cuando se quería evitar. El primer turno libre llega cuando la
            # pantalla nueva ya se construyó; desde ahí se espera un poco más.
            self.after_idle(lambda: self.after(80, lambda: self._destruir_pantalla(viejo)))
        nuevo.grid(row=0, column=1, sticky="nswe", padx=20, pady=20)
        # Cuando la pantalla nueva ya esté construida, sus textos largos se
        # ajustan al ancho real de cada caja.
        self.after_idle(lambda: self._textos_al_ancho(nuevo))

    @staticmethod
    def _textos_al_ancho(raiz):
        """BUG corregido (1.8.0, venía de antes): muchos textos largos se
        parten a un ancho fijo (wraplength=850 o 900). Con la ventana a su
        tamaño de fábrica (1180 px) o el zoom de Windows al 125 %, la caja
        es más estrecha que eso, y la etiqueta, centrada, se cortaba por los
        DOS lados: en Gaming se leía "ambia el plan..." en vez de "Cambia".

        Recorre la pantalla recién construida (antes de que se coloque) y
        apunta cada texto largo apilado en su caja en `texto_fluido`, con el
        ancho que tenía como tope.

        Rendimiento: todo el recorrido se hace con lo que Python ya sabe
        (`children`, el wraplength y el último pack que guarda
        customtkinter), sin preguntarle nada a Tk. La primera versión
        preguntaba con winfo_children/pack_info por cada widget: en Ajustes,
        unas 1.300 llamadas a Tk que se llevaban 0.8 s cuando había hilos
        trabajando (cada llamada espera su turno del GIL)."""
        pila = [raiz]
        while pila:
            w = pila.pop()
            pila.extend(getattr(w, "children", {}).values())
            if not isinstance(w, (ctk.CTkLabel, Texto)) or getattr(w, "_al_ancho", False):
                continue
            tope = int(w.cget("wraplength") or 0)
            colocacion = getattr(w, "_last_geometry_manager_call", None) or {}
            como = getattr(colocacion.get("function"), "__name__", "")
            if tope < 300 or como not in ("pack_configure", "grid_configure"):
                continue
            info = colocacion.get("kwargs", {})
            # Solo los que tienen todo el ancho de la caja para ellos: con
            # pack, los apilados (uno encima de otro); con grid, los que
            # ocupan todas las columnas (1.8.0: en Drivers, la nota del Inicio
            # rápido iba con grid y se cortaba por los dos lados).
            if como == "pack_configure" and info.get("side", "top") not in ("top", "bottom"):
                continue
            if como == "grid_configure" and (info.get("column", 0) != 0
                                             or info.get("columnspan", 1) < w.master.grid_size()[0]):
                continue
            # Sin escalar, como el ancho con el que se compara.
            padx = info.get("padx", 0)
            margen = (sum(padx) if isinstance(padx, (tuple, list)) else 2 * int(padx or 0)) + 6
            texto_fluido(w, w.master, margen, tope)

    @staticmethod
    def _destruir_pantalla(marco):
        try:
            if marco.winfo_exists():
                marco.destroy()
        except Exception:
            pass

    # ---------------- Puente entre hilos y la interfaz ----------------
    def after(self, ms, func=None, *args):
        """`after` a prueba de hilos — ver la explicación larga en __init__.

        Desde el hilo principal se comporta exactamente igual que el de
        Tkinter. Desde un hilo de fondo NO toca Tk: deja el encargo en una
        cola que el hilo principal vacía enseguida.

        Lo único que cambia es el valor devuelto: desde un hilo no hay un
        identificador que cancelar. Ningún sitio de la app guarda el
        resultado de `self.after(...)` de la ventana principal (las
        animaciones usan el `after` de SU propio widget, que no pasa por
        aquí), así que no rompe nada.
        """
        if threading.current_thread() is threading.main_thread():
            return ctk.CTk.after(self, ms, func, *args)
        if func is not None:
            self._cola_ui.put((ms, func, args))
        return None

    def _vaciar_cola_ui(self):
        """Ejecuta, ya en el hilo principal, lo que dejaron los hilos."""
        while True:
            try:
                ms, func, args = self._cola_ui.get_nowait()
            except queue.Empty:
                break
            try:
                if ms and ms > 0:
                    # Se respeta el retraso que pidió quien lo encoló: hay
                    # sitios que usan after(500, ...) o after(800, ...) a
                    # propósito, para dar tiempo a que se vea un mensaje.
                    ctk.CTk.after(self, ms, func, *args)
                else:
                    func(*args)
            except Exception:
                # Un encargo que falla no puede llevarse por delante la
                # bomba: si esta se para, la app deja de recibir CUALQUIER
                # resultado de los hilos y parece que nada funciona.
                import traceback
                self._reportar_error_interno(traceback.format_exc())
        try:
            self._pulso_cola_id = ctk.CTk.after(self, self.PULSO_COLA_MS, self._vaciar_cola_ui)
        except Exception:
            self._pulso_cola_id = None      # la ventana ya no existe: se acabó

    def solicitar_admin(self):
        opt.relaunch_as_admin()

    def _boton_ver_reporte(self, panel):
        ctk.CTkButton(panel, text=t("comun_ver_reporte"),
                      fg_color=T.boton2, hover_color=T.boton2_hover,
                      command=self.mostrar_reporte, text_color=T.texto).pack(padx=16, pady=(0, 16), anchor="w")

    # ---------------- Ventana / bandeja ----------------
    def _minimizar_a_bandeja(self):
        self.withdraw()

    def _mostrar_ventana(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        # Si arrancó escondida en la bandeja, las novedades esperaban a que
        # hubiera ventana que mirar.
        if self._novedades_pendientes:
            self._novedades_pendientes = False
            self.after(400, self._mostrar_novedades)

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
        try:
            if self.atajo_ram is not None:
                self.atajo_ram.detener()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)

    # ---------------- Acciones rápidas: bandeja y atajo de teclado (1.7.0) ----------------
    def _notificar(self, titulo, texto):
        """Notificación desde cualquier hilo de fondo. Primero por el icono
        de la bandeja (instantáneo); si no hay bandeja, la de Windows vía
        PowerShell, que tarda ~1 s: por eso NUNCA desde el hilo de Tk."""
        if self.tray.notificar(titulo, texto):
            return True
        return opt.notificar_windows(titulo, texto)

    def _pid_juego_protegido(self):
        """El juego que el Modo Juego está priorizando, para no tocarlo:
        liberarle memoria en plena partida es justo el tirón que se quiere
        evitar (el autopiloto hace lo mismo)."""
        if not self.autopilot.activo:
            return None
        return getattr(self.autopilot, "_pid_priorizado", None)

    def _liberar_ram_rapida(self, origen):
        """Liberar RAM sin abrir la ventana, desde la bandeja o el atajo de
        teclado. El resultado llega en una notificación.
        origen: "bandeja" o "atajo"."""
        if self._ram_rapida_en_curso:
            return
        self._ram_rapida_en_curso = True
        juego = self._pid_juego_protegido()
        clave_log = {"bandeja": "rapida_log_ram_bandeja", "atajo": "rapida_log_ram_atajo"}.get(
            origen, "rapida_log_ram_bandeja")

        def worker():
            try:
                r = opt.liberar_memoria(nivel="normal", exclude_pids={juego} if juego else None)
                msg = t("opt_ram_ok", antes=f"{r['uso_antes']:.0f}", despues=f"{r['uso_despues']:.0f}",
                        tamano=opt.format_bytes(r["liberado"]))
                self._notificar(t("rapida_ram_titulo"), msg)
                self._log_dev(t(clave_log), r["comando"], msg, seccion=t("seccion_automatico"),
                              exito=True, bytes_ram=r["liberado"])
            finally:
                self.after(0, lambda: setattr(self, "_ram_rapida_en_curso", False))
        threading.Thread(target=worker, daemon=True).start()

    def _limpieza_rapida_bandeja(self):
        """RAM + temporales, desde la bandeja: lo mismo que /rapido."""
        if self._ram_rapida_en_curso:
            return
        self._ram_rapida_en_curso = True
        juego = self._pid_juego_protegido()

        def worker():
            try:
                r = opt.liberar_memoria(nivel="normal", exclude_pids={juego} if juego else None)
                liberado_disco, archivos, cmd = opt.clear_temp_files()
                msg = t("rapida_limpieza_msg", ram=opt.format_bytes(r["liberado"]), archivos=archivos,
                        disco=opt.format_bytes(liberado_disco))
                self._notificar(t("rapida_limpieza_titulo"), msg)
                self._log_dev(t("rapida_log_limpieza"), f'{r["comando"]} + {cmd}', msg,
                              seccion=t("seccion_automatico"), exito=True, bytes_liberados=liberado_disco,
                              bytes_ram=r["liberado"], archivos_afectados=archivos)
            finally:
                self.after(0, lambda: setattr(self, "_ram_rapida_en_curso", False))
        threading.Thread(target=worker, daemon=True).start()

    def _aplicar_atajo_ram(self):
        """(Re)registra el atajo según las preferencias y devuelve su
        estado: "apagado", "activo" u "ocupado" (otro programa ya usa esa
        combinación: Windows solo deja registrarla a uno)."""
        if self.atajo_ram is not None:
            self.atajo_ram.detener()
            self.atajo_ram = None
        if not self.prefs.get("atajo_ram_activo", False):
            self._estado_atajo = "apagado"
        else:
            combinacion = self.prefs.get("atajo_ram_combinacion", "ctrl+alt+r")
            # Llega desde el hilo del atajo: a la interfaz, solo por after(0).
            atajo = atajos.AtajoGlobal(combinacion,
                                       lambda: self.after(0, lambda: self._liberar_ram_rapida("atajo")))
            if atajo.iniciar():
                self.atajo_ram = atajo
                self._estado_atajo = "activo"
            else:
                self._estado_atajo = "ocupado"
        self._pintar_estado_atajo()
        return self._estado_atajo

    def _pintar_estado_atajo(self):
        if not (hasattr(self, "lbl_estado_atajo") and self.lbl_estado_atajo.winfo_exists()):
            return
        combinacion = atajos.texto_combinacion(self.prefs.get("atajo_ram_combinacion", "ctrl+alt+r"))
        if self._estado_atajo == "activo":
            self.lbl_estado_atajo.configure(text=t("atajo_estado_activo", combinacion=combinacion),
                                            text_color=COLOR_OK)
        elif self._estado_atajo == "ocupado":
            self.lbl_estado_atajo.configure(text=t("atajo_estado_ocupado", combinacion=combinacion),
                                            text_color=COLOR_WARN)
        else:
            self.lbl_estado_atajo.configure(text=t("atajo_estado_apagado"), text_color=T.texto2)

    def _toggle_atajo_ram(self):
        activo = bool(self.switch_atajo_ram.get())
        self.prefs["atajo_ram_activo"] = activo
        prefs.guardar({"atajo_ram_activo": activo})
        estado = self._aplicar_atajo_ram()
        clave = {"activo": "atajo_estado_activo", "ocupado": "atajo_estado_ocupado"}.get(
            estado, "atajo_estado_apagado")
        self._log_dev(t("atajo_log"), "RegisterHotKey",
                      t(clave, combinacion=atajos.texto_combinacion(
                          self.prefs.get("atajo_ram_combinacion", "ctrl+alt+r"))),
                      seccion=t("seccion_ajustes"), exito=estado != "ocupado")

    def _cambiar_combinacion_atajo(self, texto):
        clave = next((c for c in atajos.COMBINACIONES if atajos.texto_combinacion(c) == texto), None)
        if clave is None:
            return
        self.prefs["atajo_ram_combinacion"] = clave
        prefs.guardar({"atajo_ram_combinacion": clave})
        if self.prefs.get("atajo_ram_activo", False):
            self._aplicar_atajo_ram()
        else:
            self._pintar_estado_atajo()

    # ---------------- Buscador de funciones, Ctrl+K (1.7.0) ----------------
    def _ir_pestana(self, atributo, clave, cambiar):
        """Abre una pestaña concreta de la pantalla que ya está a la vista."""
        control = getattr(self, atributo, None)
        if control is not None and control.winfo_exists():
            control.set(t(clave))
            cambiar(t(clave))

    def _paleta_ir(self, pantalla, accion=None):
        pantalla()
        if accion is not None:
            self.after(120, accion)

    def _entradas_paleta(self):
        """[(título, dónde está, palabras extra, acción)].

        Las palabras extra son sinónimos en los dos idiomas, para encontrar
        lo mismo escribiendo "ram", "memoria" o "memory". No se enseñan, así
        que no pasan por t(). Solo hay acciones que no borran nada sin
        preguntar: las que sí (vaciar la papelera...) llevan a su pantalla."""
        ir = self._paleta_ir
        pestana = self._ir_pestana
        pantallas = [
            ("nav_inicio", self.mostrar_dashboard, "inicio home dashboard salud health"),
            ("nav_componentes", self.mostrar_componentes, "hardware cpu gpu temperatura temperature"),
            ("nav_optimizar", self.mostrar_optimizador, "optimizar optimize limpiar clean"),
            ("disco_titulo", self.mostrar_espacio_disco, "espacio disco disk space storage carpetas"),
            ("drv_titulo", self.mostrar_drivers, "drivers controladores dispositivos devices"),
            ("nav_reparar", self.mostrar_reparar, "reparar repair sfc dism red network"),
            ("nav_aplicaciones", self.mostrar_aplicaciones, "apps programas desinstalar uninstall startup"),
            ("nav_privacidad", self.mostrar_privacidad, "privacidad privacy navegador browser"),
            ("nav_seguridad", self.mostrar_seguridad, "seguridad security antivirus defender malware"),
            ("nav_gaming", self.mostrar_gaming, "gaming juegos games fps"),
            ("nav_segundo_plano", self.mostrar_segundo_plano, "segundo plano background"),
            ("nav_historial", self.mostrar_reporte, "historial history registro log"),
            ("nav_energia", self.mostrar_bios, "energia power bios bateria battery"),
            ("nav_ajustes", self.mostrar_ajustes, "ajustes settings configuracion options"),
        ]
        if EDICION == "admin":
            pantallas.append(("nav_tecnico", self.mostrar_tecnico, "tecnico technician informe report"))
        entradas = [(t(clave), t("paleta_pantalla"), palabras, funcion)
                    for clave, funcion, palabras in pantallas]

        def disco(tab):
            return lambda: ir(self.mostrar_espacio_disco,
                              lambda: pestana("pestana_disco", tab, self._cambiar_pestana_disco))

        def seguridad(tab):
            return lambda: ir(self.mostrar_seguridad,
                              lambda: pestana("pestana_seguridad", tab, self._cambiar_pestana_seguridad))
        acciones = [
            ("paleta_ram", "nav_optimizar", "ram memoria memory liberar free",
             lambda: ir(self.mostrar_optimizador, self._accion_liberar_ram)),
            ("paleta_ram_profunda", "nav_optimizar", "ram memoria memory profunda deep standby",
             lambda: ir(self.mostrar_optimizador, self._accion_liberar_ram_profunda)),
            ("paleta_temporales", "nav_optimizar", "temporales temp archivos files limpiar clean",
             lambda: ir(self.mostrar_optimizador, self._accion_limpiar_temp)),
            ("paleta_dns", "nav_optimizar", "dns cache internet",
             lambda: ir(self.mostrar_optimizador, self._accion_flush_dns)),
            ("paleta_modo_juego", "nav_gaming", "modo juego game mode autopiloto", self._toggle_autopilot),
            ("paleta_widget", "nav_segundo_plano", "widget flotante overlay fps", self._toggle_widget),
            ("paleta_lag", "nav_gaming", "lag ping latencia latency jitter",
             lambda: ir(self.mostrar_gaming, self._accion_medir_lag)),
            ("paleta_wifi", "nav_gaming", "wifi wi-fi wlan senal signal canal channel router",
             lambda: ir(self.mostrar_gaming, self._accion_analizar_wifi)),
            ("paleta_velocidad_internet", "nav_componentes", "velocidad internet speedtest megas mbps",
             self._abrir_ventana_speedtest),
            ("paleta_disco", "nav_componentes", "disco disk ssd hdd nvme velocidad speed benchmark",
             lambda: ir(self.mostrar_componentes, self._accion_probar_disco)),
            ("paleta_auditoria", "nav_seguridad", "auditoria audit malware virus sospechoso suspicious",
             seguridad("seg_tab_auditoria")),
            ("paleta_extensiones", "nav_seguridad", "extensiones extensions chrome edge firefox brave navegador",
             seguridad("seg_tab_extensiones")),
            ("paleta_accesos", "disco_titulo", "accesos directos shortcuts rotos broken lnk escritorio desktop",
             disco("disco_tab_accesos")),
            ("paleta_duplicados", "disco_titulo", "duplicados duplicates copias copies", disco("disco_tab_duplicados")),
            ("paleta_limpieza_fondo", "disco_titulo", "limpieza fondo windows update cleanup liberador",
             disco("disco_tab_fondo")),
            ("paleta_archivos_grandes", "disco_titulo", "archivos grandes large files pesados",
             disco("disco_tab_archivos")),
            ("paleta_actualizar_app", "nav_ajustes", "actualizar update version nueva",
             lambda: ir(self.mostrar_ajustes, self._accion_buscar_actualizacion_manual)),
            ("paleta_novedades", "nav_ajustes", "novedades changelog whats new nuevo", self._mostrar_novedades),
        ]
        return [(t(clave), t(donde), palabras, accion) for clave, donde, palabras, accion in acciones] + entradas

    def _abrir_paleta(self):
        if getattr(self, "_paleta", None) is not None and self._paleta.winfo_exists():
            self._paleta.lift()
            return
        if self.state() in ("withdrawn", "iconic"):
            return
        v = ctk.CTkToplevel(self)
        self._paleta = v
        v.title(t("paleta_titulo"))
        ancho, alto = 600, 430
        x = self.winfo_rootx() + max(0, (self.winfo_width() - ancho) // 2)
        y = self.winfo_rooty() + 70
        v.geometry(f"{ancho}x{alto}+{x}+{y}")
        v.resizable(False, False)
        v.transient(self)
        v.grab_set()
        entrada = ctk.CTkEntry(v, placeholder_text=t("paleta_placeholder"), height=40, font=fuente(size=14))
        entrada.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(v, text=t("paleta_ayuda"), font=fuente(size=11), text_color=T.texto2).pack(
            anchor="w", padx=18, pady=(0, 6))
        lbl_vacio = ctk.CTkLabel(v, text=t("paleta_sin_resultados"), text_color=T.texto2)
        letra = fuente(size=13)
        estado = {"resultados": [], "sel": 0}
        todas = self._entradas_paleta()
        botones = []

        def ejecutar(i=None):
            i = estado["sel"] if i is None else i
            if i >= len(estado["resultados"]):
                return
            accion = estado["resultados"][i][3]
            v.destroy()
            self.after(10, accion)

        # Ocho botones fijos que se reescriben: crear y destruir botones en
        # cada tecla se notaría al escribir rápido.
        for i in range(8):
            botones.append(ctk.CTkButton(v, text="", anchor="w", height=34, font=letra, corner_radius=T.radio_boton,
                                         fg_color="transparent", hover_color=T.hover,
                                         command=lambda i=i: ejecutar(i)))

        def pintar():
            for i, b in enumerate(botones):
                if i < len(estado["resultados"]):
                    titulo, donde, _, _ = estado["resultados"][i]
                    b.configure(text=f"{titulo}    ·    {donde}",
                                fg_color=COLOR_ACCENT if i == estado["sel"] else "transparent")
                    if not b.winfo_ismapped():
                        b.pack(fill="x", padx=10, pady=1)
                else:
                    b.pack_forget()
            if estado["resultados"]:
                lbl_vacio.pack_forget()
            elif not lbl_vacio.winfo_ismapped():
                lbl_vacio.pack(pady=20)

        def refrescar(evento=None):
            if evento is not None and evento.keysym in ("Up", "Down", "Return", "Escape"):
                return
            estado["resultados"] = buscar_en_paleta(todas, entrada.get())[:8]
            estado["sel"] = 0
            pintar()

        def mover(paso):
            if estado["resultados"]:
                estado["sel"] = (estado["sel"] + paso) % len(estado["resultados"])
                pintar()
            return "break"

        entrada.bind("<KeyRelease>", refrescar)
        entrada.bind("<Down>", lambda e: mover(1))
        entrada.bind("<Up>", lambda e: mover(-1))
        entrada.bind("<Return>", lambda e: ejecutar())
        v.bind("<Escape>", lambda e: v.destroy())
        refrescar()
        # CTkToplevel se coloca y toma el foco un instante después de crearse.
        v.after(80, entrada.focus_set)

    # ---------------- Novedades de la versión (1.7.0) ----------------
    def _mostrar_novedades_si_toca(self):
        """La primera vez que se abre una versión nueva, una ventana con lo
        que cambió. Solo a quien ACTUALIZA: a quien la estrena no hay
        "novedades" que contarle."""
        if self.prefs.get("ultima_version_vista", "") == APP_VERSION:
            return
        self.prefs["ultima_version_vista"] = APP_VERSION
        prefs.guardar({"ultima_version_vista": APP_VERSION})
        if not self._habia_preferencias:
            return
        if self.state() in ("withdrawn", "iconic"):
            self._novedades_pendientes = True
            return
        self._mostrar_novedades()

    def _mostrar_novedades(self):
        v = ctk.CTkToplevel(self)
        v.title(t("nov_titulo_ventana", version=APP_VERSION))
        v.geometry("600x560")
        v.transient(self)
        ctk.CTkLabel(v, text=t("nov_titulo", version=APP_VERSION),
                     font=fuente(size=20, weight="bold")).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(v, text=t("nov_subtitulo"), font=fuente(size=12), text_color=T.texto2,
                     wraplength=550, justify="left").pack(anchor="w", padx=20, pady=(0, 8))
        marco = ctk.CTkScrollableFrame(v, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        marco.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        for clave in NOVEDADES:
            ctk.CTkLabel(marco, text=t(clave), font=fuente(size=13), wraplength=520, justify="left",
                         anchor="w").pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(v, text=t("nov_entendido"), width=160, command=v.destroy).pack(pady=(4, 14))
        v.after(100, v.lift)

    # ---------------- Dashboard ----------------
    def mostrar_dashboard(self):
        """Inicio (rediseño 1.8.0): cabecera con las dos acciones principales,
        la salud del sistema con su anillo, cuatro tarjetas de uso en vivo,
        las dos gráficas y la información del equipo."""
        self._limpiar_contenido()

        # BUG corregido (1.5.0): Inicio no tenia scroll y en un portatil de
        # 768 px lo de abajo quedaba cortado. El cuerpo va en un marco con scroll.
        self.contenido.grid_rowconfigure(0, weight=1)
        lienzo = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        lienzo.grid(row=0, column=0, columnspan=3, sticky="nswe")
        for col in range(4):
            lienzo.grid_columnconfigure(col, weight=1, uniform="metricas")

        # ---- Cabecera: título y acciones ----
        cabecera = Caja(lienzo)
        cabecera.grid(row=0, column=0, columnspan=4, sticky="we", padx=8, pady=(0, 4))
        textos = Caja(cabecera)
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(textos, text=t("dash_titulo"), font=fuente(size=26, weight="bold"), anchor="w").pack(
            fill="x")
        self.lbl_subtitulo_inicio = ctk.CTkLabel(textos, text=self._subtitulo_inicio(), text_color=T.texto2,
                                                 font=fuente(size=13), anchor="w")
        self.lbl_subtitulo_inicio.pack(fill="x")
        ctk.CTkButton(cabecera, text=_sin_emoji(t("dash_boton_optimizar_clic")), height=42,
                      font=fuente(size=14, weight="bold"),
                      image=iconos.icono("optimizar", T.sobre_acento, 16), compound="left",
                      command=self._accion_optimizacion_rapida).pack(side="right")
        boton_secundario(cabecera, _sin_emoji(t("dash_boton_vaciar_papelera")), self._accion_vaciar_papelera_user,
                         icono="papelera", height=42).pack(side="right", padx=10)
        self.lbl_resultado_user = ctk.CTkLabel(lienzo, text=t("dash_resultado_inicial"),
                                                font=fuente(size=12), text_color=T.texto2,
                                                wraplength=900, justify="left", anchor="w")
        self.lbl_resultado_user.grid(row=1, column=0, columnspan=4, sticky="we", padx=10, pady=(0, 10))

        # ---- Salud del sistema ----
        panel_salud = tarjeta(lienzo)
        panel_salud.grid(row=2, column=0, columnspan=4, sticky="we", padx=8, pady=(0, 12))
        self._panel_salud_actual = panel_salud
        fila_salud = Caja(panel_salud)
        fila_salud.pack(fill="x", padx=20, pady=18)
        # tk.Canvas no sigue el zoom de Windows como los widgets de
        # customtkinter: se escala a mano para que el anillo no quede chico.
        self._escala_salud = ctk.ScalingTracker.get_widget_scaling(self)
        lado = int(92 * self._escala_salud)
        self.canvas_salud = tk.Canvas(fila_salud, width=lado, height=lado, bg=T.panel, highlightthickness=0)
        self.canvas_salud.pack(side="left", padx=(0, 18))
        self._dibujar_anillo_salud(None, T.texto3)
        self.btn_arreglar_todo = boton_secundario(fila_salud, _sin_emoji(t("dash_arreglar_todo")),
                                                  self._accion_arreglar_todo, height=38, state="disabled")
        self.btn_arreglar_todo.pack(side="right")
        col_salud = Caja(fila_salud)
        col_salud.pack(side="left", fill="x", expand=True)
        self._col_salud_actual = col_salud
        fila_titulo = Caja(col_salud)
        fila_titulo.pack(fill="x")
        self.lbl_salud_titulo = ctk.CTkLabel(fila_titulo, text=t("dash_salud_nombre"),
                                              font=fuente(size=18, weight="bold"), anchor="w")
        self.lbl_salud_titulo.pack(side="left")
        self.lbl_salud_nivel = ctk.CTkLabel(fila_titulo, text="", font=fuente(size=12, weight="bold"),
                                            fg_color=T.fila, corner_radius=10, text_color=T.texto2, height=24)
        self.lbl_salud_nivel.pack(side="left", padx=10)
        self.lbl_salud_detalle = ctk.CTkLabel(col_salud, text=t("dash_salud_revisando"),
                                               font=fuente(size=13), text_color=T.texto2, anchor="w",
                                               wraplength=640, justify="left")
        self.lbl_salud_detalle.pack(fill="x", anchor="w", pady=(4, 0))
        # El aviso de la limpieza programada se añade aquí si está activa
        # (schtasks se consulta en un hilo: es un subproceso).
        self.lbl_limpieza_programada_info = None

        def worker_limpieza():
            if opt.limpieza_programada_activa():
                self.after(0, self._mostrar_aviso_limpieza_programada)
        threading.Thread(target=worker_limpieza, daemon=True).start()

        # ---- Uso en vivo ----
        self.gauge_ram = TarjetaMetrica(lienzo, t("dash_gauge_ram"), "memoria")
        self.gauge_ram.grid(row=3, column=0, padx=8, pady=(0, 12), sticky="nswe")
        self.gauge_cpu = TarjetaMetrica(lienzo, t("dash_gauge_cpu"), "componentes")
        self.gauge_cpu.grid(row=3, column=1, padx=8, pady=(0, 12), sticky="nswe")
        self.gauge_disco = TarjetaMetrica(lienzo, t("dash_gauge_disco"), "disco")
        self.gauge_disco.grid(row=3, column=2, padx=8, pady=(0, 12), sticky="nswe")
        self.gauge_gpu = TarjetaMetrica(lienzo, t("dash_gauge_gpu"), "gpu")
        self.gauge_gpu.grid(row=3, column=3, padx=8, pady=(0, 12), sticky="nswe")

        # ---- Últimos minutos ----
        self.spark_ram = Sparkline(lienzo, t("dash_spark_ram"))
        self.spark_ram.configurar(tono=T.acento, alto=92)
        self.spark_ram.grid(row=4, column=0, columnspan=2, padx=8, pady=(0, 12), sticky="we")
        self.spark_cpu = Sparkline(lienzo, t("dash_spark_cpu"))
        self.spark_cpu.configurar(tono=T.ok, alto=92)
        self.spark_cpu.grid(row=4, column=2, columnspan=2, padx=8, pady=(0, 12), sticky="we")

        # ---- Información del equipo ----
        info_frame = tarjeta(lienzo)
        info_frame.grid(row=5, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="we")
        ctk.CTkLabel(info_frame, text=_sin_emoji(t("dash_info_equipo_titulo")),
                     font=fuente(size=15, weight="bold"), anchor="w").pack(fill="x", padx=20, pady=(16, 6))
        info = self._system_info_cache
        texto = t("dash_info_equipo_texto", hostname=info["hostname"], usuario=info["usuario"],
                  so=info["sistema_operativo"], procesador=info["procesador"], arquitectura=info["arquitectura"])
        self.lbl_info_equipo = ctk.CTkLabel(info_frame, text=texto, justify="left", anchor="w",
                                             font=fuente(size=13), text_color=T.texto2)
        self.lbl_info_equipo.pack(fill="x", padx=20, pady=(0, 16))

        self._refrescar_gauges()
        self._calcular_salud_sistema()

    def _subtitulo_inicio(self):
        info = self._system_info_cache
        so = str(info.get("sistema_operativo") or "").split(" (")[0]
        return t("dash_subtitulo", equipo=info.get("hostname") or "?", so=so)

    def _dibujar_anillo_salud(self, puntaje, color):
        """El anillo de la salud del sistema: lleno según el puntaje y con el
        número dentro. Sin puntaje todavía, solo la pista."""
        lienzo = getattr(self, "canvas_salud", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        k = getattr(self, "_escala_salud", 1.0)
        lienzo.delete("all")
        caja = (8 * k, 8 * k, 84 * k, 84 * k)
        lienzo.create_oval(*caja, outline=T.pista, width=8 * k)
        if puntaje is not None:
            extension = -3.6 * max(0, min(100, puntaje))
            if puntaje >= 100:
                lienzo.create_oval(*caja, outline=color, width=8 * k)
            elif extension:
                lienzo.create_arc(*caja, start=90, extent=extension, style="arc", outline=color, width=8 * k)
        lienzo.create_text(46 * k, 41 * k, text="…" if puntaje is None else str(puntaje), fill=T.texto,
                           font=(T.familia_num, 22, "bold"))
        lienzo.create_text(46 * k, 62 * k, text=t("dash_de_100"), fill=T.texto2, font=(T.familia, 9))

    def _mostrar_aviso_limpieza_programada(self):
        if not (hasattr(self, "_col_salud_actual") and self._col_salud_actual.winfo_exists()):
            return
        hora_guardada = self.prefs.get("limpieza_hora", "09:00")
        # BUG corregido (1.8.0): sin wraplength, con la letra grande (Alto
        # contraste) o una ventana estrecha el aviso no cabía entre el anillo
        # y el botón y se cortaba por los dos lados. Llega desde un hilo, con
        # la pantalla ya colocada: se parte al ancho que tiene ya su columna
        # y luego lo sigue (texto_fluido). El icono va aparte (con espacios
        # delante del texto, la segunda línea quedaba más a la izquierda).
        columna = self._col_salud_actual
        ancho = int(columna.winfo_width() / ctk.ScalingTracker.get_widget_scaling(columna)) - 26
        fila = Caja(columna)
        fila.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(fila, text="", image=iconos.icono("calendario", T.texto3, 14), width=16,
                     height=18).pack(side="left", anchor="n")
        aviso = ctk.CTkLabel(fila, text=_sin_emoji(t("dash_limpieza_programada_aviso", hora=hora_guardada)),
                             font=fuente(size=12), text_color=T.texto3, justify="left", anchor="w",
                             wraplength=ancho if ancho > 40 else 640)
        aviso.pack(side="left", fill="x", expand=True, padx=(6, 0))
        texto_fluido(aviso, fila, 26)

    def _accion_arreglar_todo(self):
        self.lbl_salud_detalle.configure(text=t("dash_arreglando"))
        self.btn_arreglar_todo.configure(state="disabled")

        def worker():
            liberado_ram, procesos, cmd1 = opt.trim_process_memory()
            liberado_disco, archivos, cmd2 = opt.clear_temp_files()
            msg = t("dash_arreglo_listo", procesos=procesos, archivos=archivos,
                    total=opt.format_bytes(liberado_ram + liberado_disco))
            self._log_dev(t("log_arreglar_todo"), f"{cmd1} + {cmd2}", msg, seccion=t("seccion_inicio"),
                          exito=True, bytes_liberados=liberado_disco, bytes_ram=liberado_ram,
                          archivos_afectados=procesos + archivos)
            self.after(0, lambda: self._actualizar_label("lbl_salud_detalle", msg))
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
        if hasattr(self, "lbl_subtitulo_inicio") and self.lbl_subtitulo_inicio.winfo_exists():
            self.lbl_subtitulo_inicio.configure(text=self._subtitulo_inicio())

    def _medir_salud(self):
        """Puntaje 0-100 y sus motivos [(tipo, nivel, texto)] a partir de
        datos que ya recolectamos en otras partes de la app (RAM, disco, apps
        de inicio, temporales estimados, días encendido). Lee carpetas:
        llamar desde un hilo. La usan Inicio y el informe."""
        try:
            ram_pct = sysmon.get_ram_info()["porcentaje"]
        except Exception:
            ram_pct = None
        try:
            disco_pct = sysmon.get_disk_info()["porcentaje"]
        except Exception:
            disco_pct = None
        try:
            apps_activas = opt.contar_inicio_activo()
        except Exception:
            apps_activas = 0
        try:
            _, total_recuperable = opt.estimate_reclaimable_space()
            mb_recuperable = total_recuperable / (1024 ** 2)
        except Exception:
            mb_recuperable = 0
        dias_encendido = self.vigilante.dias_encendido()

        umbral_ram = self.prefs.get("umbral_salud_ram", 75)
        umbral_disco = self.prefs.get("umbral_salud_disco", 85)
        puntaje = 100
        motivos = []
        if ram_pct is not None:
            if ram_pct > umbral_ram + 15:
                puntaje -= 25
                motivos.append(("ram", "critico", t("dash_motivo_ram_muy_alta", pct=f"{ram_pct:.0f}")))
            elif ram_pct > umbral_ram:
                puntaje -= 10
                motivos.append(("ram", "atencion", t("dash_motivo_ram_alta", pct=f"{ram_pct:.0f}")))
        if disco_pct is not None:
            if disco_pct > umbral_disco + 10:
                puntaje -= 25
                motivos.append(("disco", "critico", t("dash_motivo_disco_casi_lleno", pct=f"{disco_pct:.0f}")))
            elif disco_pct > umbral_disco:
                puntaje -= 10
                motivos.append(("disco", "atencion", t("dash_motivo_disco_poco_espacio", pct=f"{disco_pct:.0f}")))
        # 1.8.0: se cuenta TODO lo que arranca (antes, solo la clave Run
        # de tu usuario: salían 5 donde había 15). Con el recuento
        # completo, un equipo normal tiene 10-15: los umbrales suben.
        if apps_activas > 20:
            puntaje -= 15
            motivos.append(("inicio", "atencion", t("dash_motivo_apps_inicio", n=apps_activas)))
        elif apps_activas > 12:
            puntaje -= 5
            motivos.append(("inicio", "atencion", t("dash_motivo_apps_inicio", n=apps_activas)))
        if mb_recuperable > 5000:
            puntaje -= 15
            motivos.append(("temporales", "atencion",
                            t("dash_motivo_temporales_gb", gb=f"{mb_recuperable / 1024:.1f}")))
        elif mb_recuperable > 1500:
            puntaje -= 5
            motivos.append(("temporales", "atencion", t("dash_motivo_temporales_mb", mb=f"{mb_recuperable:.0f}")))
        # 1.7.0: con el Inicio rápido de Windows, apagar no reinicia. Un
        # equipo con semanas sin reiniciar va peor aunque todo lo demás
        # esté bien, y "Arreglar todo" no lo puede arreglar: hay que
        # decírselo a la persona.
        if dias_encendido is not None:
            if dias_encendido >= 14:
                puntaje -= 10
                motivos.append(("reinicio", "atencion", t("dash_motivo_sin_reiniciar", dias=int(dias_encendido))))
            elif dias_encendido >= 7:
                puntaje -= 5
                motivos.append(("reinicio", "atencion", t("dash_motivo_sin_reiniciar", dias=int(dias_encendido))))
        puntaje = max(0, min(100, puntaje))
        if motivos:
            detalle = t("dash_salud_motivos_prefijo") + ", ".join(texto for _, _, texto in motivos) + "."
        else:
            detalle = t("dash_salud_sin_motivos")
        nivel = "bien" if puntaje >= 80 else ("atencion" if puntaje >= 50 else "critico")
        return {"puntaje": puntaje, "nivel": nivel, "motivos": motivos, "detalle": detalle}

    def _calcular_salud_sistema(self):
        """El semáforo de Inicio (_medir_salud), en un hilo aparte porque
        estimar el espacio recuperable implica leer carpetas."""
        def worker():
            salud = self._medir_salud()
            puntaje = salud["puntaje"]
            if salud["nivel"] == "bien":
                emoji, nivel, color = "🟢", t("dash_nivel_verde"), COLOR_OK
            elif salud["nivel"] == "atencion":
                emoji, nivel, color = "🟡", t("dash_nivel_amarillo"), COLOR_WARN
            else:
                emoji, nivel, color = "🔴", t("dash_nivel_rojo"), COLOR_CRIT
            detalle = salud["detalle"]
            self.after(0, lambda: self._pintar_salud_sistema(puntaje, emoji, nivel, color, detalle))

        threading.Thread(target=worker, daemon=True).start()

    def _pintar_salud_sistema(self, puntaje, emoji, nivel, color, detalle):
        if not (hasattr(self, "lbl_salud_titulo") and self.lbl_salud_titulo.winfo_exists()):
            return
        self._dibujar_anillo_salud(puntaje, color)
        self.lbl_salud_nivel.configure(text=f"  {nivel}  ", text_color=color)
        self.lbl_salud_detalle.configure(text=detalle)
        if hasattr(self, "btn_arreglar_todo") and self.btn_arreglar_todo.winfo_exists():
            # Con algo que arreglar, pasa a ser la acción principal (acento).
            if puntaje < 100:
                self.btn_arreglar_todo.configure(state="normal", fg_color=T.acento, hover_color=T.acento_hover,
                                                 text_color=T.sobre_acento)
            else:
                self.btn_arreglar_todo.configure(state="disabled", fg_color=T.boton2, text_color=T.texto3)

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
            self.gauge_disco.set_value(disco["porcentaje"], t("dash_gb_libres", gb=disco["libre_gb"]))

            # BUG corregido: esto lanzaba nvidia-smi AQUÍ, en el hilo de la
            # interfaz, cada 2 segundos: hasta 5 s de ventana congelada si
            # tardaba. Ahora se lee en un hilo y se pinta el último valor.
            gpu_pct = getattr(self, "_gpu_pct_cache", None)
            self.gauge_gpu.set_value(gpu_pct, t("dash_gpu_nvidia") if gpu_pct is not None
                                     else t("dash_gpu_no_disponible"))
            self._leer_gpu_en_fondo()

            if hasattr(self, "spark_ram") and self.spark_ram.winfo_exists():
                self.spark_ram.agregar_valor(ram["porcentaje"])
            if hasattr(self, "spark_cpu") and self.spark_cpu.winfo_exists():
                self.spark_cpu.agregar_valor(cpu["porcentaje"])
        except Exception:
            pass

    def _leer_gpu_en_fondo(self):
        """Solo guarda el número: no toca ningún widget desde el hilo."""
        if getattr(self, "_gpu_leyendo", False):
            return
        self._gpu_leyendo = True

        def worker():
            try:
                self._gpu_pct_cache = sysmon.get_gpu_utilization()
            finally:
                self._gpu_leyendo = False
        threading.Thread(target=worker, daemon=True).start()

    def _tick_dashboard(self):
        """Refresco programado en el hilo principal de Tkinter (seguro),
        en vez de un hilo aparte tocando widgets directamente.

        BUG corregido: seguía refrescando con la ventana en la bandeja,
        animando gráficas que nadie veía (unas 15 veces por segundo) y
        lanzando procesos: ~3 % de CPU constante en una app que dice
        optimizar. Oculta o minimizada, ahora solo se reprograma."""
        try:
            visible = self.state() not in ("withdrawn", "iconic")
        except Exception:
            visible = True
        if visible:
            self._refrescar_gauges()
        self.after(self._intervalo(2000), self._tick_dashboard)

    # ---------------- Piezas comunes de las pantallas (1.8.0) ----------------
    def _encabezado(self, titulo, subtitulo=None):
        """Cabecera de pantalla: título, subtítulo y, a la derecha, las
        acciones (devuelve esa Caja para que cada pantalla ponga las suyas)."""
        cabecera = Caja(self.contenido)
        cabecera.grid(row=0, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 10))
        textos = Caja(cabecera)
        textos.pack(side="left", fill="x", expand=True)
        Texto(textos, _sin_emoji(titulo), size=26, weight="bold").pack(anchor="w")
        if subtitulo:
            texto_fluido(Texto(textos, subtitulo, size=13, color=T.texto2, wraplength=640), textos, 4).pack(
                fill="x", pady=(2, 0))
        derecha = Caja(cabecera)
        derecha.pack(side="right", anchor="n", pady=(4, 0))
        return derecha

    def _cuerpo(self):
        """El resto de la pantalla, con scroll, debajo de la cabecera."""
        self.contenido.grid_rowconfigure(1, weight=1)
        cuerpo = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        cuerpo.grid(row=1, column=0, columnspan=3, sticky="nswe")
        self.cuerpo_actual = cuerpo     # para las pruebas y las capturas
        return cuerpo

    # ---------------- Componentes (monitoreo extendido de hardware) ----------------
    def mostrar_componentes(self):
        """Componentes (rediseño 1.8.0): una tarjeta por componente con sus
        datos en filas, el uso de cada núcleo en columnas, la gráfica en vivo
        de cualquier marca (antes solo NVIDIA), y la salud del disco y de la
        batería, que hasta la 1.7.0 solo tenía la edición Admin."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("comp_titulo"), t("comp_subtitulo"))
        boton_secundario(derecha, _sin_emoji(t("comp_btn_drivers")), self.mostrar_drivers, icono="componentes",
                         height=38).pack(side="right")
        boton_secundario(derecha, _sin_emoji(t("comp_btn_export_hw")), self._exportar_reporte_hardware,
                         icono="archivo", height=38).pack(side="right", padx=(0, 10))
        cuerpo = self._cuerpo()
        cuerpo.grid_columnconfigure((0, 1), weight=1, uniform="comp")
        self.lbl_comp_estado = Texto(cuerpo, "", size=12, color=T.aviso)
        self.lbl_comp_estado.grid(row=0, column=0, columnspan=2, sticky="w", padx=10)

        def celda(fila, columna, titulo, icono, span=1):
            panel, derecha_tarjeta = tarjeta_seccion(cuerpo, _sin_emoji(t(titulo)), icono)
            panel.grid(row=fila, column=columna, columnspan=span, padx=8, pady=8, sticky="nswe")
            return panel, derecha_tarjeta

        # ---- Procesador ----
        panel, derecha_tarjeta = celda(1, 0, "comp_card_cpu", "componentes")
        self.pild_cpu = pildora(derecha_tarjeta)
        self.pild_cpu.pack()
        self.lbl_cpu_nombre = Texto(panel, self._system_info_cache.get("procesador") or "", size=12,
                                    color=T.texto2, wraplength=380)
        self.lbl_cpu_nombre.pack(fill="x", padx=18, pady=(0, 8))
        self.panel_cpu = ListaDatos(panel)
        self.panel_cpu.pack(fill="x", padx=18)
        Texto(panel, t("comp_d_por_nucleo"), size=11, color=T.texto3).pack(fill="x", padx=18, pady=(10, 4))
        self.barras_nucleos = BarrasNucleos(panel)
        self.barras_nucleos.pack(fill="x", padx=18, pady=(0, 6))
        self.lbl_throttling = Texto(panel, "", size=11, color=T.aviso, wraplength=380)
        self.lbl_throttling.pack(fill="x", padx=18, pady=(0, 14))
        texto_fluido(self.lbl_throttling, panel, 36)

        # ---- Gráfica ----
        panel, derecha_tarjeta = celda(1, 1, "comp_card_gpu", "gpu")
        self.pild_gpu = pildora(derecha_tarjeta)
        self.pild_gpu.pack()
        self.lbl_gpu_nombre = Texto(panel, t("comp_leyendo"), size=12, color=T.texto2, wraplength=380)
        self.lbl_gpu_nombre.pack(fill="x", padx=18, pady=(0, 8))
        self.panel_gpu = ListaDatos(panel)
        self.panel_gpu.pack(fill="x", padx=18, pady=(0, 14))

        # ---- Memoria ----
        panel, derecha_tarjeta = celda(2, 0, "comp_card_ram", "memoria")
        self.pild_ram = pildora(derecha_tarjeta)
        self.pild_ram.pack()
        self.panel_ram = ListaDatos(panel)
        self.panel_ram.pack(fill="x", padx=18)
        self.lbl_canal_ram = Texto(panel, "", size=11, color=T.texto3, wraplength=380)
        self.lbl_canal_ram.pack(fill="x", padx=18, pady=(8, 14))
        texto_fluido(self.lbl_canal_ram, panel, 36)

        # ---- Almacenamiento (y su salud) ----
        panel, derecha_tarjeta = celda(2, 1, "comp_card_disco", "disco")
        self.pild_disco = pildora(derecha_tarjeta)
        self.pild_disco.pack()
        self.caja_particiones = Caja(panel)
        self.caja_particiones.pack(fill="x", padx=18)
        self._barras_particiones = {}
        self.panel_disco = ListaDatos(panel)
        self.panel_disco.pack(fill="x", padx=18, pady=(6, 0))
        Texto(panel, t("comp_salud_titulo"), size=13, weight="bold").pack(fill="x", padx=18, pady=(12, 4))
        self.panel_salud_disco = ListaDatos(panel)
        self.panel_salud_disco.pack(fill="x", padx=18)
        self.lbl_salud_disco = Texto(panel, t("comp_leyendo"), size=11, color=T.texto3, wraplength=380)
        self.lbl_salud_disco.pack(fill="x", padx=18, pady=(4, 0))
        texto_fluido(self.lbl_salud_disco, panel, 36)
        fila_disco = Caja(panel)
        fila_disco.pack(fill="x", padx=18, pady=(10, 14))
        boton_secundario(fila_disco, _sin_emoji(t("comp_btn_probar_disco")), self._accion_probar_disco,
                         height=32).pack(anchor="w")
        # Debajo del botón y no al lado: desde la 1.7.0 el resultado ocupa
        # varias líneas (tres velocidades y qué tipo de disco parece).
        self.lbl_resultado_disco = Texto(fila_disco, "", size=11, color=T.texto2, wraplength=380)
        self.lbl_resultado_disco.pack(fill="x", pady=(6, 0))
        texto_fluido(self.lbl_resultado_disco, fila_disco, 4)

        # ---- Red ----
        panel, _ = celda(3, 0, "comp_card_red", "globo")
        self.panel_red = ListaDatos(panel)
        self.panel_red.pack(fill="x", padx=18)
        boton_secundario(panel, _sin_emoji(t("comp_btn_speedtest")), self._abrir_ventana_speedtest,
                         height=32).pack(anchor="w", padx=18, pady=(10, 14))

        # ---- Batería (y su desgaste) ----
        panel, derecha_tarjeta = celda(3, 1, "comp_card_bateria", "energia")
        self.pild_bateria = pildora(derecha_tarjeta)
        self.pild_bateria.pack()
        self.barra_bateria = BarraFina(panel)
        self.barra_bateria.pack(fill="x", padx=18, pady=(0, 8))
        self.panel_bateria = ListaDatos(panel)
        self.panel_bateria.pack(fill="x", padx=18, pady=(0, 14))

        # ---- Equipo ----
        panel, _ = celda(4, 0, "comp_card_equipo", "monitor")
        self.panel_sistema = ListaDatos(panel)
        self.panel_sistema.pack(fill="x", padx=18, pady=(0, 14))

        # ---- Audio ----
        panel, _ = celda(4, 1, "comp_card_audio", "altavoz")
        self.panel_audio = Caja(panel)
        self.panel_audio.pack(fill="x", padx=18)
        Texto(self.panel_audio, t("comp_leyendo"), size=12, color=T.texto2).pack(anchor="w")
        fila_audio = Caja(panel)
        fila_audio.pack(fill="x", padx=18, pady=(10, 14))
        boton_secundario(fila_audio, _sin_emoji(t("comp_btn_probar_sonido")), self._accion_probar_sonido,
                         height=32).pack(side="left", padx=(0, 6))
        boton_secundario(fila_audio, _sin_emoji(t("comp_btn_probar_micro")), self._accion_abrir_prueba_microfono,
                         height=32).pack(side="left", padx=(0, 6))
        boton_secundario(fila_audio, _sin_emoji(t("comp_btn_mezclador")), self._accion_abrir_mezclador,
                         height=32).pack(side="left")

        def worker_audio():
            dispositivos = opt.listar_dispositivos_audio()
            self.after(0, lambda: self._pintar_dispositivos_audio(dispositivos))
        threading.Thread(target=worker_audio, daemon=True).start()

        # ---- Temperatura del procesador ----
        self.spark_temp_cpu = Sparkline(cuerpo, t("comp_spark_temp"), unidad="°C")
        self.spark_temp_cpu.configurar(maximo=100, tono=COLOR_OK, alto=92)
        self.spark_temp_cpu.grid(row=5, column=0, columnspan=2, padx=8, pady=8, sticky="we")

        # ---- Historial de arranques (tendencia en el tiempo) ----
        panel, _ = tarjeta_seccion(cuerpo, _sin_emoji(t("comp_arranques_titulo")), "historial",
                                   t("comp_arranques_desc"))
        panel.grid(row=6, column=0, columnspan=2, padx=8, pady=8, sticky="we")
        self.lista_arranques = Caja(panel)
        self.lista_arranques.pack(fill="x", padx=18, pady=(0, 14))
        Texto(self.lista_arranques, t("comp_leyendo"), size=12, color=T.texto2).pack(anchor="w")

        def worker_arranques():
            historial = sysmon.listar_historial_arranques(limite=15)
            self.after(0, lambda: self._pintar_historial_arranques(historial))
        threading.Thread(target=worker_arranques, daemon=True).start()

        self._cargar_salud_componentes()
        self._refrescar_componentes()
        # Sin esto, la temperatura tardaría hasta 20s en aparecer la
        # primera vez (esperando el próximo ciclo de _chequear_alerta_temperatura)
        # — se dispara una consulta inmediata al abrir la pantalla.
        self._actualizar_temperatura_cpu()

    def _cargar_salud_componentes(self):
        """La salud del disco y el desgaste de la batería. Cambian despacio:
        se leen como mucho una vez cada 10 minutos, cada una en su hilo (la
        del disco puede tardar segundos en un SATA con WMI lento; la de un
        NVMe, milisegundos), y se reutilizan."""
        ahora = time.time()
        cache = getattr(self, "_salud_comp_cache", None) or {}
        for clave, leer, pintar in (("discos", tec.salud_discos, self._pintar_salud_discos),
                                    ("baterias", tec.salud_bateria, self._pintar_salud_bateria)):
            guardado = cache.get(clave)
            if guardado and ahora - guardado[0] < 600:
                self.after(0, lambda p=pintar, d=guardado[1]: p(d))
                continue

            def worker(clave=clave, leer=leer, pintar=pintar):
                datos = leer()
                self._salud_comp_cache = dict(getattr(self, "_salud_comp_cache", None) or {})
                self._salud_comp_cache[clave] = (time.time(), datos)
                self.after(0, lambda: pintar(datos))
            threading.Thread(target=worker, daemon=True).start()

    def _pintar_salud_discos(self, discos):
        if not (hasattr(self, "panel_salud_disco") and self.panel_salud_disco.winfo_exists()):
            return
        niveles = {"bien": ("comp_salud_bien", T.ok), "atencion": ("comp_salud_atencion", T.aviso),
                   "critico": ("comp_salud_critico", T.critico)}
        if not discos:
            self.lbl_salud_disco.configure(text=t("comp_salud_no_leida"))
            return
        con_contadores = False
        apagados = 0
        varios = len(discos) > 1
        for i, d in enumerate(discos):
            clave_texto, color = niveles.get(d.get("veredicto"), niveles["bien"])
            nombre = d.get("nombre") or t("comp_nd")
            self.panel_salud_disco.poner(f"d{i}", nombre if varios else t("comp_d_estado"),
                                         t(clave_texto) if varios else f"{t(clave_texto)} · {nombre}", color)
            if isinstance(d.get("desgaste"), (int, float)):
                con_contadores = True
                self.panel_salud_disco.poner(f"v{i}", t("comp_d_vida"), f'{max(0, 100 - d["desgaste"]):.0f} %')
            if isinstance(d.get("temperatura"), (int, float)) and d["temperatura"] > 0:
                con_contadores = True
                self.panel_salud_disco.poner(f"t{i}", t("comp_d_temperatura"), f'{d["temperatura"]:.0f} °C')
            if isinstance(d.get("horas"), (int, float)):
                con_contadores = True
                self.panel_salud_disco.poner(f"h{i}", t("comp_d_horas"),
                                             t("comp_v_horas", horas=f'{int(d["horas"]):,}'.replace(",", ".")))
            if d.get("escritos_bytes"):
                self.panel_salud_disco.poner(f"w{i}", t("comp_d_escritos"),
                                             t("comp_v_tb", tb=f'{d["escritos_bytes"] / 1e12:.1f}'))
            if d.get("apagados_inseguros"):
                apagados += d["apagados_inseguros"]
                self.panel_salud_disco.poner(f"a{i}", t("comp_d_apagados"), str(d["apagados_inseguros"]))
            errores = sum(v for v in (d.get("errores_lectura"), d.get("errores_escritura"))
                          if isinstance(v, (int, float)))
            if errores:
                self.panel_salud_disco.poner(f"e{i}", t("comp_d_errores"), str(errores), T.aviso)
        motivos = [t(m) for d in discos for m in (d.get("motivos") or [])]
        if motivos:
            nota = " ".join(dict.fromkeys(motivos))
        elif not con_contadores:
            nota = t("comp_salud_sin_contadores")
        elif apagados:
            nota = t("comp_nota_apagados")
        else:
            nota = ""
        self.lbl_salud_disco.configure(text=nota)
        if not nota:
            self.lbl_salud_disco.pack_forget()

    def _pintar_salud_bateria(self, baterias):
        if not (baterias and hasattr(self, "panel_bateria") and self.panel_bateria.winfo_exists()):
            return
        b = baterias[0]
        if b.get("actual_mwh") is not None:
            color = {"bien": T.texto, "atencion": T.aviso, "critico": T.critico}.get(b.get("veredicto"), T.texto)
            self.panel_bateria.poner("capacidad", t("comp_d_capacidad"),
                                     t("comp_v_capacidad", actual=f'{b["actual_mwh"] / 1000:.1f}',
                                       diseno=f'{b["diseno_mwh"] / 1000:.1f}', pct=b["porcentaje"]), color)
        if b.get("ciclos") is not None:
            self.panel_bateria.poner("ciclos", t("comp_d_ciclos"), str(b["ciclos"]))

    def _pintar_historial_arranques(self, historial):
        if not (hasattr(self, "lista_arranques") and self.lista_arranques.winfo_exists()):
            return
        for w in self.lista_arranques.winfo_children():
            w.destroy()
        if not historial:
            texto_fluido(Texto(self.lista_arranques, t("comp_sin_arranques"), size=12, color=T.texto2,
                               wraplength=800), self.lista_arranques, 4).pack(fill="x")
            return
        lista = ListaDatos(self.lista_arranques)
        lista.pack(fill="x")
        for i, entrada in enumerate(historial[:10]):
            try:
                fecha_legible = datetime.fromisoformat(entrada["fecha"].replace("Z", "+00:00")).strftime(
                    "%d/%m/%Y %H:%M")
            except Exception:
                fecha_legible = entrada["fecha"] or "?"
            segundos = entrada["segundos"]
            color = COLOR_CRIT if segundos > 60 else (COLOR_WARN if segundos > 30 else COLOR_OK)
            lista.poner(i, fecha_legible, t("comp_segundos", segundos=f"{segundos:.0f}"), color)

    def _pintar_dispositivos_audio(self, dispositivos):
        if not (hasattr(self, "panel_audio") and self.panel_audio.winfo_exists()):
            return
        for w in self.panel_audio.winfo_children():
            w.destroy()
        if not dispositivos:
            Texto(self.panel_audio, t("comp_sin_audio"), size=12, color=T.texto2, wraplength=380).pack(anchor="w")
            return
        lista = ListaDatos(self.panel_audio)
        lista.pack(fill="x")
        for i, d in enumerate(dispositivos):
            bien = str(d.get("estado", "")).upper() == "OK"
            lista.poner(i, d["nombre"], d["estado"], T.ok if bien else T.aviso)

    def _accion_probar_sonido(self):
        """Prueba de sonido con confirmación y ayuda si no se oye nada.

        BUG corregido (lo que el usuario reportó como "el audio no
        funciona"): esto disparaba un tono y no decía absolutamente nada
        más. Si no se escuchaba, no había forma de saber si el equipo
        estaba mudo, si el volumen estaba al mínimo, si el sonido salía por
        otro dispositivo, o si la app simplemente no había hecho nada. Y
        encima el tono se generaba con winsound.Beep(), que ni siquiera
        pasa por la tarjeta de sonido (ver reproducir_sonido_prueba en
        optimizer.py): en muchos portátiles no suena nunca.

        Ahora suena un tono real por la salida de audio normal, la ventana
        pregunta si se escuchó, y si la respuesta es que no, ofrece los dos
        sitios donde está el problema el 90% de las veces: el mezclador de
        volumen y el dispositivo de salida elegido.
        """
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comp_snd_ventana"))
        dialogo.geometry("400x495")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()

        ctk.CTkLabel(dialogo, text="🔊", font=fuente(size=54)).pack(pady=(24, 2))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("comp_snd_reproduciendo"),
                                   font=fuente(size=14, weight="bold"),
                                   wraplength=340, justify="center")
        lbl_estado.pack(pady=(0, 4))
        lbl_pista = ctk.CTkLabel(dialogo, text=t("comp_snd_canales_nota"),
                                  font=fuente(size=11), text_color=T.texto2,
                                  wraplength=340, justify="center")
        lbl_pista.pack(pady=(0, 12))

        zona = ctk.CTkFrame(dialogo, fg_color="transparent")
        zona.pack(fill="both", expand=True, padx=18)

        ctk.CTkButton(dialogo, text=t("comun_cerrar"), fg_color=T.boton2, width=110,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="bottom", pady=14)

        estado = {"ocupado": False}

        def limpiar_zona():
            for hijo in zona.winfo_children():
                hijo.destroy()

        def sonar(canal="ambos"):
            """Reproduce el tono en un hilo — PlaySound sin SND_ASYNC bloquea
            hasta que termina, y hacerlo en el hilo principal congelaría la
            ventana justo mientras suena."""
            if estado["ocupado"]:
                return
            estado["ocupado"] = True
            limpiar_zona()
            lbl_estado.configure(text=t("comp_snd_reproduciendo"), text_color=T.texto)

            def worker():
                exito, comando = opt.reproducir_sonido_prueba(canal)

                def despues():
                    estado["ocupado"] = False
                    if not dialogo.winfo_exists():
                        return
                    if exito:
                        preguntar()
                    else:
                        lbl_estado.configure(text=t("comp_snd_error"), text_color=COLOR_CRIT)
                        mostrar_ayuda()
                self.after(0, despues)
                self._log_dev(t("comp_log_sonido"), comando,
                              t("comp_sonido_ok") if exito else t("comp_snd_error"),
                              seccion=t("seccion_componentes"), exito=exito)
            threading.Thread(target=worker, daemon=True).start()

        def preguntar():
            limpiar_zona()
            lbl_estado.configure(text=t("comp_snd_pregunta"), text_color=T.texto)

            def confirmado():
                limpiar_zona()
                lbl_estado.configure(text=t("comp_snd_confirmado"), text_color=COLOR_OK)
                ctk.CTkLabel(zona, text=t("comp_snd_confirmado_detalle"),
                             font=fuente(size=11), text_color=T.texto2,
                             wraplength=330, justify="center").pack(pady=(4, 10))
                fila = ctk.CTkFrame(zona, fg_color="transparent")
                fila.pack()
                ctk.CTkButton(fila, text=t("comp_snd_izq"), width=100, fg_color=T.boton2,
                              command=lambda: sonar("izquierdo"), text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=4)
                ctk.CTkButton(fila, text=t("comp_snd_der"), width=100, fg_color=T.boton2,
                              command=lambda: sonar("derecho"), text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=4)

            ctk.CTkButton(zona, text=t("comp_snd_si"), height=38, fg_color=COLOR_OK,
                          hover_color=oscurecer_color(COLOR_OK),
                          command=confirmado).pack(fill="x", pady=(4, 6))
            ctk.CTkButton(zona, text=t("comp_snd_no"), height=38, fg_color=T.boton2,
                          command=mostrar_ayuda, text_color=T.texto, hover_color=T.boton2_hover).pack(fill="x", pady=(0, 6))
            ctk.CTkButton(zona, text=t("comp_snd_repetir"), height=32, fg_color="transparent",
                          border_width=1, border_color=T.borde,
                          command=lambda: sonar("ambos")).pack(fill="x")

        def mostrar_ayuda():
            limpiar_zona()
            lbl_estado.configure(text=t("comp_snd_ayuda_titulo"), text_color=COLOR_WARN)
            ctk.CTkLabel(zona, text=t("comp_snd_ayuda_texto"), font=fuente(size=11),
                         text_color=T.texto2, wraplength=330, justify="left").pack(pady=(2, 10))
            ctk.CTkButton(zona, text=t("comp_btn_mezclador"), height=34,
                          command=self._accion_abrir_mezclador).pack(fill="x", pady=(0, 6))
            ctk.CTkButton(zona, text=t("comp_snd_abrir_sonido"), height=34, fg_color=T.boton2,
                          command=self._accion_abrir_prueba_microfono, text_color=T.texto, hover_color=T.boton2_hover).pack(fill="x", pady=(0, 6))
            ctk.CTkButton(zona, text=t("comp_snd_repetir"), height=32, fg_color="transparent",
                          border_width=1, border_color=T.borde,
                          command=lambda: sonar("ambos")).pack(fill="x")

        sonar("ambos")

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
                # Solo si rinde como un disco mecánico hace falta saber qué
                # cree Windows que es: leer las unidades tarda unos segundos.
                tipo = None
                if resultado.get("clase") == "hdd":
                    letra = (resultado.get("unidad") or "")[:1].upper()
                    tipo = next((u["tipo"] for u in opt.listar_unidades_optimizables()
                                 if u["letra"].upper() == letra), None)
                msg = texto_disco(resultado, tipo)
                exito = True
            self._log_dev(t("comp_log_disco"), t("comp_log_disco_cmd"), msg,
                          seccion=t("seccion_componentes"), exito=exito)
            self.after(0, lambda: self._actualizar_label("lbl_resultado_disco", msg))
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

    def _refrescar_componentes(self, generacion=None):
        """Bucle de refresco de la pantalla Componentes.

        BUG corregido: se detenía comprobando si panel_cpu seguía vivo, y
        eso casi siempre basta... pero deja una ventana de unos segundos.
        Al salir de Componentes el bucle viejo tiene un tic ya programado;
        si el usuario VUELVE a entrar antes de que ese tic salte, se
        encuentra un panel_cpu nuevo, da la comprobación por buena y sigue
        vivo — sumándose al bucle que acaba de arrancar la pantalla.

        Entrar y salir de Componentes un par de veces seguidas es de lo
        más normal, y cada ida y vuelta rápida dejaba un bucle más
        corriendo para siempre, cada uno lanzando consultas WMI cada pocos
        segundos. En una app cuyo trabajo es aligerar el equipo, que se
        vaya cargando sola con el uso es de lo peor que puede pasar.

        Ahora cada visita a la pantalla estrena número: los tics de una
        visita anterior se dan cuenta de que ya no les toca y se apagan.
        """
        if generacion is None:
            self._generacion_componentes = getattr(self, "_generacion_componentes", 0) + 1
            generacion = self._generacion_componentes
        elif generacion != getattr(self, "_generacion_componentes", 0):
            return                      # tic de una visita anterior: se descarta

        if not (hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists()):
            return

        def sigue_abierta():
            # Desde el hilo: dos atributos de Python, sin tocar Tk.
            return (generacion == getattr(self, "_generacion_componentes", 0)
                    and self._pantalla_actual == "mostrar_componentes")

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
                if not hasattr(self, "_gpu_info_cache") or self._gpu_info_cache.get("fuente") in (
                        "nvidia-smi", "windows"):
                    self._gpu_info_cache = sysmon.get_gpu_info()
                # BUG corregido (1.8.0): con WMI degradado lo de arriba tarda
                # segundos (hasta 8-9). Si mientras tanto el usuario salió de
                # Componentes, o salió y volvió a entrar (otra visita, con su
                # propio hilo), este ya no tiene dónde pintar: seguía con las
                # otras ocho consultas para nada. Lo vio prueba_bucles.py
                # durante el banco, con el equipo cargado.
                if not sigue_abierta():
                    return
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
                elif hasattr(self, "lbl_comp_estado") and self.lbl_comp_estado.winfo_exists():
                    self.lbl_comp_estado.configure(text=t("comp_reintentando", error=error))
                # Se pasa el número de esta visita: si para cuando salte el
                # tic ya hay una visita más nueva, este bucle se apaga solo.
                self.after(self._intervalo(3000), self._refrescar_componentes, generacion)
            self.after(0, _terminar)

        threading.Thread(target=worker, daemon=True).start()

    def _pintar_componentes(self, datos):
        if not (hasattr(self, "panel_cpu") and self.panel_cpu.winfo_exists()):
            return
        if self.lbl_comp_estado.cget("text"):
            self.lbl_comp_estado.configure(text="")

        # ---- Procesador ----
        cpu = datos["cpu"]
        # El nombre de verdad ("AMD Ryzen 7 7735HS") llega unos segundos
        # después de arrancar; hasta entonces es el de Python ("AMD64
        # Family 25 Model 68...").
        nombre_cpu = self._system_info_cache.get("procesador") or ""
        if self.lbl_cpu_nombre.cget("text") != nombre_cpu:
            self.lbl_cpu_nombre.configure(text=nombre_cpu)
        # BUG corregido (1.8.0): hasta la primera lectura (unos segundos)
        # decía "No disponible en este equipo" también en equipos que sí la
        # dan. Mientras no se ha leído, "Cargando...".
        if cpu["temperatura_c"] is not None:
            temp_cpu = f'{cpu["temperatura_c"]:.0f} °C'
        elif getattr(self, "_cpu_temp_leida", False):
            temp_cpu = t("comp_no_disponible_equipo")
        else:
            temp_cpu = t("comun_cargando")
        uso = cpu["porcentaje_total"]
        poner_pildora(self.pild_cpu, f"{uso:.0f} %", "bien" if uso < 60 else ("atencion" if uso < 85 else "critico"))
        self.panel_cpu.poner("uso", t("comp_d_uso"), f"{uso:.0f} %")
        if cpu.get("frecuencia_actual_mhz"):
            maximo = cpu.get("frecuencia_max_mhz")
            self.panel_cpu.poner("frec", t("comp_d_frecuencia"),
                                 t("comp_v_frecuencia", frec=f'{cpu["frecuencia_actual_mhz"] / 1000:.2f}',
                                   max=f"{maximo / 1000:.2f}" if maximo else t("comp_nd")))
        self.panel_cpu.poner("nucleos", t("comp_d_nucleos"),
                             t("comp_v_nucleos", fisicos=cpu["nucleos_fisicos"], logicos=cpu["nucleos_logicos"]))
        self.panel_cpu.poner("temp", t("comp_d_temperatura"), temp_cpu)
        self.barras_nucleos.poner(cpu.get("porcentaje_por_nucleo") or [])
        # Heurística de throttling térmico: CPU bajo carga significativa pero
        # corriendo muy por debajo de su frecuencia máxima — indicio (no
        # certeza absoluta, un plan de energía Silencioso también reduce el
        # clock a propósito) de que se está limitando por temperatura.
        throttling = bool(cpu.get("frecuencia_actual_mhz") and cpu.get("frecuencia_max_mhz")
                          and uso > 50 and cpu["frecuencia_actual_mhz"] < cpu["frecuencia_max_mhz"] * 0.7)
        aviso = _sin_emoji(t("comp_throttling")).strip() if throttling else ""
        if self.lbl_throttling.cget("text") != aviso:
            self.lbl_throttling.configure(text=aviso)

        if hasattr(self, "spark_temp_cpu") and self.spark_temp_cpu.winfo_exists():
            grados = cpu.get("temperatura_c")
            # La gráfica de temperatura estaba SIEMPRE en rojo, incluso a 32 °C.
            # Un CPU frío pintado de rojo alarma sin motivo; ahora el color
            # sigue la temperatura real: verde hasta 65, ámbar hasta 80, rojo
            # arriba de eso (los umbrales típicos de un portátil).
            if grados is not None:
                self.spark_temp_cpu.configurar(tono=COLOR_OK if grados < 65 else (
                    COLOR_WARN if grados < 80 else COLOR_CRIT))
            self.spark_temp_cpu.agregar_valor(grados)

        # ---- Gráfica (1.8.0: de cualquier marca) ----
        gpu = datos["gpu"]
        if self.lbl_gpu_nombre.cget("text") != gpu["nombre"]:
            self.lbl_gpu_nombre.configure(text=gpu["nombre"])
        if gpu.get("fuente") in ("windows", "nvidia-smi"):
            pct = gpu.get("porcentaje")
            poner_pildora(self.pild_gpu, f"{pct:.0f} %" if pct is not None else "…",
                          "info" if pct is None else ("bien" if pct < 60 else ("atencion" if pct < 85 else "critico")))
            self.panel_gpu.poner("uso", t("comp_d_uso"), f"{pct:.0f} %" if pct is not None else t("comun_cargando"))
            if gpu.get("vram_total_gb"):
                usada = gpu.get("vram_usada_gb")
                self.panel_gpu.poner("vram", t("comp_d_memoria_dedicada"),
                                     t("comp_v_gb_de", usado=f"{usada:.2f}" if usada is not None else "?",
                                       total=f'{gpu["vram_total_gb"]:.1f}'))
            if gpu.get("compartida_gb"):
                self.panel_gpu.poner("compartida", t("comp_d_memoria_compartida"),
                                     t("comp_v_hasta_gb", total=f'{gpu["compartida_gb"]:.1f}'))
            temp = gpu.get("temperatura_c")
            self.panel_gpu.poner("temp", t("comp_d_temperatura"),
                                 f"{temp:.0f} °C" if temp is not None else t("comp_no_disponible"))
            if gpu.get("ventilador_rpm"):
                self.panel_gpu.poner("fan", t("comp_d_ventilador"), t("comp_v_rpm", rpm=gpu["ventilador_rpm"]))
            elif gpu.get("ventilador_pct") is not None:
                self.panel_gpu.poner("fan", t("comp_d_ventilador"), f'{gpu["ventilador_pct"]:.0f} %')
            if gpu.get("otras"):
                self.panel_gpu.poner("otras", t("comp_d_otras"), ", ".join(gpu["otras"]))
        else:
            self.pild_gpu.pack_forget()
            self.panel_gpu.poner("nd", t("comp_d_uso"), t("comp_gpu_sin_vivo"), T.texto2)

        # ---- Memoria ----
        ram_sticks = datos["ram_sticks"]
        canal = None
        if ram_sticks:
            total = sum(m.get("capacidad_gb") or 0 for m in ram_sticks)
            poner_pildora(self.pild_ram, f"{total:g} GB")
            # Windows llama a veces igual a dos ranuras ("DIMM 0" y "DIMM 0"
            # en el equipo del desarrollador): entonces se numeran.
            repetidas = len({m["ranura"] for m in ram_sticks}) < len(ram_sticks)
            for i, m in enumerate(ram_sticks):
                self.panel_ram.poner(f"m{i}", t("comp_d_modulo_n", n=i + 1) if repetidas else m["ranura"],
                                     t("comp_v_modulo", capacidad=f'{m["capacidad_gb"]:g}',
                                       velocidad=m["velocidad_mhz"] or t("comp_nd"), fabricante=m["fabricante"]))
            canal = sysmon.estimar_canal_ram(ram_sticks)
            if canal:
                self.panel_ram.poner("canal", t("comp_d_canal"), t("comp_v_canal", modo=canal["modo"]))
        else:
            self.pild_ram.pack_forget()
            self.panel_ram.poner("nd", t("comp_d_modulos"), t("comp_ram_sin_detalle"), T.texto2)
        mv = datos.get("memoria_virtual")
        if mv:
            self.panel_ram.poner("virtual", t("comp_d_virtual"),
                                 t("comp_v_gb_pct", usado=mv["usado_gb"], total=mv["total_gb"],
                                   pct=f'{mv["porcentaje"]:.0f}'))
        explicacion = canal["explicacion"] if canal else ""
        if self.lbl_canal_ram.cget("text") != explicacion:
            self.lbl_canal_ram.configure(text=explicacion)

        # ---- Almacenamiento ----
        particiones = datos["particiones"]
        if particiones:
            for p in particiones:
                fila = self._barras_particiones.get(p["unidad"])
                if fila is None:
                    texto = Texto(self.caja_particiones, "", size=12)
                    texto.pack(fill="x", pady=(4, 2))
                    barra = BarraFina(self.caja_particiones)
                    barra.pack(fill="x", pady=(0, 4))
                    fila = self._barras_particiones[p["unidad"]] = (texto, barra)
                texto, barra = fila
                nuevo = t("comp_v_particion", unidad=p["unidad"], usado=p["usado_gb"], total=p["total_gb"],
                          pct=f'{p["porcentaje"]:.0f}')
                if texto.cget("text") != nuevo:
                    texto.configure(text=nuevo)
                    barra.poner(p["porcentaje"] / 100, color_uso(p["porcentaje"]))
            principal = particiones[0]
            poner_pildora(self.pild_disco, f'{principal["porcentaje"]:.0f} %',
                          "bien" if principal["porcentaje"] < 85 else "atencion")
        else:
            self.pild_disco.pack_forget()
            self.panel_disco.poner("nd", t("comp_card_disco"), t("comp_sin_unidades"), T.texto2)
        io_disco = datos["io_disco"]
        self.panel_disco.poner("lectura", t("comp_d_lectura"), t("comp_v_mbs", v=io_disco["lectura_mbps"]))
        self.panel_disco.poner("escritura", t("comp_d_escritura"), t("comp_v_mbs", v=io_disco["escritura_mbps"]))

        # ---- Red ----
        red = datos["red"]
        self.panel_red.poner("bajada", t("comp_d_bajada"), t("comp_v_mbs", v=red["bajada_mbps"]))
        self.panel_red.poner("subida", t("comp_d_subida"), t("comp_v_mbs", v=red["subida_mbps"]))

        # ---- Batería ----
        bateria = datos["bateria"]
        if bateria:
            pct = bateria["porcentaje"]
            estado = t("comp_bateria_cargando") if bateria["cargando"] else t("comp_bateria_descargando")
            poner_pildora(self.pild_bateria, f"{pct:.0f} %", "bien" if pct > 20 or bateria["cargando"] else "atencion")
            self.barra_bateria.poner(pct / 100, T.ok if pct > 20 or bateria["cargando"] else T.aviso)
            self.panel_bateria.poner("estado", t("comp_d_estado"), estado)
            if bateria["minutos_restantes"]:
                self.panel_bateria.poner("restante", t("comp_d_restante"),
                                         t("comp_v_min", minutos=bateria["minutos_restantes"]))
            else:
                self.panel_bateria.quitar("restante")
        else:
            self.pild_bateria.pack_forget()
            self.barra_bateria.pack_forget()
            self.panel_bateria.poner("nd", t("comp_d_estado"), t("comp_sin_bateria"), T.texto2)

        # ---- Equipo ----
        uptime = datos["uptime"]
        info = self._system_info_cache
        self.panel_sistema.poner("placa", t("comp_d_placa"), info.get("placa_madre", t("comp_no_disponible")))
        self.panel_sistema.poner("bios", t("comp_d_bios"), info.get("bios", t("comp_no_disponible")))
        self.panel_sistema.poner("encendido", t("comp_d_encendido"),
                                 t("comp_v_encendido", horas=int(uptime // 3600), minutos=int((uptime % 3600) // 60)))
        self.panel_sistema.poner("procesos", t("comp_d_procesos"), datos["procesos"])

    def _abrir_ventana_speedtest(self):
        """Ventana dedicada para el test de velocidad.

        Antes era solo una etiqueta apretada dentro de la tarjeta de Red;
        después pasó a una ventana con dos números y una barra. Esta versión
        muestra además la latencia, y sobre todo enseña lo que está pasando
        MIENTRAS pasa: la aguja se mueve con la velocidad real de cada
        instante, así que se ve enseguida si la conexión va estable o a
        tirones — algo que un solo número al final no cuenta.

        Sigue siendo una ventana aparte a propósito: así el resultado no
        depende de que la pantalla Componentes siga abierta (evita que un
        resultado tardío intente pintar sobre un widget de una visita
        anterior ya destruido).
        """
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comp_st_ventana"))
        dialogo.geometry("430x525")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()

        ctk.CTkLabel(dialogo, text=t("comp_st_titulo"),
                     font=fuente(size=19, weight="bold")).pack(pady=(18, 2))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("comp_preparando"), font=fuente(size=12),
                                   text_color=T.texto2, wraplength=380, justify="center")
        lbl_estado.pack(pady=(0, 8))

        medidor = MedidorAguja(dialogo)
        medidor.pack(pady=(0, 10))

        barra = ctk.CTkProgressBar(dialogo, width=320, height=8)
        barra.set(0)
        barra.pack(pady=(0, 14))

        fila_tarjetas = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila_tarjetas.pack(fill="x", padx=14)
        for col in range(3):
            fila_tarjetas.grid_columnconfigure(col, weight=1, uniform="resultado")
        tarj_ping = TarjetaMedicion(fila_tarjetas, "⏱", t("comp_st_latencia"),
                                     t("comp_st_unidad_ms"), COLOR_WARN)
        tarj_ping.grid(row=0, column=0, padx=4, sticky="we")
        tarj_bajada = TarjetaMedicion(fila_tarjetas, "↓", t("comp_st_bajada_titulo"),
                                       t("comp_st_unidad_mbps"), COLOR_ACCENT)
        tarj_bajada.grid(row=0, column=1, padx=4, sticky="we")
        tarj_subida = TarjetaMedicion(fila_tarjetas, "↑", t("comp_st_subida_titulo"),
                                       t("comp_st_unidad_mbps"), COLOR_OK)
        tarj_subida.grid(row=0, column=2, padx=4, sticky="we")

        ctk.CTkLabel(dialogo, text=t("comp_st_datos"), font=fuente(size=10),
                     text_color=T.texto3, wraplength=380, justify="center").pack(pady=(14, 0))

        fila_botones = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila_botones.pack(side="bottom", pady=16)
        ctk.CTkButton(fila_botones, text=t("comun_cerrar"), fg_color=T.boton2,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=6)
        btn_reintentar = ctk.CTkButton(fila_botones, text=t("comp_btn_reintentar"), width=110,
                                        state="disabled")
        btn_reintentar.pack(side="left", padx=6)

        refs = {"dialogo": dialogo, "estado": lbl_estado, "medidor": medidor, "barra": barra,
                "ping": tarj_ping, "bajada": tarj_bajada, "subida": tarj_subida,
                "btn_reintentar": btn_reintentar, "barra_estado": {"valor": 0.0, "id": None}}

        btn_reintentar.configure(command=lambda: self._ejecutar_speedtest(refs))
        self._ejecutar_speedtest(refs)

    def _ejecutar_speedtest(self, refs):
        dialogo = refs["dialogo"]
        if not dialogo.winfo_exists():
            return

        # Límite total. Antes eran 35 s, que no alcanzaban ni para una prueba
        # normal en una conexión modesta: el aviso de "tardó demasiado" salía
        # sobre pruebas que iban perfectamente.
        LIMITE_S = 90

        # opt.test_velocidad_internet avisa la fase con un CÓDIGO estable, no
        # con texto: antes este mapa estaba indexado por las frases en español
        # que producía el optimizador, así que en cuanto ese texto cambiara de
        # idioma el .get() habría caído siempre en el 0.5 por defecto y la
        # barra de progreso habría dejado de avanzar.
        FASES = {
            "conexion": (t("comp_st_fase_conexion"), 0.10),
            "bajada": (t("comp_st_fase_bajada"), 0.35),
            "subida": (t("comp_st_fase_subida"), 0.72),
            "listo": (t("comp_st_fase_listo"), 1.0),
        }
        TONO_FASE = {"bajada": COLOR_ACCENT, "subida": COLOR_OK}

        # BUG corregido: cada ejecución lleva su propio número. Si el usuario
        # pulsaba "Reintentar" mientras un intento anterior seguía vivo, el
        # vigilante de aquel intento seguía programado y acababa pintando
        # "tardó demasiado" encima del intento nuevo, que iba perfectamente.
        self._speedtest_gen = getattr(self, "_speedtest_gen", 0) + 1
        gen = self._speedtest_gen
        marcha = {"terminado": False}

        def vigente():
            return gen == getattr(self, "_speedtest_gen", 0) and dialogo.winfo_exists()

        refs["btn_reintentar"].configure(state="disabled")
        for tarjeta in (refs["ping"], refs["bajada"], refs["subida"]):
            tarjeta.limpiar()
        refs["estado"].configure(text=t("comp_preparando"), text_color=T.texto2)
        refs["medidor"].set_tono(COLOR_ACCENT)
        refs["medidor"].set_valor(0, texto="—")
        refs["barra_estado"] = {"valor": 0.0, "id": None}
        refs["barra"].set(0)

        suavizado = {"mbps": 0.0}

        def progreso(codigo):
            # BUG corregido: esto se llamaba desde el hilo de la prueba y
            # consultaba winfo_exists() ahí mismo. Tkinter NO es seguro fuera
            # del hilo principal; toda comprobación y todo cambio de interfaz
            # tiene que pasar por after(0, ...), como ahora.
            def aplicar():
                if not vigente():
                    return
                texto, avance = FASES.get(codigo, (codigo, 0.5))
                refs["estado"].configure(text=texto, text_color=T.texto2)
                animar_progreso(refs["barra"], avance, refs["barra_estado"])
                if codigo in TONO_FASE:
                    refs["medidor"].set_tono(TONO_FASE[codigo])
                    suavizado["mbps"] = 0.0
                    refs["medidor"].set_valor(0, texto="0.0")
            self.after(0, aplicar)

        def muestra(fase, mbps):
            def aplicar():
                if not vigente():
                    return
                # Media móvil: las muestras instantáneas saltan mucho (la red
                # entrega a ráfagas) y la aguja daría tirones sin esto.
                suavizado["mbps"] = suavizado["mbps"] * 0.55 + float(mbps) * 0.45
                refs["medidor"].set_valor(suavizado["mbps"])
            self.after(0, aplicar)

        def worker():
            resultado = opt.test_velocidad_internet(callback_progreso=progreso,
                                                     callback_muestra=muestra)

            def pintar():
                marcha["terminado"] = True
                if not vigente():
                    return
                animar_progreso(refs["barra"], 1.0, refs["barra_estado"])
                refs["btn_reintentar"].configure(state="normal")
                refs["ping"].set_valor(resultado["latencia_ms"], decimales=0)
                refs["bajada"].set_valor(resultado["bajada_mbps"])
                refs["subida"].set_valor(resultado["subida_mbps"])

                # La aguja se queda en la bajada, que es el número que la
                # gente entiende como "mi velocidad".
                principal = resultado["bajada_mbps"] or resultado["subida_mbps"]
                if principal is not None:
                    refs["medidor"].set_tono(COLOR_ACCENT)
                    refs["medidor"].set_valor(principal, texto=f"{principal:.1f}")
                else:
                    refs["medidor"].set_valor(0, texto="—")

                if resultado["bajada_mbps"] is None and resultado["subida_mbps"] is None:
                    refs["estado"].configure(text=resultado["error"] or t("optmod_sin_internet"),
                                             text_color=COLOR_CRIT)
                elif resultado["error"]:
                    # Media prueba salió: se muestra lo que sí se midió y se
                    # dice qué falló, en vez de tirar todo el resultado.
                    refs["estado"].configure(text=resultado["error"], text_color=COLOR_WARN)
                else:
                    refs["estado"].configure(text=t("comp_st_aproximado"), text_color=T.texto2)
            self.after(0, pintar)

            hubo_algo = (resultado["bajada_mbps"] is not None
                         or resultado["subida_mbps"] is not None)
            resumen = (t("comp_st_resumen", latencia=resultado["latencia_ms"],
                        bajada=resultado["bajada_mbps"], subida=resultado["subida_mbps"])
                       if hubo_algo else (resultado["error"] or ""))
            self._log_dev(t("comp_log_speedtest"), "Descarga/subida de prueba a speed.cloudflare.com",
                          resumen, seccion=t("seccion_componentes"), exito=hubo_algo)

        threading.Thread(target=worker, daemon=True).start()

        def vigilante():
            # BUG corregido: antes el vigilante no miraba si la prueba ya
            # había terminado, así que en una prueba lenta pero exitosa el
            # aviso de tiempo agotado se pintaba encima del resultado bueno.
            if marcha["terminado"] or not vigente():
                return
            refs["estado"].configure(text=t("comp_st_timeout", segundos=LIMITE_S),
                                     text_color=COLOR_CRIT)
            refs["btn_reintentar"].configure(state="normal")
        self.after(LIMITE_S * 1000, vigilante)

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
            # apunta a %APPDATA% + TechClean, que si persiste.
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
            self._log_dev(t("log_exportar_hardware"), "N/A", t("hist_exportado_msg", ruta=destino),
                          seccion=t("seccion_componentes"), exito=True)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Drivers (informativo + canales oficiales) ----------------
    def mostrar_drivers(self):
        """Drivers (rediseño 1.8.0). Trae la copia de seguridad de drivers
        (exportar antes de formatear y reinstalar después), que hasta la
        1.7.0 solo tenía la edición Admin."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("drv_titulo"), t("drv_intro"))
        boton_secundario(derecha, _sin_emoji(t("drv_volver")), self.mostrar_componentes, icono="componentes",
                         height=38).pack(side="right")
        boton_secundario(derecha, _sin_emoji(t("drv_btn_admin_disp")), self._accion_abrir_admin_dispositivos,
                         icono="ajustes", height=38).pack(side="right", padx=(0, 10))
        cuerpo = self._cuerpo()

        # ---- El equipo y su página de soporte ----
        panel, self.derecha_fab = tarjeta_seccion(cuerpo, t("drv_equipo_titulo"), "componentes")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lbl_fabricante = Texto(panel, t("drv_leyendo_fabricante"), size=14, weight="bold")
        self.lbl_fabricante.pack(fill="x", padx=18, pady=(0, 18))

        def worker_fab():
            info_fab = opt.obtener_fabricante_soporte()
            self.after(0, lambda: self._pintar_fabricante(info_fab))
        threading.Thread(target=worker_fab, daemon=True).start()

        # ---- Dispositivos sin driver o con problemas ----
        # Justo lo que hace falta después de una instalación limpia de
        # Windows: no "qué drivers ya están instalados" (eso es la lista
        # de abajo), sino "qué le falta a Windows por reconocer todavía".
        panel, derecha_p = tarjeta_seccion(cuerpo, _sin_emoji(t("drv_problemas_titulo")), "componentes",
                                           t("drv_problemas_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_problemas = pildora(derecha_p)
        self.pild_problemas.pack(side="right")
        fila_escanear = Caja(panel)
        fila_escanear.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(fila_escanear, text=_sin_emoji(t("drv_btn_escanear")), width=200,
                      command=self._accion_escanear_hardware).pack(side="left")
        self.lbl_escanear_hardware = Texto(fila_escanear, "", size=12, color=T.texto2)
        self.lbl_escanear_hardware.pack(side="left", padx=12)
        self.lista_dispositivos_problema = Caja(panel)
        self.lista_dispositivos_problema.pack(fill="x", pady=(0, 8))
        self._aviso_lista(self.lista_dispositivos_problema, t("drv_revisando"))

        def worker_problemas():
            problemas = sysmon.listar_dispositivos_con_problemas()
            self.after(0, lambda: self._pintar_dispositivos_problema(problemas))
        threading.Thread(target=worker_problemas, daemon=True).start()

        # ---- Copia de seguridad (1.8.0: antes solo en la edición Admin) ----
        panel, _ = tarjeta_seccion(cuerpo, t("drv_respaldo_titulo"), "bandeja", t("drv_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.btn_drv_exportar = fila_accion(panel, "bandeja", t("drv_exportar_titulo"), t("drv_exportar_desc"),
                                            t("drv_btn_exportar_corto"), self._accion_exportar_drivers, primera=True)
        self.btn_drv_restaurar = fila_accion(panel, "reparar", t("drv_restaurar_titulo"), t("drv_restaurar_desc"),
                                             t("drv_btn_restaurar_corto"), self._accion_restaurar_drivers)
        self.lbl_drivers = Texto(panel, "", size=12, wraplength=760)
        self.lbl_drivers.pack(fill="x", padx=20, pady=(0, 16))
        texto_fluido(self.lbl_drivers, panel, 40)
        if getattr(self, "_drv_en_curso", False):
            self._botones_drivers(False)
            self.lbl_drivers.configure(text=t("drv_en_curso", minutos=0))

        # ---- Actualizaciones e Inicio rápido ----
        panel, _ = tarjeta_seccion(cuerpo, t("drv_mantenimiento_titulo"), "reparar")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        boton = fila_accion(panel, "globo", _sin_emoji(t("drv_btn_buscar_update")), t("drv_update_desc"),
                            t("drv_btn_buscar_corto"), self._accion_buscar_drivers_update, primera=True)
        self.lbl_drivers_update = Texto(boton.master.textos, "", size=12, color=T.acento, wraplength=560)
        self.lbl_drivers_update.pack(fill="x", pady=(4, 0))
        texto_fluido(self.lbl_drivers_update, boton.master.textos, 4)
        self.switch_inicio_rapido, derecha_ir = fila_interruptor(
            panel, "energia", t("drv_ir_titulo"), t("drv_inicio_rapido_nota"), False, self._toggle_inicio_rapido)
        self.lbl_estado_inicio_rapido = Texto(derecha_ir, t("drv_leyendo_minus"), size=12, color=T.texto2)
        self.lbl_estado_inicio_rapido.pack(side="right", padx=(0, 12))
        Caja(panel, height=8).pack()

        def worker_inicio_rapido():
            estado = opt.obtener_estado_inicio_rapido()
            self.after(0, lambda: self._pintar_estado_inicio_rapido(estado))
        threading.Thread(target=worker_inicio_rapido, daemon=True).start()

        # ---- Drivers instalados ----
        panel, _ = tarjeta_seccion(cuerpo, t("drv_instalados_titulo"), "archivo")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.entry_buscar_driver = ctk.CTkEntry(panel, placeholder_text=_sin_emoji(t("drv_buscar_placeholder")))
        self.entry_buscar_driver.pack(fill="x", padx=18, pady=(0, 8))
        self.entry_buscar_driver.bind("<KeyRelease>", lambda e: self._filtrar_drivers())
        # BUG de rendimiento corregido: era un marco con una tarjeta (marco +
        # etiqueta) por driver, hasta 300: 3 s de ventana congelada al
        # cargar, y OTROS 3 s con cada letra del buscador, que lo rehacía
        # todo en cada tecla. Un solo cuadro de texto pinta los 300 al
        # instante, y además deja seleccionar y copiar el nombre.
        self.lista_drivers = ctk.CTkTextbox(panel, fg_color=T.panel, border_width=0, height=380,
                                            font=fuente(size=12), wrap="word", spacing1=4, spacing3=4)
        self.lista_drivers.pack(fill="x", padx=12, pady=(0, 14))
        self.lista_drivers.tag_config("aviso", foreground=T.texto2)
        self.lista_drivers.tag_config("nombre", foreground=T.texto)
        self.lista_drivers.tag_config("detalle", foreground=T.texto2)
        self._escribir_lista_drivers([(t("drv_leyendo_drivers_largo"), "aviso")])
        self._drivers_cache = None

        def worker():
            drivers = sysmon.listar_drivers()
            self._drivers_cache = drivers
            self.after(0, self._filtrar_drivers)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_dispositivos_problema(self, problemas):
        caja = getattr(self, "lista_dispositivos_problema", None)
        if caja is None or not caja.winfo_exists():
            return
        for w in caja.winfo_children():
            w.destroy()
        if not problemas:
            poner_pildora(self.pild_problemas, t("comp_salud_bien"), "bien")
            self._aviso_lista(caja, _sin_emoji(t("drv_sin_problemas")), T.ok)
            return
        poner_pildora(self.pild_problemas, str(len(problemas)), "atencion")
        for n, d in enumerate(problemas):
            derecha = fila(caja, "componentes", _sin_emoji(t("drv_dispositivo_problema", nombre=d["nombre"])),
                           d["explicacion"], primera=n == 0, color_icono=T.aviso)
            if d["device_id"]:
                Texto(derecha.textos, d["device_id"], size=11, color=T.texto3, family="Consolas").pack(
                    fill="x", pady=(4, 0))
                boton_secundario(derecha, t("drv_btn_copiar_id"), lambda v=d["device_id"]: self._copiar_al_portapapeles(v),
                                 width=100, height=32).pack()

    def _accion_escanear_hardware(self):
        self.lbl_escanear_hardware.configure(text=t("drv_buscando_hardware"))

        def worker():
            exito, comando = opt.escanear_hardware_nuevo()
            msg = t("drv_escaneo_ok") if exito else t("drv_escaneo_error")
            self._log_dev(t("drv_log_escanear"), comando, msg,
                          seccion=t("seccion_drivers"), exito=exito)
            self.after(0, lambda: self._actualizar_label("lbl_escanear_hardware", msg))
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
            self.lbl_estado_inicio_rapido.configure(text=t("drv_ir_no_disponible").capitalize())
            self.switch_inicio_rapido.configure(state="disabled")
            return
        self.lbl_estado_inicio_rapido.configure(
            text=(t("drv_ir_activado") if estado else t("drv_ir_desactivado")).capitalize())
        if estado:
            self.switch_inicio_rapido.select()
        else:
            self.switch_inicio_rapido.deselect()

    def _toggle_inicio_rapido(self):
        activar = bool(self.switch_inicio_rapido.get())
        self.lbl_estado_inicio_rapido.configure(text=t("drv_ir_aplicando").capitalize())

        def worker():
            exito, comando = opt.set_inicio_rapido(activar)
            texto = ((t("drv_ir_activado") if activar else t("drv_ir_desactivado")) if exito
                     else t("drv_ir_error"))
            self._log_dev(t("drv_log_inicio_rapido"), comando,
                          t("drv_ir_resultado", estado=texto),
                          seccion=t("seccion_drivers"), exito=exito)

            def terminar():
                self._actualizar_label("lbl_estado_inicio_rapido", texto.capitalize())
                # Si no se pudo, el interruptor vuelve a donde estaba: si no,
                # enseñaría un estado que el equipo no tiene.
                interruptor = getattr(self, "switch_inicio_rapido", None)
                if not exito and interruptor is not None and interruptor.winfo_exists():
                    # select/deselect y no toggle: toggle vuelve a llamar a esta función.
                    interruptor.deselect() if activar else interruptor.select()
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _escribir_lista_drivers(self, trozos):
        """Reemplaza el contenido de la lista: `trozos` es [(texto, etiqueta)]."""
        caja = self.lista_drivers
        caja.configure(state="normal")
        caja.delete("1.0", "end")
        for texto, etiqueta in trozos:
            caja.insert("end", texto, etiqueta)
        caja.configure(state="disabled")

    def _filtrar_drivers(self):
        if not (hasattr(self, "lista_drivers") and self.lista_drivers.winfo_exists()):
            return
        drivers = self._drivers_cache
        if drivers is None:
            self._escribir_lista_drivers([(t("drv_leyendo_drivers"), "aviso")])
            return
        if not drivers:
            self._escribir_lista_drivers([(t("drv_sin_drivers"), "aviso")])
            return

        termino = self.entry_buscar_driver.get().strip().lower() if hasattr(self, "entry_buscar_driver") else ""
        if termino:
            drivers = [d for d in drivers
                       if termino in str(d.get("nombre") or "").lower()
                       or termino in str(d.get("fabricante") or "").lower()]

        trozos = []
        for d in drivers[:300]:
            nombre = str(d.get("nombre") or "")
            texto = t("drv_detalle", nombre=nombre, fabricante=d.get("fabricante"),
                      version=d.get("version"), fecha=d.get("fecha"))
            # El nombre resaltado y el resto en gris; si una traducción
            # pusiera el nombre en otro sitio, la línea sale entera en gris.
            if nombre and texto.startswith(nombre):
                trozos += [(nombre, "nombre"), (texto[len(nombre):] + "\n", "detalle")]
            else:
                trozos.append((texto + "\n", "detalle"))
        self._escribir_lista_drivers(trozos or [(t("drv_sin_coincidencias", termino=termino), "aviso")])

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
            self.after(0, lambda: self._actualizar_label("lbl_drivers_update", texto))
            self._log_dev(t("drv_log_buscar_update"), comando, texto,
                          seccion=t("seccion_componentes"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_fabricante(self, info_fab):
        if not (hasattr(self, "lbl_fabricante") and self.lbl_fabricante.winfo_exists()):
            return
        self.lbl_fabricante.configure(text=t("drv_fabricante_modelo",
                                             fabricante=info_fab["fabricante"],
                                             modelo=info_fab["modelo"]))
        if info_fab["url_soporte"] and hasattr(self, "derecha_fab") and self.derecha_fab.winfo_exists():
            # webbrowser.open lanza un proceso del sistema: va en un hilo, igual
            # que el boton de donacion, para no congelar la ventana si el
            # navegador esta frio.
            ctk.CTkButton(self.derecha_fab, text=_sin_emoji(t("drv_btn_soporte")), height=32,
                          command=lambda u=info_fab["url_soporte"]: threading.Thread(
                              target=lambda: webbrowser.open(u), daemon=True).start()).pack(side="right")

    def _accion_abrir_admin_dispositivos(self):
        exito, comando = opt.abrir_administrador_dispositivos()
        self._log_dev(t("drv_log_admin_disp"), comando,
                      t("drv_admin_disp_ok") if exito else t("comp_no_abrir"),
                      seccion=t("seccion_componentes"), exito=exito)

    # ---------------- Optimizador ----------------
    # La clave ("silencioso"/"equilibrado"/...) es interna y NO se traduce: es
    # lo que entiende opt.set_power_plan() y lo que se guarda en preferencias.
    PERFILES_ENERGIA = (("silencioso", "opt_perfil_silencioso"), ("equilibrado", "opt_perfil_equilibrado"),
                        ("rendimiento", "opt_perfil_rendimiento"), ("maximo", "opt_perfil_maximo"))

    def _fila_accion(self, padre, icono, titulo, descripcion, texto_boton, comando, primera=False):
        """Una fila de acción: icono, qué hace en dos líneas, y su botón."""
        fila_accion(padre, icono, titulo, descripcion, texto_boton, comando, primera)

    def _titulo_seccion(self, padre, texto, derecha=None):
        fila = Caja(padre)
        fila.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(fila, text=_sin_emoji(texto), font=fuente(size=16, weight="bold"), anchor="w").pack(
            side="left")
        return fila

    def mostrar_optimizador(self):
        """Optimizar (rediseño 1.8.0): la memoria en dos tarjetas, el disco en
        filas con su explicación, y el perfil de energía en un selector."""
        self._limpiar_contenido()
        cabecera = Caja(self.contenido)
        cabecera.grid(row=0, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 8))
        textos = Caja(cabecera)
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(textos, text=t("opt_titulo"), font=fuente(size=26, weight="bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(textos, text=t("opt_subtitulo"), font=fuente(size=13), text_color=T.texto2,
                     anchor="w").pack(fill="x")
        boton_secundario(cabecera, _sin_emoji(t("comun_ver_reporte")), self.mostrar_reporte, icono="historial",
                         height=38).pack(side="right")

        self.contenido.grid_rowconfigure(1, weight=1)
        contenedor = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        contenedor.grid(row=1, column=0, columnspan=3, sticky="nswe")

        # El resultado de la última acción, siempre a la vista arriba.
        self.lbl_resultado_opt = ctk.CTkLabel(contenedor, text=t("opt_selecciona"), font=fuente(size=13),
                                               wraplength=880, justify="left", anchor="w", fg_color=T.fila,
                                               corner_radius=T.radio_fila, height=40)
        self.lbl_resultado_opt.pack(fill="x", padx=8, pady=(0, 10), ipadx=12)

        # ---- Memoria RAM ----
        memoria = tarjeta(contenedor)
        memoria.pack(fill="x", padx=8, pady=(0, 12))
        self._titulo_seccion(memoria, t("opt_sec_memoria"))
        pareja = Caja(memoria)
        pareja.pack(fill="x", padx=14, pady=(4, 16))
        pareja.grid_columnconfigure((0, 1), weight=1, uniform="ram")
        for col, (titulo, desc, boton, comando, principal) in enumerate((
                (t("opt_btn_ram"), t("opt_desc_ram"), t("opt_accion_liberar"), self._accion_liberar_ram, True),
                (t("opt_btn_ram_profunda"), t("opt_desc_ram_profunda"), t("opt_accion_liberar_fondo"),
                 self._accion_liberar_ram_profunda, False))):
            caja = ctk.CTkFrame(pareja, fg_color=T.fila, corner_radius=T.radio_fila, border_width=T.borde_ancho,
                                border_color=T.borde)
            caja.grid(row=0, column=col, sticky="nswe", padx=6)
            ctk.CTkLabel(caja, text=titulo, font=fuente(size=14, weight="bold"), anchor="w").pack(
                fill="x", padx=16, pady=(14, 4))
            texto_fluido(ctk.CTkLabel(caja, text=desc, font=fuente(size=12), text_color=T.texto2, anchor="w",
                                      justify="left", wraplength=360), caja, 32).pack(fill="x", padx=16)
            if principal:
                ctk.CTkButton(caja, text=boton, command=comando, height=36,
                              font=fuente(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 16))
            else:
                boton_secundario(caja, boton, comando, height=36).pack(anchor="w", padx=16, pady=(12, 16))

        # ---- Espacio en disco ----
        espacio = tarjeta(contenedor)
        espacio.pack(fill="x", padx=8, pady=(0, 12))
        fila_titulo = self._titulo_seccion(espacio, t("opt_sec_espacio"))
        ctk.CTkButton(fila_titulo, text=t("opt_btn_analizar"), fg_color="transparent", hover_color=T.hover,
                      border_width=0,
                      text_color=T.acento if temas.contraste(T.acento, T.panel) >= 4.5 else T.texto,
                      height=30, command=self.mostrar_espacio_disco).pack(side="right")
        acciones = (
            ("buscar", t("opt_btn_estimar"), t("opt_desc_estimar"), t("opt_accion_estimar"), self._accion_estimar_espacio),
            ("archivo", t("opt_btn_temp"), t("opt_desc_temp"), t("opt_accion_limpiar"), self._accion_limpiar_temp),
            ("papelera", t("opt_btn_papelera"), t("opt_desc_papelera"), t("opt_accion_vaciar"),
             self._accion_vaciar_papelera),
            ("globo", t("opt_btn_dns"), t("opt_desc_dns"), t("opt_accion_limpiar"), self._accion_flush_dns),
            ("imagen", _sin_emoji(t("opt_btn_miniaturas")), t("opt_desc_miniaturas"), t("opt_accion_limpiar"),
             self._accion_limpiar_miniaturas),
        )
        for i, (icono, titulo, desc, boton, comando) in enumerate(acciones):
            self._fila_accion(espacio, icono, titulo, desc, boton, comando, primera=i == 0)
        linea(espacio).pack(fill="x", padx=20)
        fila_unica = Caja(espacio)
        fila_unica.pack(fill="x", padx=20, pady=(12, 16))
        ctk.CTkLabel(fila_unica, text="", image=iconos.icono("calendario", T.acento, 18), width=38, height=38,
                     fg_color=T.fila, corner_radius=T.radio_boton).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(fila_unica, text=_sin_emoji(t("opt_limpieza_unica_label")),
                     font=fuente(size=13)).pack(side="left")
        boton_secundario(fila_unica, t("opt_btn_programar"), self._accion_limpieza_unica, width=110,
                         height=34).pack(side="right")
        self.combo_minutos_unica = ctk.CTkOptionMenu(fila_unica, values=["5 min", "15 min", "30 min", "60 min"],
                                                     width=96)
        self.combo_minutos_unica.pack(side="right", padx=8)

        # ---- Perfil de energía ----
        energia = tarjeta(contenedor)
        energia.pack(fill="x", padx=8, pady=(0, 12))
        fila_titulo = self._titulo_seccion(energia, t("opt_perfiles_titulo"))
        self.lbl_perfil_actual = ctk.CTkLabel(fila_titulo, text=t("opt_plan_cargando"), font=fuente(size=12),
                                              text_color=T.texto2)
        self.lbl_perfil_actual.pack(side="right")
        nombres = {clave: _sin_emoji(t(texto)) for clave, texto in self.PERFILES_ENERGIA}
        self.seg_perfil = ctk.CTkSegmentedButton(
            energia, values=list(nombres.values()), height=38, font=fuente(size=13),
            command=lambda v: self._accion_cambiar_perfil(
                next(c for c, n in nombres.items() if n == v), v))
        self.seg_perfil.pack(fill="x", padx=20, pady=(6, 8))
        if self.prefs.get("perfil_energia") in nombres:
            self.seg_perfil.set(nombres[self.prefs["perfil_energia"]])
        ctk.CTkLabel(energia, text=_sin_emoji(t("opt_perfil_maximo_desc")), font=fuente(size=12),
                     text_color=T.texto2, wraplength=860, justify="left", anchor="w").pack(
            fill="x", padx=20, pady=(0, 16))
        self._actualizar_lbl_perfil_actual()

        # ---- Optimizar unidades (TRIM en SSD, desfragmentar en HDD) ----
        unidades = tarjeta(contenedor)
        unidades.pack(fill="x", padx=8, pady=(0, 12))
        self._titulo_seccion(unidades, t("unid_titulo"))
        ctk.CTkLabel(unidades, text=t("unid_desc"), font=fuente(size=12), text_color=T.texto2,
                     wraplength=860, justify="left", anchor="w").pack(fill="x", padx=20, pady=(0, 8))
        self.lista_unidades = Caja(unidades)
        self.lista_unidades.pack(fill="x", padx=20, pady=(0, 4))
        self.lbl_unidades = ctk.CTkLabel(unidades, text="", font=fuente(size=12), anchor="w",
                                         wraplength=860, justify="left")
        self.lbl_unidades.pack(fill="x", padx=20, pady=(0, 14))
        self._cargar_unidades()

        # ---- Qué está usando la RAM o el CPU, y qué apps tienes abiertas ----
        procesos = tarjeta(contenedor)
        procesos.pack(fill="x", padx=8, pady=(0, 12))
        self._titulo_seccion(procesos, t("opt_procesos_titulo"))
        ctk.CTkLabel(procesos, text=t("opt_procesos_desc"), font=fuente(size=12), text_color=T.texto2,
                     wraplength=860, justify="left", anchor="w").pack(fill="x", padx=20, pady=(0, 10))
        fila_modo_procesos = Caja(procesos)
        fila_modo_procesos.pack(fill="x", padx=20, pady=(0, 8))
        self.pestana_procesos = ctk.CTkSegmentedButton(
            fila_modo_procesos,
            values=[t("opt_tab_ram"), t("opt_tab_cpu"), t("opt_tab_ventanas")],
            command=self._cambiar_modo_procesos)
        self.pestana_procesos.set(t("opt_tab_ram"))
        self.pestana_procesos.pack(side="left", padx=(0, 10))
        boton_secundario(fila_modo_procesos, t("opt_btn_actualizar"),
                         lambda: self._mostrar_procesos_recursos(self._modo_procesos_actual())).pack(side="left")
        self.lista_procesos_ram = ctk.CTkScrollableFrame(procesos, fg_color=T.fila,
                                                           corner_radius=T.radio_fila, height=260)
        self.lista_procesos_ram.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkLabel(self.lista_procesos_ram, text=t("opt_presiona_actualizar"),
                     text_color=T.texto2).pack(padx=8, pady=8)

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
        # Se lee ANTES de cambiar nada: una vez aplicado el plan nuevo ya no
        # hay forma de saber de dónde se venía, y sin eso no hay deshacer.
        anterior = self.prefs.get("perfil_energia")
        self.lbl_resultado_opt.configure(text=t("opt_cambiando_perfil", perfil=nombre))

        def worker():
            # El plan EXACTO de antes, leído a Windows: el perfil guardado en
            # preferencias no basta si el usuario estaba en un plan propio o
            # en el del fabricante, y deshacer lo mandaba a Equilibrado.
            guid_anterior = opt.plan_activo_guid()
            exito, comando = opt.set_power_plan(clave)
            msg = (t("opt_perfil_cambiado", perfil=nombre) if exito
                   else t("opt_perfil_error_maximo") if clave == "maximo"
                   else t("opt_perfil_error"))
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_perfil", perfil=nombre), comando, msg,
                          seccion=t("seccion_optimizador"), exito=exito)
            if exito:
                # Se anota el plan que estaba ANTES, no el nuevo: sin saber
                # de donde se venia no hay vuelta atras posible.
                self.deshacer.anotar("perfil_energia",
                                      {"anterior": anterior, "nuevo": clave, "guid_anterior": guid_anterior},
                                      t("desh_desc_perfil", perfil=nombre))
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
            # El selector refleja lo que quedó guardado: si el cambio falló
            # (el plan Máximo no existe en algunos portátiles), vuelve atrás.
            guardado = self.prefs.get("perfil_energia")
            if hasattr(self, "seg_perfil") and self.seg_perfil.winfo_exists():
                nombre = next((_sin_emoji(t(texto)) for clave, texto in self.PERFILES_ENERGIA
                               if clave == guardado), None)
                if nombre:
                    self.seg_perfil.set(nombre)

        def worker():
            actual = opt.get_active_power_plan_name()
            self.after(0, lambda: pintar(actual))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Analizador de espacio en disco ----------------
    def mostrar_espacio_disco(self):
        """Espacio en disco (rediseño 1.8.0). La primera pestaña es el
        análisis completo de la unidad (disco.py): hasta la 1.7.0 se miraban
        solo dos niveles de carpetas y casi todo quedaba sin contar."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("disco_titulo"), t("disco_subtitulo"))
        boton_secundario(derecha, _sin_emoji(t("opt_volver")), self.mostrar_optimizador,
                         icono="optimizar", height=38).pack(side="right")
        self.pestana_disco = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("disco_tab_carpetas"), t("disco_tab_archivos"),
                    t("disco_tab_instaladores"), t("disco_tab_cache"), t("disco_tab_fondo"),
                    t("disco_tab_duplicados"), t("disco_tab_accesos")],
            command=self._cambiar_pestana_disco)
        self.pestana_disco.set(t("disco_tab_carpetas"))
        self.pestana_disco.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.contenedor_disco = Caja(self.contenido)
        self.contenedor_disco.grid(row=2, column=0, columnspan=3, sticky="nswe")
        self._mostrar_carpetas_pesadas()

    def _cambiar_pestana_disco(self, valor):
        """Cambia de pestaña a partir del TEXTO VISIBLE del botón segmentado.

        El texto está traducido, así que no se compara contra literales en
        español: se resuelve contra las mismas claves con las que se
        construyó el botón. Si no coincide ninguna, cae en la primera
        pestaña, que es la de por defecto — nunca en una rama equivocada."""
        if valor == t("disco_tab_archivos"):
            self._mostrar_archivos_grandes()
        elif valor == t("disco_tab_instaladores"):
            self._mostrar_instaladores_viejos()
        elif valor == t("disco_tab_cache"):
            self._mostrar_cache_apps()
        elif valor == t("disco_tab_fondo"):
            self._mostrar_limpieza_fondo()
        elif valor == t("disco_tab_duplicados"):
            self._mostrar_duplicados()
        elif valor == t("disco_tab_accesos"):
            self._mostrar_accesos_rotos()
        else:
            self._mostrar_carpetas_pesadas()

    def _limpiar_contenedor_disco(self):
        self._vaciar_pestana(self.contenedor_disco)

    def _vaciar_pestana(self, contenedor):
        """Como _limpiar_contenido: la pestaña vieja se quita de la vista al
        momento y se destruye cuando la nueva ya está dibujada. Destruir una
        lista larga (los archivos grandes, los 300 servicios) costaba de
        0,1 a 1,5 s ANTES de empezar a dibujar la pestaña nueva."""
        for w in contenedor.winfo_children():
            w.pack_forget()
            self.after_idle(lambda w=w: self.after(80, lambda: self._destruir_pantalla(w)))

    def _lista_pestana(self, contenedor, intro=None):
        """Lo común de cada pestaña: su explicación y una lista con scroll."""
        self._vaciar_pestana(contenedor)
        if intro:
            texto_fluido(Texto(contenedor, intro, size=12, color=T.texto2, wraplength=900),
                         contenedor, 4).pack(fill="x", pady=(0, 10))
        lista = ctk.CTkScrollableFrame(contenedor, fg_color="transparent")
        lista.pack(fill="both", expand=True)
        return lista

    def _lista_disco(self, intro=None):
        return self._lista_pestana(self.contenedor_disco, intro)

    @staticmethod
    def _aviso_lista(padre, texto, color=None):
        """El texto de "buscando...", "no hay nada" o un error, dentro de
        una tarjeta."""
        etiqueta = Texto(padre, texto, size=12, color=color or T.texto2, wraplength=760)
        etiqueta.pack(fill="x", padx=20, pady=(0, 16))
        return texto_fluido(etiqueta, padre, 40)

    # ---- Pestaña: Qué ocupa espacio (análisis completo, 1.8.0) ----
    MAX_FILAS_DISCO = 40
    # La clave de idiomas de cada tipo de disco.TIPOS, escrita entera (que
    # verificar_idiomas la encuentre).
    TIPOS_DISCO = {"videos": "disco_tipo_videos", "juegos": "disco_tipo_juegos",
                   "programas": "disco_tipo_programas", "comprimidos": "disco_tipo_comprimidos",
                   "imagenes": "disco_tipo_imagenes", "musica": "disco_tipo_musica",
                   "documentos": "disco_tipo_documentos", "registros": "disco_tipo_registros",
                   "otros": "disco_tipo_otros"}

    def _mostrar_carpetas_pesadas(self):
        lista = self._lista_disco()
        self.lista_espacio_disco = lista
        panel, derecha = tarjeta_seccion(lista, t("disco_analisis_titulo"), "disco", t("disco_analisis_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_disco = pildora(derecha)
        self.pild_disco.pack(side="right")
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 14))
        unidades = [p["unidad"] for p in sysmon.get_disk_partitions()] or ["C:\\"]
        self.combo_unidad_disco = ctk.CTkOptionMenu(controles, values=unidades, width=100)
        analisis = getattr(self, "_analisis_disco", None)
        if analisis is not None and analisis.raiz in unidades:
            self.combo_unidad_disco.set(analisis.raiz)
        self.combo_unidad_disco.pack(side="left", padx=(0, 10))
        self.btn_analizar_disco = ctk.CTkButton(controles, text=t("disco_btn_analizar"), width=120,
                                                command=self._accion_analizar_disco)
        self.btn_analizar_disco.pack(side="left")
        self.lbl_disco_estado = Texto(controles, "", size=12, color=T.texto2)
        self.lbl_disco_estado.pack(side="left", padx=14)
        self.barra_disco = BarraFina(panel)
        self.barra_disco.pack(fill="x", padx=18, pady=(0, 16))
        self.caja_disco = Caja(lista)
        self.caja_disco.pack(fill="x")

        if getattr(self, "_disco_cancelar", None) is not None:
            # Un análisis lanzado antes de cambiar de pantalla sigue en curso.
            self._boton_analizar_corriendo(True)
            self.lbl_disco_estado.configure(text=t("disco_analizando", unidad=self._disco_unidad))
        elif analisis is not None:
            self._pintar_analisis_disco(analisis, getattr(self, "_disco_carpeta", 0))
        else:
            self.lbl_disco_estado.configure(text=t("disco_elige_unidad"))
            self.barra_disco.pack_forget()

    def _boton_analizar_corriendo(self, corriendo):
        boton = getattr(self, "btn_analizar_disco", None)
        if boton is None or not boton.winfo_exists():
            return
        if corriendo:
            boton.configure(text=t("comun_cancelar"), fg_color=T.boton2, hover_color=T.boton2_hover,
                            text_color=T.texto)
            self.combo_unidad_disco.configure(state="disabled")
        else:
            boton.configure(text=t("disco_btn_analizar"), fg_color=T.acento, hover_color=T.acento_hover,
                            text_color=T.sobre_acento)
            self.combo_unidad_disco.configure(state="normal")

    def _accion_analizar_disco(self, unidad=None):
        if getattr(self, "_disco_cancelar", None) is not None:
            self._disco_cancelar.set()
            self._actualizar_label("lbl_disco_estado", t("fondo_dism_cancelando"))
            return
        unidad = unidad or self.combo_unidad_disco.get()
        cancelar = threading.Event()
        self._disco_cancelar = cancelar
        self._disco_unidad = unidad
        # El análisis anterior se suelta ANTES de pedir memoria para otro.
        self._analisis_disco = None
        self._boton_analizar_corriendo(True)
        self.lbl_disco_estado.configure(text=t("disco_analizando", unidad=unidad))
        self.barra_disco.pack(fill="x", padx=18, pady=(0, 16))
        self.barra_disco.poner(0)
        for w in self.caja_disco.winfo_children():
            w.destroy()
        usado = [0, 0]

        def progreso(archivos, leidos):
            texto = t("disco_leyendo", archivos=miles(archivos), tamano=opt.format_bytes(leidos))
            fraccion = leidos / usado[0] if usado[0] else 0

            def poner():
                self._actualizar_label("lbl_disco_estado", texto)
                barra = getattr(self, "barra_disco", None)
                if barra is not None and barra.winfo_exists():
                    barra.poner(fraccion)
            self.after(0, poner)

        def worker():
            try:
                uso = shutil.disk_usage(unidad)
                usado[0], usado[1] = uso.used, uso.total
            except OSError:
                pass
            arbol = disco.analizar(unidad, progreso, cancelar)
            arbol.usado, arbol.capacidad = usado
            if not arbol.cancelado:
                self._log_dev(t("disco_log_analizar", unidad=unidad),
                              t("disco_log_analizar_cmd", unidad=unidad, hilos=disco.HILOS),
                              t("disco_log_resultado", tamano=opt.format_bytes(arbol.bytes),
                                archivos=miles(arbol.n_archivos), segundos=round(arbol.segundos)),
                              seccion=t("seccion_optimizador"), exito=True)
            self.after(0, lambda: self._fin_analisis_disco(arbol))
        threading.Thread(target=worker, daemon=True).start()

    def _fin_analisis_disco(self, arbol):
        self._disco_cancelar = None
        # A medias no sirve (los tamaños de las carpetas saldrían mal): solo
        # se guarda un análisis terminado.
        self._analisis_disco = None if arbol.cancelado else arbol
        self._disco_carpeta = 0
        self._programar_soltar_analisis()
        if not (hasattr(self, "caja_disco") and self.caja_disco.winfo_exists()):
            return
        self._boton_analizar_corriendo(False)
        if arbol.cancelado:
            self._actualizar_label("lbl_disco_estado", t("disco_cancelado"))
            self.barra_disco.pack_forget()
            return
        self._pintar_analisis_disco(arbol, 0)

    def _programar_soltar_analisis(self):
        """El árbol de un disco entero son ~50 MB. Se suelta a los 10
        minutos si no se está mirando (al volver a la pantalla, se vuelve a
        contar el plazo)."""
        self._gen_soltar_disco = getattr(self, "_gen_soltar_disco", 0) + 1
        generacion = self._gen_soltar_disco

        def soltar():
            if generacion != self._gen_soltar_disco:
                return
            if getattr(self, "_pantalla_actual", "") == "mostrar_espacio_disco":
                self._programar_soltar_analisis()
                return
            self._analisis_disco = None
        self.after(600_000, soltar)

    def _pintar_analisis_disco(self, arbol, indice):
        caja = self.caja_disco
        for w in caja.winfo_children():
            w.destroy()
        # La barra era el avance del análisis; terminado, sobra.
        self.barra_disco.pack_forget()
        usado, capacidad = getattr(arbol, "usado", 0), getattr(arbol, "capacidad", 0)
        if capacidad:
            libre = capacidad - usado
            poner_pildora(self.pild_disco, t("disco_libre", libre=opt.format_bytes(libre),
                                             total=opt.format_bytes(capacidad)),
                          "critico" if libre < capacidad * 0.05 else "atencion" if libre < capacidad * 0.15 else "info")
        self.lbl_disco_estado.configure(text=t(
            "disco_resumen", tamano=opt.format_bytes(arbol.bytes), archivos=miles(arbol.n_archivos),
            carpetas=miles(len(arbol.nombres)), segundos=max(1, round(arbol.segundos))))

        # Por tipo de archivo
        panel, _ = tarjeta_seccion(caja, t("disco_reparto_titulo"), "archivo")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        total = sum(arbol.tipos.values()) or 1
        tipos = sorted((tipo for tipo in disco.TIPOS if arbol.tipos[tipo] > 0),
                       key=lambda tipo: (tipo == "otros", -arbol.tipos[tipo]))
        colores = dict(zip(tipos, temas.serie(len(tipos))))
        if "otros" in colores:
            colores["otros"] = T.texto3
        reparto = BarraReparto(panel)
        reparto.pack(fill="x", padx=18, pady=(2, 12))
        reparto.poner([(arbol.tipos[tipo] / total, colores[tipo]) for tipo in tipos])
        leyenda = Caja(panel)
        leyenda.pack(fill="x", padx=18, pady=(0, 6))
        leyenda.grid_columnconfigure((0, 1, 2), weight=1, uniform="leyenda")
        for n, tipo in enumerate(tipos):
            celda = Caja(leyenda)
            celda.grid(row=n // 3, column=n % 3, sticky="we", pady=3, padx=(0, 12))
            Texto(celda, "●", size=13, color=colores[tipo]).pack(side="left", padx=(0, 6))
            Texto(celda, t(self.TIPOS_DISCO[tipo]), size=12).pack(side="left")
            Texto(celda, opt.format_bytes(arbol.tipos[tipo]), size=12, weight="bold").pack(side="right")
        notas = []
        if usado and usado > arbol.bytes * 1.05:
            notas.append(t("disco_falta", usado=opt.format_bytes(usado)))
        if arbol.sin_permiso:
            notas.append(t("disco_sin_permiso", n=miles(arbol.sin_permiso)))
        if notas:
            self._aviso_lista(panel, " ".join(notas)).pack_configure(pady=(6, 16))
        else:
            Caja(panel, height=10).pack()

        # Carpetas, para ir entrando
        panel, derecha = tarjeta_seccion(caja, t("disco_carpetas_titulo"), "disco")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.caja_nav_disco = Caja(panel)
        self.caja_nav_disco.pack(fill="x", pady=(0, 10))
        self._pintar_carpeta_disco(indice if indice < len(arbol.nombres) else 0)

    def _pintar_carpeta_disco(self, indice):
        arbol = getattr(self, "_analisis_disco", None)
        nav = getattr(self, "caja_nav_disco", None)
        if arbol is None or nav is None or not nav.winfo_exists():
            return
        self._disco_carpeta = indice
        ruta = arbol.ruta(indice)
        if not nav.winfo_children():
            barra = Caja(nav)
            barra.pack(fill="x", padx=18, pady=(0, 4))
            boton_secundario(barra, t("disco_abrir"), lambda: self._abrir_en_explorador(arbol.ruta(self._disco_carpeta)),
                             icono="carpeta", width=90, height=32).pack(side="right", padx=(10, 0))
            self.btn_subir_disco = boton_secundario(
                barra, t("disco_subir"), lambda: self._pintar_carpeta_disco(max(0, arbol.padres[self._disco_carpeta])),
                icono="subir", width=90, height=32)
            self.lbl_ruta_disco = texto_fluido(Texto(barra, "", size=13, weight="bold", wraplength=600), barra, 230)
            self.lbl_ruta_disco.pack(side="right", fill="x", expand=True)
            self.lbl_resumen_carpeta = Texto(nav, "", size=12, color=T.texto2)
            self.lbl_resumen_carpeta.pack(fill="x", padx=18, pady=(0, 6))
            self.lista_carpetas_disco = ListaLienzo(nav)
            self.lista_carpetas_disco.pack(fill="x")
            self.lbl_resto_disco = Texto(nav, "", size=12, color=T.texto2)
        if indice > 0:
            self.btn_subir_disco.pack(side="left", padx=(0, 12))
        else:
            self.btn_subir_disco.pack_forget()
        self.lbl_ruta_disco.configure(text=ruta)
        self.lbl_resumen_carpeta.configure(text=t("disco_carpeta_resumen", tamano=opt.format_bytes(arbol.total[indice]),
                                                  archivos=miles(arbol.archivos_total[indice])))

        hijas = arbol.hijas_de(indice)
        total = arbol.total[indice] or 1
        filas = []
        for h in hijas[:self.MAX_FILAS_DISCO]:
            se_entra = bool(arbol.hijas[h]) or arbol.propio[h] > 0
            filas.append({"icono": "carpeta", "titulo": arbol.nombres[h], "valor": opt.format_bytes(arbol.total[h]),
                          "fraccion": arbol.total[h] / total, "_tam": arbol.total[h],
                          "detalle": t("disco_fila_detalle", pct=porcentaje(arbol.total[h] / total),
                                       archivos=miles(arbol.archivos_total[h])),
                          "entrar": (lambda h=h: self._pintar_carpeta_disco(h)) if se_entra else None})
        # Los archivos que hay justo en esta carpeta, como una fila más (en
        # su sitio por tamaño), pero sin entrar.
        if arbol.propio[indice]:
            propio = arbol.propio[indice]
            filas.append({"icono": "archivo", "color_icono": T.texto3, "titulo": t("disco_sueltos"),
                          "negrita": False, "color_titulo": T.texto2, "valor": opt.format_bytes(propio),
                          "fraccion": propio / total, "color_barra": T.texto3, "_tam": propio,
                          "detalle": t("disco_fila_detalle", pct=porcentaje(propio / total),
                                       archivos=miles(arbol.archivos[indice]))})
            filas.sort(key=lambda f: f["_tam"], reverse=True)
        if not filas:
            filas = [{"titulo": t("disco_vacia"), "negrita": False, "color_titulo": T.texto2}]
        self.lista_carpetas_disco.poner(filas)
        resto = hijas[self.MAX_FILAS_DISCO:]
        if resto:
            self.lbl_resto_disco.configure(text=t("disco_y_mas", n=miles(len(resto)), tamano=opt.format_bytes(
                sum(arbol.total[h] for h in resto))))
            self.lbl_resto_disco.pack(fill="x", padx=20, pady=(8, 4))
        else:
            self.lbl_resto_disco.pack_forget()

    def _abrir_en_explorador(self, ruta, seleccionar=False):
        try:
            if seleccionar:
                subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(ruta)])
            else:
                os.startfile(ruta)
        except OSError:
            pass

    # ---- Pestaña: Archivos grandes (del mismo análisis) ----
    def _mostrar_archivos_grandes(self):
        lista = self._lista_disco()
        self.lista_archivos_grandes = lista
        arbol = getattr(self, "_analisis_disco", None)
        if arbol is None:
            panel, _ = tarjeta_seccion(lista, t("disco_grandes_titulo"), "archivo", t("disco_grandes_sin"))
            panel.pack(fill="x", padx=4, pady=(0, 12))
            unidad = (sysmon.get_disk_partitions() or [{"unidad": "C:\\"}])[0]["unidad"]
            ctk.CTkButton(panel, text=t("disco_btn_analizar_ahora", unidad=unidad), width=160,
                          command=self._analizar_desde_grandes).pack(anchor="w", padx=18, pady=(0, 18))
            return
        panel, derecha = tarjeta_seccion(lista, t("disco_grandes_titulo"), "archivo",
                                         t("disco_grandes_desc", n=len(arbol.grandes), unidad=arbol.raiz))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        if not arbol.grandes:
            self._aviso_lista(panel, t("disco_sin_archivos_grandes"))
            return
        filas = []
        for tam, ruta in arbol.grandes:
            acciones = [(t("disco_accion_mostrar"), lambda r=ruta: self._abrir_en_explorador(r, seleccionar=True))]
            detalle = os.path.dirname(ruta)
            if puede_ir_a_papelera(ruta):
                acciones.append((t("disco_accion_papelera"), lambda r=ruta: self._confirmar_borrar_archivos([r])))
            else:
                detalle += "  ·  " + t("disco_de_programa")
            filas.append({"icono": "archivo", "titulo": os.path.basename(ruta), "detalle": detalle,
                          "recorte": "inicio", "valor": opt.format_bytes(tam), "acciones": acciones})
        lienzo = ListaLienzo(panel)
        lienzo.pack(fill="x", pady=(0, 10))
        lienzo.poner(filas)

    def _analizar_desde_grandes(self):
        self.pestana_disco.set(t("disco_tab_carpetas"))
        self._mostrar_carpetas_pesadas()
        self._accion_analizar_disco()

    # ---- Pestaña: Instaladores viejos ----
    def _mostrar_instaladores_viejos(self):
        lista = self._lista_disco(t("disco_instaladores_intro"))
        self.lista_instaladores = lista
        panel, derecha = tarjeta_seccion(lista, t("disco_tab_instaladores"), "bandeja")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.derecha_instaladores = derecha
        self.caja_instaladores = Caja(panel)
        self.caja_instaladores.pack(fill="x", pady=(0, 8))
        self._aviso_lista(self.caja_instaladores, t("disco_buscando"))

        def worker():
            instaladores = opt.listar_instaladores_viejos(dias=30)
            self.after(0, lambda: self._pintar_instaladores_viejos(instaladores))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_instaladores_viejos(self, instaladores):
        caja = getattr(self, "caja_instaladores", None)
        if caja is None or not caja.winfo_exists():
            return
        for w in caja.winfo_children():
            w.destroy()
        for w in self.derecha_instaladores.winfo_children():
            w.destroy()
        if not instaladores:
            self._aviso_lista(caja, t("disco_sin_instaladores"), T.ok)
            return
        total = sum(i["bytes"] for i in instaladores)
        boton_secundario(self.derecha_instaladores, _sin_emoji(t("disco_btn_papelera_todos")),
                         lambda: self._confirmar_borrar_archivos([i["ruta"] for i in instaladores]),
                         icono="papelera", height=32).pack(side="right")
        pildora(self.derecha_instaladores, t("disco_instaladores_total", cantidad=len(instaladores),
                                             tamano=opt.format_bytes(total))).pack(side="right", padx=(0, 10))
        lienzo = ListaLienzo(caja)
        lienzo.pack(fill="x")
        lienzo.poner([{"icono": "archivo", "titulo": os.path.basename(i["ruta"]),
                       "detalle": t("disco_hace_dias", dias=int((time.time() - i["mtime"]) / 86400)),
                       "valor": opt.format_bytes(i["bytes"]),
                       "acciones": [(t("disco_accion_papelera"),
                                     lambda r=i["ruta"]: self._confirmar_borrar_archivos([r]))]}
                      for i in instaladores])

    # ---- Pestaña: Caché de apps comunes ----
    def _mostrar_cache_apps(self):
        lista = self._lista_disco(t("disco_cache_intro"))
        self.lista_cache_apps = lista
        panel, _ = tarjeta_seccion(lista, t("disco_tab_cache"), "papelera")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.caja_cache_apps = Caja(panel)
        self.caja_cache_apps.pack(fill="x", pady=(0, 8))
        self._aviso_lista(self.caja_cache_apps, t("disco_buscando"))
        self._cargar_cache_apps()

    def _cargar_cache_apps(self, mensaje=None):
        def worker():
            items = opt.listar_cache_apps_comunes()
            self.after(0, lambda: self._pintar_cache_apps(items, mensaje))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_cache_apps(self, items, mensaje=None):
        caja = getattr(self, "caja_cache_apps", None)
        if caja is None or not caja.winfo_exists():
            return
        for w in caja.winfo_children():
            w.destroy()
        if mensaje:
            self._aviso_lista(caja, mensaje, T.ok)
        if not items:
            self._aviso_lista(caja, t("disco_sin_cache"))
            return
        for n, it in enumerate(items):
            fila_accion(caja, "papelera", it["nombre"], opt.format_bytes(it["bytes"]), t("disco_btn_limpiar"),
                        lambda r=it["ruta"], nombre=it["nombre"]: self._accion_limpiar_cache_app(r, nombre),
                        primera=n == 0)

    def _accion_limpiar_cache_app(self, ruta, nombre):
        def worker():
            liberado, comando = opt.limpiar_cache_app(ruta)
            msg = t("disco_cache_liberado", tamano=opt.format_bytes(liberado), nombre=nombre)
            self._log_dev(t("disco_log_limpiar_cache", nombre=nombre), comando, msg,
                          seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado)
            self._cargar_cache_apps(msg)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Pestaña: Limpieza a fondo (lo del Liberador de espacio de Windows) ----
    def _mostrar_limpieza_fondo(self):
        lista = self._lista_disco(t("fondo_intro"))
        self._checks_fondo = {}
        panel, _ = tarjeta_seccion(lista, t("disco_tab_fondo"), "papelera")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_fondo = Caja(panel)
        self.lista_fondo.pack(fill="x")
        barra = Caja(panel)
        barra.pack(fill="x", padx=20, pady=(6, 18))
        self.btn_fondo_limpiar = ctk.CTkButton(barra, text=t("fondo_btn_limpiar"), state="disabled",
                                               command=self._accion_limpieza_fondo)
        self.btn_fondo_limpiar.pack(side="right")
        self.lbl_fondo_resultado = Texto(barra, "", size=12, wraplength=620)
        self.lbl_fondo_resultado.pack(side="left", fill="x", expand=True)
        texto_fluido(self.lbl_fondo_resultado, barra, 200)

        # Componentes de Windows (DISM): aparte, porque tarda minutos y no
        # se puede estimar antes sin tardar otros tantos.
        panel, _ = tarjeta_seccion(lista, _sin_emoji(t("fondo_dism_titulo")), "reparar", t("fondo_dism_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        fila_d = Caja(panel)
        fila_d.pack(fill="x", padx=18, pady=(0, 18))
        self.btn_fondo_dism = ctk.CTkButton(fila_d, width=200, command=self._accion_limpiar_componentes)
        self.btn_fondo_dism.pack(side="left")
        self.lbl_fondo_dism = Texto(fila_d, "", size=12, wraplength=600)
        self.lbl_fondo_dism.pack(side="left", padx=12, fill="x", expand=True)
        texto_fluido(self.lbl_fondo_dism, fila_d, 230)
        # DISM sigue corriendo aunque se cambie de pantalla. Al volver, el
        # botón tiene que ofrecer CANCELAR ese, no lanzar un segundo.
        if getattr(self, "_dism_en_curso", False):
            self._boton_dism_corriendo(True)
            self.lbl_fondo_dism.configure(text=t("fondo_dism_en_curso", minutos=0))
        else:
            self._boton_dism_corriendo(False)

        self._cargar_lista_fondo()

    def _boton_dism_corriendo(self, corriendo):
        boton = getattr(self, "btn_fondo_dism", None)
        try:
            if boton is None or not boton.winfo_exists():
                return
            if corriendo:
                boton.configure(text=t("fondo_dism_cancelar"), fg_color=T.aviso, hover_color=T.aviso,
                                text_color=T.sobre_aviso)
            else:
                boton.configure(text=t("fondo_dism_btn"), fg_color=T.acento, hover_color=T.acento_hover,
                                text_color=T.sobre_acento)
        except Exception:
            pass

    def _cargar_lista_fondo(self):
        for w in self.lista_fondo.winfo_children():
            w.destroy()
        self._aviso_lista(self.lista_fondo, t("disco_buscando"))

        def worker():
            items = opt.listar_limpieza_sistema()
            self.after(0, lambda: self._pintar_limpieza_fondo(items))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_limpieza_fondo(self, items):
        if not (hasattr(self, "lista_fondo") and self.lista_fondo.winfo_exists()):
            return
        for w in self.lista_fondo.winfo_children():
            w.destroy()
        self._checks_fondo = {}
        total = 0
        for n, it in enumerate(items):
            derecha = fila(self.lista_fondo, "papelera", it["nombre"], it["desc"], primera=n == 0)
            # Marcado de entrada solo si hay algo que borrar.
            marca = casilla(derecha, it["bytes"] > 0, text="", width=24)
            marca.pack(side="right", padx=(12, 0))
            self._checks_fondo[it["clave"]] = marca
            Texto(derecha, opt.format_bytes(it["bytes"]), size=13, weight="bold",
                  color=T.texto if it["bytes"] else T.texto3).pack(side="right")
            total += it["bytes"]
        if hasattr(self, "btn_fondo_limpiar") and self.btn_fondo_limpiar.winfo_exists():
            self.btn_fondo_limpiar.configure(state="normal" if total > 0 else "disabled")
        # Si ya hay un resultado de limpieza en la etiqueta, se respeta: es
        # lo que el usuario acaba de pedir y quiere leer.
        if not getattr(self, "_fondo_resultado_fijo", False):
            self._actualizar_label("lbl_fondo_resultado",
                                   t("fondo_total", tamano=opt.format_bytes(total)) if total
                                   else _sin_emoji(t("fondo_nada")))
        self._fondo_resultado_fijo = False

    def _accion_limpieza_fondo(self):
        claves = [clave for clave, var in self._checks_fondo.items() if var.get()]
        if not claves:
            self.lbl_fondo_resultado.configure(text=t("fondo_nada_marcado"))
            return
        self.btn_fondo_limpiar.configure(state="disabled")
        self.lbl_fondo_resultado.configure(text=t("fondo_limpiando"))

        def worker():
            liberado, borrados, comando = opt.limpiar_sistema(claves)
            msg = t("fondo_listo", tamano=opt.format_bytes(liberado), archivos=borrados)
            self._log_dev(t("fondo_log"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado, archivos_afectados=borrados)

            def terminar():
                self._actualizar_label("lbl_fondo_resultado", msg)
                if hasattr(self, "lista_fondo") and self.lista_fondo.winfo_exists():
                    self._fondo_resultado_fijo = True
                    self._cargar_lista_fondo()
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_limpiar_componentes(self):
        if getattr(self, "_dism_en_curso", False):
            self._evento_dism.set()
            self._actualizar_label("lbl_fondo_dism", t("fondo_dism_cancelando"))
            return
        self._dism_en_curso = True
        self._evento_dism = threading.Event()
        self._boton_dism_corriendo(True)
        self.lbl_fondo_dism.configure(text=t("fondo_dism_en_curso", minutos=0))

        def progreso(segundos):
            texto = t("fondo_dism_en_curso", minutos=int(segundos // 60))
            self.after(0, lambda: self._actualizar_label("lbl_fondo_dism", texto))

        def worker():
            exito, liberado, resumen, cancelado = opt.limpiar_componentes_windows(
                callback_progreso=progreso, evento_cancelar=self._evento_dism)
            if cancelado:
                msg = t("fondo_dism_cancelado")
            elif exito:
                msg = t("fondo_dism_listo", tamano=opt.format_bytes(liberado))
            else:
                msg = t("fondo_dism_error")
            self._log_dev(t("fondo_dism_log"), "Dism.exe /Online /Cleanup-Image /StartComponentCleanup",
                          msg + "\n" + resumen, seccion=t("seccion_optimizador"),
                          exito=exito, bytes_liberados=liberado)

            def terminar():
                self._dism_en_curso = False
                self._actualizar_label("lbl_fondo_dism", msg)
                self._boton_dism_corriendo(False)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Confirmación compartida para borrar archivos (envía a la papelera) ----
    def _confirmar_borrar_archivos(self, rutas):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("420x180")
        dialogo.grab_set()
        texto = (t("disco_conf_papelera_varios", cantidad=len(rutas)) if len(rutas) > 1
                 else t("disco_conf_papelera_uno", nombre=os.path.basename(rutas[0])))
        ctk.CTkLabel(dialogo, text=texto, font=fuente(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            def worker():
                tamanos = {}
                for r in rutas:
                    try:
                        tamanos[r] = os.path.getsize(r)
                    except OSError:
                        pass
                eliminados, liberado, errores = opt.enviar_a_papelera(rutas)
                borrados = [r for r in tamanos if not os.path.exists(r)]
                msg = (t("disco_papelera_ok", cantidad=eliminados, tamano=opt.format_bytes(liberado))
                       if eliminados else
                       t("disco_papelera_error",
                         errores="; ".join(errores) if errores else t("disco_error_desconocido")))
                self._log_dev(t("disco_log_papelera"), "SHFileOperationW (FO_DELETE, FOF_ALLOWUNDO)",
                              msg, seccion=t("seccion_optimizador"), exito=eliminados > 0, bytes_liberados=liberado)
                def refrescar_pestana():
                    arbol = getattr(self, "_analisis_disco", None)
                    if arbol is not None:
                        for r in borrados:
                            arbol.quitar_archivo(r, tamanos[r])
                    if hasattr(self, "pestana_disco") and self.pestana_disco.winfo_exists():
                        self._cambiar_pestana_disco(self.pestana_disco.get())
                self.after(0, refrescar_pestana)
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("disco_btn_enviar_papelera"), fg_color=COLOR_WARN, text_color=T.sobre_aviso,
                      command=confirmar).pack(side="left", padx=8)

    def _accion_liberar_ram_profunda(self):
        self._accion_liberar_ram(nivel="profunda")

    def _accion_liberar_ram(self, nivel="normal"):
        def worker():
            r = opt.liberar_memoria(nivel=nivel)
            liberado, afectados, comando = r["liberado"], r["procesos"], r["comando"]
            msg = t("opt_ram_ok", antes=f"{r['uso_antes']:.0f}", despues=f"{r['uso_despues']:.0f}",
                    tamano=opt.format_bytes(liberado))
            if r["espera_antes"] is not None and r["espera_despues"] is not None:
                msg += " " + t("opt_ram_espera", antes=opt.format_bytes(r["espera_antes"]),
                                despues=opt.format_bytes(r["espera_despues"]))
            if not r["completo"]:
                msg += "\n" + t("opt_ram_parcial")
            # BUG corregido: esto tocaba la etiqueta DESDE EL HILO del trabajo, y
            # ademas sin comprobar que siguiera viva. Si el usuario cambiaba de
            # pantalla mientras la tarea corria (limpiar temporales tarda lo suyo),
            # el widget ya no existia y el resultado se perdia en silencio.
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_ram_profunda" if nivel == "profunda" else "opt_log_ram"), comando, msg,
                          seccion=t("seccion_optimizador"),
                          exito=True, bytes_ram=liberado, archivos_afectados=afectados)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(
            text=t("opt_liberando_ram_profunda" if nivel == "profunda" else "opt_liberando_ram"))

    def _mostrar_procesos_recursos(self, modo):
        for w in self.lista_procesos_ram.winfo_children():
            w.destroy()
        if modo == "ram":
            texto_espera = t("opt_leyendo_procesos")
        elif modo == "cpu":
            texto_espera = t("opt_midiendo_cpu")
        else:
            texto_espera = t("opt_leyendo_ventanas")
        ctk.CTkLabel(self.lista_procesos_ram, text=texto_espera, text_color=T.texto2).pack(padx=8, pady=8)

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
            ctk.CTkLabel(self.lista_procesos_ram, text=texto_vacio, text_color=T.texto2).pack(padx=8, pady=8)
            return

        if modo == "ventanas":
            for v in procesos:
                riesgo, _ = opt.evaluar_riesgo_proceso(v["proceso"])
                fila = ctk.CTkFrame(self.lista_procesos_ram, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_boton)
                fila.pack(fill="x", padx=4, pady=3)
                col_texto = ctk.CTkFrame(fila, fg_color="transparent")
                col_texto.pack(side="left", padx=10, pady=8, fill="x", expand=True)
                ctk.CTkLabel(col_texto, text=v["titulo"], font=fuente(size=12, weight="bold"),
                             anchor="w", wraplength=520).pack(fill="x", anchor="w")
                ctk.CTkLabel(col_texto, text=v["proceso"], font=fuente(size=11),
                             text_color=T.texto2, anchor="w").pack(fill="x", anchor="w")
                if riesgo == "bloqueado":
                    ctk.CTkButton(fila, text=t("opt_protegido"), width=90, fg_color=T.boton2,
                                  hover_color=T.boton2_hover, state="disabled", text_color=T.texto).pack(side="right", padx=10, pady=6)
                else:
                    ctk.CTkButton(fila, text=t("comun_cerrar"), width=80, fg_color=T.peligro,
                                  hover_color=T.critico,
                                  command=lambda hwnd=v["hwnd"], titulo=v["titulo"]:
                                  self._confirmar_cerrar_ventana(hwnd, titulo), text_color=T.sobre_peligro).pack(side="right", padx=10, pady=6)
            return

        for p in procesos:
            riesgo, _ = opt.evaluar_riesgo_proceso(p["nombre"])
            fila = ctk.CTkFrame(self.lista_procesos_ram, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_boton)
            fila.pack(fill="x", padx=4, pady=3)
            nombre_mostrado = p["nombre"] + ("  🔒" if riesgo == "bloqueado" else "")
            # El vigilante marca los que llevan rato creciendo sin parar.
            fuga = self.vigilante.fugas.get(p.get("pid"))
            if fuga:
                nombre_mostrado += "  " + t("vig_fuga_etiqueta", crecimiento=opt.format_bytes(fuga["crecimiento"]),
                                            minutos=fuga["minutos"])
            ctk.CTkLabel(fila, text=nombre_mostrado, font=fuente(size=12, weight="bold"), anchor="w",
                         text_color=COLOR_WARN if fuga else None).pack(
                side="left", padx=10, pady=8, fill="x", expand=True)
            texto_valor = (opt.format_bytes(p["bytes_ram"]) if modo == "ram"
                           else t("opt_cpu_pct", pct=f'{p["cpu_pct"]:.0f}'))
            ctk.CTkLabel(fila, text=texto_valor, font=fuente(size=11),
                         text_color=T.texto2).pack(side="left", padx=(0, 10))
            if riesgo == "bloqueado":
                ctk.CTkButton(fila, text=t("opt_protegido"), width=90, fg_color=T.boton2,
                              hover_color=T.boton2_hover, state="disabled", text_color=T.texto).pack(side="right", padx=10, pady=6)
            else:
                ctk.CTkButton(fila, text=t("proc_btn_terminar"), width=80, fg_color=T.peligro, hover_color=T.critico,
                              command=lambda pid=p["pid"], nombre=p["nombre"]:
                              self._confirmar_terminar_proceso(pid, nombre), text_color=T.sobre_peligro).pack(side="right", padx=10, pady=6)

    def _confirmar_cerrar_ventana(self, hwnd, titulo):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("440x200")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("opt_conf_cerrar_titulo", titulo=titulo),
                     font=fuente(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))
        ctk.CTkLabel(dialogo,
                     text=t("opt_conf_cerrar_desc"),
                     font=fuente(size=11), text_color=T.texto2, wraplength=400, justify="center").pack(
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

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("comun_cerrar"), fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

    def _confirmar_terminar_proceso(self, pid, nombre):
        riesgo, motivo = opt.evaluar_riesgo_proceso(nombre)
        if riesgo == "bloqueado":
            self._mostrar_popup_info(
                t("proc_protegido_titulo"),
                t("proc_protegido_msg", nombre=nombre, motivo=motivo))
            return

        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("440x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("proc_conf_titulo", nombre=nombre, pid=pid),
                     font=fuente(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))

        if riesgo == "recuperable":
            ctk.CTkLabel(dialogo, text=t("proc_aviso_riesgo", motivo=motivo),
                         font=fuente(size=11, weight="bold"), text_color=COLOR_WARN,
                         wraplength=400, justify="center").pack(padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(dialogo,
                         text=t("proc_aviso_normal"),
                         font=fuente(size=11), text_color=COLOR_WARN, wraplength=400, justify="center").pack(
                padx=20, pady=(0, 10))
        ctk.CTkLabel(dialogo,
                     text=t("proc_consejo"),
                     font=fuente(size=11), text_color=T.texto2, wraplength=400, justify="center").pack(
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

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("proc_btn_terminar"), fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

    def _accion_estimar_espacio(self):
        def worker():
            resultados, total = opt.estimate_reclaimable_space()
            detalle = "\n".join(t("opt_espacio_detalle", categoria=r["categoria"],
                                   tamano=opt.format_bytes(r["bytes"])) for r in resultados)
            msg = t("opt_espacio_estimado", total=opt.format_bytes(total), detalle=detalle)
            # BUG corregido: esto tocaba la etiqueta DESDE EL HILO del trabajo, y
            # ademas sin comprobar que siguiera viva. Si el usuario cambiaba de
            # pantalla mientras la tarea corria (limpiar temporales tarda lo suyo),
            # el widget ya no existia y el resultado se perdia en silencio.
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_estimar"), t("opt_log_estimar_cmd"),
                          msg, seccion=t("seccion_optimizador"), exito=True)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_escaneando"))

    def _accion_limpiar_temp(self):
        def worker():
            liberado, borrados, comando = opt.clear_temp_files()
            msg = t("opt_temp_ok", archivos=borrados, tamano=opt.format_bytes(liberado))
            # BUG corregido: esto tocaba la etiqueta DESDE EL HILO del trabajo, y
            # ademas sin comprobar que siguiera viva. Si el usuario cambiaba de
            # pantalla mientras la tarea corria (limpiar temporales tarda lo suyo),
            # el widget ya no existia y el resultado se perdia en silencio.
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_temp"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=True, bytes_liberados=liberado, archivos_afectados=borrados)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_limpiando_temp"))

    def _accion_vaciar_papelera(self):
        """BUG corregido: esto vaciaba la papelera EN EL HILO DE LA INTERFAZ.
        SHEmptyRecycleBinW no vuelve hasta haber borrado todo de verdad, así
        que con una papelera de varios GB la ventana se quedaba tiesa y
        Windows la marcaba como "No responde" — justo la sensación que esta
        app existe para evitar. Ahora va en un hilo y avisa mientras trabaja."""
        def worker():
            exito, comando, liberado, elementos = opt.empty_recycle_bin()
            if exito and elementos == 0:
                msg = t("opt_papelera_vacia")
            elif exito:
                msg = t("opt_papelera_ok", tamano=opt.format_bytes(liberado), elementos=elementos)
            else:
                msg = t("opt_papelera_error")
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_papelera"), comando, msg, seccion=t("seccion_optimizador"),
                          exito=exito, bytes_liberados=liberado, archivos_afectados=elementos)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_opt.configure(text=t("opt_vaciando_papelera"))

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
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
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
            self.after(0, lambda: self._actualizar_label("lbl_resultado_opt", msg))
            self._log_dev(t("opt_log_limpieza_unica"), comando, msg,
                          seccion=t("seccion_optimizador"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Privacidad ----------------
    def mostrar_privacidad(self):
        """Privacidad (rediseño 1.8.0): primero quién usó tu cámara, tu
        micrófono y tu ubicación, y cuándo (lo que Windows apunta y casi
        nadie mira); después los navegadores, los interruptores de
        privacidad de Windows y otras huellas.

        BUG corregido: los interruptores (registro) se leían en el hilo de
        la interfaz, justo lo que prohíbe la regla de hilos. Ahora en uno
        aparte, como el resto."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("nav_privacidad"), t("priv_subtitulo"))
        boton_secundario(derecha, _sin_emoji(t("comun_ver_reporte")), self.mostrar_reporte, icono="historial",
                         height=38).pack(side="right")
        cuerpo = self._cuerpo()

        # ---- Quién usó la cámara, el micrófono y la ubicación ----
        panel, derecha_t = tarjeta_seccion(cuerpo, t("uso_titulo"), "privacidad", t("uso_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        boton_secundario(derecha_t, t("uso_btn_permisos"), self._accion_abrir_permisos_privacidad,
                         height=30).pack(side="right")
        self.caja_uso = Caja(panel)
        self.caja_uso.pack(fill="x", padx=18, pady=(0, 16))
        Texto(self.caja_uso, t("comun_cargando"), size=12, color=T.texto2).pack(anchor="w")

        # ---- Navegadores ----
        panel, _ = tarjeta_seccion(cuerpo, t("priv_titulo"), "globo", t("priv_cierra_navegador"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.caja_navegadores = Caja(panel)
        self.caja_navegadores.pack(fill="x")
        self.lbl_resultado_priv = Texto(panel, "", size=12, wraplength=760)
        self.lbl_resultado_priv.pack(fill="x", padx=18, pady=(0, 14))
        texto_fluido(self.lbl_resultado_priv, panel, 36)

        # ---- Privacidad de Windows ----
        panel, derecha_t = tarjeta_seccion(cuerpo, _sin_emoji(t("privw_titulo")), "seguridad", t("privw_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        ctk.CTkButton(derecha_t, text=t("privw_btn_todo"), height=32, command=self._accion_todo_privado).pack(
            side="right")
        self.lista_privacidad_win = Caja(panel)
        self.lista_privacidad_win.pack(fill="x")
        self.lbl_privacidad_win = Texto(panel, "", size=12, wraplength=760)
        self.lbl_privacidad_win.pack(fill="x", padx=18, pady=(0, 14))
        texto_fluido(self.lbl_privacidad_win, panel, 36)

        # ---- Otras huellas de actividad ----
        panel, _ = tarjeta_seccion(cuerpo, _sin_emoji(t("priv_otras_titulo")), "archivo")
        panel.pack(fill="x", padx=8, pady=(0, 12))
        fila_accion(panel, "historial", t("priv_btn_recientes"), t("priv_desc_recientes"), t("opt_accion_vaciar"),
                    self._accion_limpiar_recientes, primera=True)
        fila_accion(panel, "archivo", t("priv_btn_portapapeles"), t("priv_desc_portapapeles"),
                    t("opt_accion_vaciar"), self._accion_limpiar_portapapeles)
        self.lbl_resultado_otros_priv = Texto(panel, "", size=12, color=T.texto2, wraplength=760)
        self.lbl_resultado_otros_priv.pack(fill="x", padx=18, pady=(0, 14))

        def worker():
            datos = {"uso": priv.uso_de_permisos(), "navegadores": priv.detect_installed_browsers(),
                     "ajustes": opt.leer_ajustes_privacidad()}
            self.after(0, lambda: self._pintar_privacidad(datos))
        threading.Thread(target=worker, daemon=True).start()

    TIPOS_USO = (("webcam", "uso_camara", "ms-settings:privacy-webcam"),
                 ("microphone", "uso_microfono", "ms-settings:privacy-microphone"),
                 ("location", "uso_ubicacion", "ms-settings:privacy-location"))

    def _pintar_privacidad(self, datos):
        if not (hasattr(self, "caja_uso") and self.caja_uso.winfo_exists()):
            return
        # ---- Uso de la cámara, el micrófono y la ubicación ----
        for w in self.caja_uso.winfo_children():
            w.destroy()
        ahora = time.time()
        for tipo, clave, _ in self.TIPOS_USO:
            apps = datos["uso"].get(tipo) or []
            cabecera = Caja(self.caja_uso)
            cabecera.pack(fill="x", pady=(10, 2))
            Texto(cabecera, t(clave), size=13, weight="bold").pack(side="left")
            if any(a["en_uso"] for a in apps):
                pildora(cabecera, t("uso_en_uso"), "critico").pack(side="left", padx=10)
            if not apps:
                Texto(self.caja_uso, t("uso_nadie"), size=12, color=T.texto2).pack(fill="x")
                continue
            lista = ListaDatos(self.caja_uso)
            lista.pack(fill="x")
            for i, app in enumerate(apps[:5]):
                cuando = t("uso_en_uso") if app["en_uso"] else hace_cuanto(ahora - app["inicio"])
                lista.poner(i, app["nombre"], cuando, T.critico if app["en_uso"] else T.texto)
            if len(apps) > 5:
                Texto(self.caja_uso, t("uso_mas", n=len(apps) - 5), size=11, color=T.texto3).pack(fill="x")

        # ---- Navegadores ----
        for w in self.caja_navegadores.winfo_children():
            w.destroy()
        navegadores = datos["navegadores"]
        if not navegadores:
            Texto(self.caja_navegadores, t("priv_sin_navegadores"), size=12, color=T.texto2).pack(
                fill="x", padx=18, pady=(0, 8))
        if navegadores:
            lienzo = ListaLienzo(self.caja_navegadores, margen=18)
            lienzo.pack(fill="x")
            lienzo.poner([{"icono": "globo", "titulo": nombre,
                           "acciones": [(t("priv_btn_historial"), lambda n=nombre: self._accion_borrar_historial(n)),
                                        (t("priv_btn_cache"), lambda n=nombre: self._accion_borrar_cache(n))]}
                          for nombre in navegadores])
        self._pintar_ajustes_privacidad(datos["ajustes"])

    def _accion_abrir_permisos_privacidad(self):
        try:
            os.startfile("ms-settings:privacy-webcam")
        except Exception:
            pass

    # ---- Privacidad de Windows (interruptores con deshacer) ----
    TEXTOS_PRIVACIDAD = {
        "publicidad": ("privw_publicidad", "privw_publicidad_desc"),
        "sugerencias_inicio": ("privw_sug_inicio", "privw_sug_inicio_desc"),
        "sugerencias_configuracion": ("privw_sug_config", "privw_sug_config_desc"),
        "consejos": ("privw_consejos", "privw_consejos_desc"),
        "experiencias": ("privw_experiencias", "privw_experiencias_desc"),
        "bing_inicio": ("privw_bing", "privw_bing_desc"),
    }

    def _pintar_ajustes_privacidad(self, estado):
        if not (hasattr(self, "lista_privacidad_win") and self.lista_privacidad_win.winfo_exists()):
            return
        for w in self.lista_privacidad_win.winfo_children():
            w.destroy()
        for i, (clave, (titulo, desc)) in enumerate(self.TEXTOS_PRIVACIDAD.items()):
            interruptor, _ = fila_interruptor(self.lista_privacidad_win, "privacidad", t(titulo), t(desc),
                                              bool(estado.get(clave)), None, primera=i == 0, margen=18)
            interruptor.configure(command=lambda c=clave, sw=interruptor: self._accion_ajuste_privacidad(
                c, bool(sw.get())))

    def _accion_ajuste_privacidad(self, clave, activar):
        nombre = t(self.TEXTOS_PRIVACIDAD[clave][0])

        def worker():
            exito, comando, anteriores = opt.set_ajuste_privacidad(clave, activar)
            if exito:
                self.deshacer.anotar("ajuste_privacidad", {"clave": clave, "anteriores": anteriores},
                                     t("desh_desc_ajuste_juego", ajuste=nombre))
                msg = t("privw_ok_reinicio" if opt.AJUSTES_PRIVACIDAD[clave]["reinicio"] else "gjuego_aj_ok",
                        ajuste=nombre)
            else:
                msg = t("gjuego_aj_error", ajuste=nombre)
            self._log_dev(t("privw_log", ajuste=nombre), comando, msg, seccion=t("seccion_privacidad"), exito=exito)

            estado = opt.leer_ajustes_privacidad() if not exito else None

            def terminar():
                self._actualizar_label("lbl_privacidad_win", msg)
                if estado is not None:
                    self._pintar_ajustes_privacidad(estado)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_todo_privado(self):
        """Apaga los seis de una vez. Cada uno queda en Historial con su
        propio deshacer: así se puede volver atrás de uno solo."""
        def worker():
            hechos = 0
            for clave in self.TEXTOS_PRIVACIDAD:
                exito, comando, anteriores = opt.set_ajuste_privacidad(clave, False)
                if exito:
                    hechos += 1
                    nombre = t(self.TEXTOS_PRIVACIDAD[clave][0])
                    self.deshacer.anotar("ajuste_privacidad", {"clave": clave, "anteriores": anteriores},
                                         t("desh_desc_ajuste_juego", ajuste=nombre))
                    self._log_dev(t("privw_log", ajuste=nombre), comando, "OK",
                                  seccion=t("seccion_privacidad"), exito=True)
            msg = t("privw_todo_ok", hechos=hechos, total=len(self.TEXTOS_PRIVACIDAD))
            estado = opt.leer_ajustes_privacidad()

            def terminar():
                self._actualizar_label("lbl_privacidad_win", msg)
                self._pintar_ajustes_privacidad(estado)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Seguridad: auditoría (solo lectura) ----
    NIVEL_PILDORA = {"alto": "critico", "medio": "atencion", "info": "info"}
    TEXTO_NIVEL_AUD = {"alto": "aud_nivel_alto", "medio": "aud_nivel_medio", "info": "aud_nivel_info"}

    def _fila_hallazgo(self, padre, nivel, titulo, ruta, lineas, detalle, primera):
        """Un hallazgo de la auditoría o una extensión: su nivel, qué es, por
        qué se marcó y dónde está (con el botón para ir a mirarlo)."""
        if not primera:
            linea(padre).pack(fill="x", padx=20)
        caja = Caja(padre)
        caja.pack(fill="x", padx=20, pady=12)
        arriba = Caja(caja)
        arriba.pack(fill="x")
        pildora(arriba, t(self.TEXTO_NIVEL_AUD.get(nivel, "aud_nivel_info")),
                self.NIVEL_PILDORA.get(nivel, "info")).pack(side="left", padx=(0, 10))
        if ruta:
            boton_secundario(arriba, _sin_emoji(t("aud_btn_ubicacion")), lambda r=ruta: self._abrir_ubicacion(r),
                             icono="carpeta", height=30).pack(side="right", padx=(10, 0))
        texto_fluido(Texto(arriba, titulo, size=14, weight="bold", wraplength=560), arriba, 300).pack(
            side="left", fill="x", expand=True)
        for texto in lineas:
            texto_fluido(Texto(caja, "• " + texto, size=12, color=T.texto2, wraplength=760), caja, 4).pack(
                fill="x", pady=(4, 0))
        if detalle:
            texto_fluido(Texto(caja, detalle, size=11, color=T.texto3, wraplength=760), caja, 4).pack(
                fill="x", pady=(4, 0))

    def _mostrar_auditoria(self):
        lista = self._lista_pestana(self.contenedor_seguridad, t("aud_desc"))
        panel, self.derecha_auditoria = tarjeta_seccion(lista, _sin_emoji(t("seg_tab_auditoria")), "buscar")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 10))
        self.btn_auditar = ctk.CTkButton(controles, text=_sin_emoji(t("aud_btn")), width=200,
                                         command=self._accion_auditar)
        self.btn_auditar.pack(side="left")
        self.lbl_auditoria = Texto(controles, "", size=12, wraplength=600)
        self.lbl_auditoria.pack(side="left", padx=12, fill="x", expand=True)
        texto_fluido(self.lbl_auditoria, controles, 230)
        self.pild_auditoria = pildora(self.derecha_auditoria)
        self.pild_auditoria.pack(side="right")
        self.lista_auditoria = Caja(panel)
        self.lista_auditoria.pack(fill="x", pady=(0, 8))
        if getattr(self, "_auditoria_cache", None) is not None:
            self._pintar_auditoria(self._auditoria_cache)

    # ---- Extensiones del navegador (1.7.0) ----
    def _mostrar_extensiones(self):
        lista = self._lista_pestana(self.contenedor_seguridad, t("ext_desc"))
        panel, derecha = tarjeta_seccion(lista, _sin_emoji(t("seg_tab_extensiones")), "globo")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_extensiones = pildora(derecha)
        self.pild_extensiones.pack(side="right")
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 10))
        self.btn_extensiones = boton_secundario(controles, _sin_emoji(t("ext_btn")),
                                                self._accion_auditar_extensiones, width=200)
        self.btn_extensiones.pack(side="left")
        self.lbl_extensiones = Texto(controles, "", size=12, wraplength=600)
        self.lbl_extensiones.pack(side="left", padx=12, fill="x", expand=True)
        texto_fluido(self.lbl_extensiones, controles, 230)
        self.lista_extensiones = Caja(panel)
        self.lista_extensiones.pack(fill="x", pady=(0, 8))
        if getattr(self, "_extensiones_cache", None) is not None:
            self._pintar_extensiones(self._extensiones_cache)
        else:
            self._accion_auditar_extensiones()

    def _accion_auditar_extensiones(self):
        if getattr(self, "_auditando_extensiones", False):
            return
        self._auditando_extensiones = True
        self.btn_extensiones.configure(state="disabled")
        self.lbl_extensiones.configure(text=t("ext_revisando"), text_color=T.texto2)
        poner_pildora(self.pild_extensiones, "")
        idioma = idiomas.IDIOMA_ACTUAL

        def worker():
            try:
                extensiones = seg.auditar_extensiones(idioma)
            except Exception as e:
                extensiones = None
                self._log_dev(t("ext_log"), "seguridad.auditar_extensiones", str(e),
                              seccion=t("seccion_seguridad"), exito=False)
            if extensiones is not None:
                self._extensiones_cache = extensiones
                self._log_dev(t("ext_log"), "seguridad.auditar_extensiones",
                              t("ext_resumen", total=len(extensiones),
                                altos=sum(1 for e in extensiones if e["nivel"] == "alto"),
                                medios=sum(1 for e in extensiones if e["nivel"] == "medio")),
                              seccion=t("seccion_seguridad"), exito=True)
            self.after(0, lambda: self._pintar_extensiones(extensiones))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_extensiones(self, extensiones):
        self._auditando_extensiones = False
        if not (hasattr(self, "lista_extensiones") and self.lista_extensiones.winfo_exists()):
            return
        self.btn_extensiones.configure(state="normal")
        for w in self.lista_extensiones.winfo_children():
            w.destroy()
        if extensiones is None:
            self.lbl_extensiones.configure(text=t("ext_error"), text_color=T.critico)
            return
        if not extensiones:
            self.lbl_extensiones.configure(text=t("ext_ninguna"), text_color=T.ok)
            return
        extensiones = [e for e in extensiones if isinstance(e, dict)]
        altos = sum(1 for e in extensiones if e.get("nivel") == "alto")
        medios = sum(1 for e in extensiones if e.get("nivel") == "medio")
        self.lbl_extensiones.configure(
            text=t("ext_resumen", total=len(extensiones), altos=altos, medios=medios), text_color=T.texto2)
        poner_pildora(self.pild_extensiones, str(altos + medios) if altos or medios else t("comp_salud_bien"),
                      "critico" if altos else "atencion" if medios else "bien")
        for n, e in enumerate(extensiones[:200]):
            nombre = e.get("nombre") or e.get("id") or "?"
            if not e.get("activa", True):
                nombre += f'   ({t("ext_desactivada")})'
            perfiles = e.get("perfiles") or []
            texto_perfiles = ", ".join(perfiles[:3]) + (f" +{len(perfiles) - 3}" if len(perfiles) > 3 else "")
            ruta = e.get("ruta")
            self._fila_hallazgo(
                self.lista_extensiones, e.get("nivel"), nombre, ruta if ruta and os.path.isdir(ruta) else None,
                [t(m, organizacion=e.get("organizacion") or "") for m in e.get("motivos") or []],
                t("ext_detalle", navegador=e.get("navegador") or "?", version=e.get("version") or "?",
                  perfiles=texto_perfiles or "—"), primera=n == 0)

    def _accion_auditar(self):
        if getattr(self, "_auditando", False):
            return
        self._auditando = True
        self.btn_auditar.configure(state="disabled")
        self.lbl_auditoria.configure(text=t("aud_analizando"), text_color=T.texto2)

        def worker():
            try:
                hallazgos = seg.evaluar(seg.recolectar())
            except Exception as e:
                hallazgos = None
                self._log_dev(t("aud_log"), "seguridad.recolectar/evaluar", str(e),
                              seccion=t("seccion_seguridad"), exito=False)
            if hallazgos is not None:
                self._auditoria_cache = hallazgos
                altos = sum(1 for h in hallazgos if h["nivel"] == "alto")
                self._log_dev(t("aud_log"), "seguridad.recolectar/evaluar",
                              t("aud_resumen", altos=altos, total=len(hallazgos)),
                              seccion=t("seccion_seguridad"), exito=True)
            self.after(0, lambda: self._pintar_auditoria(hallazgos))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_auditoria(self, hallazgos):
        self._auditando = False
        if not (hasattr(self, "lista_auditoria") and self.lista_auditoria.winfo_exists()):
            return
        self.btn_auditar.configure(state="normal")
        for w in self.lista_auditoria.winfo_children():
            w.destroy()
        if hallazgos is None:
            self.lbl_auditoria.configure(text=t("aud_error"), text_color=T.critico)
            return
        if not hallazgos:
            self.lbl_auditoria.configure(text=_sin_emoji(t("aud_limpio")), text_color=T.ok)
            poner_pildora(self.pild_auditoria, t("comp_salud_bien"), "bien")
            return
        altos = sum(1 for h in hallazgos if h["nivel"] == "alto")
        self.lbl_auditoria.configure(text=t("aud_resumen", altos=altos, total=len(hallazgos)), text_color=T.texto2)
        poner_pildora(self.pild_auditoria, str(len(hallazgos)), "critico" if altos else "atencion")
        for n, h in enumerate(hallazgos):
            ruta = h.get("ruta")
            motivos = [t(m, original=h.get("original") or "?") if m == "seg_motivo_interprete_renombrado" else t(m)
                       for m in h.get("motivos") or []]
            self._fila_hallazgo(self.lista_auditoria, h["nivel"], t(h["clave"]),
                                ruta if ruta and os.path.exists(ruta) else None, motivos, h.get("detalle") or "",
                                primera=n == 0)
        linea(self.lista_auditoria).pack(fill="x", padx=20)
        texto_fluido(Texto(self.lista_auditoria, t("aud_que_hacer"), size=12, color=T.aviso, wraplength=760),
                     self.lista_auditoria, 40).pack(fill="x", padx=20, pady=12)

    def _abrir_ubicacion(self, ruta):
        """Abre el Explorador con el archivo SELECCIONADO. Solo mostrar: no
        ejecuta ni toca el archivo."""
        try:
            subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(ruta)])
        except Exception:
            pass

    # ---- Seguridad: programas en la red ----
    def _mostrar_red_programas(self):
        lista = self._lista_pestana(self.contenedor_seguridad, t("red_desc"))
        panel, derecha = tarjeta_seccion(lista, _sin_emoji(t("seg_tab_red")), "globo")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        boton_secundario(derecha, t("opt_btn_actualizar"), self._mostrar_red_programas, height=32).pack(side="right")
        self.lista_red = ListaLienzo(panel)
        self.lista_red.pack(fill="x", pady=(0, 10))
        self.lista_red.poner([{"titulo": t("comun_cargando"), "negrita": False, "color_titulo": T.texto2}])

        def worker():
            programas = seg.programas_en_red()
            self.after(0, lambda: self._pintar_red_programas(programas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_red_programas(self, programas):
        lienzo = getattr(self, "lista_red", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        if not programas:
            lienzo.poner([{"titulo": t("red_nada"), "negrita": False, "color_titulo": T.texto2}])
            return
        filas = []
        for p in programas:
            # Un programa de una carpeta de usuario que ESCUCHA conexiones
            # (no solo las abre) es lo raro: se pinta en aviso.
            aviso = p["de_usuario"] and p["escucha"]
            partes = []
            if p["escucha"]:
                partes.append(t("red_escucha", puertos=", ".join(str(x) for x in p["escucha"][:8])))
            if p["conexiones"]:
                partes.append(t("red_conexiones", n=p["conexiones"]))
            if p["exe"]:
                partes.append(p["exe"])
            filas.append({"icono": "globo", "color_icono": T.aviso if aviso else T.acento, "titulo": p["nombre"],
                          "color_titulo": T.aviso if aviso else T.texto, "detalle": "  ·  ".join(partes)})
        lienzo.poner(filas)

    def _accion_limpiar_recientes(self):
        def worker():
            borrados, comando = opt.limpiar_accesos_recientes()
            msg = (t("priv_recientes_ok", cantidad=borrados) if borrados
                   else t("priv_recientes_vacio"))
            self.after(0, lambda: self._actualizar_label("lbl_resultado_otros_priv", msg))
            self._log_dev(t("priv_btn_recientes"), comando, msg, seccion=t("seccion_privacidad"),
                          exito=True, archivos_afectados=borrados)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_limpiar_portapapeles(self):
        # opt.limpiar_portapapeles() lanza un subproceso con hasta 15s de
        # timeout: en el hilo principal eso congela la ventana entera.
        def worker():
            exito, comando = opt.limpiar_portapapeles()
            msg = t("priv_portapapeles_ok") if exito else t("priv_portapapeles_error")
            self.after(0, lambda: self._actualizar_label("lbl_resultado_otros_priv", msg))
            self._log_dev(t("priv_btn_portapapeles"), comando, msg,
                          seccion=t("seccion_privacidad"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # BUG corregido (1.8.0): las dos corrían en el hilo de la ventana. Borrar
    # la caché de un navegador recorre miles de archivos (y antes mira la
    # lista de procesos): la app se quedaba congelada mientras tanto.
    def _accion_borrar_historial(self, nombre):
        self.lbl_resultado_priv.configure(text=t("fondo_limpiando"))

        def worker():
            exito, msg, comando = priv.clear_browser_history(nombre)
            self.after(0, lambda: self._actualizar_label("lbl_resultado_priv", msg))
            self._log_dev(t("priv_log_historial", navegador=nombre), comando or "N/A", msg,
                          seccion=t("seccion_privacidad"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_borrar_cache(self, nombre):
        self.lbl_resultado_priv.configure(text=t("fondo_limpiando"))

        def worker():
            exito, liberado, msg = priv.clear_browser_cache(nombre)
            texto = (t("priv_cache_liberado", mensaje=msg, tamano=opt.format_bytes(liberado))
                     if exito else msg)
            self.after(0, lambda: self._actualizar_label("lbl_resultado_priv", texto))
            self._log_dev(t("priv_log_cache", navegador=nombre), t("priv_log_cache_cmd"), texto,
                          seccion=t("seccion_privacidad"), exito=exito, bytes_liberados=liberado)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Acción rápida (usada desde el Dashboard) ----------------
    def _accion_optimizacion_rapida(self):
        def worker():
            liberado_ram, procesos, cmd1 = opt.trim_process_memory()
            liberado_disco, archivos, cmd2 = opt.clear_temp_files()
            msg = t("dash_optimizacion_lista", procesos=procesos, ram=opt.format_bytes(liberado_ram),
                    archivos=archivos, disco=opt.format_bytes(liberado_disco))
            # BUG corregido: esto tocaba la etiqueta DESDE EL HILO del trabajo, y
            # ademas sin comprobar que siguiera viva. Si el usuario cambiaba de
            # pantalla mientras la tarea corria (limpiar temporales tarda lo suyo),
            # el widget ya no existia y el resultado se perdia en silencio.
            self.after(0, lambda: self._actualizar_label("lbl_resultado_user", msg))
            self._log_dev(t("dash_log_optimizacion"), f"{cmd1} + {cmd2}", msg, seccion=t("seccion_inicio"),
                          exito=True, bytes_liberados=liberado_disco, bytes_ram=liberado_ram,
                          archivos_afectados=procesos + archivos)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_user.configure(text=t("dash_optimizando"))

    def _accion_vaciar_papelera_user(self):
        """Mismo arreglo que en Optimizar: vaciar la papelera bloqueaba la
        ventana entera. Y este es el botón de Inicio, el primero que toca
        cualquiera al abrir la app."""
        def worker():
            exito, comando, liberado, elementos = opt.empty_recycle_bin()
            if exito and elementos == 0:
                msg = t("dash_papelera_vacia")
            elif exito:
                msg = t("dash_papelera_vaciada", tamano=opt.format_bytes(liberado), elementos=elementos)
            else:
                msg = t("dash_papelera_error")
            self.after(0, lambda: self._actualizar_label("lbl_resultado_user", msg))
            self._log_dev(t("dash_log_papelera"), comando, msg, seccion=t("seccion_inicio"),
                          exito=exito, bytes_liberados=liberado, archivos_afectados=elementos)
        threading.Thread(target=worker, daemon=True).start()
        self.lbl_resultado_user.configure(text=t("dash_vaciando_papelera"))

    # ---------------- Seguridad ----------------
    def mostrar_seguridad(self):
        self._limpiar_contenido()
        self._encabezado(t("seg_titulo"), t("seg_subtitulo"))

        self.pestana_seguridad = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("seg_tab_antivirus"), t("seg_tab_auditoria"), t("seg_tab_extensiones"), t("seg_tab_red"),
                    t("seg_tab_permisos"), t("seg_tab_firewall"), t("seg_tab_usuarios")],
            command=self._cambiar_pestana_seguridad)
        self.pestana_seguridad.set(t("seg_tab_antivirus"))
        self.pestana_seguridad.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.contenedor_seguridad = Caja(self.contenido)
        self.contenedor_seguridad.grid(row=2, column=0, columnspan=3, sticky="nswe")

        self._mostrar_antivirus()

    def _cambiar_pestana_seguridad(self, valor):
        """El texto de la pestaña está traducido: se resuelve contra las
        mismas claves con las que se construyó, y el `else` cae en Antivirus,
        que es la pestaña por defecto — nunca en una rama arbitraria."""
        if valor == t("seg_tab_auditoria"):
            self._mostrar_auditoria()
        elif valor == t("seg_tab_extensiones"):
            self._mostrar_extensiones()
        elif valor == t("seg_tab_red"):
            self._mostrar_red_programas()
        elif valor == t("seg_tab_permisos"):
            self._mostrar_permisos_privacidad()
        elif valor == t("seg_tab_firewall"):
            self._mostrar_firewall()
        elif valor == t("seg_tab_usuarios"):
            self._mostrar_usuarios_sistema()
        else:
            self._mostrar_antivirus()

    def _limpiar_contenedor_seguridad(self):
        self._vaciar_pestana(self.contenedor_seguridad)

    # ---- Antivirus (Windows Defender) ----
    def _mostrar_antivirus(self):
        """Seguridad → Protección (1.8.0): cómo está protegido el equipo
        (antivirus, cortafuegos, arranque seguro, control de cuentas,
        aislamiento del núcleo), si alguien secuestró el navegador o la
        conexión (hosts, proxy, DNS, certificados, directivas), y Defender,
        explicando por qué sale apagado cuando otro antivirus manda (antes
        decía "Protección activa: No" y nada más). Todo solo lee."""
        cuerpo = self._lista_pestana(self.contenedor_seguridad)

        panel, derecha = tarjeta_seccion(cuerpo, t("prot_titulo"), "seguridad", t("prot_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_proteccion = pildora(derecha)
        self.pild_proteccion.pack(side="right")
        self.caja_proteccion = Caja(panel)
        self.caja_proteccion.pack(fill="x", pady=(0, 10))
        Texto(self.caja_proteccion, t("seg_leyendo_estado"), size=12, color=T.texto2).pack(fill="x", padx=18)

        panel, derecha = tarjeta_seccion(cuerpo, t("sec_titulo"), "globo", t("sec_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_secuestros = pildora(derecha)
        self.pild_secuestros.pack(side="right")
        self.caja_secuestros = Caja(panel)
        self.caja_secuestros.pack(fill="x", pady=(0, 10))
        Texto(self.caja_secuestros, t("seg_leyendo_estado"), size=12, color=T.texto2).pack(fill="x", padx=18)

        panel, derecha = tarjeta_seccion(cuerpo, _sin_emoji(t("seg_defender_titulo")), "seguridad")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        boton_secundario(derecha, _sin_emoji(t("seg_btn_escaneo_completo")),
                         lambda: self._accion_escanear_defender("completo"), height=32).pack(side="right")
        ctk.CTkButton(derecha, text=_sin_emoji(t("seg_btn_escaneo_rapido")), height=32,
                      command=lambda: self._accion_escanear_defender("rapido")).pack(side="right", padx=(0, 8))
        self.lbl_estado_defender = Texto(panel, t("seg_leyendo_estado"), size=12, color=T.texto2, wraplength=760)
        self.lbl_estado_defender.pack(fill="x", padx=18, pady=(0, 4))
        texto_fluido(self.lbl_estado_defender, panel, 36)
        self.lbl_defender_pasivo = Texto(panel, "", size=12, color=T.aviso, wraplength=760)
        self.lbl_defender_pasivo.pack(fill="x", padx=18)
        texto_fluido(self.lbl_defender_pasivo, panel, 36)
        texto_fluido(Texto(panel, t("seg_escaneo_nota"), size=11, color=T.texto3, wraplength=760), panel, 36).pack(
            fill="x", padx=18, pady=(4, 16))

        panel, _ = tarjeta_seccion(cuerpo, _sin_emoji(t("seg_cifrado_titulo")), "desbloquear")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lbl_estado_bitlocker_hello = Texto(panel, t("seg_leyendo_estado"), size=12, color=T.texto2,
                                                wraplength=760)
        self.lbl_estado_bitlocker_hello.pack(fill="x", padx=18, pady=(0, 16))
        texto_fluido(self.lbl_estado_bitlocker_hello, panel, 36)

        def worker():
            datos = {"proteccion": seg.leer_proteccion(), "secuestros": seg.chequeo_secuestros()}
            self.after(0, lambda: self._pintar_proteccion(datos))
            estado = opt.obtener_estado_defender()
            self.after(0, lambda: self._pintar_estado_defender(estado, datos["proteccion"]))
        threading.Thread(target=worker, daemon=True).start()

        def worker2():
            bitlocker = opt.obtener_estado_bitlocker()
            hello = opt.obtener_estado_windows_hello()
            self.after(0, lambda: self._pintar_bitlocker_hello(bitlocker, hello))
        threading.Thread(target=worker2, daemon=True).start()

    FILAS_PROTECCION = {
        "antivirus": ("seguridad", "prot_t_antivirus"), "cortafuegos": ("globo", "prot_t_cortafuegos"),
        "arranque": ("energia", "prot_t_arranque"), "uac": ("desbloquear", "prot_t_uac"),
        "aislamiento": ("componentes", "prot_t_aislamiento"), "hosts": ("archivo", "sec_t_hosts"),
        "proxy": ("globo", "sec_t_proxy"), "dns": ("globo", "sec_t_dns"),
        "certificados": ("seguridad", "sec_t_certificados"), "navegador": ("buscar", "sec_t_navegador"),
    }
    TEXTO_NIVEL = {"bien": "comp_salud_bien", "atencion": "comp_salud_atencion", "critico": "fallos_grave",
                   "info": "prot_info"}

    def _pintar_filas_estado(self, caja, pildora_total, filas):
        for w in caja.winfo_children():
            w.destroy()
        orden = ["bien", "info", "atencion", "critico"]
        peor = max((f[1] for f in filas), key=orden.index, default="bien")
        poner_pildora(pildora_total, t(self.TEXTO_NIVEL[peor]), peor if peor != "info" else "bien")
        color = {"bien": T.ok, "atencion": T.aviso, "critico": T.critico}
        lista = []
        for clave, nivel, texto, campos in filas:
            icono, titulo = self.FILAS_PROTECCION[clave]
            explicacion = t(texto, **campos)
            lista.append({"icono": icono, "color_icono": {"critico": T.critico, "atencion": T.aviso}.get(nivel),
                          "titulo": t(titulo), "detalle": explicacion,
                          "valor": t(self.TEXTO_NIVEL[nivel]), "color_valor": color.get(nivel, T.texto2),
                          # La explicación entera, por si no cabe en la fila.
                          "pulsar": lambda ti=t(titulo), ex=explicacion: self._mostrar_popup_info(ti, ex)})
        lienzo = ListaLienzo(caja, margen=18)
        lienzo.pack(fill="x")
        lienzo.poner(lista)

    def _pintar_proteccion(self, datos):
        if not (hasattr(self, "caja_proteccion") and self.caja_proteccion.winfo_exists()):
            return
        self._pintar_filas_estado(self.caja_proteccion, self.pild_proteccion,
                                  seg.evaluar_proteccion(datos["proteccion"]))
        self._pintar_filas_estado(self.caja_secuestros, self.pild_secuestros,
                                  seg.evaluar_secuestros(datos["secuestros"]))

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

    def _pintar_estado_defender(self, estado, proteccion=None):
        if not (hasattr(self, "lbl_estado_defender") and self.lbl_estado_defender.winfo_exists()):
            return
        # Con otro antivirus al mando, Defender se apaga solo: es lo normal,
        # no un fallo. Se dice, en vez de enseñar "Protección activa: No".
        otro = next((a for a in (proteccion or {}).get("antivirus") or []
                     if a["activo"] and "defender" not in a["nombre"].lower()), None)
        if otro and estado is not None and not estado["activo"] and hasattr(self, "lbl_defender_pasivo"):
            self.lbl_defender_pasivo.configure(text=t("seg_defender_pasivo", nombre=otro["nombre"]))
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
        # Lanzar el escaneo tarda: va en un hilo para no congelar la ventana.
        tipo_txt = t("seg_tipo_completo") if tipo == "completo" else t("seg_tipo_rapido")

        def worker():
            exito, comando = opt.iniciar_escaneo_defender(tipo)
            msg = t("seg_escaneo_iniciado", tipo=tipo_txt) if exito else t("seg_escaneo_error")
            self.after(0, lambda: self._mostrar_popup_info("Windows Defender", msg))
            self._log_dev(t("seg_log_escaneo", tipo=tipo_txt), comando, msg,
                          seccion=t("seccion_seguridad"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Permisos de privacidad (cámara/micrófono/ubicación) ----
    def _mostrar_permisos_privacidad(self):
        lista = self._lista_pestana(self.contenedor_seguridad)
        panel, _ = tarjeta_seccion(lista, t("seg_tab_permisos"), "privacidad", t("seg_permisos_nota"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pestana_permiso = ctk.CTkSegmentedButton(
            panel, values=[t("seg_perm_camara"), t("seg_perm_microfono"), t("seg_perm_ubicacion")],
            command=lambda v: self._cargar_permisos_privacidad())
        self.pestana_permiso.set(t("seg_perm_camara"))
        self.pestana_permiso.pack(anchor="w", padx=18, pady=(0, 8))
        self.lista_permisos = ListaLienzo(panel)
        self.lista_permisos.pack(fill="x", pady=(0, 10))
        self._cargar_permisos_privacidad()

    def _cargar_permisos_privacidad(self):
        self.lista_permisos.poner([{"titulo": t("seg_leyendo_permisos"), "negrita": False, "color_titulo": T.texto2}])

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
        lienzo = getattr(self, "lista_permisos", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        if not permisos:
            lienzo.poner([{"titulo": t("seg_sin_permisos"), "negrita": False, "color_titulo": T.texto2}])
            return
        filas = []
        for p in permisos:
            # opt devuelve un codigo estable ("permitido"/"bloqueado"/otro);
            # el color y el texto visible se derivan aqui.
            estado_txt = {
                "permitido": t("seg_permiso_permitido"),
                "bloqueado": t("seg_permiso_bloqueado"),
            }.get(p["estado"], t("seg_permiso_desconocido"))
            color = T.ok if p["estado"] == "permitido" else (T.critico if p["estado"] == "bloqueado" else T.texto2)
            filas.append({"icono": "aplicaciones", "titulo": p["app"], "valor": estado_txt, "color_valor": color})
        lienzo.poner(filas)

    # ---- Firewall ----
    def _mostrar_firewall(self):
        lista = self._lista_pestana(self.contenedor_seguridad, t("seg_firewall_intro"))
        panel, derecha = tarjeta_seccion(lista, t("seg_tab_firewall"), "seguridad")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        ctk.CTkButton(derecha, text=_sin_emoji(t("seg_btn_bloquear")), height=32,
                      command=self._accion_elegir_bloquear_app).pack(side="right")
        self.lista_firewall = ListaLienzo(panel)
        self.lista_firewall.pack(fill="x", pady=(0, 10))
        self.lista_firewall.poner([{"titulo": t("seg_leyendo_reglas"), "negrita": False, "color_titulo": T.texto2}])

        def worker():
            reglas = opt.listar_reglas_firewall_bloqueadas()
            self.after(0, lambda: self._pintar_firewall(reglas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_firewall(self, reglas):
        lienzo = getattr(self, "lista_firewall", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        if not reglas:
            lienzo.poner([{"titulo": t("seg_sin_reglas"), "negrita": False, "color_titulo": T.texto2}])
            return
        lienzo.poner([{"icono": "seguridad", "titulo": r["nombre"], "detalle": r["direccion"],
                       # Solo las reglas que creó TechClean se pueden quitar desde aquí.
                       "acciones": [(t("seg_btn_desbloquear"), lambda n=r["nombre"]: self._accion_desbloquear_app(n))]
                       if str(r["nombre"]).startswith("TechClean-Bloqueo-") else []} for r in reglas])

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
        lista = self._lista_pestana(self.contenedor_seguridad, t("seg_usuarios_intro"))
        panel, _ = tarjeta_seccion(lista, t("seg_tab_usuarios"), "privacidad")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_usuarios = ListaLienzo(panel)
        self.lista_usuarios.pack(fill="x", pady=(0, 10))
        self.lista_usuarios.poner([{"titulo": t("seg_leyendo_usuarios"), "negrita": False, "color_titulo": T.texto2}])

        def worker():
            usuarios = opt.listar_usuarios_sistema()
            self.after(0, lambda: self._pintar_usuarios_sistema(usuarios))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_usuarios_sistema(self, usuarios):
        lienzo = getattr(self, "lista_usuarios", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        filas = []
        for u in usuarios or []:
            # Con .get() y no con corchetes: esta lista sale de parsear la
            # salida de Get-LocalUser, y una cuenta sin nombre —o con la
            # forma distinta que puede traer otra edición de Windows— haría
            # saltar un KeyError que se lleva por delante toda la pestaña.
            # Mejor mostrar la fila incompleta que no mostrar ninguna.
            nombre = u.get("nombre")
            if not nombre:
                continue
            habilitada = u.get("habilitada", True)
            etiquetas = [t("seg_admin") if u.get("es_admin") else t("seg_estandar"),
                         t("seg_habilitada") if habilitada else t("seg_deshabilitada")]
            filas.append({"icono": "privacidad", "color_icono": T.acento if habilitada else T.texto3,
                          "titulo": nombre + (t("seg_usuario_tu") if u.get("es_actual") else ""),
                          "color_titulo": T.texto if habilitada else T.texto2,
                          "detalle": "  ·  ".join(etiquetas)})
        lienzo.poner(filas or [{"titulo": t("seg_sin_usuarios"), "negrita": False, "color_titulo": T.texto2}])

    # ---- Optimizar unidades ----
    def _cargar_unidades(self):
        for w in self.lista_unidades.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_unidades, text=t("comun_cargando"), text_color=T.texto2).pack(anchor="w")

        def worker():
            unidades = opt.listar_unidades_optimizables()
            self.after(0, lambda: self._pintar_unidades(unidades))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_unidades(self, unidades):
        if not (hasattr(self, "lista_unidades") and self.lista_unidades.winfo_exists()):
            return
        for w in self.lista_unidades.winfo_children():
            w.destroy()
        if not unidades:
            ctk.CTkLabel(self.lista_unidades, text=t("unid_ninguna"), text_color=T.texto2).pack(anchor="w")
            return
        corriendo = getattr(self, "_unidad_en_curso", None)
        self._botones_unidades = {}
        for u in unidades:
            fila = ctk.CTkFrame(self.lista_unidades, fg_color=T.fila, corner_radius=T.radio_fila)
            fila.pack(fill="x", pady=3)
            tipo = {"SSD": t("unid_tipo_ssd"), "HDD": t("unid_tipo_hdd")}.get(u["tipo"], t("unid_tipo_otro"))
            ctk.CTkLabel(fila, text=f'{u["letra"]}:   {tipo}', font=fuente(size=13, weight="bold"),
                         anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(fila, text=t("unid_espacio", libre=opt.format_bytes(u["libre"]),
                                      total=opt.format_bytes(u["tamano"])),
                         font=fuente(size=11), text_color=T.texto2).pack(side="left", padx=8)
            texto = {"SSD": t("unid_btn_trim"), "HDD": t("unid_btn_desfrag")}.get(u["tipo"], t("unid_btn_optimizar"))
            boton = ctk.CTkButton(fila, text=texto, width=150,
                                  command=lambda l=u["letra"], tp=u["tipo"]: self._accion_optimizar_unidad(l, tp))
            boton.pack(side="right", padx=10, pady=6)
            self._botones_unidades[u["letra"]] = (boton, texto, boton.cget("fg_color"), boton.cget("text_color"))
        if corriendo:
            self._marcar_unidad_corriendo(corriendo)

    def _marcar_unidad_corriendo(self, letra):
        """Mientras una unidad se optimiza, su botón pasa a Cancelar y los
        demás se apagan: dos optimizaciones a la vez solo se estorban."""
        for l, (boton, texto, color, color_texto) in getattr(self, "_botones_unidades", {}).items():
            try:
                if not boton.winfo_exists():
                    continue
                if letra is None:
                    boton.configure(state="normal", text=texto, fg_color=color, text_color=color_texto)
                elif l == letra:
                    boton.configure(state="normal", text=t("fondo_dism_cancelar"), fg_color=COLOR_WARN,
                                    text_color=T.sobre_aviso)
                else:
                    boton.configure(state="disabled")
            except Exception:
                pass

    def _accion_optimizar_unidad(self, letra, tipo):
        if getattr(self, "_unidad_en_curso", None):
            self._evento_unidad.set()
            self._actualizar_label("lbl_unidades", t("fondo_dism_cancelando"))
            return
        self._unidad_en_curso = letra
        self._evento_unidad = threading.Event()
        self._marcar_unidad_corriendo(letra)
        clave_curso = "unid_en_curso_hdd" if tipo == "HDD" else "unid_en_curso"
        self.lbl_unidades.configure(text=t(clave_curso, letra=letra, minutos=0))

        def progreso(segundos):
            texto = t(clave_curso, letra=letra, minutos=int(segundos // 60))
            self.after(0, lambda: self._actualizar_label("lbl_unidades", texto))

        def worker():
            exito, resumen, cancelado = opt.optimizar_unidad(letra, callback_progreso=progreso,
                                                             evento_cancelar=self._evento_unidad)
            msg = (t("unid_cancelado", letra=letra) if cancelado
                   else t("unid_listo", letra=letra) if exito
                   else t("unid_error", letra=letra))
            self._log_dev(t("unid_log", letra=letra), f"Optimize-Volume -DriveLetter {letra} -Verbose",
                          msg + "\n" + resumen, seccion=t("seccion_optimizador"), exito=exito)

            def terminar():
                self._unidad_en_curso = None
                self._actualizar_label("lbl_unidades", msg)
                self._marcar_unidad_corriendo(None)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- DNS más rápido ----
    def _accion_comparar_dns(self):
        if getattr(self, "_dns_midiendo", False):
            return
        self._dns_midiendo = True
        self.btn_comparar_dns.configure(state="disabled")
        for w in self.lista_dns.winfo_children():
            w.destroy()
        self.lbl_dns.configure(text=t("dns_midiendo", actual=1, total="…", nombre=""))

        def progreso(i, total, nombre):
            texto = t("dns_midiendo", actual=i + 1, total=total, nombre=nombre)
            self.after(0, lambda: self._actualizar_label("lbl_dns", texto))

        def worker():
            resultados = opt.comparar_dns(callback_progreso=progreso)
            self.after(0, lambda: self._pintar_dns(resultados))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_dns(self, resultados):
        self._dns_midiendo = False
        if not (hasattr(self, "lista_dns") and self.lista_dns.winfo_exists()):
            return
        self.btn_comparar_dns.configure(state="normal")
        for w in self.lista_dns.winfo_children():
            w.destroy()
        validos = [r for r in resultados if r["ms"] is not None]
        if not validos:
            self.lbl_dns.configure(text=t("dns_sin_respuesta"))
            return
        actual = next((r for r in resultados if r["clave"] == "actual"), None)
        mejor = validos[0]
        for r in resultados:
            fila = ctk.CTkFrame(self.lista_dns, fg_color=T.fila, corner_radius=T.radio_boton)
            fila.pack(fill="x", pady=2)
            nombre = r["nombre"] + (f'  ({r["ip"]})' if r["clave"] == "actual" else "")
            ctk.CTkLabel(fila, text=nombre, font=fuente(size=12, weight="bold" if r is mejor else "normal"),
                         anchor="w").pack(side="left", padx=10, pady=6)
            ms = t("dns_ms", ms=f'{r["ms"]:.0f}') if r["ms"] is not None else t("dns_no_contesta")
            ctk.CTkLabel(fila, text=ms, font=fuente(size=12),
                         text_color=COLOR_OK if r is mejor else T.texto2).pack(side="left", padx=8)
            if r["clave"] != "actual" and r["ms"] is not None:
                ctk.CTkButton(fila, text=t("dns_btn_usar"), width=110,
                              command=lambda c=r["clave"], n=r["nombre"]: self._confirmar_aplicar_dns(c, n)).pack(
                    side="right", padx=8, pady=4)

        # Solo se recomienda cambiar si la mejora se nota: 10 ms por consulta
        # no los percibe nadie, y cambiar el DNS tiene sus propios riesgos.
        if actual is None or actual["ms"] is None:
            self.lbl_dns.configure(text=t("dns_recomienda", nombre=mejor["nombre"]))
        elif mejor is actual or actual["ms"] - mejor["ms"] < max(10, actual["ms"] * 0.25):
            self.lbl_dns.configure(text=t("dns_actual_bien", ms=f'{actual["ms"]:.0f}'))
        else:
            self.lbl_dns.configure(text=t("dns_recomienda_mejora", nombre=mejor["nombre"],
                                          ms=f'{actual["ms"] - mejor["ms"]:.0f}'))

    def _confirmar_aplicar_dns(self, clave, nombre):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("480x230")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("dns_confirmar", nombre=nombre), font=fuente(size=13),
                     wraplength=440, justify="left").pack(padx=20, pady=(20, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            self._accion_aplicar_dns(clave, nombre)
        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(
            side="left", padx=8)
        ctk.CTkButton(fila, text=t("dns_btn_usar"), command=confirmar).pack(side="left", padx=8)

    def _accion_aplicar_dns(self, clave, nombre):
        self.lbl_dns.configure(text=t("dns_aplicando", nombre=nombre))

        def worker():
            exito, comando, anterior = opt.aplicar_dns(clave)
            msg = t("dns_aplicado", nombre=nombre) if exito else t("dns_error")
            if exito:
                self.deshacer.anotar("dns", {"adaptadores": anterior, "nuevo": clave},
                                     t("desh_desc_dns", nombre=nombre))
            self._log_dev(t("dns_log", nombre=nombre), comando, msg, seccion=t("seccion_reparar"), exito=exito)
            self.after(0, lambda: self._actualizar_label("lbl_dns", msg))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Reparar ----------------
    def mostrar_reparar(self):
        """Reparar (rediseño 1.8.0): el diagnóstico de fallos arriba (lo que
        Windows apuntó: apagados de golpe, pantallazos azules, programas que
        se cierran solos, daños en el disco) y las reparaciones en filas, cada
        una con su explicación al lado del botón. Antes eran nueve botones
        azules con el texto a la derecha, que se cortaba en ventanas
        estrechas."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("rep_titulo"), t("rep_intro"))
        boton_secundario(derecha, _sin_emoji(t("comun_ver_reporte")), self.mostrar_reporte, icono="historial",
                         height=38).pack(side="right")
        cuerpo = self._cuerpo()
        self.lbl_resultado_reparar = ctk.CTkLabel(cuerpo, text=t("rep_selecciona"), font=fuente(size=13),
                                                    wraplength=880, justify="left", anchor="w", fg_color=T.fila,
                                                    corner_radius=T.radio_fila, height=40)
        self.lbl_resultado_reparar.pack(fill="x", padx=8, pady=(0, 10), ipadx=12)

        # ---- Diagnóstico de fallos ----
        panel, derecha_t = tarjeta_seccion(cuerpo, t("fallos_titulo"), "seguridad",
                                           t("fallos_desc", dias=self.DIAS_FALLOS))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.pild_fallos = pildora(derecha_t)
        self.pild_fallos.pack(side="right")
        self.btn_fallos = boton_secundario(derecha_t, t("fallos_btn_actualizar"), self._cargar_diagnostico_fallos,
                                           height=30)
        self.btn_fallos.pack(side="right", padx=(0, 10))
        self.panel_fallos = ListaDatos(panel)
        self.panel_fallos.pack(fill="x", padx=18)
        self.caja_fallos = Caja(panel)
        self.caja_fallos.pack(fill="x", padx=18, pady=(4, 0))
        self.lbl_fallos = Texto(panel, t("fallos_analizando"), size=12, color=T.texto2, wraplength=760)
        self.lbl_fallos.pack(fill="x", padx=18, pady=(6, 16))
        texto_fluido(self.lbl_fallos, panel, 36)
        self._cargar_diagnostico_fallos()

        # ---- Reparar Windows ----
        panel, _ = tarjeta_seccion(cuerpo, t("rep_sec_windows"), "reparar")
        panel.pack(fill="x", padx=8, pady=(0, 12))
        acciones = (
            ("archivo", "rep_btn_sfc", "rep_desc_sfc", "rep_accion_reparar", self._accion_reparar_sfc),
            ("buscar", "rep_btn_scanhealth", "rep_desc_scanhealth", "rep_accion_revisar",
             self._accion_revisar_salud_imagen),
            ("disco", "rep_btn_dism", "rep_desc_dism", "rep_accion_reparar", self._accion_reparar_dism),
            ("monitor", "rep_btn_explorador", "rep_desc_explorador", "rep_accion_reiniciar",
             self._accion_reiniciar_explorador),
            ("aplicaciones", "rep_btn_store", "rep_desc_store", "rep_accion_reparar", self._accion_reparar_store),
            ("historial", "rep_btn_updates", "rep_desc_updates", "rep_accion_buscar",
             self._accion_buscar_actualizaciones),
            ("calendario", "rep_btn_disco", "rep_desc_disco", "rep_accion_programar", self._accion_revisar_disco),
        )
        for i, (icono, titulo, desc, boton, comando) in enumerate(acciones):
            fila_accion(panel, icono, t(titulo), t(desc), t(boton), comando, primera=i == 0)
        Caja(panel, height=6).pack()

        # ---- Red e internet ----
        panel, _ = tarjeta_seccion(cuerpo, t("rep_sec_red"), "globo")
        panel.pack(fill="x", padx=8, pady=(0, 12))
        fila_accion(panel, "globo", t("rep_btn_red"), t("rep_desc_red"), t("rep_accion_reparar"),
                    self._accion_reparar_red, primera=True)
        fila_accion(panel, "componentes", t("rep_btn_adaptador"), t("rep_desc_adaptador"), t("rep_accion_elegir"),
                    self._accion_elegir_adaptador)
        self.btn_comparar_dns = fila_accion(panel, "optimizar", t("dns_titulo"), t("dns_desc"),
                                            t("rep_accion_comparar"), self._accion_comparar_dns)
        self.lista_dns = Caja(panel)
        self.lista_dns.pack(fill="x", padx=20)
        self.lbl_dns = Texto(panel, "", size=12, wraplength=760)
        self.lbl_dns.pack(fill="x", padx=20, pady=(4, 14))
        texto_fluido(self.lbl_dns, panel, 40)

        # ---- Puntos de restauración ----
        panel, derecha_t = tarjeta_seccion(cuerpo, _sin_emoji(t("puntos_titulo")), "historial", t("puntos_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.btn_borrar_puntos = boton_secundario(derecha_t, t("puntos_btn_borrar"), self._confirmar_borrar_puntos,
                                                  height=32, state="disabled")
        self.btn_borrar_puntos.pack(side="right")
        ctk.CTkButton(derecha_t, text=t("puntos_btn_crear"), height=32,
                      command=self._accion_crear_punto).pack(side="right", padx=(0, 8))
        self.lista_puntos = Caja(panel)
        self.lista_puntos.pack(fill="x", padx=18)
        self.lbl_puntos = Texto(panel, "", size=12, wraplength=760)
        self.lbl_puntos.pack(fill="x", padx=18, pady=(4, 4))
        texto_fluido(self.lbl_puntos, panel, 36)
        self.switch_punto_restauracion, _ = fila_interruptor(
            panel, "seguridad", t("rep_switch_punto"), t("rep_punto_desc"),
            self.prefs.get("crear_punto_restauracion", True), self._toggle_punto_restauracion, margen=18)
        self._cargar_puntos()

        # ---- Para equipos justos de recursos ----
        panel, _ = tarjeta_seccion(cuerpo, _sin_emoji(t("rep_rend_titulo")), "memoria", t("rep_rend_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        fila_accion(panel, "imagen", t("rep_btn_efectos"), t("rep_desc_efectos"), t("rep_accion_abrir"),
                    self._accion_abrir_efectos_visuales, primera=True)
        fila_accion(panel, "optimizar", t("rep_btn_animaciones"), t("rep_desc_animaciones"), t("rep_accion_aplicar"),
                    self._accion_reducir_animaciones)
        self.switch_indexacion, derecha_idx = fila_interruptor(
            panel, "buscar", t("rep_indexacion_label").rstrip(": "), t("rep_indexacion_desc"), False,
            self._toggle_indexacion_busqueda)
        self.lbl_estado_indexacion = Texto(derecha_idx, t("rep_leyendo_minus"), size=12, color=T.texto2)
        self.lbl_estado_indexacion.pack(side="right", padx=(0, 10))
        Caja(panel, height=6).pack()

        def worker_indexacion():
            estado = opt.obtener_estado_indexacion()
            self.after(0, lambda: self._pintar_estado_indexacion(estado))
        threading.Thread(target=worker_indexacion, daemon=True).start()

    DIAS_FALLOS = 30

    def _cargar_diagnostico_fallos(self):
        """El registro de eventos se lee en un hilo (PowerShell, 2-3 s)."""
        if getattr(self, "_fallos_leyendo", False):
            return
        self._fallos_leyendo = True
        self._actualizar_label("lbl_fallos", t("fallos_analizando"))

        def worker():
            try:
                diag = tec.diagnostico_fallos(self.DIAS_FALLOS)
            finally:
                self._fallos_leyendo = False
            self.after(0, lambda: self._pintar_diagnostico_fallos(diag))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_diagnostico_fallos(self, diag):
        if not (hasattr(self, "panel_fallos") and self.panel_fallos.winfo_exists()):
            return
        for w in self.caja_fallos.winfo_children():
            w.destroy()
        if diag is None:
            poner_pildora(self.pild_fallos, "")
            self.lbl_fallos.configure(text=t("fallos_error"))
            return
        nivel, motivos = tec.veredicto_fallos(diag)
        poner_pildora(self.pild_fallos, t({"bien": "comp_salud_bien", "atencion": "comp_salud_atencion",
                                           "critico": "fallos_grave"}[nivel]), nivel)
        apagados = diag["apagados"]
        en_suspension = sum(1 for a in apagados if a["suspension"])
        self.panel_fallos.poner("apagados", t("fallos_d_apagados"),
                                t("fallos_v_apagados", n=len(apagados), suspension=en_suspension)
                                if en_suspension else str(len(apagados)),
                                T.aviso if len(apagados) >= 3 else T.texto)
        self.panel_fallos.poner("pantallazos", t("fallos_d_pantallazos"), str(len(diag["pantallazos"])),
                                T.aviso if diag["pantallazos"] else T.texto)
        apps = [a for a in diag["apps"] if a["nombre"]]
        total_apps = sum(a["veces"] for a in diag["apps"])
        self.panel_fallos.poner("apps", t("fallos_d_apps"),
                                t("fallos_v_apps", n=total_apps, nombre=apps[0]["nombre"], veces=apps[0]["veces"])
                                if apps else str(total_apps))
        self.panel_fallos.poner("hardware", t("fallos_d_hardware"), str(diag["hardware"]),
                                T.critico if diag["hardware"] else T.texto)
        self.panel_fallos.poner("disco", t("fallos_d_disco"), str(diag["disco"]),
                                T.aviso if diag["disco"] else T.texto)

        # Cada pantallazo, con lo que suele haber detrás.
        for p in diag["pantallazos"][:4]:
            codigo = f'0x{p["codigo"]:X}' if p["codigo"] else ""
            texto = t("fallos_linea_pantallazo", fecha=p["fecha"], codigo=codigo, nombre=p["nombre"] or "",
                      causa=t(p["causa"]))
            if p.get("suspension"):
                texto += " " + t("fallos_durante_suspension")
            texto_fluido(Texto(self.caja_fallos, texto, size=12, color=T.aviso, wraplength=760),
                         self.caja_fallos, 4).pack(fill="x", pady=(6, 0))
        if diag.get("volcado_fallido") and diag["pantallazos"]:
            texto_fluido(Texto(self.caja_fallos, t("fallos_volcado"), size=11, color=T.texto3, wraplength=760),
                         self.caja_fallos, 4).pack(fill="x", pady=(2, 0))
        # Un daño en el sistema de archivos se arregla revisando la unidad.
        for d in diag.get("sistema_archivos") or []:
            unidad = d["unidad"]
            presente = len(unidad) == 2 and os.path.exists(unidad + "\\")
            fila_d = Caja(self.caja_fallos)
            fila_d.pack(fill="x", pady=(8, 0))
            if presente:
                boton_secundario(fila_d, t("fallos_btn_revisar", unidad=unidad),
                                 lambda u=unidad: self._accion_revisar_unidad(u), height=30).pack(side="right")
            texto = t("fallos_linea_ntfs", unidad=unidad, fecha=d["fecha"][:10]) + " " + (
                t("fallos_ntfs_presente") if presente else t("fallos_ntfs_desconectada", unidad=unidad))
            texto_fluido(Texto(fila_d, texto, size=12, color=T.aviso, wraplength=640), fila_d, 150).pack(
                side="left", fill="x", expand=True)
        consejos = [t(m) for m in motivos] or [t("fallos_bien", dias=diag["dias"])]
        self.lbl_fallos.configure(text="\n".join("• " + c for c in consejos) if motivos else consejos[0],
                                  text_color=T.texto if motivos else T.ok)

    def _accion_revisar_unidad(self, unidad):
        """Marca la unidad para que Windows la revise (chkdsk) al reiniciar."""
        self.lbl_resultado_reparar.configure(text=t("rep_programando"))

        def worker():
            exito, comando = opt.revisar_disco_en_reinicio(unidad)
            msg = t("fallos_revisar_ok", unidad=unidad) if exito else t("rep_disco_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_disco"), comando, msg, seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

    def _toggle_punto_restauracion(self):
        valor = self.switch_punto_restauracion.get()
        self.prefs["crear_punto_restauracion"] = valor
        prefs.guardar({"crear_punto_restauracion": valor})

    def _actualizar_label(self, nombre, texto):
        """Escribe en una etiqueta SOLO si sigue viva.

        Los trabajos de fondo pueden terminar DESPUES de que el usuario
        cambio de pantalla, y para entonces el widget ya fue destruido:
        tocarlo lanza TclError, y como la app atrapa todo error no
        controlado, al usuario le salta una ventana de error alarmante por
        algo que no hizo mal. hasattr() no alcanza — el atributo sigue
        existiendo aunque el widget este destruido."""
        widget = getattr(self, nombre, None)
        if widget is None:
            return
        try:
            if widget.winfo_exists():
                widget.configure(text=texto)
        except Exception:
            pass

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
        ctk.CTkLabel(dialogo, text=titulo, font=fuente(size=15, weight="bold")).pack(pady=(24, 8))
        lbl_tiempo = ctk.CTkLabel(dialogo, text=t("rep_tiempo", minutos=0, segundos="00"),
                                    font=fuente(size=20, weight="bold"))
        lbl_tiempo.pack(pady=(0, 6))
        ctk.CTkLabel(dialogo,
                     text=t("rep_larga_desc"),
                     font=fuente(size=11), text_color=T.texto2, wraplength=380, justify="center").pack(
            padx=20, pady=(0, 16))

        def cancelar():
            evento_cancelar.set()
            btn_cancelar.configure(state="disabled", text=t("rep_cancelando"))

        # La "X" de la ventana también cancela en vez de no hacer nada —
        # cerrar la ventana sin más dejaría el proceso corriendo sin
        # forma de volver a verlo ni de detenerlo.
        dialogo.protocol("WM_DELETE_WINDOW", cancelar)

        btn_cancelar = ctk.CTkButton(dialogo, text=t("comun_cancelar"), fg_color=T.peligro, hover_color=T.critico,
                                      command=cancelar, text_color=T.sobre_peligro)
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
                     font=fuente(size=14, weight="bold")).pack(pady=(16, 8))
        lista = ctk.CTkScrollableFrame(dialogo, fg_color=COLOR_BG_PANEL)
        lista.pack(fill="both", expand=True, padx=16, pady=8)
        for a in adaptadores:
            fila = ctk.CTkFrame(lista, fg_color=T.fila, corner_radius=T.radio_boton)
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(fila, text=t("rep_adaptador_detalle", nombre=a["nombre"],
                                      descripcion=a["descripcion"]), font=fuente(size=11),
                         anchor="w", wraplength=300, justify="left").pack(side="left", padx=8, pady=8, fill="x", expand=True)
            ctk.CTkButton(fila, text=t("rep_btn_reiniciar"), width=90,
                          command=lambda n=a["nombre"]: (dialogo.destroy(), self._accion_reiniciar_adaptador(n))).pack(
                side="right", padx=8, pady=6)
        ctk.CTkButton(dialogo, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(pady=(0, 12))

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
        def worker():
            exito, comando = opt.reparar_windows_store()
            msg = t("rep_store_ok") if exito else t("rep_store_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_store"), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

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
        """En un hilo, aunque parezca instantáneo: SystemParametersInfo con
        SPIF_SENDCHANGE avisa del cambio a TODAS las ventanas abiertas del
        escritorio y espera respuesta de cada una. Basta con que un programa
        cualquiera esté ocupado para que la llamada tarde varios segundos, y
        con esto en el hilo principal ese tiempo lo pagaba nuestra ventana."""
        def worker():
            exito, comando = opt.reducir_animaciones_ahora(activar_reduccion=True)
            if exito:
                # No hay forma fiable de leer el estado previo de estos dos
                # ajustes, asi que se asume lo normal: estaban activadas.
                # Deshacer las vuelve a activar, que es lo que quiere quien
                # pulsa deshacer aunque ya estuvieran reducidas.
                self.deshacer.anotar("animaciones", {"estaban_reducidas": False},
                                      t("desh_desc_animaciones"))
            msg = t("rep_animaciones_ok") if exito else t("rep_animaciones_error")
            self.after(0, lambda: self._actualizar_resultado_reparar(msg))
            self._log_dev(t("rep_log_animaciones"), comando, msg,
                          seccion=t("seccion_reparar"), exito=exito)
        threading.Thread(target=worker, daemon=True).start()

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
            self.after(0, lambda: self._actualizar_label(
                "lbl_estado_indexacion", t("rep_idx_activa") if activar else t("rep_idx_pausada")))
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
        self._encabezado(t("apps_titulo"), t("apps_subtitulo"))

        self.pestana_apps = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("apps_tab_inicio"), t("apps_tab_desinstalar"), t("apps_tab_bloat"), t("apps_tab_servicios"),
                    t("apps_tab_actualizar"), t("apps_tab_tareas")],
            command=self._cambiar_pestana_apps)
        self.pestana_apps.set(t("apps_tab_inicio"))
        self.pestana_apps.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.contenedor_apps = Caja(self.contenido)
        self.contenedor_apps.grid(row=2, column=0, columnspan=3, sticky="nswe")

        self._mostrar_inicio_windows()

    def _cambiar_pestana_apps(self, valor):
        """El texto de la pestaña está traducido: se resuelve contra las
        mismas claves con las que se construyó, y el `else` cae en Inicio de
        Windows, que es la pestaña por defecto."""
        if valor == t("apps_tab_desinstalar"):
            self._mostrar_desinstalador()
        elif valor == t("apps_tab_bloat"):
            self._mostrar_bloatware()
        elif valor == t("apps_tab_servicios"):
            self._mostrar_servicios()
        elif valor == t("apps_tab_actualizar"):
            self._mostrar_actualizar_apps()
        elif valor == t("apps_tab_tareas"):
            self._mostrar_tareas_programadas()
        else:
            self._mostrar_inicio_windows()

    def _limpiar_contenedor_apps(self):
        self._vaciar_pestana(self.contenedor_apps)

    def _mostrar_inicio_windows(self):
        """Todo lo que arranca con Windows (1.8.0): las claves Run de tu
        usuario y de todos (también las de 32 bits), las carpetas de Inicio y
        las tareas programadas al iniciar sesión. Se activa y desactiva con
        el mismo interruptor que usa el Administrador de tareas, y lo que
        parece sospechoso se marca con las reglas de la auditoría de
        seguridad (hasta la 1.7.0, la tarea del malware del equipo del
        desarrollador ni salía aquí)."""
        self._limpiar_contenedor_apps()
        texto_fluido(Texto(self.contenedor_apps, t("apps_inicio_intro"), size=12, color=T.texto2, wraplength=900),
                     self.contenedor_apps, 4).pack(fill="x", pady=(0, 10))
        lista = ctk.CTkScrollableFrame(self.contenedor_apps, fg_color="transparent")
        lista.pack(fill="both", expand=True)
        self.lista_inicio_frame = lista
        panel, derecha = tarjeta_seccion(lista, t("apps_inicio_titulo"), "inicio")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_inicio = pildora(derecha)
        self.pild_inicio.pack(side="right")
        self.lbl_inicio_resumen = Texto(panel, t("apps_cargando_inicio"), size=12, color=T.texto2, wraplength=760)
        self.lbl_inicio_resumen.pack(fill="x", padx=18, pady=(0, 6))
        texto_fluido(self.lbl_inicio_resumen, panel, 36)
        self.caja_inicio = Caja(panel)
        self.caja_inicio.pack(fill="x", pady=(0, 10))
        self._generacion_inicio = getattr(self, "_generacion_inicio", 0) + 1
        generacion = self._generacion_inicio

        # Primero lo rápido (registro y carpetas: milisegundos); después las
        # tareas programadas y quién firma cada programa (PowerShell: varios
        # segundos), y se vuelve a pintar con todo.
        def worker():
            entradas = opt.listar_inicio_completo()
            self.after(0, lambda: self._pintar_inicio_completo(entradas, generacion, completo=False))
            entradas = entradas + opt.listar_tareas_inicio()
            try:
                seg.evaluar_inicio(entradas)
            except Exception:
                pass
            self.after(0, lambda: self._pintar_inicio_completo(entradas, generacion, completo=True))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_inicio_completo(self, entradas, generacion, completo):
        if generacion != getattr(self, "_generacion_inicio", 0) or not (
                hasattr(self, "caja_inicio") and self.caja_inicio.winfo_exists()):
            return
        for w in self.caja_inicio.winfo_children():
            w.destroy()
        self._entradas_inicio = entradas
        orden = {"alto": 0, "medio": 1}
        entradas = sorted(entradas, key=lambda e: (orden.get(e.get("riesgo"), 2), not e["activo"],
                                                   e["nombre"].lower()))
        activos = sum(1 for e in entradas if e["activo"])
        sospechosos = sum(1 for e in entradas if e.get("riesgo") in ("alto", "medio"))
        resumen = t("apps_inicio_resumen", n=len(entradas), activos=activos)
        if not completo:
            resumen += " " + t("apps_inicio_revisando")
        self.lbl_inicio_resumen.configure(text=resumen)
        if sospechosos:
            poner_pildora(self.pild_inicio, t("apps_inicio_sospechosos", n=sospechosos), "critico")
        else:
            poner_pildora(self.pild_inicio, t("apps_inicio_activos", n=activos), "info")
        if not entradas:
            Texto(self.caja_inicio, t("apps_sin_inicio"), size=12, color=T.texto2).pack(fill="x", padx=18)
            return
        etiquetas = {"tarea": "apps_tag_tarea", "carpeta": "apps_tag_carpeta", "techclean": "apps_tag_techclean"}
        filas = []
        for e in entradas:
            sospechoso = e.get("riesgo") in ("alto", "medio")
            quien = e.get("firmante") or e.get("producto") or (t("apps_sin_firma") if completo and e.get("existe") else "")
            programa = e.get("programa") or e.get("exe") or ""
            notas = []
            if sospechoso:
                original = e.get("original") or "?"
                notas.append(t("apps_tag_sospechoso") + ": " + " ".join(t(m, original=original)
                                                                        for m in e.get("motivos") or []))
            if completo and e.get("existe") is False:
                notas.append(t("apps_tag_no_existe"))
            extra = [t(etiquetas[e["tipo"]])] if e["tipo"] in etiquetas else []
            if e.get("todos"):
                extra.append(t("apps_tag_todos"))
            # En la fila, lo más importante en una línea (sospechoso, o que ya
            # no existe; si no, quién lo firma y dónde está). Pulsándola sale
            # todo.
            detalle = notas[0] if notas else " · ".join(x for x in (quien, programa) if x)
            filas.append({"icono": "seguridad" if sospechoso else "aplicaciones",
                          "color_icono": T.critico if sospechoso else (T.aviso if notas else T.acento),
                          "titulo": e["nombre"], "detalle": " · ".join([detalle] + extra), "recorte": "fin",
                          "color_titulo": T.critico if sospechoso else T.texto,
                          "interruptor": bool(e["activo"]),
                          "al_cambiar": lambda nuevo, listo, e=e: self._toggle_inicio(e, nuevo, listo),
                          "pulsar": lambda e=e, quien=quien, programa=programa, notas=notas, extra=extra:
                              self._detalle_inicio(e, quien, programa, notas, extra)})
        lienzo = ListaLienzo(self.caja_inicio)
        lienzo.pack(fill="x")
        lienzo.poner(filas)

    def _detalle_inicio(self, entrada, quien, programa, notas, extra):
        """Todo lo de una entrada del inicio (en la lista se ve una línea)."""
        partes = [x for x in (" · ".join(extra), entrada.get("comando") or "", programa,
                              t("apps_inicio_firma", quien=quien) if quien else "") if x] + notas
        self._mostrar_popup_info(entrada["nombre"], "\n\n".join(partes))

    def _toggle_inicio(self, entrada, activar, listo):
        """Activa o desactiva una entrada. En un hilo (registro, PowerShell),
        comprobando el efecto, y con su forma de deshacer. listo(exito) le
        dice al interruptor si se quedó o vuelve atrás."""
        def worker():
            tipo = entrada["tipo"]
            if tipo == "tarea":
                exito, comando = opt.set_tarea_inicio(entrada["carpeta"], entrada["nombre"], activar)
                if exito:
                    self.deshacer.anotar("tarea_inicio", {"carpeta": entrada["carpeta"], "nombre": entrada["nombre"],
                                                          "estaba_activa": not activar},
                                         t("desh_desc_app_inicio", nombre=entrada["nombre"]))
            elif tipo == "techclean":
                # Lo desactivó una versión anterior con su clave propia: se
                # devuelve a su sitio (y desde ahí ya se gestiona como Windows).
                exito = opt.set_app_inicio_activa(entrada["nombre"], entrada["comando"], activar)
                comando = f"set_app_inicio_activa({entrada['nombre']!r}, {activar})"
                if exito:
                    self.deshacer.anotar("app_inicio", {"nombre": entrada["nombre"], "comando": entrada["comando"],
                                                        "estaba_activa": not activar},
                                         t("desh_desc_app_inicio", nombre=entrada["nombre"]))
            else:
                valor = entrada.get("archivo") if tipo == "carpeta" else entrada["nombre"]
                exito, anterior, comando = opt.set_inicio_aprobado(entrada["raiz"], entrada["sub"], valor, activar)
                if exito:
                    self.deshacer.anotar("inicio_aprobado", {"raiz": entrada["raiz"], "sub": entrada["sub"],
                                                             "nombre": valor, "anterior": anterior},
                                         t("desh_desc_app_inicio", nombre=entrada["nombre"]))
            if exito:
                msg = t("apps_inicio_cambiado", nombre=entrada["nombre"],
                        estado=t("apps_activado") if activar else t("apps_desactivado"))
            elif entrada.get("todos"):
                msg = t("apps_inicio_error_admin", nombre=entrada["nombre"])
            else:
                msg = t("apps_inicio_error", nombre=entrada["nombre"])
            self._log_dev(t("apps_log_activar_inicio") if activar else t("apps_log_desactivar_inicio"),
                          comando, msg, seccion=t("seccion_aplicaciones"), exito=exito)

            def terminar():
                if exito:
                    entrada["activo"] = activar
                # Si no se pudo, el interruptor vuelve a como estaba.
                listo(exito)
                self._actualizar_label("lbl_inicio_resumen", msg)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_desinstalador(self):
        lista = self._lista_pestana(self.contenedor_apps, t("apps_desinst_intro"))
        panel, derecha = tarjeta_seccion(lista, t("apps_desinst_titulo"), "aplicaciones")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_programas = pildora(derecha)
        self.pild_programas.pack(side="right")
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 8))
        boton_secundario(controles, t("apps_btn_actualizar_lista"), self._mostrar_desinstalador, width=130,
                         height=32).pack(side="right", padx=(10, 0))
        self.orden_programas = ctk.CTkSegmentedButton(controles, values=[t("apps_orden_nombre"), t("apps_orden_tamano")],
                                                      command=lambda _v: self._filtrar_programas())
        self.orden_programas.set(t("apps_orden_nombre"))
        self.orden_programas.pack(side="right", padx=(10, 0))
        self.entry_programa = ctk.CTkEntry(controles, placeholder_text=t("apps_buscar_programa"))
        self.entry_programa.pack(side="left", fill="x", expand=True)
        self.entry_programa.bind("<KeyRelease>", lambda _e: self._filtrar_programas(esperar=True))
        self.lbl_desinstalar = Texto(panel, t("apps_cargando_programas"), size=12, color=T.texto2, wraplength=760)
        self.lbl_desinstalar.pack(fill="x", padx=20, pady=(0, 6))
        texto_fluido(self.lbl_desinstalar, panel, 40)
        self.lista_programas = ListaLienzo(panel)
        self.lista_programas.pack(fill="x", pady=(0, 10))
        self._programas = None

        def worker():
            programas = opt.listar_programas_instalados()
            self.after(0, lambda: self._pintar_desinstalador(programas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_desinstalador(self, programas):
        lienzo = getattr(self, "lista_programas", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        self._programas = programas or []
        if not programas:
            self.lbl_desinstalar.configure(text=t("apps_sin_programas"))
            return
        self.lbl_desinstalar.configure(text="")
        total = sum((p.get("tamano_mb") or 0) for p in programas) * 1024 * 1024
        poner_pildora(self.pild_programas, t("apps_desinst_resumen", n=len(programas),
                                             tamano=opt.format_bytes(total)))
        self._filtrar_programas()

    def _filtrar_programas(self, esperar=False):
        """Busca y ordena. Al escribir se espera un poco a que termine la
        palabra: volver a dibujar 150 programas con cada letra se notaba."""
        if esperar:
            if getattr(self, "_filtro_programas", None):
                self.after_cancel(self._filtro_programas)
            self._filtro_programas = self.after(180, self._filtrar_programas)
            return
        self._filtro_programas = None
        lienzo = getattr(self, "lista_programas", None)
        if lienzo is None or not lienzo.winfo_exists() or self._programas is None:
            return
        termino = self.entry_programa.get().strip().lower()
        programas = [p for p in self._programas
                     if not termino or termino in (p["nombre"] or "").lower() or termino in (p["editor"] or "").lower()]
        if self.orden_programas.get() == t("apps_orden_tamano"):
            programas.sort(key=lambda p: p.get("tamano_mb") or 0, reverse=True)
        filas = []
        for p in programas:
            detalle = " · ".join(x for x in (p.get("editor"), "v" + p["version"] if p.get("version") else "") if x)
            filas.append({"icono": "aplicaciones", "titulo": p["nombre"], "detalle": detalle,
                          "valor": opt.format_bytes(p["tamano_mb"] * 1024 * 1024) if p.get("tamano_mb") else "",
                          "acciones": [(t("apps_btn_desinstalar"), lambda p=p: self._confirmar_desinstalar(p))]})
        if not filas:
            filas = [{"titulo": t("drv_sin_coincidencias", termino=termino), "negrita": False,
                      "color_titulo": T.texto2}]
        lienzo.poner(filas)

    def _confirmar_desinstalar(self, programa):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("apps_conf_desinst_titulo"))
        dialogo.geometry("440x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("apps_conf_desinst_msg", nombre=programa["nombre"]),
                     font=fuente(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            # BUG corregido (1.8.0): el desinstalador se lanzaba desde el
            # hilo de la ventana (un subprocess con shell, que puede tardar).
            def worker():
                exito, comando = opt.desinstalar_programa(programa["desinstalar_cmd"])
                msg = (t("apps_desinst_ok", nombre=programa["nombre"]) if exito
                       else t("apps_desinst_error", nombre=programa["nombre"]))
                self._log_dev(t("apps_log_desinstalar", nombre=programa["nombre"]), comando, msg,
                              seccion=t("seccion_aplicaciones"), exito=exito)
                self.after(0, lambda: self._actualizar_label("lbl_desinstalar", msg))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("apps_btn_desinstalar"), fg_color=T.peligro,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

    # ---------------- Servicios de Windows ----------------
    def _mostrar_servicios(self):
        lista = self._lista_pestana(self.contenedor_apps, t("apps_serv_intro"))
        panel, _ = tarjeta_seccion(lista, _sin_emoji(t("apps_serv_consumo_titulo")), "memoria",
                                   t("apps_serv_consumo_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_servicios_consumo = ListaLienzo(panel)
        self.lista_servicios_consumo.pack(fill="x", pady=(0, 10))
        self.lista_servicios_consumo.poner([{"titulo": t("apps_leyendo"), "negrita": False, "color_titulo": T.texto2}])

        def worker_consumo():
            top = opt.listar_servicios_por_consumo(limite=12)
            self.after(0, lambda: self._pintar_servicios_consumo(top))
        threading.Thread(target=worker_consumo, daemon=True).start()

        panel, derecha = tarjeta_seccion(lista, t("apps_serv_todos_titulo"), "ajustes")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_servicios = pildora(derecha)
        self.pild_servicios.pack(side="right")
        self.entry_buscar_servicio = ctk.CTkEntry(panel, placeholder_text=_sin_emoji(t("apps_buscar_servicio")))
        self.entry_buscar_servicio.pack(fill="x", padx=18, pady=(0, 8))
        self.entry_buscar_servicio.bind("<KeyRelease>", lambda e: self._filtrar_servicios(esperar=True))
        self.lista_servicios_frame = ListaLienzo(panel)
        self.lista_servicios_frame.pack(fill="x", pady=(0, 10))
        self.lista_servicios_frame.poner([{"titulo": t("apps_cargando_servicios"), "negrita": False,
                                           "color_titulo": T.texto2}])
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
        lienzo = getattr(self, "lista_servicios_consumo", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        if not top:
            lienzo.poner([{"titulo": t("apps_serv_consumo_error"), "negrita": False, "color_titulo": T.texto2}])
            return
        maximo = max(item["bytes_ram"] for item in top) or 1
        lienzo.poner([{"icono": "memoria", "titulo": ", ".join(item["servicios"]),
                       "fraccion": item["bytes_ram"] / maximo,
                       "detalle": t("apps_serv_proceso", n=len(item["servicios"])) if len(item["servicios"]) > 1 else "",
                       "valor": opt.format_bytes(item["bytes_ram"])} for item in top])

    INICIOS_SERVICIO = {"Automatic": "apps_serv_inicio_auto", "Manual": "apps_serv_inicio_manual",
                        "Disabled": "apps_serv_inicio_off"}

    def _filtrar_servicios(self, esperar=False):
        if esperar:
            if getattr(self, "_filtro_servicios", None):
                self.after_cancel(self._filtro_servicios)
            self._filtro_servicios = self.after(180, self._filtrar_servicios)
            return
        self._filtro_servicios = None
        lienzo = getattr(self, "lista_servicios_frame", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        servicios = self._servicios_cache
        if servicios is None:
            return
        if not servicios:
            lienzo.poner([{"titulo": t("apps_sin_servicios"), "negrita": False, "color_titulo": T.texto2}])
            return
        activos = sum(1 for s in servicios if s["estado"] == "Running")
        poner_pildora(self.pild_servicios, t("apps_serv_resumen", total=len(servicios), activos=activos))
        termino = self.entry_buscar_servicio.get().strip().lower()
        if termino:
            servicios = [s for s in servicios if termino in (s["nombre"] or "").lower()
                         or termino in (s["nombre_visible"] or "").lower()]
        filas = []
        for s in servicios:
            riesgo, _ = opt.evaluar_riesgo_servicio(s["nombre"])
            # "Running" es el valor de .NET que da Get-Service (ver
            # opt.ESTADOS_SERVICIO), no texto para mostrar.
            corriendo = s["estado"] == "Running"
            partes = [s["nombre"], t("apps_serv_en_ejecucion") if corriendo else t("apps_serv_detenido")]
            if s.get("inicio") in self.INICIOS_SERVICIO:
                partes.append(t(self.INICIOS_SERVICIO[s["inicio"]]))
            if riesgo == "bloqueado":
                partes.append(t("apps_btn_protegido"))
            if riesgo == "bloqueado" and corriendo:
                acciones = []
            elif corriendo:
                acciones = [(t("apps_btn_detener"), lambda sv=s: self._confirmar_servicio(sv, "detener"))]
            elif s.get("inicio") == "Disabled":
                acciones = []       # un servicio desactivado no se puede iniciar
            else:
                acciones = [(t("apps_btn_iniciar"), lambda sv=s: self._confirmar_servicio(sv, "iniciar"))]
            filas.append({"icono": "ajustes", "color_icono": T.ok if corriendo else T.texto3,
                          "titulo": s["nombre_visible"] or s["nombre"], "detalle": " · ".join(partes),
                          "color_titulo": T.texto if corriendo else T.texto2, "acciones": acciones})
        lienzo.poner(filas or [{"titulo": t("drv_sin_coincidencias", termino=termino), "negrita": False,
                                "color_titulo": T.texto2}])

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
                     font=fuente(size=14, weight="bold"), wraplength=400, justify="center").pack(
            pady=(20, 6))
        if riesgo == "advertencia":
            ctk.CTkLabel(dialogo, text=t("apps_serv_advertencia", motivo=motivo),
                         font=fuente(size=11, weight="bold"),
                         text_color=COLOR_WARN, wraplength=400, justify="center").pack(padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(dialogo, text=t("apps_serv_nota"),
                         font=fuente(size=11), text_color=T.texto2, wraplength=400, justify="center").pack(
                padx=20, pady=(0, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()

            def worker():
                exito, comando = opt.set_servicio_windows(servicio["nombre"], accion)
                if exito:
                    self.deshacer.anotar("servicio",
                                          {"nombre": servicio["nombre"], "accion": accion},
                                          t("desh_desc_servicio", nombre=nombre_mostrar))
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

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("apps_btn_confirmar"), fg_color=COLOR_WARN, text_color=T.sobre_aviso,
                      command=confirmar).pack(side="left", padx=8)

    # ---- Actualizar apps (winget — catálogo oficial de Microsoft) ----
    def _mostrar_actualizar_apps(self):
        lista = self._lista_pestana(self.contenedor_apps, t("apps_winget_intro"))
        panel, derecha = tarjeta_seccion(lista, t("apps_winget_titulo"), "bandeja")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_winget = pildora(derecha)
        self.pild_winget.pack(side="right")
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(controles, text=_sin_emoji(t("apps_btn_buscar_act")),
                      command=self._accion_buscar_winget).pack(side="left")
        self.btn_winget_todo = boton_secundario(
            controles, t("fondo_dism_cancelar") if getattr(self, "_winget_todo_en_curso", False)
            else _sin_emoji(t("apps_btn_todo")), self._accion_actualizar_todo_winget)
        self.btn_winget_todo.pack(side="left", padx=8)
        self.lbl_winget_todo = Texto(panel, "", size=12, wraplength=760)
        self.lbl_winget_todo.pack(fill="x", padx=20, pady=(0, 6))
        texto_fluido(self.lbl_winget_todo, panel, 40)
        self.lista_winget = ListaLienzo(panel)
        self.lista_winget.pack(fill="x", pady=(0, 10))
        self.lista_winget.poner([{"titulo": t("apps_winget_presiona"), "negrita": False, "color_titulo": T.texto2}])

    def _accion_buscar_winget(self):
        self.lista_winget.poner([{"titulo": t("apps_winget_buscando"), "negrita": False, "color_titulo": T.texto2}])

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

    @staticmethod
    def _columnas_winget(fila):
        """Una fila de winget (las columnas unidas con 3 espacios, ver
        opt.listar_actualizaciones_winget) -> (nombre, id, versión, disponible)."""
        partes = [p.strip() for p in fila.split("   ") if p.strip()]
        partes += [""] * (4 - len(partes))
        return partes[0], partes[1], partes[2], partes[3]

    def _pintar_winget(self, apps, disponible):
        lienzo = getattr(self, "lista_winget", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        aviso = None
        if not disponible:
            aviso = t("apps_winget_no_disponible")
        elif apps is None:
            aviso = t("apps_winget_error")
        elif not apps:
            aviso = _sin_emoji(t("apps_winget_al_dia"))
        if aviso:
            poner_pildora(self.pild_winget, "")
            lienzo.poner([{"titulo": aviso, "negrita": False, "color_titulo": T.texto2}])
            return
        poner_pildora(self.pild_winget, str(len(apps)), "atencion")
        filas = []
        for linea in apps:
            nombre, ident, version, nueva = self._columnas_winget(linea)
            detalle = " · ".join(x for x in (t("apps_winget_version", version=version, disponible=nueva)
                                             if version and nueva else "", ident) if x)
            filas.append({"icono": "bandeja", "titulo": nombre, "detalle": detalle,
                          "acciones": [(t("apps_winget_actualizar"),
                                        lambda n=nombre, i=ident: self._accion_actualizar_una(n, i))]
                          if ident else []})
        lienzo.poner(filas)

    def _accion_actualizar_una(self, nombre, ident):
        """Actualiza una sola app y comprueba el EFECTO: que ya no salga en
        la lista de winget, no solo que el comando terminara."""
        self._actualizar_label("lbl_winget_todo", t("apps_winget_actualizando", nombre=nombre))

        def worker():
            exito, comando = opt.actualizar_app_winget(ident)
            _, pendientes, _ = opt.listar_actualizaciones_winget()
            sigue = any(self._columnas_winget(f)[1] == ident for f in pendientes)
            msg = (t("apps_winget_no_actualizada", nombre=nombre) if (sigue or not exito)
                   else t("apps_winget_actualizada", nombre=nombre))
            self._log_dev(t("apps_log_winget_una", nombre=nombre), comando, msg,
                          seccion=t("seccion_aplicaciones"), exito=exito and not sigue)

            def terminar():
                self._actualizar_label("lbl_winget_todo", msg)
                self._pintar_winget(pendientes, disponible=True)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Aplicaciones: actualizar todas con winget ----
    def _accion_actualizar_todo_winget(self):
        if getattr(self, "_winget_todo_en_curso", False):
            self._evento_winget_todo.set()
            self._actualizar_label("lbl_winget_todo", t("fondo_dism_cancelando"))
            return
        self._winget_todo_en_curso = True
        self._evento_winget_todo = threading.Event()
        boton = getattr(self, "btn_winget_todo", None)
        if boton is not None and boton.winfo_exists():
            boton.configure(text=t("fondo_dism_cancelar"))
        self._actualizar_label("lbl_winget_todo", t("apps_todo_en_curso", minutos=0))

        def progreso(seg):
            texto = t("apps_todo_en_curso", minutos=int(seg // 60))
            self.after(0, lambda: self._actualizar_label("lbl_winget_todo", texto))

        def worker():
            exito, resumen, cancelado = opt.actualizar_todo_winget(progreso, self._evento_winget_todo)
            msg = (t("fondo_dism_cancelado") if cancelado else
                   t("apps_todo_ok") if exito else t("apps_todo_parcial"))
            self._log_dev(t("apps_log_todo"), "winget upgrade --all --silent", msg + "\n" + resumen[-500:],
                          seccion=t("seccion_aplicaciones"), exito=exito)

            def terminar():
                self._winget_todo_en_curso = False
                self._actualizar_label("lbl_winget_todo", msg)
                b = getattr(self, "btn_winget_todo", None)
                if b is not None and b.winfo_exists():
                    b.configure(text=t("apps_btn_todo"))
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Aplicaciones: apps de serie (bloatware) ----
    def _mostrar_bloatware(self):
        lista = self._lista_pestana(self.contenedor_apps, t("bloat_intro"))
        panel, _ = tarjeta_seccion(lista, t("apps_tab_bloat"), "aplicaciones")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_bloat = Caja(panel)
        self.lista_bloat.pack(fill="x")
        barra = Caja(panel)
        barra.pack(fill="x", padx=20, pady=(6, 18))
        self.btn_bloat = ctk.CTkButton(barra, text=t("bloat_btn_quitar"), fg_color=T.peligro, hover_color=T.critico,
                                       state="disabled", command=self._confirmar_quitar_bloat, text_color=T.sobre_peligro)
        self.btn_bloat.pack(side="right")
        self.lbl_bloat = Texto(barra, "", size=12, wraplength=620)
        self.lbl_bloat.pack(side="left", fill="x", expand=True)
        texto_fluido(self.lbl_bloat, barra, 250)
        self._checks_bloat = {}
        self._aviso_lista(self.lista_bloat, t("comun_cargando"))

        def worker():
            apps = opt.listar_bloatware()
            self.after(0, lambda: self._pintar_bloatware(apps))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_bloatware(self, apps):
        if not (hasattr(self, "lista_bloat") and self.lista_bloat.winfo_exists()):
            return
        for w in self.lista_bloat.winfo_children():
            w.destroy()
        self._checks_bloat = {}
        if not apps:
            self._aviso_lista(self.lista_bloat, _sin_emoji(t("bloat_nada")), T.ok)
            self._actualizar_boton_bloat()
            return
        for n, app in enumerate(apps):
            nombre = app["nombre"].split(".")[-1] if app["nombre"].count(".") else app["nombre"]
            derecha = fila(self.lista_bloat, "aplicaciones", nombre,
                           t(app["categoria"]) + "  ·  " + app["familia"].split("_")[0], primera=n == 0)
            # Ninguna marcada de entrada: quitar algo es decisión del usuario.
            marca = casilla(derecha, False, text="", width=24, command=self._actualizar_boton_bloat)
            marca.pack(side="right")
            self._checks_bloat[app["paquete"]] = (marca, app["nombre"])
        self._actualizar_boton_bloat()

    def _actualizar_boton_bloat(self):
        marcadas = sum(1 for var, _ in self._checks_bloat.values() if var.get())
        if hasattr(self, "btn_bloat") and self.btn_bloat.winfo_exists():
            self.btn_bloat.configure(state="normal" if marcadas else "disabled",
                                     text=t("bloat_btn_quitar_n", n=marcadas) if marcadas else t("bloat_btn_quitar"))

    def _confirmar_quitar_bloat(self):
        elegidas = [(p, n) for p, (var, n) in self._checks_bloat.items() if var.get()]
        if not elegidas:
            return
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("480x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("bloat_confirmar", n=len(elegidas),
                                     lista=", ".join(n.split(".")[-1] for _, n in elegidas[:8])),
                     font=fuente(size=13), wraplength=440, justify="left").pack(padx=20, pady=(20, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            self.btn_bloat.configure(state="disabled")
            self.lbl_bloat.configure(text=t("bloat_quitando"))

            def worker():
                quitados, fallidos, comando = opt.quitar_bloatware([p for p, _ in elegidas])
                msg = t("bloat_resultado", quitados=len(quitados), fallidos=len(fallidos))
                self._log_dev(t("bloat_log"), comando, msg + ("\n" + "\n".join(quitados) if quitados else ""),
                              seccion=t("seccion_aplicaciones"), exito=not fallidos)

                apps_restantes = opt.listar_bloatware()

                def terminar():
                    self._pintar_bloatware(apps_restantes)
                    self._actualizar_label("lbl_bloat", msg)
                self.after(0, terminar)
            threading.Thread(target=worker, daemon=True).start()
        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("bloat_btn_quitar"), fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

    # ---- Disco: archivos duplicados ----
    def _mostrar_duplicados(self):
        lista = self._lista_disco(t("dup_intro"))
        self._carpeta_duplicados = getattr(self, "_carpeta_duplicados", None) or os.path.expanduser("~")
        panel, _ = tarjeta_seccion(lista, t("disco_tab_duplicados"), "archivo")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        controles = Caja(panel)
        controles.pack(fill="x", padx=18, pady=(0, 10))
        self.btn_buscar_dup = ctk.CTkButton(controles, text=_sin_emoji(t("dup_btn_buscar")), width=150,
                                            command=self._accion_buscar_duplicados)
        self.btn_buscar_dup.pack(side="right")
        boton_secundario(controles, _sin_emoji(t("dup_btn_carpeta")), self._elegir_carpeta_duplicados,
                         icono="carpeta", width=150).pack(side="left")
        self.lbl_carpeta_dup = Texto(controles, self._carpeta_duplicados, size=12, color=T.texto2)
        self.lbl_carpeta_dup.pack(side="left", padx=12)
        self.lista_dup = Caja(panel)
        self.lista_dup.pack(fill="x")
        barra = Caja(panel)
        barra.pack(fill="x", padx=20, pady=(6, 18))
        self.btn_borrar_dup = ctk.CTkButton(barra, text=t("dup_btn_papelera"), state="disabled",
                                            command=self._accion_enviar_duplicados)
        self.btn_borrar_dup.pack(side="right")
        self.lbl_dup = Texto(barra, "", size=12, wraplength=620)
        self.lbl_dup.pack(side="left", fill="x", expand=True)
        texto_fluido(self.lbl_dup, barra, 250)
        self._checks_dup = []

    def _elegir_carpeta_duplicados(self):
        from tkinter import filedialog
        carpeta = filedialog.askdirectory(title=_sin_emoji(t("dup_btn_carpeta")), initialdir=self._carpeta_duplicados)
        if carpeta:
            self._carpeta_duplicados = os.path.normpath(carpeta)
            self.lbl_carpeta_dup.configure(text=self._carpeta_duplicados)

    def _accion_buscar_duplicados(self):
        self.btn_buscar_dup.configure(state="disabled")
        self.btn_borrar_dup.configure(state="disabled")
        for w in self.lista_dup.winfo_children():
            w.destroy()
        self.lbl_dup.configure(text=t("dup_buscando"), fg=T.texto)
        carpeta = self._carpeta_duplicados

        def progreso(i, n):
            texto = t("dup_comparando", i=i, n=n)
            self.after(0, lambda: self._actualizar_label("lbl_dup", texto))

        def worker():
            grupos, completo = opt.buscar_duplicados(carpeta, callback=progreso)
            self.after(0, lambda: self._pintar_duplicados(grupos, completo))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_duplicados(self, grupos, completo):
        if not (hasattr(self, "lista_dup") and self.lista_dup.winfo_exists()):
            return
        self.btn_buscar_dup.configure(state="normal")
        for w in self.lista_dup.winfo_children():
            w.destroy()
        self._checks_dup = []
        if not grupos:
            self.lbl_dup.configure(text=_sin_emoji(t("dup_nada")) if completo else t("dup_nada_parcial"),
                                   fg=T.ok if completo else T.texto)
            return
        desperdicio = sum(g["bytes"] * (len(g["rutas"]) - 1) for g in grupos)
        self.lbl_dup.configure(text=t("dup_resumen", grupos=len(grupos), tamano=opt.format_bytes(desperdicio))
                               + ("" if completo else " " + t("dup_parcial")), fg=T.texto)
        for n, g in enumerate(grupos[:150]):
            if n:
                linea(self.lista_dup).pack(fill="x", padx=20)
            caja = Caja(self.lista_dup)
            caja.pack(fill="x", padx=20, pady=8)
            Texto(caja, t("dup_grupo", copias=len(g["rutas"]), tamano=opt.format_bytes(g["bytes"])),
                  size=13, weight="bold").pack(fill="x", pady=(0, 4))
            grupo_vars = []
            for i, ruta in enumerate(g["rutas"]):
                # La primera (ruta más corta) se queda desmarcada: por
                # defecto siempre sobrevive una copia.
                marca = casilla(caja, i > 0, text=ruta, font=fuente(size=11), command=self._actualizar_boton_dup)
                marca.pack(anchor="w", padx=(4, 0), pady=1)
                grupo_vars.append((marca, ruta))
            self._checks_dup.append(grupo_vars)
        self._actualizar_boton_dup()

    def _actualizar_boton_dup(self):
        n = sum(1 for grupo in self._checks_dup for var, _ in grupo if var.get())
        if hasattr(self, "btn_borrar_dup") and self.btn_borrar_dup.winfo_exists():
            self.btn_borrar_dup.configure(state="normal" if n else "disabled",
                                          text=t("dup_btn_papelera_n", n=n) if n else t("dup_btn_papelera"))

    def _accion_enviar_duplicados(self):
        rutas = []
        for grupo in self._checks_dup:
            marcadas = [r for var, r in grupo if var.get()]
            # Nunca todas las copias de un mismo archivo, aunque el usuario
            # las marque todas: se perdería el archivo. Se salva la primera.
            if len(marcadas) == len(grupo):
                marcadas = marcadas[1:]
            rutas += marcadas
        if rutas:
            self._confirmar_borrar_archivos(rutas)

    # ---- Pestaña: Accesos directos rotos (1.7.0) ----
    def _mostrar_accesos_rotos(self):
        lista = self._lista_disco(t("accesos_intro"))
        panel, self.derecha_accesos = tarjeta_seccion(lista, t("disco_tab_accesos"), "aplicaciones")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_accesos = Caja(panel)
        self.lista_accesos.pack(fill="x")
        barra = Caja(panel)
        barra.pack(fill="x", padx=20, pady=(6, 18))
        self.btn_borrar_accesos = ctk.CTkButton(barra, text=t("dup_btn_papelera"), state="disabled",
                                                command=self._accion_enviar_accesos)
        self.btn_borrar_accesos.pack(side="right")
        self.lbl_accesos = Texto(barra, t("accesos_buscando"), size=12, wraplength=620)
        self.lbl_accesos.pack(side="left", fill="x", expand=True)
        texto_fluido(self.lbl_accesos, barra, 250)
        self._checks_accesos = []

        def worker():
            rotos = opt.buscar_accesos_rotos()
            self.after(0, lambda: self._pintar_accesos_rotos(rotos))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_accesos_rotos(self, rotos):
        if not (hasattr(self, "lista_accesos") and self.lista_accesos.winfo_exists()):
            return
        for w in self.lista_accesos.winfo_children():
            w.destroy()
        self._checks_accesos = []
        if not rotos:
            self.lbl_accesos.configure(text=_sin_emoji(t("accesos_ninguno")), fg=T.ok)
            self._actualizar_boton_accesos()
            return
        self.lbl_accesos.configure(text=t("accesos_resumen", total=len(rotos)), fg=T.aviso)
        lugares = {"escritorio": "accesos_lugar_escritorio", "inicio": "accesos_lugar_inicio",
                   "arranque": "accesos_lugar_arranque"}
        primera = True
        for r in rotos[:300]:
            if not isinstance(r, dict) or not r.get("ruta"):
                continue
            if not primera:
                linea(self.lista_accesos).pack(fill="x", padx=20)
            primera = False
            caja = Caja(self.lista_accesos)
            caja.pack(fill="x", padx=20, pady=8)
            # Los de la carpeta de arranque salen SIN marcar: un acceso que
            # se abría solo al encender y apunta a algo que ya no está puede
            # ser el resto de un programa sospechoso, y conviene mirarlo
            # (Seguridad > Auditoría) antes de hacerlo desaparecer.
            marca = casilla(caja, r.get("lugar") != "arranque", text=r.get("nombre") or r["ruta"],
                            font=fuente(size=13, weight="bold"), command=self._actualizar_boton_accesos)
            marca.pack(anchor="w")
            self._checks_accesos.append((marca, r["ruta"]))
            lugar = _sin_emoji(t(lugares.get(r.get("lugar"), "accesos_lugar_inicio")))
            if r.get("comun"):
                lugar += "  ·  " + t("accesos_comun")
            texto_fluido(Texto(caja, t("accesos_detalle", lugar=lugar, destino=r.get("destino") or "?"),
                               size=11, color=T.aviso if r.get("lugar") == "arranque" else T.texto2,
                               wraplength=760), caja, 34).pack(fill="x", padx=(34, 0), pady=(2, 0))
        self._actualizar_boton_accesos()

    def _actualizar_boton_accesos(self):
        n = sum(1 for var, _ in getattr(self, "_checks_accesos", []) if var.get())
        if hasattr(self, "btn_borrar_accesos") and self.btn_borrar_accesos.winfo_exists():
            self.btn_borrar_accesos.configure(state="normal" if n else "disabled",
                                              text=t("dup_btn_papelera_n", n=n) if n else t("dup_btn_papelera"))

    def _accion_enviar_accesos(self):
        rutas = [ruta for var, ruta in self._checks_accesos if var.get()]
        if rutas:
            # El mismo diálogo y la misma papelera que los duplicados: se
            # puede deshacer desde la papelera de Windows.
            self._confirmar_borrar_archivos(rutas)

    # ---- Tareas programadas (de terceros, no la nuestra) ----
    def _mostrar_tareas_programadas(self):
        lista = self._lista_pestana(self.contenedor_apps, t("apps_tareas_intro"))
        panel, derecha = tarjeta_seccion(lista, t("apps_tab_tareas"), "calendario")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.pild_tareas = pildora(derecha)
        self.pild_tareas.pack(side="right")
        self.lista_tareas_frame = ListaLienzo(panel)
        self.lista_tareas_frame.pack(fill="x", pady=(0, 10))
        self.lista_tareas_frame.poner([{"titulo": t("apps_leyendo_tareas"), "negrita": False,
                                        "color_titulo": T.texto2}])

        def worker():
            tareas = opt.listar_tareas_programadas_terceros()
            self.after(0, lambda: self._pintar_tareas_programadas(tareas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_tareas_programadas(self, tareas):
        lienzo = getattr(self, "lista_tareas_frame", None)
        if lienzo is None or not lienzo.winfo_exists():
            return
        if not tareas:
            lienzo.poner([{"titulo": t("apps_sin_tareas"), "negrita": False, "color_titulo": T.texto2}])
            return
        poner_pildora(self.pild_tareas, str(len(tareas)))
        # La variable del bucle se llamaba "t" y pisaba la funcion t() de
        # traduccion dentro de esta funcion: cualquier llamada a t() aqui
        # habria reventado con "dict object is not callable".
        lienzo.poner([{"icono": "calendario", "titulo": tarea["nombre"], "detalle": tarea["ruta"]}
                      for tarea in tareas])

    # ---------------- Segundo plano: widget + Modo Juego ----------------
    def mostrar_segundo_plano(self):
        """Segundo plano (rediseño 1.8.0): lo que se enciende aquí (el widget
        y la limpieza programada) y, debajo, un resumen de TODO lo que la app
        hace sola, con un salto a donde se cambia cada cosa."""
        self._limpiar_contenido()
        self._encabezado(t("segplano_titulo"), t("segplano_subtitulo"))
        cuerpo = self._cuerpo()

        panel, _ = tarjeta_seccion(cuerpo, t("segplano_card_ayudas"), "segundo_plano")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        widget_visible = (self.performance_widget is not None
                          and self.performance_widget.state() != "withdrawn")
        self.switch_widget, _ = fila_interruptor(panel, "monitor", t("segplano_widget_titulo"),
                                                 t("segplano_widget_desc"), widget_visible, self._toggle_widget,
                                                 primera=True)

        derecha = fila(panel, "calendario", t("segplano_limpieza_titulo"), t("segplano_limpieza_desc"))
        self.switch_limpieza = ctk.CTkSwitch(derecha, text="", width=46, command=self._toggle_limpieza_programada)
        self.switch_limpieza.pack(side="right")
        frecuencias = {"DAILY": t("segplano_frec_diaria"), "WEEKLY": t("segplano_frec_semanal")}
        self.combo_frecuencia = ctk.CTkOptionMenu(derecha, values=list(frecuencias.values()), width=110,
                                                  command=lambda _v: self._reprogramar_limpieza())
        self.combo_frecuencia.set(frecuencias.get(self.prefs.get("limpieza_frecuencia"), frecuencias["DAILY"]))
        self.combo_frecuencia.pack(side="right", padx=(0, 10))
        horas_disponibles = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "22:00"]
        self.combo_hora_limpieza = ctk.CTkOptionMenu(derecha, values=horas_disponibles, width=90,
                                                     command=lambda _v: self._reprogramar_limpieza())
        self.combo_hora_limpieza.set(self.prefs.get("limpieza_hora", "09:00"))
        self.combo_hora_limpieza.pack(side="right", padx=(0, 8))
        self.lbl_limpieza_prog = Texto(derecha.textos, "", size=12, color=T.acento, wraplength=520)
        self.lbl_limpieza_prog.pack(fill="x", pady=(4, 0))
        texto_fluido(self.lbl_limpieza_prog, derecha.textos, 4)

        # BUG corregido: opt.limpieza_programada_activa() llama a
        # schtasks /query (subprocess, hasta 15s de timeout) — se
        # consultaba directo en el hilo principal cada vez que se abría
        # esta pantalla. Ahora se consulta en un hilo aparte.
        # BUG corregido (encontrado en los registros de error del banco de
        # pruebas, 22 veces): winfo_exists() se llamaba DESDE el hilo, y
        # eso ya es tocar Tk fuera del hilo principal ("main thread is not
        # in main loop"). La comprobación va dentro de lo que se manda con
        # after(0), que sí corre en el hilo de la interfaz.
        def marcar_switch_limpieza():
            if hasattr(self, "switch_limpieza") and self.switch_limpieza.winfo_exists():
                self.switch_limpieza.select()

        def worker_estado_limpieza():
            if opt.limpieza_programada_activa():
                self.after(0, marcar_switch_limpieza)
        threading.Thread(target=worker_estado_limpieza, daemon=True).start()

        fila_accion(panel, "historial", t("segplano_ver_titulo"), t("segplano_ver_desc"), t("segplano_btn_abrir"),
                    self.mostrar_reporte)
        Caja(panel, height=6).pack()

        # ---- Todo lo que la app hace sola ----
        panel, _ = tarjeta_seccion(cuerpo, t("segplano_resumen_titulo"), "correcto", t("segplano_resumen_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        avisos = ("avisar_fugas", "avisar_disco_lleno", "avisar_reinicio", "avisar_carga_bateria")
        por_defecto = {"avisar_fugas": True, "avisar_disco_lleno": True, "avisar_reinicio": True,
                       "avisar_carga_bateria": False}
        n_avisos = sum(1 for a in avisos if self.prefs.get(a, por_defecto[a]))
        temp = self.prefs.get("alerta_temp_cpu")
        juegos = len(self.prefs.get("juegos_modo_auto", []))
        combinacion = atajos.texto_combinacion(self.prefs.get("atajo_ram_combinacion", "ctrl+alt+r"))
        filas = [
            ("memoria", t("ajustes_auto_ram_titulo"), self.prefs.get("auto_ram_activa", True),
             t("segplano_ram_detalle", pct=self.prefs.get("umbral_ram_auto", 85)), self.mostrar_ajustes),
            ("campana", t("ajustes_avisos_titulo"), n_avisos > 0,
             t("segplano_avisos_detalle", n=n_avisos, total=len(avisos)), self.mostrar_ajustes),
            ("componentes", t("segplano_temp_titulo"), bool(temp),
             t("segplano_temp_detalle", grados=int(temp)) if temp else t("segplano_temp_off"), self.mostrar_ajustes),
            ("consola", t("atajo_titulo"), self.prefs.get("atajo_ram_activo", False),
             t("segplano_atajo_detalle", combinacion=combinacion), self.mostrar_ajustes),
            ("energia", t("ajustes_bateria_titulo"), bool(self.prefs.get("bateria_ahorro_automatico")),
             t("segplano_bateria_detalle", pct=self.prefs.get("bateria_umbral_ahorro", 20)), self.mostrar_ajustes),
            ("gaming", t("gaming_auto_label"), juegos > 0, t("segplano_juegos_detalle", n=juegos),
             self.mostrar_gaming),
        ]
        lienzo = ListaLienzo(panel)
        lienzo.pack(fill="x", pady=(0, 10))
        lienzo.poner([{"icono": icono, "titulo": _sin_emoji(titulo), "detalle": detalle,
                       "valor": t("segplano_estado_on") if activo else t("segplano_estado_off"),
                       "color_valor": T.ok if activo else T.texto3,
                       "acciones": [(t("segplano_btn_cambiar"), destino)]}
                      for icono, titulo, activo, detalle, destino in filas])

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
        """Gaming (rediseño 1.8.0). Novedades: el Modo Juego reconoce los
        juegos de la biblioteca aunque no estén a pantalla completa (y ya no
        confunde un vídeo o el navegador con un juego), frena lo que acapara
        la CPU mientras juegas, cada juego puede encenderlo solo, y una
        prueba de lag con la conexión ocupada (bufferbloat).

        BUG corregido: los ajustes de Windows para juegos (registro) se
        leían en el hilo de la interfaz. Ahora en uno aparte."""
        self._limpiar_contenido()
        self._encabezado(t("gaming_titulo"), t("gaming_subtitulo"))
        cuerpo = self._cuerpo()

        # ---- Modo Juego ----
        panel, derecha = tarjeta_seccion(cuerpo, t("gaming_modo_juego"), "gaming", t("gaming_modo_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.switch_gaming = ctk.CTkSwitch(derecha, text="", width=46, command=self._toggle_autopilot)
        self.switch_gaming.pack(side="right")
        if self.autopilot.activo:
            self.switch_gaming.select()
        self.lbl_estado_gaming = Texto(derecha, "", size=13, weight="bold")
        self.lbl_estado_gaming.pack(side="right", padx=(0, 10))
        botones = Caja(panel)
        botones.pack(fill="x", padx=18, pady=(0, 6))
        ctk.CTkButton(botones, text=_sin_emoji(t("gaming_btn_antes")), height=34,
                      command=self._accion_antes_de_jugar).pack(side="left", padx=(0, 8))
        boton_secundario(botones, _sin_emoji(t("gaming_btn_fps")), self._accion_abrir_fps, height=34).pack(
            side="left", padx=(0, 8))
        boton_secundario(botones, _sin_emoji(t("gaming_btn_enfoque")), self._accion_abrir_enfoque_asistido,
                         height=34).pack(side="left")
        self.lbl_resultado_gaming = Texto(panel, "", size=12, color=T.texto2, wraplength=760)
        self.lbl_resultado_gaming.pack(fill="x", padx=18, pady=(4, 0))
        texto_fluido(self.lbl_resultado_gaming, panel, 36)
        self.switch_frenar, _ = fila_interruptor(panel, "componentes", t("gaming_frenar_titulo"),
                                                 t("gaming_frenar_desc"), self.prefs.get("frenar_acaparadores", True),
                                                 self._toggle_frenar, margen=18)
        texto_fluido(Texto(panel, t("gaming_nota_overlay"), size=11, color=T.texto3, wraplength=760),
                     panel, 36).pack(fill="x", padx=18, pady=(0, 16))

        # ---- Biblioteca: cada juego puede encender el Modo Juego solo ----
        panel, _ = tarjeta_seccion(cuerpo, t("gaming_biblioteca_titulo"), "aplicaciones", t("gaming_biblioteca_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.lista_juegos = Caja(panel)
        self.lista_juegos.pack(fill="x", pady=(0, 10))
        Texto(self.lista_juegos, t("gaming_buscando_juegos"), size=12, color=T.texto2).pack(fill="x", padx=18)

        # ---- Cerrar apps al jugar ----
        panel, derecha = tarjeta_seccion(cuerpo, _sin_emoji(t("gjuego_cerrar_titulo")), "papelera",
                                         t("gjuego_cerrar_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        # Interruptor general, APAGADO de fábrica: las apps marcadas se
        # quedan guardadas, pero no se cierra nada hasta encenderlo. Así,
        # el día que se juega con el navegador o Discord abiertos a
        # propósito, basta con apagarlo en vez de desmarcar todo.
        self.switch_cerrar_jugar = ctk.CTkSwitch(derecha, text="", width=46, command=self._toggle_cerrar_al_jugar)
        self.switch_cerrar_jugar.pack(side="right")
        if self.prefs.get("cerrar_apps_al_jugar", False):
            self.switch_cerrar_jugar.select()
        self.lista_cerrar_jugar = ctk.CTkFrame(panel, fg_color=T.fila, corner_radius=T.radio_fila)
        self.lista_cerrar_jugar.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkLabel(self.lista_cerrar_jugar, text=t("comun_cargando"), text_color=T.texto2).grid(padx=8, pady=8)

        def worker_candidatas():
            candidatas = self._candidatas_cerrar_al_jugar()
            self.after(0, lambda: self._pintar_cerrar_al_jugar(candidatas))
        threading.Thread(target=worker_candidatas, daemon=True).start()

        # ---- Ajustes de Windows para juegos ----
        panel, _ = tarjeta_seccion(cuerpo, _sin_emoji(t("gjuego_ajustes_titulo")), "ajustes",
                                   t("gjuego_ajustes_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.lista_ajustes_juego = Caja(panel)
        self.lista_ajustes_juego.pack(fill="x")
        self.lbl_ajustes_juego = Texto(panel, "", size=12, wraplength=760)
        self.lbl_ajustes_juego.pack(fill="x", padx=18, pady=(0, 14))
        texto_fluido(self.lbl_ajustes_juego, panel, 36)

        # ---- La conexión: lag, bufferbloat y Wi-Fi ----
        panel, _ = tarjeta_seccion(cuerpo, t("gaming_sec_conexion"), "globo")
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.btn_medir_lag = fila_accion(panel, "optimizar", _sin_emoji(t("gjuego_lag_titulo")), t("gjuego_lag_desc"),
                                         t("bb_btn"), self._accion_medir_lag, primera=True)
        self.lbl_lag = Texto(panel, "", size=12, wraplength=760)
        self.lbl_lag.pack(fill="x", padx=20)
        texto_fluido(self.lbl_lag, panel, 40)
        self.btn_bufferbloat = fila_accion(panel, "bandeja", t("bb_titulo"), t("bb_desc"), t("bb_btn"),
                                           self._accion_bufferbloat)
        self.lbl_bufferbloat = Texto(panel, "", size=12, wraplength=760)
        self.lbl_bufferbloat.pack(fill="x", padx=20)
        texto_fluido(self.lbl_bufferbloat, panel, 40)
        self.btn_wifi = fila_accion(panel, "globo", _sin_emoji(t("wifi_titulo")), t("wifi_desc"), t("bb_btn"),
                                    self._accion_analizar_wifi)
        self.lbl_wifi = Texto(panel, "", size=12, wraplength=760)
        self.lbl_wifi.pack(fill="x", padx=20, pady=(0, 14))
        texto_fluido(self.lbl_wifi, panel, 40)

        def worker():
            datos = {"juegos": opt.listar_juegos_instalados(), "ajustes": opt.leer_ajustes_juego()}
            self.after(0, lambda: self._pintar_ajustes_juego(datos["ajustes"]))
            self.after(0, lambda: self._pintar_juegos(datos["juegos"]))
        threading.Thread(target=worker, daemon=True).start()

        self._actualizar_tarjeta_gaming()

    def _leer_carpetas_juegos(self):
        try:
            self._carpetas_juegos = opt.carpetas_de_juegos()
        except Exception:
            self._carpetas_juegos = []

    def _toggle_frenar(self):
        activo = bool(self.switch_frenar.get())
        self.prefs["frenar_acaparadores"] = activo
        prefs.guardar({"frenar_acaparadores": activo})
        self._log_dev(t("gaming_frenar_titulo"), "N/A", t("gaming_frenar_on") if activo else t("gaming_frenar_off"),
                      seccion=t("seccion_gaming"), exito=True)

    def _toggle_juego_auto(self, juego, interruptor):
        """Marca o desmarca un juego para que encienda el Modo Juego solo."""
        carpeta = os.path.normcase(os.path.normpath(juego["ruta"])) + os.sep
        marcados = [c for c in self.prefs.get("juegos_modo_auto", []) if c != carpeta]
        if interruptor.get():
            marcados.append(carpeta)
        self.prefs["juegos_modo_auto"] = marcados
        prefs.guardar({"juegos_modo_auto": marcados})
        if marcados:
            self.vigia_juegos.iniciar()
        else:
            self.vigia_juegos.detener()
        self._log_dev(t("gaming_auto_log"), "N/A",
                      t("gaming_auto_marcado" if interruptor.get() else "gaming_auto_desmarcado", juego=juego["nombre"]),
                      seccion=t("seccion_gaming"), exito=True)

    def _modo_juego_por_juego(self, nombre):
        """El vigía vio delante un juego marcado: Modo Juego encendido,
        apuntando que fue él (para apagarlo al cerrar el juego)."""
        if self.autopilot.activo:
            return
        self._modo_juego_auto = True
        self._toggle_autopilot()
        self._log_dev(t("gaming_auto_log"), "N/A", t("gaming_auto_encendido", juego=nombre),
                      seccion=t("seccion_gaming"), exito=True)

    def _fin_modo_juego_por_juego(self):
        # Si el usuario lo encendió a mano, el vigía no lo apaga.
        if getattr(self, "_modo_juego_auto", False) and self.autopilot.activo:
            self._modo_juego_auto = False
            self._toggle_autopilot()

    # ---- Gaming: cerrar apps al jugar ----
    # Apps que suelen quedarse abiertas de fondo y gastan RAM, CPU o red
    # mientras se juega. NO van lanzadores de juegos (Steam, Epic, Battle.net,
    # EA...): muchos juegos dejan de funcionar si se les cierra el lanzador.
    APPS_FONDO_CONOCIDAS = (
        "discord.exe", "spotify.exe", "onedrive.exe", "ms-teams.exe", "teams.exe", "chrome.exe", "msedge.exe",
        "firefox.exe", "opera.exe", "brave.exe", "skype.exe", "zoom.exe", "dropbox.exe", "googledrivefs.exe",
        "slack.exe", "whatsapp.exe", "telegram.exe", "outlook.exe", "olk.exe", "notion.exe",
    )
    LANZADORES_JUEGOS = ("steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "battle.net.exe",
                         "eadesktop.exe", "origin.exe", "ubisoftconnect.exe", "upc.exe", "riotclientservices.exe",
                         "robloxplayerbeta.exe", "gog galaxy.exe", "galaxyclient.exe", "xboxpcapp.exe")

    def _candidatas_cerrar_al_jugar(self):
        """Nombres de proceso para elegir: las elegidas antes, las de fondo
        conocidas que estén abiertas, y cualquier app con ventana abierta."""
        abiertos = {}
        de_windows = set()
        carpeta_windows = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + os.sep
        for p in psutil.process_iter(["name", "exe"]):
            nombre = (p.info.get("name") or "").lower()
            if nombre:
                abiertos[nombre] = p.info.get("exe")
                # Piezas del propio Windows con ventana (applicationframehost,
                # textinputhost, systemsettings...): cerrarlas rompe cosas.
                if os.path.normcase(p.info.get("exe") or "").startswith(carpeta_windows):
                    de_windows.add(nombre)
        candidatas = {n.lower() for n in self.prefs.get("apps_cerrar_al_jugar", [])}
        candidatas |= {n for n in self.APPS_FONDO_CONOCIDAS if n in abiertos}
        for v in opt.listar_ventanas_abiertas():
            nombre = (v.get("proceso") or "").lower()
            if nombre:
                candidatas.add(nombre)
        propio = os.path.basename(sys.executable).lower()
        return sorted(n for n in candidatas
                      if n not in self.LANZADORES_JUEGOS and n != propio and n not in de_windows
                      and opt.evaluar_riesgo_proceso(n)[0] != "bloqueado")

    def _pintar_cerrar_al_jugar(self, candidatas):
        if not (hasattr(self, "lista_cerrar_jugar") and self.lista_cerrar_jugar.winfo_exists()):
            return
        for w in self.lista_cerrar_jugar.winfo_children():
            w.destroy()
        elegidas = {n.lower() for n in self.prefs.get("apps_cerrar_al_jugar", [])}
        if not candidatas:
            ctk.CTkLabel(self.lista_cerrar_jugar, text=t("gjuego_sin_candidatas"), text_color=T.texto2).pack(
                padx=8, pady=8)
            return
        for i, nombre in enumerate(candidatas):
            marca = casilla(self.lista_cerrar_jugar, nombre in elegidas, text=nombre)
            marca.configure(command=lambda n=nombre, c=marca: self._guardar_app_cerrar(n, bool(c.get())))
            marca.grid(row=i // 3, column=i % 3, sticky="w", padx=10, pady=4)

    def _apps_a_cerrar_al_jugar(self):
        """Lo que el Modo Juego debe cerrar AHORA: las apps marcadas, pero
        solo si el interruptor general está encendido."""
        if not self.prefs.get("cerrar_apps_al_jugar", False):
            return []
        return list(self.prefs.get("apps_cerrar_al_jugar", []))

    def _toggle_cerrar_al_jugar(self):
        activo = bool(self.switch_cerrar_jugar.get())
        self.prefs["cerrar_apps_al_jugar"] = activo
        prefs.guardar({"cerrar_apps_al_jugar": activo})
        self._log_dev(t("gjuego_cerrar_titulo"), "N/A",
                      t("gjuego_cerrar_on") if activo else t("gjuego_cerrar_off"),
                      seccion=t("seccion_gaming"), exito=True)

    def _guardar_app_cerrar(self, nombre, marcada):
        actuales = [n.lower() for n in self.prefs.get("apps_cerrar_al_jugar", [])]
        if marcada and nombre not in actuales:
            actuales.append(nombre)
        if not marcada and nombre in actuales:
            actuales.remove(nombre)
        self.prefs["apps_cerrar_al_jugar"] = actuales
        prefs.guardar({"apps_cerrar_al_jugar": actuales})

    # ---- Gaming: ajustes de Windows para juegos ----
    def _pintar_ajustes_juego(self, estado):
        if not (hasattr(self, "lista_ajustes_juego") and self.lista_ajustes_juego.winfo_exists()):
            return
        for w in self.lista_ajustes_juego.winfo_children():
            w.destroy()
        textos = {"modo_juego": ("gjuego_aj_modo", "gjuego_aj_modo_desc"),
                  "grabacion_fondo": ("gjuego_aj_grabacion", "gjuego_aj_grabacion_desc"),
                  "gpu_hags": ("gjuego_aj_hags", "gjuego_aj_hags_desc")}
        for i, (clave, (titulo, desc)) in enumerate(textos.items()):
            valor = estado.get(clave)
            recomendado = opt.AJUSTES_JUEGO[clave]["recomendado"]
            marca = t("gjuego_recomendado_on") if recomendado else t("gjuego_recomendado_off")
            if valor is None:
                marca += "  ·  " + t("gjuego_estado_desconocido")
            interruptor, _ = fila_interruptor(self.lista_ajustes_juego, "gaming", t(titulo), t(desc) + "\n" + marca,
                                              bool(valor), None, primera=i == 0, margen=18)
            interruptor.configure(command=lambda c=clave, sw=interruptor: self._accion_ajuste_juego(c, bool(sw.get())))

    def _accion_ajuste_juego(self, clave, activar):
        nombre = t({"modo_juego": "gjuego_aj_modo", "grabacion_fondo": "gjuego_aj_grabacion",
                    "gpu_hags": "gjuego_aj_hags"}[clave])

        def worker():
            exito, comando, anteriores = opt.set_ajuste_juego(clave, activar)
            if exito:
                self.deshacer.anotar("ajuste_juego", {"clave": clave, "anteriores": anteriores},
                                     t("desh_desc_ajuste_juego", ajuste=nombre))
                msg = t("gjuego_aj_ok_reinicio" if opt.AJUSTES_JUEGO[clave]["reinicio"] else "gjuego_aj_ok",
                        ajuste=nombre)
            else:
                msg = t("gjuego_aj_error", ajuste=nombre)
            self._log_dev(t("gjuego_log_ajuste", ajuste=nombre), comando, msg,
                          seccion=t("seccion_gaming"), exito=exito)

            estado = opt.leer_ajustes_juego() if not exito else None

            def terminar():
                self._actualizar_label("lbl_ajustes_juego", msg)
                if estado is not None:
                    self._pintar_ajustes_juego(estado)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Gaming: medidor de lag ----
    def _accion_medir_lag(self):
        if getattr(self, "_midiendo_lag", False):
            return
        self._midiendo_lag = True
        self.btn_medir_lag.configure(state="disabled")
        self.lbl_lag.configure(text=t("gjuego_lag_midiendo", tramo=t("gjuego_lag_router"), i=0, n=30))

        def progreso(tramo, i, n):
            texto = t("gjuego_lag_midiendo", tramo=t("gjuego_lag_router" if tramo == "router" else "gjuego_lag_internet"),
                      i=i, n=n)
            self.after(0, lambda: self._actualizar_label("lbl_lag", texto))

        def worker():
            r = opt.diagnosticar_lag(callback=progreso)
            self._log_dev(t("gjuego_log_lag"), "IcmpSendEcho x30 (router + 1.1.1.1)",
                          t({"bien": "gjuego_lag_v_bien", "local": "gjuego_lag_v_local",
                             "proveedor": "gjuego_lag_v_proveedor"}[r["veredicto"]]),
                          seccion=t("seccion_gaming"), exito=True)
            self.after(0, lambda: self._pintar_lag(r))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_lag(self, r):
        self._midiendo_lag = False
        if not (hasattr(self, "lbl_lag") and self.lbl_lag.winfo_exists()):
            return
        self.btn_medir_lag.configure(state="normal")

        def linea(etiqueta, s):
            if s is None:
                return t("gjuego_lag_linea_nd", tramo=etiqueta)
            if not s["recibidos"]:
                return t("gjuego_lag_linea_sin", tramo=etiqueta)
            return t("gjuego_lag_linea", tramo=etiqueta, media=s["media_ms"], jitter=s["jitter_ms"],
                     perdida=s["perdida_pct"], min=s["min_ms"], max=s["max_ms"])
        veredicto = t({"bien": "gjuego_lag_v_bien", "local": "gjuego_lag_v_local",
                       "proveedor": "gjuego_lag_v_proveedor"}[r["veredicto"]])
        if r["veredicto"] == "local":
            # El problema está en casa: el análisis de Wi-Fi dice por qué.
            veredicto += "\n" + t("gjuego_lag_ver_wifi")
        self.lbl_lag.configure(
            text="\n".join([linea(t("gjuego_lag_router") + (f' ({r["router_ip"]})' if r["router_ip"] else ""),
                                  r["router"]),
                            linea(t("gjuego_lag_internet") + " (1.1.1.1)", r["internet"]), "", veredicto]),
            text_color=COLOR_OK if r["veredicto"] == "bien" else COLOR_WARN)

    # ---- Gaming: bufferbloat (1.8.0) ----
    def _accion_bufferbloat(self):
        if getattr(self, "_midiendo_bb", False):
            return
        self._midiendo_bb = True
        self.btn_bufferbloat.configure(state="disabled")
        self.lbl_bufferbloat.configure(text=t("bb_fase_reposo", i=0, n=10), text_color=T.texto2)

        def progreso(fase, i, n):
            texto = t("bb_fase_reposo" if fase == "reposo" else "bb_fase_carga", i=i, n=n)
            self.after(0, lambda: self._actualizar_label("lbl_bufferbloat", texto))

        def worker():
            r = opt.prueba_bufferbloat(callback=progreso)
            if r["nota"]:
                msg = t("bb_resultado", nota=r["nota"], reposo=r["reposo"]["media_ms"], carga=r["carga"]["media_ms"],
                        aumento=r["aumento_ms"], mbps=r["mbps"])
                msg += "\n" + t("bb_v_bien" if r["nota"] in ("A+", "A", "B") else "bb_v_mal")
            else:
                msg = t("bb_error")
            self._log_dev(t("bb_titulo"), "IcmpSendEcho + descarga (speed.cloudflare.com)", msg.split("\n")[0],
                          seccion=t("seccion_gaming"), exito=bool(r["nota"]))
            self.after(0, lambda: self._pintar_bufferbloat(msg, r["nota"]))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_bufferbloat(self, msg, nota):
        self._midiendo_bb = False
        if not (hasattr(self, "lbl_bufferbloat") and self.lbl_bufferbloat.winfo_exists()):
            return
        self.btn_bufferbloat.configure(state="normal")
        color = COLOR_OK if nota in ("A+", "A") else (COLOR_WARN if nota in ("B", "C") else COLOR_CRIT)
        self.lbl_bufferbloat.configure(text=msg, text_color=color if nota else T.texto2)

    # ---- Gaming: Wi-Fi (1.7.0) ----
    def _accion_analizar_wifi(self):
        if getattr(self, "_analizando_wifi", False):
            return
        if not (hasattr(self, "btn_wifi") and self.btn_wifi.winfo_exists()):
            return
        self._analizando_wifi = True
        self.btn_wifi.configure(state="disabled")
        self.lbl_wifi.configure(text=t("wifi_analizando"), text_color=T.texto2)

        def worker():
            datos = sysmon.leer_wifi(escanear=True)
            texto, nivel = texto_wifi(datos)
            # En el historial va el veredicto, no el nombre de la red.
            self._log_dev(t("wifi_log"), "wlanapi.dll (WlanQueryInterface + WlanGetNetworkBssList)",
                          t(_VEREDICTOS_WIFI.get(nivel, "wifi_v_bien")) if nivel != "info" else texto,
                          seccion=t("seccion_gaming"), exito=datos is not None)
            self.after(0, lambda: self._pintar_wifi(texto, nivel))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_wifi(self, texto, nivel):
        self._analizando_wifi = False
        if not (hasattr(self, "lbl_wifi") and self.lbl_wifi.winfo_exists()):
            return
        self.btn_wifi.configure(state="normal")
        colores = {"bien": COLOR_OK, "regular": COLOR_WARN, "mal": COLOR_CRIT}
        self.lbl_wifi.configure(text=texto, text_color=colores.get(nivel, T.texto2))

    def _actualizar_tarjeta_gaming(self):
        if not (hasattr(self, "lbl_estado_gaming") and self.lbl_estado_gaming.winfo_exists()):
            return
        if self.autopilot.activo:
            self.lbl_estado_gaming.configure(text=t("gaming_estado_on"), text_color=COLOR_OK)
        else:
            self.lbl_estado_gaming.configure(text=t("gaming_estado_off"), text_color=T.texto2)

    def _pintar_juegos(self, juegos):
        if not (hasattr(self, "lista_juegos") and self.lista_juegos.winfo_exists()):
            return
        for w in self.lista_juegos.winfo_children():
            w.destroy()
        if juegos:
            self._carpetas_juegos = opt.carpetas_de_juegos(juegos)
        if not juegos:
            Texto(self.lista_juegos, t("gaming_sin_juegos"), size=12, color=T.texto2, wraplength=760).pack(
                fill="x", padx=18)
            return
        marcados = set(self.prefs.get("juegos_modo_auto", []))
        for i, j in enumerate(juegos):
            tamano_txt = opt.format_bytes(j["bytes"]) if j["bytes"] else t("gaming_tamano_nd")
            derecha = fila(self.lista_juegos, "gaming", j["nombre"],
                           t("gaming_juego_detalle", plataforma=j["plataforma"], tamano=tamano_txt),
                           primera=i == 0, margen=18)
            if not j.get("ruta"):
                continue
            interruptor = ctk.CTkSwitch(derecha, text="", width=46)
            interruptor.configure(command=lambda j=j, sw=interruptor: self._toggle_juego_auto(j, sw))
            if os.path.normcase(os.path.normpath(j["ruta"])) + os.sep in marcados:
                interruptor.select()
            interruptor.pack(side="right")
            Texto(derecha, t("gaming_auto_label"), size=11, color=T.texto3).pack(side="right", padx=(0, 8))

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
                          seccion=t("seccion_gaming"), exito=True, bytes_ram=liberado, archivos_afectados=procesos)

            if not self.autopilot.activo:
                self.after(0, self._toggle_autopilot)

            exito_fps, comando_fps = opt.abrir_contador_fps_windows()
            self._log_dev(t("gaming_log_antes_fps"), comando_fps,
                          t("gaming_fps_abierto") if exito_fps else t("gaming_fps_no_abierto"),
                          seccion=t("seccion_gaming"), exito=exito_fps)

            msg = (t("gaming_listo_con_fps", tamano=opt.format_bytes(liberado)) if exito_fps
                   else t("gaming_listo_sin_fps", tamano=opt.format_bytes(liberado)))
            self.after(0, lambda: self._actualizar_label("lbl_resultado_gaming", msg))
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
        if exito:
            msg = t("gaming_fps_ok")
        else:
            # Se dice qué falta exactamente, en vez de un "no se pudo" a
            # secas. El motivo llega como CLAVE desde el optimizador, nunca
            # como texto ya traducido.
            _, motivo = opt.game_bar_disponible()
            msg = t(motivo) if motivo else t("gaming_fps_error")
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

        def poner_switch(encendido, texto):
            def hacer():
                interruptor = getattr(self, "switch_limpieza", None)
                if interruptor is not None and interruptor.winfo_exists():
                    interruptor.select() if encendido else interruptor.deselect()
                self._actualizar_label("lbl_limpieza_prog", texto)
            self.after(0, hacer)

        def worker():
            if encender:
                exito, comando = opt.crear_limpieza_programada(frecuencia=frecuencia, hora=hora)
                # Comprobar el EFECTO (1.8.0): que la tarea exista de verdad.
                exito = exito and opt.limpieza_programada_activa()
                msg = (t("segplano_programada_ok", frecuencia=etiqueta_frecuencia, hora=hora)
                       if exito else t("segplano_programada_error"))
                self._log_dev(t("log_limpieza_prog_on"), comando, msg, seccion=t("seccion_segundo_plano"), exito=exito)
                if exito:
                    self.prefs["limpieza_hora"] = hora
                    self.prefs["limpieza_frecuencia"] = frecuencia
                    prefs.guardar({"limpieza_hora": hora, "limpieza_frecuencia": frecuencia})
                poner_switch(exito, msg)
            else:
                exito, comando = opt.quitar_limpieza_programada()
                msg = t("segplano_quitada_ok") if exito else t("segplano_quitada_error")
                self._log_dev(t("log_limpieza_prog_off"), comando, msg,
                              seccion=t("seccion_segundo_plano"), exito=exito)
                # Si no se pudo quitar, sigue programada: el interruptor vuelve.
                poner_switch(not exito, msg)
        threading.Thread(target=worker, daemon=True).start()

    def _reprogramar_limpieza(self):
        """Cambiar la hora o la frecuencia con la limpieza ya activa vuelve a
        crear la tarea (antes no hacía nada hasta apagar y encender)."""
        interruptor = getattr(self, "switch_limpieza", None)
        if interruptor is not None and interruptor.winfo_exists() and interruptor.get():
            self._toggle_limpieza_programada()

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
                     font=fuente(size=15, weight="bold")).pack(pady=(20, 6))
        ctk.CTkLabel(dialogo,
                     text=t("ligero_texto"),
                     font=fuente(size=12), wraplength=380, justify="left").pack(padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def activar():
            dialogo.destroy()
            self.prefs["modo_ligero"] = True
            prefs.guardar({"modo_ligero": True})
            self._aplicar_preferencia_animaciones()

        ctk.CTkButton(fila, text=t("ligero_no"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(
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
            self._cpu_temp_leida = True
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
    MAX_HISTORIAL = 200

    def mostrar_reporte(self):
        """Historial (rediseño 1.8.0). Cada acción es una fila de un lienzo
        (ListaLienzo): con el historial completo eran miles de tarjetas de
        widgets, segundos de ventana congelada. Se ven de 200 en 200 y, al
        pulsar una, sale el resultado entero."""
        self._limpiar_contenido()
        derecha = self._encabezado(t("hist_titulo"), t("hist_subtitulo"))
        self.btn_borrar_historial = boton_secundario(derecha, _sin_emoji(t("hist_borrar")),
                                                     self._confirmar_borrar_historial, icono="papelera", height=38)
        self.btn_borrar_historial.pack(side="right")
        boton_secundario(derecha, t("hist_exportar_txt"), self._exportar_reporte, icono="archivo",
                         height=38).pack(side="right", padx=(0, 10))
        self.btn_informe_pdf = ctk.CTkButton(derecha, text=t("informe_btn"), height=38,
                                             image=iconos.icono("archivo", T.sobre_acento, 16), compound="left",
                                             command=self._crear_informe_pdf)
        self.btn_informe_pdf.pack(side="right", padx=(0, 10))

        # Elegir entre lo de ahora y todo lo guardado. Antes solo existía lo
        # de la sesión, porque al cerrar la app se perdía todo.
        self.ambito_historial = ctk.CTkSegmentedButton(
            self.contenido, values=[t("hist_ambito_sesion"), t("hist_ambito_todo"),
                                     t("hist_ambito_deshacer")],
            command=lambda v: self._cambiar_ambito_historial())
        self.ambito_historial.set(t("hist_ambito_sesion"))
        self.ambito_historial.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        cuerpo = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        cuerpo.grid(row=2, column=0, columnspan=3, sticky="nswe")
        self.cuerpo_historial = cuerpo

        panel = tarjeta(cuerpo)
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lbl_resumen_historial = Texto(panel, "", size=13, weight="bold", wraplength=860)
        self.lbl_resumen_historial.pack(fill="x", padx=18, pady=(16, 10))
        texto_fluido(self.lbl_resumen_historial, panel, 36)
        fila_busqueda = Caja(panel)
        fila_busqueda.pack(fill="x", padx=18, pady=(0, 16))
        self.combo_seccion_historial = ctk.CTkOptionMenu(
            fila_busqueda, values=[t("hist_todas_secciones")], width=180,
            command=lambda v: self._filtrar_historial())
        self.combo_seccion_historial.set(t("hist_todas_secciones"))
        self.combo_seccion_historial.pack(side="right")
        self.entry_buscar_historial = ctk.CTkEntry(
            fila_busqueda, placeholder_text=_sin_emoji(t("hist_buscar_placeholder")))
        self.entry_buscar_historial.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_buscar_historial.bind("<KeyRelease>", lambda e: self._filtrar_historial(esperar=True))
        self.lbl_informe_hist = Texto(panel, t("informe_desc"), size=12, color=T.texto2, wraplength=860)
        self.lbl_informe_hist.pack(fill="x", padx=18, pady=(0, 16))
        texto_fluido(self.lbl_informe_hist, panel, 36)
        if getattr(self, "_informe_en_curso", False):
            self.btn_informe_pdf.configure(state="disabled")

        panel = tarjeta(cuerpo)
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lista_historial = Caja(panel)
        self.lista_historial.pack(fill="x", pady=(8, 8))
        self._cambiar_ambito_historial()

    def _ambito_historial_actual(self):
        """Cuál de las tres vistas está elegida: "sesion", "todo" o "deshacer"."""
        if not (hasattr(self, "ambito_historial") and self.ambito_historial.winfo_exists()):
            return "sesion"
        valor = self.ambito_historial.get()
        if valor == t("hist_ambito_todo"):
            return "todo"
        if valor == t("hist_ambito_deshacer"):
            return "deshacer"
        return "sesion"

    def _viendo_historial_completo(self):
        return self._ambito_historial_actual() == "todo"

    def _entradas_del_ambito(self):
        """Las entradas que toca mostrar según lo elegido arriba."""
        if self._viendo_historial_completo():
            return self.reporte.historial_completo()
        return self.reporte.entradas_recientes_primero()

    def _cambiar_ambito_historial(self):
        """Rehace el resumen y la lista de secciones al cambiar de ámbito.

        Leer el historial completo toca el disco, así que va en un hilo: con
        3000 acciones guardadas se notaría el tirón al pulsar."""
        ambito = self._ambito_historial_actual()

        def worker():
            if ambito == "deshacer":
                pendientes = self.deshacer.pendientes()
                texto = t("hist_resumen_deshacer", total=len(pendientes))
                entradas, secciones = [], []
                def pintar_deshacer():
                    if not (hasattr(self, "lbl_resumen_historial")
                            and self.lbl_resumen_historial.winfo_exists()):
                        return
                    self.lbl_resumen_historial.configure(text=texto)
                    self.combo_seccion_historial.configure(values=[t("hist_todas_secciones")])
                    self.combo_seccion_historial.set(t("hist_todas_secciones"))
                    self._pintar_lista_deshacer(pendientes)
                self.after(0, pintar_deshacer)
                return

            if ambito == "todo":
                resumen = self.reporte.resumen_historial()
                entradas = self.reporte.historial_completo()
                texto = t("hist_resumen_todo",
                          total=resumen["acciones"], sesiones=resumen["sesiones"],
                          espacio=opt.format_bytes(resumen["bytes"]),
                          ram=opt.format_bytes(resumen["ram"]),
                          mes_acciones=resumen["mes_acciones"],
                          mes_espacio=opt.format_bytes(resumen["mes_bytes"]),
                          mes_ram=opt.format_bytes(resumen["mes_ram"]),
                          desde=(resumen["desde"] or t("hist_sin_fecha"))[:10])
            else:
                entradas = self.reporte.entradas_recientes_primero()
                texto = t("hist_resumen",
                          total=self.reporte.total_acciones(),
                          exitosas=self.reporte.total_exitosas(),
                          fallidas=self.reporte.total_fallidas(),
                          espacio=opt.format_bytes(self.reporte.total_bytes_liberados()),
                          ram=opt.format_bytes(self.reporte.total_bytes_ram()))
            secciones = sorted({e.get("seccion", "") for e in entradas if e.get("seccion")})

            def pintar():
                if not (hasattr(self, "lbl_resumen_historial")
                        and self.lbl_resumen_historial.winfo_exists()):
                    return
                self.lbl_resumen_historial.configure(text=texto)
                elegida = self.combo_seccion_historial.get()
                self.combo_seccion_historial.configure(
                    values=[t("hist_todas_secciones")] + secciones)
                # Si la sección que estaba elegida ya no existe en este
                # ámbito, se vuelve a "todas" en vez de dejar una selección
                # que no filtra nada y deja la lista vacía sin explicación.
                if elegida not in secciones:
                    self.combo_seccion_historial.set(t("hist_todas_secciones"))
                self._filtrar_historial()
            self.after(0, pintar)
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_lista_deshacer(self, pendientes):
        """La lista de cambios que todavía se pueden revertir.

        Arriba de todo va el aviso de lo que NO se puede deshacer. Eso es
        más importante que la propia lista: un botón de "Deshacer" que a
        veces no funciona es peor que no tenerlo, porque la gente acaba
        contando con él para cosas que no cubre.
        """
        caja = getattr(self, "lista_historial", None)
        if caja is None or not caja.winfo_exists():
            return
        for w in caja.winfo_children():
            w.destroy()
        Texto(caja, _sin_emoji(t("desh_aviso_titulo")), size=13, weight="bold", color=T.aviso).pack(
            fill="x", padx=20, pady=(8, 2))
        texto_fluido(Texto(caja, t("desh_aviso_texto"), size=12, color=T.texto2, wraplength=820), caja, 40).pack(
            fill="x", padx=20, pady=(0, 10))
        linea(caja).pack(fill="x", padx=20)
        if not pendientes:
            self._aviso_lista(caja, t("desh_vacio")).pack_configure(pady=(12, 8))
            return
        lienzo = ListaLienzo(caja)
        lienzo.pack(fill="x")
        lienzo.poner([{"icono": "historial",
                       "titulo": entrada.get("descripcion") or t(desh.TIPOS.get(entrada.get("tipo"),
                                                                                  "desh_tipo_desconocido")),
                       "detalle": entrada.get("timestamp", ""),
                       "acciones": [(_sin_emoji(t("desh_boton")), lambda e=entrada: self._confirmar_deshacer(e))]}
                      for entrada in pendientes])

    def _confirmar_deshacer(self, entrada):
        descripcion = entrada.get("descripcion") or t("desh_este_cambio")
        self._pedir_confirmacion(
            t("desh_confirmar_titulo"),
            t("desh_confirmar_mensaje", cambio=descripcion),
            t("desh_boton"),
            lambda: self._ejecutar_deshacer(entrada))

    def _ejecutar_deshacer(self, entrada):
        """Revertir toca el sistema (powercfg, servicios, registro): va en un
        hilo, como todo lo demás que puede tardar."""
        CLAVES = ("desh_ok", "desh_fallo", "desh_no_encontrado", "desh_tipo_desconocido")

        def worker():
            exito, clave, comando = self.deshacer.deshacer(entrada.get("id"), opt)
            msg = t(clave) if clave in CLAVES else t("desh_fallo")
            self._log_dev(t("desh_log", cambio=entrada.get("descripcion") or ""),
                          comando or "N/A", msg,
                          seccion=t("seccion_historial"), exito=exito)

            def despues():
                self._mostrar_popup_info(t("desh_confirmar_titulo"), msg)
                # Se repinta la lista: lo deshecho ya no debe seguir ahí.
                if self._ambito_historial_actual() == "deshacer":
                    self._cambiar_ambito_historial()
            self.after(0, despues)
        threading.Thread(target=worker, daemon=True).start()

    def _confirmar_borrar_historial(self):
        self._pedir_confirmacion(
            t("hist_borrar_titulo"), t("hist_borrar_mensaje"), t("hist_borrar"),
            self._borrar_historial)

    def _borrar_historial(self):
        exito = self.reporte.borrar_historial()
        self._log_dev(t("hist_log_borrar"), "historial.jsonl",
                      t("hist_borrado") if exito else t("hist_borrar_error"),
                      seccion=t("seccion_historial"), exito=exito)
        self._cambiar_ambito_historial()

    def _filtrar_historial(self, esperar=False, mas=False):
        if esperar:
            if getattr(self, "_filtro_historial", None):
                self.after_cancel(self._filtro_historial)
            self._filtro_historial = self.after(200, self._filtrar_historial)
            return
        self._filtro_historial = None
        caja = getattr(self, "lista_historial", None)
        if caja is None or not caja.winfo_exists():
            return
        self._limite_historial = (getattr(self, "_limite_historial", self.MAX_HISTORIAL) + self.MAX_HISTORIAL
                                  if mas else self.MAX_HISTORIAL)
        for w in caja.winfo_children():
            w.destroy()

        termino = self.entry_buscar_historial.get().strip().lower() if hasattr(self, "entry_buscar_historial") else ""
        seccion_elegida = (self.combo_seccion_historial.get()
                           if hasattr(self, "combo_seccion_historial") else t("hist_todas_secciones"))
        entradas = self._entradas_del_ambito()
        if termino:
            entradas = [e for e in entradas
                        if termino in (e.get("accion") or "").lower()
                        or termino in (e.get("seccion") or "").lower()
                        or termino in (e.get("resultado") or "").lower()]
        if seccion_elegida and seccion_elegida != t("hist_todas_secciones"):
            entradas = [e for e in entradas if e.get("seccion") == seccion_elegida]

        if not entradas:
            sin_filtros = not termino and seccion_elegida == t("hist_todas_secciones")
            if not sin_filtros:
                texto = t("hist_sin_resultados")
            else:
                texto = (t("hist_vacio_historial") if self._viendo_historial_completo()
                         else t("hist_vacio"))
            self._aviso_lista(caja, texto).pack_configure(pady=(12, 8))
            return
        vistas = entradas[:self._limite_historial]
        lienzo = ListaLienzo(caja)
        lienzo.pack(fill="x")
        lienzo.poner([self._fila_historial(e) for e in vistas])
        if len(entradas) > len(vistas):
            pie = Caja(caja)
            pie.pack(fill="x", padx=20, pady=(8, 8))
            Texto(pie, t("hist_mostrando", n=len(vistas), total=len(entradas)), size=12,
                  color=T.texto2).pack(side="left")
            boton_secundario(pie, t("hist_ver_mas", n=min(self.MAX_HISTORIAL, len(entradas) - len(vistas))),
                             lambda: self._filtrar_historial(mas=True), height=32).pack(side="right")

    def _fila_historial(self, entrada):
        resultado = str(entrada.get("resultado") or "").strip().split("\n")[0]
        detalle = " · ".join(x for x in (entrada.get("timestamp"), entrada.get("seccion"), resultado) if x)
        return {"icono": "correcto" if entrada.get("exito") else "fallo",
                "color_icono": T.ok if entrada.get("exito") else T.critico,
                "titulo": entrada.get("accion") or "", "detalle": detalle,
                "entrar": lambda e=entrada: self._detalle_historial(e)}

    def _detalle_historial(self, entrada):
        """El resultado entero de una acción (en la lista se ve una línea)."""
        partes = [" · ".join(x for x in (entrada.get("timestamp"), entrada.get("seccion")) if x),
                  t("hist_resultado", resultado=entrada.get("resultado") or "")]
        # El comando técnico exacto solo se muestra en la Edición Administrador.
        if EDICION == "admin" and entrada.get("comando"):
            partes.append(t("hist_comando", comando=entrada["comando"]))
        self._mostrar_popup_info(entrada.get("accion") or t("hist_titulo"), "\n\n".join(partes))

    # ---------------- El informe en PDF (1.8.0) ----------------
    CONSEJOS_SALUD = {"ram": "informe_consejo_ram", "disco": "informe_consejo_disco_lleno",
                      "inicio": "informe_consejo_inicio", "temporales": "informe_consejo_temporales",
                      "reinicio": "informe_consejo_reinicio"}
    ESTADOS_INFORME = {"bien": "informe_estado_bien", "atencion": "informe_estado_atencion",
                       "critico": "informe_estado_critico"}
    MAX_ACCIONES_INFORME = 60

    def _crear_informe_pdf(self):
        """Cómo está el equipo, qué problemas tiene y qué hizo TechClean, en
        un PDF con la cara de la app (informe.py), en el Escritorio. Todo lo
        que mira es de solo lectura."""
        if getattr(self, "_informe_en_curso", False):
            return
        self._informe_en_curso = True
        boton = getattr(self, "btn_informe_pdf", None)
        if boton is not None and boton.winfo_exists():
            boton.configure(state="disabled")

        def progreso(clave):
            self.after(0, lambda: self._actualizar_label("lbl_informe_hist", t(clave)))

        def worker():
            ruta = None
            try:
                datos = self._datos_informe(progreso)
                html = informe.generar_html(datos, t)
                progreso("informe_paso_pdf")
                carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
                nombre = t("informe_archivo", equipo=datos.get("equipo_nombre") or "PC",
                           fecha=datetime.now().strftime("%Y-%m-%d %H%M"))
                nombre = "".join(c for c in nombre if c not in '\\/:*?"<>|')
                ruta = os.path.join(carpeta, nombre + ".pdf")
                if informe.a_pdf(html, ruta):
                    msg = t("informe_listo_pdf", ruta=ruta)
                else:
                    # Sin Edge (o si no pudo): la misma página, que el
                    # navegador pasa a PDF con Ctrl+P.
                    ruta = os.path.join(carpeta, nombre + ".html")
                    with open(ruta, "w", encoding="utf-8") as f:
                        f.write(html)
                    msg = t("informe_listo_html", ruta=ruta)
                os.startfile(ruta)
                exito = True
            except Exception as e:
                msg, exito = t("informe_error", error=e), False
            self._log_dev(t("informe_log"), "informe.generar_html + msedge --headless --print-to-pdf", msg,
                          seccion=t("seccion_historial"), exito=exito)

            def terminar():
                self._informe_en_curso = False
                b = getattr(self, "btn_informe_pdf", None)
                if b is not None and b.winfo_exists():
                    b.configure(state="normal")
                self._actualizar_label("lbl_informe_hist", msg)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _datos_informe(self, progreso):
        """Todo lo del informe, en un hilo (registro de eventos, discos,
        protección, auditoría...: 20-40 s). Solo lee: generar el informe no
        cambia nada del equipo."""
        info = dict(self._system_info_cache)
        datos = {"version": APP_VERSION, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "equipo_nombre": info.get("hostname") or "", "logo": informe.logo_data_uri(rutas.recurso("icono.ico"))}
        problemas = []

        def problema(nivel, titulo, detalle="", consejo=""):
            problemas.append({"nivel": nivel, "titulo": titulo, "detalle": detalle, "consejo": consejo})

        # ---- La salud de Inicio y el equipo ----
        progreso("informe_paso_equipo")
        salud = self._medir_salud()
        datos["salud"] = {"puntaje": salud["puntaje"], "nivel": salud["nivel"],
                          "estado": t(self.ESTADOS_INFORME[salud["nivel"]]),
                          "texto": t("informe_salud_texto", puntaje=salud["puntaje"]) + " " + salud["detalle"]}
        for tipo, nivel, texto in salud["motivos"]:
            problema(nivel, texto[:1].upper() + texto[1:], "", t(self.CONSEJOS_SALUD[tipo]))
        cargando = t("comun_cargando")
        equipo = [(t("inf_eq_nombre"), info.get("hostname")), (t("inf_eq_so"), info.get("sistema_operativo")),
                  (t("inf_eq_cpu"), info.get("procesador")),
                  (t("inf_eq_ram"), opt.format_bytes(psutil.virtual_memory().total)),
                  (t("inf_eq_placa"), info.get("placa_madre"))]
        try:
            gpu = sysmon.get_gpu_info() or {}
            equipo.append((t("informe_eq_gpu"), gpu.get("nombre")))
        except Exception:
            pass
        for p in sysmon.get_disk_partitions():
            equipo.append((t("informe_eq_unidad", unidad=p["unidad"]),
                           t("informe_eq_unidad_valor", libre=opt.format_bytes(p["libre_gb"] * 1024 ** 3),
                             total=opt.format_bytes(p["total_gb"] * 1024 ** 3), pct=f'{p["porcentaje"]:.0f}')))
        dias = self.vigilante.dias_encendido()
        if dias is not None:
            equipo.append((t("informe_eq_encendido"), t("informe_eq_dias", n=f"{dias:.1f}") if dias >= 1
                           else t("informe_eq_horas", n=max(1, round(dias * 24)))))

        # ---- Estabilidad: pantallazos, apagados, apps que se cierran ----
        progreso("informe_paso_fallos")
        diag = tec.diagnostico_fallos(30)
        if diag:
            nivel, motivos = tec.veredicto_fallos(diag)
            apagados = diag["apagados"]
            equipo.append((t("informe_eq_estabilidad"),
                           t("informe_eq_estabilidad_valor", pantallazos=len(diag["pantallazos"]),
                             apagados=len(apagados))))
            if nivel != "bien":
                lineas = [t("fallos_d_apagados") + ": " + t("fallos_v_apagados", n=len(apagados),
                                                                  suspension=sum(1 for a in apagados if a["suspension"]))]
                for p in diag["pantallazos"][:5]:
                    codigo = f'0x{p["codigo"]:X}' if p["codigo"] else ""
                    lineas.append(t("fallos_linea_pantallazo", fecha=p["fecha"], codigo=codigo,
                                    nombre=p["nombre"] or "", causa=t(p["causa"])))
                problema(nivel, t("informe_p_estabilidad"), "\n".join(lineas), " ".join(t(m) for m in motivos))

        # ---- Discos y batería ----
        progreso("informe_paso_discos")
        for d in tec.salud_discos() or []:
            nivel, motivos = tec.veredicto_disco(d)
            nombre = t("inf_disco", nombre=d.get("nombre") or "?")
            equipo.append((nombre, _sin_emoji(t(tec.NIVELES_SALUD[nivel]))))
            if nivel != "bien":
                problema(nivel, nombre, ", ".join(t(m) for m in motivos), t("informe_consejo_disco"))
        for b in tec.salud_bateria() or []:
            resumen = t("bat_resumen", porcentaje=b.get("porcentaje"), ciclos=b.get("ciclos") or "?")
            equipo.append((t("inf_bateria"), resumen))
            if b.get("veredicto") not in (None, "bien"):
                problema(b["veredicto"], t("inf_bateria"), resumen, t("informe_consejo_bateria"))
        datos["equipo"] = [(k, v) for k, v in equipo if v and v != cargando]

        # ---- Protección, secuestros y malware ----
        progreso("informe_paso_seguridad")
        try:
            filas = (seg.evaluar_proteccion(seg.leer_proteccion())
                     + seg.evaluar_secuestros(seg.chequeo_secuestros()))
        except Exception:
            filas = []
        for clave, nivel, texto, campos in filas:
            if nivel in ("atencion", "critico") and clave in self.FILAS_PROTECCION:
                problema(nivel, t(self.FILAS_PROTECCION[clave][1]), t(texto, **campos), t("informe_consejo_seguridad"))
        hallazgos = getattr(self, "_auditoria_cache", None)
        if hallazgos is None:
            try:
                hallazgos = seg.evaluar(seg.recolectar())
                self._auditoria_cache = hallazgos
            except Exception:
                hallazgos = []
        for h in hallazgos:
            if h.get("nivel") not in ("alto", "medio"):
                continue
            motivos = [t(m, original=h.get("original") or "?") if m == "seg_motivo_interprete_renombrado" else t(m)
                       for m in h.get("motivos") or []]
            problema("critico" if h["nivel"] == "alto" else "atencion", t(h["clave"]),
                     "\n".join(motivos + ([h["detalle"]] if h.get("detalle") else [])), t("informe_consejo_auditoria"))

        # ---- Drivers ----
        progreso("informe_paso_drivers")
        for d in sysmon.listar_dispositivos_con_problemas() or []:
            problema("atencion", t("informe_p_driver", nombre=d.get("nombre") or "?"), d.get("explicacion") or "",
                     t("informe_consejo_driver"))
        datos["problemas"] = problemas
        graves = sum(1 for p in problemas if p["nivel"] == "critico")
        revisar = sum(1 for p in problemas if p["nivel"] == "atencion")
        orden = ["bien", "atencion", "critico"]
        peor = max([salud["nivel"]] + [p["nivel"] for p in problemas if p["nivel"] in orden], key=orden.index)
        datos["salud"]["nivel"] = peor
        datos["salud"]["estado"] = t(self.ESTADOS_INFORME[peor])
        if graves:
            datos["salud"]["texto"] = t("informe_salud_graves", puntaje=salud["puntaje"], n=graves)
        elif revisar and salud["nivel"] == "bien":
            datos["salud"]["texto"] = t("informe_salud_revisar", puntaje=salud["puntaje"], n=revisar)

        # ---- Lo que hizo TechClean: esta sesión (o lo último guardado) ----
        entradas = self.reporte.entradas_recientes_primero() or self.reporte.historial_completo(limite=40)
        disco_lib = sum(rep._bytes_de(e)[0] for e in entradas)
        ram_lib = sum(rep._bytes_de(e)[1] for e in entradas)
        bien = sum(1 for e in entradas if e.get("exito"))
        # Sin trabajo hecho, sin cifras de trabajo ("0 B liberados" no dice nada).
        datos["totales"] = [(v, k) for v, k, hay in (
            (opt.format_bytes(disco_lib), t("informe_cifra_disco"), disco_lib > 0),
            (opt.format_bytes(ram_lib), t("informe_cifra_ram"), ram_lib > 0),
            (f"{bien}/{len(entradas)}", t("informe_cifra_acciones"), bool(entradas))) if hay]
        datos["acciones"] = [{"fecha": (e.get("timestamp") or "")[:16], "seccion": e.get("seccion"),
                              "accion": e.get("accion"), "resultado": e.get("resultado"), "exito": e.get("exito")}
                             for e in entradas[:self.MAX_ACCIONES_INFORME]]
        datos["acciones_mas"] = max(0, len(entradas) - self.MAX_ACCIONES_INFORME)
        return datos

    def _exportar_reporte(self):
        """Exporta lo que se está viendo: la sesión o el historial entero."""
        completo = self._viendo_historial_completo()
        nombre = "historial_techclean.txt" if completo else "reporte_techclean.txt"
        carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
        incluir_comando = (EDICION == "admin")
        try:
            ruta = self.reporte.export_txt(os.path.join(carpeta, nombre),
                                            incluir_comando=incluir_comando,
                                            incluir_historial=completo)
        except Exception:
            # El Escritorio puede no ser escribible (carpeta redirigida,
            # permisos, OneDrive sin sesión): se cae a la carpeta de datos,
            # que es nuestra y siempre existe.
            try:
                ruta = self.reporte.export_txt(os.path.join(prefs.carpeta_datos(), nombre),
                                                incluir_comando=incluir_comando,
                                                incluir_historial=completo)
            except Exception:
                self._mostrar_popup_info(t("hist_exportado_titulo"), t("hist_export_error"))
                return
        self._mostrar_popup_info(t("hist_exportado_titulo"), t("hist_exportado_msg", ruta=ruta))

    def _mostrar_privacidad_app(self):
        """Lo esencial de PRIVACIDAD.md (1.8.0), dentro de la app: qué guarda,
        cuándo se conecta y qué no hace."""
        self._mostrar_popup_info(t("priv_app_titulo"), t("priv_app_texto"))

    def _mostrar_popup_info(self, titulo, mensaje):
        """Un aviso con su texto, del tamaño del texto. BUG corregido (1.8.0):
        era una ventana fija de 420x150 y un texto largo se cortaba (el
        detalle de una acción del Historial, de algo del Inicio de Windows,
        la explicación de la protección). Si es muy largo, con scroll, y se
        puede seleccionar y copiar."""
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(titulo)
        dialogo.grab_set()
        mensaje = str(mensaje)
        if len(mensaje) > 1200 or mensaje.count("\n") > 16:
            caja = ctk.CTkTextbox(dialogo, width=560, height=340, wrap="word", font=fuente(size=12))
            caja.insert("1.0", mensaje)
            caja.configure(state="disabled")
            caja.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        else:
            ctk.CTkLabel(dialogo, text=mensaje, wraplength=480,
                         justify="left" if "\n" in mensaje else "center").pack(pady=(24, 12), padx=24)
        ctk.CTkButton(dialogo, text=t("comun_ok"), command=dialogo.destroy).pack(pady=(4, 16))
        # El tamaño que pide lo de dentro (geometry de customtkinter va sin
        # escalar: se divide por el zoom de Windows).
        dialogo.update_idletasks()
        escala = ctk.ScalingTracker.get_window_scaling(dialogo) or 1
        ancho = max(420, round(dialogo.winfo_reqwidth() / escala))
        alto = max(150, round(dialogo.winfo_reqheight() / escala))
        dialogo.geometry(f"{ancho}x{alto}")

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
                     font=fuente(size=16, weight="bold"), text_color=COLOR_CRIT).pack(pady=(16, 4))
        ctk.CTkLabel(dialogo,
                     text=t("error_explicacion"),
                     font=fuente(size=11), text_color=T.texto2, wraplength=520, justify="left").pack(
            padx=20, pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=fuente(family="Consolas", size=10))
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
        ctk.CTkLabel(self.contenido, text=t("dev_panel_titulo"),
                     font=fuente(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self.contenido, text=t("dev_panel_sub"), anchor="w",
                     font=fuente(size=12), text_color=T.texto2).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(2, weight=1)
        self.dev_console = DevConsole(
            self.contenido,
            on_comando=lambda texto: self._ejecutar_comando(texto, consola=self.dev_console))
        self.dev_console.grid(row=2, column=0, columnspan=3, sticky="nswe", padx=8, pady=(0, 10))

        # La referencia técnica antes era una etiqueta gris suelta debajo de
        # la consola, escrita a mano en español — o sea que en la build en
        # inglés salía en español. Ahora es una tarjeta traducida y plegable:
        # ocupa nueve líneas que no hacen falta mientras estás escribiendo.
        self._ref_abierta = False
        tarjeta_ref = ctk.CTkFrame(self.contenido, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        tarjeta_ref.grid(row=3, column=0, columnspan=3, sticky="we", padx=8, pady=(0, 8))
        boton_ref = ctk.CTkButton(
            tarjeta_ref, text="▸  " + t("dev_ref_titulo"), anchor="w",
            fg_color="transparent", hover_color=T.boton2_hover, height=30,
            font=fuente(size=12, weight="bold"))
        boton_ref.pack(fill="x", padx=6, pady=6)
        cuerpo_ref = ctk.CTkLabel(tarjeta_ref, text=t("dev_ref_cuerpo"), justify="left",
                                  anchor="w", font=fuente(family="Consolas", size=11),
                                  text_color=T.texto2)

        def alternar_ref():
            self._ref_abierta = not self._ref_abierta
            if self._ref_abierta:
                cuerpo_ref.pack(fill="x", padx=16, pady=(0, 12))
                boton_ref.configure(text="▾  " + t("dev_ref_titulo"))
            else:
                cuerpo_ref.pack_forget()
                boton_ref.configure(text="▸  " + t("dev_ref_titulo"))

        boton_ref.configure(command=alternar_ref)

    def _log_dev(self, accion, comando, resultado, seccion=None, exito=True,
                 bytes_liberados=0, archivos_afectados=0, bytes_ram=0):
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
                              bytes_liberados, archivos_afectados, bytes_ram)
        self.after(0, _hacer)

    # ---------------- Panel de comandos oculto (solo Edición Cliente) ----------------
    def mostrar_panel_oculto(self):
        if EDICION != "cliente" or not self.modo_desarrollador.get():
            self.mostrar_dashboard()
            return
        self._limpiar_contenido()
        ctk.CTkLabel(self.contenido, text=t("consola_titulo_panel"),
                     font=fuente(size=22, weight="bold")).grid(
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

        # Antes todo se imprimía igual: un "listo" y un "no se pudo" salían
        # del mismo color y con la misma forma. Ahora cada respuesta lleva su
        # tipo, y decir(exito, texto) elige verde o rojo por el resultado de
        # verdad de la operación, no por lo que dice la frase.
        def decir(exito, mensaje):
            consola.imprimir(mensaje, "ok" if exito else "error")

        if comando in ("/help", "/ayuda", "ayuda", "help", "?"):
            ancho = max(len(c) for c in COMANDOS_DISPONIBLES)
            lineas = [f"{c:<{ancho}}   {t(clave)}" for c, clave in
                      sorted(COMANDOS_DISPONIBLES.items())]
            consola.imprimir("\n".join(lineas), "info")
            return

        if comando == "/limpiar":
            consola.limpiar()
            return

        if comando == "/guardar":
            consola.guardar_log()
            return

        if comando == "/version":
            consola.imprimir(self._texto_version_consola(), "info")
            return

        if comando == "/estado":
            # Una foto del sistema dentro de la propia consola: es la
            # pregunta que uno se hace justo antes y justo después de
            # lanzar algo, y hasta ahora había que irse a otra pantalla.
            consola.imprimir(t("consola_estado_midiendo"), "dim")

            def worker():
                lineas = self._lineas_estado_consola()
                self.after(0, lambda: consola.imprimir(lineas, "info"))
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/ram":
            consola.imprimir(t("consola_liberando_ram"), "dim")

            def worker():
                liberado, afectados, _ = opt.trim_process_memory()
                msg = t("consola_ram_ok", procesos=afectados, tamano=opt.format_bytes(liberado))
                self.after(0, lambda: decir(True, msg))
                self._log_dev(t("consola_log_ram", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_ram=liberado, archivos_afectados=afectados)
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/temporales":
            consola.imprimir(t("consola_limpiando_temp"), "dim")

            def worker():
                liberado, borrados, _ = opt.clear_temp_files()
                msg = t("consola_temp_ok", archivos=borrados, tamano=opt.format_bytes(liberado))
                self.after(0, lambda: decir(True, msg))
                self._log_dev(t("consola_log_temp", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_liberados=liberado, archivos_afectados=borrados)
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/papelera":
            consola.imprimir(t("consola_vaciando_papelera"), "dim")

            def worker():
                exito, _, liberado, elementos = opt.empty_recycle_bin()
                msg = (t("consola_papelera_ok", tamano=opt.format_bytes(liberado), elementos=elementos)
                       if exito else t("consola_papelera_error"))
                self.after(0, lambda: decir(exito, msg))
                self._log_dev(t("consola_log_papelera", origen=seccion_origen), "N/A", msg,
                              seccion=seccion_origen, exito=exito,
                              bytes_liberados=liberado, archivos_afectados=elementos)
            threading.Thread(target=worker, daemon=True).start()
            return

        if comando == "/dns":
            exito, _ = opt.flush_dns()
            msg = t("consola_dns_ok") if exito else t("consola_dns_error")
            decir(exito, msg)
            self._log_dev(t("consola_log_dns", origen=seccion_origen), "N/A", msg,
                          seccion=seccion_origen, exito=exito)
            return

        if comando == "/rapido":
            consola.imprimir(t("consola_rapido"), "dim")

            def worker():
                liberado_ram, procesos, _ = opt.trim_process_memory()
                liberado_disco, archivos, _ = opt.clear_temp_files()
                msg = t("consola_rapido_ok", procesos=procesos,
                        ram=opt.format_bytes(liberado_ram), archivos=archivos,
                        disco=opt.format_bytes(liberado_disco))
                self.after(0, lambda: decir(True, msg))
                self._log_dev(t("consola_log_rapido", origen=seccion_origen), "N/A", msg, seccion=seccion_origen,
                              exito=True, bytes_liberados=liberado_disco, bytes_ram=liberado_ram,
                              archivos_afectados=procesos + archivos)
            threading.Thread(target=worker, daemon=True).start()
            return

        # ---- Comandos de la 1.6.0 ----
        # Los que tardan (PowerShell, mediciones) van en un hilo y contestan
        # por after(0): la consola no se puede congelar esperando a WMI.
        def en_hilo(trabajo):
            def worker():
                try:
                    exito, texto = trabajo()
                except Exception as e:
                    exito, texto = False, t("consola_error_interno", error=e)
                self.after(0, lambda: decir(exito, texto))
            threading.Thread(target=worker, daemon=True).start()

        if comando == "/ramprofunda":
            consola.imprimir(t("opt_liberando_ram_profunda"), "dim")

            def trabajo():
                r = opt.liberar_memoria(nivel="profunda")
                msg = t("opt_ram_ok", antes=f"{r['uso_antes']:.0f}", despues=f"{r['uso_despues']:.0f}",
                        tamano=opt.format_bytes(r["liberado"]))
                if r["espera_antes"] is not None and r["espera_despues"] is not None:
                    msg += " " + t("opt_ram_espera", antes=opt.format_bytes(r["espera_antes"]),
                                    despues=opt.format_bytes(r["espera_despues"]))
                self._log_dev(t("opt_log_ram_profunda"), r["comando"], msg, seccion=seccion_origen,
                              exito=True, bytes_ram=r["liberado"])
                return True, msg
            en_hilo(trabajo)
            return

        if comando == "/fondo":
            consola.imprimir(t("fondo_limpiando"), "dim")

            def trabajo():
                claves = [c["clave"] for c in opt.listar_limpieza_sistema() if c["bytes"] > 0]
                liberado, borrados, cmd = opt.limpiar_sistema(claves)
                msg = t("fondo_listo", tamano=opt.format_bytes(liberado), archivos=borrados)
                self._log_dev(t("fondo_log"), cmd, msg, seccion=seccion_origen, exito=True,
                              bytes_liberados=liberado, archivos_afectados=borrados)
                return True, msg
            en_hilo(trabajo)
            return

        if comando == "/fugas":
            fugas = dict(self.vigilante.fugas)
            if not self.prefs.get("avisar_fugas", True):
                consola.imprimir(t("consola_fugas_apagado"), "aviso")
            elif not fugas:
                decir(True, t("consola_fugas_ninguna"))
            else:
                consola.imprimir("\n".join(
                    t("consola_fugas_linea", nombre=f["nombre"], pid=pid, crecimiento=opt.format_bytes(f["crecimiento"]),
                      minutos=f["minutos"], actual=opt.format_bytes(f["actual"]))
                    for pid, f in fugas.items()), "aviso")
            return

        if comando == "/procesos":
            def trabajo():
                procesos = opt.listar_procesos_por_ram(limite=10)
                if not procesos:
                    return False, t("opt_sin_procesos")
                ancho = max(len(p["nombre"]) for p in procesos)
                return True, "\n".join(f'{p["nombre"]:<{ancho}}  {opt.format_bytes(p["bytes_ram"]):>10}'
                                       + ("  📈" if p.get("pid") in self.vigilante.fugas else "")
                                       for p in procesos)
            en_hilo(trabajo)
            return

        if comando == "/discos":
            consola.imprimir(t("salud_revisando"), "dim")

            def trabajo():
                discos = tec.salud_discos()
                if discos is None:
                    return False, t("salud_discos_error")
                lineas = []
                for d in discos:
                    lineas.append(t("consola_disco_linea", nombre=d.get("nombre") or "?",
                                    nivel=t(tec.NIVELES_SALUD[d["veredicto"]]),
                                    desgaste=d["desgaste"] if d.get("desgaste") is not None else "?",
                                    temperatura=d["temperatura"] if d.get("temperatura") is not None else "?"))
                    lineas += ["   " + t(m) for m in d.get("motivos") or []]
                return all(d["veredicto"] == "bien" for d in discos), "\n".join(lineas) or t("salud_discos_error")
            en_hilo(trabajo)
            return

        if comando == "/bateria":
            def trabajo():
                baterias = tec.salud_bateria()
                if baterias is None:
                    return False, t("bat_error")
                if not baterias:
                    return True, t("bat_ninguna")
                return (all(b["veredicto"] == "bien" for b in baterias),
                        "\n".join(t("bat_resumen", porcentaje=b["porcentaje"],
                                    ciclos=b["ciclos"] if b["ciclos"] is not None else "?") for b in baterias))
            en_hilo(trabajo)
            return

        if comando == "/pantallazos":
            consola.imprimir(t("salud_revisando"), "dim")

            def trabajo():
                fallos = tec.historial_fallos()
                if fallos is None:
                    return False, t("bsod_error")
                lineas = [t("bsod_resumen", pantallazos=len(fallos["pantallazos"])),
                          t("bsod_apagados", apagados=fallos["apagados"], dias=fallos["dias"])]
                for p in fallos["pantallazos"][:10]:
                    codigo = f'0x{p["codigo"]:X}' if p["codigo"] is not None else "?"
                    lineas.append(f'  {p["fecha"]}  {codigo}  {p["nombre"] or ""}  — {t(p["causa"])}')
                return not fallos["pantallazos"], "\n".join(lineas)
            en_hilo(trabajo)
            return

        if comando == "/unidades":
            def trabajo():
                unidades = opt.listar_unidades_optimizables()
                if not unidades:
                    return False, t("unid_ninguna")
                tipos = {"SSD": t("unid_tipo_ssd"), "HDD": t("unid_tipo_hdd")}
                return True, "\n".join(
                    f'{u["letra"]}:  {tipos.get(u["tipo"], t("unid_tipo_otro"))}  ·  '
                    + t("unid_espacio", libre=opt.format_bytes(u["libre"]), total=opt.format_bytes(u["tamano"]))
                    for u in unidades)
            en_hilo(trabajo)
            return

        if comando == "/medirdns":
            consola.imprimir(t("dns_midiendo", actual=1, total="…", nombre=""), "dim")

            def trabajo():
                resultados = opt.comparar_dns()
                lineas = [f'{r["nombre"]:<16} ' + (t("dns_ms", ms=f'{r["ms"]:.0f}') if r["ms"] is not None
                                                  else t("dns_no_contesta")) for r in resultados]
                return any(r["ms"] is not None for r in resultados), "\n".join(lineas)
            en_hilo(trabajo)
            return

        if comando == "/plan":
            def trabajo():
                nombre = opt.get_active_power_plan_name()
                return bool(nombre), t("opt_plan_activo", plan=nombre or t("opt_plan_no_leido"))
            en_hilo(trabajo)
            return

        if comando == "/red":
            def trabajo():
                adaptadores = opt.leer_dns_actual()
                if not adaptadores:
                    return False, t("consola_red_sin_conexion")
                direcciones = psutil.net_if_addrs()
                lineas = []
                for a in adaptadores:
                    ips = [d.address for d in direcciones.get(a["nombre"], []) if d.family == socket.AF_INET]
                    lineas.append(t("consola_red_linea", nombre=a["nombre"], ip=", ".join(ips) or "?",
                                    dns=", ".join(a["dns"]) or "?"))
                return True, "\n".join(lineas)
            en_hilo(trabajo)
            return

        if comando == "/autoram":
            activa = not self.prefs.get("auto_ram_activa", True)
            self.prefs["auto_ram_activa"] = activa
            prefs.guardar({"auto_ram_activa": activa})
            if activa:
                self.auto_ram.iniciar()
            else:
                self.auto_ram.detener()
            if hasattr(self, "switch_auto_ram") and self.switch_auto_ram.winfo_exists():
                (self.switch_auto_ram.select if activa else self.switch_auto_ram.deselect)()
            consola.imprimir(t("ajustes_auto_ram_on") if activa else t("ajustes_auto_ram_off"),
                             "ok" if activa else "aviso")
            return

        if comando == "/tecnico":
            if EDICION != "admin":
                consola.imprimir(t("consola_solo_admin"), "aviso")
                return
            consola.imprimir(t("consola_abriendo"), "dim")
            self.after(300, self.mostrar_tecnico)
            return

        # ---- Comandos de la 1.7.0 ----
        if comando == "/wifi":
            consola.imprimir(t("wifi_analizando"), "dim")

            def trabajo():
                texto, nivel = texto_wifi(sysmon.leer_wifi(escanear=True))
                return nivel in ("bien", "info"), texto
            en_hilo(trabajo)
            return

        if comando == "/disco":
            consola.imprimir(t("comp_disco_fase_escribiendo"), "dim")

            def trabajo():
                r = opt.prueba_velocidad_disco(tamano_mb=256)
                if not r or "error" in r:
                    return False, t("comp_disco_error", error=(r or {}).get("error") or t("comp_error_desconocido"))
                self._log_dev(t("comp_log_disco"), t("comp_log_disco_cmd"), texto_disco(r),
                              seccion=seccion_origen, exito=True)
                return r["clase"] != "hdd", texto_disco(r)
            en_hilo(trabajo)
            return

        if comando == "/extensiones":
            consola.imprimir(t("ext_revisando"), "dim")

            def trabajo():
                extensiones = seg.auditar_extensiones(idiomas.IDIOMA_ACTUAL)
                if not extensiones:
                    return True, t("ext_ninguna")
                niveles = {"alto": "aud_nivel_alto", "medio": "aud_nivel_medio", "info": "aud_nivel_info"}
                lineas = [t("ext_resumen", total=len(extensiones),
                            altos=sum(1 for e in extensiones if e["nivel"] == "alto"),
                            medios=sum(1 for e in extensiones if e["nivel"] == "medio"))]
                for e in extensiones[:40]:
                    lineas.append(f'[{t(niveles[e["nivel"]])}] {e["navegador"]}: {e["nombre"]}'
                                  + ("" if e["activa"] else f'  ({t("ext_desactivada")})'))
                return not any(e["nivel"] == "alto" for e in extensiones), "\n".join(lineas)
            en_hilo(trabajo)
            return

        if comando == "/accesos":
            def trabajo():
                rotos = opt.buscar_accesos_rotos()
                if not rotos:
                    return True, t("accesos_ninguno")
                lineas = [t("accesos_resumen", total=len(rotos))]
                lineas += [f'{r["nombre"]}  →  {r["destino"]}' for r in rotos[:40]]
                lineas.append(t("consola_accesos_donde"))
                return False, "\n".join(lineas)
            en_hilo(trabajo)
            return

        if comando == "/encendido":
            dias = self.vigilante.dias_encendido()
            if dias is None:
                decir(False, t("consola_encendido_error"))
                return
            limite = self.prefs.get("dias_reinicio", 7)
            texto = t("consola_encendido", dias=f"{dias:.1f}")
            if dias >= limite:
                texto += "\n" + t("vig_reinicio_msg", dias=int(dias))
            decir(dias < limite, texto)
            return

        if comando == "/buscar":
            consola.imprimir(t("consola_abriendo"), "dim")
            self.after(300, self._abrir_paleta)
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
            consola.imprimir(t("consola_abriendo"), "dim")
            self.after(300, navegacion[comando])
            return

        if comando == "/widget":
            self._toggle_widget()
            activo = self.performance_widget is not None
            decir(activo, t("consola_widget_ok") if activo else t("consola_widget_error"))
            return

        if comando == "/auto":
            self._toggle_autopilot()
            consola.imprimir(t("consola_modo_juego",
                                estado=t("consola_activado") if self.autopilot.activo
                                else t("consola_desactivado")),
                             "ok" if self.autopilot.activo else "aviso")
            return

        if comando == "/fps":
            exito, _ = opt.abrir_contador_fps_windows()
            decir(exito, t("consola_fps_ok") if exito else t("consola_fps_error"))
            return

        # Se recorta lo que se devuelve: si alguien pega media pagina en la
        # consola, no tiene sentido volcarsela entera de vuelta.
        eco = texto if len(texto) <= 60 else texto[:60] + "..."
        consola.imprimir(t("consola_no_reconocido", comando=eco), "error")
        # Una letra de más no debería obligar a leerse /help otra vez.
        cercanos = difflib.get_close_matches(comando, COMANDOS_DISPONIBLES, n=3, cutoff=0.6)
        if cercanos:
            consola.imprimir(t("consola_sugerencia", sugerencia="   ".join(cercanos)), "aviso")

    def _texto_version_consola(self):
        """Lo que hace falta saber para reportar un fallo: versión, edición,
        permisos, si va compilada o desde el código, y dónde guarda los
        datos. Antes había que preguntárselo al usuario dato por dato."""
        congelada = getattr(sys, "frozen", False)
        return "\n".join([
            t("consola_ver_app", version=APP_VERSION),
            t("consola_ver_edicion", edicion=(t("consola_estado_edicion_admin") if EDICION == "admin"
                                              else t("consola_estado_edicion_cliente"))),
            t("consola_ver_permisos", permisos=(t("consola_estado_admin") if opt.is_admin()
                                                else t("consola_estado_usuario"))),
            t("consola_ver_python", version=platform.python_version(),
              modo=t("consola_ver_compilada") if congelada else t("consola_ver_codigo")),
            t("consola_ver_windows", version=platform.version()),
            t("consola_ver_datos", ruta=prefs.carpeta_datos()),
        ])

    def _lineas_estado_consola(self):
        """Se llama desde un hilo de fondo a propósito: la temperatura y la
        GPU se consultan por WMI / nvidia-smi y pueden tardar un par de
        segundos. Hecho en el hilo de la interfaz, la ventana se congelaría
        justo después de escribir el comando."""
        try:
            cpu = psutil.cpu_percent(interval=0.4)
            memoria = psutil.virtual_memory()
            disco = sysmon.get_disk_info()
            temperatura = sysmon.get_cpu_temperature()
            gpu = sysmon.get_gpu_info()
            uptime = sysmon.get_uptime_seconds()
            bateria = psutil.sensors_battery()
        except Exception as e:
            return t("consola_estado_error", error=e)

        lineas = [
            t("consola_estado_cpu", pct=f"{cpu:.0f}", nucleos=psutil.cpu_count(logical=True)),
            t("consola_estado_ram", pct=f"{memoria.percent:.0f}",
              usada=opt.format_bytes(memoria.used), total=opt.format_bytes(memoria.total)),
            t("consola_estado_disco", pct=f'{disco["porcentaje"]:.0f}', libres=disco["libre_gb"]),
            t("consola_estado_gpu", nombre=gpu.get("nombre") or "N/D",
              pct=(f'{gpu["porcentaje"]:.0f}' if gpu.get("porcentaje") is not None else "--")),
            (t("consola_estado_temp", temp=f"{temperatura:.0f}") if temperatura is not None
             else t("consola_estado_temp_nd")),
            t("consola_estado_uptime", horas=int(uptime // 3600), minutos=int((uptime % 3600) // 60)),
        ]
        if bateria is not None:
            lineas.append(t("consola_estado_bateria", pct=f"{bateria.percent:.0f}"))
        return "\n".join(lineas)

    # ---------------- Herramientas de técnico (solo Edición Administrador) ----------------
    def mostrar_tecnico(self):
        """Pantalla exclusiva del admin: foto antes/después, inspector de
        arranque y grabación de métricas a CSV.

        No son "las mismas funciones con otro color": son cosas que solo
        tienen sentido si arreglás computadoras ajenas. El código es
        público, así que cualquiera puede compilar esta edición — esconder
        funciones no es posible y fingir que sí sería engañarse. Lo que sí
        se puede es que esta edición sea de verdad otra cosa.
        """
        if EDICION != "admin":
            self.mostrar_dashboard()
            return
        self._limpiar_contenido()

        ctk.CTkLabel(self.contenido, text=t("tec_titulo"),
                     font=fuente(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self.contenido, text=t("tec_subtitulo"), font=fuente(size=12),
                     text_color=T.texto2, wraplength=900, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.pestana_tecnico = ctk.CTkSegmentedButton(
            self.contenido,
            values=[t("tec_tab_foto"), t("tec_tab_mantenimiento"), t("tec_tab_salud"),
                    t("tec_tab_drivers"), t("tec_tab_arranque"), t("tec_tab_grabar")],
            command=self._cambiar_pestana_tecnico)
        self.pestana_tecnico.set(t("tec_tab_foto"))
        self.pestana_tecnico.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.contenido.grid_rowconfigure(3, weight=1)
        self.contenedor_tecnico = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.contenedor_tecnico.grid(row=3, column=0, columnspan=3, sticky="nswe")
        self.contenedor_tecnico.grid_columnconfigure(0, weight=1)
        self.contenedor_tecnico.grid_rowconfigure(0, weight=1)

        self._mostrar_foto_sistema()

    def _cambiar_pestana_tecnico(self, valor):
        if valor == t("tec_tab_mantenimiento"):
            self._mostrar_mantenimiento()
        elif valor == t("tec_tab_salud"):
            self._mostrar_salud()
        elif valor == t("tec_tab_drivers"):
            self._mostrar_drivers_respaldo()
        elif valor == t("tec_tab_arranque"):
            self._mostrar_inspector_arranque()
        elif valor == t("tec_tab_grabar"):
            self._mostrar_grabador_metricas()
        else:
            self._mostrar_foto_sistema()

    def _limpiar_contenedor_tecnico(self):
        for w in self.contenedor_tecnico.winfo_children():
            w.destroy()

    # ---- Pestaña 1: foto del sistema (antes / después) ----
    def _mostrar_foto_sistema(self):
        self._limpiar_contenedor_tecnico()
        fila = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(fila, text=t("tec_btn_tomar_foto"),
                      command=self._accion_tomar_foto).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila, text=t("tec_btn_comparar"), fg_color=T.boton2,
                      hover_color=T.boton2_hover,
                      command=self._accion_comparar_foto, text_color=T.texto).pack(side="left")

        ctk.CTkLabel(self.contenedor_tecnico, text=t("tec_foto_como_se_usa"),
                     font=fuente(size=11), text_color=T.texto2,
                     wraplength=880, justify="left").pack(anchor="w", pady=(0, 8))

        self.lista_tecnico = ctk.CTkScrollableFrame(self.contenedor_tecnico,
                                                     fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        self.lista_tecnico.pack(fill="both", expand=True)

        guardada = tec.cargar_foto(prefs.carpeta_datos())
        texto = (t("tec_foto_existente", momento=guardada.get("momento"))
                 if guardada else t("tec_foto_ninguna"))
        ctk.CTkLabel(self.lista_tecnico, text=texto, text_color=T.texto2,
                     wraplength=820, justify="left").pack(padx=16, pady=16)

    def _accion_tomar_foto(self):
        def worker():
            foto = tec.tomar_foto(sysmon, opt)
            ruta = tec.guardar_foto(prefs.carpeta_datos(), foto)
            msg = (t("tec_foto_guardada", momento=foto["momento"]) if ruta
                   else t("tec_foto_error"))
            self._log_dev(t("tec_log_foto"), "N/A", msg,
                          seccion=t("seccion_tecnico"), exito=bool(ruta))
            self.after(0, lambda: self._pintar_aviso_tecnico(msg))
        self._pintar_aviso_tecnico(t("tec_tomando_foto"))
        threading.Thread(target=worker, daemon=True).start()

    def _accion_comparar_foto(self):
        antes = tec.cargar_foto(prefs.carpeta_datos())
        if not antes:
            self._pintar_aviso_tecnico(t("tec_foto_ninguna"))
            return

        def worker():
            despues = tec.tomar_foto(sysmon, opt)
            filas = tec.comparar_fotos(antes, despues)
            self._log_dev(t("tec_log_comparar"), "N/A",
                          t("tec_comparacion_hecha", campos=len(filas)),
                          seccion=t("seccion_tecnico"), exito=True)
            self.after(0, lambda: self._pintar_comparacion(antes, despues, filas))
        self._pintar_aviso_tecnico(t("tec_comparando"))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_aviso_tecnico(self, texto):
        if not (hasattr(self, "lista_tecnico") and self.lista_tecnico.winfo_exists()):
            return
        for w in self.lista_tecnico.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_tecnico, text=texto, text_color=T.texto2,
                     wraplength=820, justify="left").pack(padx=16, pady=16)

    def _pintar_comparacion(self, antes, despues, filas):
        if not (hasattr(self, "lista_tecnico") and self.lista_tecnico.winfo_exists()):
            return
        for w in self.lista_tecnico.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.lista_tecnico,
                     text=t("tec_comparacion_titulo", antes=antes.get("momento"),
                            despues=despues.get("momento")),
                     font=fuente(size=13, weight="bold"), anchor="w",
                     wraplength=820, justify="left").pack(fill="x", padx=16, pady=(14, 8))

        if not filas:
            ctk.CTkLabel(self.lista_tecnico, text=t("tec_comparacion_vacia"),
                         text_color=T.texto2).pack(padx=16, pady=16)
            return

        for f in filas:
            fila = ctk.CTkFrame(self.lista_tecnico, fg_color=T.fila, corner_radius=T.radio_fila)
            fila.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(fila, text=t(f["clave"]), font=fuente(size=12), anchor="w",
                         width=210).pack(side="left", padx=12, pady=9)
            # BUG corregido: "recuperable" salía en bytes crudos ("523452345 B").
            ctk.CTkLabel(fila, text=f'{tec._formatear_valor(f["antes"], f["unidad"])}  →  '
                                    f'{tec._formatear_valor(f["despues"], f["unidad"])}',
                         font=fuente(size=12), text_color=T.texto2, anchor="w",
                         width=220).pack(side="left", pady=9)
            color = {"mejor": COLOR_OK, "peor": COLOR_CRIT}.get(f["sentido"], T.texto2)
            signo = "+" if f["diferencia"] > 0 else ""
            ctk.CTkLabel(fila, text=f'{signo}{tec._formatear_valor(f["diferencia"], f["unidad"])}',
                         font=fuente(size=12, weight="bold"),
                         text_color=color).pack(side="right", padx=12, pady=9)
        self._pintar_caja_informe(antes, despues, filas)

    # ---- Informe para el cliente ----
    def _pintar_caja_informe(self, antes, despues, filas):
        """Debajo de la comparación: quién hizo el trabajo, para quién, y el
        botón que genera el informe."""
        caja = ctk.CTkFrame(self.lista_tecnico, fg_color=T.fila, corner_radius=T.radio_fila)
        caja.pack(fill="x", padx=8, pady=(14, 6))
        ctk.CTkLabel(caja, text=t("inf_caja_titulo"), font=fuente(size=13, weight="bold"),
                     anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(caja, text=t("inf_caja_desc"), font=fuente(size=11), text_color=T.texto2,
                     anchor="w", wraplength=820, justify="left").pack(fill="x", padx=12, pady=(0, 6))
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(0, 10))
        entrada_tecnico = ctk.CTkEntry(fila, width=200, placeholder_text=t("inf_ph_tecnico"))
        entrada_tecnico.pack(side="left", padx=(0, 8))
        if self.prefs.get("tecnico_nombre"):
            entrada_tecnico.insert(0, self.prefs["tecnico_nombre"])
        entrada_cliente = ctk.CTkEntry(fila, width=200, placeholder_text=t("inf_ph_cliente"))
        entrada_cliente.pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila, text=t("inf_btn_generar"),
                      command=lambda: self._generar_informe(antes, despues, filas,
                                                            entrada_tecnico.get().strip(),
                                                            entrada_cliente.get().strip())).pack(side="left")
        self.lbl_informe = ctk.CTkLabel(caja, text="", font=fuente(size=12), anchor="w",
                                        wraplength=820, justify="left")
        self.lbl_informe.pack(fill="x", padx=12, pady=(0, 10))

    def _generar_informe(self, antes, despues, filas, tecnico, cliente):
        if tecnico != self.prefs.get("tecnico_nombre"):
            self.prefs["tecnico_nombre"] = tecnico
            prefs.guardar({"tecnico_nombre": tecnico})
        self._actualizar_label("lbl_informe", t("inf_generando"))

        def worker():
            # Lo hecho desde la primera foto. El historial guarda la hora con
            # el mismo formato que la foto, así que se comparan como texto.
            desde = (antes or {}).get("momento", "")
            acciones = [a for a in reversed(self.reporte.historial_completo(limite=400))
                        if a.get("timestamp", "") >= desde
                        and a.get("seccion") not in (t("seccion_ajustes"), t("seccion_tecnico"))]
            salud = getattr(self, "_salud_cache", None) or {}
            equipo = dict(self._system_info_cache)
            equipo["ram"] = opt.format_bytes(psutil.virtual_memory().total)
            html = tec.generar_informe_html({
                "version": APP_VERSION, "logo": informe.logo_data_uri(rutas.recurso("icono.ico")),
                "equipo": equipo, "tecnico": tecnico, "cliente": cliente,
                "antes": antes, "despues": despues, "filas": filas, "acciones": acciones,
                "discos": salud.get("discos") or tec.salud_discos() or [],
                "baterias": salud.get("baterias") if "baterias" in salud else (tec.salud_bateria() or []),
                "fallos": salud.get("fallos") or tec.historial_fallos(),
            }, t)
            carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
            nombre = f"Informe_TechClean_{equipo.get('hostname', 'PC')}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            ruta = os.path.join(carpeta, "".join(c for c in nombre if c not in '\\/:*?"<>|'))
            try:
                # 1.8.0: en PDF, con la cara de TechClean (informe.py); si no
                # hay Edge, la página HTML, como antes.
                if informe.a_pdf(html, ruta + ".pdf"):
                    ruta += ".pdf"
                else:
                    ruta += ".html"
                    with open(ruta, "w", encoding="utf-8") as f:
                        f.write(html)
                os.startfile(ruta)
                msg, exito = t("inf_listo", ruta=ruta), True
            except Exception as e:
                msg, exito = t("inf_error", error=e), False
            self._log_dev(t("inf_log"), "N/A", msg, seccion=t("seccion_tecnico"), exito=exito)
            self.after(0, lambda: self._actualizar_label("lbl_informe", msg))
        threading.Thread(target=worker, daemon=True).start()

    # ---- Pestaña: mantenimiento completo ----
    PASOS_MANTENIMIENTO = [
        ("punto", "mant_paso_punto"), ("ram", "mant_paso_ram"), ("temporales", "mant_paso_temporales"),
        ("fondo", "mant_paso_fondo"), ("dns", "mant_paso_dns"), ("sfc", "mant_paso_sfc"),
        ("dism", "mant_paso_dism"), ("unidades", "mant_paso_unidades"),
    ]

    def _mostrar_mantenimiento(self):
        self._limpiar_contenedor_tecnico()
        ctk.CTkLabel(self.contenedor_tecnico, text=t("mant_desc"), font=fuente(size=11),
                     text_color=T.texto2, wraplength=880, justify="left", anchor="w").pack(fill="x", pady=(0, 8))
        opciones = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        opciones.pack(fill="x", pady=(0, 6))
        if not hasattr(self, "_mant_var_reparar"):
            self._mant_var_reparar = ctk.BooleanVar(value=False)
            self._mant_var_hdd = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opciones, text=t("mant_op_reparar"), variable=self._mant_var_reparar).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(opciones, text=t("mant_op_hdd"), variable=self._mant_var_hdd).pack(anchor="w", pady=2)
        self.btn_mantenimiento = ctk.CTkButton(self.contenedor_tecnico, width=240, command=self._accion_mantenimiento)
        self.btn_mantenimiento.pack(anchor="w", pady=(6, 8))
        self._mant_colores = (self.btn_mantenimiento.cget("fg_color"), self.btn_mantenimiento.cget("text_color"))
        self.lista_tecnico = ctk.CTkScrollableFrame(self.contenedor_tecnico, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        self.lista_tecnico.pack(fill="both", expand=True)
        self._pintar_mantenimiento()

    def _pintar_mantenimiento(self):
        if not (hasattr(self, "lista_tecnico") and self.lista_tecnico.winfo_exists()
                and hasattr(self, "btn_mantenimiento") and self.btn_mantenimiento.winfo_exists()):
            return
        en_curso = getattr(self, "_mant_en_curso", False)
        if en_curso:
            self.btn_mantenimiento.configure(text=t("fondo_dism_cancelar"), fg_color=COLOR_WARN, text_color=T.sobre_aviso)
        else:
            self.btn_mantenimiento.configure(text=t("mant_btn_iniciar"), fg_color=self._mant_colores[0],
                                             text_color=self._mant_colores[1])
        for w in self.lista_tecnico.winfo_children():
            w.destroy()
        estados = getattr(self, "_mant_estados", {})
        iconos = {"espera": "·", "curso": "⏳", "ok": "✓", "error": "✗", "omitido": "—"}
        colores = {"ok": COLOR_OK, "error": COLOR_CRIT, "curso": COLOR_WARN}
        for clave, texto in self.PASOS_MANTENIMIENTO:
            estado, detalle = estados.get(clave, ("espera", ""))
            fila = ctk.CTkFrame(self.lista_tecnico, fg_color=T.fila, corner_radius=T.radio_boton)
            fila.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(fila, text=iconos[estado], width=24, font=fuente(size=14, weight="bold"),
                         text_color=colores.get(estado, T.texto2)).pack(side="left", padx=(10, 4), pady=6)
            ctk.CTkLabel(fila, text=t(texto), font=fuente(size=12), anchor="w").pack(side="left", pady=6)
            if detalle:
                ctk.CTkLabel(fila, text=detalle, font=fuente(size=11), text_color=T.texto2,
                             anchor="e", wraplength=420, justify="right").pack(side="right", padx=10, pady=6)
        resumen = getattr(self, "_mant_resumen", None)
        if resumen and not en_curso:
            ctk.CTkLabel(self.lista_tecnico, text=resumen, font=fuente(size=13, weight="bold"),
                         anchor="w", wraplength=820, justify="left").pack(fill="x", padx=16, pady=(12, 4))
            fotos = getattr(self, "_mant_fotos", None)
            if fotos and fotos[0] and fotos[1]:
                self._pintar_caja_informe(fotos[0], fotos[1], tec.comparar_fotos(fotos[0], fotos[1]))

    def _accion_mantenimiento(self):
        if getattr(self, "_mant_en_curso", False):
            self._evento_mant.set()
            return
        incluir_reparar = bool(self._mant_var_reparar.get())
        incluir_hdd = bool(self._mant_var_hdd.get())
        self._mant_en_curso = True
        self._evento_mant = threading.Event()
        self._mant_estados = {}
        self._mant_resumen = None
        self._mant_fotos = None
        self._pintar_mantenimiento()

        def marcar(clave, estado, detalle=""):
            self._mant_estados[clave] = (estado, detalle)
            self.after(0, self._pintar_mantenimiento)

        def progreso_de(clave):
            return lambda seg: marcar(clave, "curso", t("mant_minutos", minutos=int(seg // 60)))

        def worker():
            evento = self._evento_mant
            foto_antes = tec.tomar_foto(sysmon, opt)
            pasos = []

            def punto():
                exito, cmd = opt.crear_punto_restauracion(t("mant_punto_nombre"))
                return exito, "" if exito else t("mant_punto_fallo"), cmd

            def ram():
                r = opt.liberar_memoria(nivel="normal")
                return True, opt.format_bytes(r["liberado"]), r["comando"]

            def temporales():
                liberado, archivos, cmd = opt.clear_temp_files()
                return True, t("mant_det_archivos", archivos=archivos, tamano=opt.format_bytes(liberado)), cmd

            def fondo():
                claves = [c["clave"] for c in opt.listar_limpieza_sistema()]
                liberado, archivos, cmd = opt.limpiar_sistema(claves)
                return True, t("mant_det_archivos", archivos=archivos, tamano=opt.format_bytes(liberado)), cmd

            def dns():
                exito, cmd = opt.flush_dns()
                return exito, "", cmd

            def sfc():
                exito, resumen, cmd = opt.reparar_archivos_sistema(progreso_de("sfc"), evento)
                return exito, "", cmd

            def dism():
                exito, resumen, cmd = opt.reparar_imagen_windows(progreso_de("dism"), evento)
                return exito, "", cmd

            def unidades():
                hechas, fallidas = [], []
                for u in opt.listar_unidades_optimizables():
                    if evento.is_set():
                        break
                    if u["tipo"] == "HDD" and not incluir_hdd:
                        continue
                    if u["tipo"] not in ("SSD", "HDD"):
                        continue
                    exito, _, _ = opt.optimizar_unidad(u["letra"], progreso_de("unidades"), evento)
                    (hechas if exito else fallidas).append(u["letra"] + ":")
                detalle = " ".join(hechas) + ((" ✗ " + " ".join(fallidas)) if fallidas else "")
                return not fallidas, detalle or t("mant_det_nada"), "Optimize-Volume"

            funciones = {"punto": punto, "ram": ram, "temporales": temporales, "fondo": fondo, "dns": dns,
                         "sfc": sfc, "dism": dism, "unidades": unidades}
            for clave, texto in self.PASOS_MANTENIMIENTO:
                if evento.is_set():
                    marcar(clave, "omitido", t("mant_det_cancelado"))
                    continue
                if clave in ("sfc", "dism") and not incluir_reparar:
                    marcar(clave, "omitido", t("mant_det_no_elegido"))
                    continue
                marcar(clave, "curso")
                try:
                    exito, detalle, comando = funciones[clave]()
                except Exception as e:
                    exito, detalle, comando = False, str(e)[:120], "N/A"
                if evento.is_set() and clave in ("sfc", "dism", "unidades"):
                    exito, detalle = False, t("mant_det_cancelado")
                marcar(clave, "ok" if exito else "error", detalle)
                pasos.append(exito)
                self._log_dev(t("mant_log_paso", paso=t(texto)), comando, detalle or ("OK" if exito else "✗"),
                              seccion=t("seccion_mantenimiento"), exito=exito)

            foto_despues = tec.tomar_foto(sysmon, opt)

            def terminar():
                self._mant_en_curso = False
                self._mant_fotos = (foto_antes, foto_despues)
                self._mant_resumen = (t("mant_cancelado") if evento.is_set()
                                      else t("mant_listo", ok=sum(pasos), total=len(pasos)))
                self._pintar_mantenimiento()
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Pestaña: salud del equipo ----
    def _mostrar_salud(self):
        self._limpiar_contenedor_tecnico()
        fila = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(fila, text=t("salud_btn_revisar"), command=self._accion_revisar_salud).pack(side="left")
        ctk.CTkButton(fila, text=t("bat_btn_informe_windows"), fg_color=T.boton2, hover_color=T.boton2_hover,
                      command=self._accion_informe_bateria, text_color=T.texto).pack(side="left", padx=8)
        ctk.CTkLabel(self.contenedor_tecnico, text=t("salud_desc"), font=fuente(size=11), text_color=T.texto2,
                     wraplength=880, justify="left", anchor="w").pack(fill="x", pady=(0, 8))
        self.lista_tecnico = ctk.CTkScrollableFrame(self.contenedor_tecnico, fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        self.lista_tecnico.pack(fill="both", expand=True)
        if getattr(self, "_salud_cache", None):
            self._pintar_salud(self._salud_cache)
        else:
            self._accion_revisar_salud()

    def _accion_revisar_salud(self):
        self._pintar_aviso_tecnico(t("salud_revisando"))

        def worker():
            datos = {"discos": tec.salud_discos(), "baterias": tec.salud_bateria(),
                     "fallos": tec.historial_fallos()}
            self._salud_cache = datos
            self.after(0, lambda: self._pintar_salud(datos))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_salud(self, datos):
        if not (hasattr(self, "lista_tecnico") and self.lista_tecnico.winfo_exists()):
            return
        for w in self.lista_tecnico.winfo_children():
            w.destroy()
        colores = {"bien": COLOR_OK, "atencion": COLOR_WARN, "critico": COLOR_CRIT}

        def titulo(texto):
            ctk.CTkLabel(self.lista_tecnico, text=texto, font=fuente(size=14, weight="bold"),
                         anchor="w").pack(fill="x", padx=12, pady=(12, 4))

        def tarjeta(nombre, nivel, lineas):
            caja = ctk.CTkFrame(self.lista_tecnico, fg_color=T.fila, corner_radius=T.radio_fila)
            caja.pack(fill="x", padx=8, pady=3)
            arriba = ctk.CTkFrame(caja, fg_color="transparent")
            arriba.pack(fill="x", padx=12, pady=(8, 2))
            ctk.CTkLabel(arriba, text=nombre, font=fuente(size=13, weight="bold"), anchor="w").pack(side="left")
            if nivel:
                ctk.CTkLabel(arriba, text=t(tec.NIVELES_SALUD[nivel]), font=fuente(size=12, weight="bold"),
                             text_color=colores[nivel]).pack(side="right")
            for linea in lineas:
                ctk.CTkLabel(caja, text=linea, font=fuente(size=11), text_color=T.texto2, anchor="w",
                             wraplength=820, justify="left").pack(fill="x", padx=12, pady=(0, 2))
            ctk.CTkFrame(caja, height=4, fg_color="transparent").pack()

        def o_no(valor, formato):
            return formato.format(valor) if isinstance(valor, (int, float)) else t("salud_no_disponible")

        titulo(t("salud_discos"))
        discos = datos.get("discos")
        if discos is None:
            tarjeta(t("salud_discos_error"), None, [])
        for d in discos or []:
            contados = [v for v in (d.get("errores_lectura"), d.get("errores_escritura"))
                        if isinstance(v, (int, float))]
            lineas = [t("salud_disco_linea1", tipo=d.get("tipo") or "?", bus=d.get("bus") or "?",
                        tamano=opt.format_bytes(d.get("tamano") or 0), salud=d.get("salud") or "?"),
                      t("salud_disco_linea2", desgaste=o_no(d.get("desgaste"), "{}%"),
                        temperatura=o_no(d.get("temperatura"), "{} °C"), horas=o_no(d.get("horas"), "{}"),
                        errores=o_no(sum(contados) if contados else None, "{}"))]
            lineas += [t(m) for m in d.get("motivos") or []]
            if all(d.get(k) is None for k in ("desgaste", "temperatura", "horas")):
                lineas.append(t("salud_sin_contadores"))
            tarjeta(d.get("nombre") or "?", d["veredicto"], lineas)

        titulo(t("salud_bateria"))
        baterias = datos.get("baterias")
        if baterias is None:
            tarjeta(t("bat_error"), None, [])
        elif not baterias:
            tarjeta(t("bat_ninguna"), None, [])
        for b in baterias or []:
            tarjeta(f'{b["fabricante"]} {b["nombre"]}'.strip() or t("inf_bateria"), b["veredicto"],
                    [t("bat_resumen", porcentaje=b["porcentaje"], ciclos=b["ciclos"] if b["ciclos"] is not None else "?"),
                     t("bat_capacidad", actual=b["actual_mwh"], diseno=b["diseno_mwh"]),
                     t({"bien": "bat_consejo_bien", "atencion": "bat_consejo_atencion",
                        "critico": "bat_consejo_critico"}[b["veredicto"]])])

        titulo(t("salud_estabilidad"))
        fallos = datos.get("fallos")
        if fallos is None:
            tarjeta(t("bsod_error"), None, [])
        else:
            pantallazos = fallos["pantallazos"]
            nivel = "critico" if len(pantallazos) >= 3 else ("atencion" if pantallazos or fallos["apagados"] >= 5 else "bien")
            lineas = [t("bsod_resumen", pantallazos=len(pantallazos)),
                      t("bsod_apagados", apagados=fallos["apagados"], dias=fallos["dias"])]
            if fallos["apagados"] >= 5 and not pantallazos:
                lineas.append(t("bsod_apagados_consejo"))
            tarjeta(t("salud_estabilidad_titulo"), nivel, lineas)
            for p in pantallazos[:15]:
                codigo = f'0x{p["codigo"]:X}' if p["codigo"] is not None else "?"
                tarjeta(f'{p["fecha"]}  ·  {codigo}  {p["nombre"] or ""}', None,
                        [t(p["causa"]), t("bsod_pista")])

    def _accion_informe_bateria(self):
        def worker():
            ruta = tec.abrir_informe_bateria_windows(opt.carpeta_conocida("escritorio") or prefs.carpeta_datos())
            msg = t("bat_informe_ok", ruta=ruta) if ruta else t("bat_informe_error")
            self.after(0, lambda: self._pintar_aviso_tecnico(msg) if not ruta else None)
            self._log_dev(t("bat_log_informe"), "powercfg /batteryreport", msg,
                          seccion=t("seccion_tecnico"), exito=bool(ruta))
        threading.Thread(target=worker, daemon=True).start()

    # ---- Pestaña: respaldo de controladores ----
    def _mostrar_drivers_respaldo(self):
        self._limpiar_contenedor_tecnico()
        ctk.CTkLabel(self.contenedor_tecnico, text=t("drv_desc"), font=fuente(size=11), text_color=T.texto2,
                     wraplength=880, justify="left", anchor="w").pack(fill="x", pady=(0, 8))
        fila = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 8))
        self.btn_drv_exportar = ctk.CTkButton(fila, text=t("drv_btn_exportar"), width=230,
                                              command=self._accion_exportar_drivers)
        self.btn_drv_exportar.pack(side="left")
        self.btn_drv_restaurar = ctk.CTkButton(fila, text=t("drv_btn_restaurar"), width=230, fg_color=T.boton2,
                                               hover_color=T.boton2_hover, command=self._accion_restaurar_drivers, text_color=T.texto)
        self.btn_drv_restaurar.pack(side="left", padx=8)
        self.lbl_drivers = ctk.CTkLabel(self.contenedor_tecnico, text="", font=fuente(size=12), anchor="w",
                                        wraplength=880, justify="left")
        self.lbl_drivers.pack(fill="x", pady=(4, 0))
        if getattr(self, "_drv_en_curso", False):
            self._botones_drivers(False)
            self.lbl_drivers.configure(text=t("drv_en_curso", minutos=0))

    def _botones_drivers(self, activos):
        for nombre in ("btn_drv_exportar", "btn_drv_restaurar"):
            boton = getattr(self, nombre, None)
            try:
                if boton is not None and boton.winfo_exists():
                    boton.configure(state="normal" if activos else "disabled")
            except Exception:
                pass

    def _correr_drivers(self, funcion, carpeta, mensaje_ok, mensaje_error, nombre_log, comando):
        self._drv_en_curso = True
        self._botones_drivers(False)
        self._actualizar_label("lbl_drivers", t("drv_en_curso", minutos=0))

        def progreso(seg):
            texto = t("drv_en_curso", minutos=int(seg // 60))
            self.after(0, lambda: self._actualizar_label("lbl_drivers", texto))

        def worker():
            resultado = funcion(carpeta, opt, progreso)
            exito = resultado[0]
            msg = mensaje_ok(resultado) if exito else (
                mensaje_error(resultado) if callable(mensaje_error) else mensaje_error)
            self._log_dev(nombre_log, comando, msg + "\n" + str(resultado[-1])[-400:],
                          seccion=t("seccion_tecnico"), exito=exito)

            def terminar():
                self._drv_en_curso = False
                self._botones_drivers(True)
                self._actualizar_label("lbl_drivers", msg)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _accion_exportar_drivers(self):
        from tkinter import filedialog
        base = filedialog.askdirectory(title=t("drv_elegir_destino"),
                                       initialdir=opt.carpeta_conocida("escritorio") or os.path.expanduser("~"))
        if not base:
            return
        # Nombre corto a propósito: pnputil se corta con "nombre de archivo
        # demasiado largo" si la ruta de destino ya es larga.
        nombre = f"Drivers_{datetime.now().strftime('%Y%m%d')}"
        carpeta = os.path.join(base, "".join(c for c in nombre if c not in '\\/:*?"<>|'))
        try:
            os.makedirs(carpeta, exist_ok=True)
        except OSError as e:
            self.lbl_drivers.configure(text=t("drv_error_carpeta", error=e))
            return
        self._correr_drivers(
            tec.exportar_drivers, carpeta,
            lambda r: t("drv_exportado", cantidad=r[1], tamano=opt.format_bytes(r[2]), ruta=carpeta),
            lambda r: (t("drv_exportado_parcial", exportados=r[5], total=r[4], ruta=carpeta)
                       if r[4] and r[5] is not None and r[5] < r[4] else t("drv_exportar_error")),
            t("drv_log_exportar"), f'pnputil /export-driver * "{carpeta}"')

    def _accion_restaurar_drivers(self):
        from tkinter import filedialog
        carpeta = filedialog.askdirectory(title=t("drv_elegir_origen"),
                                          initialdir=opt.carpeta_conocida("escritorio") or os.path.expanduser("~"))
        if not carpeta:
            return
        cantidad, _ = tec.contar_drivers(carpeta)
        if cantidad == 0:
            self.lbl_drivers.configure(text=t("drv_carpeta_vacia"))
            return
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("480x220")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("drv_confirmar", cantidad=cantidad, ruta=carpeta), font=fuente(size=13),
                     wraplength=440, justify="left").pack(padx=20, pady=(20, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            self._correr_drivers(
                tec.restaurar_drivers, carpeta, lambda r: t("drv_restaurado", cantidad=cantidad),
                t("drv_restaurar_error"), t("drv_log_restaurar"),
                f'pnputil /add-driver "{carpeta}\\*.inf" /subdirs /install')
        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("drv_btn_instalar"), command=confirmar).pack(side="left", padx=8)

    # ---- Pestaña 2: inspector de arranque ----
    def _mostrar_inspector_arranque(self):
        self._limpiar_contenedor_tecnico()
        fila = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(fila, text=t("tec_btn_inspeccionar"),
                      command=self._accion_inspeccionar_arranque).pack(side="left")
        ctk.CTkLabel(self.contenedor_tecnico, text=t("tec_arranque_explicacion"),
                     font=fuente(size=11), text_color=T.texto2,
                     wraplength=880, justify="left").pack(anchor="w", pady=(0, 8))

        self.lista_tecnico = ctk.CTkScrollableFrame(self.contenedor_tecnico,
                                                     fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        self.lista_tecnico.pack(fill="both", expand=True)
        ctk.CTkLabel(self.lista_tecnico, text=t("tec_arranque_pulsa"),
                     text_color=T.texto2).pack(padx=16, pady=16)

    def _accion_inspeccionar_arranque(self):
        self._pintar_aviso_tecnico(t("tec_arranque_buscando"))

        def worker():
            entradas = tec.inspeccionar_arranque()
            self._log_dev(t("tec_log_arranque"), "N/A",
                          t("tec_arranque_encontradas", total=len(entradas)),
                          seccion=t("seccion_tecnico"), exito=True)
            self.after(0, lambda: self._pintar_inspector_arranque(entradas))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_inspector_arranque(self, entradas):
        if not (hasattr(self, "lista_tecnico") and self.lista_tecnico.winfo_exists()):
            return
        for w in self.lista_tecnico.winfo_children():
            w.destroy()
        if not entradas:
            ctk.CTkLabel(self.lista_tecnico, text=t("tec_arranque_vacio"),
                         text_color=T.texto2, wraplength=820).pack(padx=16, pady=16)
            return

        origen_actual = None
        for e in entradas:
            origen = e.get("origen") or ""
            if origen != origen_actual:
                origen_actual = origen
                ctk.CTkLabel(self.lista_tecnico, text=origen,
                             font=fuente(size=12, weight="bold"),
                             text_color=COLOR_ACCENT, anchor="w").pack(
                    fill="x", padx=14, pady=(12, 4))
            fila = ctk.CTkFrame(self.lista_tecnico, fg_color=T.fila, corner_radius=T.radio_fila)
            fila.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(fila, text=e.get("nombre") or "?", anchor="w",
                         font=fuente(size=12, weight="bold"),
                         wraplength=280, justify="left", width=290).pack(
                side="left", padx=12, pady=8)
            ctk.CTkLabel(fila, text=e.get("comando") or "", anchor="w",
                         font=fuente(family="Consolas", size=11), text_color=T.texto2,
                         wraplength=520, justify="left").pack(
                side="left", padx=(0, 12), pady=8, fill="x", expand=True)

    # ---- Pestaña 3: grabar métricas a CSV ----
    def _mostrar_grabador_metricas(self):
        self._limpiar_contenedor_tecnico()
        fila = ctk.CTkFrame(self.contenedor_tecnico, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 10))
        self.btn_grabar_metricas = ctk.CTkButton(
            fila, text=t("tec_btn_grabar"), command=self._toggle_grabar_metricas)
        self.btn_grabar_metricas.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(fila, text=t("tec_grabar_intervalo"), font=fuente(size=12),
                     text_color=T.texto2).pack(side="left", padx=(0, 6))
        self.combo_intervalo_metricas = ctk.CTkOptionMenu(
            fila, values=["2", "5", "10", "30"], width=80)
        self.combo_intervalo_metricas.set("5")
        self.combo_intervalo_metricas.pack(side="left")

        ctk.CTkLabel(self.contenedor_tecnico, text=t("tec_grabar_explicacion"),
                     font=fuente(size=11), text_color=T.texto2,
                     wraplength=880, justify="left").pack(anchor="w", pady=(0, 8))

        self.lista_tecnico = ctk.CTkScrollableFrame(self.contenedor_tecnico,
                                                     fg_color=COLOR_BG_PANEL, corner_radius=T.radio_panel)
        self.lista_tecnico.pack(fill="both", expand=True)
        activo = self._grabador is not None and self._grabador.activo
        self._pintar_estado_grabador(
            t("tec_grabando", muestras=self._grabador.muestras) if activo
            else t("tec_grabar_parado"))
        if activo:
            self.btn_grabar_metricas.configure(text=t("tec_btn_parar"))

    def _pintar_estado_grabador(self, texto):
        self._pintar_aviso_tecnico(texto)

    def _toggle_grabar_metricas(self):
        if self._grabador is not None and self._grabador.activo:
            muestras = self._grabador.detener()
            ruta = self._grabador.ruta
            self.btn_grabar_metricas.configure(text=t("tec_btn_grabar"))
            self._pintar_estado_grabador(t("tec_grabar_terminado", muestras=muestras, ruta=ruta))
            self._log_dev(t("tec_log_grabar_fin"), ruta,
                          t("tec_grabar_terminado", muestras=muestras, ruta=ruta),
                          seccion=t("seccion_tecnico"), exito=True)
            return

        try:
            intervalo = int(self.combo_intervalo_metricas.get())
        except ValueError:
            intervalo = 5
        carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
        nombre = f"techclean_metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._grabador = tec.GrabadorMetricas(os.path.join(carpeta, nombre), sysmon,
                                               intervalo_seg=intervalo)
        self._grabador.iniciar()
        self.btn_grabar_metricas.configure(text=t("tec_btn_parar"))
        self._pintar_estado_grabador(t("tec_grabar_iniciado", ruta=self._grabador.ruta,
                                        intervalo=intervalo))
        self._log_dev(t("tec_log_grabar_inicio"), self._grabador.ruta,
                      t("tec_grabar_iniciado", ruta=self._grabador.ruta, intervalo=intervalo),
                      seccion=t("seccion_tecnico"), exito=True)

    # ---------------- BIOS / UEFI ----------------
    def mostrar_bios(self):
        """Energía (rediseño 1.8.0): la batería y su desgaste, qué apps gastan
        más energía (la estimación de Windows de los últimos 7 días) y las
        acciones de encendido en filas, en vez de seis botones de colores."""
        self._limpiar_contenido()
        self._encabezado(t("energia_titulo"), t("energia_subtitulo"))
        cuerpo = self._cuerpo()

        # ---- Batería ----
        if sysmon.get_battery_info() is not None:
            panel, derecha = tarjeta_seccion(cuerpo, t("ene_bat_titulo"), "energia")
            panel.pack(fill="x", padx=8, pady=(0, 12))
            self.pild_bateria_ene = pildora(derecha)
            self.pild_bateria_ene.pack(side="right")
            boton_secundario(derecha, t("ene_bat_informe"), self._accion_informe_bateria_energia, height=30).pack(
                side="right", padx=(0, 10))
            self.barra_bateria_ene = BarraFina(panel)
            self.barra_bateria_ene.pack(fill="x", padx=18, pady=(0, 8))
            self.panel_bateria_ene = ListaDatos(panel)
            self.panel_bateria_ene.pack(fill="x", padx=18, pady=(0, 16))

        # ---- Qué gasta la energía ----
        panel, _ = tarjeta_seccion(cuerpo, t("ene_consumo_titulo"), "optimizar", t("ene_consumo_desc"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        self.caja_consumo = Caja(panel)
        self.caja_consumo.pack(fill="x", padx=18, pady=(0, 16))
        Texto(self.caja_consumo, t("comun_cargando"), size=12, color=T.texto2).pack(fill="x")

        # ---- Acciones ----
        panel, _ = tarjeta_seccion(cuerpo, t("ene_sec_acciones"), "energia", t("energia_intro"))
        panel.pack(fill="x", padx=8, pady=(0, 12))
        acciones = (
            ("energia", "energia_apagar", "energia_apagar_desc", self._confirmar_apagar),
            ("historial", "energia_reiniciar", "energia_reiniciar_desc", self._confirmar_reiniciar),
            ("calendario", "energia_suspender", "energia_suspender_desc", self._accion_suspender),
            ("disco", "energia_hibernar", "energia_hibernar_desc", self._accion_hibernar),
            ("componentes", "energia_bios", "energia_bios_desc", self._confirmar_reinicio_bios),
        )
        for i, (icono, titulo, desc, comando) in enumerate(acciones):
            fila_accion(panel, icono, t(titulo), t(desc), _sin_emoji(t(titulo)), comando, primera=i == 0)
        fila_accion(panel, "archivo", _sin_emoji(t("energia_inf_btn")), t("energia_inf_desc"),
                    t("ene_accion_generar"), self._accion_informe_energia)
        self.lbl_informe_energia = Texto(panel, "", size=12, wraplength=760)
        self.lbl_informe_energia.pack(fill="x", padx=20, pady=(0, 14))
        texto_fluido(self.lbl_informe_energia, panel, 40)

        def worker():
            datos = {"bateria": sysmon.get_battery_info(), "salud": tec.salud_bateria()}
            self.after(0, lambda: self._pintar_bateria_energia(datos))
            consumo = tec.consumo_energia_apps()
            self.after(0, lambda: self._pintar_consumo(consumo))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_bateria_energia(self, datos):
        if not (hasattr(self, "panel_bateria_ene") and self.panel_bateria_ene.winfo_exists()):
            return
        b = datos["bateria"]
        if b:
            carga = b["porcentaje"]
            self.barra_bateria_ene.poner(carga / 100, T.ok if carga > 20 or b["cargando"] else T.aviso)
            estado = t("comp_bateria_cargando") if b["cargando"] else t("comp_bateria_descargando")
            self.panel_bateria_ene.poner("carga", t("comp_d_estado"), f"{carga:.0f} % · {estado}")
            if b["minutos_restantes"]:
                self.panel_bateria_ene.poner("restante", t("comp_d_restante"),
                                             t("comp_v_min", minutos=b["minutos_restantes"]))
        salud = (datos.get("salud") or [None])[0]
        if salud and salud.get("actual_mwh") is not None:
            nivel = salud.get("veredicto") or "bien"
            poner_pildora(self.pild_bateria_ene, t({"bien": "comp_salud_bien", "atencion": "comp_salud_atencion",
                                                    "critico": "fallos_grave"}[nivel]), nivel)
            self.panel_bateria_ene.poner("capacidad", t("comp_d_capacidad"),
                                         t("comp_v_capacidad", actual=f'{salud["actual_mwh"] / 1000:.1f}',
                                           diseno=f'{salud["diseno_mwh"] / 1000:.1f}', pct=salud["porcentaje"]))
            if salud.get("ciclos") is not None:
                self.panel_bateria_ene.poner("ciclos", t("comp_d_ciclos"), str(salud["ciclos"]))
            if salud.get("quimica") or salud.get("fabricante"):
                self.panel_bateria_ene.poner("modelo", t("ene_d_modelo"),
                                             " · ".join(x for x in (salud.get("fabricante"), salud.get("nombre"),
                                                                    salud.get("quimica")) if x))

    def _pintar_consumo(self, consumo):
        if not (hasattr(self, "caja_consumo") and self.caja_consumo.winfo_exists()):
            return
        for w in self.caja_consumo.winfo_children():
            w.destroy()
        if consumo.get("error"):
            texto = t("ene_consumo_admin") if consumo["error"] == "admin" else t("ene_consumo_error")
            texto_fluido(Texto(self.caja_consumo, texto, size=12, color=T.texto2, wraplength=760),
                         self.caja_consumo, 4).pack(fill="x")
            return
        apps = consumo["apps"]
        if not apps:
            Texto(self.caja_consumo, t("ene_consumo_vacio"), size=12, color=T.texto2).pack(fill="x")
            return
        for app in apps[:8]:
            linea_app = Caja(self.caja_consumo)
            linea_app.pack(fill="x", pady=(6, 0))
            Texto(linea_app, app["nombre"], size=12).pack(side="left")
            detalle = f'{app["pct"]:.0f} %'
            if app["con_bateria"] and app["energia"]:
                detalle += "  ·  " + t("ene_v_con_bateria", pct=round(app["con_bateria"] * 100 / app["energia"]))
            Texto(linea_app, detalle, size=12, color=T.texto2).pack(side="right")
            BarraFina(self.caja_consumo, grosor=5).poner(app["pct"] / 100, T.acento)
            self.caja_consumo.winfo_children()[-1].pack(fill="x", pady=(2, 0))

    def _accion_informe_bateria_energia(self):
        """El informe de batería de Windows desde Energía. Se llamaba igual
        que el de la pestaña Técnico (edición Admin) y lo pisaba: allí el
        informe dejó de guardarse en el Escritorio y de avisar si fallaba
        (BUG de la propia 1.8.0, encontrado buscando definiciones repetidas)."""
        def worker():
            ruta = tec.abrir_informe_bateria_windows(prefs.carpeta_datos())
            self._log_dev(t("bat_log_informe"), "powercfg /batteryreport",
                          ruta or t("bat_error"), seccion=t("seccion_energia"), exito=bool(ruta))
            if not ruta:
                self.after(0, lambda: self._mostrar_popup_info(t("ene_bat_informe"), t("bat_informe_error")))
        threading.Thread(target=worker, daemon=True).start()

    # ---- Reparar: puntos de restauración ----
    def _cargar_puntos(self):
        if not (hasattr(self, "lista_puntos") and self.lista_puntos.winfo_exists()):
            return
        for w in self.lista_puntos.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lista_puntos, text=t("comun_cargando"), text_color=T.texto2).pack(anchor="w")

        def worker():
            puntos = opt.listar_puntos_restauracion()
            usado, maximo = opt.espacio_puntos_restauracion()
            self.after(0, lambda: self._pintar_puntos(puntos, usado, maximo))
        threading.Thread(target=worker, daemon=True).start()

    def _pintar_puntos(self, puntos, usado, maximo):
        if not (hasattr(self, "lista_puntos") and self.lista_puntos.winfo_exists()):
            return
        for w in self.lista_puntos.winfo_children():
            w.destroy()
        if puntos is None:
            texto_fluido(Texto(self.lista_puntos, t("puntos_sin_permiso"), size=12, color=T.texto2, wraplength=760),
                         self.lista_puntos, 4).pack(fill="x")
            self.btn_borrar_puntos.configure(state="disabled")
            return
        if usado is not None:
            Texto(self.lista_puntos, t("puntos_espacio", usado=opt.format_bytes(usado),
                                       maximo=opt.format_bytes(maximo or 0)), size=12, weight="bold").pack(
                fill="x", pady=(0, 4))
        if not puntos:
            Texto(self.lista_puntos, t("puntos_ninguno"), size=12, color=T.texto2).pack(fill="x")
        lista = ListaDatos(self.lista_puntos)
        lista.pack(fill="x")
        for i, p in enumerate(puntos[:20]):
            lista.poner(i, p["fecha"], p["descripcion"], T.texto2)
        self.btn_borrar_puntos.configure(state="normal" if len(puntos) > 1 else "disabled")

    def _accion_crear_punto(self):
        self._actualizar_label("lbl_puntos", t("puntos_creando"))

        def worker():
            exito, comando = opt.crear_punto_restauracion(t("puntos_desc_manual"))
            msg = t("puntos_creado") if exito else t("puntos_no_creado")
            self._log_dev(t("rep_log_punto"), comando, msg, seccion=t("seccion_reparar"), exito=exito)

            def terminar():
                self._actualizar_label("lbl_puntos", msg)
                self._cargar_puntos()
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _confirmar_borrar_puntos(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("480x220")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("puntos_confirmar"), font=fuente(size=13), wraplength=440,
                     justify="left").pack(padx=20, pady=(20, 10))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            self._actualizar_label("lbl_puntos", t("puntos_borrando"))

            def worker():
                borrados, restantes, comando = opt.borrar_puntos_antiguos()
                msg = t("puntos_borrados", borrados=borrados, restantes=restantes)
                self._log_dev(t("puntos_log_borrar"), comando, msg, seccion=t("seccion_reparar"),
                              exito=borrados > 0)

                def terminar():
                    self._actualizar_label("lbl_puntos", msg)
                    self._cargar_puntos()
                self.after(0, terminar)
            threading.Thread(target=worker, daemon=True).start()
        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("puntos_btn_borrar"), fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

    # ---- Energía: informe de energía de Windows ----
    def _accion_informe_energia(self):
        if getattr(self, "_energia_en_curso", False):
            self._evento_energia.set()
            return
        self._energia_en_curso = True
        self._evento_energia = threading.Event()
        self._actualizar_label("lbl_informe_energia", t("energia_inf_en_curso", segundos=0))

        def progreso(seg):
            texto = t("energia_inf_en_curso", segundos=int(seg))
            self.after(0, lambda: self._actualizar_label("lbl_informe_energia", texto))

        def worker():
            carpeta = opt.carpeta_conocida("escritorio") or prefs.carpeta_datos()
            exito, ruta, resumen, cancelado = opt.informe_energia(carpeta, progreso, self._evento_energia)
            if exito:
                try:
                    os.startfile(ruta)
                except Exception:
                    pass
            msg = (t("fondo_dism_cancelado") if cancelado else
                   t("energia_inf_ok", ruta=ruta) if exito else t("energia_inf_error"))
            self._log_dev(t("energia_inf_log"), "powercfg /energy /duration 60", msg + "\n" + resumen[-400:],
                          seccion=t("seccion_energia"), exito=exito)

            def terminar():
                self._energia_en_curso = False
                self._actualizar_label("lbl_informe_energia", msg)
            self.after(0, terminar)
        threading.Thread(target=worker, daemon=True).start()

    def _confirmar_apagar(self):
        self._pedir_confirmacion(
            t("energia_conf_apagar_tit"), t("energia_conf_apagar_msg"),
            t("energia_conf_apagar_btn"),
            lambda: self._ejecutar_accion_energia(opt.apagar_equipo, t("energia_log_apagar")))

    def _confirmar_reiniciar(self):
        self._pedir_confirmacion(
            t("energia_conf_reiniciar_tit"), t("energia_conf_reiniciar_msg"),
            t("energia_conf_reiniciar_btn"),
            lambda: self._ejecutar_accion_energia(opt.reiniciar_equipo, t("energia_log_reiniciar")))

    def _confirmar_reinicio_bios(self):
        self._pedir_confirmacion(
            t("energia_conf_bios_tit"), t("energia_conf_bios_msg"),
            t("energia_conf_bios_btn"),
            lambda: self._ejecutar_accion_energia(opt.restart_to_uefi, t("energia_log_bios")))

    def _pedir_confirmacion(self, titulo, mensaje, texto_boton, accion_confirmada):
        """Ventana de "¿seguro?" reutilizable. Nacio para Energia (de ahi el
        nombre viejo, _confirmar_accion_energia) pero no tiene nada de
        Energia: la usa cualquier accion que convenga confirmar."""
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("420x200")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=titulo, font=fuente(size=15, weight="bold"),
                     wraplength=380, justify="center").pack(pady=(20, 6))
        ctk.CTkLabel(dialogo, text=mensaje, font=fuente(size=12), text_color=T.texto2,
                     wraplength=380, justify="center").pack(padx=20, pady=(0, 16))
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            accion_confirmada()

        ctk.CTkButton(fila, text=t("comun_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=texto_boton, fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

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
        """Ajustes (rediseño 1.8.0): agrupados en tarjetas, cada ajuste en su
        fila con lo que hace debajo. Antes era una sola lista larguísima."""
        self._limpiar_contenido()
        self._encabezado(t("ajustes_titulo"))
        cuerpo = self._cuerpo()

        # ---- Acerca de ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_card_acerca"), "marca")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.lbl_version = Texto(panel, t("ajustes_version", version=APP_VERSION), size=15, weight="bold",
                                 cursor="hand2" if EDICION == "cliente" else "arrow")
        self.lbl_version.pack(fill="x", padx=18)
        if EDICION == "cliente":
            self.lbl_version.bind("<Button-1>", self._click_dev_unlock)
        self.lbl_credito = Texto(panel, t("ajustes_desarrollado_por", nombre=DEV_NAME, alias=DEV_ALIAS),
                                 size=13, color=T.texto2, cursor="hand2")
        self.lbl_credito.pack(fill="x", padx=18, pady=(2, 0))
        self.lbl_credito.bind("<Button-1>", self._click_easter_egg)
        Texto(panel, t("ajustes_descripcion_app"), size=12, color=T.texto2).pack(fill="x", padx=18, pady=(2, 12))
        fila_actualizacion = Caja(panel)
        fila_actualizacion.pack(fill="x", padx=18, pady=(0, 18))
        boton_secundario(fila_actualizacion, _sin_emoji(t("ajustes_buscar_actualizaciones")),
                         self._accion_buscar_actualizacion_manual, icono="bandeja").pack(side="left")
        boton_secundario(fila_actualizacion, t("nov_btn_ver"), self._mostrar_novedades, icono="marca").pack(
            side="left", padx=(8, 0))
        boton_secundario(fila_actualizacion, t("priv_app_btn"), self._mostrar_privacidad_app,
                         icono="privacidad").pack(side="left", padx=(8, 0))
        self.lbl_resultado_actualizacion = Texto(fila_actualizacion, "", size=12, color=T.texto2)
        self.lbl_resultado_actualizacion.pack(side="left", padx=12)

        self._seccion_apariencia(cuerpo)

        # La tarjeta de apoyo va deliberadamente distinta al resto de filas de
        # Ajustes: antes era un boton gris "#2a2d36" identico al de Buscar
        # actualizaciones justo debajo, y se perdia entre las demas opciones.
        # Ahora tiene fondo calido propio, borde de acento y su propio titulo,
        # para que se distinga sin volverse un anuncio molesto.
        tarjeta_donar = ctk.CTkFrame(cuerpo, fg_color=T.calido, corner_radius=T.radio_panel,
                                     border_width=1, border_color=COLOR_DONAR)
        tarjeta_donar.pack(fill="x", padx=4, pady=(0, 12))
        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_titulo"),
                     font=fuente(size=15, weight="bold"), text_color=COLOR_DONAR).pack(
            padx=18, pady=(14, 2), anchor="w")
        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_desc"),
                     font=fuente(size=12), text_color=T.texto2,
                     wraplength=620, justify="left").pack(padx=18, pady=(0, 2), anchor="w")
        ctk.CTkLabel(tarjeta_donar, text=t("ajustes_donar_nota"),
                     font=fuente(size=11), text_color=T.texto3,
                     wraplength=620, justify="left").pack(padx=18, pady=(0, 10), anchor="w")
        ctk.CTkButton(tarjeta_donar, text=t("ajustes_donar_boton"), width=200, height=38,
                      font=fuente(size=13, weight="bold"),
                      fg_color=COLOR_DONAR, hover_color="#e0524f", text_color="white",
                      command=self._accion_abrir_donacion).pack(padx=18, pady=(0, 16), anchor="w")

        # ---- General ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_card_general"), "ajustes")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.switch_inicio, _ = fila_interruptor(panel, "inicio", t("ajustes_inicio_windows_titulo"),
                                                 t("ajustes_inicio_windows_desc"), False,
                                                 self._toggle_inicio_automatico, primera=True)
        # Aviso para una tarea que existe pero no va a arrancar — ver
        # opt.diagnostico_inicio_automatico(). Nace oculto y solo aparece
        # si de verdad hay algo que decir (justo debajo de su interruptor).
        caja_aviso = Caja(panel)
        caja_aviso.pack(fill="x")
        self.fila_aviso_inicio = Caja(caja_aviso)
        self.btn_arreglar_inicio = ctk.CTkButton(self.fila_aviso_inicio, width=110,
                                                 text=t("ajustes_inicio_arreglar"),
                                                 command=self._arreglar_inicio_automatico)
        self.btn_arreglar_inicio.pack(side="right", padx=(10, 0))
        self.lbl_aviso_inicio = Texto(self.fila_aviso_inicio, "", size=12, color=T.aviso, wraplength=620)
        self.lbl_aviso_inicio.pack(side="left", fill="x", expand=True)
        texto_fluido(self.lbl_aviso_inicio, self.fila_aviso_inicio, 140)

        # is_startup_enabled() y el diagnóstico llaman a schtasks: hasta 10 s
        # de subproceso. En el hilo principal congelaban Ajustes al abrirlo.
        def worker_estado_inicio():
            activo = opt.is_startup_enabled()
            estado = opt.diagnostico_inicio_automatico() if activo else None
            self.after(0, lambda: self._pintar_estado_inicio(activo, estado))
        threading.Thread(target=worker_estado_inicio, daemon=True).start()

        self.switch_modo_ligero, _ = fila_interruptor(panel, "energia", t("ajustes_modo_ligero_titulo"),
                                                      t("ajustes_modo_ligero_desc"), self.prefs.get("modo_ligero"),
                                                      self._toggle_modo_ligero)
        # El selector de idioma es exclusivo de la edicion admin: el cliente se
        # reparte como dos ejecutables separados, uno por idioma, asi que ahi
        # no hay nada que elegir. Ver IDIOMA_BUILD arriba.
        if EDICION == "admin":
            derecha = fila(panel, "globo", t("ajustes_idioma_titulo"), t("ajustes_idioma_descripcion"))
            self.combo_idioma = ctk.CTkOptionMenu(
                derecha, values=list(idiomas.IDIOMAS_DISPONIBLES.values()),
                command=self._cambiar_idioma, width=140)
            self.combo_idioma.set(idiomas.IDIOMAS_DISPONIBLES.get(
                self.prefs.get("idioma", IDIOMA_BUILD), "Español"))
            self.combo_idioma.pack(side="right")
        Caja(panel, height=6).pack()

        # ---- Memoria ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_card_memoria"), "memoria")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        self.switch_auto_ram, _ = fila_interruptor(panel, "memoria", t("ajustes_auto_ram_titulo"),
                                                   t("ajustes_umbral_ram_desc"),
                                                   self.prefs.get("auto_ram_activa", True), self._toggle_auto_ram,
                                                   primera=True)
        derecha = fila(panel, "optimizar", t("ajustes_umbral_ram_titulo"), None)
        self.combo_umbral_ram = ctk.CTkOptionMenu(
            derecha, values=["50%", "60%", "70%", "75%", "80%", "85%", "90%"], width=90,
            command=lambda v: self._guardar_umbral_ram(int(v.replace("%", ""))))
        self.combo_umbral_ram.set(f'{self.prefs.get("umbral_ram_auto", 85)}%')
        self.combo_umbral_ram.pack(side="right")
        derecha = fila(panel, "historial", t("ajustes_auto_ram_intervalo"), None)
        # El texto visible se traduce; lo que se guarda son minutos. Se
        # resuelve contra este mismo diccionario, nunca contra un literal.
        opciones_intervalo = {t("ajustes_auto_ram_nunca"): 0}
        for minutos in (15, 30, 60, 120):
            opciones_intervalo[t("ajustes_auto_ram_cada", minutos=minutos)] = minutos
        self.combo_intervalo_ram = ctk.CTkOptionMenu(
            derecha, values=list(opciones_intervalo), width=130,
            command=lambda v: self._guardar_intervalo_ram(opciones_intervalo.get(v, 0)))
        actual = self.prefs.get("auto_ram_intervalo_min", 0)
        self.combo_intervalo_ram.set(next((k for k, v in opciones_intervalo.items() if v == actual),
                                          t("ajustes_auto_ram_nunca")))
        self.combo_intervalo_ram.pack(side="right")

        # Atajo de teclado global (1.7.0)
        derecha = fila(panel, "consola", t("atajo_titulo"), t("atajo_desc"))
        self.switch_atajo_ram = ctk.CTkSwitch(derecha, text="", width=46, command=self._toggle_atajo_ram)
        self.switch_atajo_ram.pack(side="right")
        if self.prefs.get("atajo_ram_activo", False):
            self.switch_atajo_ram.select()
        self.combo_atajo_ram = ctk.CTkOptionMenu(
            derecha, values=[atajos.texto_combinacion(c) for c in atajos.COMBINACIONES], width=160,
            command=self._cambiar_combinacion_atajo)
        self.combo_atajo_ram.set(atajos.texto_combinacion(self.prefs.get("atajo_ram_combinacion", "ctrl+alt+r")))
        self.combo_atajo_ram.pack(side="right", padx=(0, 10))
        self.lbl_estado_atajo = Texto(derecha.textos, "", size=12)
        self.lbl_estado_atajo.pack(fill="x", pady=(4, 0))
        self._pintar_estado_atajo()
        Caja(panel, height=6).pack()

        # ---- Avisos ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_avisos_titulo"), "campana", t("ajustes_avisos_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        derecha = fila(panel, "componentes", t("ajustes_alerta_temp_titulo"), t("ajustes_alerta_temp_desc"),
                       primera=True)
        self.entry_alerta_temp = ctk.CTkEntry(derecha, width=70, placeholder_text=t("ajustes_temp_placeholder"))
        umbral_actual = self.prefs.get("alerta_temp_cpu")
        if umbral_actual:
            self.entry_alerta_temp.insert(0, str(int(umbral_actual)))
        self.entry_alerta_temp.pack(side="right")
        boton_secundario(derecha, t("ajustes_guardar"), self._guardar_alerta_temp, width=80, height=32).pack(
            side="right", padx=(0, 8))
        self.switch_avisar_fugas, _ = fila_interruptor(
            panel, "memoria", t("ajustes_avisar_fugas"), None, self.prefs.get("avisar_fugas", True),
            lambda: self._toggle_aviso("avisar_fugas", self.switch_avisar_fugas))
        self.switch_avisar_disco, _ = fila_interruptor(
            panel, "disco", t("ajustes_avisar_disco"), None, self.prefs.get("avisar_disco_lleno", True),
            lambda: self._toggle_aviso("avisar_disco_lleno", self.switch_avisar_disco))
        # 1.7.0: días sin reiniciar y límite de carga de la batería.
        self.switch_avisar_reinicio, derecha = fila_interruptor(
            panel, "reparar", t("ajustes_avisar_reinicio"), None, self.prefs.get("avisar_reinicio", True),
            lambda: self._toggle_aviso("avisar_reinicio", self.switch_avisar_reinicio))
        dias_opciones = {3: t("ajustes_dias_3"), 7: t("ajustes_dias_7"), 14: t("ajustes_dias_14")}
        self.combo_dias_reinicio = ctk.CTkOptionMenu(
            derecha, values=list(dias_opciones.values()), width=110,
            command=lambda v: self._guardar_numero_pref(
                "dias_reinicio", next(d for d, txt in dias_opciones.items() if txt == v)))
        self.combo_dias_reinicio.set(dias_opciones.get(self.prefs.get("dias_reinicio", 7), dias_opciones[7]))
        self.combo_dias_reinicio.pack(side="right", padx=(0, 10))
        self.switch_avisar_carga, derecha = fila_interruptor(
            panel, "energia", t("ajustes_avisar_carga"), t("ajustes_carga_desc"),
            self.prefs.get("avisar_carga_bateria", False),
            lambda: self._toggle_aviso("avisar_carga_bateria", self.switch_avisar_carga))
        self.combo_limite_carga = ctk.CTkOptionMenu(
            derecha, values=["80%", "85%", "90%"], width=90,
            command=lambda v: self._guardar_numero_pref("limite_carga_bateria", int(v.replace("%", ""))))
        self.combo_limite_carga.set(f'{self.prefs.get("limite_carga_bateria", 80)}%')
        self.combo_limite_carga.pack(side="right", padx=(0, 10))
        self.switch_bateria, derecha = fila_interruptor(
            panel, "energia", t("ajustes_bateria_titulo"), t("ajustes_bateria_desc"),
            self.prefs.get("bateria_ahorro_automatico"), self._toggle_ahorro_bateria)
        self.combo_umbral_bateria = ctk.CTkOptionMenu(
            derecha, values=["10%", "15%", "20%", "25%", "30%"], width=80,
            command=lambda v: self._guardar_umbral_bateria(int(v.replace("%", ""))))
        self.combo_umbral_bateria.set(f'{self.prefs.get("bateria_umbral_ahorro", 20)}%')
        self.combo_umbral_bateria.pack(side="right", padx=(0, 10))
        Caja(panel, height=6).pack()

        # ---- Semáforo de Inicio ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_umbral_salud_titulo"), "inicio", t("ajustes_umbral_salud_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        derecha = fila(panel, "memoria", t("ajustes_umbral_salud_ram"), None, primera=True)
        self.combo_umbral_salud_ram = ctk.CTkOptionMenu(
            derecha, values=["60%", "65%", "70%", "75%", "80%", "85%"], width=90,
            command=lambda v: self._guardar_umbral_salud("ram", int(v.replace("%", ""))))
        self.combo_umbral_salud_ram.set(f'{self.prefs.get("umbral_salud_ram", 75)}%')
        self.combo_umbral_salud_ram.pack(side="right")
        derecha = fila(panel, "disco", t("ajustes_umbral_salud_disco"), None)
        self.combo_umbral_salud_disco = ctk.CTkOptionMenu(
            derecha, values=["70%", "75%", "80%", "85%", "90%", "95%"], width=90,
            command=lambda v: self._guardar_umbral_salud("disco", int(v.replace("%", ""))))
        self.combo_umbral_salud_disco.set(f'{self.prefs.get("umbral_salud_disco", 85)}%')
        self.combo_umbral_salud_disco.pack(side="right")
        Caja(panel, height=6).pack()

        # ---- Bandeja y widget ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_card_bandeja"), "monitor")
        panel.pack(fill="x", padx=4, pady=(0, 12))
        derecha = fila(panel, "bandeja", t("ajustes_icono_bandeja_titulo"), t("ajustes_icono_bandeja_desc"),
                       primera=True)
        opciones_icono = {t("ajustes_icono_bandeja_nada"): None, t("ajustes_icono_bandeja_cpu"): "cpu",
                          t("ajustes_icono_bandeja_ram"): "ram"}
        valor_guardado = self.prefs.get("icono_bandeja_metrica")
        self.combo_icono_bandeja = ctk.CTkOptionMenu(
            derecha, values=list(opciones_icono.keys()), width=170,
            command=lambda seleccion: self._guardar_icono_bandeja(opciones_icono[seleccion]))
        self.combo_icono_bandeja.set(next((k for k, v in opciones_icono.items() if v == valor_guardado),
                                          t("ajustes_icono_bandeja_nada")))
        self.combo_icono_bandeja.pack(side="right")
        derecha = fila(panel, "monitor", t("ajustes_widget_metricas_titulo"), t("ajustes_widget_metricas_desc"))
        metricas_guardadas = self.prefs.get("widget_metricas") or ["cpu", "ram", "red", "gpu"]
        self.check_widget_metricas = {}
        for clave, etiqueta in reversed([("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU"),
                                         ("red", t("ajustes_widget_metrica_red"))]):
            marca = casilla(derecha, clave in metricas_guardadas, text=etiqueta, width=60,
                            command=self._guardar_widget_metricas)
            marca.pack(side="right", padx=(10, 0))
            self.check_widget_metricas[clave] = marca
        Caja(panel, height=6).pack()

        # ---- Diagnóstico y errores ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_errores_titulo"), "reparar", t("ajustes_errores_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        botones = Caja(panel)
        botones.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(botones, text=_sin_emoji(t("ajustes_diagnostico_boton")),
                      command=self._accion_diagnostico_completo).pack(side="left", padx=(0, 8))
        boton_secundario(botones, _sin_emoji(t("ajustes_abrir_carpeta_registros")),
                         self._accion_abrir_carpeta_datos, icono="carpeta").pack(side="left", padx=(0, 8))
        # Los dos botones de "Probar error" provocan un fallo A PROPOSITO para
        # comprobar que el aviso de errores funciona. Al usuario final no le
        # sirven de nada: su unico efecto visible es una ventana de error
        # alarmante sin que haya pasado nada malo. Solo en la edicion admin.
        # El resto de esta seccion (Diagnostico completo, Abrir carpeta de
        # registros) SI se queda en cliente: son justo las herramientas que se
        # le piden a alguien cuando reporta un problema.
        if EDICION == "admin":
            boton_secundario(botones, _sin_emoji(t("ajustes_probar_error_directo")),
                             self._accion_probar_error).pack(side="left", padx=(0, 8))
            boton_secundario(botones, _sin_emoji(t("ajustes_probar_error_segundo_plano")),
                             self._accion_probar_error_segundo_plano).pack(side="left")
        boton = boton_secundario(fila(panel, "archivo", t("rend_titulo"), t("rend_desc")),
                                 _sin_emoji(t("rend_btn_generar")), self._accion_reporte_rendimiento, height=34)
        boton.pack()
        Caja(panel, height=6).pack()

        # ---- Exportar / importar / restablecer configuración ----
        panel, _ = tarjeta_seccion(cuerpo, t("ajustes_config_titulo"), "ajustes", t("ajustes_historial_nota"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        fila_config = Caja(panel)
        fila_config.pack(fill="x", padx=18, pady=(0, 8))
        boton_secundario(fila_config, _sin_emoji(t("ajustes_exportar")), self._accion_exportar_config,
                         icono="subir").pack(side="left", padx=(0, 8))
        boton_secundario(fila_config, _sin_emoji(t("ajustes_importar")), self._accion_importar_config,
                         icono="bandeja").pack(side="left", padx=(0, 8))
        ctk.CTkButton(fila_config, text=_sin_emoji(t("ajustes_restablecer")), fg_color=T.peligro,
                      hover_color=T.critico, command=self._accion_restablecer_config,
                      text_color=T.sobre_peligro).pack(side="left")
        self.lbl_resultado_config = Texto(panel, "", size=12, color=T.texto2, wraplength=760)
        self.lbl_resultado_config.pack(fill="x", padx=18, pady=(0, 16))
        texto_fluido(self.lbl_resultado_config, panel, 36)

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
            aceptadas, descartadas = prefs.filtrar_importables(datos)
            if not aceptadas:
                raise ValueError(t("ajustes_importar_formato_invalido"))
            prefs.guardar(aceptadas)
            self.prefs = prefs.cargar()
            texto = t("ajustes_importar_exito")
            if descartadas:
                texto += " " + t("ajustes_importar_descartadas", n=len(descartadas))
            self.lbl_resultado_config.configure(text=texto)
            self._log_dev(t("ajustes_log_importar"), "N/A",
                          t("ajustes_importar_desde", origen=origen),
                          seccion=t("seccion_ajustes"), exito=True)
        except Exception as e:
            self.lbl_resultado_config.configure(text=t("ajustes_importar_error", error=e))

    def _accion_restablecer_config(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("comun_confirmar_titulo"))
        dialogo.geometry("420x180")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("ajustes_restablecer_confirmar"),
                     font=fuente(size=13), wraplength=380, justify="center").pack(pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)

        def confirmar():
            dialogo.destroy()
            prefs.restablecer()
            self.prefs = prefs.cargar()
            self.lbl_resultado_config.configure(text=t("ajustes_restablecer_exito"))
            self._log_dev(t("ajustes_log_restablecer"), "N/A",
                          t("ajustes_restablecida"), seccion=t("seccion_ajustes"), exito=True)

        ctk.CTkButton(fila, text=t("ajustes_cancelar"), fg_color=T.boton2, command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(
            side="left", padx=8)
        ctk.CTkButton(fila, text=t("ajustes_restablecer_boton"), fg_color=T.peligro, hover_color=T.critico,
                      command=confirmar, text_color=T.sobre_peligro).pack(side="left", padx=8)

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
            self.after(0, lambda: self._actualizar_label("lbl_resultado_actualizacion", texto))
            if resultado["hay_nueva"]:
                self.after(0, lambda: self._mostrar_aviso_actualizacion(resultado))
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_aviso_actualizacion(self, resultado):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title(t("upd_titulo_ventana"))
        dialogo.geometry("420x260")
        dialogo.grab_set()
        ctk.CTkLabel(dialogo, text=t("upd_disponible", version=resultado["version"]),
                     font=fuente(size=15, weight="bold"), wraplength=380, justify="left").pack(
            padx=20, pady=(20, 6))
        ctk.CTkLabel(dialogo, text=t("upd_instalada", version=APP_VERSION),
                     font=fuente(size=12), text_color=T.texto2).pack(padx=20, anchor="w")
        if resultado["notas"]:
            caja = ctk.CTkTextbox(dialogo, height=80, font=fuente(size=11))
            caja.pack(fill="x", padx=20, pady=10)
            caja.insert("1.0", resultado["notas"])
            caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(side="bottom", pady=16)
        ctk.CTkButton(fila, text=t("upd_ahora_no"), fg_color=T.boton2,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=6)
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
        ctk.CTkLabel(dialogo, text="🌐", font=fuente(size=36)).pack(pady=(28, 6))
        ctk.CTkLabel(dialogo, text="Selecciona tu idioma\nSelect your language",
                     font=fuente(size=15, weight="bold"), justify="center").pack(pady=(0, 8))
        ctk.CTkLabel(dialogo, text="Se puede cambiar después en Ajustes.\nYou can change this later in Settings.",
                     font=fuente(size=11), text_color=T.texto2, justify="center").pack(pady=(0, 20))

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
                     font=fuente(size=13), wraplength=380, justify="center").pack(padx=20, pady=20)
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=10)
        ctk.CTkButton(fila, text=t("ajustes_mas_tarde"), fg_color=T.boton2,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=8)
        ctk.CTkButton(fila, text=t("ajustes_cerrar_ahora"), fg_color=T.peligro, hover_color=T.critico,
                      command=self._salir_definitivo, text_color=T.sobre_peligro).pack(side="left", padx=8)

    def _aplicar_preferencia_animaciones(self):
        """Modo Ligero apaga la animacion de las barras, en la ventana
        principal y en el widget flotante, sin reiniciar la app."""
        global ANIMAR_BARRAS
        ANIMAR_BARRAS = not self.prefs.get("modo_ligero")
        widget_mod.ANIMAR_BARRAS = ANIMAR_BARRAS

    def _guardar_aviso_reinicio(self, aviso):
        """Como _guardar_avisos_disco: lo llama el vigilante desde su hilo."""
        self.prefs["aviso_reinicio"] = aviso
        prefs.guardar({"aviso_reinicio": aviso})

    def _guardar_avisos_disco(self, avisos):
        """Lo llama el vigilante (desde su hilo) al avisar de un disco lleno.
        Solo toca preferencias, nada de la interfaz."""
        self.prefs["avisos_disco"] = avisos
        prefs.guardar({"avisos_disco": avisos})

    # ---------------- Apariencia: temas (1.8.0) ----------------
    def _seccion_apariencia(self, cuerpo):
        """Ajustes → Apariencia: una tarjeta por tema, con su miniatura."""
        panel, _ = tarjeta_seccion(cuerpo, t("apariencia_titulo"), "imagen", t("apariencia_desc"))
        panel.pack(fill="x", padx=4, pady=(0, 12))
        escala = ctk.ScalingTracker.get_widget_scaling(panel)
        GaleriaTemas(panel, self._elegir_tema).pack(fill="x", padx=round(18 * escala), pady=(0, round(8 * escala)))
        texto_fluido(Texto(panel, t("apariencia_cerrado"), size=12, color=T.texto2, wraplength=760), panel, 36).pack(
            fill="x", padx=18, pady=(4, 16))

    def _elegir_tema(self, nombre):
        if nombre == T.nombre:
            return
        self._aplicar_tema(nombre)
        self._log_dev(t("tema_log"), "temas.aplicar", t("tema_aplicado", tema=t(NOMBRES_TEMA[T.nombre][0])),
                      seccion=t("seccion_ajustes"), exito=True)

    def _aplicar_tema(self, nombre):
        """Cambia de tema al momento: colores, letra, bordes y la forma de la
        barra lateral, y vuelve a dibujar la pantalla abierta. Las ventanas
        sueltas (el widget flotante, la consola) toman el tema al reabrirse."""
        nombre = temas.aplicar(nombre)
        temas.resolver_fuentes(self)
        _sincronizar_colores()
        ctk.set_widget_scaling(T.escala)
        self.prefs["tema"] = nombre
        prefs.guardar({"tema": nombre})
        self.configure(fg_color=T.fondo)
        self._construir_sidebar()
        getattr(self, self._pantalla_actual, self.mostrar_dashboard)()
        return nombre

    def _guardar_numero_pref(self, clave, valor):
        """Un número de Ajustes que el vigilante lee en cada vuelta: basta
        con guardarlo, no hay nada que reiniciar."""
        self.prefs[clave] = valor
        prefs.guardar({clave: valor})

    def _toggle_aviso(self, clave, switch):
        """Avisos del vigilante. El vigilante lee self.prefs en cada vuelta,
        así que basta con actualizarla: no hay nada que reiniciar."""
        activo = bool(switch.get())
        self.prefs[clave] = activo
        prefs.guardar({clave: activo})
        self._log_dev(t("ajustes_log_avisos"), "N/A",
                      t("ajustes_aviso_on") if activo else t("ajustes_aviso_off"),
                      seccion=t("seccion_ajustes"), exito=True)

    def _toggle_modo_ligero(self):
        activo = bool(self.switch_modo_ligero.get())
        self.prefs["modo_ligero"] = activo
        prefs.guardar({"modo_ligero": activo})
        self._aplicar_preferencia_animaciones()
        self._log_dev(t("ajustes_log_modo_ligero_on") if activo else t("ajustes_log_modo_ligero_off"),
                      "N/A", t("ajustes_modo_ligero_aplica"),
                      seccion=t("seccion_ajustes"), exito=True)

    def _toggle_auto_ram(self):
        activa = bool(self.switch_auto_ram.get())
        self.prefs["auto_ram_activa"] = activa
        prefs.guardar({"auto_ram_activa": activa})
        if activa:
            self.auto_ram.iniciar()
        else:
            self.auto_ram.detener()
        self._log_dev(t("ajustes_log_auto_ram"), "N/A",
                      t("ajustes_auto_ram_on") if activa else t("ajustes_auto_ram_off"),
                      seccion=t("seccion_ajustes"), exito=True)

    def _guardar_intervalo_ram(self, minutos):
        self.prefs["auto_ram_intervalo_min"] = minutos
        prefs.guardar({"auto_ram_intervalo_min": minutos})
        self.auto_ram.intervalo_min = minutos
        self._log_dev(t("ajustes_log_auto_ram"), "N/A",
                      t("ajustes_auto_ram_intervalo_msg", minutos=minutos) if minutos
                      else t("ajustes_auto_ram_solo_umbral"),
                      seccion=t("seccion_ajustes"), exito=True)

    def _guardar_umbral_ram(self, valor):
        self.prefs["umbral_ram_auto"] = valor
        prefs.guardar({"umbral_ram_auto": valor})
        # Se aplica de inmediato al autopilot que ya está corriendo, sin
        # tener que reiniciar la app — es un atributo simple, no hace
        # falta recrear el objeto entero.
        self.autopilot.umbral_ram = valor
        self.auto_ram.umbral_ram = valor
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
                     font=fuente(size=16, weight="bold")).pack(pady=(20, 4))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("diag_ejecutando"),
                                    font=fuente(size=11), text_color=T.texto2, wraplength=560,
                                    justify="center")
        lbl_estado.pack(padx=20, pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=fuente(family="Consolas", size=10))
        caja.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        caja.insert("1.0", t("diag_iniciando") + "\n")
        caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=(0, 16))
        btn_copiar = ctk.CTkButton(fila, text=t("comun_copiar_todo"), state="disabled")
        btn_copiar.pack(side="left", padx=6)
        ctk.CTkButton(fila, text=t("comun_cerrar"), fg_color=T.boton2,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=6)

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
                (t("diagp_apps_inicio"), lambda: opt.listar_inicio_completo()),
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
                     font=fuente(size=16, weight="bold")).pack(pady=(20, 4))
        lbl_estado = ctk.CTkLabel(dialogo, text=t("rend_reuniendo"), font=fuente(size=11),
                                    text_color=T.texto2)
        lbl_estado.pack(pady=(0, 10))
        caja = ctk.CTkTextbox(dialogo, font=fuente(family="Consolas", size=10))
        caja.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        caja.configure(state="disabled")
        fila = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila.pack(pady=(0, 16))
        btn_copiar = ctk.CTkButton(fila, text=t("comun_copiar_todo"), state="disabled")
        btn_copiar.pack(side="left", padx=6)
        ctk.CTkButton(fila, text=t("comun_cerrar"), fg_color=T.boton2,
                      command=dialogo.destroy, text_color=T.texto, hover_color=T.boton2_hover).pack(side="left", padx=6)

        def worker():
            cpu = sysmon.get_cpu_details(incluir_temperatura=True)
            ram = sysmon.get_ram_info()
            ram_sticks = sysmon.get_ram_sticks()
            canal = sysmon.estimar_canal_ram(ram_sticks) if ram_sticks else None
            disco = sysmon.get_disk_info()
            gpu = sysmon.get_gpu_info()
            try:
                apps_activas = opt.contar_inicio_activo()
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
                lbl_estado.configure(text=t("comun_listo"))
                btn_copiar.configure(state="normal", command=lambda: self._copiar_al_portapapeles(texto_final))
            self.after(0, _mostrar)
            self._log_dev(t("log_reporte_rendimiento"), "N/A", t("log_generado_ok"), seccion=t("seccion_ajustes"), exito=True)
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

    def _pintar_estado_inicio(self, activo, estado):
        """Pone el interruptor donde toca y avisa si la tarea no va a servir."""
        if not (hasattr(self, "switch_inicio") and self.switch_inicio.winfo_exists()):
            return
        if activo:
            self.switch_inicio.select()
        else:
            self.switch_inicio.deselect()

        if not (hasattr(self, "fila_aviso_inicio") and self.fila_aviso_inicio.winfo_exists()):
            return
        # Las claves se nombran enteras a propósito, sin construirlas
        # pegando trozos: verificar_idiomas.py no puede seguir una clave
        # armada al vuelo, y avisaría de que están sin usar.
        avisos = {
            "inicio_config_vieja": "ajustes_inicio_config_vieja",
            "inicio_ruta_vieja": "ajustes_inicio_ruta_vieja",
        }
        if estado in avisos:
            self.lbl_aviso_inicio.configure(text=_sin_emoji(t(avisos[estado])))
            self.fila_aviso_inicio.pack(fill="x", padx=72, pady=(0, 14))
        else:
            self.fila_aviso_inicio.pack_forget()

    def _arreglar_inicio_automatico(self):
        """Vuelve a crear la tarea con la definición buena. Es lo mismo que
        apagar y encender el interruptor, pero sin que el usuario tenga que
        adivinar que eso era la solución."""
        self.btn_arreglar_inicio.configure(state="disabled")

        def worker():
            exito, comando = opt.set_startup(True)
            estado = opt.diagnostico_inicio_automatico() if exito else None
            msg = t("ajustes_inicio_agregado") if exito else t("ajustes_inicio_error")
            self._log_dev(t("ajustes_log_inicio_auto"), comando, msg,
                          seccion=t("seccion_ajustes"), exito=exito)

            def despues():
                if hasattr(self, "btn_arreglar_inicio") and self.btn_arreglar_inicio.winfo_exists():
                    self.btn_arreglar_inicio.configure(state="normal")
                self._pintar_estado_inicio(True, estado)
                if not exito:
                    self._mostrar_popup_info(t("ajustes_inicio_windows_titulo"), msg)
            self.after(0, despues)
        threading.Thread(target=worker, daemon=True).start()

    def _toggle_inicio_automatico(self):
        # opt.set_startup() crea/borra una tarea programada con schtasks:
        # subproceso con hasta 10s de timeout, fuera del hilo de la interfaz.
        habilitar = bool(self.switch_inicio.get())

        def worker():
            exito, comando = opt.set_startup(habilitar)
            resultado = (t("ajustes_inicio_agregado") if habilitar else t("ajustes_inicio_quitado")) \
                if exito else t("ajustes_inicio_error")
            self._log_dev(t("ajustes_log_inicio_auto"), comando, resultado,
                          seccion=t("seccion_ajustes"), exito=exito)

            def revertir_si_fallo():
                # Si no se pudo aplicar, el switch vuelve a su estado real —
                # pero solo si Ajustes sigue en pantalla.
                if exito:
                    return
                if not (hasattr(self, "switch_inicio") and self.switch_inicio.winfo_exists()):
                    return
                if habilitar:
                    self.switch_inicio.deselect()
                else:
                    self.switch_inicio.select()
            self.after(0, revertir_si_fallo)
        threading.Thread(target=worker, daemon=True).start()

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
        ctk.CTkLabel(dialogo, text="🪿 HONK!", font=fuente(size=32, weight="bold")).pack(pady=(24, 6))
        ctk.CTkLabel(dialogo, text=t("huevo_texto"),
                     font=fuente(size=12), justify="center").pack(pady=6)
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
