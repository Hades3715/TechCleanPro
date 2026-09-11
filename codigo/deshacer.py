"""
deshacer.py
Registro de cambios reversibles, con su vuelta atrás.

Por qué existe
--------------
TechClean se descarga como un `.exe` sin firma digital, de un desarrollador
que nadie conoce, y toca cosas del sistema: planes de energía, apps de
inicio, servicios, efectos visuales. Pedirle a alguien que confíe en eso a
ciegas es mucho pedir. Poder deshacerlo es la diferencia.

La regla de honestidad
----------------------
**No todo se puede deshacer, y decirlo importa más que la propia función.**
Un archivo temporal borrado no vuelve. La papelera vaciada tampoco. Un
proceso terminado no se resucita. Esta lista guarda SOLO lo que de verdad
se puede revertir, y la interfaz avisa de lo que no — en vez de dar un
botón de "Deshacer" que a veces miente.

Lo que sí se puede deshacer:

  * Perfil de energía          -> volver al plan que estaba antes
  * App de inicio deshabilitada-> volver a habilitarla
  * Servicio detenido/iniciado -> hacer lo contrario
  * Animaciones reducidas      -> volver a activarlas
  * Inicio rápido de Windows   -> volver a como estaba
  * Inicio automático de la app-> volver a como estaba
  * Limpieza programada        -> volver a como estaba

Lo que NO, y la app lo dice claro:

  * Archivos temporales borrados
  * Papelera vaciada
  * Caché e historial de navegadores
  * Procesos terminados
  * Archivos enviados a la papelera — estos no los deshace la app, pero
    siguen EN la papelera: se restauran desde Windows, y eso también se
    avisa.

Cómo se guarda
--------------
Igual que el historial: JSON por líneas dentro de %APPDATA%\\TechClean. Una
línea por cambio, se añade al final sin releer nada, y una línea corrupta
no se lleva por delante el resto.
"""

import json
import os
from datetime import datetime

NOMBRE_ARCHIVO = "deshacer.jsonl"

# Cuántos cambios reversibles se recuerdan. Pasado ese número se olvidan
# los más viejos: deshacer algo de hace tres meses casi nunca es lo que
# alguien quiere, y el archivo no puede crecer sin freno.
LIMITE = 200

# Cada tipo dice qué función lo revierte. La CLAVE de idiomas se guarda
# aquí y no el texto ya traducido: si se guardara el texto, un historial
# escrito en español se leería en español aunque la app estuviera en
# inglés.
TIPOS = {
    "perfil_energia": "desh_tipo_perfil",
    "app_inicio": "desh_tipo_app_inicio",
    "servicio": "desh_tipo_servicio",
    "animaciones": "desh_tipo_animaciones",
    "inicio_rapido": "desh_tipo_inicio_rapido",
    "inicio_automatico": "desh_tipo_inicio_automatico",
    "limpieza_programada": "desh_tipo_limpieza_programada",
}


