# TechClean

App de escritorio para Windows (Python + customtkinter) que optimiza, limpia,
repara y audita el equipo. Bilingüe es/en. El detalle de cada decisión y de
cada error ya corregido está en `documentacion/CONTEXTO_PROYECTO.md`:
**buscar ahí la sección que toque (grep), no leerlo entero** — es largo.

## Dónde está cada cosa
- `codigo/main.py` — interfaz (`TechCleanApp`) y motor de comandos de consola.
- `codigo/optimizer.py` — acciones sobre el sistema. `autopilot.py` — todo lo
  que corre en segundo plano (Modo Juego, RAM automática, `Vigilante`).
- `codigo/tecnico.py` — herramientas de la edición Admin. `seguridad.py` —
  auditor de malware y de extensiones (solo lee). `atajos.py` — atajo de
  teclado global (`RegisterHotKey`, nunca ganchos de teclado).
  `idiomas.py` — todos los textos.
- `herramientas/` — banco de pruebas. `compilar/` — PyInstaller e Inno Setup.

## Ediciones y builds
- Cliente: `codigo/main.py`, idioma fijado al compilar (`build_config.py`) →
  `TechClean_ES.exe` y `TechClean_EN.exe`. Admin: `codigo/main_admin.py`
  (pone `EDICION = "admin"`) → `TechClean_Admin.exe`, no se publica.
- Probar sin compilar: `Iniciar.bat` / `Iniciar_Admin.bat`.
- Versión: `APP_VERSION` en `codigo/main.py`. La release de GitHub
  (`Hades3715/TechCleanPro`) debe llevar la etiqueta `vX.Y.Z` igual: el
  buscador de actualizaciones de la app compara las dos.

## Antes de dar algo por terminado
`herramientas\Verificar_Todo.bat` (39 comprobaciones; la última gasta ~60 MB
de datos). Una suelta: `PYTHONIOENCODING=utf-8 python herramientas/<x>.py`.
Al añadir una prueba, registrarla en el `.bat` (o `auditoria.py` falla); al
añadir un módulo, sumarlo a `herramientas/_rutas.py` (`MODULOS`).

## Reglas que no se rompen
- **Hilos:** subprocess, winreg, PowerShell/WMI nunca en el hilo de Tk. Desde
  un hilo, la interfaz se toca SOLO con `self.after(0, ...)`, y la
  comprobación `winfo_exists()` va DENTRO de ese callback (o se usa
  `_actualizar_label`). Bucles repetidos: número de generación.
- **Textos:** todo lo visible pasa por `t("clave")`, en es y en, con los
  mismos `{campos}`. Nunca comparar contra texto traducido: convertirlo a una
  clave interna. Diccionarios que se construyen al importar guardan la CLAVE.
- **Comprobar el efecto, no el código de salida.** Releer el registro,
  contar los puntos de restauración, medir antes y después de borrar. Ya
  mintió la app así una docena de veces (ver CONTEXTO).
- **Borrar:** siempre por `_vaciar_contenido` / `_recorrer` de
  `optimizer.py`. `os.walk` entra en uniones (junctions) y llegó a borrar
  fuera de %TEMP%.
- **Cambios reversibles:** `self.deshacer.anotar(tipo, datos)` con el valor
  ANTERIOR, y su inversa en `deshacer.py`. Lo que no se puede deshacer, se
  confirma antes con un diálogo.
- **Procesos y servicios:** pasan por `evaluar_riesgo_proceso` /
  `evaluar_riesgo_servicio`. Ventanas `CTkToplevel` de decisión llevan
  `grab_set()`.
- **Ligera:** sin dependencias nuevas; nada en segundo plano sin necesidad;
  con la ventana oculta no se refresca nada. Medir el consumo si se toca algo
  que corre solo.
- **Nada que espere en el hilo de Tk**, ni un `psutil.cpu_percent(interval=…)`
  ni un `time.sleep`: congelaba Inicio el 15 % del tiempo (ver CONTEXTO,
  "Versión 1.7.0"). Listas largas: un `CTkTextbox`, no un widget por fila.
  `herramientas/prueba_rendimiento.py` lo vigila.
- `.bat` con finales de línea CRLF y rutas con `/`.

## Entorno del desarrollador
- Windows en español; el desarrollador escribe en español y prefiere pasos
  concretos.
- `gh` (GitHub CLI) instalado en `C:\Program Files\GitHub CLI\gh.exe`; puede
  no estar en el PATH de la terminal.
