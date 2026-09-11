# -*- coding: utf-8 -*-
"""Comprueba que los .exe ya compilados lleven dentro TODO lo que importan.

Por que hace falta una comprobacion aparte para esto:

PyInstaller decide que meter en el paquete leyendo los imports del codigo. Si
por lo que sea deja fuera un modulo, el codigo fuente sigue funcionando
perfectamente —el modulo esta instalado en el equipo— y el fallo aparece SOLO
en el .exe que se reparte, en el momento en que alguien entra a la pantalla
que lo usa. Es el peor tipo de fallo: no se puede reproducir probando.

Ya paso una vez con los imports tardios de ssl. Y la consola trajo un import
nuevo, difflib, que solo se usa cuando alguien escribe un comando mal: si
faltara, el error saldria justo cuando la persona ya se habia equivocado.

Como se comprueba, sin compilar nada y sin tocar %TEMP%:

  1. Se leen los imports de nivel superior de los modulos de la app.
  2. Se abre el .exe ya compilado y se lee su archivo interno (el CArchive) y
     el PYZ que lleva dentro, que es donde van los modulos de Python.
  3. Se compara.

Es a proposito NO destructiva. La otra prueba del .exe (prueba_frozen.py)
limpia los temporales de verdad, porque es lo que reproducia su bug — pero
eso se lleva por delante cualquier archivo que otro programa tenga abierto
en %TEMP%, asi que esa se corre a mano y esta se puede correr siempre.

Uso:  python herramientas\\revisar_empaquetado.py
"""
import ast
import io
import os
import sys
import tempfile
import zipfile

import _rutas
RAIZ = _rutas.RAIZ
EXES = ["TechClean_ES.exe", "TechClean_EN.exe", "TechClean_Admin.exe"]

# Modulos propios de la app: se miran sus imports.
# La lista sale de _rutas para que no haya dos listas de modulos que se
# puedan desincronizar: si manana se anade un modulo y solo se apunta en un
# sitio, esta comprobacion dejaria de vigilarlo sin decir nada.
PROPIOS = _rutas.MODULOS

# Estos viven en el CArchive de fuera (extensiones compiladas, DLL) o son
# parte del propio arranque, no modulos del PYZ.
FUERA_DEL_PYZ = {"tkinter", "_tkinter", "ctypes", "winreg", "winsound",
                 "sqlite3", "_socket", "select"}

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


def imports_de(ruta):
    """Los modulos que un archivo importa, incluidos los imports ANIDADOS.

    Los anidados son justo los peligrosos: un `import ssl` dentro de una
    funcion se ejecuta la primera vez que se entra ahi, no al arrancar, asi
    que si falta no se nota hasta que alguien usa esa funcion concreta."""
    arbol = ast.parse(io.open(ruta, encoding="utf-8").read(), ruta)
    encontrados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                encontrados.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module:
                encontrados.add(nodo.module.split(".")[0])
    return encontrados


print("== Lo que la app importa ==")
necesarios = set()
for nombre in PROPIOS:
    ruta = _rutas.fuente(nombre)
    if not os.path.exists(ruta):
        continue
    necesarios |= imports_de(ruta)
# Los propios tambien tienen que estar dentro.
necesarios |= {os.path.splitext(n)[0] for n in PROPIOS
               if os.path.exists(_rutas.fuente(n))}
necesarios -= FUERA_DEL_PYZ
# Los puntos de ENTRADA no van en el PYZ: son el script principal del .exe.
# Y main_admin es el punto de entrada de la OTRA edicion — que no este dentro
# de TechClean_ES.exe es exactamente lo correcto, no un fallo.
necesarios.discard("main")
necesarios.discard("main_admin")
print(f"  {len(necesarios)} modulos de nivel superior")

print("\n== Ejecutables encontrados ==")
presentes = [e for e in EXES if os.path.exists(os.path.join(RAIZ, e))]
for e in EXES:
    if e in presentes:
        tam = os.path.getsize(os.path.join(RAIZ, e)) / 1_000_000
        print(f"  [OK  ] {e:24} {tam:.1f} MB")
    else:
        print(f"  [info ] {e:24} no compilado todavia (se omite)")

if not presentes:
    print("\nNo hay ningun .exe compilado. Corre Generar_App_Instalable.bat")
    print("y vuelve a pasar esta comprobacion antes de publicar.")
    sys.exit(0)

try:
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
except ImportError:
    print("\nPyInstaller no esta instalado: no se puede abrir el .exe por dentro.")
    print("  pip install pyinstaller")
    sys.exit(0)


def modulos_dentro(ruta_exe):
    """Todo lo que el .exe lleva dentro, mirando los TRES sitios donde
    PyInstaller reparte los modulos.

    Esto costo un rato de falsos positivos. Mirando solo el PYZ, la
    comprobacion decia que faltaban io, os, re y traceback — y no faltaban:

      * el PYZ lleva los modulos de la app y los de terceros;
      * base_library.zip, que va en el archivo de fuera, lleva el nucleo de
        la biblioteca estandar (io, os, re, traceback y unos 25 mas);
      * y sys, math o time no estan en ningun archivo porque van COMPILADOS
        dentro del propio interprete.

    Una comprobacion que grita por siete modulos que si estan es peor que no
    tenerla: se aprende a ignorar la seccion, y el dia que falte uno de
    verdad tampoco se mira.
    """
    archivo = CArchiveReader(ruta_exe)
    dentro = set(archivo.toc)

    if "PYZ.pyz" in archivo.toc:
        # El PYZ se extrae a un archivo porque ZlibArchiveReader lee de disco.
        temporal = os.path.join(tempfile.gettempdir(),
                                "tc_pyz_" + os.path.basename(ruta_exe) + ".pyz")
        try:
            io.open(temporal, "wb").write(archivo.extract("PYZ.pyz"))
            dentro |= set(ZlibArchiveReader(temporal).toc)
        finally:
            try:
                os.remove(temporal)
            except OSError:
                pass

    if "base_library.zip" in archivo.toc:
        temporal = os.path.join(tempfile.gettempdir(),
                                "tc_base_" + os.path.basename(ruta_exe) + ".zip")
        try:
            io.open(temporal, "wb").write(archivo.extract("base_library.zip"))
            with zipfile.ZipFile(temporal) as z:
                dentro |= {n.split("/")[0].split(".")[0] for n in z.namelist()}
        finally:
            try:
                os.remove(temporal)
            except OSError:
                pass

    # Y los que van dentro del interprete, sin archivo que los contenga.
    dentro |= set(sys.builtin_module_names)
    return dentro


for nombre in presentes:
    print(f"\n== {nombre} ==")
    dentro = modulos_dentro(os.path.join(RAIZ, nombre))
    print(f"      {len(dentro)} entradas empaquetadas")
    faltan = sorted(m for m in necesarios
                    if m not in dentro and not any(n.startswith(m + ".") for n in dentro))
    comprobar(f"{nombre}: lleva dentro todo lo que importa", not faltan,
              f"FALTAN: {faltan}" if faltan else f"{len(necesarios)} modulos comprobados")

    # Los que mas duelen, uno por uno, para que el mensaje diga cual.
    for critico in ("difflib", "idiomas", "deshacer", "tecnico", "widget",
                    "optimizer", "preferences"):
        if critico not in necesarios:
            continue
        hay = critico in dentro or any(n.startswith(critico + ".") for n in dentro)
        comprobar(f"{nombre}: {critico}", hay)

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
