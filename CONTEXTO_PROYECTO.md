# TechClean — Contexto del proyecto

Este documento es para que quien retome el proyecto (incluido yo mismo, en una
sesión nueva) tenga el contexto completo sin tener que releer meses de
conversación. Está escrito pensando en alguien (o en mí) que abre esta carpeta
por primera vez.

## Qué es esto

App de escritorio para Windows — optimización, diagnóstico y mantenimiento del
sistema. Desarrollada por **Edwin Javier Cortez Cardoza**, alias **Hades**
(usuario ITSI2A). Es un proyecto real, en uso, no un ejercicio — el desarrollador
la instaló en su propia laptop y en la de otra persona con equipo de bajo
rendimiento, y varios bugs se encontraron así, con uso real.

- **Versión actual**: 1.5.0 (`APP_VERSION` en `main.py`)
- **Stack**: Python + customtkinter (tema oscuro), psutil, pystray+Pillow,
  winreg, ctypes, sqlite3, PowerShell (para WMI vía `Get-CimInstance`)
- **~12,600 líneas** repartidas en `main.py`, `optimizer.py`,
  `system_monitor.py`, `idiomas.py` (que crecio mucho al traducir todo), más
  módulos más pequeños.
- **Bilingüe completo**: 1,037 claves con paridad exacta español/inglés.
  Ocho módulos usan `t()`: main, optimizer, system_monitor, privacy,
  autopilot, widget, tray e idiomas.

## Las dos ediciones

- **Cliente** (`main.py`, `EDICION = "cliente"`): oculta lo técnico. Panel oculto
  (7 clics en la versión, en Ajustes) con comandos `/help`, `/ram`, etc.
- **Admin** (`main_admin.py`, importa y reusa casi todo de `main.py`): Consola
  Dev siempre visible con el comando técnico exacto de cada acción — nunca se
  reparte al usuario final, es para el propio desarrollador o soporte técnico.

**Solo se sube a GitHub la edición cliente.** La admin nunca se publica
como `.exe`. Su CÓDIGO sí queda visible si el repositorio es público, y no
pasa nada: `main_admin.py` son 29 líneas que ponen `EDICION = "admin"`, y
toda la lógica admin vive en `main.py` detrás de comprobaciones
`if EDICION == "admin"`. Quitar ese archivo del repositorio no esconde
nada — cualquiera puede poner esa variable a mano. No hay secretos ahí:
solo enseña los comandos técnicos que la app ya ejecuta.

### El idioma va por build, no por selector
La edición cliente **no lleva selector de idioma**. El idioma queda fijado
al compilar, en `build_config.py` (un archivo de dos líneas), y se publican
dos ejecutables — `TechClean_ES.exe` y `TechClean_EN.exe` — para que
cada quien descargue el suyo por el nombre del archivo.

`build_config.py` está aislado a propósito: `Generar_App_Instalable.bat` lo
reescribe entre una build y la otra, y si algo falla a media compilación es
mucho mejor que quede tocado un archivo de dos líneas y no `main.py`.
`main.py` lo importa con try/except y cae a español si faltara.

La edición admin SÍ conserva el selector y la pregunta de primer arranque:
es una sola build, del propio desarrollador, y sirve para revisar cómo queda
todo en ambos idiomas sin recompilar.

## Cómo compilar

`Generar_App_Instalable.bat` (cliente) y `Generar_App_Admin.bat` (admin) —
PyInstaller, `--onefile --windowed --uac-admin`. Ambos scripts tienen una
sección de **firma digital opcional** al inicio (`CERT_THUMBPRINT` vacío por
defecto) — se activa sola en cuanto se rellene, sin tocar nada más del script.
`Iniciar_Rapido.bat`/`Iniciar_Rapido_Admin.bat` corren desde código fuente
directo, sin compilar (para probar rápido).

El script del cliente genera **las dos builds de una pasada** (ES y EN),
firma cada una si hay certificado, y restaura `build_config.py` a español al
terminar — también cuando algo falla, con una etiqueta `:error`. Antes de
compilar corre `herramientas/verificar_idiomas.py` y aborta si hay
desbalance entre idiomas: eso saldría a la luz recién con el `.exe` ya
repartido, y ahí ya es tarde.

**Los `.bat` DEBEN llevar finales de línea CRLF.** Con LF, `cmd.exe` se come
el primer carácter de cada línea (`chcp`→`hcp`, `if`→`f`) y el script falla
entero mostrando "no se encontró Python" antes de cerrarse. Los cuatro
estaban así y no compilaban nada. Hay un `.gitattributes` con
`*.bat text eol=crlf` para que no vuelva a pasar al clonar.

## Estado de publicación (a la fecha de este documento)

