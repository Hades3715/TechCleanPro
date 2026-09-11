# -*- coding: utf-8 -*-
"""Comprueba que limpiar temporales NO borre la propia app.

En la build --onefile, PyInstaller descomprime la aplicacion entera en
%TEMP%\\_MEIxxxxx. Si la limpieza borra esa carpeta, la app se rompe desde
adentro: los modulos que se importan tarde (ssl, por ejemplo) ya no
encuentran su archivo.

Trabaja sobre una carpeta temporal PROPIA, no sobre el %TEMP% real del
usuario: la prueba no debe borrarle nada a nadie.
"""
import os, sys, tempfile, shutil

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import optimizer as opt

banco = tempfile.mkdtemp(prefix="tcp_prueba_limpieza_")
gettempdir_real = tempfile.gettempdir
tempfile.gettempdir = lambda: banco          # la limpieza mira AQUI
opt.tempfile.gettempdir = lambda: banco

# 1) carpeta _MEI falsa, como la que crea PyInstaller
mei = os.path.join(banco, "_MEI99999")
os.makedirs(os.path.join(mei, "sub"), exist_ok=True)
protegidos = [os.path.join(mei, "_ssl.pyd"),
              os.path.join(mei, "sub", "python314.dll")]
for p in protegidos:
    with open(p, "wb") as f:
        f.write(b"x" * 5000)

# 2) temporales normales, que SI deben borrarse
basura = [os.path.join(banco, "algo.tmp"), os.path.join(banco, "otro.log")]
for p in basura:
    with open(p, "wb") as f:
        f.write(b"y" * 3000)

sys._MEIPASS = mei                            # simular que corremos congelados

print("=== antes ===")
for p in protegidos + basura:
    print(f"  {'[protegido]' if p in protegidos else '[borrable] '} {os.path.basename(p):16} existe={os.path.exists(p)}")

liberado, borrados, _ = opt.clear_temp_files()
print(f"\nlimpieza: {borrados} archivo(s), {liberado} bytes")

print("=== despues ===")
fallos = 0
for p in protegidos:
    vive = os.path.exists(p)
    if not vive:
        fallos += 1
    print(f"  [protegido] {os.path.basename(p):16} existe={vive}  {'OK' if vive else 'FALLO: la app se borro a si misma'}")
for p in basura:
    vive = os.path.exists(p)
    if vive:
        fallos += 1
    print(f"  [borrable]  {os.path.basename(p):16} existe={vive}  {'OK' if not vive else 'FALLO: no limpio nada'}")

tempfile.gettempdir = gettempdir_real
shutil.rmtree(banco, ignore_errors=True)
print(f"\nRESULTADO: {'sin fallos' if fallos == 0 else str(fallos) + ' FALLOS'}")
sys.exit(1 if fallos else 0)
