# -*- coding: utf-8 -*-
"""Comprueba el analizador de disco de la 1.8.0 (codigo/disco.py) y lo que
lo rodea, sin tocar nada fuera de una carpeta temporal.

  * Que cuente bien: en una carpeta inventada con tamaños conocidos, los
    totales de cada carpeta, los archivos más grandes y el reparto por tipo.
  * Que NO entre en uniones (junctions): una unión dentro del árbol apunta a
    una carpeta con un archivo enorme; si se contara, el total saldría mal
    (y en un disco de verdad, contaría cosas dos veces o en bucle).
  * Que descontar un archivo borrado deje los totales igual que si se
    volviera a recorrer.
  * Que las cachés de sombreadores solo se limpien de juegos DESINSTALADOS.
  * Qué se ofrece mandar a la papelera desde Espacio en disco (nada de
    Windows, programas, juegos ni AppData) y que la papelera solo cuente
    lo que de verdad se fue.

Uso:  python herramientas/prueba_disco.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import _rutas
_rutas.poner_en_ruta()
import disco
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def escribir(ruta, tam):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(b"x" * tam)


base = tempfile.mkdtemp(prefix="tc_disco_")
fuera = tempfile.mkdtemp(prefix="tc_disco_fuera_")
try:
    print("== Recorrer y sumar ==")
    raiz = os.path.join(base, "raiz")
    escribir(os.path.join(raiz, "suelto.txt"), 100)
    escribir(os.path.join(raiz, "videos", "peli.mp4"), 5000)
    escribir(os.path.join(raiz, "videos", "clip.MKV"), 3000)
    escribir(os.path.join(raiz, "juego", "datos", "pak0.pak"), 8000)
    escribir(os.path.join(raiz, "juego", "datos", "sub", "registro.etl"), 700)
    escribir(os.path.join(raiz, "juego", "sin_extension"), 50)
    os.makedirs(os.path.join(raiz, "vacia"))
    # Una unión que lleva FUERA del árbol, a un archivo grande: no se cuenta.
    escribir(os.path.join(fuera, "enorme.bin"), 100_000)
    union = os.path.join(raiz, "union")
    r = subprocess.run(["cmd", "/c", "mklink", "/J", union, fuera], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    hay_union = r.returncode == 0 and os.path.isdir(union)

    arbol = disco.analizar(raiz, hilos=4)
    total = 100 + 5000 + 3000 + 8000 + 700 + 50
    comprobar(arbol.bytes == total, f"el total es la suma de los archivos ({arbol.bytes} == {total})")
    comprobar(arbol.n_archivos == 6, f"cuenta 6 archivos ({arbol.n_archivos})")
    if hay_union:
        comprobar(arbol.buscar(union) is None, "no entra en la unión (lo de dentro es de otro sitio)")
    else:
        print("  (no se pudo crear la unión: se salta esa comprobación)")
    juego = arbol.buscar(os.path.join(raiz, "juego"))
    comprobar(juego is not None and arbol.total[juego] == 8750, "una carpeta suma todo lo que tiene debajo")
    comprobar(juego is not None and arbol.archivos_total[juego] == 3, "y cuenta sus archivos de todos los niveles")
    comprobar(arbol.propio[0] == 100 and arbol.archivos[0] == 1, "los archivos sueltos de la raíz, aparte")
    hijas = [arbol.nombres[h] for h in arbol.hijas_de(0)]
    comprobar(hijas[:2] == ["juego", "videos"], f"las subcarpetas, de la que más ocupa a la que menos ({hijas})")
    sub = arbol.buscar(os.path.join(raiz, "juego", "datos", "sub"))
    comprobar(sub is not None and arbol.ruta(sub) == os.path.join(raiz, "juego", "datos", "sub"),
              "ruta() rehace la ruta de una carpeta")
    comprobar(sub is not None and arbol.camino(sub)[0] == 0 and arbol.camino(sub)[-1] == sub,
              "camino() va de la raíz a la carpeta")
    comprobar(arbol.buscar(os.path.join(raiz, "VIDEOS")) is not None, "buscar() no distingue mayúsculas")
    comprobar([os.path.basename(r) for _, r in arbol.grandes[:3]] == ["pak0.pak", "peli.mp4", "clip.MKV"],
              "los archivos más grandes, en orden")
    comprobar(arbol.tipos["videos"] == 8000 and arbol.tipos["juegos"] == 8000
              and arbol.tipos["registros"] == 700 and arbol.tipos["otros"] == 50
              and arbol.tipos["documentos"] == 100, f"el reparto por tipo ({arbol.tipos})")

    print("== Descontar lo borrado ==")
    peli = os.path.join(raiz, "videos", "peli.mp4")
    arbol.quitar_archivo(peli, 5000)
    comprobar(arbol.bytes == total - 5000, "el total baja lo que ocupaba")
    videos = arbol.buscar(os.path.join(raiz, "videos"))
    comprobar(arbol.total[videos] == 3000 and arbol.archivos_total[videos] == 1, "y su carpeta también")
    comprobar(all(r != peli for _, r in arbol.grandes), "deja de salir entre los más grandes")
    comprobar(arbol.tipos["videos"] == 3000, "y en el reparto por tipo")

    print("== Cancelar ==")
    parar = threading.Event()
    parar.set()
    cancelado = disco.analizar(raiz, cancelar=parar)
    comprobar(cancelado.cancelado, "un análisis cancelado lo dice (la interfaz no lo enseña a medias)")

    print("== Tipos y carpetas especiales ==")
    comprobar(disco.tipo_de("Pelicula.MP4") == "videos" and disco.tipo_de("data.ucas") == "juegos"
              and disco.tipo_de("setup.exe") == "programas" and disco.tipo_de("copia.7z") == "comprimidos"
              and disco.tipo_de("log.etl") == "registros" and disco.tipo_de(".gitignore") == "otros"
              and disco.tipo_de("SINEXT") == "otros", "tipo_de por extensión")
    comprobar(disco.es_de_la_nube(0x9000701A) and disco.es_de_la_nube(0x9000F01A)
              and not disco.es_de_la_nube(0xA0000003), "OneDrive y Dropbox son de la nube; una unión no")
    comprobar(disco.se_entra(0x10, 0) and not disco.se_entra(0x410, 0xA0000003)
              and not disco.se_entra(0x410, 0xA000000C) and disco.se_entra(0x431, 0x9000701A)
              and not disco.se_entra(0x400010, 0), "se entra en carpetas normales y de OneDrive; no en enlaces "
              "ni en las que están solo en la nube")

    print("== Cachés de sombreadores ==")
    biblioteca = os.path.join(base, "steam")
    escribir(os.path.join(biblioteca, "steamapps", "appmanifest_10.acf"), 10)
    escribir(os.path.join(biblioteca, "steamapps", "shadercache", "10", "a.bin"), 10)
    escribir(os.path.join(biblioteca, "steamapps", "shadercache", "20", "b.bin"), 10)
    escribir(os.path.join(biblioteca, "steamapps", "shadercache", "no_es_id", "c.bin"), 10)
    original = opt._bibliotecas_steam
    opt._bibliotecas_steam = lambda: [biblioteca]
    try:
        huerfanos = opt._sombreadores_huerfanos()
    finally:
        opt._bibliotecas_steam = original
    comprobar([os.path.basename(h) for h in huerfanos] == ["20"],
              f"solo la del juego desinstalado ({[os.path.basename(h) for h in huerfanos]})")

    print("== La papelera ==")
    eliminados, liberado, errores = opt.enviar_a_papelera([os.path.join(base, "no_existe.iso")])
    comprobar(eliminados == 0 and liberado == 0, "lo que no existía no cuenta como enviado")
finally:
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(fuera, ignore_errors=True)

print("== Qué se ofrece mandar a la papelera ==")
import main  # noqa: E402  (después de lo que no necesita la interfaz)
casa = os.path.expanduser("~")
for ruta, esperado, texto in (
        (os.path.join(casa, "Downloads", "pelicula.iso"), True, "lo de tus carpetas, sí"),
        (os.path.join(casa, "AppData", "Local", "cache.bin"), False, "los datos de las apps (AppData), no"),
        (os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "x.dll"), False, "Windows, no"),
        (r"C:\pagefile.sys", False, "pagefile.sys, no"),
        (r"C:\Program Files (x86)\Steam\steamapps\common\Juego\pak0.pak", False, "los juegos de Steam, no"),
        (r"D:\Juegos\steamapps\common\Juego\pak0.pak", False, "tampoco en otra unidad"),
        (os.path.join(os.path.dirname(casa), "OtraCuenta", "Documents", "x.pdf"), False, "lo de otra cuenta, no"),
        (r"D:\Copias\disco.vhdx", True, "una copia tuya en otra unidad, sí")):
    comprobar(main.puede_ir_a_papelera(ruta) == esperado, texto)

print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
