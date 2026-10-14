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
  `temas.py` — los 9 temas (colores, letra, forma). `iconos.py` — iconos
  de línea dibujados con Pillow. `idiomas.py` — todos los textos.
  `disco.py` — análisis completo de una unidad (8 hilos, solo lee).
  `gpu.py` — GPU de cualquier marca (D3DKMT + contadores PDH).
  `informe.py` — el informe en PDF (HTML con la cara de la app → Edge).
  `reportar.py` — el texto de "Reportar un problema" (quita usuario,
  equipo y carpetas; abre un issue de GitHub, la app no envía nada).
- `PRIVACIDAD.md` — qué guarda la app y cuándo se conecta: si se añade una
  conexión a internet nueva, actualizarlo (y `priv_app_texto`).
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
`herramientas\Verificar_Todo.bat` (43 comprobaciones; la última gasta ~60 MB
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
  "Versión 1.7.0"). Listas largas: `ListaLienzo` (filas en un `tk.Canvas`)
  o un `CTkTextbox`, no un widget por fila: en Windows cada widget es una
  ventana del sistema, y 40 filas tardaban 1 s en colocarse (ver CONTEXTO,
  "cada widget de Tk es una ventana"). `herramientas/prueba_rendimiento.py`
  lo vigila.
- **PowerShell que se lee como texto:** `PS_UTF8 +` delante del script y
  `encoding="utf-8"` (si no, las tildes salen rotas), y los enumerados de
  `ConvertTo-Json` llegan como NÚMEROS en PowerShell 5.1.
- **Widgets baratos:** para ordenar, `Caja(padre)` y no un
  `CTkFrame(fg_color="transparent")`; letras con `fuente(size, weight)`, no
  `ctk.CTkFont(...)`; textos que se parten al ancho de su caja, con
  `texto_fluido`; lo que se anima o se repite mucho, en un `tk.Canvas` (una
  CTkProgressBar cuesta ~10 ms). El rediseño de la 1.8.0 hizo la app el
  doble de lenta por esto (ver CONTEXTO, "El rediseño hizo la app el DOBLE
  de lenta").
- **Colores:** nunca escritos a mano (`"#2a2d36"`, `"gray60"`): una ficha del
  tema, `T.panel`, `T.texto2`, `T.acento`... (`from temas import T`). Si no,
  esa parte no cambia con el tema. Los temas son cerrados: van en el código,
  nada se descarga. `prueba_temas.py` lo vigila (y el contraste).
- `.bat` con finales de línea CRLF y rutas con `/`.

## Entorno del desarrollador
- Windows en español; el desarrollador escribe en español y prefiere pasos
  concretos.
- `gh` (GitHub CLI) instalado en `C:\Program Files\GitHub CLI\gh.exe`; puede
  no estar en el PATH de la terminal.
