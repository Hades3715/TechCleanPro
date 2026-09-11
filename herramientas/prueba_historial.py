# -*- coding: utf-8 -*-
"""Banco de pruebas del historial que sobrevive al cierre de la app.

Antes todo lo que hacia la app se perdia al cerrarla, asi que era
imposible responder a la pregunta que de verdad importa: "¿mi equipo va
peor que hace tres meses?".

El archivo es JSON por lineas (una accion por linea) a proposito, no un
JSON grande: cada accion se anade al final sin releer nada, y si una
linea se corrompiera —un apagon a mitad de escritura— se descarta esa y
el resto del historial se sigue leyendo. Con un unico JSON grande, un
byte malo se llevaria por delante el archivo entero. Eso es justo lo que
comprueba la prueba 4.

Uso:  python herramientas\\prueba_historial.py
"""
import os
import sys
import tempfile

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import report as rep

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


carpeta = tempfile.mkdtemp(prefix="tcp_hist_")

print("== 1. Lo de una sesion se guarda y lo lee la siguiente ==")
sesion1 = rep.SessionReport(carpeta_datos=carpeta)
sesion1.add("Optimizar", "Limpiar temporales", "cmd1", True, "borrado", 5_000_000, 120)
sesion1.add("Optimizar", "Liberar RAM", "cmd2", True, "liberado", 300_000_000, 40)
sesion1.add("Reparar", "sfc", "cmd3", False, "fallo")

sesion2 = rep.SessionReport(carpeta_datos=carpeta)     # como si se reabriera la app
comprobar("la sesion nueva arranca vacia", sesion2.total_acciones() == 0)
anteriores = sesion2.historial_completo()
comprobar("pero ve las 3 acciones de la anterior", len(anteriores) == 3,
          f"{len(anteriores)} leidas")
comprobar("de lo mas nuevo a lo mas viejo",
          anteriores[0]["accion"] == "sfc" and anteriores[-1]["accion"] == "Limpiar temporales")

print("\n== 2. El resumen suma todas las sesiones ==")
sesion2.add("Optimizar", "Vaciar papelera", "cmd4", True, "vaciada", 1_000_000, 8)
resumen = sesion2.resumen_historial()
comprobar("cuenta las 4 acciones", resumen["acciones"] == 4, f"{resumen['acciones']}")
comprobar("suma el espacio de las dos sesiones", resumen["bytes"] == 306_000_000,
          f"{resumen['bytes']}")
comprobar("distingue 2 sesiones", resumen["sesiones"] == 2, f"{resumen['sesiones']}")
comprobar("los totales de LA SESION siguen siendo solo suyos",
          sesion2.total_acciones() == 1 and sesion2.total_bytes_liberados() == 1_000_000)

print("\n== 3. Se puede excluir lo de ahora ==")
solo_viejas = sesion2.historial_completo(solo_anteriores=True)
comprobar("deja fuera lo de esta sesion", len(solo_viejas) == 3, f"{len(solo_viejas)}")
comprobar("y no aparece la accion de ahora",
          all(e["accion"] != "Vaciar papelera" for e in solo_viejas))

print("\n== 4. Una linea corrupta no se lleva el archivo entero ==")
ruta = os.path.join(carpeta, rep.NOMBRE_ARCHIVO)
with open(ruta, "a", encoding="utf-8") as f:
    f.write('{"esto no es json valido...\n')
sesion2.add("Seguridad", "Revisar Defender", "cmd5", True, "ok")
recuperadas = sesion2.historial_completo()
comprobar("se salta la linea rota y lee el resto", len(recuperadas) == 5,
          f"{len(recuperadas)} de 5 buenas")
comprobar("incluida la que se escribio DESPUES de la rota",
          any(e["accion"] == "Revisar Defender" for e in recuperadas))

print("\n== 5. El archivo no crece sin freno ==")
grande = rep.SessionReport(carpeta_datos=tempfile.mkdtemp(prefix="tcp_hist2_"))
for i in range(120):
    grande.add("Prueba", f"accion {i}", "cmd", True, "ok")
sobrantes = grande.recortar_historial(limite=50)
comprobar("recorta lo que sobra", sobrantes == 70, f"quito {sobrantes}")
quedan = grande.historial_completo()
comprobar("deja exactamente el limite", len(quedan) == 50, f"{len(quedan)}")
comprobar("y conserva las MAS RECIENTES", quedan[0]["accion"] == "accion 119",
          f"la primera es {quedan[0]['accion']!r}")
comprobar("recortar de nuevo no hace nada", grande.recortar_historial(limite=50) == 0)

print("\n== 6. Exportar ==")
destino = os.path.join(carpeta, "salida.txt")
sesion2.export_txt(destino, incluir_historial=False)
texto_sesion = open(destino, encoding="utf-8").read()
comprobar("el reporte de sesion solo trae lo de ahora",
          "Vaciar papelera" in texto_sesion and "Limpiar temporales" not in texto_sesion)
sesion2.export_txt(destino, incluir_historial=True)
texto_todo = open(destino, encoding="utf-8").read()
comprobar("el historial completo los trae todos",
          "Vaciar papelera" in texto_todo and "Limpiar temporales" in texto_todo)
comprobar("y va de lo mas viejo a lo mas nuevo en el archivo",
          texto_todo.index("Limpiar temporales") < texto_todo.index("Vaciar papelera"))

print("\n== 7. Borrar ==")
comprobar("borra el archivo", sesion2.borrar_historial() is True)
comprobar("y ya no queda nada guardado", sesion2.historial_completo() == [])
comprobar("borrar cuando no hay nada tampoco falla", sesion2.borrar_historial() is True)

print("\n== 8. Sin carpeta no se toca el disco (para las pruebas) ==")
sin_disco = rep.SessionReport()
sin_disco.add("Prueba", "algo", "cmd", True, "ok")
comprobar("guarda en memoria", sin_disco.total_acciones() == 1)
comprobar("pero no lee ni escribe nada", sin_disco.historial_completo() == [])

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