- **Repositorio**: `Hades3715/TechClean` (público). El buscador de
  actualizaciones está ACTIVO: `REPO_ACTUALIZACIONES` en `optimizer.py` ya
  apunta ahí. Consulta la API de GitHub Releases y compara `tag_name` (sin
  la "v" inicial) contra `APP_VERSION`. Si el repo no responde o no hay
  releases, devuelve "sin novedad" en silencio — es un estado normal, no un
  error que haya que mostrar.
- **Certificado de firma digital**: no comprado todavía (~$220/año, OV/IV de
  Sectigo o Comodo — no EV, ya no vale la pena desde que Microsoft quitó la
  ventaja de SmartScreen instantáneo en 2024). Script listo para cuando exista.
- **Donaciones**: SÍ está activo — Ko-fi conectado a PayPal (Buy Me a Coffee no
  sirve, no paga a El Salvador). `URL_DONACION = "https://ko-fi.com/hadesdev"`
  en `optimizer.py`, botón "☕ Apoyar el proyecto" en Ajustes ya funcionando.
- **Plan de distribución**: dos builds separadas por idioma (ES/EN), que se
  eligen por el nombre del archivo en Releases. **Ya implementado**: el
  selector salió de la edición cliente (ver arriba).
- **Versión**: `APP_VERSION = "1.5.0"` en `main.py`, unificada con el
  changelog del README (antes decía 1.0.0, un descuido). La etiqueta de la
  release de GitHub debe coincidir: el buscador de actualizaciones compara
  esa constante contra `tag_name`, quitandole la "v" inicial, así que la
  etiqueta `v1.5.0` es la correcta. Si no coinciden, o avisa de una
  actualización que no existe, o no avisa de una que sí.
- **Al subir una versión nueva**: cambiar `APP_VERSION`, recompilar las dos
  builds, y recién entonces crear la release con la etiqueta que coincida.
  Los `.exe` llevan la versión adentro: publicar los viejos con una etiqueta
  nueva deja la app avisando de una actualización que ya tiene instalada.

## Patrones de seguridad ya establecidos — MUY IMPORTANTE seguir igual

### Clasificación de riesgo (procesos y servicios)
`evaluar_riesgo_proceso()` y `evaluar_riesgo_servicio()` en `optimizer.py`
devuelven `("bloqueado"|"advertencia"|"normal", motivo)`. Bloqueado = la UI
deshabilita el botón por completo (candado 🔒). Advertencia = se permite pero
con aviso fuerte en rojo. Si se agrega alguna acción nueva que pueda terminar
un proceso o detener un servicio del sistema, **debe pasar por este mismo
patrón**, no una confirmación genérica.

### Ventanas emergentes (Toplevel)
Toda ventana que representa una acción larga o una decisión real necesita
`dialogo.grab_set()` — sin eso, el usuario puede hacer clic en el menú lateral
y la ventana queda escondida detrás de la principal (bug real que ya pasó y
se corrigió en varias ventanas). La ÚNICA excepción a propósito es la ventana
de error (`_mostrar_ventana_error`), que usa `-topmost` en vez de `grab_set()`
porque un error puede saltar mientras ya hay otra ventana modal abierta, y
forzar un segundo grab ahí podría chocar con el que ya existe.

### Threading
Cualquier llamada a `subprocess`, `winreg`, o consultas WMI/PowerShell debe ir
en un hilo aparte (`threading.Thread(target=worker, daemon=True).start()`),
nunca en el hilo principal de Tkinter. Cualquier callback que toque un widget
después de un `self.after(...)` debe revisar
`hasattr(self, "widget") and self.widget.winfo_exists()` antes de tocarlo —
el usuario pudo haber cambiado de pantalla mientras el hilo corría.

### `self.contenido` es compartido entre TODAS las pantallas
`_limpiar_contenido()` ahora resetea las columnas/filas del grid a un estado
base conocido cada vez que se cambia de pantalla — antes, si una pantalla
cambiaba el ancho de alguna columna para su propio diseño (como hacía
Componentes), esa configuración se quedaba pegada en la SIGUIENTE pantalla
que se abriera, dejando espacio real sin usar. Si se agrega una pantalla
nueva que necesite una configuración de grid particular, hay que configurarla
DESPUÉS de `_limpiar_contenido()`, nunca asumir que el estado anterior sigue.

### WMI está degradado en el equipo principal de pruebas
Se confirmó con datos reales (vía el Diagnóstico completo) que el subsistema
WMI de la laptop del desarrollador es lento — consultas que deberían tardar
milisegundos tardan 8-30 segundos y a veces vuelven vacías. Por eso:
- Las consultas WMI (`_cim()`) tienen timeouts generosos y configurables
  (8s por defecto, hasta 30s para las más pesadas como Drivers).
