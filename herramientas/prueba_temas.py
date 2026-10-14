# -*- coding: utf-8 -*-
"""Comprueba los temas de la interfaz (1.8.0).

Por que importa
---------------
  * Legibilidad: un tema con texto gris sobre gris o botones con letra
    casi del mismo color que el fondo no se nota programando, se nota
    usando la app. Aqui se mide el contraste (WCAG) de cada par que la
    interfaz usa, en los 9 temas.
  * Cerrados: el tema se elige de una lista que va dentro de la app. Un
    nombre raro en preferencias.json (editado a mano, o por un programa)
    tiene que caer en el de fabrica, nunca romper ni cargar nada de fuera.
  * Sin colores sueltos: si alguien vuelve a escribir "#2a2d36" o "gray60"
    a mano en main.py, esa parte ya no cambia con el tema. Se buscan.
  * Que cambiar de tema funcione en caliente: la barra lateral cambia de
    forma (Telemetria es una columna estrecha), la pantalla abierta se
    vuelve a dibujar y la eleccion se guarda.

La ventana va fuera de la pantalla: no se ve nada.

Uso:  python herramientas/prueba_temas.py
"""
import ast
import json
import os
import re
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_temas_")
os.environ["APPDATA"] = perfil
os.makedirs(os.path.join(perfil, "TechClean"), exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False, "ultima_version_vista": "9.9.9",
           "tema": "../../temas_de_fuera/malo"},
          open(os.path.join(perfil, "TechClean", "preferencias.json"), "w", encoding="utf-8"))

import _rutas
_rutas.poner_en_ruta()
import temas
import iconos

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== Cada tema trae todas sus fichas, con colores validos ==")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
for nombre in temas.ORDEN:
    f = temas.TEMAS[nombre]
    faltan = [k for k in temas.FICHAS if k not in f]
    malos = [k for k, v in f.items() if isinstance(v, str) and v.startswith("#") and not HEX.match(v)]
    comprobar(not faltan and not malos, f"{nombre}: completo ({len(f)} fichas)" +
              (f" FALTAN {faltan}" if faltan else "") + (f" MAL {malos}" if malos else ""))
comprobar(set(temas.ORDEN) == set(temas.TEMAS), "la lista de Ajustes y los temas definidos son los mismos")
comprobar(temas.POR_DEFECTO in temas.TEMAS, f"el de fabrica existe ({temas.POR_DEFECTO})")

print("== Contraste (WCAG): texto 4.5:1, graficos 3:1 ==")
TEXTO = [("texto", "fondo"), ("texto", "panel"), ("texto", "fila"), ("texto2", "panel"), ("texto2", "fila"),
         ("texto2", "fondo"), ("texto3", "panel"), ("texto3", "fondo"), ("texto", "boton2"),
         ("sobre_acento", "acento"), ("nav_activo_tx", "nav_activo_bg"), ("sobre_aviso", "aviso"),
         ("sobre_peligro", "peligro"), ("texto2", "lateral"), ("texto", "entrada")]
GRAFICOS = [("acento", "panel"), ("ok", "panel"), ("aviso", "panel"), ("critico", "panel")]
for nombre in temas.ORDEN:
    f = temas.TEMAS[nombre]
    malos = [f"{a}/{b}={temas.contraste(f[a], f[b]):.1f}" for a, b in TEXTO if temas.contraste(f[a], f[b]) < 4.5]
    malos += [f"{a}/{b}={temas.contraste(f[a], f[b]):.1f}" for a, b in GRAFICOS if temas.contraste(f[a], f[b]) < 3.0]
    comprobar(not malos, f"{nombre}: se lee bien" + (f"  -> {malos}" if malos else ""))

print("== Cerrado: un nombre que no esta en la lista no carga nada ==")
for raro in ("../../temas_de_fuera/malo", "", None, 123, "PULIDO", "C:\\tema.json"):
    comprobar(temas.nombre_valido(raro) == temas.POR_DEFECTO, f"{raro!r} -> el de fabrica")
comprobar(temas.aplicar("no_existe") == temas.POR_DEFECTO and temas.T.nombre == temas.POR_DEFECTO,
          "aplicar() con un nombre raro deja el de fabrica activo")

print("== Sin colores escritos a mano en main.py ==")
ruta_main = os.path.join(_rutas.RAIZ, "codigo", "main.py")
src = open(ruta_main, encoding="utf-8").read()
arbol = ast.parse(src)
COLOR = re.compile(r"^(#[0-9a-fA-F]{6}|gray\d+|white|black)$")
# La consola y su globito de ayuda son una terminal: oscuras en todos los
# temas a proposito. Y la tarjeta de donar lleva su propio color calido.
PERMITIDAS = {"_ConsolaBase", "DevConsole", "ComandoConsole", "_tooltip_ctk"}
zonas = set()
for nodo in arbol.body:
    if isinstance(nodo, (ast.ClassDef, ast.FunctionDef)) and nodo.name in PERMITIDAS:
        zonas.update(range(nodo.lineno, nodo.end_lineno + 1))
