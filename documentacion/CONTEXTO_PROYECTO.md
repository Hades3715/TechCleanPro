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

- **Versión actual**: 1.7.0 (preparada el 2026-10-04; la 1.6.0 se publicó ese mismo día) (`APP_VERSION` en `codigo/main.py`)
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

`compilar/Generar_App_Instalable.bat` (cliente) y `compilar/Generar_App_Admin.bat` (admin) —
PyInstaller, `--onefile --windowed --uac-admin`. Ambos scripts tienen una
sección de **firma digital opcional** al inicio (`CERT_THUMBPRINT` vacío por
defecto) — se activa sola en cuanto se rellene, sin tocar nada más del script.
`Iniciar.bat`/`Iniciar_Admin.bat` (en la raíz) corren desde código fuente
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

- **Repositorio**: `Hades3715/TechCleanPro` (público; se llamaba así cuando
  la app era "TechClean Pro" y el nombre se quedó). El buscador de
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
- **Versión**: `APP_VERSION = "1.7.0"` en `codigo/main.py`, unificada con el
  changelog del README (antes decía 1.0.0, un descuido). La etiqueta de la
  release de GitHub debe coincidir: el buscador de actualizaciones compara
  esa constante contra `tag_name`, quitandole la "v" inicial, así que la
  etiqueta `v1.7.0` es la correcta. Si no coinciden, o avisa de una
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

**`compilar/TechClean.iss`** — script de Inno Setup. El desinstalador
borra las tareas programadas que la app crea; si un nombre no coincide, la
tarea queda huérfana intentando ejecutar un archivo borrado. `revisar_instalador.py`
compara esos nombres contra las constantes reales de `optimizer.py`, y ya
pilló un error así.

## Estructura de carpetas (reorganización de la 1.5.0)

La raíz tenía 35 cosas sueltas: los 14 `.py`, cinco `.bat` de nombres
parecidos, los `.md`, un `.exe` de respaldo de 22 MB, `dist/` con 44 MB de
sobras y hasta un `.txt` basura de un comando mal escrito. Quedó así:

```
Iniciar.bat, Iniciar_Admin.bat   ← abrir desde el código (antes Iniciar_Rapido*.bat)
TechClean_*.exe                  ← los compilados, a la vista
codigo/          los 15 módulos de la app
compilar/        Generar_App_*.bat, Compilar_Instalador.bat, TechClean.iss
documentacion/   este archivo y las notas de versión
herramientas/    el banco de pruebas
assets/          icono y sonido
```

Cosas que hay que saber para no romperla:

- **`codigo/rutas.py` es el único sitio que sabe dónde está `assets/`.**
  Antes era `dirname(__file__)`, y funcionaba porque todo estaba junto. Con
  el código en `codigo/`, eso apunta a `codigo/assets`, que no existe — y el
  síntoma habría sido la app sin icono ni sonido **solo desde el código**:
  compilada va bien porque PyInstaller descomprime todo junto en `_MEIPASS`.
  Un fallo invisible en lo que se reparte y visible solo para quien programa.
- **Los generadores viven en `compilar/` pero trabajan desde la raíz**:
  hacen `cd /d "%~dp0.."`. Así `assets`, `requirements.txt`, `dist` y el
  `.exe` de salida siguen valiendo tal cual; solo cambia que el script de
  entrada es `codigo\main.py` y que PyInstaller recibe `--paths codigo`.
- **Las herramientas piden las rutas a `herramientas/_rutas.py`.** Antes
  cada una lo resolvía a su manera, y varias dependían del directorio actual
  (`sys.path.insert(0, ".")`, `open("main.py")`): funcionaban solo porque el
  `.bat` hacía `cd` a la raíz antes. Ahora ninguna depende de dónde se la
  llame. `_rutas.MODULOS` es la única lista de módulos; `revisar_empaquetado`
  la usa en vez de tener la suya.
- `revisar_empaquetado.py` cazó la reorganización a medias: tras crear
  `rutas.py`, los `.exe` viejos no lo llevaban dentro. Recompilar lo arregló.

### Bug encontrado al recompilar: el generador admin decía "Listo" sin copiar

`Generar_App_Admin.bat` tenía `copy /Y ... >nul`. Con el `.exe` anterior
abierto (lo normal: uno lo deja en la bandeja para probar), Windows no deja
sobreescribirlo, el `copy` fallaba en silencio y el script decía "Listo"
dejando el ejecutable **de tres horas antes**. Ese mismo arreglo ya estaba
en `Generar_App_Instalable.bat`, pero nunca llegó al otro generador: dos
copias del mismo paso, el arreglo en una sola. Ahora los dos apartan el
`.exe` viejo con `ren` (Windows sí deja renombrar un `.exe` en ejecución) y
comprueban el `errorlevel` del `copy`. Comprobado: se recompiló con dos
`TechClean_Admin.exe` corriendo.

Es el tercer caso del mismo patrón en la 1.5.0 (las dos consolas, los dos
generadores, las dos listas de módulos): **cuando algo existe dos veces, un
arreglo llega a una sola.**

## Rutina de auditoría — correr SIEMPRE antes de dar algo por terminado

Ya no es a mano: doble clic en **`herramientas\Verificar_Todo.bat`**, que
corre las 35 comprobaciones seguidas y espera una tecla al final. Los
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
| `revisar_comandos.py` | Que los 25 comandos del panel oculto existan, naveguen y aguanten entrada rara |
| `prueba_consola.py` | La consola entera: historial con flechas, Tab, tope de líneas, color por tipo de línea, y con `ast` que no quede ni una frase escrita a mano sin traducir |
| `revisar_pantallas.py` | Abre las 16 pantallas, pulsa cada pestaña y repinta con datos vacíos o a medias |
| `prueba_deshacer.py` | Que deshacer llame a la función inversa correcta, con un optimizer de mentira |
| `prueba_tecnico.py` | Foto antes/después, inspector de arranque y grabación a CSV |
| `revisar_instalador.py` | Que el script del instalador no mienta sobre archivos, versión ni tareas |
| `revisar_empaquetado.py` | Que los `.exe` ya compilados lleven dentro todo lo que la app importa (abre el CArchive, el PYZ y `base_library.zip`). No destructiva: se puede correr siempre |
| `revisar_ajustes.py` | Que cambiar un ajuste surta efecto sin reiniciar (que se actualice `self.prefs`, no solo el disco) |
| `prueba_bucles.py` | Que entrar y salir de Componentes deprisa no deje bucles de refresco acumulados |
| `prueba_memoria.py` | Liberación de RAM: estructuras de Windows, que excluir un proceso no use órdenes de sistema y, como admin, que cada paso funcione de verdad |
| `prueba_auto_ram.py` | Liberación automática: umbral con espera de 2 min, intervalo, que se aparte con el Modo Juego, y la espera del autopiloto |
| `prueba_limpieza_fondo.py` | Borrado seguro: no entrar en uniones, no contar lo bloqueado, filtros, salida de sfc/DISM y que no se cuelgue con mucha salida |
| `prueba_vigilante.py` | Qué es y qué no es una fuga, avisos sin repetir, PIDs reciclados, disco lleno, y la lectura rápida de procesos contra psutil |
| `prueba_dns_unidades.py` | Consulta DNS contra un servidor de mentira local, filtrado de lo que llega a PowerShell, proveedores y plan Máximo. No cambia nada |
| `prueba_gaming.py` | Cerrar/reabrir apps (nunca el juego ni lo intocable), ajustes de juego contra una clave de prueba propia, cuentas del lag |
| `prueba_seguridad.py` | El malware real se detecta; Lenovo/Discord/OneDrive no; mineros, exclusiones, antivirus |
| `prueba_apps_sistema.py` | Tabla de winget en cualquier idioma, bloatware solo de la lista, duplicados, puntos de restauración con Windows sustituido |
| `revisar_errores_banco.py` | Los errores que la APP registró durante el banco (`ultimo_error.txt` de cada prueba). Va al final, tras marcar el inicio |

Ninguna muestra ventanas ni toca las preferencias reales: apuntan `APPDATA`
a una carpeta temporal.

Sigue valiendo, y ninguna herramienta lo cubre:
- `python -m py_compile` de todos los `.py` (lo hace cualquier import, pero
  conviene tenerlo presente).
- Si se agrega una ventana `Toplevel`: confirmar que tiene `grab_set()`, o
  una razón documentada para no tenerlo (como la ventana de error).

## Pasada de consola y widget (repaso de acabado)

### Lo que se hizo en la consola

Las dos consolas (Consola Dev del admin y Panel de comandos del cliente) eran
dos clases separadas haciendo casi lo mismo, y eso ya había producido un bug:
el botón de la del cliente decía `"Enviar"` **escrito a mano en el código**,
así que en la build en inglés salía en español. Ahora las dos salen de
`_ConsolaBase` y solo eligen color y título.

Lo que se le añadió: historial con ↑/↓ (con recuperación del borrador al
bajar hasta el final), completar con Tab, fichas clicables, hora y color por
tipo de línea, tope de 400 líneas con recorte por arriba, sugerencia del
comando parecido con `difflib`, y copiar / limpiar / guardar el registro.

Cuatro comandos nuevos: `/estado`, `/version`, `/limpiar`, `/guardar`.

**Cuidado al tocar `_ejecutar_comando`:** `revisar_comandos.py` y
`prueba_consola.py` le pasan una consola de mentira. Si cambia lo que se le
pide a una consola (por ejemplo cuando `imprimir` empezó a recibir un `tipo`),
hay que actualizar esas clases falsas o el banco falla con `TypeError` en
todos los comandos — un fallo del banco, no de la app.

### Lo que se hizo en el widget

- **Esquinas redondeadas de verdad**, con `-transparentcolor` y un lienzo de
  fondo que dibuja un polígono suavizado. El color clave (`#ff00fe`) NO puede
  aparecer en ningún otro widget: donde aparezca, Windows abre un agujero en
  la ventana. Hay una comprobación que recorre el fondo de todos los widgets
  del contenido para verificarlo.
- El orden importa: `-transparentcolor` **antes** de `-alpha`. Las dos se
  apoyan en la misma ventana en capas de Windows y al revés la primera se
  queda sin efecto.
- **`Canvas.lower()` no es el de apilar ventanas**, es `tag_lower()`, que baja
  un dibujo dentro del lienzo y pide su nombre. Llamarlo sin argumentos
  revienta con `wrong # args` y el widget no abre. El de apilar es
  `tk.Misc.lower(w)`.
- **La barra compacta temblaba.** Sin `width`, una etiqueta de Tk se mide por
  su texto: de "CPU 9%" a "CPU 10%" crecía un carácter y empujaba a las de su
  derecha. Ancho fijo en caracteres **y** tipografía de ancho fijo.
- Minigráfica con las últimas 40 muestras por métrica. La historia se apunta
  con el valor **medido**, no con los pasos intermedios de la animación: si no,
  la gráfica dibuja la animación en vez de lo que hizo el sistema.
- Hover en los atajos, menos en el de Modo Juego: su fondo ya dice si el modo
  está encendido, y pintarlo al apuntarlo haría dudar de si está activo.

**Al probar el widget con `event_generate`:** Tk no reparte eventos de cruce a
un widget que no está mostrado. Los atajos viven dentro del panel plegado, así
que hay que llamar a `_toggle_expandir()` antes o el hover parece roto
estándolo. Y el fondo se lee **inmediatamente** después del `<Enter>`, sin
pasar por `update()`: al procesar la cola aparece el globo del tooltip, que es
una ventana nueva encima, y el gestor de ventanas manda entonces un `<Leave>`
de verdad porque el ratón de carne y hueso no está ahí.

