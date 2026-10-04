# TechClean 1.6.0

**La versión más grande hasta ahora: RAM al nivel de Mem Reduct, limpieza a
fondo del disco, un auditor de seguridad, y un Modo Juego que por fin cierra
lo que estorba.** Y una tanda de errores corregidos, algunos serios.

Si venías de la 1.5.0, tus preferencias y tu historial siguen como estaban.

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

### 🧠 La RAM, al nivel de Mem Reduct

Antes TechClean le pedía a cada programa, uno por uno, que soltara memoria.
Eso dejaba fuera los programas protegidos (antivirus, servicios), la caché
de archivos de Windows y los datos pendientes de escribir a disco. Ahora se
libera igual que lo hacen Mem Reduct y RAMMap. Medido en un equipo real:
**de 38 % a 25 % de RAM en uso**.

- **Liberación profunda** (botón aparte): además vacía la caché en espera.
  Libera más, pero lo que abras justo después tarda un poco más la primera
  vez. Por eso nunca se hace sola.
- **La RAM se libera sola de verdad.** Ajustes decía que lo hacía, pero solo
  pasaba con el Modo Juego encendido. Ahora funciona siempre: al pasar el
  umbral y, si querés, cada 15, 30, 60 o 120 minutos.

### 🧹 Limpieza a fondo del disco

Una pestaña nueva en Espacio en disco con lo mismo que el Liberador de
espacio de Windows, con el tamaño real de cada cosa: descargas viejas de
Windows Update, informes de errores, volcados de memoria, registros
antiguos. Y aparte, **limpiar los componentes viejos de Windows** (puede
liberar varios GB en equipos con muchas actualizaciones).

También: **buscador de archivos duplicados** (mismo contenido, no solo el
mismo nombre; siempre queda una copia) y **optimizar unidades** (TRIM en SSD,
desfragmentar solo en discos mecánicos).

### 🎮 Gaming

- **Cerrar apps mientras jugás.** Marcás cuáles (Discord, el navegador,
  OneDrive...) y, con el Modo Juego, se cierran al detectar un juego y se
  vuelven a abrir solas al terminar. Es **opcional**: viene apagado. Nunca
  cierra el juego, ni Steam/Epic/Riot (muchos juegos mueren sin ellos), ni
  partes de Windows.
- **Ajustes de Windows para juegos** en un solo sitio: Modo de juego,
  grabación en segundo plano de la Game Bar, programación de GPU acelerada.
  Cada uno se puede deshacer.
- **Medidor de lag.** La prueba de velocidad mide megas; lo que molesta al
  jugar es el lag. Mide tu router y un servidor de internet por separado y te
  dice si el problema es tu Wi-Fi o tu proveedor.
- **Plan "Máximo rendimiento"**, el plan oculto de Windows, con un clic.
- **Juegos de GOG**: ahora aparecen también los instalados con GOG Galaxy y
  los copiados de otro disco.

### 🔎 Auditoría de seguridad

Una pestaña nueva en Seguridad que busca señales de malware que los
antivirus no siempre ven: programas disfrazados (un intérprete de Python
renombrado y escondido en AppData), cosas que se arrancan solas con comandos
ocultos, mineros de criptomonedas, exclusiones añadidas a Windows Defender.
**Solo mira: no borra ni cierra nada.** Te dice qué encontró, por qué es
sospechoso y dónde está.

Nació de un caso real: un programa malicioso que pasó meses en un equipo sin
que el antivirus lo viera. Este auditor lo encuentra en unos 20 segundos. Y
se ajustó para no marcar programas legítimos (Lenovo, Roblox, Discord): un
auditor que grita por todo enseña a ignorarlo.

También: **programas que escuchan en la red** y un **vigilante** que te avisa
si un programa tiene una fuga de memoria (no para de crecer) o si un disco
se está llenando.

### 🔒 Privacidad de Windows

Seis interruptores para lo que Windows usa para mostrarte anuncios: ID de
publicidad, sugerencias del menú Inicio y de Configuración, consejos,
experiencias personalizadas y resultados de Bing en el buscador de Inicio.
Con un botón para apagar todo. Cada uno se puede deshacer.

