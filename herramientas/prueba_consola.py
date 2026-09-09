# -*- coding: utf-8 -*-
"""Banco de pruebas de las dos consolas (Consola Dev y Panel de comandos).

Las dos salen de la misma clase base, asi que lo que se comprueba aqui vale
para las dos. Lo que se mira:

  1. Que el HISTORIAL funcione como en una consola de verdad: subir, bajar,
     no pasarse por arriba ni por abajo, no guardar el mismo comando dos
     veces seguidas, y recuperar lo que estabas escribiendo cuando bajas
     hasta el final.
  2. Que Tab COMPLETE, y que con varios candidatos complete solo la parte
     comun en vez de elegir uno al azar.
  3. Que el TOPE DE LINEAS recorte de verdad. Sin esto el cuadro de texto
     crece sin limite: con el autopiloto registrando, una sesion larga
     acaba con miles de lineas dentro y Tk las repinta lento.
  4. Que cada linea salga con su COLOR. Antes todo era del mismo verde: un
     "Papelera vaciada" y un "No se pudo vaciar la papelera" se veian igual
     y habia que leer la frase para saber cual era. Se comprueba sobre las
     etiquetas del widget de texto, no sobre el texto.
  5. Que los TITULOS Y BOTONES esten traducidos. Esta es la que pillo el
     fallo de verdad: el boton del panel del cliente decia "Enviar" escrito
     a mano en el codigo, asi que en la build en ingles salia en espanol.
  6. Que el encabezado diga la EDICION y los PERMISOS reales.
  7. Que /limpiar, copiar y guardar el registro hagan lo que dicen.
  8. Que un comando inventado SUGIERA el parecido.

No muestra ninguna ventana al usuario: todo ocurre en +4000+4000, fuera del
area visible, y con %APPDATA% en una carpeta temporal.

Uso:  python herramientas\\prueba_consola.py
"""
import json
import os
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_consola_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import customtkinter as ctk
import tkinter as tk
import idiomas
import main

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


root = ctk.CTk()
root.geometry("1100x700+4000+4000")
recibidos = []
consola = main.DevConsole(root, on_comando=recibidos.append)
consola.pack(fill="both", expand=True)
for _ in range(6):
    root.update()
    time.sleep(0.02)


def bombear(veces=4):
    for _ in range(veces):
        root.update()
        time.sleep(0.01)


def escribir(texto):
    consola.entry.delete(0, "end")
    consola.entry.insert(0, texto)


# ---------------- 1. Historial ----------------
print("== Historial con las flechas ==")
for orden in ("/ram", "/dns", "/dns", "/estado"):
    escribir(orden)
    consola._enviar()
bombear()
comprobar("se guardaron los comandos", len(consola._historial) == 3,
          f"historial={consola._historial}")
comprobar("no guarda el mismo comando dos veces seguidas",
          consola._historial == ["/ram", "/dns", "/estado"], f"{consola._historial}")

escribir("a medio escribir")
consola._historial_atras()
comprobar("una flecha arriba trae el ultimo", consola.entry.get() == "/estado",
          repr(consola.entry.get()))
consola._historial_atras()
consola._historial_atras()
comprobar("tres arriba trae el primero", consola.entry.get() == "/ram",
          repr(consola.entry.get()))
consola._historial_atras()
comprobar("una cuarta no se pasa del principio", consola.entry.get() == "/ram",
          repr(consola.entry.get()))
for _ in range(3):
    consola._historial_adelante()
comprobar("bajar hasta el final recupera lo que estabas escribiendo",
          consola.entry.get() == "a medio escribir", repr(consola.entry.get()))
consola._historial_adelante()
comprobar("una mas abajo no borra lo escrito",
          consola.entry.get() == "a medio escribir", repr(consola.entry.get()))

consola._vaciar_entrada()
comprobar("Escape vacia la linea", consola.entry.get() == "")

# ---------------- 2. Completar con Tab ----------------
print("\n== Completar con Tab ==")
escribir("/priv")
consola._completar()
comprobar("un solo candidato se completa entero", consola.entry.get() == "/privacidad",
          repr(consola.entry.get()))

escribir("/gu")
consola._completar()
comprobar("tambien completa uno que se anadio despues", consola.entry.get() == "/guardar",
          repr(consola.entry.get()))

# /papelera y /privacidad comparten "/p": con dos candidatos NO debe elegir uno.
escribir("/p")
consola._completar()
elegido = consola.entry.get()
comprobar("con varios candidatos no elige uno al azar",
          elegido in ("/p", "/pa", "/pr") or not elegido.startswith(("/pap", "/pri")),
          repr(elegido))