### La lección de esta pasada: el banco de pruebas también es código

`Verificar_Todo.bat` llevaba **ocho** rutas mal escritas. Se habían escrito
como `herramientas\revisar_algo.py` y esa barra invertida seguida de `r`
acabó convertida en un retorno de carro de verdad dentro del archivo — el
mismo tipo de destrozo que ya había pasado con `\n` en `idiomas.py` al usar
heredocs del shell.

Lo grave no es el error, es que **no se notaba**: cmd leía
`python herramientas` (que falla) y `evisar_algo.py` como otro comando, y un
`.bat` sigue con la línea siguiente cuando una falla. El banco imprimía los
23 títulos, no imprimía ningún FALLO, y parecía estar pasando entero. En
realidad corrían 15.

Tres cosas cambiaron por esto:

1. **Las rutas del `.bat` van con barra normal** (`herramientas/x.py`). cmd y
   Python la aceptan igual, y sin barras invertidas no hay nada que se pueda
   convertir en otra cosa.
2. **Cada comprobación pasa por `:comprobar`**, que mira el `errorlevel`,
   cuenta los fallos y avisa cuando una no llega ni a arrancar. Al final dice
   cuántas pasaron. Y `auditoria.py` ahora **devuelve código de salida** —
   antes encontraba cosas y el banco la daba por buena.
3. **Sección 5 de `auditoria.py`**: vigila el propio `.bat`. Busca retornos de
   carro sueltos, scripts invocados que no existen, y scripts escritos que
   nadie invoca. Se probó rompiendo el archivo a mano: lo detecta por las tres
   vías.

> **Corolario de "una función que no da error no es una función que
> funcione":** una comprobación que no da error no es una comprobación que se
> esté ejecutando. Cuando se añade un banco de pruebas nuevo, hay que verlo
> **fallar** al menos una vez a propósito.

### Cómo revisar la consola o el widget a ojo sin capturar la pantalla del usuario

No hace falta abrir la app y hacer una captura de pantalla completa. Se monta
la pieza sola en una ventana propia, con datos de mentira pero realistas, y se
recorta la captura al rectángulo exacto de esa ventana
(`winfo_rootx/rooty/width/height`) con `CopyFromScreen`. Para el widget se
pone detrás un panel de color plano propio y se deja 16 px de margen, que es
lo que hace falta para ver si las esquinas quedaron redondeadas. Así en la
imagen no entra nada de lo que la persona tenga abierto.

Y `SetProcessDpiAwareness(1)` antes de crear la ventana, o en una pantalla
escalada la captura sale recortada arriba a la izquierda en vez de escalada.

### Cuidado con `prueba_frozen.py`

Esa prueba limpia los temporales **de verdad** (es lo que reproducía su bug),
así que se lleva por delante cualquier archivo que otro programa tenga abierto
en `%TEMP%` — incluidos los de la herramienta con la que estés trabajando. Se
corre a mano y aparte. Para lo que se necesita el 99% de las veces —saber si
un módulo quedó dentro del `.exe`— está `revisar_empaquetado.py`, que lee el
binario sin ejecutarlo y sin borrar nada.

## Liberación de RAM a nivel de sistema (para la 1.6.0)

Queja del usuario: con la misma RAM, Mem Reduct liberaba bastante más.
Tenía razón, y no por poco. `trim_process_memory` era solo un bucle de
`EmptyWorkingSet` proceso por proceso, y eso deja fuera tres cosas:

1. **Los procesos protegidos** (antivirus, servicios, "System"):
   `OpenProcess` no los abre, así que nunca se tocaban.
2. **La caché de archivos del sistema**: vive en el working set del
   SISTEMA, no en el de ningún proceso.
3. **La lista modificada**: páginas pendientes de escribir a disco, que
   cuentan como memoria EN USO hasta que alguien las escribe.

Ahora `liberar_memoria(nivel)` en `optimizer.py` hace lo mismo que Mem
Reduct y RAMMap: `NtSetSystemInformation(SystemMemoryListInformation)` para
vaciar todos los working sets y escribir la lista modificada, más
`SetSystemFileCacheSize(-1, -1)` (este sí documentado) para la caché.
`trim_process_memory` sigue existiendo con la misma firma y llama a la
nueva, así que los ocho sitios que liberan RAM (Optimizador, Inicio,
widget, autopiloto, consola, Modo Juego, limpieza programada) mejoraron
sin tocarlos.

**Dos niveles, a propósito:**
- `normal`: lo de arriba. Seguro para el autopiloto.
- `profunda` (botón aparte en el Optimizador): además vacía la lista EN
  ESPERA y combina páginas idénticas. La lista en espera es caché de
  disco: vaciarla hace que lo próximo que se abra tarde algo más. Por eso
  nunca se hace en automático.

**Cosas que hay que saber para no romperlo:**
- **Ser administrador no basta**: los privilegios
  `SeProfileSingleProcessPrivilege` y `SeIncreaseQuotaPrivilege` vienen
  APAGADOS en el token. `_activar_privilegio` los enciende, y mira
  `GetLastError() == 0` porque `AdjustTokenPrivileges` devuelve éxito
  aunque no haya podido asignar nada (error 1300).
- **Con un proceso excluido** (el juego del Modo Juego) NO se usa ninguna
  orden de sistema: vacían todo sin excepciones, y escribir la lista
  modificada en mitad de una partida puede dar un tirón de disco. Se cae
  al bucle de siempre.
- **Vaciar la lista en espera NO sube la memoria disponible**: esas páginas
  ya cuentan como disponibles. Por eso el nivel profundo informa la caché
  en espera aparte (antes → después). Sin eso parecería que no hizo nada.
- Sin administrador (corriendo desde `Iniciar.bat` sin elevar) se cae al
  bucle viejo y la pantalla lo dice. No presume de liberación completa.

**Medido en la laptop del desarrollador (como administrador):** normal,
38 % → 25 % (2.5 GB); profunda, caché en espera de 14.8 GB → 51 MB.
`herramientas/prueba_memoria.py` lo comprueba, incluida la verificación
cruzada de la estructura: libre + en espera cuadró con la memoria
disponible al 0 %. Sin admin solo prueba el camino de respaldo; para la
parte completa hay que correrla elevada (y con `--profunda` para el
segundo nivel, que no va en el banco porque vacía la caché del equipo).

## Liberación automática de RAM (para la 1.6.0)

**El ajuste mentía.** Ajustes decía "TechClean libera memoria sola en
segundo plano, sin que tengas que hacer nada", pero eso solo lo hacía el
autopiloto, y el autopiloto solo corre con el Modo Juego encendido. Con el
Modo Juego apagado, el umbral se guardaba y nunca pasaba nada.

Ahora hay `LimpiezaAutomaticaRAM` en `autopilot.py`, encendida por defecto
(`auto_ram_activa`), que libera al pasar el umbral y, si se elige, cada N
minutos (`auto_ram_intervalo_min`). Reglas:

- **Con el Modo Juego activo se aparta.** El autopiloto ya libera RAM
  EXCLUYENDO el juego; si actuaran las dos, esta vaciaría la memoria del
  juego.
- **Solo nivel normal**, nunca el profundo: vaciar la caché en espera en
  automático haría que todo abriera más lento sin que nadie supiera por qué.
- **2 minutos de espera tras liberar por umbral** (`ESPERA_TRAS_LIBERAR_SEG`).
  El autopiloto del Modo Juego NO la tenía: con la RAM por encima del
  umbral (lo normal cuando de verdad se necesita esa memoria) liberaba cada
  8 segundos para siempre, forzando a todo a recargar de disco. Era el
  autopiloto el que daba los tirones que se suponía que evitaba.
- `revisar(ahora=...)` está separado del bucle para probarlo sin hilos ni
  esperas (`prueba_auto_ram.py`).

## Limpieza a fondo del disco (para la 1.6.0)

Pestaña nueva en Espacio en disco: lo mismo que el Liberador de espacio de
Windows (descargas de Windows Update, Optimización de distribución,
informes de errores, volcados de memoria, registros CBS archivados), con el
tamaño real de cada cosa. Y aparte, `DISM /StartComponentCleanup`.

**Lo que hay que saber para no romperlo:**
- **`_vaciar_contenido` NUNCA entra en uniones ni enlaces** (`_es_enlace`).
  Una unión dentro de una caché puede apuntar a cualquier sitio, y seguirla
  convierte "vaciar la caché" en "vaciar lo que haya al otro lado". La
  prueba lo comprobó rompiéndolo: sin esa protección borró un archivo de
  fuera de la carpeta.
- **Se mide antes y después**, nunca se suma lo que se intentó. Un archivo
  en uso no se borra y no cuenta.
- **Windows Update: se respeta lo de los últimos 3 días**, por si hay una
  actualización descargándose o instalándose.
- **CBS: solo `CbsPersist_*`.** `CBS.log` es el que se lee tras un sfc.
- **DISM sin `/ResetBase`**: con él ya no se puede desinstalar ninguna
  actualización. Lo liberado se mide como espacio libre del disco antes y
  después (DISM no lo informa). Si se cambia de pantalla sigue corriendo,
  y al volver el botón ofrece CANCELAR ese, no lanzar otro.
- **Fuera a propósito**: caché de sombreadores (los juegos darían tirones
  al recompilarlos, en una app con Modo Juego), Prefetch (Windows lo usa
  para abrir más rápido; borrarlo es un mito) y Windows.old (se borra solo
  a los 10 días y quitarlo a mano exige tomar posesión de archivos).

## Vigilante: fugas de memoria y disco casi lleno (para la 1.6.0)

`Vigilante` en `autopilot.py` (no en un módulo nuevo: un módulo nuevo deja
los `.exe` viejos sin él y `revisar_empaquetado` falla hasta recompilar).
Una muestra por minuto; avisa con notificación de Windows.

- **Fuga** (`es_fuga`, función pura): ≥30 min observado, ≥500 MB **y** ≥50 %
  de crecimiento, sube en 6 de cada 10 muestras, y sigue arriba ahora. Los
  umbrales son conservadores a propósito: un aviso falso enseña a ignorar
  los verdaderos. Se mide la memoria PRIVADA, no el working set: el working
  set baja cada vez que TechClean libera RAM y la fuga parecería curarse.
- La clave es `(pid, hora_de_creación)`: Windows recicla PIDs, y sin la hora
  un programa nuevo heredaba la historia de uno cerrado.
- "Memory Compression", System, etc. no se vigilan: crecer es su trabajo.
- **Disco**: mismo umbral que el semáforo de Inicio (`umbral_salud_disco`).
  Como mucho un aviso al día por unidad; se rearma si baja 5 puntos.
- **La lectura de procesos NO usa psutil.** Para los procesos protegidos
  psutil pide la lista ENTERA del sistema una vez por proceso: 1.6 s por
  muestra. `_leer_procesos_nt` hace una sola llamada a
  `NtQuerySystemInformation(SystemProcessInformation)`, como el Administrador
  de tareas: 10 ms. La estructura se comprueba contra psutil (PIDs, hora de
  creación exacta, memoria privada) en `prueba_vigilante.py`.
- La lista de procesos de Optimizar marca en ámbar los que tienen fuga.

## Plan Máximo rendimiento (para la 1.6.0)

