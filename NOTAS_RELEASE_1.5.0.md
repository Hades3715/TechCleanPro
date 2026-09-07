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

### ↩ Deshacer lo que la app cambió

Esta es la grande, y no la tiene ninguna app gratis de limpieza.

TechClean se descarga como un `.exe` sin firma, hecho por alguien que no
conoces, y toca cosas de tu sistema. Pedirte que confíes a ciegas es mucho
pedir. Ahora la app guarda **cómo estaba cada cosa antes de tocarla**, y en
el Historial hay una pestaña **↩ Se puede deshacer** para volver atrás:

- el perfil de energía
- las apps de inicio que desactivaste
- los servicios que paraste o iniciaste
- los efectos visuales
- el Inicio rápido de Windows
- el arranque automático y la limpieza programada

**Y dice claro lo que NO se puede deshacer**, arriba de la lista, antes que
nada: los archivos temporales borrados no vuelven, ni la papelera vaciada,
ni el caché del navegador, ni un proceso que cerraste. Un botón de
"Deshacer" que a veces no funciona es peor que no tenerlo, porque acabas
contando con él para cosas que no cubre. (Los archivos que enviaste a la
papelera sí se recuperan, pero desde la papelera de Windows.)

### 🧰 Herramientas de técnico (Edición Administrador)

Para quien arregla computadoras ajenas:

- **📸 Antes y después** — guarda cómo está el equipo, optimizas, y te
  muestra la diferencia campo por campo. Para enseñarle a la persona qué
  cambió, en vez de decir "quedó mejor".
- **🚀 Arranque completo** — todo lo que se inicia con Windows en una sola
  lista: registro del usuario y de la máquina (incluida la clave de 32 bits,
  que casi nadie revisa), las dos carpetas Inicio y las tareas programadas.
  La pantalla de Aplicaciones solo mira uno de esos cuatro sitios.
- **📈 Grabar métricas** — apunta CPU, RAM, disco y temperatura a un CSV.
  Para el caso de "a veces se pone lento y no sé por qué": lo dejas
  grabando, usas el equipo, y después buscas el pico en Excel.

### 📦 Instalador

Ya hay un instalador normal, de los de toda la vida: se instala en Archivos
de programa, aparece en "Agregar o quitar programas" y se desinstala limpio
—incluidas las tareas programadas que la app deja, para que no queden
huérfanas apuntando a un archivo borrado.


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
`Generar_App_Rapida.bat` la misma app queda en modo carpeta, sin nada que
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

Y un error que aparecía al abrir la app en algunos equipos
(`main thread is not in main loop`).

---

## Para quien mire el código

El banco de comprobaciones pasó de 5 a **20**: doble clic en
`herramientas\Verificar_Todo.bat`. Revisa hilos, contrato de datos entre
módulos, las 16 pantallas con cada pestaña, repintados con datos rotos, los
21 comandos del panel oculto, que los ajustes surtan efecto sin reiniciar, y
que los bucles de refresco no se acumulen.

---

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.
Gratis de usar y de leer — ver [LICENSE.md](LICENSE.md).
