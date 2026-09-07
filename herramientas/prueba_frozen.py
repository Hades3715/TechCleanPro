# -*- coding: utf-8 -*-
"""Verifica el arreglo DENTRO de un ejecutable congelado con PyInstaller.

El bug de "la app se borra a si misma" no se puede reproducir desde el
codigo fuente: solo existe en la build --onefile, donde la aplicacion vive
descomprimida en %TEMP%\\_MEIxxxxx. Por eso esta prueba se compila y se
ejecuta como .exe.

Hace exactamente lo que hacia el usuario cuando aparecio el fallo:
  1. limpia los archivos temporales
  2. despues intenta usar la prueba de velocidad (que importa ssl tarde)

Escribe el resultado en un archivo junto al .exe, porque limpiar %TEMP%
borra cualquier salida que estuviera ahi — que fue justamente como se
descubrio el problema.
"""
import os, sys

destino = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                       "resultado_frozen.txt")
lineas = []


def anotar(txt):
    print(txt)
    lineas.append(txt)


anotar(f"congelado: {getattr(sys, 'frozen', False)}")
mei = getattr(sys, "_MEIPASS", None)
anotar(f"_MEIPASS: {mei}")

if not mei:
    anotar("ERROR: no corre congelado, la prueba no aplica")
else:
    antes = len(os.listdir(mei))
    anotar(f"archivos en _MEIPASS antes: {antes}")

    import optimizer as opt
    liberado, borrados, _ = opt.clear_temp_files()
    anotar(f"limpieza: {borrados} archivos, {liberado/1_000_000:.1f} MB")

    if os.path.isdir(mei):
        despues = len(os.listdir(mei))
        anotar(f"archivos en _MEIPASS despues: {despues}")
        anotar(f"la app sobrevivio: {despues >= antes}")
    else:
        anotar("FALLO: _MEIPASS fue BORRADO")
        despues = 0

    # El tono de audio se sintetiza con imports TARDIOS (io/math/struct/wave)
    # dentro de la propia funcion. PyInstaller los detecta aunque esten
    # anidados, pero eso hay que comprobarlo: si alguno faltara, la prueba de
    # sonido reventaria solo en el .exe repartido, nunca aqui en el codigo.
    try:
        datos = opt.generar_wav_tono()
        cabecera_ok = datos[:4] == b"RIFF" and datos[8:12] == b"WAVE"
        anotar(f"tono WAV en el .exe: {len(datos)} bytes, cabecera {'OK' if cabecera_ok else 'MAL'}")
        tono_ok = cabecera_ok and len(datos) > 10000
    except Exception as e:
        anotar(f"FALLO generando el tono: {type(e).__name__}: {e}")
        tono_ok = False

    # Los modulos nuevos: si PyInstaller no los empaquetara, la pantalla que
    # los usa reventaria solo en el .exe repartido, nunca en el codigo.
    try:
        import deshacer, tecnico
        reg = deshacer.RegistroDeshacer()
        reg.anotar("animaciones", {"estaban_reducidas": True}, "prueba en el exe")
        filas = tecnico.comparar_fotos({"ram_pct": 80}, {"ram_pct": 60})
        entradas = tecnico.inspeccionar_arranque()
        anotar(f"deshacer y tecnico en el .exe: OK "
               f"({len(filas)} campo(s) comparados, {len(entradas)} entradas de arranque)")
        modulos_ok = len(filas) == 1
    except Exception as e:
        anotar(f"FALLO con los modulos nuevos: {type(e).__name__}: {e}")
        modulos_ok = False

    # La prueba de fuego: un import tardio, como el que reventaba antes.
    try:
        import ssl
        anotar(f"import ssl tardio: OK ({ssl.OPENSSL_VERSION})")
        import urllib.request
        with urllib.request.urlopen("https://api.github.com", timeout=10) as r:
            anotar(f"HTTPS despues de limpiar: OK ({r.status})")
        ok = True
    except Exception as e:
        anotar(f"FALLO en import tardio: {type(e).__name__}: {e}")
        ok = False

    anotar("")
    anotar("RESULTADO: " + ("ARREGLADO" if ok and tono_ok and modulos_ok and os.path.isdir(mei) else "SIGUE ROTO"))

with open(destino, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas))
