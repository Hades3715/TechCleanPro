# -*- coding: utf-8 -*-
"""Comprueba Seguridad → Protección y el Inicio de Windows completo (1.8.0)
con datos inventados. Lo que escribe en el registro va a una clave PROPIA
(HKCU\\Software\\TechCleanPrueba), nunca a la de Windows.

  * El archivo hosts: un bloqueo (0.0.0.0, 0.0.0.1 de McAfee) o un nombre de
    tu red o de Tailscale NO es un secuestro; mandar un nombre a una IP
    PÚBLICA sí. Con la primera regla salían en rojo cosas normales.
  * El resto de secuestros: proxy, DNS, certificados raíz, directivas.
  * El estado de la protección: antivirus, cortafuegos, control de cuentas.
  * Inicio de Windows: el valor que escribe el Administrador de tareas para
    activar o desactivar (y deshacer dejándolo igual que estaba), el
    programa de una línea de comando, y las reglas de la auditoría sobre
    cada entrada (un comando oculto es sospechoso; lo que ya no existe se
    dice).

Uso:  python herramientas/prueba_proteccion.py
"""
import os
import sys
import tempfile
import winreg

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt
import seguridad as seg

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


print("== El archivo hosts ==")
with tempfile.NamedTemporaryFile("w", suffix=".hosts", delete=False, encoding="utf-8") as f:
    f.write("# comentario\n127.0.0.1 localhost\n0.0.0.0 anuncios.com tracker.com\n0.0.0.1 mssplus.mcafee.com\n"
            "100.92.10.20 mipc.tail1234.ts.net\n192.168.1.5 nas\n93.184.216.34 www.mibanco.com  # raro\n")
    ruta_hosts = f.name
try:
    hosts = seg.leer_hosts(ruta_hosts)
finally:
    os.remove(ruta_hosts)
comprobar(len(hosts["bloqueos"]) == 3, f"bloqueos (0.0.0.0, 0.0.0.1) ({hosts['bloqueos']})")
comprobar(sorted(n for n, _ in hosts["locales"]) == ["mipc.tail1234.ts.net", "nas"], "tu red y Tailscale, aparte")
comprobar(hosts["redirecciones"] == [("www.mibanco.com", "93.184.216.34")], "lo que va a una IP pública")
comprobar(seg.leer_hosts(r"C:\no\existe\hosts") is None, "un hosts que no se puede leer: None")

print("== Secuestros ==")


def nivel_de(filas, clave):
    return next((f[1] for f in filas if f[0] == clave), None)


limpio = {"hosts_leido": True, "hosts_bloqueos": hosts["bloqueos"], "hosts_locales": hosts["locales"],
          "proxy_activo": False, "dns": ["8.8.8.8"], "certificados": [], "politicas": []}
filas = seg.evaluar_secuestros(limpio)
comprobar(all(f[1] == "bien" for f in filas), "bloqueos, Google DNS, sin proxy ni certificados: todo bien")
filas = seg.evaluar_secuestros(dict(limpio, hosts_redirecciones=hosts["redirecciones"]))
comprobar(nivel_de(filas, "hosts") == "critico", "un nombre mandado a una IP pública: rojo")
filas = seg.evaluar_secuestros(dict(limpio, proxy_activo=True, proxy="127.0.0.1:8888"))
comprobar(nivel_de(filas, "proxy") == "info", "un proxy en el propio equipo (Fiddler, un antivirus): info")
filas = seg.evaluar_secuestros(dict(limpio, proxy_pac="http://raro.example/proxy.pac"))
comprobar(nivel_de(filas, "proxy") == "atencion", "un proxy automático (PAC): atención")
filas = seg.evaluar_secuestros(dict(limpio, dns=["45.11.45.11"]))
comprobar(nivel_de(filas, "dns") == "atencion", "un DNS desconocido y público: atención")
filas = seg.evaluar_secuestros(dict(limpio, dns=["192.168.1.1"]))
comprobar(nivel_de(filas, "dns") == "bien", "el router como DNS: bien")
filas = seg.evaluar_secuestros(dict(limpio, certificados=[
    {"tipo": "antivirus", "nombre": "CN=McAfee Web Root"}, {"tipo": "adware", "nombre": "CN=Superfish, O=x"}]))
comprobar(nivel_de(filas, "certificados") == "critico", "un certificado de adware manda sobre el del antivirus")
filas = seg.evaluar_secuestros(dict(limpio, politicas=[{"navegador": "Chrome", "valor": "https://buscador.raro"}]))
comprobar(nivel_de(filas, "navegador") == "atencion", "una directiva que fija la página de inicio: atención")

print("== Estado de la protección ==")
base = {"antivirus": [{"nombre": "McAfee", "activo": True, "al_dia": True},
                      {"nombre": "Windows Defender", "activo": False, "al_dia": True}],
        "cortafuegos": {"dominio": True, "privada": True, "publica": True}, "cortafuegos_terceros": [],
        "arranque_seguro": True, "uac": 1, "uac_avisos": 5, "aislamiento": True}
