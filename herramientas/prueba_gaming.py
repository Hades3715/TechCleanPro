# -*- coding: utf-8 -*-
"""Comprueba el paquete Gaming de la 1.6.0, sin cambiar nada del sistema.

  * Cerrar apps al jugar y reabrirlas al terminar: con procesos de mentira.
    Lo importante es lo que NO se cierra: el juego, TechClean y los procesos
    intocables (aunque el usuario los hubiera marcado).
  * Ajustes de Windows para juegos: se prueban contra una clave de registro
    PROPIA (HKCU\\Software\\TechCleanPrueba), nunca contra las de Windows. Lo
    delicado es deshacer cuando la clave no existía: hay que BORRARLA, no
    dejarla a 0.
  * Medidor de lag: las cuentas y el veredicto (funciones puras), y un ping
    de verdad a 127.0.0.1.

Uso:  python herramientas/prueba_gaming.py
"""
import os
import sys

import _rutas
_rutas.poner_en_ruta()
import autopilot as auto
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== Cerrar y reabrir apps al jugar ==")
procesos = [(100, "Discord.exe", r"C:\Apps\Discord.exe"), (101, "Discord.exe", r"C:\Apps\Discord.exe"),
            (200, "spotify.exe", r"C:\Apps\Spotify.exe"), (300, "juego.exe", r"C:\Juegos\juego.exe"),
            (400, "csrss.exe", r"C:\Windows\System32\csrss.exe"), (500, "chrome.exe", r"C:\Apps\chrome.exe")]
terminados, lanzados, registro = [], [], []
piloto = auto.Autopilot(
    log_callback=lambda *a, **k: registro.append(a),
    apps_cerrar=lambda: ["discord.exe", "Spotify.exe", "juego.exe", "csrss.exe"],
    listar_procesos=lambda: iter(procesos),
    terminar=lambda pid: terminados.append(pid) or True,
    lanzar=lambda exe: lanzados.append(exe) or True)
cerradas = piloto._cerrar_apps(excluir_pid=300)
comprobar(sorted(terminados) == [100, 101, 200], f"cierra Discord (los dos procesos) y Spotify ({terminados})")
comprobar(300 not in terminados, "NO cierra el juego aunque estuviera marcado")
comprobar(400 not in terminados, "NO cierra un proceso intocable (csrss.exe) aunque estuviera marcado")
comprobar(500 not in terminados, "NO cierra lo que no se marco (chrome.exe)")
comprobar(piloto._cerradas == [r"C:\Apps\Discord.exe", r"C:\Apps\Spotify.exe"],
          "apunta cada .exe una sola vez para reabrirlo")
reabiertas = piloto._reabrir_apps()
comprobar(lanzados == [r"C:\Apps\Discord.exe", r"C:\Apps\Spotify.exe"], "al terminar, reabre las dos apps")
comprobar(piloto._cerradas == [] and piloto._reabrir_apps() == [], "y no las reabre dos veces")

terminados.clear(); lanzados.clear()
piloto._cerrar_apps(excluir_pid=300)
piloto.detener()
comprobar(len(lanzados) == 2, "apagar el Modo Juego a mitad de partida tambien las reabre")

vacio = auto.Autopilot(apps_cerrar=lambda: [], listar_procesos=lambda: iter(procesos),
                       terminar=lambda pid: terminados.append(pid) or True)
terminados.clear()
comprobar(vacio._cerrar_apps(300) == [] and not terminados, "sin apps marcadas no cierra nada")

print("== Juego detectado -> cerrar; juego terminado -> reabrir ==")
terminados.clear(); lanzados.clear()
original = auto._get_foreground_fullscreen_pid
try:
    piloto2 = auto.Autopilot(apps_cerrar=lambda: ["spotify.exe"], listar_procesos=lambda: iter(procesos),
                             terminar=lambda pid: terminados.append(pid) or True,
                             lanzar=lambda exe: lanzados.append(exe) or True)
    import os
    auto._get_foreground_fullscreen_pid = lambda: os.getpid()   # un "juego" que existe de verdad
    original_nice = auto.psutil.Process.nice
    auto.psutil.Process.nice = lambda self, valor=None: None    # sin cambiar prioridades reales
    piloto2._chequear_juego()
    comprobar(terminados == [200], f"al detectar el juego cierra Spotify ({terminados})")
    auto._get_foreground_fullscreen_pid = lambda: None
    piloto2._chequear_juego()
    comprobar(lanzados == [r"C:\Apps\Spotify.exe"], "al salir del juego lo reabre")