- Los refrescos frecuentes (como Componentes, cada 3s) NUNCA deben incluir
  una consulta WMI en el camino rápido — la temperatura de CPU se cachea
  aparte (`self._cpu_temp_cache`) y se actualiza cada 20s, no cada ciclo.
- El nombre de la GPU se cachea una sola vez si no es NVIDIA (no cambia
  durante la sesión, no hay razón para volver a preguntarlo).

### Registro vs. Tareas Programadas para inicio automático
La app requiere administrador (`--uac-admin`), así que el inicio automático de
LA APP MISMA usa una **tarea programada con privilegios más altos**
(`schtasks /create ... /rl highest`), NO la clave de registro `Run` normal —
una app elevada no arranca de forma confiable desde esa clave. La clave de
registro `Run` SÍ se sigue usando para gestionar apps de TERCEROS que inician
con Windows (esa es una función distinta, en la pestaña "Inicio de Windows"
de Aplicaciones) — no confundir los dos casos.

## Sistema de idiomas (`idiomas.py`)

`t("clave", **kwargs)` — diccionario `TEXTOS["es"]`/`TEXTOS["en"]`, con
interpolación tipo `.format()`. Primer arranque pregunta el idioma (bilingüe,
antes de que exista `self.contenido`); cambiar en Ajustes pide reiniciar.

**Progreso de traducción: TERMINADO.** 1,037 claves, paridad exacta entre
español e inglés, ninguna sin usar ni sin definir. Las 16 pantallas y los
ocho módulos con texto visible están migrados.

Quedan **7 textos en español a propósito**, y deben quedarse así:
- 2 son el diálogo de idioma del primer arranque, que es BILINGÜE por
  necesidad: en ese punto todavía no se sabe qué idioma habla quien abre la
  app, así que no se puede usar `t()`.
- 5 son texto técnico de comandos (`del /s /q %TEMP%`, el centinela
  `URL_DONACION vacía`, la referencia de comandos de la Consola Dev). Solo
  se ven en la edición admin.

Al agregar texto nuevo: catalogar TODOS los strings (incluidos los que solo
aparecen en callbacks, no solo en la construcción de la pantalla), agregarlo
a ambos idiomas, y correr `herramientas/verificar_idiomas.py`.

### Diccionarios que se construyen al importar el módulo
Hay cuatro que guardan **el nombre de la clave**, no el texto, y resuelven
con `t()` al usarse: `CODIGOS_ERROR_DISPOSITIVO` (system_monitor),
`SERVICIOS_BLOQUEADOS`/`SERVICIOS_ADVERTENCIA`/`PROCESOS_BLOQUEADOS`/
`PROCESOS_RECUPERABLES` (optimizer) y `COMANDOS_DISPONIBLES` (main). Se
construyen ANTES de que `establecer_idioma()` corra, así que guardar ahí el
texto traducido lo dejaría congelado en el idioma por defecto. Lo mismo vale
para los valores por defecto en la firma de una función: `t()` en un
`def f(x=t("clave"))` se evalúa al importar. Usar `None` como centinela.

### Nunca comparar contra texto traducido
El error más repetido de toda la migración, y el que más daño hacía. Si el
valor visible de una pestaña, un combo o un estado alimenta lógica, ese
valor **no** se compara contra un literal: se convierte una vez a un código
interno estable, o se compara contra la misma clave con la que se construyó.
Aparecio siete veces y provocaba desde una pestaña que abría la pantalla
equivocada hasta datos falsos sin ningún error visible (los permisos de
micrófono y ubicación mostrando los de la cámara).

## Investigaciones ya hechas — no repetirlas

- **Enfoque Asistido (Focus Assist)**: NO existe forma documentada/confiable
  de leerlo o cambiarlo por WMI/registro — confirmado, incluso empleados de
  Microsoft en sus propios foros dicen que las claves que circulan no
  funcionan consistentemente. Se deja como redirect a `ms-settings:quiethours`.
- **Efectos visuales**: SÍ hay una API oficial (`SystemParametersInfo`),
  documentada desde Windows 2000. Solo se implementaron las dos llamadas que
  se pudieron verificar con certeza total (`SPI_SETDRAGFULLWINDOWS`,
  `SPI_SETANIMATION`) — deliberadamente no se adivinaron más constantes por
  el riesgo de acertarle a un parámetro de sistema distinto al querido.
- **Canal dual/simple de RAM**: WMI no lo puede confirmar con certeza (ni
  CPU-Z siempre puede sin acceso más profundo al hardware) — se implementó
  como ESTIMADO basado en cantidad/coincidencia de módulos, etiquetado como
  tal en la interfaz.
