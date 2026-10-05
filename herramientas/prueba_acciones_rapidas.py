# -*- coding: utf-8 -*-
"""Comprueba lo que se puede hacer sin buscar por las pantallas (1.7.0).

  * Buscador Ctrl+K: que encuentre con tildes o sin ellas, en los dos
    idiomas, con faltas de ortografia, y que Enter haga lo elegido.
  * Atajo de teclado global: que se registre, que diga "ocupado" cuando
    otro programa ya tiene esa combinacion (Windows solo deja a uno), y
    que al apagarlo se suelte de verdad.
  * Bandeja: "Liberar RAM" y "Limpieza rapida" en el menu, y que el
    resultado vaya al historial como RAM, no como espacio de disco.
  * Novedades: solo a quien actualiza, y una sola vez.
  * Importar ajustes: que un archivo con basura no rompa la app.
  * Cambiar de pantalla: la vieja se destruye DESPUES de dibujar la nueva.

No libera RAM ni notifica de verdad: esas partes son de mentira. No pulsa
teclas (pulsar Ctrl+Alt+algo de verdad le llegaria al programa que tengas
delante).

Uso:  python herramientas/prueba_acciones_rapidas.py
"""
import json
import os
import sys
import tempfile
import time

perfil = tempfile.mkdtemp(prefix="tcp_rapidas_")
os.environ["APPDATA"] = perfil
os.makedirs(os.path.join(perfil, "TechClean"), exist_ok=True)
json.dump({"idioma": "es", "idioma_preguntado": True, "widget_visible": False,
           "ultima_version_vista": "1.6.0"},
          open(os.path.join(perfil, "TechClean", "preferencias.json"), "w", encoding="utf-8"))