finally:
    auto._get_foreground_fullscreen_pid = original
    auto.psutil.Process.nice = original_nice

print("== Ajustes de juego (clave de prueba propia) ==")
if opt.IS_WINDOWS:
    import winreg
    RUTA = r"Software\TechCleanPrueba"
    tabla = {"prueba": {"claves": [("HKCU", RUTA, "UnoDWORD"), ("HKCU", RUTA + r"\Sub", "DosDWORD")],
                        "on": 2, "off": 1, "defecto": None, "recomendado": True, "reinicio": False}}
    try:
        comprobar(opt.leer_ajustes_juego(tabla) == {"prueba": None}, "sin clave y sin defecto -> desconocido")
        exito, _, anteriores = opt.set_ajuste_juego("prueba", True, tabla)
        comprobar(exito and anteriores == [None, None], "activa y apunta que antes no existia")
        comprobar(opt.leer_ajustes_juego(tabla) == {"prueba": True}, "se lee como activado")
        exito, _ = opt.restaurar_ajuste_juego("prueba", anteriores, tabla)
        comprobar(exito and opt._leer_dword("HKCU", RUTA, "UnoDWORD") is None,
                  "deshacer BORRA el valor que no existia (no lo deja a 0)")
        opt._escribir_dword("HKCU", RUTA, "UnoDWORD", 1)
        opt._escribir_dword("HKCU", RUTA + r"\Sub", "DosDWORD", 1)
        _, _, anteriores = opt.set_ajuste_juego("prueba", True, tabla)
        opt.restaurar_ajuste_juego("prueba", anteriores, tabla)
        comprobar(opt.leer_ajustes_juego(tabla) == {"prueba": False}, "y vuelve al valor que si existia")
        comprobar(opt.set_ajuste_juego("no_existe", True, tabla)[0] is False, "un ajuste desconocido no hace nada")
    finally:
        for sub in (RUTA + r"\Sub", RUTA):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass
    for clave, a in opt.AJUSTES_JUEGO.items():
        comprobar(a["on"] != a["off"] and a["claves"], f"{clave}: valores on/off distintos y alguna clave")

print("== Medidor de lag ==")
e = opt.estadisticas_ping([10, 12, None, 11, 30])
comprobar(e["perdida_pct"] == 20.0 and e["media_ms"] == 15.8, f"media y perdida ({e})")
comprobar(e["jitter_ms"] == round((2 + 1 + 19) / 3, 1), "la variacion es la media de saltos entre pings seguidos")
comprobar(opt.estadisticas_ping([None, None])["perdida_pct"] == 100.0, "todo perdido -> 100 %")
bien = {"recibidos": 30, "perdida_pct": 0, "media_ms": 3, "jitter_ms": 1}
comprobar(opt.veredicto_lag(bien, {"recibidos": 30, "perdida_pct": 0, "media_ms": 40, "jitter_ms": 2}) == "bien",
          "todo bien -> bien")
comprobar(opt.veredicto_lag({"recibidos": 30, "perdida_pct": 6, "media_ms": 3, "jitter_ms": 1},
                            {"recibidos": 30, "perdida_pct": 6, "media_ms": 90, "jitter_ms": 30}) == "local",
          "si el router ya pierde paquetes, el problema es local (aunque internet tambien vaya mal)")
comprobar(opt.veredicto_lag(bien, {"recibidos": 30, "perdida_pct": 0, "media_ms": 150, "jitter_ms": 5})
          == "proveedor", "router bien e internet lento -> proveedor")
comprobar(opt.veredicto_lag(None, {"recibidos": 0, "perdida_pct": 100, "media_ms": None, "jitter_ms": None})
          == "proveedor", "sin router conocido y sin respuesta de internet -> proveedor")
if opt.IS_WINDOWS:
    ms = opt._ping_una_vez("127.0.0.1")
    comprobar(ms is not None and ms < 50, f"un ping real a 127.0.0.1 contesta ({ms} ms)")

