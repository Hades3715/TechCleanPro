"""
idiomas.py
Sistema de traducción de TechClean Pro.

Cómo funciona: cada texto de la interfaz se identifica con una CLAVE fija
que nunca cambia (por ejemplo "nav_inicio"), y esa clave se traduce según
el idioma activo. En el resto de la app se usa así:

    from idiomas import t
    ctk.CTkButton(self.sidebar, text=t("nav_inicio"), ...)

Esto es un trabajo en progreso: por ahora el menú lateral y la pantalla de
Inicio están migrados a este sistema — el resto de la app (más de 350
textos) todavía está en español directo dentro de main.py, y se irá
migrando pantalla por pantalla en próximas actualizaciones.

Cambiar de idioma en Ajustes pide reiniciar la app para aplicarse —
reconstruir cada pantalla ABIERTA en caliente sería mucho más complejo, y
con más riesgo de bugs, que simplemente pedir un reinicio (así lo hacen
la mayoría de programas para esto).
"""

IDIOMA_ACTUAL = "es"  # se sobreescribe al arrancar, según preferencias.json

IDIOMAS_DISPONIBLES = {"es": "Español", "en": "English"}

TEXTOS = {
    "es": {
        # ---- Menú lateral ----
        "nav_inicio": "📊  Inicio",
        "nav_componentes": "🔬  Componentes",
        "nav_optimizar": "🧹  Optimizar",
        "nav_reparar": "🛠  Reparar",
        "nav_aplicaciones": "📦  Aplicaciones",
        "nav_privacidad": "🔒  Privacidad",
        "nav_seguridad": "🛡️  Seguridad",
        "nav_gaming": "🎮  Gaming",
        "nav_segundo_plano": "🧩  Segundo Plano",
        "nav_historial": "📋  Historial",
        "nav_energia": "⚡  Energía",
        "nav_consola_dev": "💻  Consola Dev",
        "nav_panel_oculto": "🔓  Panel oculto",
        "nav_ajustes": "⚙  Ajustes",
        "nav_minimizar_bandeja": "🗕 Minimizar a bandeja",
        "sidebar_admin_estado_si": "🛡 Administrador",
        "sidebar_admin_estado_no": "⚠ Modo estándar",
        "sidebar_cliente_estado_si": "✅ Todas las funciones activas",
        "sidebar_cliente_estado_no": "🔓 Hay funciones por desbloquear",
        "sidebar_boton_reiniciar_admin": "Reiniciar como Admin",
        "sidebar_boton_desbloquear": "🔓 Desbloquear funciones",
        # ---- Ajustes: selector de idioma ----
        "ajustes_idioma_titulo": "🌐 Idioma",
        "ajustes_idioma_descripcion": "Cambiar el idioma pide reiniciar la app para aplicarse en toda la "
                                       "interfaz. Por ahora, solo el menú lateral está traducido — el resto "
                                       "de las pantallas se irán traduciendo en próximas actualizaciones.",
        "ajustes_idioma_reiniciar_aviso": "Se aplicará la próxima vez que abras TechClean Pro. ¿Cerrar la app "
                                           "ahora para que apliques el cambio?",
        # ---- Inicio (Dashboard) ----
        "dash_titulo": "Resumen del sistema",
        "dash_boton_optimizar_clic": "🚀 Optimización con un clic",
        "dash_boton_vaciar_papelera": "🗑 Vaciar papelera",
        "dash_resultado_inicial": "Un clic y TechClean Pro se encarga del resto.",
        "dash_optimizando": "Optimizando, espera un momento...",
        "dash_optimizacion_lista": "Listo ✅\nRAM compactada en {procesos} procesos ({ram} liberados).\n"
                                    "{archivos} archivos temporales eliminados ({disco} recuperados).",
        "dash_papelera_vaciada": "Papelera vaciada ✅",
        "dash_papelera_error": "No se pudo vaciar la papelera.",
        "dash_arreglar_todo": "🔧 Arreglar todo",
        "dash_salud_calculando": "Salud del sistema: calculando...",
        "dash_salud_revisando": "Revisando RAM, disco, inicio y temporales...",
        "dash_salud_titulo": "Salud del sistema: {nivel} ({puntaje}/100)",
        "dash_nivel_verde": "Verde",
        "dash_nivel_amarillo": "Amarillo",
        "dash_nivel_rojo": "Rojo",
        "dash_salud_sin_motivos": "No se encontró nada que valga la pena optimizar ahora mismo.",
        "dash_salud_motivos_prefijo": "Motivos: ",
        "dash_motivo_ram_muy_alta": "RAM muy alta ({pct}%)",
        "dash_motivo_ram_alta": "RAM alta ({pct}%)",
        "dash_motivo_disco_casi_lleno": "disco casi lleno ({pct}%)",
        "dash_motivo_disco_poco_espacio": "poco espacio libre ({pct}%)",
        "dash_motivo_apps_inicio": "{n} apps abren con Windows",
        "dash_motivo_temporales_gb": "~{gb} GB de temporales recuperables",
        "dash_motivo_temporales_mb": "~{mb} MB de temporales recuperables",
        "dash_arreglando": "Arreglando lo que se puede automáticamente...",
        "dash_arreglo_listo": "Listo: RAM compactada en {procesos} procesos y {archivos} temporales eliminados "
                               "({total} liberados en total). Para apps de inicio o espacio en disco, revisa "
                               "Aplicaciones u Optimizar directamente.",
        "dash_limpieza_programada_aviso": "🗓 Limpieza automática programada activa — a las {hora} (ver "
                                           "frecuencia en Segundo Plano)",
        "dash_info_equipo_titulo": "  Información del equipo",
        "dash_info_equipo_texto": "Equipo: {hostname}\nUsuario: {usuario}\nSO: {so}\nProcesador: {procesador}\n"
                                   "Arquitectura: {arquitectura}",
        "dash_gauge_ram": "Memoria RAM",
        "dash_gauge_cpu": "CPU",
        "dash_gauge_disco": "Almacenamiento",
        "dash_gauge_gpu": "GPU",
        "dash_spark_ram": "Memoria RAM (últimos minutos)",
        "dash_spark_cpu": "CPU (últimos minutos)",
        # ---- Ajustes (pantalla completa) ----
        "ajustes_titulo": "Ajustes",
        "ajustes_version": "TechClean Pro — versión {version}",
        "ajustes_desarrollado_por": "Desarrollado por {nombre} ({alias})",
        "ajustes_descripcion_app": "Panel de optimización, diagnóstico y privacidad para Windows.",
        "ajustes_donar_boton": "☕ Apoyar el proyecto",
        "ajustes_donar_desc": "TechClean Pro es gratis y seguirá siéndolo — esto es solo si quieres invitarme "
                               "un café, nunca un requisito.",
        "ajustes_donar_no_configurado_titulo": "Todavía sin configurar",
        "ajustes_donar_no_configurado_msg": "El desarrollador todavía no configuró un link de donación en "
                                             "esta versión.",
        "ajustes_buscar_actualizaciones": "🔄 Buscar actualizaciones",
        "ajustes_inicio_windows_titulo": "Iniciar TechClean Pro con Windows",
        "ajustes_inicio_windows_desc": "Así queda disponible en la bandeja del sistema desde que enciendes el "
                                        "equipo, sin abrir la ventana automáticamente.",
        "ajustes_alerta_temp_titulo": "🌡 Avisarme si la CPU pasa de (°C)",
        "ajustes_guardar": "Guardar",
        "ajustes_alerta_temp_desc": "Deja el campo vacío y presiona Guardar para desactivar la alerta. Solo "
                                     "funciona si tu equipo expone la temperatura de CPU (ver la sección "
                                     "Componentes).",
        "ajustes_modo_ligero_titulo": "🪶 Modo Ligero (para equipos de bajo rendimiento)",
        "ajustes_modo_ligero_desc": "Espacia las actualizaciones en pantalla de la propia app (widget, "
                                     "Componentes, ícono de bandeja) para consumir menos CPU — ninguna función "
                                     "se pierde, solo se actualizan un poco menos seguido. TechClean Pro te lo "
                                     "sugiere solo una vez, al primer arranque, si detecta un equipo modesto.",
        "ajustes_umbral_ram_titulo": "🧠 Liberar RAM automáticamente al llegar a",
        "ajustes_umbral_ram_desc": "Cuando el uso de RAM llegue a este porcentaje, TechClean Pro libera memoria "
                                    "sola en segundo plano, sin que tengas que hacer nada. Bájalo en equipos que "
                                    "ya andan justos de RAM desde que encienden — no hace falta esperar a que "
                                    "llegue tan alto para que valga la pena liberar espacio.",
        "ajustes_umbral_salud_titulo": "🩺 Umbrales del semáforo de salud (Inicio)",
        "ajustes_umbral_salud_ram": "Avisar cuando la RAM pase de",
        "ajustes_umbral_salud_disco": "Avisar cuando el disco esté lleno a",
        "ajustes_umbral_salud_desc": "A partir de qué porcentaje el semáforo de Inicio empieza a restar "
                                      "puntos y sugerir que revises algo. Bájalos en equipos donde ya es "
                                      "normal andar más justo de recursos, para que el semáforo sea realista "
                                      "con lo que es \"normal\" en ese equipo en particular.",
        "ajustes_errores_titulo": "🛡 Manejo de errores y diagnóstico",
        "ajustes_errores_desc": "El manejo de errores está activo automáticamente en toda la app — si "
                                 "cualquier función falla, aparece un aviso con el detalle técnico exacto, "
                                 "queda en el Historial, y se guarda en un archivo. El Diagnóstico completo es "
                                 "distinto: en vez de esperar a toparte con un error navegando, recorre unas 35 "
                                 "funciones de solo lectura de una sola vez y te dice cuáles fallan — así "
                                 "tienes el resultado listo para compartirlo con quien te esté ayudando, sin "
                                 "tener que ir pantalla por pantalla probando.",
        "ajustes_diagnostico_boton": "🔬 Diagnóstico completo",
        "ajustes_probar_error_directo": "🧪 Probar error (clic directo)",
        "ajustes_probar_error_segundo_plano": "🧪 Probar error (segundo plano)",
        "ajustes_abrir_carpeta_registros": "📂 Abrir carpeta de registros",
        "ajustes_icono_bandeja_titulo": "🔔 Mostrar en el ícono de la bandeja",
        "ajustes_icono_bandeja_nada": "Nada (ícono normal)",
        "ajustes_icono_bandeja_cpu": "% de CPU",
        "ajustes_icono_bandeja_ram": "% de RAM",
        "ajustes_icono_bandeja_desc": "Útil si prefieres no tener el widget flotante ocupando pantalla: el "
                                       "número aparece directo en el ícono de la bandeja (zona de iconos "
                                       "ocultos de la barra de tareas).",
        "ajustes_bateria_titulo": "🔋 Ahorro automático con batería baja",
        "ajustes_bateria_desc": "Cuando la batería baje del porcentaje elegido (y no esté cargando), cambia "
                                 "sola al plan Silencioso. Vuelve a Equilibrado al conectar el cargador o subir "
                                 "10 puntos más.",
        "ajustes_widget_metricas_titulo": "📊 Métricas en el widget flotante",
        "ajustes_widget_metrica_red": "Red (↑↓)",
        "ajustes_widget_metricas_desc": "Se aplica la próxima vez que actives el widget (desactívalo y vuelve "
                                         "a activarlo).",
        "ajustes_config_titulo": "⚙ Configuración de TechClean Pro",
        "ajustes_exportar": "📤 Exportar",
        "ajustes_importar": "📥 Importar",
        "ajustes_restablecer": "♻ Restablecer todo",
        "ajustes_historial_nota": "TechClean Pro siempre te muestra en el Historial qué acciones realizó.",
        "ajustes_exportar_dialogo_titulo": "Exportar configuración",
        "ajustes_exportar_exito": "Configuración exportada a:\n{destino}",
        "ajustes_exportar_error": "No se pudo exportar: {error}",
        "ajustes_importar_dialogo_titulo": "Importar configuración",
        "ajustes_importar_formato_invalido": "El archivo no tiene el formato esperado.",
        "ajustes_importar_exito": "Configuración importada. Cierra y vuelve a abrir TechClean Pro para que "
                                   "todo se aplique.",
        "ajustes_importar_error": "No se pudo importar: {error}",
        "ajustes_restablecer_confirmar": "¿Restablecer TODA la configuración a valores de fábrica?\n\nEsto no "
                                          "borra el Historial de esta sesión ni tus archivos — solo las "
                                          "preferencias guardadas (perfil de energía, alertas, widget, etc.).",
        "ajustes_cancelar": "Cancelar",
        "ajustes_restablecer_boton": "Restablecer",
        "ajustes_restablecer_exito": "Configuración restablecida. Cierra y vuelve a abrir TechClean Pro para "
                                      "que todo se aplique.",
        "ajustes_buscando": "Buscando...",
        "ajustes_hay_version_nueva": "🎉 Hay una versión nueva: {version} (tienes {actual})",
        "ajustes_version_al_dia": "Ya tienes la última versión ({actual}).",
        "ajustes_no_se_pudo_consultar": "No se pudo consultar (sin internet, o el desarrollador no configuró "
                                         "esto todavía).",
        "ajustes_alerta_desactivada_titulo": "Alerta desactivada",
        "ajustes_alerta_desactivada_msg": "Ya no se avisará por temperatura de CPU.",
        "ajustes_valor_invalido_titulo": "Valor inválido",
        "ajustes_valor_invalido_msg": "Escribe solo un número, por ejemplo 85.",
        "ajustes_alerta_guardada_titulo": "Alerta guardada",
        "ajustes_alerta_guardada_msg": "Se te avisará si la CPU pasa de {valor}°C.",
        "ajustes_inicio_agregado": "Se agregó al inicio de Windows.",
        "ajustes_inicio_quitado": "Se quitó del inicio de Windows.",
        "ajustes_inicio_error": "No se pudo modificar el inicio automático.",
        "ajustes_temp_placeholder": "ej. 85",
        # ---- Segundo Plano ----
        "segplano_titulo": "Trabajo en segundo plano",
        "segplano_subtitulo": "Deja que TechClean Pro te ayude mientras usas tu equipo, sin abrir la ventana completa. ¿Buscas Modo Juego, FPS o Enfoque asistido? Se mudaron a 🎮 Gaming.",
        "segplano_widget_titulo": "🧩 Widget de rendimiento flotante",
        "segplano_widget_desc": "Una barra pequeña, siempre visible y arrastrable, con CPU/GPU/RAM/Red en vivo. Haz clic en ▾ dentro del widget para expandirlo y ver más detalle.",
        "segplano_limpieza_titulo": "🗓 Limpieza programada automática",
        "segplano_frec_diaria": "Diaria",
        "segplano_frec_semanal": "Semanal",
        "segplano_limpieza_desc": "Crea una tarea en el Programador de tareas de Windows que libera RAM y limpia temporales todos los días (o cada semana), a la hora que elijas — sin abrir ninguna ventana, ni siquiera minimizada. Se puede desactivar en cualquier momento con este switch.",
        "segplano_programada_ok": "Limpieza {frecuencia} programada a las {hora}.",
        "segplano_programada_error": "No se pudo crear la tarea programada (¿permisos suficientes?).",
        "segplano_quitada_ok": "Tarea programada eliminada.",
        "segplano_quitada_error": "No se pudo eliminar la tarea.",
    },
    "en": {
        "nav_inicio": "📊  Home",
        "nav_componentes": "🔬  Components",
        "nav_optimizar": "🧹  Optimize",
        "nav_reparar": "🛠  Repair",
        "nav_aplicaciones": "📦  Applications",
        "nav_privacidad": "🔒  Privacy",
        "nav_seguridad": "🛡️  Security",
        "nav_gaming": "🎮  Gaming",
        "nav_segundo_plano": "🧩  Background",
        "nav_historial": "📋  History",
        "nav_energia": "⚡  Power",
        "nav_consola_dev": "💻  Dev Console",
        "nav_panel_oculto": "🔓  Hidden panel",
        "nav_ajustes": "⚙  Settings",
        "nav_minimizar_bandeja": "🗕 Minimize to tray",
        "sidebar_admin_estado_si": "🛡 Administrator",
        "sidebar_admin_estado_no": "⚠ Standard mode",
        "sidebar_cliente_estado_si": "✅ All features active",
        "sidebar_cliente_estado_no": "🔓 There are features to unlock",
        "sidebar_boton_reiniciar_admin": "Restart as Admin",
        "sidebar_boton_desbloquear": "🔓 Unlock features",
        # ---- Settings: language picker ----
        "ajustes_idioma_titulo": "🌐 Language",
        "ajustes_idioma_descripcion": "Changing the language requires restarting the app to apply everywhere. "
                                       "For now, only the sidebar is translated — the rest of the screens will "
                                       "be translated in future updates.",
        "ajustes_idioma_reiniciar_aviso": "This will apply the next time you open TechClean Pro. Close the app "
                                           "now to apply the change?",
        # ---- Home (Dashboard) ----
        "dash_titulo": "System overview",
        "dash_boton_optimizar_clic": "🚀 One-click optimization",
        "dash_boton_vaciar_papelera": "🗑 Empty recycle bin",
        "dash_resultado_inicial": "One click and TechClean Pro takes care of the rest.",
        "dash_optimizando": "Optimizing, please wait...",
        "dash_optimizacion_lista": "Done ✅\nRAM compacted across {procesos} processes ({ram} freed).\n"
                                    "{archivos} temp files deleted ({disco} recovered).",
        "dash_papelera_vaciada": "Recycle bin emptied ✅",
        "dash_papelera_error": "Couldn't empty the recycle bin.",
        "dash_arreglar_todo": "🔧 Fix everything",
        "dash_salud_calculando": "System health: calculating...",
        "dash_salud_revisando": "Checking RAM, disk, startup apps and temp files...",
        "dash_salud_titulo": "System health: {nivel} ({puntaje}/100)",
        "dash_nivel_verde": "Green",
        "dash_nivel_amarillo": "Yellow",
        "dash_nivel_rojo": "Red",
        "dash_salud_sin_motivos": "Nothing worth optimizing right now.",
        "dash_salud_motivos_prefijo": "Reasons: ",
        "dash_motivo_ram_muy_alta": "RAM very high ({pct}%)",
        "dash_motivo_ram_alta": "RAM high ({pct}%)",
        "dash_motivo_disco_casi_lleno": "disk almost full ({pct}%)",
        "dash_motivo_disco_poco_espacio": "low free space ({pct}%)",
        "dash_motivo_apps_inicio": "{n} apps open with Windows",
        "dash_motivo_temporales_gb": "~{gb} GB of recoverable temp files",
        "dash_motivo_temporales_mb": "~{mb} MB of recoverable temp files",
        "dash_arreglando": "Fixing what can be fixed automatically...",
        "dash_arreglo_listo": "Done: RAM compacted across {procesos} processes and {archivos} temp files "
                               "deleted ({total} freed in total). For startup apps or disk space, check "
                               "Applications or Optimize directly.",
        "dash_limpieza_programada_aviso": "🗓 Automatic scheduled cleanup active — at {hora} (check frequency "
                                           "in Background)",
        "dash_info_equipo_titulo": "  Computer info",
        "dash_info_equipo_texto": "Computer: {hostname}\nUser: {usuario}\nOS: {so}\nProcessor: {procesador}\n"
                                   "Architecture: {arquitectura}",
        "dash_gauge_ram": "RAM Memory",
        "dash_gauge_cpu": "CPU",
        "dash_gauge_disco": "Storage",
        "dash_gauge_gpu": "GPU",
        "dash_spark_ram": "RAM Memory (last few minutes)",
        "dash_spark_cpu": "CPU (last few minutes)",
        # ---- Settings (full screen) ----
        "ajustes_titulo": "Settings",
        "ajustes_version": "TechClean Pro — version {version}",
        "ajustes_desarrollado_por": "Developed by {nombre} ({alias})",
        "ajustes_descripcion_app": "Optimization, diagnostics, and privacy panel for Windows.",
        "ajustes_donar_boton": "☕ Support the project",
        "ajustes_donar_desc": "TechClean Pro is free and will stay that way — this is only if you'd like to "
                               "buy me a coffee, never a requirement.",
        "ajustes_donar_no_configurado_titulo": "Not set up yet",
        "ajustes_donar_no_configurado_msg": "The developer hasn't set up a donation link in this version yet.",
        "ajustes_buscar_actualizaciones": "🔄 Check for updates",
        "ajustes_inicio_windows_titulo": "Start TechClean Pro with Windows",
        "ajustes_inicio_windows_desc": "This makes it available in the system tray as soon as you turn on "
                                        "your computer, without opening the window automatically.",
        "ajustes_alerta_temp_titulo": "🌡 Alert me if CPU goes above (°C)",
        "ajustes_guardar": "Save",
        "ajustes_alerta_temp_desc": "Leave the field empty and press Save to turn off the alert. Only works "
                                     "if your computer exposes CPU temperature (see the Components section).",
        "ajustes_modo_ligero_titulo": "🪶 Light Mode (for low-performance computers)",
        "ajustes_modo_ligero_desc": "Spaces out the app's own on-screen updates (widget, Components, tray "
                                     "icon) to use less CPU — no feature is lost, they just update a bit less "
                                     "often. TechClean Pro suggests it only once, on first launch, if it "
                                     "detects a modest computer.",
        "ajustes_umbral_ram_titulo": "🧠 Automatically free RAM when it reaches",
        "ajustes_umbral_ram_desc": "When RAM usage reaches this percentage, TechClean Pro frees up memory on "
                                    "its own in the background, without you having to do anything. Lower it on "
                                    "computers that already run tight on RAM from the moment they start — no "
                                    "need to wait for it to get that high before it's worth freeing up space.",
        "ajustes_umbral_salud_titulo": "🩺 Health meter thresholds (Home)",
        "ajustes_umbral_salud_ram": "Warn when RAM goes above",
        "ajustes_umbral_salud_disco": "Warn when disk is full up to",
        "ajustes_umbral_salud_desc": "The percentage at which the Home health meter starts subtracting points "
                                      "and suggesting you check something. Lower these on computers where "
                                      "running tighter on resources is already normal, so the meter reflects "
                                      "what's actually \"normal\" for that specific computer.",
        "ajustes_errores_titulo": "🛡 Error handling and diagnostics",
        "ajustes_errores_desc": "Error handling is automatically active throughout the app — if any function "
                                 "fails, a notice appears with the exact technical detail, it's logged in "
                                 "History, and saved to a file. Full Diagnostics is different: instead of "
                                 "waiting to run into an error while navigating, it runs through about 35 "
                                 "read-only functions at once and tells you which ones fail — so you have the "
                                 "result ready to share with whoever is helping you, without going screen by "
                                 "screen testing.",
        "ajustes_diagnostico_boton": "🔬 Full Diagnostics",
        "ajustes_probar_error_directo": "🧪 Test error (direct click)",
        "ajustes_probar_error_segundo_plano": "🧪 Test error (background)",
        "ajustes_abrir_carpeta_registros": "📂 Open logs folder",
        "ajustes_icono_bandeja_titulo": "🔔 Show in the tray icon",
        "ajustes_icono_bandeja_nada": "Nothing (normal icon)",
        "ajustes_icono_bandeja_cpu": "CPU %",
        "ajustes_icono_bandeja_ram": "RAM %",
        "ajustes_icono_bandeja_desc": "Useful if you'd rather not have the floating widget taking up screen "
                                       "space: the number appears directly on the tray icon (the hidden icons "
                                       "area of the taskbar).",
        "ajustes_bateria_titulo": "🔋 Automatic power saving on low battery",
        "ajustes_bateria_desc": "When the battery drops below the chosen percentage (and isn't charging), it "
                                 "switches to the Quiet plan on its own. Goes back to Balanced when you plug "
                                 "in the charger or it rises 10 more points.",
        "ajustes_widget_metricas_titulo": "📊 Floating widget metrics",
        "ajustes_widget_metrica_red": "Network (↑↓)",
        "ajustes_widget_metricas_desc": "Applies the next time you turn on the widget (turn it off and back "
                                         "on).",
        "ajustes_config_titulo": "⚙ TechClean Pro configuration",
        "ajustes_exportar": "📤 Export",
        "ajustes_importar": "📥 Import",
        "ajustes_restablecer": "♻ Reset everything",
        "ajustes_historial_nota": "TechClean Pro always shows you in History which actions it performed.",
        "ajustes_exportar_dialogo_titulo": "Export configuration",
        "ajustes_exportar_exito": "Configuration exported to:\n{destino}",
        "ajustes_exportar_error": "Couldn't export: {error}",
        "ajustes_importar_dialogo_titulo": "Import configuration",
        "ajustes_importar_formato_invalido": "The file isn't in the expected format.",
        "ajustes_importar_exito": "Configuration imported. Close and reopen TechClean Pro for everything to "
                                   "apply.",
        "ajustes_importar_error": "Couldn't import: {error}",
        "ajustes_restablecer_confirmar": "Reset ALL settings to factory defaults?\n\nThis doesn't erase this "
                                          "session's History or your files — only saved preferences (power "
                                          "plan, alerts, widget, etc.).",
        "ajustes_cancelar": "Cancel",
        "ajustes_restablecer_boton": "Reset",
        "ajustes_restablecer_exito": "Settings reset. Close and reopen TechClean Pro for everything to apply.",
        "ajustes_buscando": "Checking...",
        "ajustes_hay_version_nueva": "🎉 There's a new version: {version} (you have {actual})",
        "ajustes_version_al_dia": "You already have the latest version ({actual}).",
        "ajustes_no_se_pudo_consultar": "Couldn't check (no internet, or the developer hasn't set this up yet).",
        "ajustes_alerta_desactivada_titulo": "Alert turned off",
        "ajustes_alerta_desactivada_msg": "You won't be notified about CPU temperature anymore.",
        "ajustes_valor_invalido_titulo": "Invalid value",
        "ajustes_valor_invalido_msg": "Enter just a number, for example 85.",
        "ajustes_alerta_guardada_titulo": "Alert saved",
        "ajustes_alerta_guardada_msg": "You'll be notified if the CPU goes above {valor}°C.",
        "ajustes_inicio_agregado": "Added to Windows startup.",
        "ajustes_inicio_quitado": "Removed from Windows startup.",
        "ajustes_inicio_error": "Couldn't change automatic startup.",
        "ajustes_temp_placeholder": "e.g. 85",
        # ---- Background ----
        "segplano_titulo": "Background work",
        "segplano_subtitulo": "Let TechClean Pro help you while you use your computer, without opening the full window. Looking for Game Mode, FPS or Focus assist? They moved to 🎮 Gaming.",
        "segplano_widget_titulo": "🧩 Floating performance widget",
        "segplano_widget_desc": "A small bar, always visible and draggable, with live CPU/GPU/RAM/Network. Click ▾ inside the widget to expand it and see more detail.",
        "segplano_limpieza_titulo": "🗓 Scheduled automatic cleanup",
        "segplano_frec_diaria": "Daily",
        "segplano_frec_semanal": "Weekly",
        "segplano_limpieza_desc": "Creates a task in the Windows Task Scheduler that frees RAM and clears temporary files every day (or every week), at the time you choose — without opening any window, not even minimized. You can turn it off at any time with this switch.",
        "segplano_programada_ok": "Cleanup scheduled {frecuencia} at {hora}.",
        "segplano_programada_error": "Couldn't create the scheduled task (enough permissions?).",
        "segplano_quitada_ok": "Scheduled task removed.",
        "segplano_quitada_error": "Couldn't remove the task.",
    },
}


def t(clave, **kwargs):
    """Devuelve el texto traducido para 'clave' en el idioma actual. Si
    falta en el idioma activo, cae a español; si tampoco existe ahí,
    devuelve la clave misma (para que el hueco sea visible y se pueda
    corregir, en vez de una pantalla en blanco). Soporta interpolación
    tipo .format() vía **kwargs, ej. t("saludo", nombre="Ana")."""
    texto = TEXTOS.get(IDIOMA_ACTUAL, {}).get(clave)
    if texto is None:
        texto = TEXTOS["es"].get(clave, clave)
    if kwargs:
        try:
            return texto.format(**kwargs)
        except Exception:
            return texto
    return texto


def establecer_idioma(codigo):
    global IDIOMA_ACTUAL
    if codigo in TEXTOS:
        IDIOMA_ACTUAL = codigo