- **Impacto de arranque por app** (como lo muestra el Administrador de
  tareas): NO tiene forma documentada de leerse desde afuera — se decidió NO
  implementarlo en vez de inventar un número que probablemente no coincida
  con lo que Windows ya muestra.
- **Inicio rápido de Windows** (`HiberbootEnabled`): clave oficial y
  documentada. Importante: NO afecta reinicios (un "Reiniciar" siempre hace
  arranque completo) — solo afecta apagar y volver a encender. Se agregó por
  su efecto documentado en la fiabilidad de instalación de drivers/updates,
  no como solución a temas de firmware/BIOS (eso está fuera del alcance de
  cualquier app de Windows).
- **Historial de arranques**: SÍ hay una fuente real (evento 100 del Visor de
  Eventos, `Microsoft-Windows-Diagnostics-Performance/Operational`) — pero en
  algunos equipos/configuraciones de Windows ese evento no se registra
  (documentado, no es un bug nuestro). La función ya maneja ese caso.
- **Precios de donación bajos** ($0.25-$0.99): NO son viables con casi
  ningún procesador de pago — el cargo fijo (~$0.30-$0.50) se come todo o
  más de esos montos. Por eso se fue por donaciones voluntarias en vez de
  cobrar la app.

## Bugs reales encontrados con uso real (histórico, para no repetirlos)

- `_cim` se llamaba en `optimizer.py` sin estar definida ahí (existía solo en
  `system_monitor.py`) — `NameError` en Drivers. Causa: nunca se probó esa
  ruta de código hasta que el desarrollador la usó de verdad.
- `reproducir_sonido_prueba` usaba `winsound.PlaySound` con un alias de
  Windows — si el usuario tiene el esquema de sonidos en "Sin sonidos", no
  sonaba nada sin ningún error. Cambiado a `winsound.Beep()` (no depende de
  ningún archivo/tema).
- Varias ventanas de reparación/diagnóstico largas no tenían `grab_set()` —
  el usuario reportó que "se cancelaban" al cambiar de pantalla; en realidad
  seguían corriendo, solo quedaban escondidas detrás de la ventana principal.
- `set_startup()` (inicio automático de la app) usaba la clave de registro
  Run normal — no funciona de forma confiable para una app que pide admin.
  Corregido con tarea programada (ver arriba).
- Al reescribir `set_startup()`, se borró por accidente la función auxiliar
  `_startup_registry_path()` que OTRA función (gestión de apps de inicio de
  terceros) todavía necesitaba — encontrado al revisar referencias cruzadas
  antes de dar por terminado el cambio, no en producción.

## Bugs encontrados durante la migración de idiomas (33 en total)

Los que enseñan algo, no la lista completa. El patrón dominante ya está
arriba ("Nunca comparar contra texto traducido").

- **La exportación de reportes guardaba donde nadie mira.** Se armaba la ruta
  como `~/Desktop`, pero con OneDrive sincronizando el escritorio y Windows
  en español, el escritorio real es `~/OneDrive/Escritorio`. `~/Desktop`
  existe pero está VACÍO, así que la escritura no fallaba: el archivo se
  guardaba, la app mostraba esa ruta, y en el escritorio no aparecía nada.
  Ahora se le pregunta a Windows con `SHGetKnownFolderPath`, vía
  `opt.carpeta_conocida("escritorio" | "descargas")`. **Nunca armar a mano
  la ruta de una carpeta conocida.**

- **El respaldo era peor que el problema.** Si fallaba escribir en el
  escritorio, caía en `BASE_DIR`. En la build `--onefile` eso es la carpeta
  temporal donde se descomprime el `.exe`, que Windows borra al cerrar: el
  archivo se "guardaba" y desaparecía solo. Ahora cae en
  `prefs.carpeta_datos()`.

- **La prueba de velocidad medía 7 veces menos.** Descargaba 10 MB y dividía
  el total entre el tiempo total, así que casi toda la medición caía dentro
  del arranque lento de TCP (slow start). Reportaba 18 Mbps sobre una línea
  de 135. Ahora descarta los primeros 2 segundos y cronometra 5 del tramo
  estable. **Cuanto más rápida la conexión, peor salía el número.**

- **Los `.bat` tenían finales de línea LF.** `cmd.exe` se comía el primer
  carácter de cada línea y los cuatro scripts fallaban enteros — incluido el
  de compilar. Ver la sección de compilación.

- **Cinco llamadas bloqueantes en el hilo de Tkinter** (vaciar portapapeles,
  escaneo de Defender, reparar Tienda, inicio automático, app de inicio):
  `subprocess` con timeouts de 10-15s congelando la ventana entera.