### 📦 Aplicaciones

- **Quitar apps de serie** (Candy Crush, Noticias, Solitaire...). Solo de una
  lista conocida, nunca la Tienda, Fotos o la Calculadora, y se pueden volver
  a instalar.
- **Actualizar todas las apps de una vez** con winget.

### 🌐 Red

**DNS más rápido**: mide tu DNS y cuatro públicos desde tu conexión. Si el
tuyo ya es de los más rápidos, te lo dice en vez de empujarte a cambiarlo.
Si cambiás, se puede deshacer.

### 🛟 Sistema

- **Puntos de restauración**: cuántos tenés, cuánto ocupan (a veces muchos
  GB), crear uno y borrar los viejos dejando el más reciente.
- **Informe de energía de Windows**: qué impide que la laptop suspenda o qué
  gasta batería.

### 🧰 Edición Administrador

Informe para el cliente (el antes y el después y el trabajo hecho, listo
para imprimir o guardar como PDF), salud de discos y batería, historial de
pantallazos azules, respaldo de controladores antes de formatear, y
mantenimiento completo en un clic.

### ⌨ Consola

13 comandos nuevos (38 en total): `/ramprofunda`, `/autoram`, `/fondo`,
`/fugas`, `/procesos`, `/discos`, `/bateria`, `/pantallazos`, `/unidades`,
`/medirdns`, `/plan`, `/red` y `/tecnico`.

---

## Errores corregidos

Los que importan, contados tal cual:

- **"Limpiar archivos temporales" podía borrar archivos de FUERA de la
  carpeta de temporales.** Si un instalador dejaba dentro de %TEMP% un acceso
  a otra carpeta (una "unión" de Windows), la limpieza la vaciaba también.
  Se comprobó con la 1.5.0: borró un documento de prueba que estaba fuera.
  Ya no pasa, y hay una prueba que lo vigila.
- **"Punto de restauración creado" podía ser mentira.** Windows solo crea
  uno cada 24 horas; si ya había uno, no creaba otro, pero la app decía que
  sí. Y eso se usaba justo antes de reparar con sfc/DISM.
- **La liberación automática de RAM no funcionaba** sin el Modo Juego, y con
  él, si la RAM seguía alta, liberaba cada 8 segundos sin parar.
- **Con la app minimizada en la bandeja, seguía trabajando**: dibujaba
  gráficas que nadie veía y lanzaba procesos cada 2 segundos. CPU en la
  bandeja: de **3.1 % a 1.0 %** (o menos).
- **sfc y DISM podían colgarse para siempre** si escribían mucho texto.
- **La lista de actualizaciones de apps salía vacía** con winget en español.
- **Steam y Discord no aparecían** en la limpieza de caché de apps (miraba
  carpetas equivocadas), y la caché de apps anunciaba más espacio del que
  borraba.
- **11 sitios tocaban la interfaz desde un hilo**, la causa de errores como
  `main thread is not in main loop`.
- **Unos 20 textos salían en español en la versión en inglés.**
- Deshacer un cambio de plan de energía te mandaba a "Equilibrado" aunque
  antes estuvieras en otro plan. Ahora vuelve al plan exacto.

---

## Para quien mire el código

El banco de comprobaciones pasó de 26 a **35**. Las más interesantes:

- **`revisar_errores_banco.py`**: la app atrapa sus propios errores para no
  cerrarse en la cara de nadie, así que una prueba podía decir "ok" aunque
  dentro hubiera saltado un error. Esta revisa lo que la app registró
  mientras corría el banco. Así aparecieron los 11 sitios de hilos.
- **`prueba_seguridad.py`**: el primer caso es el malware real del que nació
  el auditor. Si alguien cambia las reglas y deja de detectarse, falla.
- `verificar_idiomas.py` ya **falla** cuando encuentra algo (antes lo
  imprimía y el banco lo daba por bueno) y busca textos de la interfaz
  escritos a mano sin traducir.

Y un `CLAUDE.md` con las reglas del proyecto en una página.

---

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.
Gratis de usar y de leer — ver [LICENSE.md](LICENSE.md).