import _rutas
_rutas.poner_en_ruta()
import atajos
import preferences as prefs
import main
from idiomas import t

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def correr(app, segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        app.update()
        time.sleep(0.01)


print("== Buscador: la busqueda ==")
nada = lambda: None
entradas = [("Liberar RAM", "Optimizar", "ram memoria memory liberar free", nada),
            ("Energía", "Pantalla", "energia power bios bateria battery", nada),
            ("Limpiar la caché DNS", "Optimizar", "dns cache internet", nada),
            ("Analizar el Wi-Fi", "Gaming", "wifi wi-fi senal signal", nada),
            ("Liberación profunda de RAM", "Optimizar", "ram memoria profunda deep", nada)]
titulos = lambda r: [e[0] for e in r]
comprobar(len(main.buscar_en_paleta(entradas, "")) == len(entradas), "sin escribir nada: lo ensena todo")
comprobar(titulos(main.buscar_en_paleta(entradas, "ram"))[:2] == ["Liberar RAM", "Liberación profunda de RAM"],
          "'ram': las dos de RAM")
comprobar(titulos(main.buscar_en_paleta(entradas, "energia")) == ["Energía"], "'energia' encuentra 'Energía' (sin tilde)")
comprobar(titulos(main.buscar_en_paleta(entradas, "CACHÉ")) == ["Limpiar la caché DNS"], "mayusculas y tildes dan igual")
comprobar(titulos(main.buscar_en_paleta(entradas, "memory")) [:1] == ["Liberar RAM"], "en ingles por los sinonimos")
comprobar(titulos(main.buscar_en_paleta(entradas, "liberar ram"))[0] == "Liberar RAM",
          "varias palabras: primero lo que empieza asi")
comprobar(titulos(main.buscar_en_paleta(entradas, "memroia"))[:1] in (["Liberar RAM"], ["Liberación profunda de RAM"]),
          "con una falta de ortografia ('memroia') tambien encuentra")
comprobar(main.buscar_en_paleta(entradas, "xylofono") == [], "algo que no existe: nada")

print("== Atajo de teclado: registrar y soltar ==")
a = atajos.AtajoGlobal("ctrl+alt+f10", lambda: None)
comprobar(a.iniciar(), "se registra")
b = atajos.AtajoGlobal("ctrl+alt+f10", lambda: None)
comprobar(not b.iniciar(), "la misma combinacion por segunda vez: Windows la rechaza (ocupada)")
a.detener()
comprobar(not a.activo, "al detenerlo queda inactivo")
c = atajos.AtajoGlobal("ctrl+alt+f10", lambda: None)
comprobar(c.iniciar(), "y queda libre para volver a registrarla")
c.detener()
comprobar(not atajos.AtajoGlobal("no+existe", lambda: None).iniciar(), "una combinacion desconocida: False, sin reventar")
comprobar(all(atajos.texto_combinacion(k) for k in atajos.COMBINACIONES), "todas tienen texto para ensenar")

print("== Importar ajustes ==")
aceptadas, descartadas = prefs.filtrar_importables({
    "umbral_ram_auto": 80, "auto_ram_activa": False, "alerta_temp_cpu": 85, "icono_bandeja_metrica": "ram",
    "umbral_salud_disco": "alto", "auto_ram_activa_x": True, "avisos_disco": {"C:": 1},
    "dias_reinicio": True, "widget_metricas": ["cpu"], "idioma": "en"})
comprobar(aceptadas == {"umbral_ram_auto": 80, "auto_ram_activa": False, "alerta_temp_cpu": 85,
                        "icono_bandeja_metrica": "ram", "widget_metricas": ["cpu"], "idioma": "en"},
          f"se queda solo con ajustes conocidos y del tipo correcto ({sorted(aceptadas)})")
comprobar(set(descartadas) == {"umbral_salud_disco", "auto_ram_activa_x", "avisos_disco", "dias_reinicio"},
          "descarta un texto donde va un numero, claves inventadas, registros del otro equipo y un True donde va un numero")
comprobar(prefs.filtrar_importables([1, 2]) == ({}, [1, 2]), "algo que no es un diccionario: nada")

print("== La app: cambiar de pantalla ==")
app = main.TechCleanApp()
app.geometry("1300x850+40+40")
correr(app, 1.0)
vieja = app.contenido
app.mostrar_reporte()
comprobar(vieja.winfo_exists() and not vieja.winfo_ismapped(),
          "la pantalla vieja se esconde al instante (aun no se destruye)")
correr(app, 0.6)
comprobar(not vieja.winfo_exists(), "y se destruye en cuanto la nueva esta dibujada")
comprobar(app.contenido.winfo_exists() and app.contenido is not vieja, "la nueva usa su propio marco")

print("== La app: novedades ==")
correr(app, 1.2)          # la comprobacion salta a los 1.5 s de abrir
ventanas = [w for w in app.winfo_children() if isinstance(w, main.ctk.CTkToplevel)]
comprobar(any("1.7.0" in w.title() for w in ventanas), "quien venia de la 1.6.0 ve las novedades")
comprobar(prefs.cargar().get("ultima_version_vista") == main.APP_VERSION, "y se apunta que ya las vio")
for w in ventanas:
    w.destroy()
antes = len(app.winfo_children())
app._mostrar_novedades_si_toca()
comprobar(len(app.winfo_children()) == antes, "la segunda vez ya no salen")
app.prefs["ultima_version_vista"] = ""
app._habia_preferencias = False
app._mostrar_novedades_si_toca()
comprobar(len(app.winfo_children()) == antes, "quien la estrena (sin preferencias de antes) no ve 'novedades'")
comprobar(app.prefs["ultima_version_vista"] == main.APP_VERSION, "pero queda apuntado para la proxima version")

print("== La app: buscador Ctrl+K ==")
app._abrir_paleta()
correr(app, 0.4)
paleta = getattr(app, "_paleta", None)
comprobar(paleta is not None and paleta.winfo_exists(), "se abre")
entrada = next(w for w in paleta.winfo_children() if isinstance(w, main.ctk.CTkEntry))
entrada.insert(0, "historial")
entrada._entry.event_generate("<KeyRelease>", keysym="l")
correr(app, 0.2)
visibles = [w for w in paleta.winfo_children() if isinstance(w, main.ctk.CTkButton) and w.winfo_ismapped()]
comprobar(visibles and t("nav_historial") in visibles[0].cget("text"),
          f"'historial' pone primero la pantalla Historial ({visibles[0].cget('text') if visibles else None})")
app._abrir_paleta()
comprobar(sum(1 for w in app.winfo_children() if isinstance(w, main.ctk.CTkToplevel) and w.winfo_exists()) == 1,
          "Ctrl+K con el buscador ya abierto no abre otro")
entrada._entry.event_generate("<Return>")
correr(app, 0.5)
comprobar(not paleta.winfo_exists(), "Enter cierra el buscador")
comprobar(hasattr(app, "lbl_resumen_historial") and app.lbl_resumen_historial.winfo_exists(),
          "y abre lo elegido")
todas = app._entradas_paleta()
comprobar(all(callable(e[3]) and e[0] and e[1] for e in todas), f"las {len(todas)} entradas tienen titulo, lugar y accion")

print("== La app: bandeja y atajo ==")
if app.tray.icon is not None:
    textos = [str(i.text) for i in app.tray.icon.menu.items]
    comprobar(t("tray_liberar_ram") in textos and t("tray_limpieza_rapida") in textos,
              "el menu de la bandeja trae 'Liberar RAM' y 'Limpieza rapida'")
avisos = []
app._notificar = lambda titulo, texto: avisos.append((titulo, texto)) or True
llamadas = []
original = main.opt.liberar_memoria


def liberar_falso(nivel="normal", exclude_pids=None):
    llamadas.append(exclude_pids)
    time.sleep(0.3)
    return {"liberado": 700 * 1024 * 1024, "uso_antes": 70.0, "uso_despues": 55.0, "comando": "falso"}


main.opt.liberar_memoria = liberar_falso
try:
    app._liberar_ram_rapida("atajo")
    app._liberar_ram_rapida("atajo")          # pulsado dos veces seguidas
    correr(app, 1.0)
finally:
    main.opt.liberar_memoria = original
comprobar(len(llamadas) == 1, "pulsar dos veces seguidas no libera dos veces a la vez")
comprobar(avisos and "700" in avisos[-1][1], f"avisa con una notificacion ({avisos[-1][1] if avisos else None})")
ultima = app.reporte.entries[-1] if app.reporte.entries else {}
comprobar(ultima.get("bytes_ram") == 700 * 1024 * 1024 and not ultima.get("bytes_liberados"),
          "en el historial va como RAM, no como espacio de disco")

ajena = atajos.AtajoGlobal("ctrl+shift+r", lambda: None)
ocupada_por_otro = ajena.iniciar()
app.prefs.update({"atajo_ram_activo": True, "atajo_ram_combinacion": "ctrl+shift+r"})
if ocupada_por_otro:
    comprobar(app._aplicar_atajo_ram() == "ocupado", "si otro programa tiene la combinacion: 'ocupado'")
    ajena.detener()
estado = app._aplicar_atajo_ram()
comprobar(estado in ("activo", "ocupado"), f"con la combinacion libre: {estado}")
hilo = app.atajo_ram._hilo if app.atajo_ram else None
app.prefs["atajo_ram_activo"] = False
comprobar(app._aplicar_atajo_ram() == "apagado" and app.atajo_ram is None, "al apagarlo: 'apagado'")
time.sleep(0.2)
comprobar(hilo is None or not hilo.is_alive(), "y su hilo termina (no queda nada escuchando)")

app.destroy()
print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