Viene OCULTO en Windows: se copia de su plantilla
(`e9a42b02-d5df-448d-aa00-03f14749eb61`) con `/duplicatescheme` y un GUID
**fijo propio** (`POWER_PLANS["maximo"]`). Con uno al azar, cada clic
dejaba otro plan igual en el Panel de control. Probado en la laptop del
desarrollador: se crea, se activa, el segundo clic no duplica, y se vuelve
al plan anterior. En portátiles con Modern Standby Windows puede negarse;
la app lo dice con su propio mensaje.

**Deshacer el plan ahora vuelve al plan EXACTO** (`guid_anterior`, leído a
Windows antes de cambiar). Antes se guardaba el perfil de las preferencias,
y si el usuario estaba en un plan propio o del fabricante, deshacer lo
mandaba a Equilibrado.

## Optimizar unidades (para la 1.6.0)

`Optimize-Volume -DriveLetter X` sin parámetros: Windows decide (TRIM en
SSD, desfragmentar en HDD), igual que su propia herramienta. La app NUNCA
elige desfragmentar: hacerlo en un SSD no sirve y lo desgasta. La letra
pasa por `_letra_unidad`, que deja solo una letra A-Z, porque va dentro de
un comando de PowerShell. El tipo de disco tarda ~8 s en leerse
(Get-PhysicalDisk, WMI lento) y se cachea por sesión.

## DNS más rápido (para la 1.6.0, en Reparar)

Mide con consultas DNS armadas a mano (`_paquete_dns`, RFC 1035) el DNS
actual y Cloudflare, Google, Quad9 y OpenDNS; mediana de 8 dominios.
**Solo recomienda cambiar si la mejora se nota** (más de 10 ms y más del
25 %). En la laptop del desarrollador el DNS del proveedor fue el más
rápido (16 ms contra 44-93) y la app lo dice en vez de empujar a cambiar.

- Se ponen las direcciones IPv4 **y** IPv6 del proveedor: con solo IPv4,
  Windows puede seguir usando el DNS IPv6 del router.
- "Éxito" = releer el DNS después y ver el pedido, no que el comando no
  haya dado error.
- **Deshacer** (`tipo "dns"`): se guarda si el DNS era automático o fijo
  (registro `NameServer` de Tcpip y Tcpip6). Automático → `-ResetServerAddresses`;
  fijo → las direcciones que había.
- Las IP pasan por `_ps_lista`, que descarta cualquier cosa que no sea una IP.
- NO se probó aplicar un DNS en el equipo real (cambiaría su red); la
  medición, la lectura y el filtrado sí.

## Errores corregidos en la pasada de la 1.6.0

- **`limpiar_cache_app` mentía**: medía antes de borrar y sumaba ese número
  con `rmtree(ignore_errors=True)`. Mismo fallo que ya se había corregido
  en la caché del navegador. **Tercera vez del mismo patrón**: ahora todo
  borrado pasa por `_vaciar_contenido`, que mide antes y después.
- **Las cachés de Steam y Discord nunca aparecían**: apuntaban a carpetas
  donde esas apps no guardan nada (Steam usa Local, Discord usa Roaming).
  En la laptop del desarrollador eran 761 MB de Steam invisibles.
- **Las reparaciones largas (sfc, DISM) podían colgarse para siempre.** La
  salida iba a un PIPE que no se leía hasta el final; el búfer ronda los
  64 KB y, lleno, el comando espera a que alguien lea mientras la app
  espera a que el comando termine. Ahora va a un archivo temporal. De paso
  se lee bien: sfc escribe en UTF-16 y DISM en la página OEM (cp850).
- **`C:\Windows\Temp` escrito a mano**: con Windows en otra unidad, la
  limpieza de temporales del sistema no hacía nada. Ahora `_carpeta_windows()`
  pregunta `%SystemRoot%`.
- **Textos en español en la build en inglés**: "Temporales de Windows", el
  aviso de reparación cancelada y el título de cuatro ventanas "Confirmar".
- **Dos textos más sin traducir**: el botón "Protegido" de la lista de
  procesos (en el mismo archivo ya existía `opt_protegido`, usado en la
  otra rama del mismo `if`).

## Revisión antes de subir la 1.6.0

- **"Limpiar temporales" borraba a través de uniones (junctions).**
  `os.walk(followlinks=False)` esquiva los enlaces simbólicos, pero en
  Windows SÍ entra en las uniones. Una unión dentro de %TEMP% hacia otra
  carpeta (las dejan algunos instaladores) hacía que se vaciara esa otra
  carpeta. **Comprobado con la versión publicada**: borró un documento de
  fuera de %TEMP%. Ahora todo borrado pasa por `_recorrer` /
  `_vaciar_contenido`, que podan enlaces y uniones, y `prueba_limpieza_fondo`
  lo prueba con una unión de verdad. **Nunca recorrer para borrar con
  os.walk a pelo.**
- **`verificar_idiomas.py` nunca devolvía código de error.** Imprimía las
  claves que faltaban y el banco lo daba por bueno igual — exactamente lo
  que ya le había pasado a `auditoria.py`. Ahora sale con 1, y además
  busca con `ast` textos de interfaz escritos a mano (`text=`, `title=`)
  sin pasar por `t()`. Encontró cinco más: "Cerrar", "Terminar",
  "Desinstalar", "Listo." y "🔓 Panel oculto activo". Se le vio fallar
  metiendo uno a propósito.
- **El aviso de disco lleno se repetía en cada arranque**: "una vez al día"
  vivía en memoria, y la app arranca con Windows. Se guarda en
  `avisos_disco` (preferencias) con hora de reloj, y la primera revisión
  de disco es a los 10 minutos, no al encender.
- **Cambiar el DNS podía fallar entero** en un adaptador con IPv6
  desactivado (Windows rechaza la lista por las direcciones IPv6). Si
  falla, se reintenta solo con IPv4.

## Edición Admin: herramientas nuevas de técnico (para la 1.6.0)

Todo en `tecnico.py` (lógica pura, probada en `prueba_tecnico.py`) y en
pestañas nuevas de Herramientas de técnico. **Ninguna añade dependencias**:
PowerShell, powercfg, pnputil y la librería estándar. El `.exe` no crece.

- **Informe para el cliente** (`generar_informe_html`): antes/después, el
  trabajo hecho (Historial desde la primera foto) y la salud del hardware.
  HTML y no PDF a propósito: un PDF exige otra librería dentro del `.exe`, y
  cualquier navegador imprime a PDF. Se guarda en el Escritorio y se abre.
  Todo pasa por `html.escape`: el nombre del equipo o del cliente no puede
  meter HTML. La foto antes/después ya existía, pero solo se veía en
  pantalla y el "recuperable" salía en bytes crudos ("523452345 B").
- **Salud de discos**: `Get-StorageReliabilityCounter`. Necesita admin, y
  muchos controladores no dan desgaste/temperatura: un `None` se enseña como
  "n/d", **nunca como 0** (sería inventar que está perfecto).
- **Batería**: `powercfg /batteryreport /xml` (el XML no está traducido ni
  cambia de formato; el HTML sí). Ojo: falla si la ruta de salida va con
  barras mezcladas — usar `os.path.join`.
- **Pantallazos**: evento 1001 de WER (el código está en `Properties[0]`) y
  evento 41 de Kernel-Power para apagados inesperados. Los códigos
  `0x1000xxxx` se normalizan al base. La causa es una pista, y se dice.
  En la laptop del desarrollador: 0 pantallazos y **52 apagados inesperados
  en 90 días**.
- **Respaldo de controladores**: `pnputil /export-driver *`. **Probado de
  verdad, y salió mal la primera vez**: con una ruta de destino larga,
  pnputil se cortó en 54 de 91 ("nombre de archivo demasiado largo") y la
  app lo daba por bueno porque solo miraba que hubiera `.inf`. Ahora lee
  los totales del final de la salida (`contar_exportados`) y avisa de un
  respaldo a medias; la carpeta se llama corta (`Drivers_AAAAMMDD`). Con
  ruta corta: 91 de 91, 3.2 GB, 15 s.
- **pnputil escribe en la página ANSI** (cp1252), no en la OEM como DISM:
  `_decodificar_salida_consola` prueba las dos y se queda con la que deja
  texto legible ("exportó" y no "export¾").
- **Mantenimiento completo**: punto de restauración, RAM, temporales,
  limpieza a fondo, DNS, (sfc + DISM opcional), optimizar discos (HDD
  opcional), con foto antes/después y el informe al final. Cancelable
  entre pasos y dentro de los largos.

## Consola: 13 comandos nuevos (38 en total)

`/ramprofunda /autoram /fondo /fugas /procesos /discos /bateria
/pantallazos /unidades /medirdns /plan /red /tecnico`. Los lentos van por
`en_hilo()` dentro de `_ejecutar_comando`. `revisar_comandos.py` los
tiene en `CON_EFECTOS`: lanzan PowerShell o tocan el sistema, y un hilo
vivo al cerrar la app de prueba ensuciaría el banco. Los comandos solo son
de una palabra: el banco los descubre con `comando == "/[a-z]+"`.

## Rendimiento: la app trabajaba en la bandeja

Medido (perfilado con la ventana oculta), y venía de antes de esta sesión:
**Inicio seguía refrescándose con la app en la bandeja** — animando
gráficas que nadie veía unas 15 veces por segundo y lanzando `nvidia-smi`
cada 2 s **desde el hilo de la interfaz** (hasta 5 s de ventana congelada
si tardaba). ~3 % de CPU constante en una app de optimización.

- `_tick_dashboard` no refresca nada si la ventana está oculta o
  minimizada (`prueba_bucles.py` lo vigila).
- La GPU se lee en un hilo (`_leer_gpu_en_fondo`) y se pinta el último
  valor. Sin `nvidia-smi` en el equipo, no se vuelve a intentar.
- Resultado: en la bandeja, **3.1 % → 1.0 %** de un núcleo (y parte de ese
  1 % es el bucle de la propia medición). RAM igual (~69 MB). El `.exe`
  sigue en ~22.7 MB.

## Revisión de idiomas, segunda vuelta

`verificar_idiomas.py` ahora también reconoce `t('clave')` con comillas
simples (dentro de f-strings no se veían), y quedaron otros textos a mano
fuera de `text=`: "Cargando..." de la info del equipo, "GB libres", "GPU
NVIDIA" y "No disponible en vivo" (Inicio). **El ast solo mira `text=`,
`title=` y `message=`**: un texto en un argumento posicional o en un
diccionario se le escapa.

## Los errores que se veían pasar por la pantalla durante el banco

El desarrollador avisó: mientras corría el banco, aparecían ventanas de
error que se cerraban solas. **El banco decía "todo en verde"**: la app
atrapa el error, lo apunta en `ultimo_error.txt` y enseña la ventana, pero
la prueba no se entera. Había 24 registros en las carpetas temporales de
las pruebas:

- **22 eran un error real**: `worker_estado_limpieza` (Segundo plano)
  llamaba a `winfo_exists()` DESDE el hilo — "main thread is not in main
  loop". `revisar_hilos.py` no lo veía porque solo buscaba métodos que
  CAMBIAN algo (`configure`, `pack`...), no consultas. Con la lista
  ampliada (`winfo_*`, `cget`, `update`) aparecieron **10 sitios más** con
  el mismo patrón `if ... winfo_exists(): self.after(0, ...)` en el hilo.
  Todos corregidos: la comprobación va DENTRO de lo que se manda por
  `after(0)`, o se usa `_actualizar_label`, que ya la hace.
