# -*- coding: utf-8 -*-
"""
Donde estan las cosas, segun como se este ejecutando la app.

Existe por un motivo concreto. Antes todos los .py vivian en la misma
carpeta que assets/, asi que para encontrar el icono bastaba con:

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ICON_PATH = os.path.join(BASE_DIR, "assets", "icono.ico")

Al mover el codigo a codigo/, eso empezaria a apuntar a codigo/assets — que
no existe. Y el sintoma seria de los malos: la app abre igual, sin icono y
sin sonido, y SOLO al correrla desde el codigo. Compilada seguiria bien,
porque PyInstaller descomprime todo junto. O sea que el fallo no aparece en
lo que se reparte, aparece en lo que usa quien esta programando.

Se pone en un modulo aparte, y no repetido en main.py y en tray.py, porque
una ruta calculada en dos sitios es una ruta que tarde o temprano se calcula
distinto en cada sitio.
"""
import os
import sys

# La carpeta donde estan los .py de la app.
CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))


def carpeta_recursos():
    """La carpeta que CONTIENE assets/.

    Compilada con PyInstaller --onefile, la app se descomprime entera en una
    carpeta temporal que el propio Python publica en sys._MEIPASS, y assets/
    queda ahi dentro (lo pone el --add-data de los generadores). Asi que ahi
    la raiz de recursos es _MEIPASS y no tiene nada que ver con __file__.

    Desde el codigo, assets/ esta en la raiz del proyecto: un nivel por
    encima de codigo/.
    """
    empaquetada = getattr(sys, "_MEIPASS", None)
    if empaquetada:
        return empaquetada
    return os.path.dirname(CARPETA_CODIGO)


def recurso(*partes):
    """Ruta a un archivo de assets/. Ej: recurso("icono.ico")

    No comprueba que exista a proposito: quien lo use ya tiene que estar
    preparado para que falte —el icono y el sonido son opcionales y la app
    arranca sin ellos— y una comprobacion aqui daria una falsa sensacion de
    garantia."""
    return os.path.join(carpeta_recursos(), "assets", *partes)