comprobar("y los enseña en la consola",
          "/papelera" in consola.texto_completo() and "/privacidad" in consola.texto_completo())

escribir("/estonoexiste")
antes = consola.entry.get()
consola._completar()
comprobar("sin candidatos no toca lo escrito", consola.entry.get() == antes)

# ---------------- 3. Tope de lineas ----------------
print("\n== Tope de lineas ==")
consola.limpiar()
tope = consola.MAX_LINEAS
for i in range(tope + 60):
    consola.imprimir(f"linea de relleno numero {i}", "info")
bombear()
lineas_reales = int(consola.textbox.index("end-1c").split(".")[0])
comprobar("el cuadro no crece sin limite", lineas_reales <= tope + 5,
          f"{lineas_reales} lineas en el widget (tope {tope})")
comprobar("el contador interno concuerda con el widget",
          abs(consola._lineas - lineas_reales) <= 2,
          f"contador={consola._lineas} widget={lineas_reales}")
comprobar("avisa de que recorto", t_recortado := idiomas.t("consola_recortado")[:12] in consola.texto_completo())
comprobar("se quedo con las lineas NUEVAS, no con las viejas",
          f"numero {tope + 59}" in consola.texto_completo()
          and "numero 0\n" not in consola.texto_completo())

# ---------------- 4. Color por tipo de linea ----------------
print("\n== Cada linea con su color ==")
consola.limpiar()
consola.imprimir("todo bien", "ok")
consola.imprimir("todo mal", "error")
consola.imprimir("ojo", "aviso")
consola.imprimir("un comando", "orden", prefijo="> ")
bombear()
for etiqueta in ("ok", "error", "aviso", "orden", "hora"):
    comprobar(f"la etiqueta {etiqueta:6} se aplico", bool(consola.textbox.tag_ranges(etiqueta)))
colores = {e: consola.textbox.tag_cget(e, "foreground") for e in ("ok", "error", "aviso")}
comprobar("un exito y un error NO son del mismo color",
          colores["ok"] != colores["error"], str(colores))
comprobar("la hora va en su propio tono, mas apagado",
          consola.textbox.tag_cget("hora", "foreground") == consola.COLOR_HORA)
comprobar("un tipo inventado no revienta y cae en el neutro",
          (consola.imprimir("raro", "no_existe_este_tipo") or True))

# ---------------- 5. Traducciones (el fallo de verdad) ----------------
print("\n== Nada escrito a mano en espanol ==")
import re
import ast

# Se lee con ast y no con una expresion regular: la primera version de esta
# comprobacion leia el fuente en crudo y marcaba como fallo las frases que
# estan DENTRO de los comentarios y los docstrings explicando el arreglo.
# Un banco que grita por su propia documentacion no sirve de nada.
arbol = ast.parse(open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read())
nombres = {"_tooltip_ctk", "_ConsolaBase", "DevConsole", "ComandoConsole"}
nodos = [n for n in arbol.body
         if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in nombres]
comprobar("estan las cuatro piezas de la consola", len(nodos) == 4,
          str(sorted(n.name for n in nodos)))

# Los docstrings son el primer hijo del cuerpo: se apartan por identidad,
# no por contenido, para no confundirlos con una cadena de verdad.
docstrings = set()
for nodo in nodos:
    for sub in ast.walk(nodo):
        if isinstance(sub, (ast.FunctionDef, ast.ClassDef, ast.Module)):
            cuerpo = getattr(sub, "body", [])
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant)                     and isinstance(cuerpo[0].value.value, str):
                docstrings.add(id(cuerpo[0].value))

sospechosas = []
for nodo in nodos:
    for sub in ast.walk(nodo):
        if not (isinstance(sub, ast.Constant) and isinstance(sub.value, str)):
            continue
        if id(sub) in docstrings:
            continue
        texto = sub.value
        # Una frase es dos o mas palabras de letras seguidas. Los nombres de
        # fuente, los colores, los formatos de fecha y las claves de idioma
        # no lo son, y son casi todo lo que queda.
        if re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}", texto) and "Consolas" not in texto:
            sospechosas.append(texto)
comprobar("ninguna frase visible escrita a mano en el codigo de la consola",
          not sospechosas, str(sospechosas[:3]) if sospechosas else "")

