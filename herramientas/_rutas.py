# -*- coding: utf-8 -*-
"""Las rutas del proyecto, para las herramientas.

Antes cada herramienta se las arreglaba sola, y de tres formas distintas:

    sys.path.insert(0, ".")                                  # depende del cwd
    sys.path.insert(0, dirname(dirname(abspath(__file__))))   # no depende
    open("main.py")                                          # depende del cwd

Las que dependian del directorio actual funcionaban solo porque
Verificar_Todo.bat hace cd a la raiz antes de llamarlas. Correr una a mano
desde otra carpeta y ya fallaba. Y al mover el codigo a codigo/ habia que
tocar las veintidos, cada una a su manera.

Ahora todas piden lo mismo aqui y ninguna depende de donde se la llame.

Empieza con guion bajo para que no la confundan con un banco de pruebas:
las herramientas de verdad se llaman prueba_* / revisar_* / verificar_*, y
la seccion 5 de auditoria.py se queja de cualquiera de esas que nadie
invoque desde el .bat.
"""
import os
import sys

# .../TechClean/herramientas/_rutas.py  ->  .../TechClean
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CODIGO = os.path.join(RAIZ, "codigo")
HERRAMIENTAS = os.path.join(RAIZ, "herramientas")
COMPILAR = os.path.join(RAIZ, "compilar")
DOCUMENTACION = os.path.join(RAIZ, "documentacion")
ASSETS = os.path.join(RAIZ, "assets")

# Los modulos de la app, en el orden en que conviene leerlos.
MODULOS = ["main.py", "main_admin.py", "optimizer.py", "system_monitor.py",
           "idiomas.py", "widget.py", "tray.py", "autopilot.py", "privacy.py",
           "report.py", "preferences.py", "deshacer.py", "tecnico.py",
           "rutas.py", "build_config.py"]


def poner_en_ruta():
    """Deja codigo/ al frente de sys.path para poder importar los modulos.

    Se llama antes de `import main`. Va al frente y no al final para que un
    paquete instalado que se llamara igual que uno nuestro no gane."""
    if CODIGO not in sys.path:
        sys.path.insert(0, CODIGO)
    return CODIGO


def fuente(nombre):
    """Ruta a un .py de la app. Ej: fuente("main.py")"""
    return os.path.join(CODIGO, nombre)


def leer(nombre):
    """El texto de un .py de la app, para analizarlo con ast o expresiones."""
    import io
    with io.open(fuente(nombre), encoding="utf-8") as f:
        return f.read()


def modulos_existentes():
    """Los de MODULOS que de verdad estan en disco.

    build_config.py lo reescriben los generadores, y una compilacion
    interrumpida en mal momento podria dejarlo a medias o no dejarlo: una
    herramienta no deberia reventar por eso."""
    return [n for n in MODULOS if os.path.exists(fuente(n))]