- Los otros eran el `1 / 0` provocado a propósito por
  `prueba_hilos_interfaz.py`. Ahora esa prueba sustituye la ventana de
  error por una que solo apunta, y comprueba que se habría mostrado.

**`revisar_errores_banco.py`** cierra el hueco: `Verificar_Todo.bat` apunta
la hora al empezar (`--inicio`) y, al final, busca `ultimo_error.txt` en
todas las carpetas temporales de las pruebas. Si la app registró algo que
no sea provocado (se reconoce por el archivo de la prueba en el traceback,
nunca por el tipo de error), el banco falla y dice la línea de NUESTRO
código. Se le vio fallar con los 24 registros viejos.

> **Corolario:** que una prueba no falle no significa que la app no haya
> fallado durante ella. La app se traga sus errores a propósito, para no
> cerrarse en la cara del usuario; el banco tiene que ir a buscarlos.

Y cinco etiquetas del Historial seguían en español a mano (`_log_dev("...")`
como argumento posicional, que el ast de `verificar_idiomas` no mira).

## Cuatro paquetes más para la 1.6.0

### Gaming
- **Cerrar apps al jugar y reabrirlas al salir** (`Autopilot._cerrar_apps` /
  `_reabrir_apps`). Nunca el juego, ni TechClean, ni lo "bloqueado" por
  `evaluar_riesgo_proceso`, aunque el usuario lo marque. Se reabren con
  `explorer.exe <app>`: TechClean es administrador y lanzar Discord desde
  ella lo abriría elevado. La lista para elegir excluye lanzadores de juegos
  (muchos juegos mueren sin ellos) y todo lo que corre desde %SystemRoot%
  (applicationframehost, textinputhost...: cerrarlos rompe Windows).
- **Ajustes de Windows para juegos** (`AJUSTES_JUEGO`): Modo de juego,
  grabación en segundo plano de Game Bar, HAGS. Cada uno = lista de claves
  de registro con valores on/off; `set_ajuste_juego` devuelve los valores
  CRUDOS anteriores y `restaurar_ajuste_juego` BORRA el valor si antes no
  existía (no lo deja a 0: no es lo mismo para Windows).
- **Cerrar apps al jugar es OPCIONAL**: interruptor general
  `cerrar_apps_al_jugar`, apagado de fábrica. Las apps marcadas se guardan
  aparte (`apps_cerrar_al_jugar`) para que apagar la función no obligue a
  desmarcarlas: hay quien juega con el navegador o Discord abiertos a
  propósito. `_apps_a_cerrar_al_jugar()` es lo único que lee el autopiloto.
- **Juegos de GOG, tres fuentes** (`_juegos_gog`): el registro (instalador
  clásico), la base SQLite de GOG Galaxy 2.0 (`InstalledBaseProducts` +
  `LimitedDetails`, leída sobre una COPIA porque Galaxy la tiene abierta) y
  los `goggame-<id>.info` de cada carpeta de juego (juegos copiados de otro
  disco). Sin repetir por id o carpeta; los DLC (rootGameId distinto) no
  cuentan. Antes solo miraba el registro, y lo instalado con Galaxy no
  salía. Se quitó `detectar_juegos_instalados`: un segundo detector de
  juegos que no usaba nadie (101 líneas).
- **Medidor de lag**: `IcmpSendEcho` (iphlpapi, sin admin y sin depender de
  la salida traducida de ping.exe). Mide el router y 1.1.1.1 por separado
  para decir si el problema es la red local o el proveedor.

### Privacidad y seguridad
- **Privacidad de Windows** (`AJUSTES_PRIVACIDAD`, mismo mecanismo que los
  de juego): ID de publicidad, sugerencias de Inicio y Configuración,
  consejos, experiencias personalizadas y Bing en el buscador de Inicio.
- **`seguridad.py` — auditor que SOLO LEE.** Nació del malware real del
  equipo del desarrollador (ver más abajo). `recolectar()` pregunta al
  sistema; `evaluar()` es pura. La señal más fuerte: **un intérprete firmado
  pero renombrado** (OriginalFilename de la versión ≠ nombre del archivo)
  en una carpeta de usuario. Renombrado + firmado NO basta: Lenovo instala
  un mismo UdcPluginHost.exe con varios nombres y Roblox compila RobloxApp.exe
  como RobloxPlayerBeta.exe; marcarlos era ruido. `prueba_seguridad.py`
  tiene el malware real como primer caso.
- **Programas en la red**: lo que escucha fuera de 127.0.0.1 y las
  conexiones establecidas, por programa.

### Aplicaciones y disco
- **Bloatware** (`BLOATWARE`, prefijos de PackageFamilyName): solo esa
  lista; `quitar_bloatware` rechaza cualquier otro paquete y cualquier
  nombre con caracteres raros ANTES de llamar a PowerShell.
- **Actualizar todas** con `winget upgrade --all`.
- **`listar_actualizaciones_winget` buscaba la cabecera "Name"**: con winget
  en español ("Nombre ... Disponible Origen") la lista salía vacía sin
  aviso. `_filas_tabla_winget` toma como cabecera la línea de encima de los
  guiones y una columna por palabra (entre "Disponible" y "Origen" hay UN
  espacio).
- **Duplicados**: tamaño → primeros 64 KB → contenido completo (BLAKE2), sin
  entrar en uniones. La interfaz deja desmarcada una copia por grupo y, si
  el usuario marca todas, `_accion_enviar_duplicados` salva la primera.

### Sistema
- **Puntos de restauración**: lista, espacio (`Win32_ShadowStorage`), crear
  y borrar todos menos el más reciente (`vssadmin delete shadows /oldest`
  n-1 veces). En la laptop del desarrollador: 2 puntos, 4.25 GB.
- **`crear_punto_restauracion` mentía**: con un punto de las últimas 24 h,
  Windows no crea otro pero `Checkpoint-Computer` sale con código 0. Se
  usaba antes de sfc/DISM y en el mantenimiento. Ahora cuenta los puntos
  antes y después.
- **Informe de energía** (`powercfg /energy`, 60 s). powercfg sale con
  código de error cuando ENCUENTRA problemas: el éxito es que exista el
  informe.

## Versión 1.7.0: rendimiento y la "gran update"

El desarrollador notó la app "un poco lenta" y después pidió una actualización
grande. Todo lo de abajo está medido en su equipo (Lenovo 83K7, NVMe, Wi-Fi
Realtek RTL8852BE, Windows 11).

### Por qué iba lenta (medido, no supuesto)

- **Inicio congelado el 15 % del tiempo.** `sysmon.get_cpu_info()` usaba
  `psutil.cpu_percent(interval=0.3)`, que DUERME 0.3 s, y `_refrescar_gauges`
  la llama en el hilo de Tk cada 2 s. Ahora `interval=None` (se ceba al
  importar el módulo). De 300 ms a 11 ms por refresco. `prueba_rendimiento.py`
  lo vigila.
- **customtkinter 6.0 recalcula la ventana entera en cada barra de
  desplazamiento.** `CTkScrollbar._draw` y `CTkOptionMenu._draw` terminan con
  `self._canvas.update_idletasks()`, que procesa la disposición de TODA la
  ventana, y eso mueve las barras otra vez: una cascada. Era ~30 % de lo que
  tardaba abrir una pantalla. Parche en `main.py` (`_sin_redibujo_forzado`):
  se anula `update_idletasks` SOLO en el canvas de esas dos clases.
- **Drivers: 300 tarjetas.** Un marco + una etiqueta por driver: 3.3 s
  congelada al cargar, y otros 3 s por cada letra del buscador (rehacía todo
  en `<KeyRelease>`). Ahora es un único `CTkTextbox`: 10 ms.
- **Destruir la pantalla vieja** costaba 0.1-0.3 s ANTES de empezar a dibujar
  la nueva. Ahora cada pantalla estrena marco (`_limpiar_contenido`) y el
  viejo se oculta y se destruye después. OJO: con `after_idle` +
  `after(80)`, no con `after(ms)` a secas: un temporizador ya vencido se
  atiende ANTES que el dibujado pendiente.
- **Lo que queda**: abrir una pantalla tarda 0.5-1 s, y es el dibujado de
  customtkinter (100-260 widgets, cada uno con su canvas). Descartado con
  medidas: no es el GIL (`sys.setswitchinterval` no cambia nada) ni crear un
  `CTkFont` por widget (sin diferencia clara). El siguiente paso sería guardar
  las pantallas ya dibujadas, pero eso arrastra datos viejos y los números de
  generación de cada bucle: no se hizo sin preguntar.
- **Consumo con todo lo nuevo encendido** (atajo, aviso de carga): 0.35 % de
  CPU con la ventana a la vista, 0.09 % en la bandeja, 70 MB.

### Funciones nuevas y sus decisiones

- **Buscador Ctrl+K**: `buscar_en_paleta()` es pura (se prueba sin ventana):
  sin tildes ni mayúsculas, sinónimos es/en que no se enseñan (por eso no
  pasan por `t()`), y con faltas vía `difflib`. Solo acciones que no borran
  nada sin preguntar; las que borran (papelera) llevan a su pantalla. Ocho
  botones fijos que se reescriben, no se crean por tecla.
- **Bandeja**: "Liberar RAM" y "Limpieza rápida". La notificación va por
  `tray.notificar()` (`pystray.Icon.notify`), instantánea, y no por
  `opt.notificar_windows`, que lanza un PowerShell (~1 s y ~60 MB justo
  después de liberar RAM). Si el Modo Juego está activo, se excluye el PID
  del juego, igual que el autopiloto.
- **Atajo global** (`atajos.py`): `RegisterHotKey` en un hilo propio con
  `GetMessageW`; para soltarlo, `PostThreadMessageW(WM_QUIT)` y el propio
  hilo hace `UnregisterHotKey`. NADA de ganchos de teclado (`keyboard`,
  `SetWindowsHookEx`): ven cada tecla, que es lo que hace un keylogger. Si
  otro programa ya tiene la combinación, Windows lo rechaza y la app lo dice
  ("ocupado"). Apagado de fábrica.
- **Wi-Fi** (`sysmon.leer_wifi`): `wlanapi.dll` por ctypes, no `netsh` (sale
  traducido). Tamaños verificados en la prueba: `WLAN_BSS_ENTRY` 360,
  `WLAN_INTERFACE_INFO` 532, `WLAN_CONNECTION_ATTRIBUTES` 604. **Sin
  `WlanScan`, Windows 11 solo devuelve la red propia** en
  `WlanGetNetworkBssList` (comprobado: 1 red sin escaneo, 24 con él), así
  que `escanear=True` espera 4 s. La banda sale de la frecuencia del BSS
  propio: los canales de 6 GHz repiten los números de 2.4 y 5. Solo cuentan
  como vecinas las redes con RSSI ≥ -82 dBm. El SSID no va al Historial.
- **Prueba de disco**: ver "errores corregidos". En este equipo: 720 MB/s
  escritura, 1284 lectura, 13 MB/s en bloques de 4 KB.
