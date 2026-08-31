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
        "ajustes_donar_titulo": "☕ Apoyar el proyecto",
        "ajustes_donar_log_accion": "Abrir página de donación",
        "ajustes_donar_log_ok": "Abriendo en el navegador.",
        "ajustes_donar_log_error": "No se pudo abrir.",
        "ajustes_donar_nota": "Lo desarrolla una sola persona, estudiante, en su tiempo libre.",
        "ajustes_donar_boton": "Apoyar en Ko-fi",
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
        # ---- Privacidad ----
        "priv_titulo": "Privacidad — Historial de navegación",
        "priv_sin_navegadores": "No se detectaron navegadores compatibles en este equipo.",
        "priv_cierra_navegador": "Cierra el navegador antes de limpiar sus datos.",
        "priv_btn_historial": "Borrar historial",
        "priv_btn_cache": "Limpiar caché",
        "priv_otras_titulo": "🗂 Otras huellas de actividad",
        "priv_btn_recientes": "Vaciar accesos recientes",
        "priv_btn_portapapeles": "Vaciar portapapeles",
        "priv_otras_desc": "Accesos recientes: borra los atajos a archivos/carpetas que Windows recuerda, no los archivos en sí. Portapapeles: borra lo último que copiaste (texto o imagen).",
        "priv_recientes_ok": "{cantidad} acceso(s) reciente(s) eliminados.",
        "priv_recientes_vacio": "No había accesos recientes para limpiar.",
        "priv_portapapeles_ok": "Portapapeles vaciado.",
        "priv_portapapeles_error": "No se pudo vaciar el portapapeles.",
        "priv_log_historial": "Borrar historial ({navegador})",
        "priv_log_cache": "Limpiar caché ({navegador})",
        "priv_log_cache_cmd": "Eliminación recursiva de carpeta Cache",
        "priv_cache_liberado": "{mensaje} ({tamano} liberados)",
        # ---- privacy.py (mensajes del módulo) ----
        "privmod_no_soportado": "Navegador no soportado",
        "privmod_abierto_hist": "{navegador} está abierto. Ciérralo antes de borrar su historial.",
        "privmod_abierto_cache": "{navegador} está abierto. Ciérralo antes de limpiar su caché.",
        "privmod_sin_perfil_ff": "No se encontró perfil de Firefox",
        "privmod_hist_ok": "Historial de {navegador} borrado correctamente.",
        "privmod_db_error": "No se pudo abrir la base de datos de {navegador} (¿sigue en uso?).",
        "privmod_hist_error": "Error al borrar historial de {navegador}: {error}",
        "privmod_sin_ruta": "{navegador} no tiene ruta de caché configurada en esta versión.",
        "privmod_sin_cache": "{navegador} no tenía caché acumulado.",
        "privmod_cache_ok": "Caché de {navegador} eliminado ({ruta})",
        "privmod_cache_error": "Error al limpiar caché de {navegador}: {error}",
        # ---- Acciones rápidas del Dashboard (historial) ----
        "dash_log_optimizacion": "Optimización rápida",
        "dash_log_papelera": "Vaciar papelera (inicio)",
        # ---- Energía / BIOS ----
        "energia_titulo": "⚡ Energía",
        "energia_intro": "Todas estas acciones son del sistema operativo (no algo que la app simule). Guarda tu trabajo antes de Apagar, Reiniciar o entrar a BIOS — con Suspender e Hibernar no hace falta, todo sigue abierto tal cual estaba al reanudar.",
        "energia_apagar": "⏻  Apagar",
        "energia_apagar_desc": "Apaga el equipo por completo.",
        "energia_reiniciar": "🔄  Reiniciar",
        "energia_reiniciar_desc": "Reinicio normal — vuelve a Windows directo, sin entrar a BIOS.",
        "energia_suspender": "🌙  Suspender",
        "energia_suspender_desc": "Bajo consumo, reanuda casi al instante — todo sigue abierto tal cual.",
        "energia_hibernar": "❄  Hibernar",
        "energia_hibernar_desc": "Guarda todo en disco y apaga del todo — cero consumo mientras hiberna, arranca un poco más lento que Suspender al volver.",
        "energia_bios": "🔧  Reiniciar a BIOS/UEFI",
        "energia_bios_desc": "Reinicia y entra directo al menú de configuración de UEFI, sin tener que presionar teclas durante el arranque.",
        "energia_conf_apagar_tit": "¿Apagar el equipo?",
        "energia_conf_apagar_msg": "Se apagará en 5 segundos. Guarda tu trabajo antes de confirmar.",
        "energia_conf_apagar_btn": "Apagar",
        "energia_conf_reiniciar_tit": "¿Reiniciar el equipo?",
        "energia_conf_reiniciar_msg": "Se reiniciará en 5 segundos. Guarda tu trabajo antes de confirmar.",
        "energia_conf_reiniciar_btn": "Reiniciar",
        "energia_conf_bios_tit": "¿Reiniciar y entrar a la BIOS/UEFI?",
        "energia_conf_bios_msg": "El equipo se reiniciará en 5 segundos y entrará directo a la BIOS/UEFI. Guarda tu trabajo antes de confirmar.",
        "energia_conf_bios_btn": "Reiniciar a BIOS",
        "energia_log_apagar": "Apagar equipo",
        "energia_log_reiniciar": "Reiniciar equipo",
        "energia_log_bios": "Reiniciar a UEFI/BIOS",
        "energia_log_suspender": "Suspender equipo",
        "energia_log_hibernar": "Hibernar equipo",
        "energia_log_ok": "Iniciado correctamente.",
        "energia_log_error": "Falló (¿estás en Windows con privilegios?)",
        "energia_log_suspendido": "Suspendido.",
        "energia_log_suspender_error": "No se pudo suspender.",
        "energia_log_hibernado": "Hibernado.",
        "energia_log_hibernar_error": "No se pudo hibernar (¿está deshabilitada la hibernación?).",
        # ---- Nombres de sección (aparecen en Historial y en el reporte) ----
        "seccion_ajustes": "Ajustes",
        "seccion_aplicaciones": "Aplicaciones",
        "seccion_automatico": "Automático",
        "seccion_componentes": "Componentes",
        "seccion_drivers": "Drivers",
        "seccion_energia": "Energía",
        "seccion_gaming": "Gaming",
        "seccion_general": "General",
        "seccion_inicio": "Inicio",
        "seccion_optimizador": "Optimizador",
        "seccion_privacidad": "Privacidad",
        "seccion_reparar": "Reparar",
        "seccion_segundo_plano": "Segundo Plano",
        "seccion_seguridad": "Seguridad",
        "seccion_sistema": "Sistema",
        # ---- Textos comunes reutilizados ----
        "comun_cancelar": "Cancelar",
        "comun_confirmar_titulo": "Confirmar",
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
        "ajustes_donar_titulo": "☕ Support the project",
        "ajustes_donar_log_accion": "Open donation page",
        "ajustes_donar_log_ok": "Opening in the browser.",
        "ajustes_donar_log_error": "Couldn't open it.",
        "ajustes_donar_nota": "Built by one person, a student, in their free time.",
        "ajustes_donar_boton": "Support on Ko-fi",
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
        # ---- Privacy ----
        "priv_titulo": "Privacy — Browsing history",
        "priv_sin_navegadores": "No supported browsers were detected on this computer.",
        "priv_cierra_navegador": "Close the browser before clearing its data.",
        "priv_btn_historial": "Clear history",
        "priv_btn_cache": "Clear cache",
        "priv_otras_titulo": "🗂 Other activity traces",
        "priv_btn_recientes": "Clear recent items",
        "priv_btn_portapapeles": "Clear clipboard",
        "priv_otras_desc": "Recent items: clears the shortcuts to files/folders that Windows remembers, not the files themselves. Clipboard: clears the last thing you copied (text or image).",
        "priv_recientes_ok": "{cantidad} recent item(s) removed.",
        "priv_recientes_vacio": "There were no recent items to clear.",
        "priv_portapapeles_ok": "Clipboard cleared.",
        "priv_portapapeles_error": "Couldn't clear the clipboard.",
        "priv_log_historial": "Clear history ({navegador})",
        "priv_log_cache": "Clear cache ({navegador})",
        "priv_log_cache_cmd": "Recursive deletion of Cache folder",
        "priv_cache_liberado": "{mensaje} ({tamano} freed)",
        # ---- privacy.py (module messages) ----
        "privmod_no_soportado": "Browser not supported",
        "privmod_abierto_hist": "{navegador} is open. Close it before clearing its history.",
        "privmod_abierto_cache": "{navegador} is open. Close it before clearing its cache.",
        "privmod_sin_perfil_ff": "No Firefox profile was found",
        "privmod_hist_ok": "{navegador} history cleared successfully.",
        "privmod_db_error": "Couldn't open the {navegador} database (is it still in use?).",
        "privmod_hist_error": "Error clearing {navegador} history: {error}",
        "privmod_sin_ruta": "{navegador} has no cache path configured in this version.",
        "privmod_sin_cache": "{navegador} had no cache built up.",
        "privmod_cache_ok": "{navegador} cache removed ({ruta})",
        "privmod_cache_error": "Error clearing {navegador} cache: {error}",
        # ---- Dashboard quick actions (history) ----
        "dash_log_optimizacion": "Quick optimization",
        "dash_log_papelera": "Empty Recycle Bin (home)",
        # ---- Power / BIOS ----
        "energia_titulo": "⚡ Power",
        "energia_intro": "All of these actions belong to the operating system (not something the app simulates). Save your work before Shut down, Restart or entering BIOS — with Sleep and Hibernate there's no need, everything stays open exactly as it was when you resume.",
        "energia_apagar": "⏻  Shut down",
        "energia_apagar_desc": "Turns the computer off completely.",
        "energia_reiniciar": "🔄  Restart",
        "energia_reiniciar_desc": "Normal restart — goes straight back to Windows, without entering BIOS.",
        "energia_suspender": "🌙  Sleep",
        "energia_suspender_desc": "Low power, resumes almost instantly — everything stays open as it was.",
        "energia_hibernar": "❄  Hibernate",
        "energia_hibernar_desc": "Saves everything to disk and shuts down fully — zero power while hibernating, starts a little slower than Sleep when you come back.",
        "energia_bios": "🔧  Restart to BIOS/UEFI",
        "energia_bios_desc": "Restarts and goes straight into the UEFI setup menu, without having to press keys during startup.",
        "energia_conf_apagar_tit": "Shut down the computer?",
        "energia_conf_apagar_msg": "It will shut down in 5 seconds. Save your work before confirming.",
        "energia_conf_apagar_btn": "Shut down",
        "energia_conf_reiniciar_tit": "Restart the computer?",
        "energia_conf_reiniciar_msg": "It will restart in 5 seconds. Save your work before confirming.",
        "energia_conf_reiniciar_btn": "Restart",
        "energia_conf_bios_tit": "Restart and enter BIOS/UEFI?",
        "energia_conf_bios_msg": "The computer will restart in 5 seconds and go straight into BIOS/UEFI. Save your work before confirming.",
        "energia_conf_bios_btn": "Restart to BIOS",
        "energia_log_apagar": "Shut down computer",
        "energia_log_reiniciar": "Restart computer",
        "energia_log_bios": "Restart to UEFI/BIOS",
        "energia_log_suspender": "Sleep computer",
        "energia_log_hibernar": "Hibernate computer",
        "energia_log_ok": "Started successfully.",
        "energia_log_error": "Failed (are you on Windows with privileges?)",
        "energia_log_suspendido": "Asleep.",
        "energia_log_suspender_error": "Couldn't enter sleep.",
        "energia_log_hibernado": "Hibernated.",
        "energia_log_hibernar_error": "Couldn't hibernate (is hibernation disabled?).",
        # ---- Section names (shown in History and in the report) ----
        "seccion_ajustes": "Settings",
        "seccion_aplicaciones": "Apps",
        "seccion_automatico": "Automatic",
        "seccion_componentes": "Components",
        "seccion_drivers": "Drivers",
        "seccion_energia": "Power",
        "seccion_gaming": "Gaming",
        "seccion_general": "General",
        "seccion_inicio": "Home",
        "seccion_optimizador": "Optimizer",
        "seccion_privacidad": "Privacy",
        "seccion_reparar": "Repair",
        "seccion_segundo_plano": "Background",
        "seccion_seguridad": "Security",
        "seccion_sistema": "System",
        # ---- Shared reusable text ----
        "comun_cancelar": "Cancel",
        "comun_confirmar_titulo": "Confirm",
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