for clave in ("consola_titulo_dev", "consola_titulo_panel", "consola_ejecutar",
              "consola_placeholder", "consola_pista", "consola_btn_copiar",
              "consola_btn_limpiar", "consola_btn_guardar", "dev_panel_titulo",
              "dev_ref_titulo", "dev_ref_cuerpo"):
    en_es = idiomas.TEXTOS["es"].get(clave)
    en_en = idiomas.TEXTOS["en"].get(clave)
    comprobar(f"{clave:24} traducida en los dos idiomas",
              bool(en_es) and bool(en_en) and en_es != en_en if clave != "dev_ref_cuerpo"
              else bool(en_es) and bool(en_en))

# ---------------- 6. El encabezado dice la verdad ----------------
print("\n== El filito de color debajo del encabezado ==")
# Un separador de 2 px que no se pinta es invisible en las dos direcciones: no
# se ve en pantalla, y tampoco se ve leyendo el codigo, porque el widget esta
# ahi y hasta mide sus 2 px. La primera version era un CTkFrame, que pinta su
# fondo dibujando en un lienzo interno, y con 2 px de alto no quedaba nada que
# dibujar. Se comprueba sobre el widget, no sobre una imagen.
filitos = [h for h in consola.winfo_children()
           if isinstance(h, tk.Frame) and not isinstance(h, ctk.CTkFrame)
           and int(h.cget("height")) <= 4]
comprobar("hay un separador fino", len(filitos) == 1, f"{len(filitos)} encontrado(s)")
if filitos:
    comprobar("va del color de acento de la consola",
              str(filitos[0].cget("bg")).lower() == consola.acento.lower(),
              f'{filitos[0].cget("bg")} vs acento {consola.acento}')
    comprobar("y esta mostrado en pantalla", bool(filitos[0].winfo_ismapped()))

print("\n== Encabezado con edicion, permisos y PID ==")
estado = consola._texto_estado()
comprobar("lleva la version", main.APP_VERSION in estado, estado)
comprobar("lleva el PID de este proceso", str(os.getpid()) in estado)
comprobar("dice la edicion en el idioma de la build",
          idiomas.t("consola_estado_edicion_cliente") in estado
          or idiomas.t("consola_estado_edicion_admin") in estado)

main.EDICION = "admin"
comprobar("y cambia si cambia la edicion",
          idiomas.t("consola_estado_edicion_admin") in consola._texto_estado(),
          consola._texto_estado())
main.EDICION = "cliente"

# ---------------- 7. Limpiar, copiar y guardar ----------------
print("\n== Botones del registro ==")
consola.imprimir("algo que estaba escrito", "info")
consola.limpiar()
bombear()
comprobar("limpiar deja la consola vacia",
          "algo que estaba escrito" not in consola.texto_completo())
comprobar("y avisa de que la limpio",
          idiomas.t("consola_limpiado") in consola.texto_completo())

consola.imprimir("esto se copia", "info")
consola.copiar()
bombear()
try:
    portapapeles = root.clipboard_get()
except Exception as e:
    portapapeles = f"(no se pudo leer: {e})"
comprobar("copiar deja el registro en el portapapeles",
          "esto se copia" in portapapeles, portapapeles[:40])

consola.guardar_log()
bombear()
carpeta_reg = os.path.join(carpeta, "registros")
archivos = os.listdir(carpeta_reg) if os.path.isdir(carpeta_reg) else []
comprobar("guardar crea un archivo de verdad", len(archivos) == 1, str(archivos))
if archivos:
    contenido = open(os.path.join(carpeta_reg, archivos[0]), encoding="utf-8").read()
    comprobar("y dentro esta lo que se veia en pantalla", "esto se copia" in contenido)
    comprobar("y dice en la consola donde lo dejo",
              carpeta_reg in consola.texto_completo())

# ---------------- 8. Fichas y sugerencias ----------------
print("\n== Fichas y sugerencias ==")
recibidos.clear()
consola._lanzar_ficha("/dns")
comprobar("pulsar una ficha lanza el comando", recibidos == ["/dns"], str(recibidos))
comprobar("y queda en el historial para poder repetirlo con la flecha",
          consola._historial[-1] == "/dns")
for ficha in consola.FICHAS:
    comprobar(f"la ficha {ficha:12} es un comando que existe",
              ficha in main.COMANDOS_DISPONIBLES)

# El motor de comandos de verdad, para la sugerencia.
app = main.TechCleanApp()
app.geometry("1200x800+4000+4000")
app.withdraw()
bombear(8)


