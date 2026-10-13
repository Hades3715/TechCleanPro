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

print("== 1.8.0: qué cuenta como juego ==")
carpetas = [os.path.normcase(os.path.normpath(r"D:\Steam\steamapps\common\Juego")) + os.sep]
comprobar(auto.en_carpeta_de_juego(r"D:\Steam\steamapps\common\Juego\bin\juego.exe", carpetas),
          "un programa dentro de la carpeta de un juego")
comprobar(not auto.en_carpeta_de_juego(r"D:\Steam\steamapps\common\JuegoDos\x.exe", carpetas),
          "no la de otro juego que empieza igual")
piloto = auto.Autopilot(carpetas_juegos=lambda: carpetas)
originales = (auto._get_foreground_fullscreen_pid, auto._pid_en_primer_plano, auto._exe_de)
exes = {10: r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        20: r"D:\Steam\steamapps\common\Juego\bin\juego.exe", 30: r"C:\Apps\editor.exe"}
try:
    auto._exe_de = lambda pid: exes.get(pid, "")
    auto._get_foreground_fullscreen_pid, auto._pid_en_primer_plano = lambda: 10, lambda: 10
    comprobar(piloto._buscar_juego() is None, "el navegador a pantalla completa NO es un juego")
    auto._get_foreground_fullscreen_pid, auto._pid_en_primer_plano = lambda: None, lambda: 20
    comprobar(piloto._buscar_juego() == 20, "un juego de la biblioteca cuenta aunque vaya en ventana")
    auto._get_foreground_fullscreen_pid, auto._pid_en_primer_plano = lambda: None, lambda: 30
    comprobar(piloto._buscar_juego() is None, "otro programa en ventana, no")
finally:
    auto._get_foreground_fullscreen_pid, auto._pid_en_primer_plano, auto._exe_de = originales

print("== 1.8.0: Modo Juego automático por juego ==")
encendidos, apagados = [], []
vigia = auto.VigiaJuegos(carpetas=lambda: carpetas, encender=encendidos.append,
                         apagar=lambda: apagados.append(True))
vivos = {20}
originales = (auto._pid_en_primer_plano, auto._exe_de, auto.psutil.pid_exists)
try:
    auto._exe_de = lambda pid: exes.get(pid, "")
    auto.psutil.pid_exists = lambda pid: pid in vivos
    auto._pid_en_primer_plano = lambda: 30
    vigia.revisar()
    comprobar(not encendidos, "con otro programa delante, nada")
    auto._pid_en_primer_plano = lambda: 20
    vigia.revisar()
    comprobar(encendidos == ["juego"], "con el juego delante, se enciende (una vez)")
    auto._pid_en_primer_plano = lambda: 30
    vigia.revisar()
    comprobar(encendidos == ["juego"] and not apagados, "cambiar de ventana no lo apaga: el juego sigue abierto")
    vivos.clear()
    vigia.revisar()
    comprobar(apagados == [True], "al cerrar el juego, se apaga")
    vigia_vacio = auto.VigiaJuegos(carpetas=lambda: [], encender=encendidos.append)
    vigia_vacio.revisar()
    comprobar(encendidos == ["juego"], "sin juegos marcados no mira nada")
finally:
    auto._pid_en_primer_plano, auto._exe_de, auto.psutil.pid_exists = originales

print("== 1.8.0: frenar lo que acapara la CPU ==")
# Un proceso PROPIO que gasta CPU sin parar. Se le hace creer al piloto que es
# el único proceso del equipo: nunca toca los de verdad.
import subprocess
import time
gloton = subprocess.Popen([sys.executable, "-c", "while True: pass"], creationflags=subprocess.CREATE_NO_WINDOW)
iter_original = auto.psutil.process_iter
try:
    auto.psutil.process_iter = lambda attrs=None: (p for p in iter_original(attrs) if p.pid == gloton.pid)
    piloto = auto.Autopilot(frenar_acaparadores=lambda: True)
    for _ in range(4):
        piloto._frenar_acaparadores(pid_juego=999999)
        time.sleep(0.6)
    frenado = auto.psutil.Process(gloton.pid).nice() == auto.psutil.BELOW_NORMAL_PRIORITY_CLASS
    comprobar(frenado and gloton.pid in piloto._frenados, "tras dos vueltas por encima, baja su prioridad")
    piloto._soltar_frenados()
    comprobar(auto.psutil.Process(gloton.pid).nice() == auto.psutil.NORMAL_PRIORITY_CLASS,
              "al terminar la partida se le devuelve la normal")
    piloto = auto.Autopilot(frenar_acaparadores=lambda: False)
    for _ in range(3):
        piloto._frenar_acaparadores(pid_juego=999999)
        time.sleep(0.4)
    comprobar(not piloto._frenados, "con el interruptor apagado no frena nada")
    piloto = auto.Autopilot(frenar_acaparadores=lambda: True)
    for _ in range(3):
        piloto._frenar_acaparadores(pid_juego=gloton.pid)
        time.sleep(0.4)
    comprobar(not piloto._frenados, "nunca frena el propio juego")
finally:
    auto.psutil.process_iter = iter_original
    gloton.kill()

print("== 1.8.0: nota de bufferbloat ==")
comprobar([opt.nota_bufferbloat(x) for x in (None, 2, 20, 45, 150, 300, 800)]
          == [None, "A+", "A", "B", "C", "D", "F"], "la escala de Waveform")

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