- **Cuatro etiquetas escritas tras `after()` sin comprobar que siguieran
  vivas.** `hasattr()` NO alcanza: el atributo sobrevive aunque el widget
  esté destruido, y por eso el fallo pasaba desapercibido. Hay que usar
  `winfo_exists()` — o el helper `_actualizar_label()`.

- **Una variable de bucle llamada `t`** pisaba la función de traducción
  dentro de su función. Cualquier `t("clave")` ahí dentro habría reventado
  con "dict object is not callable".

- **Claves internas filtradas a la interfaz**: mensajes que interpolaban la
  clave que entiende el sistema (`"silencioso"`, `"rapido"`, `"detener"`) en
  vez del nombre traducido. En inglés salía "Switching to the 'silencioso'
  profile...". La clave viaja al sistema; a la pantalla va el texto.

## Bugs encontrados en la pasada de interfaz de la 1.5.0

El usuario mandó tres capturas ("mejora esto") y de paso salió que el audio
no sonaba. Buscando por qué, aparecieron estos:

- **La subida de la prueba de internet fallaba de forma intermitente.**
  Mandaba siempre 10 MB con `timeout=15`. Una conexión de 5 Mbps de subida
  —muy común— tarda 16 s en mandar 10 MB: se agotaba el tiempo y la subida
  salía vacía en una conexión sana. Es la queja literal del usuario: "a
  veces no da la bajada y a veces no da la subida". Ahora hay un sondeo de
  1.5 MB y con ese dato se calcula un tamaño que tarde ~4 s en ESA conexión;
  si el intento grande falla, se conserva el número del sondeo.

- **El `socket.setdefaulttimeout(20)` global era MENOR que algunos timeouts
  de la propia función.** El socket se queda con el más corto de los dos, así
  que cortaba antes de lo que el código decía. Subido a 60.

- **Un fallo en la bajada cortaba la función entera** y la subida ni se
  intentaba. Ahora cada mitad es independiente.

- **El vigilante de tiempo (35 s) no miraba si la prueba ya había terminado**,
  así que en una conexión lenta pero sana pintaba "tardó demasiado" encima
  del resultado bueno. Y al pulsar "Reintentar" el vigilante viejo seguía
  programado, pisando el intento nuevo. Ahora cada ejecución lleva número de
  generación y una bandera de terminado.

- **La prueba de internet consultaba `winfo_exists()` desde el hilo de la
  prueba.** Tkinter no es seguro fuera del hilo principal — ver la sección
  de Threading. Todo pasa ya por `after(0, ...)`.

- **El tono de prueba de audio no sonaba en muchos equipos.** Este bug tiene
  dos capas: la primera versión usaba `PlaySound("SystemAsterisk")`, que
  depende del tema de sonidos de Windows; el "arreglo" fue `winsound.Beep()`,
  que resultó peor, porque **no pasa por la tarjeta de sonido**: llama al
  generador de tonos del kernel (`beep.sys`), desactivado de fábrica en
  bastantes portátiles. Las dos versiones devolvían éxito sin sonar nada. Y
  aunque Beep hubiera sonado, no probaba lo que interesa: ni el dispositivo
  de salida, ni el volumen, ni las bocinas. Ahora se sintetiza un WAV en
  memoria (`generar_wav_tono`) y se reproduce con `SND_MEMORY`.

  **Lección general:** una función que "no da error" no es una función que
  funcione. Cuando el resultado es algo que ocurre FUERA del programa —un
  sonido, una ventana, un archivo— hay que preguntarle al usuario si pasó.
  De ahí la ventana de confirmación con "¿Escuchaste el tono?".

- **Las gráficas de línea (Sparkline) tenían un ancho fijo de 260 px** aunque
  el panel que las contiene se estira con la ventana (`sticky="we"`). En una
  pantalla ancha quedaban como un bloquecito perdido en un panel enorme y
  vacío — que es exactamente lo que se veía en las capturas que mandó el
  usuario. Ahora el canvas hace `fill="x"` y se redibuja con `<Configure>`.

- **Inicio no tenía scroll.** Su contenido pide más de 1000 px de alto; en un
  portátil de 768 px, o en uno de 1080 con escalado de Windows al 125% (lo
  normal de fábrica), las dos gráficas de abajo quedaban cortadas y no había
  forma de llegar a ellas. Ahora el cuerpo va en un `CTkScrollableFrame`,
  como ya hacía Componentes.

  **Ojo al medir esto:** una ventana con `withdraw()` no calcula geometría,
  así que `winfo_width()` devuelve el tamaño de arranque y parece que nada
  se estira. Para comprobarlo de verdad hay que abrir la ventana; el banco de
  pruebas la abre en `+4000+4000`, fuera de la pantalla.

