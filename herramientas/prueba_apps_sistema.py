# -*- coding: utf-8 -*-
"""Comprueba Aplicaciones, Disco y Sistema de la 1.6.0, sin cambiar nada.

  * La tabla de winget se lee en cualquier idioma (antes, con winget en
    español, la lista de actualizaciones salía vacía).
  * Quitar apps de serie solo acepta paquetes de la lista, y nada que pueda
    colarse en el comando de PowerShell.
  * Duplicados: mismo contenido, no mismo nombre; nunca entra en uniones; y
    al enviar a la papelera NUNCA se van todas las copias de un archivo.
  * Puntos de restauración: crear uno con otro de hace menos de 24 h ya no
    se da por bueno; borrar los antiguos deja siempre el más reciente.
    Con las llamadas a Windows sustituidas: no se crea ni se borra nada.

Uso:  python herramientas/prueba_apps_sistema.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== Tabla de winget en cualquier idioma ==")
en = ("Name          Id           Version  Available Source\n"
      "-----------------------------------------------------\n"
      "Git           Git.Git      2.55.0.4 2.55.0.5  winget\n"
      "2 upgrades available.\n")
es = ("Nombre                Id                  Versión  Disponible Origen\n"
      "-------------------------------------------------------------------\n"
      "Terminal de Windows   Microsoft.Terminal  1.24     1.25       winget\n"
      "1 actualizaciones disponibles.\n")
comprobar(opt._filas_tabla_winget(en) == [["Git", "Git.Git", "2.55.0.4", "2.55.0.5", "winget"]], "ingles")
comprobar(opt._filas_tabla_winget(es) == [["Terminal de Windows", "Microsoft.Terminal", "1.24", "1.25", "winget"]],
          "espanol, con cabeceras separadas por UN espacio y nombres con espacios")
comprobar(opt._filas_tabla_winget("No se encontraron actualizaciones.") == [], "sin tabla -> lista vacia")

print("== Quitar apps de serie: solo lo de la lista ==")
llamadas = []
original_run = opt.subprocess.run


class Resultado:
    returncode = 0
    stdout = ""


opt.subprocess.run = lambda *a, **k: llamadas.append(a[0]) or Resultado()
try:
    quitados, fallidos, _ = opt.quitar_bloatware([
        "Microsoft.WindowsStore_22409.1401.0.0_x64__8wekyb3d8bbwe",
        "king.com.CandyCrush'; Remove-Item C:\\ -Recurse; '",
        "Microsoft.BingNews_1.0.2.0_x64__8wekyb3d8bbwe"])
finally:
    opt.subprocess.run = original_run
comprobar(quitados == ["Microsoft.BingNews_1.0.2.0_x64__8wekyb3d8bbwe"], "quita solo la de la lista")
comprobar(len(fallidos) == 2, "rechaza la Tienda y el nombre con un comando colado")
comprobar(len(llamadas) == 1, f"y ni siquiera llama a PowerShell para los rechazados ({len(llamadas)})")

print("== Duplicados ==")
base = tempfile.mkdtemp(prefix="tc_dup_")
try:
    MB = 1024 * 1024
    contenido = os.urandom(2 * MB)
    for nombre in ("a.bin", os.path.join("sub", "copia de a.bin")):
        os.makedirs(os.path.dirname(os.path.join(base, nombre)) or base, exist_ok=True)
        open(os.path.join(base, nombre), "wb").write(contenido)
    open(os.path.join(base, "mismo_tamano_distinto.bin"), "wb").write(contenido[:-1] + b"X")
    open(os.path.join(base, "pequeno1.txt"), "wb").write(b"hola")
    open(os.path.join(base, "pequeno2.txt"), "wb").write(b"hola")
    fuera = tempfile.mkdtemp(prefix="tc_dup_fuera_")
    open(os.path.join(fuera, "a_fuera.bin"), "wb").write(contenido)
    union = os.path.join(base, "union")
    hay_union = subprocess.run(["cmd", "/c", "mklink", "/J", union, fuera], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
    grupos, completo = opt.buscar_duplicados(base)
    comprobar(completo and len(grupos) == 1 and len(grupos[0]["rutas"]) == 2,
              f"un grupo de 2: mismo contenido, distinto nombre ({[len(g['rutas']) for g in grupos]})")
    comprobar(not any("mismo_tamano_distinto" in r for g in grupos for r in g["rutas"]),
              "mismo tamano pero distinto contenido NO es duplicado")
    comprobar(not any("pequeno" in r for g in grupos for r in g["rutas"]), "por debajo de 1 MB no se mira")
    if hay_union:
        comprobar(not any("a_fuera" in r for g in grupos for r in g["rutas"]), "no entra en uniones")
    ev = threading.Event()
    ev.set()
    _, completo2 = opt.buscar_duplicados(base, evento_cancelar=ev)
    comprobar(completo2 is False, "cancelado -> lo dice (completo=False)")
finally:
    if os.path.isdir(os.path.join(base, "union")):
        os.rmdir(os.path.join(base, "union"))
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(fuera, ignore_errors=True)

print("== Enviar duplicados: nunca todas las copias ==")
import main


class Var:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


enviadas = []
falso = types.SimpleNamespace(
    _checks_dup=[[(Var(True), "C:/x/a.bin"), (Var(True), "C:/x/b.bin")],
                 [(Var(False), "C:/y/a.mp4"), (Var(True), "C:/y/b.mp4"), (Var(True), "C:/y/c.mp4")]],
    _confirmar_borrar_archivos=lambda rutas: enviadas.extend(rutas))
main.TechCleanApp._accion_enviar_duplicados(falso)
comprobar("C:/x/a.bin" not in enviadas and "C:/x/b.bin" in enviadas,
          "con todas las copias marcadas, la primera se salva igual")
comprobar(enviadas.count("C:/y/b.mp4") == 1 and "C:/y/a.mp4" not in enviadas, "lo demas se respeta tal cual")

print("== Puntos de restauracion (sin tocar Windows) ==")
original_listar = opt.listar_puntos_restauracion
original_run = opt.subprocess.run
llamadas.clear()
try:
    opt.listar_puntos_restauracion = lambda: [{"numero": 5}]
    opt.subprocess.run = lambda *a, **k: llamadas.append(a[0]) or Resultado()
    exito, _ = opt.crear_punto_restauracion("prueba")
    comprobar(exito is False, "Checkpoint-Computer 'bien' pero sin punto nuevo (limite de 24 h) -> NO creado")
    llamadas.clear()
    comprobar(opt.borrar_puntos_antiguos()[:2] == (0, 1) and not llamadas,
              "con un solo punto no borra nada (y no llama a vssadmin)")
    estado = {"puntos": [{"numero": 3}, {"numero": 2}, {"numero": 1}]}

    def run_falso(cmd, *a, **k):
        llamadas.append(cmd)
        if cmd[0] == "vssadmin":
            estado["puntos"] = estado["puntos"][:-1]
        return Resultado()
    opt.listar_puntos_restauracion = lambda: list(estado["puntos"])
    opt.subprocess.run = run_falso
    borrados, restantes, _ = opt.borrar_puntos_antiguos()
    vss = [c for c in llamadas if c[0] == "vssadmin"]
    comprobar(len(vss) == 2 and all("/oldest" in c for c in vss), "con 3 puntos: dos borrados de 'el mas antiguo'")
    comprobar((borrados, restantes) == (2, 1), "y queda el mas reciente")
finally:
    opt.listar_puntos_restauracion = original_listar
    opt.subprocess.run = original_run

print("== Informe de energia ==")
tmp = tempfile.mkdtemp(prefix="tc_energia_")
original = opt._ejecutar_reparacion_cancelable
try:
    def falso_powercfg(cmd, **k):
        open(os.path.join(tmp, "informe_energia_windows.html"), "w").write("<html></html>")
        return False, "Se encontraron 3 errores", False   # powercfg sale con error si ENCUENTRA problemas
    opt._ejecutar_reparacion_cancelable = falso_powercfg
    exito, ruta, _, _ = opt.informe_energia(tmp)
    comprobar(exito and ruta, "si el informe existe, es un exito aunque powercfg salga con codigo de error")
finally:
    opt._ejecutar_reparacion_cancelable = original
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