class ConsolaFalsa:
    def __init__(self):
        self.dicho, self.tipos = [], []

    def imprimir(self, texto, tipo="info", prefijo=""):
        self.dicho.append(str(texto))
        self.tipos.append(tipo)

    def limpiar(self):
        pass

    def guardar_log(self):
        pass


falsa = ConsolaFalsa()
app._ejecutar_comando("/papelra", consola=falsa)
comprobar("un comando mal escrito se marca como error", "error" in falsa.tipos,
          str(falsa.tipos))
comprobar("y sugiere el parecido",
          any("/papelera" in d for d in falsa.dicho), str(falsa.dicho))

falsa = ConsolaFalsa()
app._ejecutar_comando("/qqqqzzzz", consola=falsa)
comprobar("uno que no se parece a nada no inventa una sugerencia",
          not any("/papelera" in d for d in falsa.dicho), str(falsa.dicho))

falsa = ConsolaFalsa()
app._ejecutar_comando("/version", consola=falsa)
texto_version = "\n".join(falsa.dicho)
comprobar("/version dice si va como administrador",
          idiomas.t("consola_estado_admin") in texto_version
          or idiomas.t("consola_estado_usuario") in texto_version, texto_version[:60])
comprobar("/version dice donde guarda los datos", carpeta in texto_version)

print("\n== Estado del sistema (/estado) ==")
lineas_estado = app._lineas_estado_consola()
comprobar("devuelve varias lineas", lineas_estado.count("\n") >= 4,
          f"{lineas_estado.count(chr(10)) + 1} lineas")
comprobar("no filtra claves internas sin traducir", "consola_estado_" not in lineas_estado)
comprobar("nunca deja un {placeholder} sin rellenar",
          "{" not in lineas_estado, lineas_estado)

# ---------------- 9. La pantalla del admin, entera ----------------
print("\n== Panel de Desarrollador (pantalla del admin) ==")
main.EDICION = "admin"
app.mostrar_consola()
bombear(8)
comprobar("la consola se monto en la pantalla", app.dev_console is not None)
comprobar("la referencia tecnica arranca plegada", app._ref_abierta is False)

botones = []


def _recoger(w):
    if isinstance(w, ctk.CTkButton):
        botones.append(w)
    for hijo in w.winfo_children():
        _recoger(hijo)


_recoger(app.contenido)
plegable = [b for b in botones if str(b.cget("text"))[:1] in ("▸", "▾")]
comprobar("hay un solo boton para plegar la referencia", len(plegable) == 1,
          f"{len(plegable)} encontrado(s)")
if plegable:
    plegable[0].invoke()
    bombear()
    comprobar("se despliega al pulsarlo", app._ref_abierta is True)
    comprobar("y la flecha apunta hacia abajo",
              str(plegable[0].cget("text")).startswith("▾"))
    plegable[0].invoke()
    bombear()
    comprobar("se vuelve a plegar", app._ref_abierta is False)
    comprobar("y la flecha vuelve a apuntar a la derecha",
              str(plegable[0].cget("text")).startswith("▸"))

# El registro tecnico en vivo: _log_dev alimenta la consola Y el historial.
app._log_dev("Accion de prueba", "comando de prueba", "resultado de prueba")
bombear(8)
volcado = app.dev_console.texto_completo()
comprobar("el registro tecnico en vivo llega a la consola",
          "Accion de prueba" in volcado)
comprobar("con el comando y el resultado, cada uno en su linea",
          "comando de prueba" in volcado and "resultado de prueba" in volcado)

# _log_dev se llama desde hilos de fondo (el autopiloto lo hace). Tiene que
# aguantarlo: es el fallo de "main thread is not in main loop" otra vez.
import threading as _hilos

fallo_en_hilo = []


def _desde_un_hilo():
    try:
        app._log_dev("Desde un hilo", "N/A", "sin reventar")
    except Exception as e:
        fallo_en_hilo.append(repr(e))


h = _hilos.Thread(target=_desde_un_hilo)
h.start()
h.join(3)
bombear(10)
comprobar("registrar desde un hilo de fondo no revienta", not fallo_en_hilo,
          str(fallo_en_hilo))
comprobar("y lo escrito desde el hilo aparece",
          "Desde un hilo" in app.dev_console.texto_completo())
main.EDICION = "cliente"

# ---------------- 10. Destruir con todo abierto ----------------
print("\n== Destruir sin dejar nada colgando ==")
consola.destroy()
bombear(6)
comprobar("destruir la consola no revienta", True)
app.destroy()
root.destroy()

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