- **La gráfica de temperatura estaba siempre en rojo**, incluso a 32 °C.
  Alarmaba sin motivo. Ahora el color sigue la temperatura real.

## Segunda pasada de revisión de la 1.5.0 (buscando bugs a propósito)

Esta tanda salió de revisar el widget y los modulos que nunca se habian
mirado a fondo. Casi todos son del mismo puñado de patrones que ya estaban
documentados aquí arriba — la lección es que documentarlos no basta: hay
que tener una herramienta que los busque sola.

- **Modo Juego le subía la prioridad al Explorador de Windows.** La
  heurística era "si la ventana activa mide lo mismo o más que la pantalla,
  es un juego". Dos falsos positivos, los dos comprobados en el equipo:
  al minimizar todo, la ventana en primer plano pasa a ser Progman —el
  escritorio, dueño explorer.exe— que mide exactamente la pantalla; y
  cualquier ventana MAXIMIZADA cuenta también, porque Windows le da unos
  píxeles de más por los bordes invisibles de redimensionado.

  La regla que de verdad separa los casos es **WS_CAPTION**: un juego a
  pantalla completa (o en ventana sin bordes) no tiene barra de título;
  una ventana maximizada sí la conserva. Está cubierto por
  `prueba_modo_juego.py`.

- **Cuatro sitios más tocaban la interfaz desde un hilo** sin pasar por
  `after(0, ...)` y sin comprobar `winfo_exists()`. Ya se había corregido
  este patrón dos veces (autopiloto, prueba de velocidad) sin revisar si
  quedaban más. Quedaban. Ahora hay `revisar_hilos.py`, que los busca solo.

- **Vaciar la papelera congelaba la ventana.** `SHEmptyRecycleBinW` es
  síncrona: borra de verdad antes de volver. Iba en el hilo principal, en
  el botón de Inicio (el primero que toca cualquiera). Y encima no se
  miraba lo que devolvía, así que decía "vaciada ✅" pasara lo que pasara.

- **El widget saltaba al arrastrarlo.** Guardaba `event.x`, que es la
  posición del clic DENTRO del widget que lo recibió — y en Tk una
  vinculación puesta en el toplevel salta también con los eventos de todos
  sus hijos. Agarrándolo por un botón de atajo, ese número valía 5 en vez
  de 300 y la ventana pegaba un brinco. Lo correcto es el desfase contra
  la VENTANA: `winfo_pointerx() - winfo_x()`.

- **Las preferencias se leían del disco en cada consulta** y el widget las
  consulta cada segundo. Además `carpeta_datos()` llamaba a `os.makedirs`
  en cada lectura: 245 µs por llamada, el 65% del coste total, para
  comprobar algo que ya se sabía. Ahora hay caché con firma del archivo
  (mtime + tamaño) y la carpeta se crea una vez por ejecución.

- **Guardar preferencias no era atómico**: `open(ruta, "w")` vacía el
  archivo ANTES de escribir. Un corte a mitad y `preferencias.json` queda
  roto; como `cargar()` se traga los errores y devuelve valores de fábrica,
  el usuario perdía toda su configuración sin un solo aviso.

- El widget pintaba la temperatura con `_color()`, que es para
  PORCENTAJES: 62 °C —normal— salía en ámbar. Mismo error que ya se había
  corregido en la gráfica de Inicio; el widget se quedó fuera.

- Los tooltips del widget son `Toplevel` aparte: al ocultar el widget con
  uno abierto, el globito negro se quedaba flotando solo en el escritorio.

- Oculto, el widget seguía haciendo las consultas CARAS (GPU, temperatura)
  y repintándose cada segundo. Y al volver marcaba un pico de red falso,
  porque dividía todo el tráfico acumulado mientras estuvo oculto entre un
  segundo.

### Añadido: la temperatura ahora sí funciona en este equipo

Solo se consultaba `MSAcpi_ThermalZoneTemperature` (root/wmi). En el
portátil del desarrollador esa clase no devuelve NADA, y sin embargo
`Win32_PerfFormattedData_Counters_ThermalZoneInformation` sí: da 324, que
son 50.9 °C. La app decía "No disponible en este equipo" teniendo el dato
a mano, y con eso se quedaban muertas cuatro cosas: la tarjeta de
temperatura, su gráfica, la fila del widget y la alerta de Ajustes.

**Cuidado con las unidades**: la clase ACPI da DÉCIMAS de kelvin; el
contador da KELVIN ENTEROS. Confundirlas da un número absurdo.