class RegistroDeshacer:
    def __init__(self, carpeta_datos=None):
        """`carpeta_datos`: dónde guardar. None = no se toca el disco, para
        que el banco de pruebas no ensucie los datos reales."""
        self.carpeta_datos = carpeta_datos

    # ---------------- Escribir ----------------
    def _ruta(self):
        if not self.carpeta_datos:
            return None
        return os.path.join(self.carpeta_datos, NOMBRE_ARCHIVO)

    def anotar(self, tipo, datos, descripcion=""):
        """Guarda un cambio que se puede deshacer.

        `datos` lleva lo que haga falta para revertirlo — el valor ANTERIOR,
        no el nuevo. Esa es toda la gracia: sin saber cómo estaba antes, no
        hay vuelta atrás posible.
        """
        if tipo not in TIPOS:
            return None
        entrada = {
            "id": f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex()}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": tipo,
            "datos": datos,
            "descripcion": descripcion,
            "deshecho": False,
        }
        ruta = self._ruta()
        if ruta:
            try:
                with open(ruta, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
            except Exception:
                # Que no se pueda anotar no puede impedir que la acción se
                # haga: esto es una red de seguridad, no el cometido.
                pass
        return entrada["id"]

    # ---------------- Leer ----------------
    def _todas(self):
        ruta = self._ruta()
        if not ruta or not os.path.exists(ruta):
            return []
        entradas = []
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        entrada = json.loads(linea)
                    except ValueError:
                        continue          # línea rota: se salta, el resto vale
                    if isinstance(entrada, dict) and entrada.get("id"):
                        entradas.append(entrada)
        except OSError:
            return []
        return entradas

    def pendientes(self, limite=None):
        """Cambios que todavía se pueden deshacer, del más reciente al más
        viejo. Los ya deshechos no salen: deshacer dos veces lo mismo o no
        hace nada, o —peor— vuelve a aplicar lo contrario."""
        vivos = [e for e in self._todas() if not e.get("deshecho")]
        vivos.reverse()
        return vivos[:limite] if limite else vivos

    def _marcar_deshecho(self, id_entrada):
        """Reescribe el archivo con esa entrada marcada.

        Se escribe a un temporal y se reemplaza al final: un corte a mitad
        dejaría el registro de cambios partido, y este archivo es
        justamente el que hace falta cuando algo salió mal.
        """
        ruta = self._ruta()
        if not ruta:
            return False
        entradas = self._todas()
        encontrada = False
        for e in entradas:
            if e.get("id") == id_entrada:
                e["deshecho"] = True
                e["deshecho_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                encontrada = True
        if not encontrada:
            return False
        try:
            temporal = ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                for e in entradas[-LIMITE:]:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            os.replace(temporal, ruta)
            return True
        except OSError:
            return False

    def recortar(self, limite=LIMITE):
        entradas = self._todas()
        if len(entradas) <= limite:
            return 0
        ruta = self._ruta()
        try:
            temporal = ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                for e in entradas[-limite:]:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            os.replace(temporal, ruta)
            return len(entradas) - limite
        except OSError:
            return 0

    def borrar_todo(self):
        ruta = self._ruta()
        if not ruta:
            return False
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
            return True
        except OSError:
            return False

    # ---------------- Deshacer ----------------
    def deshacer(self, id_entrada, opt):
        """Revierte un cambio. Devuelve (exito, clave_de_mensaje, comando).

        `opt` se pasa como parámetro en vez de importarlo arriba para que
        el banco de pruebas pueda darle un doble y comprobar la lógica sin
        tocar el sistema de verdad.
        """
        entrada = next((e for e in self._todas()
                        if e.get("id") == id_entrada and not e.get("deshecho")), None)
        if entrada is None:
            return False, "desh_no_encontrado", ""

        tipo = entrada.get("tipo")
        datos = entrada.get("datos") or {}
        exito, comando = False, ""

        if tipo == "perfil_energia":
            anterior = datos.get("anterior")
            if anterior:
                exito, comando = opt.set_power_plan(anterior)

        elif tipo == "app_inicio":
            # Se guardó si estaba activa ANTES; deshacer es devolverla a eso.
            exito = opt.set_app_inicio_activa(datos.get("nombre", ""),
                                               datos.get("comando", ""),
                                               bool(datos.get("estaba_activa")))
            comando = f'set_app_inicio_activa({datos.get("nombre")!r}, activar={bool(datos.get("estaba_activa"))})'

        elif tipo == "servicio":
            # Si se detuvo, deshacer es iniciarlo, y al revés.
            accion_inversa = "iniciar" if datos.get("accion") == "detener" else "detener"
            exito, comando = opt.set_servicio_windows(datos.get("nombre", ""), accion_inversa)

        elif tipo == "animaciones":
            exito, comando = opt.reducir_animaciones_ahora(
                activar_reduccion=bool(datos.get("estaban_reducidas")))

        elif tipo == "inicio_rapido":
            exito, comando = opt.set_inicio_rapido(bool(datos.get("estaba_activo")))

        elif tipo == "inicio_automatico":
            exito, comando = opt.set_startup(bool(datos.get("estaba_activo")))

        elif tipo == "limpieza_programada":
            if datos.get("estaba_activa"):
                exito, comando = opt.crear_limpieza_programada(
                    frecuencia=datos.get("frecuencia", "DAILY"),
                    hora=datos.get("hora", "09:00"))
            else:
                exito, comando = opt.quitar_limpieza_programada()

        else:
            return False, "desh_tipo_desconocido", ""

        if exito:
            self._marcar_deshecho(id_entrada)
            return True, "desh_ok", comando
        return False, "desh_fallo", comando