print("== Interruptor general de cerrar apps ==")
import types
import main
for activo, esperado in ((False, []), (True, ["discord.exe"])):
    falso = types.SimpleNamespace(prefs={"cerrar_apps_al_jugar": activo, "apps_cerrar_al_jugar": ["discord.exe"]})
    comprobar(main.TechCleanApp._apps_a_cerrar_al_jugar(falso) == esperado,
              f"interruptor {'encendido' if activo else 'APAGADO'} -> {esperado or 'no cierra nada aunque haya apps marcadas'}")
falso = types.SimpleNamespace(prefs={"apps_cerrar_al_jugar": ["discord.exe"]})
comprobar(main.TechCleanApp._apps_a_cerrar_al_jugar(falso) == [], "de fabrica (sin el ajuste) viene apagado")

print("== Juegos de GOG: tres fuentes ==")
import json
import shutil
import sqlite3
import tempfile
tmp = tempfile.mkdtemp(prefix="tc_gog_")
try:
    db = os.path.join(tmp, "galaxy-2.0.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE InstalledBaseProducts (productId INTEGER, installationPath TEXT)")
    con.execute("CREATE TABLE LimitedDetails (productId INTEGER, title TEXT)")
    con.execute("INSERT INTO InstalledBaseProducts VALUES (1207658924, 'D:\\GOG Games\\The Witcher 3')")
    con.execute("INSERT INTO InstalledBaseProducts VALUES (1453375253, 'D:\\GOG Games\\Cyberpunk 2077')")
    con.execute("INSERT INTO LimitedDetails VALUES (1207658924, 'The Witcher 3: Wild Hunt')")
    con.commit()
    con.close()
    galaxy = opt._gog_galaxy(db)
    comprobar(sorted(j["nombre"] for j in galaxy) == ["Cyberpunk 2077", "The Witcher 3: Wild Hunt"],
              f"lee la base de Galaxy (con y sin titulo) ({[j['nombre'] for j in galaxy]})")
    comprobar(os.path.exists(db) and not any(f.startswith("techclean_galaxy_") for f in os.listdir(tempfile.gettempdir())),
              "lee una copia y la borra (no deja rastro ni bloquea la original)")
    con = sqlite3.connect(os.path.join(tmp, "otra.db"))
    con.execute("CREATE TABLE Distinta (x INTEGER)")
    con.close()
    comprobar(opt._gog_galaxy(os.path.join(tmp, "otra.db")) == [], "si Galaxy cambia el esquema, vacio (no revienta)")
    comprobar(opt._gog_galaxy(os.path.join(tmp, "no_existe.db")) == [], "sin Galaxy instalado, vacio")

    raiz = os.path.join(tmp, "GOG Games")
    for carpeta, info in (("Stardew Valley", {"gameId": "1453375253", "rootGameId": "1453375253", "name": "Stardew Valley"}),
                          ("Stardew Valley", {"gameId": "999", "rootGameId": "1453375253", "name": "DLC de algo"}),
                          ("Hollow Knight", {"gameId": "1308320804", "name": "Hollow Knight"})):
        os.makedirs(os.path.join(raiz, carpeta), exist_ok=True)
        with open(os.path.join(raiz, carpeta, f"goggame-{info['gameId']}.info"), "w", encoding="utf-8-sig") as f:
            json.dump(info, f)
    os.makedirs(os.path.join(raiz, "Carpeta sin juego"), exist_ok=True)
    infos = opt._gog_archivos_info([raiz, os.path.join(tmp, "no_existe")])
    comprobar(sorted(j["nombre"] for j in infos) == ["Hollow Knight", "Stardew Valley"],
              f"lee los goggame-*.info y descarta los DLC ({[j['nombre'] for j in infos]})")

    juntos = opt._juegos_gog([
        [{"id": "1207658924", "nombre": "The Witcher 3", "ruta": "D:\\GOG Games\\The Witcher 3"}],   # registro
        galaxy,                                                                                       # Galaxy
        [{"id": "", "nombre": "Witcher (otra vez)", "ruta": "d:\\gog games\\the witcher 3\\"}]])        # .info
    comprobar(sorted(j["nombre"] for j in juntos) == ["Cyberpunk 2077", "The Witcher 3"],
              "el mismo juego en varias fuentes sale UNA vez (por id o por carpeta)")
    comprobar(all(j["plataforma"] == "GOG" for j in juntos), "y como GOG")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
