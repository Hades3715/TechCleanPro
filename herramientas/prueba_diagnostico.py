# -*- coding: utf-8 -*-
"""Comprueba las lecturas de diagnóstico de la 1.8.0 con datos inventados
(funciones puras) y dos cosas de verdad del sistema que ya fallaron.

  * Salud NVMe: el registro de 512 bytes del propio disco, leído campo a
    campo, y el veredicto cuando el disco avisa o se queda sin repuesto.
  * Diagnóstico de fallos: pantallazos contados una vez (el 41 y el 1001 del
    mismo), apagados durante la suspensión, el volcado que no se pudo
    guardar (volmgr 161) y los daños del sistema de archivos (Ntfs).
  * Consumo de energía por app (powercfg /srumutil): las columnas por su
    nombre, sin contar dos veces lo que un proceso hace por otro.
  * Nombres legibles de apps (rutas y apps de la Tienda).
  * Lo que viene de PowerShell: el estado de los servicios como texto (se
    leía como número y todos salían "detenidos") y las tildes (salían
    "Optimizaci¢n").
  * Copia de drivers con una carpeta que no vale: la misma forma de
    respuesta (antes se quedaba en "Trabajando..." para siempre).

Uso:  python herramientas/prueba_diagnostico.py
"""
import subprocess
import sys

import _rutas
_rutas.poner_en_ruta()
import optimizer as opt
import privacy as priv
import tecnico as tec

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def entero(valor, largo):
    return valor.to_bytes(largo, "little")


print("== Salud NVMe ==")
crudo = bytearray(512)
crudo[0] = 0x01                                  # aviso crítico: repuesto bajo
crudo[1:3] = entero(320, 2)                      # 320 K = 47 °C
crudo[3], crudo[4], crudo[5] = 8, 10, 3          # repuesto 8 % (mínimo 10 %), desgaste 3 %
crudo[32:48] = entero(1000, 16)                  # unidades leídas (de 512.000 bytes)
crudo[48:64] = entero(2000, 16)                  # unidades escritas
crudo[112:128] = entero(150, 16)
crudo[128:144] = entero(3000, 16)
crudo[144:160] = entero(107, 16)
d = tec.leer_registro_nvme(bytes(crudo))
comprobar(d["temperatura"] == 47, f"temperatura en °C ({d['temperatura']})")
comprobar(d["leidos_bytes"] == 512_000_000 and d["escritos_bytes"] == 1_024_000_000, "datos leídos y escritos")
comprobar(d["ciclos"] == 150 and d["horas"] == 3000 and d["apagados_inseguros"] == 107,
          "encendidos, horas y apagados inseguros")
comprobar(tec.leer_registro_nvme(bytes(512))["temperatura"] is None, "sin sensor (0 K): temperatura desconocida")
nivel, motivos = tec.veredicto_disco(dict(d, tipo="SSD"))
comprobar(nivel == "critico" and "salud_motivo_aviso_nvme" in motivos and "salud_motivo_repuesto" in motivos,
          f"el aviso del propio disco y el repuesto bajo lo ponen en rojo ({nivel}, {motivos})")
crudo[0], crudo[3] = 0, 100
nivel, _ = tec.veredicto_disco(dict(tec.leer_registro_nvme(bytes(crudo)), tipo="SSD"))
comprobar(nivel == "bien", "un NVMe sano sale bien")

print("== Diagnóstico de fallos ==")
datos = {
    "apagados": [
        {"fecha": "2026-09-28 14:02", "codigo": "159", "suspension": "0", "boton": "0"},
        {"fecha": "2026-09-20 08:00", "codigo": "0", "suspension": "1", "boton": "0"},
        {"fecha": "2026-09-10 21:00", "codigo": "", "suspension": "", "boton": ""},
    ],
    # El mismo 0x9F del 28 (no se cuenta dos veces) y otro distinto.
    "pantallazos": [{"fecha": "2026-09-28 14:05", "codigo": "0x0000009f (0x3, 0x0)"},
                    {"fecha": "2026-09-01 10:00", "codigo": "0x00000050"}],
    "apps": [{"nombre": "bad_module_info", "veces": 3}, {"nombre": "chrome.exe", "veces": 2}],
    "hardware": 0,
    "disco": [{"fecha": "2026-09-28 14:03", "proveedor": "volmgr", "id": 161, "unidad": ""},
              {"fecha": "2026-09-15 09:00", "proveedor": "Ntfs", "id": 55, "unidad": "D:"},
              {"fecha": "2026-09-16 09:00", "proveedor": "disk", "id": 7, "unidad": ""}],
}
diag = tec.leer_diagnostico(datos, 30)
comprobar(len(diag["pantallazos"]) == 2, f"un pantallazo con su apagado cuenta una vez ({len(diag['pantallazos'])})")
comprobar(diag["pantallazos"][0]["codigo"] == 0x9F, "el más reciente primero, con su código")
comprobar(any(a["suspension"] for a in diag["apagados"]), "se ve el apagado durante la suspensión")
comprobar(diag["apps"][0]["nombre"] is None and diag["apps"][1]["nombre"] == "chrome.exe",
          "\"bad_module_info\" es que Windows no sabe qué programa era")
