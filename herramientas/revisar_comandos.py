# -*- coding: utf-8 -*-
"""Comprueba el panel de comandos oculto y la Consola Dev.

Los dos usan el mismo motor (_ejecutar_comando). Lo que se comprueba:

  * Que TODO comando anunciado en /help este de verdad implementado. Un
    comando que aparece en la ayuda y no hace nada es peor que no tenerlo:
    el usuario cree que fallo la app.
  * Que no haya comandos implementados que /help no mencione — existen
    pero nadie los descubre.
  * Que los que solo NAVEGAN a una pantalla funcionen de verdad.
  * Que la entrada rara (vacia, espacios, mayusculas, un comando que no
    existe, texto larguisimo) no reviente nada.

No ejecuta los comandos que TOCAN el sistema (/ram, /temporales,
/papelera, /dns, /rapido, /fps, /widget, /auto): esos hacen cosas de
verdad. De esos solo se comprueba que esten implementados.

Uso:  python herramientas\\revisar_comandos.py
"""
import json
import os
import re
import sys
import tempfile
import time
import traceback

perfil = tempfile.mkdtemp(prefix="tcp_cmd_")
os.environ["APPDATA"] = perfil
carpeta = os.path.join(perfil, "TechClean")
os.makedirs(carpeta, exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False},
          open(os.path.join(carpeta, "preferencias.json"), "w", encoding="utf-8"))

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import main

# Los que hacen algo de verdad: se comprueba que existan, no se ejecutan.
CON_EFECTOS = {"/ram", "/temporales", "/papelera", "/dns", "/rapido",
               "/fps", "/widget", "/auto", "/guardar"}

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


fuente = open(_rutas.fuente("main.py"), encoding="utf-8").read()
cuerpo = fuente[fuente.index("def _ejecutar_comando"):]
cuerpo = cuerpo[:cuerpo.index("\n    # ---------------- BIOS")]

declarados = set(main.COMANDOS_DISPONIBLES)
# Implementados: los comparados con == y los del diccionario de navegacion
implementados = set(re.findall(r'comando == "(/[a-z]+)"', cuerpo))
implementados |= set(re.findall(r'^\s*"(/[a-z]+)": self\.', cuerpo, re.M))
implementados |= {"/help"}

print("== Cobertura de comandos ==")
print(f"  anunciados en /help : {len(declarados)}")
print(f"  implementados       : {len(implementados)}")

sin_implementar = declarados - implementados
comprobar("todo lo que /help anuncia esta implementado", not sin_implementar,
          f"faltan: {sorted(sin_implementar)}" if sin_implementar else "")

ocultos = implementados - declarados - {"/ayuda"}
comprobar("no hay comandos implementados que /help no mencione", not ocultos,
          f"sin anunciar: {sorted(ocultos)}" if ocultos else "")

# ---- Ejecucion real de los que solo navegan ----
app = main.TechCleanApp()
app.geometry("1200x800+4000+4000")
app.withdraw()
for _ in range(8):
    app.update()
    time.sleep(0.02)

# Consola de mentira, para recoger lo que responde cada comando.
class ConsolaFalsa:
    """Imita la interfaz que _ejecutar_comando espera de una consola.

    Tiene que seguir a la de verdad: cuando imprimir() empezo a recibir un
    `tipo` para elegir el color, esta clase se quedo con la firma vieja y el
    banco fallaba con TypeError en TODOS los comandos — un fallo del banco,
    no de la app. Se registra tambien el tipo para poder comprobar que un
    error sale marcado como error y no del mismo color que un exito.
    """

    def __init__(self):
        self.dicho = []
        self.tipos = []
        self.limpiada = 0
        self.guardada = 0

    def imprimir(self, texto, tipo="info", prefijo=""):
        self.dicho.append(prefijo + str(texto))
        self.tipos.append(tipo)

    def limpiar(self):
        self.limpiada += 1
        self.imprimir("(limpiada)", "dim")

    def guardar_log(self):
        self.guardada += 1
        self.imprimir("(guardada)", "ok")


print("\n== Comandos de navegacion (se ejecutan de verdad) ==")
navegacion = sorted(declarados - CON_EFECTOS - {"/help", "/salir"})
for comando in navegacion:
    consola = ConsolaFalsa()
    try:
        app._ejecutar_comando(comando, consola=consola)
        for _ in range(25):          # navegacion va con after(300, ...)
            app.update()
            time.sleep(0.02)
        contesto = bool(consola.dicho)
        comprobar(f"{comando:14} responde y no revienta", contesto,
                  (consola.dicho[0][:40] if consola.dicho else "sin respuesta"))
    except Exception:
        ultima = traceback.format_exc().strip().splitlines()[-1]
        comprobar(f"{comando:14} responde y no revienta", False, ultima)

print("\n== Entrada rara ==")
raros = [("vacia", ""), ("solo espacios", "   "), ("mayusculas", "/HELP"),
         ("sin barra", "help"), ("inventado", "/estonoexiste"),
         ("con espacios", "  /help  "), ("larguisimo", "/" + "a" * 5000),
         ("simbolos", "/../..\\x00"), ("acentos", "/ñandú")]
for etiqueta, entrada in raros:
    consola = ConsolaFalsa()
    try:
        app._ejecutar_comando(entrada, consola=consola)
        app.update()
        comprobar(f"entrada {etiqueta:14} no revienta", True,
                  (consola.dicho[0][:45] if consola.dicho else "(sin respuesta)"))
    except Exception:
        ultima = traceback.format_exc().strip().splitlines()[-1]
        comprobar(f"entrada {etiqueta:14} no revienta", False, ultima)

print("\n== /help se traduce ==")
consola = ConsolaFalsa()
app._ejecutar_comando("/help", consola=consola)
ayuda = consola.dicho[0] if consola.dicho else ""
comprobar("lista todos los comandos", ayuda.count("/") >= len(declarados),
          f"{ayuda.count('/')} lineas")
comprobar("no filtra claves internas sin traducir", "cmd_" not in ayuda)

app.destroy()
print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
