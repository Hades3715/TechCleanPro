# TechClean 1.5.0

**La app se llamaba TechClean Pro. Ahora es TechClean, a secas.**

Si venías de la versión anterior, tus preferencias se traen solas: el widget,
el perfil de energía, los umbrales y el idioma siguen como los tenías.

---

## Descarga

| Archivo | Para quién |
|---|---|
| **TechClean_ES.exe** | Si querés la app en español |
| **TechClean_EN.exe** | If you want the app in English |

Descargá **uno solo**, el que te sirva. No hace falta instalar nada más.

> **Windows te va a avisar la primera vez.** Sale una pantalla azul que dice
> "Windows protegió tu PC". Es porque la app no tiene firma digital (cuesta
> unos cientos de dólares al año y soy estudiante). Hacé clic en **Más
> información** → **Ejecutar de todas formas**. El código está entero acá
> arriba para que cualquiera lo revise.

---

## Novedades

### El historial ya no se pierde al cerrar la app

Antes todo lo que hacías se borraba al salir. Ahora se guarda, y la pantalla
de Historial tiene un selector entre **Esta sesión** y **Todo el historial**:
cuántas acciones, en cuántas sesiones, cuánto espacio liberaste en total y
desde cuándo. Así se puede responder a la pregunta que de verdad importa:
*¿mi equipo va peor que hace tres meses?*

Se guarda solo en tu computadora, hay un botón para borrarlo, y se recorta
solo para no engordar sin freno.

### Prueba de velocidad de internet rehecha

Ahora mide también la **latencia** y muestra la velocidad **en vivo** mientras
corre, con una aguja de escala logarítmica: una conexión de 6 Mbps se lee
igual de bien que una de fibra.

### Una versión que abre en medio segundo

El `.exe` de un solo archivo tiene que descomprimir 22 MB cada vez que lo
abrís, antes de que aparezca nada: **3.7 segundos**. Con
`compilar\Generar_App_Rapida.bat` la misma app queda en modo carpeta, sin nada que
descomprimir: **0.5 segundos**.

### La temperatura del CPU funciona en muchos más equipos

Solo se consultaba un sensor que un montón de portátiles no publican. Se
añadió una segunda fuente, y con eso aparece la temperatura donde antes decía
"No disponible en este equipo" — lo que reactiva la tarjeta de temperatura, su
gráfica, la fila del widget flotante y las alertas de Ajustes.

### Gráficas nuevas

Las de RAM, CPU y temperatura entran deslizándose en vez de saltar, con
rejilla para leer la altura, degradado y los valores mínimo y máximo. La de
temperatura ya no está siempre en rojo: sigue la temperatura real.

### La consola, rehecha

El panel de comandos ahora se maneja como una consola de verdad: **flecha
arriba y abajo** para recorrer lo que ya escribiste, **Tab** para completar,
**fichas** arriba con los comandos más usados, y **Ctrl+L** para limpiar.

Cada línea lleva su hora y su color: verde lo que salió bien, rojo lo que
falló, ámbar los avisos. Antes todo salía del mismo verde, así que un
"Papelera vaciada" y un "No se pudo vaciar la papelera" se veían exactamente
igual y había que leer la frase entera para saber cuál de los dos era.

Si escribís un comando mal, te sugiere el parecido en vez de mandarte a leer
la lista otra vez. Y hay botones para **copiar**, **limpiar** y **guardar** el
registro en un archivo, que es lo que hace falta cuando querés reportar algo.

Cuatro comandos nuevos: `/estado` (foto rápida de CPU, RAM, disco, GPU,
temperatura y batería sin salir de la consola), `/version` (versión, edición,
permisos y dónde guarda los datos), `/limpiar` y `/guardar`.

### El widget flotante ya no es un rectángulo

Tiene **esquinas redondeadas de verdad**, no simuladas: encima del escritorio
o de un juego ya no se ve como un recorte de cartón pegado a la pantalla.