sueltos = []
for nodo in ast.walk(arbol):
    if isinstance(nodo, ast.Call) and nodo.lineno not in zonas:
        claves = {k.arg: k.value for k in nodo.keywords}
        donar = isinstance(claves.get("fg_color"), ast.Name) and claves["fg_color"].id == "COLOR_DONAR"
        for k in nodo.keywords:
            v = k.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and COLOR.match(v.value) and not donar:
                sueltos.append(f"linea {v.lineno}: {k.arg}={v.value}")
comprobar(not sueltos, f"ningun color suelto en los widgets ({len(sueltos)})" +
          ("".join(f"\n          {s}" for s in sueltos[:10])))

print("== Iconos: todos los que pide la interfaz existen ==")
pedidos = set(re.findall(r'iconos\.icono\("([a-z_]+)"', src))
pedidos |= set(re.findall(r'icono="([a-z_]+)"', src))
pedidos |= {m for m in re.findall(r'"nav_[a-z_]+", "nav_corto_[a-z_]+", "([a-z_]+)"', src)}
pedidos |= {m for m in re.findall(r'\(\s*"([a-z_]+)", t\("opt_btn', src)}
faltan = sorted(p for p in pedidos if p not in iconos.TRAZOS)
comprobar(not faltan, f"{len(pedidos)} iconos pedidos, todos dibujables" + (f" FALTAN {faltan}" if faltan else ""))
img = iconos.dibujar("inicio", "#ffffff", 18)
comprobar(img.size == (54, 54) and img.getbbox() is not None, "un icono se dibuja a 3x y no sale vacio")
comprobar(iconos.dibujar("no_existe", "#ffffff").getbbox() is None, "un icono que no existe sale vacio, sin reventar")

print("== La app: el tema raro de preferencias.json cae en el de fabrica ==")
import main
app = main.TechCleanApp()
app.geometry("1180x780+5000+5000")


def correr(seg):
    fin = time.time() + seg
    while time.time() < fin:
        app.update()
        time.sleep(0.01)


correr(1.5)
comprobar(temas.T.nombre == temas.POR_DEFECTO, f"arranca con el de fabrica ({temas.T.nombre})")
comprobar(main.COLOR_BG_PANEL == temas.T.panel and main.COLOR_OK == temas.T.ok,
          "los COLOR_* de main.py son los del tema")

print("== Cambiar de tema en caliente ==")
app.mostrar_drivers()
correr(0.5)
marcado = [m for m, b in app._nav_botones.items() if b["boton"].cget("fg_color") == temas.T.nav_activo_bg]
comprobar(marcado == ["mostrar_componentes"], f"en Drivers, la barra marca Componentes ({marcado})")
peor = 0
for nombre in temas.ORDEN:
    a = time.perf_counter()
    app._aplicar_tema(nombre)
    correr(0.2)
    peor = max(peor, time.perf_counter() - a)
    rail = all(b["rail"] for b in app._nav_botones.values())
    if nombre == "telemetria":
        comprobar(rail, "Telemetria: la barra es la columna estrecha")
    elif nombre == "claro":
        comprobar(not rail and app.cget("fg_color") in (temas.T.fondo, [temas.T.fondo] * 2, (temas.T.fondo,) * 2),
                  "Claro: barra normal y fondo claro")
comprobar(app._pantalla_actual == "mostrar_drivers", "tras cambiar de tema sigue en la misma pantalla")
comprobar(peor < 4, f"cambiar de tema tarda poco (peor: {peor:.2f} s)")
comprobar(main.prefs.cargar().get("tema") == temas.ORDEN[-1], "la eleccion se guarda en preferencias")

print("== Ajustes > Apariencia ==")
app._aplicar_tema("pulido")
app.mostrar_ajustes()
correr(0.5)
app._elegir_tema("bosque")
correr(0.3)
comprobar(temas.T.nombre == "bosque" and app._pantalla_actual == "mostrar_ajustes",
          "elegir una tarjeta cambia el tema y se queda en Ajustes")
ultima = app.reporte.entries[-1] if app.reporte.entries else {}
comprobar("Bosque" in str(ultima.get("resultado")), "el cambio queda en el Historial")

# Al pasar entre claro y oscuro, customtkinter devuelve el foco 1 ms despues
# a quien lo tenia. Si era un boton de la barra lateral (se reconstruye al
# cambiar de tema) saltaba "bad window path name" en el aviso de errores.
# Si salta o no depende de cuando corre ese 1 ms, y de que la ventana tenga
# el foco de Windows (mientras alguien usa el equipo, no siempre). Por eso
# customtkinter recibe aqui el foco que Tk recuerda para la ventana, y se
# mira a quien se lo va a devolver: que siga existiendo.
errores_tk, focos = [], []
despues = app.after


