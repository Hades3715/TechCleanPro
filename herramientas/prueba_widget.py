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

# ---------------- 7. Destruir a media animacion ----------------
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
