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


# ---------------- Sparkline del panel principal ----------------
print("== Sparkline: el punto nuevo entra deslizandose ==")
main.ANIMAR_BARRAS = True
sp = main.Sparkline(root, "RAM")
sp.pack(fill="x", expand=True)
root.update()
for v in (40, 42, 41):          # tres valores para llenar el historial
    sp.agregar_valor(v)
    while sp._anim_id is not None:
        root.update(); time.sleep(0.005)

fotos = []
dibujar_orig = sp._dibujar
sp._dibujar = lambda: (fotos.append(round(sp._t, 3)), dibujar_orig())[1]
sp.agregar_valor(75)
inicio = time.time()
while sp._anim_id is not None and time.time() - inicio < 3:
    root.update(); time.sleep(0.005)
print(f"  cuadros dibujados: {len(fotos)}")
print(f"  avance: {fotos[:4]} ... {fotos[-2:]}")
print(f"  termina en su sitio (t=1): {fotos[-1] == 1.0}")
print(f"  guarda un punto de mas del maximo: {len(sp.valores)} <= {sp.max_puntos + 1}")
sp._dibujar = dibujar_orig

print("== Sparkline: se estira con el panel (era ancho fijo de 260) ==")
# Hace falta una ventana de verdad: una retirada con withdraw() no calcula
# geometria, asi que el canvas se quedaria en su tamano de arranque y la
# prueba diria que no se estira aunque si lo haga. Se abre fuera de la
# pantalla para no molestar a nadie mientras corre el banco.
vent = ctk.CTkToplevel(root)
vent.geometry("900x200+4000+4000")
sp_ancha = main.Sparkline(vent, "RAM")
sp_ancha.pack(fill="x", expand=True, padx=20)
for _ in range(10):
    root.update(); time.sleep(0.02)
ancho_grande = sp_ancha.ancho
vent.geometry("500x200+4000+4000")
for _ in range(10):
    root.update(); time.sleep(0.02)
ancho_chico = sp_ancha.ancho
vent.destroy()
print(f"  ancho con la ventana grande: {ancho_grande} | encogida: {ancho_chico}")
print(f"  sigue al panel (antes era siempre 260): {ancho_grande > 600 and ancho_chico < ancho_grande}")

print("== Sparkline: valor None no revienta ni ensucia el historial ==")
antes = len(sp.valores)
sp.agregar_valor(None)
print(f"  puntos antes={antes} despues={len(sp.valores)} (deben ser iguales)")

print("== Sparkline: destruir a media animacion ==")
sp2 = main.Sparkline(root, "CPU")
sp2.pack()
root.update()
for v in (10, 20, 30):
    sp2.agregar_valor(v)
root.update()
sp2.destroy()
for _ in range(40):
    root.update(); time.sleep(0.01)
print("  sin excepciones")

# ---------------- Medidor de aguja (prueba de internet) ----------------
print("== MedidorAguja: escala logaritmica y aguja animada ==")
med = main.MedidorAguja(root)
med.pack()
root.update()
f0 = med._fraccion(0); f10 = med._fraccion(10); f100 = med._fraccion(100)
print(f"  fraccion 0={f0:.3f}  10={f10:.3f}  100={f100:.3f}")
print(f"  0 al principio y 1000 al final: {abs(f0) < 0.001 and abs(med._fraccion(1000) - 1) < 0.001}")
print(f"  las decadas quedan repartidas parejo: {abs((f100 - f10) - f10) < 0.05}")
print(f"  pasarse de la escala no la rompe: {med._fraccion(99999) <= 1.0}")

pasos_aguja = []
dib = med._dibujar
med._dibujar = lambda: (pasos_aguja.append(round(med._valor, 2)), dib())[1]
med.set_valor(120)
inicio = time.time()
while med._anim_id is not None and time.time() - inicio < 3:
    root.update(); time.sleep(0.005)
print(f"  cuadros: {len(pasos_aguja)} | recorrido: {pasos_aguja[:3]} ... {pasos_aguja[-2:]}")
print(f"  termina exacto en 120: {pasos_aguja[-1] == 120.0}")
med._dibujar = dib

# ---------------- Tarjetas de resultado ----------------
print("== TarjetaMedicion: el numero sube desde cero ==")
tarj = main.TarjetaMedicion(root, "v", "Bajada", "Mbps", main.COLOR_ACCENT)
tarj.pack()
root.update()
tarj.set_valor(78.63)
inicio = time.time()
while tarj._anim_id is not None and time.time() - inicio < 3:
    root.update(); time.sleep(0.005)
print(f"  valor final mostrado: {tarj.lbl_valor.cget('text')} (esperado 78.63)")
tarj.limpiar()
print(f"  tras limpiar: {tarj.lbl_valor.cget('text')}")
tarj.set_valor(None)
print(f"  set_valor(None) no revienta: {tarj.lbl_valor.cget('text')}")

# ---------------- Barra de progreso animada ----------------
print("== animar_progreso: la barra no salta ==")
barra = ctk.CTkProgressBar(root, width=200)
barra.pack()
root.update()
estado = {"valor": 0.0, "id": None}
main.animar_progreso(barra, 0.8, estado)
inicio = time.time()
while estado["id"] is not None and time.time() - inicio < 3:
    root.update(); time.sleep(0.005)
print(f"  termina en {estado['valor']:.2f} (esperado 0.80)")
main.animar_progreso(barra, 0.3, estado)
main.animar_progreso(barra, 1.0, estado)     # un destino nuevo pisa al anterior
inicio = time.time()
while estado["id"] is not None and time.time() - inicio < 3:
    root.update(); time.sleep(0.005)
print(f"  dos destinos seguidos terminan en {estado['valor']:.2f} (esperado 1.00)")

root.destroy()
print("\nOK: animacion verificada")
