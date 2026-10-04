# -*- coding: utf-8 -*-
"""Comprueba la medicion de DNS, el cambio de DNS y la optimizacion de
unidades, sin cambiar nada del sistema.

Lo que se comprueba
-------------------
  * La consulta DNS armada a mano es valida (un servidor DNS de mentira,
    en este mismo equipo, la recibe, la entiende y contesta).
  * Que solo cuente la respuesta a SU pregunta, no cualquier paquete.
  * Que un servidor que no contesta salga como "no contesta" y no como
    rapidisimo.
  * Que nada que llegue a un comando de PowerShell pueda colar otra cosa:
    letras de unidad y direcciones IP se filtran.
  * Que el plan Maximo rendimiento tenga su plantilla y un GUID fijo valido.

Uso:  python herramientas/prueba_dns_unidades.py
"""
import re
import socket
import struct
import sys
import threading

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== Paquete DNS ==")
paquete = opt._paquete_dns("www.google.com", 0x1234)
ident, banderas, preguntas = struct.unpack(">HHH", paquete[:6])
comprobar(ident == 0x1234 and banderas == 0x0100 and preguntas == 1, "cabecera: id, recursion, 1 pregunta")
comprobar(paquete[12:] == b"\x03www\x06google\x03com\x00\x00\x01\x00\x01", "nombre codificado por etiquetas + tipo A")

print("== Servidor DNS de mentira ==")
servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
servidor.bind(("127.0.0.1", 0))
puerto = servidor.getsockname()[1]
recibidas = []
modo = {"responder": True, "basura_antes": False}


def atender():
    servidor.settimeout(5)
    while True:
        try:
            datos, origen = servidor.recvfrom(1500)
        except OSError:
            return
        recibidas.append(datos)
        if not modo["responder"]:
            continue
        if modo["basura_antes"]:
            # Un paquete con OTRO id: no debe contarse como la respuesta.
            servidor.sendto(b"\x99\x99" + datos[2:], origen)
        servidor.sendto(datos[:2] + b"\x81\x80" + datos[4:], origen)


hilo = threading.Thread(target=atender, daemon=True)
hilo.start()

# medir_servidor_dns usa el puerto 53; para la prueba se apunta al de mentira.


class SocketPrueba(socket.socket):
    def sendto(self, datos, direccion):
        return super().sendto(datos, ("127.0.0.1", puerto))


socket_original = socket.socket
socket.socket = SocketPrueba
try:
    ms = opt.medir_servidor_dns("127.0.0.1", dominios=["a.com", "b.com", "c.com"], timeout=1)
    comprobar(ms is not None and ms < 200, f"mide un servidor que contesta ({ms})")
    comprobar(len(recibidas) == 3, f"hace una consulta por dominio ({len(recibidas)})")

    modo["basura_antes"] = True
    ms = opt.medir_servidor_dns("127.0.0.1", dominios=["a.com", "b.com"], timeout=1)
    comprobar(ms is not None, "ignora el paquete con otro id y espera el suyo")

    modo["responder"] = False
    ms = opt.medir_servidor_dns("127.0.0.1", dominios=["a.com", "b.com"], timeout=0.3)
    comprobar(ms is None, "un servidor que no contesta sale como None, no como rapido")
finally:
    socket.socket = socket_original
    servidor.close()

print("== Nada raro llega a PowerShell ==")
comprobar(opt._ps_lista(["1.1.1.1", "2606:4700::1111", "1.1.1.1'; Remove-Item C:\\ -Recurse; '"])
          == "'1.1.1.1','2606:4700::1111'", "las direcciones con algo mas que una IP se descartan")
# Solo la funcion que extrae la letra: llamar a optimizar_unidad con una
# letra valida optimizaria el disco de verdad.
comprobar(opt._letra_unidad("C; Format-Volume") == "C", "de 'C; Format-Volume' solo pasa la letra C")
comprobar(opt._letra_unidad("d") == "D", "minuscula -> mayuscula")
for mala in ("1", "", "ñ", " ", None, "$x"):
    comprobar(opt._letra_unidad(mala) is None, f"{mala!r} rechazada")
comprobar(opt.optimizar_unidad("1")[1] == opt.t("unid_letra_invalida"),
          "optimizar_unidad con una letra invalida no ejecuta nada")
comprobar(opt.aplicar_dns("no_existe")[0] is False, "un proveedor desconocido no cambia nada")

print("== Proveedores y plan Maximo ==")
for clave, p in opt.PROVEEDORES_DNS.items():
    comprobar(len(p["v4"]) == 2 and len(p["v6"]) == 2, f"{clave}: dos direcciones IPv4 y dos IPv6")
    for ip in p["v4"] + p["v6"]:
        try:
            socket.inet_pton(socket.AF_INET6 if ":" in ip else socket.AF_INET, ip)
        except OSError:
            comprobar(False, f"{clave}: {ip} es una IP valida")
maximo = opt.POWER_PLANS.get("maximo", {})
patron = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
comprobar(re.fullmatch(patron, maximo.get("guid", "")) is not None, "el plan Maximo tiene GUID fijo valido")
comprobar(maximo.get("plantilla") == "e9a42b02-d5df-448d-aa00-03f14749eb61",
          "y la plantilla oficial de Ultimate Performance")
comprobar(maximo.get("guid") not in {p["guid"] for k, p in opt.POWER_PLANS.items() if k != "maximo"},
          "su GUID no pisa el de otro plan")

print()
print("FALLOS: " + ", ".join(fallos) if fallos else "Todo bien.")
sys.exit(1 if fallos else 0)