Y hay que **recordar cuál de las dos funciona**: cada consulta WMI levanta
un PowerShell y cuesta ~0.9 s. Probar siempre las dos, sabiendo ya cuál
contesta, era pagar el doble en una función que el widget llama cada
4 segundos.

## Inspección completa (la pasada de "no dejes nada sin mirar")

Se revisó la app entera a propósito, no buscando un fallo concreto. Salió
una tanda entera del MISMO patrón, que a estas alturas es claramente el
punto débil del proyecto:

> **Una función que no da error no es una función que funcione.** Cuando
> el resultado ocurre FUERA del programa —un sonido, una ventana, un
> archivo borrado, un proceso que arranca— hay que comprobarlo, no
> suponerlo.

Ya había pasado con el tono de audio, la papelera y el Game Bar. En esta
pasada aparecieron seis más:

- **Reiniciar el Explorador** mataba explorer.exe, lo lanzaba de nuevo y
  devolvía True sin comprobar nada. Si el arranque fallaba, el usuario se
  quedaba sin barra de tareas, sin menú Inicio y sin iconos del
  escritorio, con la app diciéndole que todo fue bien. Ahora espera a ver
  el proceso vivo y reintenta una vez.

- **Limpiar la caché del navegador** medía el tamaño ANTES de borrar e
  informaba ese número como espacio liberado. Y `rmtree` iba con
  `ignore_errors=True`, que nunca lanza: el `except` era código muerto.
  Un navegador deja archivos bloqueados aunque parezca cerrado, así que se
  borraba una parte y se anunciaba el total.

- **Quitar la limpieza programada** apagaba el interruptor aunque la tarea
  siguiera ahí ejecutándose sola cada día.

- **Reducir animaciones** no miraba lo que devuelve `SystemParametersInfo`.

- **`flush_dns`** no miraba el código de salida de ipconfig.

- **Las notificaciones** daban por mostrada una que podía no salir nunca —
  y de eso dependen las alertas de temperatura.

Aparte: apagar, reiniciar y entrar a la BIOS eran las únicas llamadas a
`shutdown.exe` sin `CREATE_NO_WINDOW`, así que asomaba una consola negra
justo antes de que la pantalla se fuera; y ninguna de las cuatro llevaba
timeout.

### Lo que la inspección confirmó que SÍ está bien

Vale documentarlo para no volver a revisarlo desde cero:

- Ningún `except:` pelado, ningún `open()` sin `with`, ninguna función
  duplicada, ninguna clave de diccionario repetida, ningún `is` con
  literales, ningún nombre pisando `t()` ni un builtin.
- Las 130 lecturas con corchetes de la interfaz están cubiertas:
  `revisar_claves.py` comprueba que toda clave que se lee la escribe
  alguien. No hace falta reescribirlas a `.get()`.
- Las funciones lentas (`get_system_info` 4 s, `get_cpu_details` 1.3 s)
  ya se llaman todas desde un hilo.
- Los 21 comandos del panel oculto están implementados y anunciados, y la
  entrada rara (vacía, 5000 caracteres, símbolos, acentos) no rompe nada.
- Los 19 guardados de preferencias actualizan también la copia en memoria
  (`self.prefs`), así que ningún ajuste necesita reiniciar para aplicarse.

### Lo único que salió de la revisión de bucles

`_refrescar_componentes` se paraba comprobando si su panel seguía vivo, y
eso casi siempre basta — pero al salir de la pantalla queda un tic ya
programado. Si el usuario volvía a entrar antes de que saltara, ese tic se
encontraba un panel nuevo, daba la comprobación por buena y seguía vivo,
sumándose al bucle recién arrancado. Cada ida y vuelta rápida dejaba un
bucle más, cada uno consultando WMI cada pocos segundos, para siempre.

**Lección para cualquier bucle nuevo:** comprobar que el widget siga vivo
NO alcanza para pararlo. Hace falta un número de generación, como el que
ya usaban la prueba de velocidad y el autopiloto.

## Módulos nuevos de la 1.5.0

**`deshacer.py`** — registro de cambios reversibles. La regla que gobierna
todo el módulo: se guarda el estado **ANTERIOR**, nunca el nuevo. Sin saber
de dónde se venía no hay vuelta atrás, y es el error fácil de cometer (el
perfil de energía hay que leerlo ANTES de aplicar el nuevo). Lo que no se
puede deshacer se dice en la propia pantalla, arriba de la lista.

**`tecnico.py`** — las tres herramientas de la Edición Administrador. Ojo
con `comparar_fotos`: cada campo lleva escrito si SUBIR es bueno o malo. Sin
eso la tabla del antes/después diría que subir la RAM usada es una mejora,
y esa tabla es justo la que un técnico le enseña a un cliente.

