# -*- coding: utf-8 -*-
"""Comprueba la revision de extensiones y los accesos directos rotos (1.7.0).

Por que importa
---------------
  * Extensiones: un auditor que grita por todo ensena a ignorarlo. El
    primer borrador marco como "riesgo alto" las diez extensiones que una
    ESCUELA instala en sus cuentas (las pone a la fuerza, como haria un
    malware). Aqui se arma un navegador de mentira con cada caso: una
    extension normal de la tienda, una cargada desde una carpeta, una
    forzada por directiva en el registro, una de la organizacion, un tema,
    una del propio navegador... y se comprueba que cada una caiga donde
    toca.
  * Accesos rotos: el .lnk se lee a mano (formato MS-SHLLINK). Si se
    leyera mal, la app mandaria a la papelera accesos que SI funcionan. Se
    crean accesos de verdad con Windows (WScript.Shell) y se comprueba que
    solo se marque el que apunta a algo borrado, y nunca uno de un disco
    desenchufado ni uno que no se puede comprobar.

No toca los navegadores ni los accesos reales: todo va en carpetas temporales.

Uso:  python herramientas/prueba_extensiones_accesos.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import _rutas
_rutas.poner_en_ruta()
import idiomas
idiomas.establecer_idioma("es")
import seguridad as seg
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)


def extension(perfil, ext_id, manifiesto, locales=None):
    carpeta = os.path.join(perfil, "Extensions", ext_id, "1.0_0")
    escribir_json(os.path.join(carpeta, "manifest.json"), manifiesto)
    for loc, mensajes in (locales or {}).items():
        escribir_json(os.path.join(carpeta, "_locales", loc, "messages.json"), mensajes)
    return carpeta


tmp = tempfile.mkdtemp(prefix="tc_ext_")
try:
    print("== Extensiones: un Chrome de mentira con cada caso ==")
    datos = os.path.join(tmp, "Chrome", "User Data")
    personal = os.path.join(datos, "Default")
    escuela = os.path.join(datos, "Profile 1")
    escribir_json(os.path.join(datos, "Local State"), {"profile": {"info_cache": {
        "Default": {"name": "Personal", "hosted_domain": "NO_HOSTED_DOMAIN", "is_managed": 0},
        "Profile 1": {"name": "Escuela", "hosted_domain": "colegio.edu.sv", "is_managed": 1}}}})
    ids = {n: (c * 32) for n, c in (("tienda", "a"), ("adblock", "b"), ("sin_tienda", "c"), ("tema", "d"),
                                    ("interna", "e"), ("forzada", "f"), ("externa", "g"), ("proxy", "h"))}
    extension(personal, ids["tienda"], {"name": "__MSG_nombre__", "version": "2.1", "default_locale": "en",
                                        "permissions": ["storage"]},
              {"en": {"nombre": {"message": "Notas"}}, "es": {"Nombre": {"message": "Notas rápidas"}}})
    extension(personal, ids["adblock"], {"name": "Bloqueador", "version": "5", "permissions": ["webRequest"],
                                         "host_permissions": ["<all_urls>"]})
    extension(personal, ids["tema"], {"name": "Tema oscuro", "version": "1", "theme": {"colors": {}}})
    extension(personal, ids["interna"], {"name": "Visor PDF", "version": "1", "permissions": ["<all_urls>"]})
    extension(personal, ids["externa"], {"name": "Asesor del antivirus", "version": "8",
                                         "permissions": ["nativeMessaging"],
                                         "content_scripts": [{"matches": ["<all_urls>"], "js": ["x.js"]}]})
    extension(personal, ids["proxy"], {"name": "VPN gratis", "version": "1", "permissions": ["proxy"]})
    # La cargada "desde una carpeta" vive fuera de Extensions/: su ruta es absoluta.
    desempaquetada = os.path.join(tmp, "descargas", "extension_rara")
    escribir_json(os.path.join(desempaquetada, "manifest.json"),
                  {"name": "Ayudante de compras", "version": "0.1",
                   "permissions": ["cookies", "debugger"], "host_permissions": ["*://*/*"]})
    escribir_json(os.path.join(personal, "Secure Preferences"), {"extensions": {"settings": {
        ids["tienda"]: {"location": 1, "from_webstore": True},
        ids["adblock"]: {"location": 1, "from_webstore": True, "disable_reasons": [1]},
        ids["tema"]: {"location": 1},
        ids["interna"]: {"location": 5},
        ids["externa"]: {"location": 6, "from_webstore": True},
        ids["proxy"]: {"location": 1, "from_webstore": True},
        ids["sin_tienda"]: {"location": 4, "path": desempaquetada}}}})
    extension(escuela, ids["forzada"], {"name": "Diccionario", "version": "3"})
    extension(escuela, ids["tienda"], {"name": "Notas", "version": "2.1", "permissions": ["storage"]})
    escribir_json(os.path.join(escuela, "Preferences"), {"extensions": {"settings": {
        ids["forzada"]: {"location": 9}, ids["tienda"]: {"location": 1, "from_webstore": True}}}})

    crudas = seg._leer_perfiles_chromium("Chrome", datos, "es")
    por_id = {}
    for e in crudas:
        por_id.setdefault(e["id"], []).append(e)
    comprobar(ids["tema"] not in por_id, "un tema de colores no se lista")
    comprobar(ids["interna"] not in por_id, "las del propio navegador (Visor PDF) no se listan")
    comprobar(por_id[ids["tienda"]][0]["nombre"] in ("Notas rápidas", "Notas"),
              f"traduce '__MSG_nombre__' con sus _locales ({por_id[ids['tienda']][0]['nombre']})")
    comprobar(por_id[ids["tienda"]][0]["nombre"] == "Notas rápidas",
              "y elige el idioma de la app, aunque la clave venga con otras mayusculas")
    comprobar(por_id[ids["sin_tienda"]][0]["origen"] == "sin_tienda", "la cargada desde una carpeta se reconoce")
    comprobar(not por_id[ids["adblock"]][0]["activa"], "la desactivada sale como desactivada")
    comprobar(por_id[ids["forzada"]][0]["origen"] == "organizacion"
              and por_id[ids["forzada"]][0]["organizacion"] == "colegio.edu.sv",
              "la forzada en el perfil de la escuela es 'de tu organizacion', no un ataque")
    comprobar("<all_urls>" in por_id[ids["externa"]][0]["permisos"],
              "un script en todas las webs cuenta como permiso para todas las webs")

    print("== Extensiones: nivel de cada una ==")
    seg_nav = seg.NAVEGADORES_CHROMIUM
    seg_dir = seg.leer_directivas_extensiones
    seg.NAVEGADORES_CHROMIUM = (("Chrome", datos),)
    malicioso = "z" * 32
    seg.leer_directivas_extensiones = lambda: {"Chrome": [(malicioso, "https://servidor-raro.example/crx")]}
    os.environ["APPDATA"] = os.path.join(tmp, "sin_firefox")
    try:
        todas = seg.auditar_extensiones("es")
    finally:
        seg.NAVEGADORES_CHROMIUM = seg_nav
        seg.leer_directivas_extensiones = seg_dir
    niveles = {e["id"]: e for e in todas}
    comprobar(niveles[ids["tienda"]]["nivel"] == "info" and sorted(niveles[ids["tienda"]]["perfiles"]) == ["Escuela", "Personal"],
              "la misma extension en dos perfiles sale UNA vez, con los dos perfiles")
    comprobar(niveles[ids["sin_tienda"]]["nivel"] == "alto", "cargada desde una carpeta con cookies y debugger: alto")
    comprobar(niveles[malicioso]["nivel"] == "alto" and niveles[malicioso]["origen"] == "directiva",
              "forzada por el registro en un equipo personal: alto (aunque no se haya descargado aun)")
    comprobar(niveles[ids["forzada"]]["nivel"] == "info", "la de la escuela: informativa")
    comprobar(niveles[ids["adblock"]]["nivel"] == "medio", "todas las webs + webRequest: para revisar")
    comprobar(niveles[ids["proxy"]]["nivel"] == "medio" and "ext_mot_proxy" in niveles[ids["proxy"]]["motivos"],
              "una VPN gratis con proxy: para revisar, y dice por que")
    comprobar("ext_mot_externa" in niveles[ids["externa"]]["motivos"], "la que puso otro programa lo dice")
    comprobar(todas[0]["nivel"] == "alto" and todas[-1]["nivel"] == "info", "ordenadas de mas a menos grave")

    print("== Extensiones: Firefox ==")
    perfil_ff = os.path.join(tmp, "ff", "Mozilla", "Firefox", "Profiles", "abc.default")
    escribir_json(os.path.join(perfil_ff, "extensions.json"), {"addons": [
        {"id": "ublock@x", "type": "extension", "location": "app-profile", "active": True, "signedState": 2,
         "defaultLocale": {"name": "uBlock"}, "userPermissions": {"permissions": ["webRequest"], "origins": ["<all_urls>"]}},
        {"id": "raro@x", "type": "extension", "location": "app-profile", "active": True, "signedState": 0,
         "defaultLocale": {"name": "Sin firmar"}},
        {"id": "tema@x", "type": "theme", "location": "app-profile"},
        {"id": "pocket@mozilla", "type": "extension", "location": "app-builtin"}]})
    os.environ["APPDATA"] = os.path.join(tmp, "ff")
    ff = {e["id"]: e for e in seg._leer_firefox()}
    comprobar(set(ff) == {"ublock@x", "raro@x"}, f"lee las extensiones y salta temas e integradas ({sorted(ff)})")
    comprobar(ff["raro@x"]["origen"] == "sin_tienda" and seg.evaluar_extension(ff["raro@x"])[0] == "alto",
              "una sin firmar: alto")

    print("== Extensiones: los navegadores de este equipo (solo que no reviente) ==")
    os.environ["APPDATA"] = os.environ.get("APPDATA_REAL", os.path.expandvars("%USERPROFILE%\\AppData\\Roaming"))
    reales = seg.auditar_extensiones("es")
    comprobar(isinstance(reales, list) and all({"nivel", "motivos", "perfiles"} <= set(e) for e in reales),
              f"lee {len(reales)} extensiones con su nivel")

    print("== Accesos directos: crear unos de verdad con Windows ==")
    carpeta = os.path.join(tmp, "Escritorio")
    os.makedirs(carpeta)
    existe = os.path.join(tmp, "programa_que_existe.exe")
    open(existe, "wb").close()
    borrado = os.path.join(tmp, "programa_borrado.exe")
    open(borrado, "wb").close()
    letra_libre = next(l for l in "QXYZWVUTS" if not os.path.exists(f"{l}:\\"))
    accesos = {"Funciona": existe, "Roto": borrado, "Carpeta": tmp,
               "Disco desenchufado": f"{letra_libre}:\\juego\\juego.exe"}
    script = "$s = New-Object -ComObject WScript.Shell;"
    for nombre, destino in accesos.items():
        script += (f"$l = $s.CreateShortcut('{os.path.join(carpeta, nombre + '.lnk')}');"
                   f"$l.TargetPath = '{destino}'; $l.Save();")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=60,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    creados = sorted(f for f in os.listdir(carpeta) if f.endswith(".lnk"))
    comprobar(len(creados) >= 3, f"Windows creo los accesos ({creados})")
    os.remove(borrado)                                          # ahora el acceso "Roto" apunta a la nada
    with open(os.path.join(carpeta, "Basura.lnk"), "wb") as f:  # un .lnk que no lo es
        f.write(b"esto no es un acceso directo")

    comprobar(opt.leer_destino_lnk(os.path.join(carpeta, "Funciona.lnk")) == ("local", existe),
              "lee el destino igual que Windows")
    comprobar(opt.leer_destino_lnk(os.path.join(carpeta, "Basura.lnk"))[0] == "invalido",
              "un archivo que no es un .lnk: invalido, sin reventar")
    rotos = opt.buscar_accesos_rotos(carpetas=[(carpeta, "escritorio", False, False)])
    nombres = [r["nombre"] for r in rotos]
    comprobar(nombres == ["Roto"], f"solo marca el que apunta a algo borrado ({nombres})")
    comprobar(rotos and rotos[0]["destino"] == borrado and rotos[0]["lugar"] == "escritorio",
              "con su destino y su lugar")
    comprobar("Disco desenchufado" not in nombres, "uno de un disco que no esta conectado NO se marca")

    print("== Accesos directos: los de este equipo (solo leer) ==")
    reales = opt.buscar_accesos_rotos()
    comprobar(isinstance(reales, list), f"busca en el Escritorio y el menu Inicio ({len(reales)} rotos)")
    comprobar(all(not os.path.exists(r["destino"]) for r in reales), "todos los que marca apuntan de verdad a nada")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