- **Extensiones** (`seg.auditar_extensiones`): `Secure Preferences` +
  `Preferences` de cada perfil, `location` de Chromium (1 tienda; 2/3/6
  otro programa; 4/8 desde carpeta; 7/9 directiva; 5/10 del navegador, no se
  listan). **Caso real**: el desarrollador tiene perfiles de su escuela
  (`clases.edu.sv`) con 10 extensiones forzadas por la organización; el
  primer borrador las marcó TODAS como riesgo alto. Ahora los perfiles con
  `is_managed` + `hosted_domain` en `Local State` dan origen "organizacion"
  (informativo). Lo forzado desde el REGISTRO (`ExtensionInstallForcelist`)
  sí es alto. En este equipo: 17 extensiones, 3 para revisar (McAfee
  WebAdvisor, Adobe Acrobat, una VPN gratis en Edge).
- **Accesos rotos** (`opt.buscar_accesos_rotos`): parser propio de .lnk
  (MS-SHLLINK). Solo se marca un destino "local" en una unidad FIJA que esté
  conectada; los programas "anunciados" de MSI (Office), las apps de la
  Tienda y los de red o USB dan "otro" y no se tocan. Comparado contra
  `WScript.Shell` en los 147 accesos de este equipo: coinciden. Encontró dos
  rotos: uno de Roblox y **`server.lnk` del malware** (en la carpeta de
  Inicio): los de esa carpeta salen SIN marcar y con aviso. No se borró.
- **Vigilante**: `revisar_reinicio` (una vez por hora; reavisa cada 3 días
  en el mismo arranque; se guarda en `aviso_reinicio` para no repetir al
  reabrir) y `revisar_carga` (cada minuto; se rearma al desenchufar o al bajar
  5 puntos; apagado de fábrica, porque muchas marcas ya cortan la carga solas).
  Cada revisión del bucle va en su propio try: antes, si fallaba la de fugas,
  no se miraba el disco.
- **Salud de Inicio**: -5 con 7 días sin reiniciar, -10 con 14. "Arreglar
  todo" no lo puede arreglar: hay que decírselo a la persona.
- **Novedades**: solo si `preferencias.json` existía ANTES de arrancar
  (`_habia_preferencias`) y `ultima_version_vista` no es esta versión. Si la
  app arrancó en la bandeja, espera a que se abra la ventana.

### Errores corregidos

- **La prueba de disco medía la RAM.** Leía con `open()` el archivo que
  acababa de escribir y Windows lo servía desde la caché. El comentario decía
  que evitarlo "requería privilegios": falso. `FILE_FLAG_NO_BUFFERING` lo
  puede usar cualquiera (búfer alineado con `VirtualAlloc`, bloques múltiplos
  de 4096). Con `FILE_FLAG_DELETE_ON_CLOSE` el archivo desaparece aunque la
  app muera a mitad.
- **El Historial sumaba la RAM como espacio de disco.** Campo nuevo
  `bytes_ram` en `report.add` y `_log_dev`; lo guardado antes se clasifica
  por el comando (`_RASTROS_RAM`). La "Limpieza rápida" y "Arreglar todo"
  guardan las dos cifras por separado.
- **Importar ajustes** guardaba el JSON tal cual: `prefs.filtrar_importables`
  deja solo claves conocidas, del tipo correcto, y nunca los registros de
  otro equipo (`avisos_disco`, `aviso_reinicio`...).
- **Fechas de drivers** como `/Date(1150848000000)/` (ConvertTo-Json de
  PowerShell 5.1): `sysmon._fecha_cim`.
- **`prueba_bucles.py` daba un falso fallo** al volverse más rápida la
  pantalla: contaba un tic que luego se apagaba sin consultar nada. Ahora
  cuenta las consultas de verdad (`get_cpu_details`).

### Lección del entorno: las barras invertidas en Bash

