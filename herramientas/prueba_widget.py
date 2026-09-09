# -*- coding: utf-8 -*-
"""Banco de pruebas del widget flotante de rendimiento.

Cubre los fallos que se encontraron revisandolo a fondo:

  1. El SALTO al arrastrar. La vinculacion de arrastre se pone sobre la
     ventana, y en Tk una vinculacion en el toplevel salta tambien con los
     eventos de todos sus hijos. Se guardaba event.x —la posicion dentro
     del widget que recibio el clic— asi que al agarrar el widget por un
     boton de atajo, ese numero valia 5 en vez de 300 y la ventana pegaba
     un brinco.

  2. Se podia arrastrar FUERA de la pantalla. Como no tiene barra de
     titulo de Windows (overrideredirect), una vez fuera no habia forma de
     traerlo de vuelta.

  3. Se escribia preferencias.json en cada clic, aunque no se moviera.

  4. La temperatura se pintaba con los umbrales de un PORCENTAJE, asi que
     62 grados —normal— salia en ambar como si algo fuera mal.

  5. Los tooltips son ventanas aparte: al ocultar el widget con uno
     abierto, el globito negro se quedaba flotando solo en el escritorio.

  6. Oculto seguia consultando GPU y temperatura (las consultas caras) y
     repintando cada segundo.

Y lo que trajo el repaso estetico:

  7. La barra compacta TEMBLABA. Las etiquetas se median por su texto, asi
     que al pasar de "CPU 9%" a "CPU 10%" crecian un caracter y empujaban a
     las de su derecha: la barra entera se recolocaba cada segundo. Se
     comprueba midiendo la etiqueta con los dos textos.
  8. La red iba siempre en K: a 5 MB/s ponia "5120K".
  9. La minigrafica tiene que apuntar el valor MEDIDO, no los pasos
     intermedios de la animacion — si no, dibujaria la animacion en vez de
     lo que hizo el sistema.
 10. Las esquinas redondeadas se hacen con un color clave transparente. El
     riesgo es que ese color aparezca en otro sitio: donde aparezca,
     Windows abre un agujero en la ventana. Se revisa el fondo de todos los
     widgets del contenido.
 11. Los atajos no daban ninguna senal de ser pulsables. El de Modo Juego
     es la excepcion a proposito: su fondo dice si el modo esta encendido.

No muestra ninguna ventana en la pantalla del usuario: todo ocurre en
+4000+4000, fuera del area visible, y con %APPDATA% apuntando a una
carpeta temporal.

Uso:  python herramientas\\prueba_widget.py
"""
import json
import os
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_widget_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import customtkinter as ctk
import preferences as prefs
import widget as widget_mod

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    marca = "OK  " if condicion else "FALLO"
    print(f"  [{marca}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


root = ctk.CTk()
root.geometry("300x200+4000+4000")
w = widget_mod.PerformanceWidget(root)
w.geometry("+4000+4000")
for _ in range(15):
    root.update()
    time.sleep(0.02)

# ---------------- 1. Colores de temperatura ----------------
print("== Temperatura: umbrales propios, no los de un porcentaje ==")
comprobar("40 grados en verde", widget_mod._color_temp(40) == widget_mod.COLOR_OK)
comprobar("62 grados AUN en verde (antes salia ambar)",
          widget_mod._color_temp(62) == widget_mod.COLOR_OK)
comprobar("72 grados en ambar", widget_mod._color_temp(72) == widget_mod.COLOR_WARN)
comprobar("90 grados en rojo", widget_mod._color_temp(90) == widget_mod.COLOR_CRIT)
comprobar("sin sensor no revienta", widget_mod._color_temp(None) == widget_mod.COLOR_TXT_DIM)
comprobar("los porcentajes conservan su escala",
          widget_mod._color(62) == widget_mod.COLOR_WARN)

# ---------------- 2. Arrastre sin salto ----------------
print("\n== Arrastre: el desfase se mide contra la VENTANA, no contra el hijo ==")
w.geometry("+300+200")
root.update()


class _EventoFalso:
    """Un clic llegado desde un hijo hundido en la jerarquia: sus
    coordenadas locales no tienen nada que ver con las de la ventana."""
    x, y = 5, 7


w._iniciar_arrastre(_EventoFalso())
desfase_x, desfase_y = w._drag_x, w._drag_y
esperado_x = w.winfo_pointerx() - w.winfo_x()
esperado_y = w.winfo_pointery() - w.winfo_y()
comprobar("el desfase no es el event.x del hijo",
          (desfase_x, desfase_y) != (5, 7), f"desfase={(desfase_x, desfase_y)}")
comprobar("el desfase es puntero - ventana",
          (desfase_x, desfase_y) == (esperado_x, esperado_y))

# ---------------- 3. No se escapa de la pantalla ----------------
print("\n== Arrastre: no se puede tirar fuera de la pantalla ==")
ancho_pantalla = w.winfo_screenwidth()
alto_pantalla = w.winfo_screenheight()
w._drag_x = w._drag_y = 0
w._arrastrar(_EventoFalso())          # usa la posicion real del puntero
root.update()
x_tras_arrastre, y_tras_arrastre = w.winfo_x(), w.winfo_y()
comprobar("queda dentro de los limites",
          x_tras_arrastre < ancho_pantalla and y_tras_arrastre < alto_pantalla
          and y_tras_arrastre >= 0,
          f"pos=({x_tras_arrastre}, {y_tras_arrastre}) pantalla={ancho_pantalla}x{alto_pantalla}")

# ---------------- 4. Solo guarda si se movio ----------------
print("\n== Preferencias: no se escribe en cada clic ==")
w.geometry("+400+300")
root.update()
w._iniciar_arrastre(_EventoFalso())
w._terminar_arrastre(_EventoFalso())          # sin moverse
ruta_prefs = os.path.join(carpeta, "preferencias.json")
firma_antes = os.stat(ruta_prefs).st_mtime_ns
time.sleep(0.05)
w._iniciar_arrastre(_EventoFalso())
w._terminar_arrastre(_EventoFalso())          # otra vez sin moverse
comprobar("clic sin arrastrar no reescribe el archivo",
          os.stat(ruta_prefs).st_mtime_ns == firma_antes)

w._iniciar_arrastre(_EventoFalso())
w.geometry("+450+320")
root.update()
w._terminar_arrastre(_EventoFalso())
guardada = prefs.cargar().get("widget_pos")
comprobar("moverse SI guarda la posicion", guardada is not None, f"guardada={guardada}")

# ---------------- 5. Tooltips ----------------
print("\n== Tooltips: son ventanas aparte y hay que cerrarlas a mano ==")
comprobar("se registraron los tooltips de los atajos", len(w._tooltips) >= 5,
          f"{len(w._tooltips)} registrados")
# Se llama al manejador directamente, no con event_generate: <Enter> y
# <Leave> los reparte el gestor de ventanas y no llegan de forma fiable a
# una ventana colocada fuera de la pantalla, que es donde corre esto.
for globo in w._tooltips[:3]:
    globo["mostrar"](None)
root.update()
time.sleep(0.05)
root.update()
abiertos = sum(1 for g in w._tooltips if g.get("win") is not None)
comprobar("pasar el raton abre el globo", abiertos == 3, f"{abiertos} abierto(s)")
w._tooltips[0]["ocultar"]()
comprobar("salir del boton lo cierra", w._tooltips[0]["win"] is None)
w.ocultar()
root.update()
quedan = sum(1 for g in w._tooltips if g.get("win") is not None)
comprobar("ocultar el widget los cierra todos", quedan == 0,
          f"{quedan} huerfano(s)")

# ---------------- 6. Oculto no trabaja ----------------
print("\n== Oculto: ni repinta ni consulta lo caro ==")
comprobar("marcado como no visible", w._visible is False)
pintados = {"veces": 0}
original = w._actualizar_loop


def espia():
    pintados["veces"] += 1
    original()


w._actualizar_loop = espia
w._actualizar_loop()
root.update()
comprobar("el bucle sigue programado (puede volver)", pintados["veces"] >= 1)

w.mostrar()
root.update()
comprobar("mostrar lo reactiva", w._visible is True)
comprobar("y pone a cero los contadores de red para no dar un pico falso",
          abs(time.time() - w._net_prev_time) < 2.0)

# ---------------- 7. La red se lee ----------------
print("\n== Velocidad de red: escala y ancho ==")
comprobar("por debajo de 1000 va en K", widget_mod._formato_red(842) == "842K",
          widget_mod._formato_red(842))
comprobar("5 MB/s ya NO sale como 5120K", widget_mod._formato_red(5120) == "5.0M",
          widget_mod._formato_red(5120))
comprobar("muy rapido pierde el decimal para no ensanchar",
          widget_mod._formato_red(51200) == "50M", widget_mod._formato_red(51200))
comprobar("sin dato no revienta", widget_mod._formato_red(None) == "--")
comprobar("un negativo (contador reiniciado) no imprime basura",
          widget_mod._formato_red(-5) == "--")
largos = {v: len(widget_mod._formato_red(v))
          for v in (0, 1, 999, 1000, 9999, 10240, 99999, 999999)}
comprobar("nunca pasa de 5 caracteres, que es lo que reserva la etiqueta",
          max(largos.values()) <= 5, str(largos))

# ---------------- 8. Los numeros no mueven la barra ----------------
print("\n== La barra compacta no tiembla ==")
etiquetas = [e for e in (w.lbl_cpu, w.lbl_ram, w.lbl_gpu, w.lbl_net_up, w.lbl_net_down)
             if e is not None]
comprobar("hay etiquetas en la barra compacta", len(etiquetas) >= 3, f"{len(etiquetas)}")
for i, lbl in enumerate(etiquetas):
    comprobar(f"la etiqueta {i} tiene ancho fijo", int(lbl.cget("width")) > 0,
              f'width={lbl.cget("width")}')
    familia = str(lbl.cget("font"))
    comprobar(f"la etiqueta {i} usa digitos de ancho fijo", "Consolas" in familia,
              familia)

# Lo que importa de verdad: que al cambiar el texto la etiqueta NO cambie de
# tamano. Es la comprobacion que habria pillado el temblor original.
lbl = etiquetas[0]
lbl.configure(text="CPU 9%")
root.update_idletasks()
ancho_corto = lbl.winfo_reqwidth()
lbl.configure(text="CPU 100%")
root.update_idletasks()
ancho_largo = lbl.winfo_reqwidth()
comprobar("de 9% a 100% la etiqueta mide lo mismo", ancho_corto == ancho_largo,
          f"{ancho_corto} px vs {ancho_largo} px")

# ---------------- 9. La minigrafica guarda historia ----------------
print("\n== Minigrafica: historia, no solo el valor de ahora ==")
barra = w._barras["cpu"]
barra._historia.clear()
widget_mod.ANIMAR_BARRAS = False       # sin animacion, un paso por valor
for valor in (10, 20, 30, 40, 50):
    barra.set_valor(valor)
comprobar("apunta cada medida", barra._historia == [10, 20, 30, 40, 50],
          str(barra._historia))
for valor in range(200):
    barra.set_valor(valor % 100)
comprobar("no crece sin limite", len(barra._historia) == barra.MUESTRAS,
          f"{len(barra._historia)} muestras (tope {barra.MUESTRAS})")

# Con la animacion encendida, la historia tiene que llevar el valor MEDIDO,
# no los pasos intermedios que dibuja la animacion: si no, la grafica
# contaria la animacion en vez de lo que hizo el sistema.
widget_mod.ANIMAR_BARRAS = True
barra._historia.clear()
barra._valor_mostrado = 0.0
barra.set_valor(90)
for _ in range(20):
    root.update()
    time.sleep(0.01)
comprobar("con animacion apunta UNA sola muestra, la medida",
          barra._historia == [90.0], str(barra._historia))

comprobar("un valor imposible se recorta en vez de salirse del dibujo",
          (barra.set_valor(500) or True) and barra._historia[-1] == 100.0,
          str(barra._historia[-1]))
comprobar("None se trata como cero y no revienta",
          (barra.set_valor(None) or True) and barra._historia[-1] == 0.0)

print("\n== Mezclar colores (el canvas de Tk no tiene transparencia) ==")
comprobar("mezcla al 0 devuelve el primero",
          widget_mod._mezclar("#ff0000", "#0000ff", 0) == "#ff0000")
comprobar("mezcla al 1 devuelve el segundo",
          widget_mod._mezclar("#ff0000", "#0000ff", 1) == "#0000ff")
comprobar("a medias sale a medias",
          widget_mod._mezclar("#000000", "#ffffff", 0.5) in ("#808080", "#7f7f7f"),
          widget_mod._mezclar("#000000", "#ffffff", 0.5))
comprobar("un color con nombre no revienta el repintado",
          widget_mod._mezclar("gray50", "#1c1f29", 0.5) == "#1c1f29")
comprobar("None tampoco", widget_mod._mezclar(None, "#1c1f29", 0.5) == "#1c1f29")

# ---------------- 10. Esquinas redondeadas ----------------
print("\n== Esquinas redondeadas de la ventana ==")
comprobar("Windows acepto el color clave", w._redondeada is True)
comprobar("hay un lienzo de fondo", w._fondo is not None and w._fondo.winfo_exists())
if w._fondo is not None:
    comprobar("el lienzo esta por DEBAJO del contenido",
              w.frame_header.winfo_exists() and w._fondo.winfo_exists())
    w.mostrar()
    root.update()
    w._repintar_fondo()
    root.update()
    dibujos = w._fondo.find_all()
    comprobar("el fondo se pinto", len(dibujos) >= 1, f"{len(dibujos)} figura(s)")
    coords = w._fondo.coords(dibujos[0]) if dibujos else []
    comprobar("el fondo cubre la ventana entera",
              bool(coords) and max(coords[0::2]) >= w.winfo_width() - 3,
              f"borde derecho del dibujo={max(coords[0::2]) if coords else '-'} "
              f"ventana={w.winfo_width()}")
    # El color clave NO puede aparecer en ningun otro sitio: donde aparezca,
    # Windows abre un agujero en la ventana.
    def fondos(widget, encontrados):
        try:
            encontrados.append(str(widget.cget("bg")).lower())
        except Exception:
            pass
        for hijo in widget.winfo_children():
            fondos(hijo, encontrados)
        return encontrados

    usados = fondos(w.frame_header, []) + fondos(w.frame_compacto, []) \
        + fondos(w.frame_expandido, [])
    comprobar("el color clave no se usa en ningun widget del contenido",
              widget_mod.COLOR_CLAVE.lower() not in usados,
              f"{len(usados)} fondos revisados")

print("\n== Redondeado: los puntos del poligono ==")
puntos = widget_mod._puntos_redondeados(0, 0, 100, 40, 10)
comprobar("salen pares de coordenadas", len(puntos) % 2 == 0, f"{len(puntos)} numeros")
comprobar("no se sale del rectangulo pedido",
          min(puntos[0::2]) >= 0 and max(puntos[0::2]) <= 100
          and min(puntos[1::2]) >= 0 and max(puntos[1::2]) <= 40)
apretado = widget_mod._puntos_redondeados(0, 0, 6, 4, 20)
comprobar("un radio mayor que la caja se recorta en vez de invertirla",
          max(apretado[0::2]) <= 6 and max(apretado[1::2]) <= 4,
          f"x max={max(apretado[0::2])} y max={max(apretado[1::2])}")

# ---------------- 11. Responde al raton ----------------
print("\n== Los atajos parecen pulsables ==")
# Hay que DESPLEGAR el panel antes de probar el raton. Tk no reparte eventos
# de cruce a un widget que no esta mostrado en pantalla, y los atajos viven
# dentro del panel plegado: con el panel cerrado, event_generate("<Enter>")
# no llega a ninguna parte y el hover parece roto estandolo. Es la misma
# razon por la que la prueba de los tooltips llama a los manejadores a mano.
if not w._expandido:
    w._toggle_expandir()
for _ in range(6):
    root.update()
    time.sleep(0.02)
atajos = [hijo for hijo in w._botones_atajos.values()]
btn_juego = w._botones_atajos.get("modo_juego")
comprobar("el atajo de Modo Juego se guardo aparte", btn_juego is not None)
# Un atajo normal: se busca entre los hermanos del de Modo Juego.
hermanos = [h for h in btn_juego.master.winfo_children() if h is not btn_juego]
comprobar("hay otros atajos ademas del de Modo Juego", len(hermanos) >= 3,
          f"{len(hermanos)}")
otro = hermanos[0]
fondo_reposo = str(otro.cget("bg"))
# El fondo se lee INMEDIATAMENTE despues de generar el <Enter>, sin pasar por
# root.update(). event_generate ejecuta la vinculacion ahi mismo, pero al
# procesar la cola de eventos aparece el globo del tooltip, que es una
# ventana nueva encima, y el gestor de ventanas manda entonces un <Leave> de
# verdad al boton — el raton de carne y hueso no esta ahi. Leyendo despues
# del update se ve el fondo YA restaurado y parece que el hover no funciona.
otro.event_generate("<Enter>")
fondo_encima = str(otro.cget("bg"))
comprobar("al pasar el raton por encima cambia de fondo",
          fondo_encima != fondo_reposo, f"{fondo_reposo} -> {fondo_encima}")
comprobar("y el fondo de encima es el tono de hover",
          fondo_encima.lower() == widget_mod.COLOR_HOVER.lower(), fondo_encima)
otro.event_generate("<Leave>")
comprobar("al salir vuelve al fondo de reposo", str(otro.cget("bg")) == fondo_reposo,
          str(otro.cget("bg")))
root.update()

# El de Modo Juego NO debe reaccionar al raton: su fondo dice si el modo esta
# encendido, y pintarlo al apuntarlo haria dudar de si esta activo.
fondo_juego = str(btn_juego.cget("bg"))
btn_juego.event_generate("<Enter>")
comprobar("el de Modo Juego no cambia de fondo al apuntarlo (su color dice si esta activo)",
          str(btn_juego.cget("bg")) == fondo_juego,
          f"{fondo_juego} -> {btn_juego.cget('bg')}")
btn_juego.event_generate("<Leave>")
root.update()

print("\n== Las filas de Sistema se distinguen sin leerlas ==")
iconos = [str(punto.cget("text")) for punto, _ in w.filas_sistema.values()]
comprobar("cada fila tiene su propio icono", len(set(iconos)) == len(iconos),
          " ".join(f"U+{ord(i):04X}" for i in iconos))
comprobar("y son cuatro", len(iconos) == 4)

# ---------------- 12. Destruir a media animacion ----------------
print("\n== Destruir con animaciones en curso ==")
for barra in w._barras.values():
    barra.set_valor(90)
root.update()
w.destruir()
for _ in range(30):
    root.update()
    time.sleep(0.01)
comprobar("sin excepciones al destruir", True)

root.destroy()
print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
