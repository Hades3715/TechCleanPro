# -*- coding: utf-8 -*-
"""Comprueba que las barras animan de verdad: captura cada valor intermedio
que se dibuja, sin mostrar ninguna ventana."""
import os, sys, json, tempfile, time

perfil = tempfile.mkdtemp(prefix="tcp_anim_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechCleanPro")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

sys.path.insert(0, ".")
import customtkinter as ctk
import main, widget as widget_mod

root = ctk.CTk()
root.withdraw()

# ---------------- Gauge de Inicio ----------------
g = main.Gauge(root, "CPU")
g.pack()
root.update()

capturas = []
original = g._dibujar
g._dibujar = lambda v: (capturas.append(round(v, 1) if v is not None else None), original(v))[1]

print("== Gauge: 0% -> 80%, con animacion ==")
main.ANIMAR_BARRAS = True
g.set_value(80, "prueba")
inicio = time.time()
while g._anim_id is not None and time.time() - inicio < 3:
    root.update()
    time.sleep(0.005)
print(f"  cuadros dibujados: {len(capturas)}")
print(f"  recorrido: {capturas[:5]} ... {capturas[-3:]}")
crece = all(b >= a for a, b in zip(capturas, capturas[1:]))
print(f"  monotono (nunca retrocede): {crece}")
print(f"  termina exacto en 80: {capturas[-1] == 80.0}")

capturas.clear()
print("== Gauge: 80% -> 20%, SIN animacion (Modo Ligero) ==")
main.ANIMAR_BARRAS = False
g.set_value(20, "prueba")
root.update()
print(f"  cuadros dibujados: {len(capturas)} (debe ser 1)  valores: {capturas}")

capturas.clear()
main.ANIMAR_BARRAS = True
print("== Gauge: valor None (N/D) no revienta ==")
g.set_value(None, "sin dato")
root.update()
print(f"  valores: {capturas}")

capturas.clear()
print("== Gauge: dos cambios seguidos no dejan animaciones pisadas ==")
g.set_value(10)
g.set_value(90)
inicio = time.time()
while g._anim_id is not None and time.time() - inicio < 3:
    root.update()
    time.sleep(0.005)
print(f"  termina en: {capturas[-1]} (esperado 90.0)")

# ---------------- _MiniBarra del widget ----------------
b = widget_mod._MiniBarra(root, ancho=64)
b.pack()
root.update()
caps_b = []
orig_b = b._dibujar
b._dibujar = lambda v, c=None: (caps_b.append(round(v, 1)), orig_b(v, c))[1]

print("== _MiniBarra: 0% -> 65% ==")
widget_mod.ANIMAR_BARRAS = True
b.set_valor(65)
inicio = time.time()
while b._anim_id is not None and time.time() - inicio < 3:
    root.update()
    time.sleep(0.005)
print(f"  cuadros: {len(caps_b)} | recorrido: {caps_b[:4]} ... {caps_b[-2:]}")
print(f"  termina exacto en 65: {caps_b[-1] == 65.0}")

# ---------------- destruir a media animacion no revienta ----------------
print("== destruir a media animacion ==")
b2 = widget_mod._MiniBarra(root, ancho=64)
b2.pack()
root.update()
b2.set_valor(100)
root.update()
b2.destroy()
for _ in range(40):
    root.update()
    time.sleep(0.01)
print("  sin excepciones tras destruir con animacion en curso")

root.destroy()
print("\nOK: animacion verificada")