comprobar(diag["volcado_fallido"], "volmgr 161: no se pudo guardar el volcado (no es el disco fallando)")
comprobar(diag["sistema_archivos"] == [{"unidad": "D:", "fecha": "2026-09-15 09:00"}],
          "Ntfs: el sistema de archivos dañado, por unidad")
comprobar(diag["disco"] == 1, "solo el aviso del driver de disco cuenta como aviso de disco")
nivel, motivos = tec.veredicto_fallos(diag)
comprobar(nivel == "critico" and "fallos_motivo_pantallazos" in motivos and "fallos_motivo_suspension" in motivos
          and "fallos_motivo_ntfs" in motivos, f"el veredicto ({nivel}, {motivos})")
nivel, _ = tec.veredicto_fallos(tec.leer_diagnostico({}, 30))
comprobar(nivel == "bien", "sin eventos: bien")

print("== Consumo de energía por app ==")
csv = ("AppId,UserId,TimeStamp,CpuEnergyConsumption,DisplayEnergyConsumption,"
       "CpuEnergyConsumptionWorkOnBehalf,OnBattery\n"
       "\\Device\\HarddiskVolume3\\Program Files\\Google\\Chrome\\Application\\chrome.exe,S-1,x,600,200,999,1\n"
       "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe,S-1,x,100,100,999,0\n"
       "Microsoft.WindowsTerminal_8wekyb3d8bbwe!App,S-1,x,0,0,999,0\n"
       "Microsoft.WindowsCamera_8wekyb3d8bbwe!App,S-1,x,200,0,5,1\n")
apps = tec.leer_srum_csv(csv)
comprobar(apps is not None and [a["nombre"] for a in apps] == ["chrome", "Windows Camera"],
          f"agrupa por programa y quita los que no gastaron ({[a['nombre'] for a in apps or []]})")
comprobar(apps and apps[0]["energia"] == 1000 and apps[0]["pct"] == 83.3,
          "suma CPU + pantalla, sin lo hecho por otro proceso")
comprobar(apps and apps[0]["con_bateria"] == 800 and apps[1]["con_bateria"] == 200, "lo gastado con batería")
comprobar(tec.leer_srum_csv("nada,que,ver\n1,2,3") is None, "un CSV que no se reconoce: None")
comprobar(tec.nombre_app_srum("Microsoft.WindowsTerminal_8wekyb3d8bbwe!App") == "Windows Terminal",
          "nombre de una app de la Tienda")

print("== Nombres de apps en el uso de permisos ==")
comprobar(priv.nombre_de_app("C:#Program Files#Zoom#bin#Zoom.exe", False) == ("Zoom", r"C:\Program Files\Zoom\bin\Zoom.exe"),
          "una ruta de programa")
comprobar(priv.nombre_de_app("Microsoft.WindowsCamera_8wekyb3d8bbwe", True) == ("Windows Camera", None),
          "una app de la Tienda")
comprobar(priv._filetime_a_epoch(116444736000000000) == 0 and priv._filetime_a_epoch(0) is None,
          "fechas de Windows (FILETIME) a segundos")

print("== PowerShell ==")
r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", opt.PS_UTF8 + "'Optimización ñ'"],
                   capture_output=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW,
                   timeout=60)
comprobar(r.stdout.strip() == "Optimización ñ", f"las tildes llegan bien ({r.stdout.strip()!r})")
servicios = opt.listar_servicios_windows()
estados = {s["estado"] for s in servicios}
comprobar(servicios and estados <= set(opt.ESTADOS_SERVICIO.values()) and "Running" in estados,
          f"el estado de los servicios es texto, y hay alguno en marcha ({sorted(estados)})")
comprobar(not any("¢" in (s["nombre_visible"] or "") or "¡" in (s["nombre_visible"] or "") for s in servicios),
          "ningún nombre de servicio con las tildes rotas")

print("== Copia de drivers ==")
respuesta = tec.exportar_drivers(r"C:\no\existe\esta\carpeta", opt)
comprobar(len(respuesta) == 6 and respuesta[0] is False, "con una carpeta que no vale, la misma forma de respuesta")

print()
print("RESULTADO: " + ("sin fallos" if not fallos else f"{len(fallos)} FALLOS"))
sys.exit(1 if fallos else 0)