**`instalador/TechClean.iss`** — script de Inno Setup. El desinstalador
borra las tareas programadas que la app crea; si un nombre no coincide, la
tarea queda huérfana intentando ejecutar un archivo borrado. `revisar_instalador.py`
compara esos nombres contra las constantes reales de `optimizer.py`, y ya
pilló un error así.

## Rutina de auditoría — correr SIEMPRE antes de dar algo por terminado

Ya no es a mano: doble clic en **`herramientas\Verificar_Todo.bat`**, que
corre las cinco comprobaciones seguidas y espera una tecla al final. Los
`.py` sueltos imprimen y salen, así que al hacerles doble clic la ventana se
cierra antes de poder leer nada — para eso está el `.bat`.

| Herramienta | Qué comprueba |
|---|---|
| `auditoria.py` | Duplicados de clase/módulo, `self._algo()` sin definir, `opt.`/`sysmon.` inexistentes |
| `verificar_idiomas.py` | Paridad es/en, claves sin definir o sin usar, y que los `{campos}` coincidan entre idiomas |
| `prueba_arranque.py` | Construye la ventana y abre las 16 pantallas, en el idioma que se le pase |
| `prueba_ediciones.py` | Qué opciones ve cada edición (cliente vs admin) |
| `prueba_animacion.py` | Que las barras, gráficas, aguja y tarjetas animen, y no revienten al destruirlas a media animación |
| `revisar_hilos.py` | Que nadie toque la interfaz desde un hilo de fondo sin pasar por `after(0, ...)` |
| `prueba_widget.py` | Widget flotante: arrastre sin saltos, límites de pantalla, tooltips, colores de temperatura, no trabajar oculto |
| `prueba_modo_juego.py` | Que el escritorio, la barra de tareas y una ventana maximizada NO se tomen por un juego |
| `prueba_limpieza_temp.py` | Que limpiar temporales no borre la propia app descomprimida en `%TEMP%\_MEIxxxxx` |
| `prueba_velocidad.py` | Que la prueba de internet devuelva latencia, bajada **y** subida (usa ~60 MB de datos reales) |
| `prueba_historial.py` | Que el historial sobreviva al cierre, aguante una línea corrupta y se recorte solo |
| `prueba_hilos_interfaz.py` | El puente hilo→interfaz, antes de `mainloop()` y después de cerrar |
| `revisar_claves.py` | Que toda clave que lee la interfaz la escriba algún módulo de datos |
| `revisar_lecturas.py` | Ejecuta las ~30 consultas de solo lectura y revisa tipo, claves y cuánto tardan |
| `revisar_comandos.py` | Que los 21 comandos del panel oculto existan, naveguen y aguanten entrada rara |
| `revisar_pantallas.py` | Abre las 16 pantallas, pulsa cada pestaña y repinta con datos vacíos o a medias |
| `prueba_deshacer.py` | Que deshacer llame a la función inversa correcta, con un optimizer de mentira |
| `prueba_tecnico.py` | Foto antes/después, inspector de arranque y grabación a CSV |
| `revisar_instalador.py` | Que el script del instalador no mienta sobre archivos, versión ni tareas |
| `revisar_ajustes.py` | Que cambiar un ajuste surta efecto sin reiniciar (que se actualice `self.prefs`, no solo el disco) |
| `prueba_bucles.py` | Que entrar y salir de Componentes deprisa no deje bucles de refresco acumulados |

Ninguna muestra ventanas ni toca las preferencias reales: apuntan `APPDATA`
a una carpeta temporal.

Sigue valiendo, y ninguna herramienta lo cubre:
- `python -m py_compile` de todos los `.py` (lo hace cualquier import, pero
  conviene tenerlo presente).
- Si se agrega una ventana `Toplevel`: confirmar que tiene `grab_set()`, o
  una razón documentada para no tenerlo (como la ventana de error).

## Ideas ya discutidas y descartadas (para no proponerlas de nuevo sin repensar)

- Verificación de activación de Windows: descartada, no tiene relación con
  rendimiento (la app está enfocada en eso, no en diagnóstico general).
- Quitar Privacidad/Seguridad de la app por no ser "rendimiento" puro: se
  decidió NO quitar nada — son secciones útiles ya construidas, aunque no
  encajen 100% en el tema de rendimiento.
- Meta de donación en Ko-fi ("Set a goal"): se decidió esperar — no tiene
  sentido sin movimiento previo en la página, y "pagar mis estudios" es un
  apoyo continuo, no algo puntual con un final claro. Si en el futuro se
  quiere, algo concreto y medible (como "$220 para la firma digital") sí
  encajaría bien ahí.