filas = seg.evaluar_proteccion(base)
comprobar(all(f[1] == "bien" for f in filas), "todo encendido: todo bien")
comprobar(next(f for f in filas if f[0] == "antivirus")[3]["nombre"] == "McAfee", "el antivirus que manda")
filas = seg.evaluar_proteccion(dict(base, antivirus=[{"nombre": "X", "activo": False, "al_dia": True}]))
comprobar(nivel_de(filas, "antivirus") == "critico", "ningún antivirus activo: rojo")
filas = seg.evaluar_proteccion(dict(base, cortafuegos={"dominio": True, "privada": True, "publica": False}))
comprobar(nivel_de(filas, "cortafuegos") == "critico", "cortafuegos apagado en redes públicas: rojo")
filas = seg.evaluar_proteccion(dict(base, uac=0))
comprobar(nivel_de(filas, "uac") == "critico", "control de cuentas apagado: rojo")
filas = seg.evaluar_proteccion(dict(base, uac_avisos=0))
comprobar(nivel_de(filas, "uac") == "atencion", "control de cuentas sin avisos: atención")
comprobar(seg._producto_activo(0x061000) == (True, True) and seg._producto_activo(0x060010) == (False, False),
          "productState: activo y al día")

print("== Inicio de Windows: activar y desactivar ==")
comprobar(opt.valor_aprobado(True) == bytes([2]) + bytes(11), "activo: 02 y ceros")
desactivado = opt.valor_aprobado(False, momento=0)
comprobar(desactivado[:4] == bytes([3, 0, 0, 0]) and len(desactivado) == 12, "desactivado: 03 y la fecha")
comprobar(opt.esta_aprobado(None) and opt.esta_aprobado(opt.valor_aprobado(True))
          and not opt.esta_aprobado(desactivado), "sin valor = activo; impar = desactivado")
BASE = r"Software\TechCleanPrueba\StartupApproved"
try:
    exito, anterior, _ = opt.set_inicio_aprobado("HKCU", "Run", "Prueba", False, base=BASE)
    comprobar(exito and anterior is None, "desactivar: se relee y queda desactivado (antes no había valor)")
    comprobar(not opt.esta_aprobado(opt.leer_aprobado("HKCU", "Run", "Prueba", BASE)), "y lo que hay lo dice")
    exito, _ = opt.restaurar_inicio_aprobado("HKCU", "Run", "Prueba", anterior, base=BASE)
    comprobar(exito and opt.leer_aprobado("HKCU", "Run", "Prueba", BASE) is None,
              "deshacer lo deja como estaba: SIN valor (no un 02)")
finally:
    for sub in (BASE + r"\Run", BASE, r"Software\TechCleanPrueba"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            pass

print("== El programa de una línea de comando ==")
comprobar(opt.ejecutable_de_comando('"C:\\Program Files\\App\\app.exe" --minimizado') == r"C:\Program Files\App\app.exe",
          "entre comillas")
comprobar(opt.ejecutable_de_comando(r"C:\Herramientas\x.exe -silent") == r"C:\Herramientas\x.exe", "sin comillas")
comprobar(opt.ejecutable_de_comando("%SystemRoot%\\system32\\cmd.exe /c algo").lower()
          == os.path.join(os.environ["SystemRoot"], "system32", "cmd.exe").lower(), "con variables")

print("== Las reglas de la auditoría en el Inicio ==")
sistema = os.path.join(os.environ["SystemRoot"], "System32", "notepad.exe")
entradas = [
    {"tipo": "registro", "nombre": "Normal", "exe": sistema, "comando": sistema},
    {"tipo": "registro", "nombre": "Oculto", "exe": sistema,
     "comando": "powershell.exe -windowstyle hidden -enc AAAA"},
    {"tipo": "registro", "nombre": "Huerfano", "exe": r"C:\No\Existe\viejo.exe", "comando": r"C:\No\Existe\viejo.exe"},
]
firmas = {os.path.normcase(sistema): {"estado": "Valid", "firmante": "CN=Microsoft Windows, O=Microsoft Corporation"}}
seg.evaluar_inicio(entradas, firmas=firmas, accesos=[], carpetas=[os.path.normcase(tempfile.gettempdir())])
comprobar(entradas[0]["existe"] and entradas[0]["riesgo"] is None, "un programa firmado de Windows: nada que decir")
comprobar(entradas[1]["riesgo"] == "alto" and "seg_motivo_comando_oculto" in entradas[1]["motivos"],
          "un comando oculto (powershell -enc) es sospechoso")
comprobar(not entradas[2]["existe"], "lo que ya no existe se dice (es un resto de algo desinstalado)")

print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