def anotar(ms, func=None, *args):
    if getattr(func, "__name__", "") in ("focus", "focus_set"):
        focos.append(func.__self__)
    return despues(ms, func, *args)


app.report_callback_exception = lambda tipo, valor, tb: errores_tk.append(f"{tipo.__name__}: {valor}")
app.focus_get = lambda: app.nametowidget(app.tk.call("focus", "-lastfor", app))
for nombre in ("claro", "oled", "claro"):
    app._nav_botones["mostrar_ajustes"]["boton"].focus_set()
    app.after = anotar
    app._aplicar_tema(nombre)
    del app.after
    correr(0.3)
del app.focus_get
del app.report_callback_exception
muertos = [str(w) for w in focos if not w.winfo_exists()]
comprobar(len(focos) == 3 and not muertos and not errores_tk,
          f"claro <-> oscuro con el foco en la barra lateral: se devuelve a algo que existe "
          f"({len(focos)} de 3, {muertos[:1]}, {errores_tk[:1]})")

print("== Textos largos: se parten al ancho de su caja ==")
app._aplicar_tema("claro")
app.mostrar_gaming()
correr(1.0)
cortados = []
pila = [app.contenido]
while pila:
    w = pila.pop()
    pila.extend(w.winfo_children())
    if isinstance(w, main.ctk.CTkLabel) and getattr(w, "_al_ancho", False) and w.winfo_ismapped():
        escala = main.ctk.ScalingTracker.get_widget_scaling(w)
        if w.winfo_reqwidth() > w.master.winfo_width() + 2:
            cortados.append((w.cget("text")[:30], w.winfo_reqwidth(), w.master.winfo_width()))
comprobar(not cortados, f"en Gaming ningun texto pide mas ancho que su caja ({len(cortados)})"
          + "".join(f"\n          {c}" for c in cortados[:5]))

print("== Rendimiento del rediseno (lo que lo hizo el doble de lento) ==")


def todos(raiz):
    pila, vistos = [raiz], []
    while pila:
        w = pila.pop()
        vistos.append(w)
        pila.extend(w.winfo_children())
    return vistos


# Textos: cada uno se ajusta a su caja UNA vez al abrir la pantalla. Antes
# pasaban por anchos intermedios (en Ajustes 800 -> 234 -> 729 -> 800) y dos
# ajustes se pisaban en Optimizar; cada cambio volvia a colocar y dibujar el
# panel entero.
cambios = {}
configurar = main.ctk.CTkLabel.configure


def contar(self, require_redraw=False, **kwargs):
    if "wraplength" in kwargs:
        cambios[id(self)] = cambios.get(id(self), 0) + 1
    return configurar(self, require_redraw, **kwargs)


main.ctk.CTkLabel.configure = contar
app._aplicar_tema("pulido")
for pantalla in ("mostrar_optimizador", "mostrar_ajustes", "mostrar_gaming"):
    cambios.clear()
    getattr(app, pantalla)()
    correr(1.0)
    peor = max(cambios.values(), default=0)
    comprobar(peor <= 1, f"{pantalla}: cada texto se ajusta como mucho una vez (peor: {peor}, {len(cambios)} textos)")
main.ctk.CTkLabel.configure = configurar

letras = len(app._fuentes_compartidas)
app.mostrar_optimizador()
correr(0.3)
comprobar(len(app._fuentes_compartidas) == letras,
          f"volver a abrir una pantalla no crea letras nuevas: se comparten ({letras} en total)")

app.mostrar_dashboard()
correr(1.0)
barras = [w for w in todos(app.contenido) if isinstance(w, main.ctk.CTkProgressBar)]
comprobar(not barras, "Inicio sin CTkProgressBar (~10 ms cada una, y se redibujaba en cada paso de la animacion)")

# Alto contraste agranda todo un 12 %: la galeria de temas se coloca primero
# con un ancho provisional y la ultima columna llego a quedar cortada.
app._aplicar_tema("alto_contraste")
app.mostrar_ajustes()
correr(1.0)
galerias = [w for w in todos(app.contenido) if isinstance(w, main.GaleriaTemas)]
fuera = [nombre for g in galerias for nombre, fondo, _ in g._tarjetas
         if g.bbox(fondo)[2] > g.winfo_width() + 2 or g.bbox(fondo)[3] > g.winfo_height() + 2]
comprobar(len(galerias) == 1 and not fuera,
          f"Alto contraste: las {len(temas.ORDEN)} tarjetas de temas caben en la galeria" +
          (f" FUERA {fuera}" if fuera else ""))

app.destroy()
print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
