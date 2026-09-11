# -*- coding: utf-8 -*-
"""Banco de pruebas del registro de cambios reversibles.

Se comprueba con un OPTIMIZER DE MENTIRA: un objeto que apunta lo que le
piden en vez de hacerlo. Asi se puede verificar que deshacer llama a la
funcion correcta con los argumentos correctos sin cambiarle de verdad el
plan de energia ni parar servicios en el equipo de nadie.

Lo importante que se comprueba:
  * Que se guarde el valor ANTERIOR, no el nuevo. Sin eso no hay vuelta
    atras posible, y es el error facil de cometer.
  * Que deshacer llame a la funcion inversa correcta en cada tipo.
  * Que algo ya deshecho no se pueda deshacer otra vez — hacerlo dos
    veces no es inofensivo: volveria a aplicar lo contrario.
  * Que si la operacion falla, NO se marque como deshecha.
  * Que una linea corrupta no se lleve por delante el resto.

Uso:  python herramientas\\prueba_deshacer.py
"""
import os
import sys
import tempfile

import _rutas
RAIZ = _rutas.RAIZ
_rutas.poner_en_ruta()
import deshacer

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    print(f"  [{'OK  ' if condicion else 'FALLO'}] {descripcion}" + (f"   {detalle}" if detalle else ""))
    if not condicion:
        fallos.append(descripcion)


class OptimizerFalso:
    """Apunta lo que le piden en vez de tocar el sistema."""

    def __init__(self, todo_bien=True):
        self.llamadas = []
        self.todo_bien = todo_bien

    def _apuntar(self, nombre, *args, **kwargs):
        self.llamadas.append((nombre, args, kwargs))
        return self.todo_bien, f"{nombre}{args}"

    def set_power_plan(self, perfil):
        return self._apuntar("set_power_plan", perfil)

    def set_app_inicio_activa(self, nombre, comando, activar):
        self.llamadas.append(("set_app_inicio_activa", (nombre, comando, activar), {}))
        return self.todo_bien

    def set_servicio_windows(self, nombre, accion):
        return self._apuntar("set_servicio_windows", nombre, accion)

    def reducir_animaciones_ahora(self, activar_reduccion=True):
        return self._apuntar("reducir_animaciones_ahora", activar_reduccion)

    def set_inicio_rapido(self, activar):
        return self._apuntar("set_inicio_rapido", activar)

    def set_startup(self, habilitar):
        return self._apuntar("set_startup", habilitar)

    def crear_limpieza_programada(self, frecuencia="DAILY", hora="09:00"):
        return self._apuntar("crear_limpieza_programada", frecuencia, hora)

    def quitar_limpieza_programada(self):
        return self._apuntar("quitar_limpieza_programada")


carpeta = tempfile.mkdtemp(prefix="tcp_desh_")
reg = deshacer.RegistroDeshacer(carpeta_datos=carpeta)

print("== 1. Se guarda el valor ANTERIOR, que es lo que permite volver ==")
id_perfil = reg.anotar("perfil_energia",
                       {"anterior": "equilibrado", "nuevo": "rendimiento"},
                       "Perfil cambiado a Rendimiento")
comprobar("anotar devuelve un identificador", bool(id_perfil))
pendientes = reg.pendientes()
comprobar("queda un cambio pendiente", len(pendientes) == 1, f"{len(pendientes)}")
comprobar("guarda el plan que estaba antes",
          pendientes[0]["datos"]["anterior"] == "equilibrado")

falso = OptimizerFalso()
exito, clave, _ = reg.deshacer(id_perfil, falso)
comprobar("deshacer dice que fue bien", exito and clave == "desh_ok", clave)
comprobar("y pide volver al plan ANTERIOR, no al nuevo",
          falso.llamadas == [("set_power_plan", ("equilibrado",), {})],
          f"{falso.llamadas}")

print("\n== 2. Deshacer dos veces lo mismo no puede pasar ==")
comprobar("ya no aparece como pendiente", reg.pendientes() == [])
falso2 = OptimizerFalso()
exito2, clave2, _ = reg.deshacer(id_perfil, falso2)
comprobar("el segundo intento se rechaza", not exito2 and clave2 == "desh_no_encontrado", clave2)
comprobar("y no se llama a nada", falso2.llamadas == [], f"{falso2.llamadas}")

