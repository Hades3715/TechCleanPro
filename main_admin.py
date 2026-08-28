"""
main_admin.py
Punto de entrada de la EDICIÓN ADMINISTRADOR de TechClean Pro.

Comparte el 100% del código con la edición cliente (main.py): la misma
interfaz, los mismos optimizadores, el mismo monitoreo de componentes.
La única diferencia es que aquí NO se oculta nada técnico:

  - La "Consola Dev" aparece siempre en el menú lateral.
  - Cada tarjeta del Historial muestra el comando/API técnica exacta.
  - Las etiquetas usan lenguaje de administrador ("🛡 Administrador" /
    "Reiniciar como Admin") en vez del lenguaje simplificado del cliente.

Pensado para el propio desarrollador o para soporte técnico — no para
distribuir al usuario final (para eso está TechCleanPro.exe / main.py).

Ejecutar:      python main_admin.py
Compilar:      Generar_App_Admin.bat  →  produce TechCleanPro_Admin.exe
"""

import main

main.EDICION = "admin"

if __name__ == "__main__":
    app = main.TechCleanApp()
    if "--minimizado" in main.sys.argv:
        app.after(50, app._minimizar_a_bandeja)
    app.mainloop()