Los atajos **responden al pasar el ratón** — antes no daban ninguna señal de
ser pulsables. Cada fila de Sistema tiene su propio icono en vez de cuatro
puntos idénticos. Y cada métrica lleva una **minigráfica** con el último medio
minuto: un número dice dónde estás, la forma dice si vas subiendo o si fue un
pico que ya pasó.

**Y la barra ya no tiembla.** Al pasar de "CPU 9%" a "CPU 10%" la etiqueta
crecía un carácter y empujaba a las de su derecha, así que la barra entera se
recolocaba sola una o dos veces por segundo mientras la mirabas. La velocidad
de red además iba siempre en K: a 5 MB/s ponía "5120K".

---

## Correcciones importantes

**La app no arrancaba con Windows.** La tarea se creaba y se veía habilitada,
pero Windows le ponía por su cuenta "no iniciar si el equipo va con batería":
en un portátil sin enchufar no arrancaba nunca, sin ningún error. Si ya la
tenías activada, Ajustes lo detecta y te ofrece un botón para arreglarla.

**Modo Juego le subía la prioridad al Explorador de Windows.** Daba por juego
a pantalla completa cualquier ventana del tamaño de la pantalla — y eso
incluye el escritorio al minimizar todo, y cualquier ventana maximizada.

**El overlay de FPS mandaba a la Microsoft Store**, porque usaba un enlace que
las versiones nuevas de Xbox Game Bar ya no reconocen.

**El tono de prueba de audio no sonaba en muchos equipos.** No pasaba por la
tarjeta de sonido. Ahora suena de verdad, la ventana te pregunta si lo
escuchaste y, si no, te lleva al mezclador y al selector de dispositivo.

**Reiniciar el Explorador podía dejarte sin barra de tareas** y decirte que
todo había ido bien.

**Limpiar la caché del navegador informaba de más:** medía el tamaño antes de
borrar y te daba ese número aunque no hubiera podido borrar nada.

**Vaciar la papelera congelaba la ventana** y decía "vaciada" pasara lo que
pasara. Ahora va en segundo plano y te dice cuánto liberó de verdad.

**Entrar y salir de Componentes deprisa dejaba procesos de refresco
acumulados**, consultando el sistema cada pocos segundos, para siempre.

**Ocho de las comprobaciones del banco de pruebas no se estaban
ejecutando.** El archivo que las corre tenía ocho rutas mal escritas, y el
fallo era silencioso: imprimía el título de cada comprobación, no imprimía
ningún error, y seguía con la siguiente. Parecía estar pasando entero. Los
`.py` sí funcionaban —se corren también uno a uno— pero quien hiciera doble
clic al `.bat` estaba comprobando quince cosas de veintitrés creyendo que
comprobaba las veintitrés.

Además de arreglarlo, ahora el banco cuenta los fallos y avisa cuando una
comprobación no llega ni a arrancar, y hay una comprobación nueva que vigila
el propio archivo que corre las demás.

Y un error que aparecía al abrir la app en algunos equipos
(`main thread is not in main loop`).

---

## Para quien mire el código

El banco de comprobaciones pasó de 5 a **26**: doble clic en
`herramientas\Verificar_Todo.bat`. Revisa hilos, contrato de datos entre
módulos, las 16 pantallas con cada pestaña, repintados con datos rotos, los
25 comandos del panel oculto, que los ajustes surtan efecto sin reiniciar, y
que los bucles de refresco no se acumulen.

Dos comprobaciones nuevas de esta tanda merecen mención, porque las dos
vigilan cosas que no dan la cara probando la app:

- **`revisar_empaquetado.py`** abre los `.exe` ya compilados y mira si llevan
  dentro todo lo que la app importa. Un módulo que PyInstaller deje fuera
  funciona perfectamente desde el código —está instalado en el equipo— y
  falla solo en la copia que se reparte, en el momento en que alguien entra a
  la pantalla que lo usa.
- **La sección 5 de `auditoria.py`** vigila el archivo que corre el banco. Es
  la que faltaba para que las ocho comprobaciones saltadas no hubieran pasado
  desapercibidas.

---

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.
Gratis de usar y de leer — ver [LICENSE.md](LICENSE.md).