print("\n== 3. Cada tipo llama a su funcion inversa ==")
casos = [
    ("app_inicio", {"nombre": "Spotify", "comando": "C:\\sp.exe", "estaba_activa": True},
     ("set_app_inicio_activa", ("Spotify", "C:\\sp.exe", True), {})),
    ("servicio", {"nombre": "Spooler", "accion": "detener"},
     ("set_servicio_windows", ("Spooler", "iniciar"), {})),
    ("servicio", {"nombre": "Spooler", "accion": "iniciar"},
     ("set_servicio_windows", ("Spooler", "detener"), {})),
    ("animaciones", {"estaban_reducidas": False},
     ("reducir_animaciones_ahora", (False,), {})),
    ("inicio_rapido", {"estaba_activo": True},
     ("set_inicio_rapido", (True,), {})),
    ("inicio_automatico", {"estaba_activo": False},
     ("set_startup", (False,), {})),
    ("limpieza_programada", {"estaba_activa": True, "frecuencia": "WEEKLY", "hora": "07:30"},
     ("crear_limpieza_programada", ("WEEKLY", "07:30"), {})),
    ("limpieza_programada", {"estaba_activa": False},
     ("quitar_limpieza_programada", (), {})),
]
for tipo, datos, esperado in casos:
    identificador = reg.anotar(tipo, datos, f"prueba {tipo}")
    doble = OptimizerFalso()
    reg.deshacer(identificador, doble)
    comprobar(f"{tipo:22} -> {esperado[0]}{esperado[1]}",
              doble.llamadas == [esperado], f"llamo a {doble.llamadas}")

print("\n== 4. Si la operacion falla, el cambio sigue pendiente ==")
id_fallo = reg.anotar("perfil_energia", {"anterior": "silencioso"}, "prueba fallo")
roto = OptimizerFalso(todo_bien=False)
exito3, clave3, _ = reg.deshacer(id_fallo, roto)
comprobar("dice que fallo", not exito3 and clave3 == "desh_fallo", clave3)
comprobar("y NO lo marca como deshecho (se puede reintentar)",
          any(e["id"] == id_fallo for e in reg.pendientes()))
bueno = OptimizerFalso()
exito4, _, _ = reg.deshacer(id_fallo, bueno)
comprobar("al reintentar con exito, ahora si", exito4)

print("\n== 5. Un tipo desconocido no revienta ==")
comprobar("anotar un tipo inventado devuelve None",
          reg.anotar("tipo_que_no_existe", {}, "x") is None)

print("\n== 6. Una linea corrupta no se lleva el archivo ==")
ruta = os.path.join(carpeta, deshacer.NOMBRE_ARCHIVO)
with open(ruta, "a", encoding="utf-8") as f:
    f.write("{esto no es json\n")
id_tras_corrupcion = reg.anotar("animaciones", {"estaban_reducidas": True}, "despues de la rota")
pend = reg.pendientes()
comprobar("se lee lo que hay pese a la linea rota", len(pend) >= 1, f"{len(pend)} pendientes")
comprobar("incluida la escrita DESPUES de la rota",
          any(e["id"] == id_tras_corrupcion for e in pend))

print("\n== 7. El archivo no crece sin freno ==")
reg2 = deshacer.RegistroDeshacer(carpeta_datos=tempfile.mkdtemp(prefix="tcp_desh2_"))
for i in range(40):
    reg2.anotar("animaciones", {"estaban_reducidas": True}, f"cambio {i}")
sobran = reg2.recortar(limite=15)
comprobar("recorta lo que sobra", sobran == 25, f"quito {sobran}")
comprobar("deja el limite", len(reg2.pendientes()) == 15, f"{len(reg2.pendientes())}")
comprobar("conserva los MAS RECIENTES",
          reg2.pendientes()[0]["descripcion"] == "cambio 39",
          reg2.pendientes()[0]["descripcion"])

print("\n== 8. Sin carpeta no se toca el disco ==")
sin_disco = deshacer.RegistroDeshacer()
sin_disco.anotar("animaciones", {"estaban_reducidas": True}, "en el aire")
comprobar("no guarda nada", sin_disco.pendientes() == [])

print("\n== 9. Borrar el registro ==")
comprobar("borra", reg.borrar_todo() is True)
comprobar("queda vacio", reg.pendientes() == [])

print("\nRESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS: " + ", ".join(fallos)))
sys.exit(1 if fallos else 0)
