# -*- coding: utf-8 -*-
"""
Idioma de ESTA compilacion.

Se publican dos ejecutables separados de la edicion cliente — uno en espanol
y otro en ingles — y cada quien descarga el que le sirve por el nombre del
archivo. Por eso la edicion cliente no lleva selector de idioma dentro.

Generar_App_Instalable.bat reescribe SOLO este archivo antes de cada
compilacion, y lo deja de vuelta en "es" al terminar. Se aisla aqui, en vez
de tocar main.py, para que una compilacion interrumpida no deje el codigo
principal modificado.

La edicion admin ignora este valor: conserva el selector de idioma porque es
una sola build, del propio desarrollador.
"""

IDIOMA = "es"