En la herramienta Bash, un heredoc con un script de Python colapsa `\\` en
`\`: un `"\n"` acaba como un salto de línea real dentro de la cadena y rompe
el archivo (pasó tres veces en esta sesión: `idiomas.py`, `report.py`,
`main.py`). Para cualquier cambio que lleve barras invertidas: Edit/Write, o
un `.py` escrito con Write en el scratchpad.

## Temas y rediseño de la interfaz (para la 1.8.0)

El desarrollador dijo que la interfaz se veía "seca". Se dibujaron tres
direcciones (lienzo de diseños en claude.ai: Pulido, Telemetría, Claro) y
seis temas más; aprobó todos menos uno (Synthwave). Quedaron 9:
Original, Pulido (de fábrica), Telemetría, Claro, Negro puro (OLED),
Bosque, Terminal retro, Sakura y Alto contraste.

### Cómo funciona (`temas.py`, `iconos.py`)

- **Cerrado a propósito** (lo pidió el desarrollador): los temas van
  compilados dentro de la app. Nada se descarga ni se lee de archivos;
  en preferencias solo se guarda el NOMBRE (`"tema"`), y cualquier valor
  que no esté en `temas.TEMAS` cae en el de fábrica (`nombre_valido`). Se
  descartó la idea de temas descargables: un tema son colores (pocos KB),
  las letras son de Windows, y descargar algo para ejecutarlo en una app que
  corre como administrador es una puerta para malware.
- Cada tema es un diccionario de **fichas** (`temas.FICHAS`): fondo,
  lateral, panel, fila, borde, texto/texto2/texto3, acento, sobre_acento,
  peligro, radios de las esquinas, letra, modo claro/oscuro, estilo de la
  barra ("lista" o "rail") y escala (Alto contraste: 1.12).
- `temas.aplicar(nombre)` construye el diccionario de colores por defecto
  de customtkinter (`ThemeManager.theme`, a partir del "blue" de la
  librería) y pone el modo. **Va ANTES de crear la ventana** (la ventana es
  el primer widget que lee el tema): `TechCleanApp.__init__` lee
  preferencias, aplica, y luego `super().__init__()`.
  `temas.resolver_fuentes(raiz)` elige la primera letra instalada de cada
  lista (Segoe UI Variable no existe en Windows 10).
- En la interfaz, **`T.<ficha>`** (`from temas import T`) en vez de colores
  escritos a mano. Se lee al crear cada widget; cambiar de tema
  (`_aplicar_tema`) vuelve a construir la barra y la pantalla abierta. Las
  `COLOR_*` de main.py siguen existiendo: `_sincronizar_colores()` las
  reasigna (las funciones leen las globales al ejecutarse).
- Los colores escritos a mano (446 en main.py; quedan 26, los de la consola
  y la tarjeta de donar) se cambiaron por fichas SEGÚN SU PAPEL,
  con un script sobre el árbol de sintaxis (no por valor: el mismo
  "#2a2d36" era fondo de botón, separador u hover). Los botones
  secundarios ganaron `text_color=T.texto` (el de por defecto es el de
  "sobre el acento", casi negro en Telemetría) y los de peligro pasaron a
  `T.peligro` (rojo oscuro) con texto blanco en todos los temas.
- **La consola se queda oscura** en todos los temas (es una terminal), y su
  globito de ayuda también. `prueba_temas.py` permite colores sueltos solo
  ahí y en la tarjeta de donar.
- Iconos de línea dibujados con Pillow (`iconos.TRAZOS`, cuadrícula 24x24,
  a 3x para que se vean nítidos con el zoom de Windows). Sin archivos de
  imagen. Las miniaturas de los temas en Ajustes también son imágenes de
  Pillow: una imagen pesa mucho menos que una docena de widgets por tarjeta.

### Barra lateral nueva

- Grupos (Sistema, Protección, Herramientas), iconos en vez de emojis y la
  sección abierta marcada (antes no había forma de saber dónde estabas).
  Ajustes y "minimizar a la bandeja" quedan fijos abajo.
- La pantalla abierta se sabe SIN tocar cada `mostrar_*`:
  `_limpiar_contenido` mira quién la llamó (`sys._getframe(1)`), lo guarda
  en `_pantalla_actual` y lo marca. Las que cuelgan de otra (Drivers,
  Espacio en disco) marcan a su madre (`NAV_DE_PANTALLA`).
- Telemetría usa una columna estrecha (`_sidebar_rail`) con nombres cortos
  (`nav_corto_*`) y la explicación en un globito.

### Inicio y Optimizar rediseñados

- Inicio: cabecera con las dos acciones a la derecha, tarjeta de salud con
  anillo (tk.Canvas escalado a mano: no sigue el zoom de Windows como los
  widgets de customtkinter), cuatro `TarjetaMetrica` (misma interfaz
  `set_value` que `Gauge`: `_refrescar_gauges` no cambió; la animación se
  sacó a `_ValorAnimado`, que comparten), gráficas e información.
- Optimizar: la RAM en dos tarjetas, el disco en filas (icono, qué hace,
  botón), el perfil de energía en un selector que vuelve atrás si el
  cambio falla.
- El resto de pantallas toma colores, letra y bordes del tema; su
  rediseño a fondo queda para después, una por una.

### Errores encontrados por el camino

- **Textos cortados por los dos lados** (venía de antes): muchos textos se
  partían a un ancho fijo (wraplength=850/900). Con la ventana a su tamaño
  de fábrica o el zoom al 125 %, la caja era más estrecha y la etiqueta,
  centrada, se cortaba: en Gaming se leía "ambia el plan..." en vez de
  "Cambia". `_textos_al_ancho` ajusta cada texto largo al ancho real de su
  caja cuando la pantalla termina de dibujarse.
- En Alto contraste el tema pone borde de 2 px a TODOS los botones; los de
  la barra y los enlaces llevan `border_width=0` explícito.
- El azul del tema Original (#1f6aa5) no llegaba al contraste mínimo como
  color de línea sobre los paneles (2.9:1): se aclaró a #2070ab.
- En Alto contraste el aviso de "Limpieza automática programada" de Inicio
  no tenía wraplength y se cortaba por los dos lados (llega desde un hilo,
  después del ajuste de textos): ahora se parte al ancho de su columna.

### El rediseño hizo la app el DOBLE de lenta (y cómo se arregló)

Medido con la ventana de fábrica, cambiando de pantalla (construir y
dibujar), contra la 1.7.0 en el mismo equipo y el mismo rato:

| Pantalla  | 1.7.0        | rediseño recién hecho | arreglado    |
|-----------|--------------|-----------------------|--------------|
| Inicio    | 0.50-0.67 s  | 1.4 s                 | 0.63-0.76 s  |
| Optimizar | 0.65-1.0 s   | 2.1 s                 | 1.0-1.17 s   |
| Ajustes   | 1.07-1.6 s   | 2.5 s                 | 1.25-1.6 s   |
| Gaming    | 1.12-1.4 s   | 1.6 s                 | 1.0-1.3 s    |
| Reparar   | 0.81-1.0 s   | 1.2 s                 | 0.74-0.9 s   |

(Rangos de varias tandas alternando versiones, con el equipo más o menos
ocupado.) Gaming y Reparar quedan igual que en la 1.7.0; Inicio, Optimizar
y Ajustes, un 15-25 % por encima: enseñan más (las explicaciones de cada
acción a la vista, la galería de temas). CPU con Inicio abierto y quieto:
0.80 % con el rediseño recién hecho, 0.41 % arreglado (0.42 % la 1.7.0);
RAM 84 MB (80 la 1.7.0). Lo que costaba, de más a menos:

- **Una CTkProgressBar cuesta ~10 ms** (crearla y dibujarla) y se
  redibujaba ENTERA en cada paso de la animación de las tarjetas de Inicio:
  16 pasos por refresco y por tarjeta, también con la app quieta (de ahí la
  CPU en reposo). `TarjetaMetrica` dibuja ahora número y barra en un
  tk.Canvas: un texto y dos líneas de punta redonda; cada paso, dos llamadas.
- **Los textos largos se reajustaban 3 o 4 veces al abrir una pantalla.**
  `_textos_al_ancho` (el arreglo de los textos cortados) cambiaba el
  wraplength en CADA `<Configure>`, y mientras la pantalla se coloca su
  caja pasa por anchos intermedios: en Ajustes 800 → 234 → 729 → 800 px.
  Cada cambio volvía a colocar y dibujar el panel entero. En Optimizar,
  además, `texto_fluido` y `_textos_al_ancho` ajustaban la misma etiqueta
  con márgenes distintos y se pisaban (620 ↔ 683). Ahora hay un solo
  mecanismo (`texto_fluido`): cada `<Configure>` solo apunta la caja, y el
  ajuste se hace UNA vez, cuando nada se mueve desde hace
  `ESPERA_TEXTOS_MS` y han pasado tres ratos libres seguidos de Tk, y solo
  en cajas ya asentadas (`_caja_asentada`: visibles, y sin un
  CTkScrollableFrame que aún no ha fijado el ancho de su interior). Tk
  atiende los temporizadores ANTES que su propio trabajo de colocar
  ventanas: sin esas esperas el ajuste llegaba a media colocación.
- **La galería de temas: ~0.8 s** (9 tarjetas × 4 widgets). `GaleriaTemas`
  la dibuja en un solo tk.Canvas: cada tarjeta es una imagen de fondo con
  la miniatura dentro (`iconos.tarjeta_tema`) y dos textos del lienzo.
- **Una CTkFont por etiqueta.** `ctk.CTkFont(...)` crea una fuente nueva de
  Tk cada vez, y había 390. Con la fuente compartida, crear y dibujar una
  etiqueta cuesta ~1.3 ms menos: `fuente(size, weight, family)` las guarda
  por ventana (en la ventana principal: las fuentes son de su intérprete de
  Tcl, y las pruebas abren y cierran varias).
- **Marcos invisibles.** Un `CTkFrame(fg_color="transparent")` es un lienzo
  que dibuja un rectángulo redondeado aunque no se vea, y lo redibuja en
  cada cambio de tamaño (~6 ms frente a ~1.5 de un tk.Frame). El rediseño
  llenó Inicio y Optimizar de filas y cabeceras así. `Caja` es un tk.Frame
  del color de su padre que escala sus márgenes con el zoom de Windows
  (como hace customtkinter); `linea()` es el separador de 1 px. El marco
  de cada pantalla (`_limpiar_contenido`) también es una `Caja`.
- **La barra lateral repintaba sus 15 botones** en cada cambio de pantalla
  para marcar uno: ahora solo el que se desmarca y el que se marca
  (`_nav_marcado`).

Lo que NO era: el tema en sí (con el "blue" de customtkinter tardaba lo
mismo), el radio de las esquinas, ni la letra Segoe UI Variable (~10 %).

Medidas sueltas por widget (crear + dibujar, este equipo): CTkLabel 1.3 +
2.0 ms (3 ms con una CTkFont nueva; 7 con fondo y esquinas), tk.Label
0.5 + 0.85, CTkButton 5.3 + 3.1, CTkFrame 2.5 + 3.8, tk.Frame 0.02 + 1.5,
CTkProgressBar 4.2 + 6.2. Para lo que se dibuja muchas veces o en
cantidad: tk.Canvas o widgets de Tk; customtkinter para lo que se toca.

Dos errores que salieron al pasar el banco después del arreglo:

- **El buscador Ctrl+K no abría** (UnboundLocalError). Al cambiar los 390
  `ctk.CTkFont(` por `fuente(` de golpe, en `_abrir_paleta` quedó
  `fuente = fuente(size=13)`: asignar el nombre lo hace local en TODA la
  función, y la llamada a `fuente()` de unas líneas antes reventaba.
  Python no lo avisa hasta ejecutar esa línea. `auditoria.py` (paso 6)
  busca ahora variables locales que tapan una función del módulo.
- **Componentes seguía consultando WMI con la pantalla cerrada** (venía de
  antes; lo destapó `prueba_bucles.py` con el equipo cargado). Cada visita
  lanza un hilo que primero hace las consultas lentas (módulos de RAM,
  GPU: con WMI degradado, 8-9 s). Si entretanto el usuario salía, o salía
  y volvía, el hilo viejo seguía con las otras ocho consultas sin tener
  dónde pintar. Ahora, tras la parte lenta, mira si su visita sigue
  abierta (`sigue_abierta`: número de visita y `_pantalla_actual`, dos
  atributos de Python, sin tocar Tk desde el hilo).

`prueba_temas.py` vigila que ningún texto se ajuste más de una vez al
abrir Optimizar, Ajustes y Gaming, que las fuentes se compartan, que Inicio
no lleve CTkProgressBar y que la galería quepa en Alto contraste.

Cómo medirlo (sin compilar): un script que crea `TechCleanApp` con un
APPDATA temporal, la pone fuera de la pantalla, y cronometra
`getattr(app, pantalla)(); app.update()`. Los tiempos varían ±20 % de una
vez a otra: comparar siempre contra la versión anterior en la MISMA
tanda (un `git worktree` con la etiqueta anterior), alternando. Para
saber QUÉ cuesta, contar llamadas (cProfile, cuántas veces se dibuja cada
clase o cambia cada wraplength): eso no varía.

### Cómo mirar la app sin molestar al usuario

`PrintWindow` sobre una ventana FUERA de la pantalla no sirve (customtkinter
no pinta sus lienzos ahí: salen restos). Lo que funciona: la ventana EN la
pantalla pero con `attributes("-alpha", 0.0)`: no se ve, los clics la
atraviesan, y `PrintWindow(hwnd, dc, 2)` la captura entera.

## La 1.8.0 a fondo: funciones nuevas, Admin al cliente y el resto del rediseño

Pedido del desarrollador el 2026-10-07, con los temas ya hechos: "la de
Admin es de Admin por algo", pero lo que ya funcionaba allí (salud de
discos y batería, historial de fallos, arranque completo, copia de
drivers) pasa también al cliente en lenguaje sencillo; añadir los grupos
A, B y C de la propuesta de "qué tan profundo se puede llegar" **menos los
FPS reales en juegos** (lo descartó él); rediseñar las pantallas que solo
habían tomado los colores del tema ("según mis amigos ya va quedando algo
feita"); y revisar bugs. Después: "déjalo como 1.8.0, la 1.9.0 ya veremos".
Todo esto va, por tanto, en la 1.8.0 (los comentarios que decían "1.9.0"
se cambiaron).

### Funciones nuevas y sus decisiones

- **Salud de los discos, sin administrador (Componentes).** Los NVMe se
  leen directo: `\\.\PhysicalDriveN` abierto con acceso 0 (no pide
  administrador) e `IOCTL_STORAGE_QUERY_PROPERTY` con la página de
  registro 0x02 del protocolo NVMe: temperatura, repuesto, desgaste, datos
  escritos, horas, apagados inseguros. 18 ms. Los SATA siguen por
  `Get-StorageReliabilityCounter` (PowerShell, necesita administrador).
  `tecnico.leer_registro_nvme` y `veredicto_disco` son puras (las prueba
  `prueba_diagnostico.py`). En el equipo de desarrollo: SSD al 98 % de vida
  y 107 apagados inseguros.
- **GPU de cualquier marca (`gpu.py`).** Lo mismo que el Administrador de
  tareas: `D3DKMTEnumAdapters2` / `D3DKMTQueryAdapterInfo` (tipos 3, 8 y 62:
  nombre, memoria, temperatura y ventilador) y los contadores PDH
  `\GPU Engine(*)\Utilization Percentage` y `\GPU Adapter Memory(*)\Dedicated
  Usage`. Antes, uso y temperatura solo salían con NVIDIA (`nvidia-smi`).
- **Reparar → Diagnóstico de fallos (`tecnico.diagnostico_fallos`).** Los
  últimos 30 días del registro de eventos: evento 41 de Kernel-Power con su
  `BugcheckCode` y `SleepInProgress` (un 0x9F del 28/09 solo constaba ahí:
  Windows no llegó a guardar el informe 1001), 1001 de WER, 1000 de
  Application Error, WHEA y los avisos de disco **filtrados por
  proveedor**. Lección: los IDs se repiten entre proveedores (el 153 de
  Kernel-Boot es de arranque, el 7 de BTHUSB es Bluetooth): contando por
  número salían 39 "errores de disco" que no lo eran. Y aun por proveedor
  hay que leerlos: volmgr 161 = no se pudo guardar el volcado; Ntfs 55 =
  daño en el sistema de archivos de una unidad.
- **Aplicaciones → Inicio de Windows completo.** Las claves Run de tu usuario
  y de todos (también las de 32 bits), las carpetas de Inicio y las tareas
  programadas al iniciar sesión. Se activa y desactiva **como el
  Administrador de tareas**: `...\Explorer\StartupApproved\<Run|Run32|
  StartupFolder>`, 12 bytes: `02` + ceros = activo; `03` + tres ceros +
  FILETIME = desactivado (sin valor = activo). Las tareas, con
  `Enable/Disable-ScheduledTask`. Todo con deshacer (`inicio_aprobado`,
  `tarea_inicio`): deshacer deja el valor EXACTAMENTE como estaba, también
  "sin valor" (no un 02). Cada entrada pasa por las reglas de la auditoría
  (`seg.evaluar_inicio`): con la versión anterior, la tarea del malware del
  equipo ni salía aquí.
- **Privacidad: quién usó la cámara, el micrófono y la ubicación.**
  `HKCU\...\CapabilityAccessManager\ConsentStore\<permiso>`, valores
  `LastUsedTimeStart/Stop` (FILETIME; Stop = 0 es que lo está usando). Las
  apps de escritorio van en `NonPackaged` con las barras cambiadas por `#`.
- **Seguridad → Protección y secuestros.** El Centro de seguridad
  (`root/SecurityCenter2`: `productState`, segundo byte 0x10/0x11 = activo,
  tercero 0x00 = al día; no es API documentada pero es lo que lee todo el
  mundo), cortafuegos, arranque seguro, control de cuentas y aislamiento del
  núcleo, del registro. Defender sale "pasivo" con McAfee al mando: se
  explica (antes decía "Protección activa: No" a secas). Secuestros: hosts,
  proxy (también PAC), DNS, certificados raíz raros y directivas del
  navegador. **El hosts**: la primera regla ("todo lo que no va a
  127.0.0.1 es una redirección") marcaba en rojo un bloqueo de McAfee
  (0.0.0.1) y los nombres de Tailscale (100.92.x.x). Ahora hay tres
  grupos: bloqueos (0.x, 127.x), tu red o VPN (privadas, 100.64.0.0/10) y
  redirecciones a una IP PÚBLICA, lo único grave.
- **Energía: consumo por app.** `powercfg /srumutil` (SRUM) a CSV. Necesita
  administrador. Microsoft no documenta las columnas: se buscan por nombre
  (`AppId`, `TotalEnergyConsumption` o la suma de las que acaban en
  `EnergyConsumption`, SIN las `WorkOnBehalf`, que repiten lo que un
  proceso hizo por otro; `OnBattery`). Sin comprobar todavía como
  administrador en el equipo de desarrollo.
- **Gaming.** Qué cuenta como juego (`Autopilot._buscar_juego`): a pantalla
  completa salvo navegadores y reproductores (`NO_JUEGOS`), o cualquier
  programa que viva en la carpeta de un juego de la biblioteca (Steam, Epic,
  GOG) aunque vaya en ventana. **Modo Juego automático por juego**
  (`VigiaJuegos`): solo corre si hay algún juego marcado, cada 10 s mira qué
  hay delante; no apaga un Modo Juego encendido a mano. **Frenar lo que
  acapara la CPU** (como el ProBalance de Process Lasso): más del 25 % de un
  núcleo dos vueltas seguidas → prioridad "por debajo de lo normal"; nunca
  el juego, lo del sistema, el chat de voz ni la grabación (`NO_FRENAR`), y
  se devuelve al acabar. **Bufferbloat**: el ping en reposo y con la línea
  llena (dos descargas, tope ~60 MB), con la escala de Waveform.
- **Limpieza a fondo: cachés de sombreadores.** Se mantuvo la decisión de
  NO borrar las de juegos instalados (darían tirones, en contra del Modo
  Juego); solo `steamapps\shadercache\<id>` sin `appmanifest_<id>.acf` (juego
  desinstalado). En el equipo de desarrollo no había ninguna.
- **Espacio en disco: análisis completo (`disco.py`).** Ver abajo.
- **Drivers: copia de seguridad** (exportar con `pnputil /export-driver` y
  reinstalar) en el cliente. **Segundo plano** enseña de un vistazo todo lo
  que la app hace sola, con un salto a donde se cambia.

### El analizador de disco, y por qué no lee la MFT

Antes: dos niveles de carpetas, casi todo sin contar. Ahora `disco.py`
recorre la unidad entera con `os.scandir` en **8 hilos** (en Windows
scandir trae el tamaño en el propio listado, y suelta el GIL mientras
espera al disco). Medido en C: (300 GB, 713.000 archivos): 1 hilo, 50 s en
caliente y hasta 400 s en frío; 8 hilos, **14-26 s**; 16 hilos, igual que
8. La ventana sigue respondiendo (peor atasco ~0,15-0,2 s, media 7 ms).

- Solo carpetas en memoria (cada una con lo que suman sus archivos):
  ~50 MB para C:, que se sueltan a los 10 minutos sin mirar la pantalla.
  Una subcarpeta siempre tiene un índice mayor que su madre, así que los
  totales salen de una sola pasada del final al principio.
- **Uniones y la nube**: OneDrive y Dropbox son puntos de análisis igual
  que una unión (atributo 0x400), pero con etiqueta `0x9000?01A`; en esas sí
  se entra. En una primera medida se saltaron y faltaba OneDrive. Lo que
  está solo en la nube (RECALL_ON_DATA_ACCESS / RECALL_ON_OPEN / OFFLINE) no
  se cuenta ni se lista: listarlo lo bajaría de internet. Nunca se abre un
  archivo.
- Los enlaces duros (WinSxS) se cuentan como en el Explorador: dos veces.
- **La MFT no se lee** (lo de WizTree, grupo C): necesita administrador y
  un lector a mano de las estructuras de NTFS (registros con fixups,
  atributos residentes y no residentes, listas de atributos), y aquí no se
  podía comprobar contra un disco real. Con 14-26 s no compensaba el riesgo
  de enseñar tamaños mal leídos. Si se retoma: validar contra `scandir`
  en carpetas sin enlaces duros antes de enseñar nada.
- Lo que encontró en el equipo de desarrollo: **14,6 GB de `.etl`** en
  `C:\ProgramData\McAfee\wps\log` (registros de McAfee; no se tocaron: es
  del antivirus). De ahí el tipo "Registros y volcados".
- La papelera desde aquí solo se ofrece para lo del usuario
  (`puede_ir_a_papelera`): nada de Windows, programas, juegos (un .pak
  borrado rompe el juego), AppData ni otras cuentas.

### Rendimiento: cada widget de Tk es una ventana de Windows

Entrar en una carpeta del analizador (40 filas) tardaba **0,9-1 s** con
un widget por pieza (unas 450 ventanas del sistema: Windows mueve cada una
al recolocar). Construirlas fuera de la vista no ayudaba: lo caro era
colocarlas y destruirlas. **`ListaLienzo`**: todas las filas dibujadas en
UN `tk.Canvas` (icono, título, barra, detalle, valor, acciones de texto),
con zonas pulsables y resalte al pasar el ratón: **~50 ms**. Además:

- `font measure` cuesta ~0,2 ms y recortar un texto pide varias: las
  medidas se guardan; el lienzo se dibuja UNA vez con `after_idle` aunque
  su ancho cambie tres veces al colocarse; columnas del mismo ancho para
  que barras y valores queden alineados.
- La pestaña vieja se oculta al momento y se destruye después
  (`_vaciar_pestana`), como las pantallas: destruir los 300 servicios
  costaba 1,5 s ANTES de dibujar la pestaña nueva.
- Ojo: un lienzo de Windows no pasa de 32.767 px de alto. El Historial se
  ve de 200 en 200 acciones.

Con eso: Archivos grandes 2 s → 0,4 s; Desinstalar programas 1,8 s →
0,5 s; Servicios (al venir de otra pestaña) 1,8 s → 0,2 s.

### Errores corregidos (y por qué no se veían)

- **Servicios: todos "Detenido".** `ConvertTo-Json` de Windows PowerShell
  5.1 escribe los enumerados como NÚMEROS (`Status: 4`), y la pantalla
  comparaba con `"Running"`. Se traducen en `opt.ESTADOS_SERVICIO`.
- **Tildes rotas en todo lo que venía de PowerShell** ("Optimizaci¢n"):
  por una tubería, PowerShell escribe en la página OEM (cp850) y Python
  leía con la ANSI (cp1252). Las 30 llamadas que leen texto llevan
  `PS_UTF8` delante del script y `encoding="utf-8"`. Las que leen bytes
  siguen con `_decodificar_salida_consola`.
- **La papelera daba por enviados todos** en cuanto SHFileOperation volvía
  con 0: ahora cuenta lo que de verdad ya no está.
- **Copia de drivers con una carpeta que no vale**: devolvía 4 valores y
  la interfaz leía 6; el hilo moría y se quedaba en "Trabajando...".
- **Un método definido dos veces**: `_accion_informe_bateria` de Energía
  (nuevo) pisó al de la pestaña Técnico, que dejó de guardar en el
  Escritorio. Y `_raiz_registro` dos veces en optimizer. `auditoria.py` ya
  los imprimía en el paso 2… pero no los contaba como fallo. Ahora sí.
- **Textos de los dos idiomas mezclados**: un script añadió textos detrás
  de una línea que era IGUAL en español y en inglés, y metió los de los dos
  en cada bloque (en un diccionario, el segundo pisa al primero sin avisar).
  `verificar_idiomas.py` busca ahora claves repetidas.
- En el hilo de la ventana: borrar caché/historial del navegador (recorre
  miles de archivos) y lanzar un desinstalador.
- Segundo plano: el interruptor del widget no reflejaba si estaba
  visible; cambiar la hora de la limpieza programada no la reprogramaba;
  la frecuencia no se guardaba; un "quitar" fallido dejaba el interruptor
  apagado. Drivers: si no se podía cambiar el Inicio rápido, el
  interruptor se quedaba en la posición falsa.
- Actualizar una app con winget: se lanzaba y se daba por hecho. Ahora
  espera y comprueba que ya no sale en la lista de pendientes.
- **El aviso "Limpieza automática programada activa" salía DOS veces en
  Inicio** (visto en las capturas, después de publicar la 1.8.0). El hilo
  que mira schtasks ponía el aviso en `self._col_salud_actual` al
  contestar; si Inicio se rehacía antes (cambiar de tema, volver a Inicio),
  los dos hilos lo ponían en la columna nueva. Ahora cada hilo escribe solo
  en la columna de su pantalla. `prueba_acciones_rapidas.py` lo reproduce
  con schtasks lento: con 0,4 s el primer hilo ya había contestado y no se
  veía; con 1,5 s sí.
- "Windows solo da este dato a una app abierta como administrador (el .exe
  de TechClean lo es)": solo sale cuando la app NO es administrador, así
  que lo útil es decir qué hacer: pulsar «Desbloquear funciones».

### El informe en PDF (`informe.py`) y la privacidad

Lo pidió el desarrollador (2026-10-13): que el informe "tenga nuestra propia
forma, bien organizadito, y los errores que presente el equipo". Hasta
entonces, el cliente solo exportaba el Historial a `.txt`, y la edición
Admin hacía un HTML sin marca para el cliente.

- **PDF sin librerías nuevas**: el informe se arma en HTML
  (`informe.generar_html`, pura) y lo imprime **Microsoft Edge en modo
  headless** (`--headless=new --print-to-pdf`, `informe.a_pdf`), que viene
  con Windows 10 y 11. Texto seleccionable, tildes bien, colores. Probado:
  2-3 s. Con su propio perfil temporal (`--user-data-dir`): con el normal,
  si Edge ya estaba abierto, la orden se la queda esa ventana y no imprime.
  "Éxito" es que el PDF exista y no esté vacío. Sin Edge, se guarda el HTML.
  Word o Excel habrían pedido librerías nuevas (python-docx, openpyxl).
- El pie de página con el número de página va en `@page { @bottom-right }`
  (Chromium lo admite desde 2024). La franja de color: un elemento
  `position: fixed` se coloca DENTRO del área de la página; con
  desplazamientos negativos hacia el margen, Edge lo recortaba y no salía.
- `_datos_informe` (main) junta lo que la app ya sabe leer: la salud de
  Inicio (`_medir_salud`, sacada de `_calcular_salud_sistema` para usarla en
  los dos sitios), el diagnóstico de fallos, salud de discos y batería,
  protección y secuestros, la auditoría de malware (se ejecuta si no estaba
  hecha), dispositivos sin driver y el Historial. ~20 s en el equipo de
  desarrollo. Solo lee. El estado del resumen es el PEOR entre el
  rendimiento y los problemas: con el malware a la vista, la primera versión
  decía "Tu equipo está bien" (95 de 100).
- Los colores del papel van escritos a mano en `informe.py` a propósito: un
  PDF tiene que verse igual con cualquier tema (con Negro puro sería tinta
  tirada).
- `tecnico.generar_informe_html` (el informe de la edición Admin para el
  cliente) usa ahora la misma plantilla.
- **Privacidad**: `PRIVACIDAD.md` (en la raíz y en el instalador) y Ajustes →
  Privacidad. Comprobado en el código: la app solo se conecta a
  `api.github.com` (actualizaciones, como mucho una vez al día) y a lo que el
  usuario pulsa (Cloudflare y gstatic para velocidad y bufferbloat, pings a
  1.1.1.1, DNS públicos al compararlos, winget). Sin telemetría. El
  instalador de Inno Setup ya pedía aceptar `LICENSE.md`.

### Más listas en lienzo, y dos errores al medir

- `ListaLienzo` aprendió a dibujar un **interruptor** (cambia al momento,
  queda en espera hasta que quien lo gestiona llama a `listo(exito)`, y
  vuelve atrás si falló) y filas que se pulsan sin flecha (`pulsar`, para ver
  el detalle). Con eso pasaron a lienzo Inicio de Windows (16 interruptores:
  de 0,9-1 s a 0,2-0,3 s), el resumen de Segundo plano, los navegadores de
  Privacidad y las filas de Protección.
- `_mostrar_popup_info` era una ventana fija de 420×150: los textos largos
  (el detalle de una acción del Historial, de una entrada del inicio) se
  cortaban. Ahora se ajusta al texto, y con scroll si es muy largo.
- Al medir salían avisos "main thread is not in main loop" de
  `Variable.__del__`: las `BooleanVar` de las casillas las liberaba el
  recolector de Python desde un hilo de fondo. `casilla()` crea la
  CTkCheckBox sin variable (ella guarda su estado; `.get()` da 1 o 0).
- **"bad window path name" al cambiar de tema** (lo vio el desarrollador
  con la app compilada, 2026-10-13): al pasar entre un tema claro y uno
  oscuro, customtkinter oculta y vuelve a enseñar la ventana para cambiar
  el color de la barra de título, y 1 ms después devuelve el foco a quien
  lo tenía. Si era un botón de la barra lateral (pulsar una sección le da
  el foco), ese botón ya no existía: `_aplicar_tema` reconstruye la barra.
  Ahora el foco pasa antes a la ventana. El banco no lo veía: cambiaba de
  tema sin haber pulsado nada, y su ventana no siempre tiene el foco de
  Windows (si el equipo se está usando). `prueba_temas.py` le da a
  customtkinter el que Tk recuerda (`focus -lastfor`) y mira a quién se lo
  devuelve.
- Medido contra la 1.7.0 (mediana de 4, alternando): las pantallas tardan
  entre 0,1 y 0,5 s más en abrirse (enseñan bastante más; Drivers, de 0,36
  a 0,94 s); Aplicaciones, Privacidad y Gaming igual o menos. En la bandeja,
  el mismo consumo; con la ventana quieta, 0,45 % de CPU (0,35 %): Inicio
  ahora lee también la GPU de AMD e Intel. Memoria: 97 MB (86 MB).

### Ajustar TechClean a este equipo (`recomendaciones.py`, 1.8.0)

Idea del desarrollador: "un botón que analice el PC y le indique o active
qué funciones tener encendidas y apagadas", al inicio y no escondido.

- Una tarjeta en Inicio ("Ajusta TechClean a tu equipo") hasta que se usa o
  se pulsa "Ahora no" (`ajuste_equipo_visto`); después, en Ajustes. No es
  una ventana que salte sola al abrir: molesta, y con su `grab_set` habría
  estorbado a todo el banco, que crea la app sin preferencias.
- Propone, no aplica: la app solo cambia lo que se le pide. Cada propuesta
  va marcada y con su porqué; se aplica lo que quede marcado.
- `recomendaciones.recomendar(equipo, estado)` es pura y solo devuelve lo
  que CAMBIA: Modo Ligero (encender en equipos de ≤2 núcleos o ≤4 GB,
  quitar en ≥4 núcleos y ≥8 GB), liberar RAM automática (siempre: solo
  actúa al llenarse; 80 % con ≤8 GB, si no 85 %), ahorro con batería baja
  (portátiles), Modo Juego automático en los juegos instalados (si no
  marcó ninguno: lo que eligió no se toca), frenar acaparadores, limpieza
  semanal y abrir con Windows (si hay algo automático: solo funciona con
  la app abierta).
- Sustituye a la sugerencia del Modo Ligero (una ventana, una vez, solo en
  equipos modestos).
- El plan de energía NO se propone: "alto rendimiento" en un sobremesa
  moderno apenas gana y gasta más; no hay una recomendación honesta
  general.
- La limpieza programada y el inicio con Windows son tareas de schtasks:
  en un hilo y comprobando que quedaron. En el banco se simulan (no se
  crean tareas de verdad en el equipo de desarrollo).

### Condiciones de uso antes de abrir la app (1.8.0)

Lo pidió el desarrollador ("quizá un usuario me meta en problemas"): que
haya que aceptar las condiciones antes de usarla. Antes se le había
desaconsejado en el .exe portable; decidió que sí, y es su decisión.

- `main.pedir_terminos()` se llama en `__main__`, ANTES de crear
  `TechCleanApp`: hasta aceptar no arranca nada (bandeja, buscador de
  actualizaciones, vigilante). Es una ventana `ctk.CTk` propia que se
  destruye antes de crear la de la app: dos raíces de Tk seguidas en el
  mismo proceso funcionan (prueba_acciones_rapidas.py lo comprueba).
  Como no está en `TechCleanApp.__init__`, el banco (que crea la app
  directamente) no la ve.
- Aceptar solo con la casilla marcada; cerrar la ventana es no aceptar y
  la app sale. Se guarda `terminos_aceptados` (= `TERMINOS_VERSION`) y la
  fecha; las dos claves no se importan con "Importar ajustes".
- `--limpieza-programada` sin aceptar no limpia: alguien que actualiza
  desde la 1.7.0 con la limpieza programada puesta no ha visto todavía las
  condiciones nuevas.
- Solo en la edición cliente (`__main__` de main.py); la Admin la usa el
  propio desarrollador.
- Texto en llano, no revisado por un abogado: sin garantía, bajo su
  responsabilidad "en la medida en que la ley lo permita", solo en equipos
  propios o con permiso, privacidad y licencia.

### El widget flotante con el tema (1.8.0)

Lo vio el desarrollador con la app compilada: el rediseño no llegó al
widget, que seguía con los colores de la 1.6 escritos a mano y no pegaba
con Pulido (el de fábrica) ni con ningún otro tema.

- `widget._tomar_colores()` lee las fichas del tema activo al crear el
  widget. Del diccionario `temas.TEMAS[T.nombre]` y no de `T.<ficha>`: T
  solo se rellena con `temas.aplicar()`, y el banco crea el widget sin la
  app. Las esquinas se limitan (ventana ≤ 14, tarjetas ≤ 10): las de Claro
  (18) se comían media fila en algo tan pequeño.
- Tarjetas redondeadas como las de la app (`_Tarjeta`, la misma idea que
  `Tarjeta` de main.py: esquinas de `iconos.esquinas`, borde de cuatro
  rectángulos). Los emojis de los atajos y los caracteres ⚙ ✕ ▾ pasaron a
  los iconos de línea (`iconos.foto` / `icono_cuadro`; nuevos: cerrar,
  abajo, arriba, bateria, temperatura, diana). Modo Juego encendido se
  pinta con el acento, como lo seleccionado en la app.
- Al cambiar de tema, `main._rehacer_widget` lo vuelve a crear como
  estaba (visible u oculto, desplegado o no). Antes había que cerrarlo y
  abrirlo.
- Primera versión: solo cambiaban los colores, y al desarrollador no le
  convenció ("se ve casi igual al primero que tuvimos"): lo que iba bien
  era VERDE en todos los temas, y el verde era lo que más se veía. Se hizo
  como la app (`color_uso`): lo que va bien en el ACENTO del tema, aviso y
  crítico solo cuando se llena; los números en el color del texto (en el
  acento con Telemetría, el tema "de panel de control", que además pone
  los títulos en mayúsculas); los atajos, cuadritos teñidos del acento; el
  logo sobre su cuadrito de acento y la versión en una píldora, como en la
  barra lateral; la barra compacta con iconos en vez de "CPU 26%"; las
  cifras con la letra de números del tema (`T.familia_num`) y todo al
  tamaño del tema (Alto contraste, +12 %).
- Las cifras van en etiquetas de ancho fijo: pasar de 9 % a 10 % no mueve
  la barra (ver "LOS NÚMEROS YA NO TIEMBLAN" en widget.py). Ya no hace
  falta Consolas para eso: lo que lo evita es el ancho fijo.

### Reportar un problema (`reportar.py`)

Lo pidió el desarrollador (2026-10-13): que si a alguien le falla la app,
le pueda mandar el error y cómo es su equipo. Se descartó un envío
automático: haría falta un servidor, o meter en el `.exe` una clave (un
webhook de Discord, un token) que cualquiera podría sacar y usar; y
rompería "TechClean no envía nada" de `PRIVACIDAD.md`.

- El aviso de errores tiene **Enviar este error**, y Ajustes, **Reportar un
  problema** (con el último error de la sesión, si hubo). La ventana
  enseña EXACTAMENTE el texto (Markdown), y la persona puede añadir qué
  estaba haciendo.
- `reportar.limpiar` quita la carpeta de usuario (en sus tres formas: con
  `\`, con `/` y escapada con `\\` como sale en un `repr`), el nombre de
  usuario y el del equipo, como palabra suelta y de 3 letras o más. El más
  largo primero: con el usuario "Ana" y el equipo "ANA-PC", quitar antes
  el usuario dejaba "<usuario>-PC".
- *Abrir en GitHub* = la dirección de nuevo issue con `title` y `body`.
  GitHub rechaza direcciones de más de ~8 KB: si no cabe, se recorta el
  error por el medio (se quedan el principio y las últimas líneas, que son
  las que dicen qué pasó) y el texto completo se copia al portapapeles.
- La gráfica se pide en un hilo (`get_gpu_info` lee contadores del
  sistema).
- Probar Edge desde la consola Bash de las herramientas de desarrollo
  fallaba en silencio (código 0, sin PDF); desde PowerShell o la app,
  bien. No es la app: es ese entorno.

### Pendiente de comprobar como administrador

El consumo de energía por app (SRUM), la salud de los discos SATA y el
análisis de disco de las carpetas del sistema. La app compilada siempre
corre como administrador (`--uac-admin`); el banco, no.

Ya comprobado (2026-10-13, Admin 1.8.0 compilada): desactivar lo que
arranca para todos los usuarios (HKLM `Run` y `Run32`): el valor de
`StartupApproved` queda en 03 y la acción entra en Deshacer.

## Malware encontrado en el equipo del desarrollador (2026-10-04)

Durante un escaneo de solo lectura apareció un malware en Python instalado
el 2026-04-16: tarea programada "\Orion Terrorist Ghana 32308-S-1-5-21-…"
(al iniciar sesión, sin autor) que lanza `gep.exe` = **pythonw.exe
renombrado** desde `%APPDATA%\Autodesk\Inventor Interoperability 2026\FileCache`
(carpeta falsa; Autodesk real está instalado) con `node_modules.asar` =
`exec(b85decode(...))` → capa RC4 → capa ofuscada. McAfee (activo y al día)
no lo detectó en seis meses. Es el caso real que imita
`prueba_seguridad.py` (con datos inventados: la prueba no depende de él).

**Quitado el 2026-10-13**, a petición del desarrollador. Estaba corriendo y
con una conexión abierta a 172.67.223.17:443 (Cloudflare). Se exportó y
borró la tarea, se paró el proceso, y la carpeta y `Inicio\server.lnk`
quedaron en `C:\Users\<usuario>\Cuarentena_TechClean\2026-10-13_Orion\`
como `.zip` (con huellas, la tarea en XML y un LEEME): la muestra sigue
disponible para el antivirus, fuera de OneDrive a propósito. Una búsqueda
a fondo después (tareas, Run, servicios, WMI, IFEO, binarios renombrados,
conexiones) no encontró nada más.

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
- FPS reales dentro de los juegos (2026-10-07): descartado por el
  desarrollador. Haría falta leer los eventos de presentación de DirectX
  (ETW, como PresentMon), con administrador y mucho más trabajo en segundo
  plano del que quiere una app ligera.
- Drivers de kernel o cualquier cosa "a nivel 3" (leer sensores a mano,
  tocar la memoria de otros procesos): nunca. Un driver mal hecho tumba el
  equipo, y firmarlo no es viable.
- Leer la MFT para el análisis de disco: no descartado, aplazado (ver "El
  analizador de disco, y por qué no lee la MFT").
