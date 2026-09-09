# TechClean — Panel de Optimización de Sistema

App de escritorio para **Windows 10 y Windows 11**: monitoreo real de CPU/RAM/
GPU/disco/red/batería, lectura extendida de componentes (por núcleo, por
módulo de RAM, por partición, temperaturas cuando el equipo las expone),
optimización de memoria, perfiles de energía, Modo Juego, limpieza programada,
reparación de sistema, gestor de apps de inicio, desinstalador, limpieza de
temporales, borrado real de historial de navegadores, historial transparente
de cada acción, widget flotante de rendimiento, bandeja del sistema, inicio
automático con Windows, y acceso directo a BIOS/UEFI.

Disponible en **español e inglés**: se publican dos ejecutables separados,
uno por idioma. Descarga el que te sirva por el nombre del archivo.

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.

**Gratis, pero no de dominio público.** Podés usarla libremente, leer el
código y compilar tu propia copia. Lo que no podés es redistribuirla,
publicarla como tuya ni venderla — ver [LICENSE.md](LICENSE.md).

---

## 0. La forma más fácil de empezar (recomendada)

No necesitas leer todo este documento para usar la app. Extrae el ZIP y haz
doble clic en:

**`Generar_App_Instalable.bat`**

Ese archivo hace todo el trabajo una sola vez (instala lo necesario y
compila la app) y al final te deja **dos** archivos en la misma carpeta:

- **`TechClean_ES.exe`** — la app en español
- **`TechClean_EN.exe`** — la app en inglés

Quédate con el que quieras usar (o reparte los dos). Ese `.exe` sí lo puedes
mover a tu Escritorio y abrir con doble clic para siempre — no necesitas
Python instalado, ni volver a correr ningún script, ni escribir ningún
comando.

Requisito: tener [Python](https://www.python.org/downloads/) instalado una
vez (marca "Add Python to PATH" al instalarlo). Es solo para generar el
`.exe`; una vez generado, ya no hace falta.

Si mientras seguimos ajustando la app prefieres probar cambios rápido sin
recompilar el `.exe` cada vez, usa `Iniciar_Rapido.bat` en su lugar.

### ¿Y si quieres que abra más rápido?

El `.exe` de un solo archivo lleva la app comprimida dentro, y Windows tiene
que descomprimir 22 MB en una carpeta temporal **cada vez** que lo abres,
antes de que aparezca nada. Medido en el equipo de desarrollo: **3.7
segundos**.

`Generar_App_Rapida.bat` compila la misma app en modo carpeta, sin nada que
descomprimir: **0.5 segundos**. El costo es que en vez de un archivo suelto
es una carpeta con muchos archivos dentro (el script deja también los `.zip`
listos para repartir).

Para usarla a diario en tu propio equipo, esa es la buena. El `.exe` único
sigue existiendo porque es más cómodo de descargar y de pasarle a alguien.

### ¿Y un instalador normal?

También hay uno. `instalador\Compilar_Instalador.bat` genera un instalador
de los de toda la vida: se instala en Archivos de programa, aparece en
"Agregar o quitar programas", crea accesos directos y se desinstala limpio
(incluidas las tareas programadas que la app deja, para que no queden
huérfanas).

Necesita [Inno Setup](https://jrsoftware.org/isdl.php) instalado, que es
gratis. **No reemplaza la firma digital**: Windows va a seguir avisando la
primera vez, solo que menos.

### Windows va a mostrarte una advertencia la primera vez

Al abrir el `.exe` verás una pantalla azul que dice **"Windows protegió tu
PC"** y *Editor desconocido*. **Es normal y esperado.** No significa que el
archivo tenga un virus.

Pasa porque la app no está firmada con un certificado de firma de código:
cuestan unos $220 al año y este es un proyecto de una sola persona, así que
por ahora no lo tiene. Cualquier programa sin firmar recibe esa advertencia,
sea bueno o malo.

Para abrirla igualmente: haz clic en **"Más información"** y luego en
**"Ejecutar de todas formas"**.

Si prefieres no confiar en un ejecutable sin firmar — que es una postura
perfectamente razonable — el código fuente completo está en este mismo
repositorio y puedes generar tu propio `.exe` con `Generar_App_Instalable.bat`,
o correr la app directamente con `Iniciar_Rapido.bat`.

El resto de este documento explica el paso a paso manual y el detalle
técnico de cada sección, por si lo necesitas.

---

## 1. Dos ediciones: Cliente y Administrador

TechClean se genera en **dos aplicaciones separadas**, a partir del
mismo código:

| | Edición Cliente | Edición Administrador |
|---|---|---|
| Archivo fuente | `main.py` | `main_admin.py` |
| Script para generar el `.exe` | `Generar_App_Instalable.bat` | `Generar_App_Admin.bat` |
| `.exe` resultante | `TechClean_ES.exe` y `TechClean_EN.exe` | `TechClean_Admin.exe` |
| Idioma | Fijo, según el `.exe` que descargues | Selector en Ajustes (ES/EN) |
| Consola Dev en el menú | No existe | Siempre visible |
| Comando técnico exacto en el Historial | Oculto | Siempre visible |
| Botones de "Probar error" en Ajustes | Ocultos | Visibles |
| Etiquetas de permisos | "Todas las funciones activas" / "Desbloquear funciones" | "🛡 Administrador" / "Reiniciar como Admin" |
| Panel de comandos oculto | Sí (ver sección 3) | No hace falta — ya se ve todo |
| Pensada para | Repartir al usuario final | Uso propio / soporte técnico |

Ambas ediciones comparten el 100% de la lógica real: la única diferencia es
qué tan visible es lo técnico. `main_admin.py` es un lanzador de una línea
que activa la edición admin antes de arrancar `main.py`.

**Sobre el idioma:** la edición cliente no lleva selector dentro. El idioma
queda fijado al compilar (`build_config.py`) y se publican dos ejecutables,
uno por idioma, para que cada quien descargue el suyo por el nombre del
archivo. La edición admin sí conserva el selector, porque es una sola build
y sirve para revisar cómo queda todo en ambos idiomas sin recompilar.

---

### Qué trae la Edición Administrador que no trae la de cliente

Una pestaña **🧰 Técnico** con tres herramientas pensadas para quien arregla
computadoras ajenas:

- **📸 Antes y después** — guarda cómo está el equipo, optimizas, y te
  muestra la diferencia campo por campo. Para enseñarle a quien te pidió el
  favor qué cambió, en vez de decir "quedó mejor".
- **🚀 Arranque completo** — todo lo que se inicia con Windows en una lista:
  el registro del usuario y el de la máquina (incluida la clave de 32 bits,
  que casi nadie revisa), las dos carpetas Inicio, y las tareas programadas.
  La pantalla de Aplicaciones solo mira uno de esos cuatro sitios.
- **📈 Grabar métricas** — apunta CPU, RAM, disco y temperatura a un CSV cada
  pocos segundos. Para el caso de "a veces se pone lento y no sé por qué":
  lo dejas grabando, usas el equipo, y después buscas el pico en Excel.

Además: el comando exacto de cada acción en el Historial, la Consola de
Desarrollador y el selector de idioma dentro de la app.

**Una aclaración honesta:** el código de esta app es público, así que
cualquiera puede compilar la Edición Administrador. Esconder funciones no es
posible y fingir que sí sería engañarte. Estas herramientas están ahí porque
son útiles para un técnico, no como una cerradura.

---

## 2. Instalación (paso a paso, sin perderte)

### Paso 1 — Extrae el ZIP
Descarga el archivo `TechClean.zip` y **extráelo completo** (clic derecho →
"Extraer todo...") en una carpeta fácil de recordar, por ejemplo tu Escritorio.

```
TechClean/
├── Generar_App_Instalable.bat   ← doble clic: genera TechClean_ES.exe y _EN.exe
├── Generar_App_Rapida.bat       ← doble clic: la misma app, pero abre en medio segundo
├── Generar_App_Admin.bat        ← doble clic: genera TechClean_Admin.exe
├── Iniciar_Rapido.bat           ← doble clic: prueba la edición cliente sin compilar
├── Iniciar_Rapido_Admin.bat     ← doble clic: prueba la edición admin sin compilar
├── main.py                      ← app + edición cliente
├── main_admin.py                ← lanzador de la edición administrador
├── idiomas.py                   ← todos los textos, en español e inglés
├── deshacer.py                  ← registro de cambios reversibles
├── tecnico.py                   ← herramientas de la edición administrador
├── instalador/                  ← script del instalador (necesita Inno Setup)
├── build_config.py              ← idioma de esta compilación (lo reescribe el .bat)
├── system_monitor.py
├── optimizer.py
├── preferences.py
├── privacy.py
├── report.py
├── autopilot.py
├── tray.py
├── widget.py
├── requirements.txt
├── README.md
├── LICENSE.md
├── herramientas/                ← el banco de comprobaciones (ver sección 11)
└── assets/
    └── honk.wav
```

Si solo ves un archivo `.py` suelto, es que no extrajiste el ZIP — todavía está
comprimido. Tiene que quedar la carpeta completa con TODOS los archivos.

### Paso 2 — Instala Python (si no lo tienes)
[python.org/downloads](https://www.python.org/downloads/) — marca **"Add
Python to PATH"** durante la instalación.

### Paso 3 — Abre una terminal EN esa carpeta
Abre la carpeta `TechClean` en el Explorador, clic en la barra de
direcciones, escribe `powershell`, Enter.

Para varias funciones (papelera, RAM, reparación, BIOS) es mejor abrirla como
administrador: clic derecho sobre PowerShell en el menú inicio → "Ejecutar
como administrador", y moverte con `cd` hasta la carpeta:
```
cd $HOME\Desktop\TechClean
```

### Paso 4 — Instala las dependencias
```
pip install -r requirements.txt
```

### Paso 5 — Ejecuta la app
```
python main.py
```
(o `python main_admin.py` para la edición administrador)

---

## 3. Panel de comandos oculto (solo Edición Cliente)

En **Ajustes**, haz **7 clics seguidos** sobre el número de versión. Aparece
"🔓 Panel oculto" en el menú — una consolita tipo terminal donde puedes
**escribir comandos** en vez de hacer clic en botones. No expone comandos
reales del sistema operativo: cada comando dispara la misma función que ya
existe en la interfaz.

Se maneja como una consola de verdad:

- **Fichas** arriba con los comandos más usados: no hace falta saber que
  existe `/help` para descubrir que hay algo.
- **Flecha arriba y flecha abajo** recorren lo que ya escribiste. Si estabas
  a medio escribir algo y subes, al volver abajo lo recuperas.
- **Tab** completa. Con varios candidatos completa la parte común y te los
  enseña, en vez de elegir uno por ti.
- **Cada línea con su hora y su color**: verde lo que salió bien, rojo lo
  que falló, ámbar los avisos. Antes todo salía del mismo color y había que
  leer la frase entera para saber cuál de los dos era.
- **Escribes un comando mal y te sugiere el parecido** en vez de mandarte a
  leer la lista otra vez.
- **Copiar, limpiar y guardar** el registro. Guardar deja un `.txt` en
  `%APPDATA%\TechClean\registros` y te dice la ruta — útil si hay que
  reportar algo.
- **Ctrl+L** limpia. **Esc** vacía la línea.

| Comando | Qué hace |
|---|---|
| `/help` | Muestra esta lista |
| `/ram` | Libera memoria RAM |
| `/temporales` | Limpia archivos temporales |
| `/papelera` | Vacía la papelera |
| `/dns` | Limpia la caché DNS |
| `/rapido` | Optimización con un clic (RAM + temporales) |
| `/componentes` | Abre Componentes del equipo |
| `/reparar` | Abre Reparar el sistema |
| `/apps` | Abre Aplicaciones (inicio de Windows / desinstalador) |
| `/privacidad` | Abre Privacidad |
| `/historial` | Abre el Historial de actividad |
| `/widget` | Muestra/oculta el widget flotante |
| `/auto` | Activa/desactiva el Modo Juego |
| `/bios` | Abre Reiniciar a BIOS |
| `/ajustes` | Abre Ajustes |
| `/estado` | Foto rápida de CPU, RAM, disco, GPU, temperatura y batería |
| `/version` | Versión, edición, permisos, si va compilada y dónde guarda los datos |
| `/limpiar` | Vacía la consola |
| `/guardar` | Guarda el registro en un archivo de texto |
| `/salir` | Vuelve a Inicio |

Repite los 7 clics para ocultarlo de nuevo.

---

## 4. Qué hace cada apartado

| Apartado | Qué hace realmente |
|---|---|
| **Inicio** | CPU, RAM, GPU, disco e info del equipo en vivo, con "Optimización con un clic" arriba |
| **Componentes** | CPU por núcleo + frecuencia + temperatura, GPU con VRAM/temperatura/ventilador, RAM por módulo físico, disco por partición + velocidad de I/O, red, batería, placa madre/BIOS, tiempo encendido, procesos activos, **medidor de velocidad de internet**, **reporte de hardware exportable** |
| **Optimizar** | RAM, temporales, papelera, DNS, **Perfiles de energía**, y **analizador de espacio en disco** |
| **Reparar** | sfc /scannow, DISM RestoreHealth, reparar red, chequeo de disco, buscar actualizaciones de Windows, **punto de restauración automático** |
| **Aplicaciones** | Gestor de apps de inicio, Desinstalador de programas, y **Servicios de Windows** (con confirmación) |
| **Privacidad** | Borra historial y caché real de Chrome/Edge/Firefox (pide cerrarlos primero) |
| **Segundo Plano** | Widget flotante, **Modo Juego**, y Limpieza programada automática |
| **Historial** | Cada acción ejecutada y su resultado — exportable a `.txt`, con **buscador en tiempo real** |
| **Reiniciar a BIOS** | Reinicia directo al firmware, sin pulsar teclas durante el arranque |
| **Ajustes** | Créditos, inicio automático con Windows, **alerta de temperatura de CPU**, easter egg 🪿 |

### Perfiles de energía
En **Optimizar**, tres botones cambian el plan de energía de Windows:
Silencioso (ahorro), Equilibrado (uso diario) y Rendimiento (máxima
velocidad). Usan los planes que Windows trae por defecto — si tu equipo no
los tiene (algunos fabricantes los quitan), se buscan por nombre como
respaldo.

### Modo Juego (estilo AMD Adrenaline)
En **Segundo Plano**, actívalo y hace todo esto junto:
1. Cambia el plan de energía a Rendimiento.
2. Cada 8 segundos (bajo consumo, no en bucle continuo) revisa si hay una
   app a pantalla completa y le sube la prioridad de CPU sin tocarla de
   ninguna otra forma.
3. Si la RAM pasa del 85%, libera memoria automáticamente **excluyendo
   siempre el juego priorizado**, para no causarle un micro-tirón justo
   mientras se supone que lo protege.

Al desactivarlo, vuelve al plan Equilibrado. Todo queda en el Historial.

### Limpieza programada automática
También en **Segundo Plano**: crea una tarea real en el Programador de
tareas de Windows (Diaria o Semanal, 9:00 AM) que libera RAM y limpia
temporales **sin abrir ninguna ventana** — usa la bandera interna
`--limpieza-programada`, que hace el trabajo y termina al instante.

### Reparar
Todo con herramientas oficiales de Windows — TechClean no reemplaza
nada, solo les da un botón:
- **sfc /scannow** — repara archivos protegidos del sistema dañados.
- **DISM /RestoreHealth** — repara el almacén de componentes de Windows.
- **Reparar red** — reinicia Winsock, TCP/IP y limpia DNS.
- **Revisar disco** — programa un chequeo (chkdsk) para el próximo reinicio.

La mayoría necesita permisos de administrador para completarse, y las dos
primeras pueden tardar varios minutos — la app no se congela mientras
corren, pero es mejor esperar antes de cerrarla.

### Aplicaciones — Inicio de Windows y Desinstalador
- **Inicio de Windows**: lista lo que abre solo con el equipo (de tu
  usuario) y permite activar/desactivar cada una. Desactivar NO desinstala
  nada — solo deja de abrirse sola; se puede reactivar cuando quieras.
- **Desinstalar programas**: lee la misma lista que "Programas y
  características" de Windows y ejecuta el desinstalador **oficial** de
  cada programa — TechClean nunca borra archivos de otros programas a mano.

### Sobre Componentes — límites honestos
- La **temperatura de CPU** no tiene una API pública y universal en Windows.
  Se intenta leer vía el sensor ACPI estándar, disponible en varias laptops
  pero no en todos los equipos ni en la mayoría de PCs de escritorio.
- La **temperatura/VRAM/ventilador de GPU** en vivo solo están disponibles
  para GPUs NVIDIA (vía `nvidia-smi`). En AMD/Intel se muestra el nombre,
  no esas métricas en vivo.
- El **detalle de RAM/placa madre/BIOS** se lee una sola vez y se cachea.

### Historial — transparencia
El comando/API técnica exacta solo aparece en la Edición Administrador —
en la edición cliente el resultado se muestra en lenguaje simple, tanto en
pantalla como en el `.txt` exportado.

### Widget flotante
Ve a **Segundo Plano** → activa "Widget de rendimiento flotante". Barra
pequeña, siempre encima, arrastrable. CPU/RAM/Red cada 1s; GPU cada 4s en
un hilo aparte para no afectar el rendimiento mientras juegas.

### Bandeja del sistema
Cerrar con la X **no cierra la app**: se minimiza a la bandeja. Clic derecho
ahí: abrir el panel, mostrar/ocultar el widget, activar/desactivar Modo
Juego, o salir de verdad.

### Inicio automático con Windows
En **Ajustes**, activa "Iniciar TechClean con Windows" — se abre solo,
minimizada, cada vez que enciendas el equipo. Usa `HKCU\...\Run`; no
requiere administrador. Funciona igual en código fuente y en el `.exe`.

### Easter egg 🪿
En **Ajustes**, 5 clics seguidos sobre el crédito del desarrollador.

---

## 5. Compatibilidad Windows 10 y 11

`wmic` está siendo **retirada por Microsoft de Windows 11** (deshabilitada
por defecto desde 24H2, eliminada del todo en 25H2 en adelante). TechClean
Pro usa **PowerShell + CIM** (`Get-CimInstance`), el reemplazo oficial, que
funciona igual en Windows 10 y en todas las versiones de Windows 11. También
se corrige la detección de versión cuando el registro dice "Windows 10" en
un equipo que ya corre Windows 11 (se verifica el build number real).

---

## 6. Convertirla en un .exe independiente (manual, opcional)

`Generar_App_Instalable.bat` ya hace esto por ti (y genera los dos idiomas
de una pasada). Si prefieres hacerlo a mano:

```
pip install pyinstaller

REM Edición cliente — el idioma sale de build_config.py, así que hay que
REM cambiarlo entre una compilación y la otra (IDIOMA = "es" / "en").
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_ES" --add-data "assets;assets" main.py

REM Edición administrador
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_Admin" --add-data "assets;assets" main_admin.py
```

---

## 7. Limitaciones honestas (para que no haya sorpresas)

- **Entrar a la BIOS sin reiniciar es físicamente imposible** — corre antes
  de que el sistema operativo cargue. El botón reinicia directo al menú.
- "Liberar RAM" compacta la que los procesos tienen reservada pero no usan
  — no crea memoria de la nada. Misma técnica que herramientas profesionales.
- El **% de uso de GPU en vivo** solo con NVIDIA (`nvidia-smi`).
- La **temperatura de CPU** no siempre está disponible — depende del equipo.
- El "Modo Juego" detecta pantalla completa con una **heurística simple** —
  no distingue juego de video/presentación. Intencionalmente conservador:
  solo sube prioridad de CPU, nunca cierra ni limita otros procesos.
- **Reparar** (sfc/DISM/red) necesita permisos de administrador para
  completarse de verdad; sin ellos, la app te lo dice en el resultado en
  vez de fingir que funcionó.
- Borrar historial de navegador es **irreversible**; exige cerrarlo antes.
- Desinstalar un programa abre su desinstalador oficial — completar el
  proceso depende de esa ventana, TechClean no controla lo que pasa
  dentro de ella.

---

## 8. Novedades y correcciones de la versión 1.5.0

**Nuevo en esta versión, lo más grande:**

- **↩ Deshacer.** La app ahora guarda cómo estaba cada cosa ANTES de tocarla,
  y en el Historial hay una pestaña para revertir: perfil de energía, apps de
  inicio, servicios, efectos visuales, Inicio rápido, arranque automático y
  limpieza programada. Y dice bien claro, arriba de la lista, **lo que no se
  puede deshacer** — los temporales borrados no vuelven, ni la papelera, ni
  el caché del navegador. Un botón que a veces no funciona es peor que no
  tenerlo.
- **🧰 Herramientas de técnico** en la Edición Administrador: foto del sistema
  antes/después, inspector del arranque completo y grabación de métricas a
  CSV. Ver la sección 1.
- **Instalador de verdad** (necesita Inno Setup, gratis): Archivos de
  programa, Agregar o quitar programas, y desinstalación limpia.

---

**Cambio de nombre:** la app pasa de llamarse *TechClean Pro* a **TechClean**.
Al actualizar, tus preferencias se traen solas de la carpeta anterior (widget,
perfil de energía, umbrales, idioma) y la tarea de inicio automático se
reemplaza sin dejar la vieja suelta.

**También en la 1.5.0 — tercera pasada, inspección completa:**

**Nuevo:**
- **El historial ya no se pierde al cerrar la app.** Se guarda en
  `%APPDATA%\TechClean` y la pantalla de Historial tiene un selector entre
  "Esta sesión" y "Todo el historial", con su propio resumen: cuántas
  acciones, en cuántas sesiones, cuánto espacio liberado y desde cuándo. Hay
  botón para borrarlo, y se recorta solo a las 3000 acciones más recientes.
- **Versión que arranca en medio segundo** (`Generar_App_Rapida.bat`) — ver
  la sección 0.

**Corregido:**
- **La app no arrancaba con Windows.** La tarea se creaba y se veía
  habilitada, pero `schtasks` le ponía por su cuenta "no iniciar si el equipo
  va con batería": en un portátil sin enchufar no arrancaba nunca, sin ningún
  error. Ahora la tarea se define por XML, con 30 s de retraso tras iniciar
  sesión y sin límite de ejecución. Si ya tenías una tarea creada por la
  versión anterior, Ajustes lo detecta y te ofrece un botón para rehacerla.
- **El overlay de FPS mandaba a la Microsoft Store.** Usaba un protocolo que
  las versiones nuevas de Xbox Game Bar ya no registran — y `os.startfile`
  con un protocolo sin registrar no da error: Windows da la llamada por buena
  y abre la tienda. Ahora se mira el registro antes de abrir nada.
- **`RuntimeError: main thread is not in main loop`** al abrir la app. Había
  89 sitios que podían provocarlo. Corregido en un solo punto, no en los 89.
- **Reiniciar el Explorador** podía dejarte sin barra de tareas y decirte que
  todo había ido bien. Ahora comprueba que el proceso vuelva de verdad.
- **Limpiar la caché del navegador** informaba como "espacio liberado" el
  tamaño medido ANTES de borrar, pasara lo que pasara después. Ahora se mide
  después y se informa lo que se liberó de verdad.
- Quitar la limpieza programada apagaba el interruptor aunque la tarea
  siguiera ejecutándose sola cada día.
- Reducir animaciones, vaciar la caché DNS y las notificaciones daban por
  hecho el éxito sin comprobarlo — y de las notificaciones dependen las
  alertas de temperatura de CPU.
- Apagar, reiniciar y entrar a la BIOS asomaban una consola negra justo antes
  de que la pantalla se fuera.
- **Entrar y salir de Componentes deprisa dejaba bucles de refresco
  acumulados**, cada uno consultando el sistema cada pocos segundos, para
  siempre.

---

**También en la 1.5.0 — segunda pasada de revisión:**

**Nuevo:**
- **La temperatura del CPU ahora funciona en muchos más equipos.** Solo se
  consultaba el sensor ACPI clásico, que un montón de portátiles no
  publican — en el del desarrollador, por ejemplo, no devuelve nada. Se
  añadió una segunda fuente (el contador de zonas térmicas de Windows), y
  con eso aparece la temperatura donde antes decía "No disponible en este
  equipo". Eso reactiva de golpe la tarjeta de temperatura, su gráfica, la
  fila del widget flotante y la alerta de temperatura de Ajustes.
- Vaciar la papelera ahora **dice cuánto liberó** ("340 elementos, 1.2 GB")
  en vez de un simple "listo", y avisa aparte cuando ya estaba vacía.

**Corregido:**
- **Modo Juego le subía la prioridad al Explorador de Windows.** Daba por
  "juego a pantalla completa" a cualquier ventana del tamaño de la
  pantalla, y eso incluye el ESCRITORIO (al minimizar todo) y cualquier
  ventana maximizada — Windows les da unos píxeles de más. Ahora se exige
  que la ventana no tenga barra de título, que no sea del sistema, y que
  cubra el monitor en el que está (no el principal).
- **Vaciar la papelera congelaba la aplicación.** La llamada de Windows no
  vuelve hasta haber borrado todo, y se hacía en el hilo de la interfaz:
  con una papelera grande, la ventana se quedaba tiesa y Windows la
  marcaba como "No responde".
- Vaciar la papelera decía "✅ hecho" aunque Windows se hubiera negado: no
  se miraba el resultado de la llamada.
- Cuatro sitios más escribían resultados en la pantalla **desde su hilo de
  trabajo**, sin comprobar que el widget siguiera vivo. Si cambiabas de
  pantalla mientras la tarea corría, el resultado se perdía en silencio.
- Reducir animaciones también bloqueaba la ventana: avisa del cambio a
  todas las ventanas abiertas del escritorio y espera respuesta de cada una.
- **El widget flotante pegaba un salto al arrastrarlo** si lo agarrabas por
  cualquier sitio que no fuera el borde superior.
- El widget se podía arrastrar **fuera de la pantalla**, y como no tiene
  barra de título de Windows, ya no había forma de recuperarlo.
- El widget pintaba la temperatura con los umbrales de un porcentaje: 62 °C
  —normal— salía en ámbar como si algo fuera mal.
- Los globos de ayuda del widget son ventanas aparte: al ocultar el widget
  con uno abierto, el globito se quedaba flotando solo en el escritorio.
- Oculto, el widget seguía consultando GPU y temperatura y repintándose
  cada segundo. Ahora se calla hasta que vuelve.
- Al reaparecer, el widget marcaba un pico de red falso de miles de KB/s
  (dividía todo el tráfico acumulado mientras estuvo oculto entre 1 segundo).
- **Las preferencias se leían del disco en cada consulta**, y el widget
  consulta una vez por segundo: una lectura y un parseo de JSON por
  segundo, para siempre, en el hilo de la interfaz. Ahora van en caché y
  solo se releen si el archivo cambió — 5 veces más rápido.
- Guardar preferencias vaciaba el archivo antes de escribirlo: un corte a
  mitad dejaba `preferencias.json` roto y el usuario perdía toda su
  configuración sin ningún aviso. Ahora la escritura es atómica.
- El widget escribía preferencias en **cada clic**, aunque no lo movieras.

---

### Primera pasada

**Nuevo:**
- **Prueba de velocidad de internet rehecha.** Ahora mide también la
  **latencia** (ping) y enseña la velocidad **en vivo** mientras corre, con
  una aguja de escala logarítmica: una conexión de 6 Mbps se lee igual de
  bien que una de fibra, cosa que en una escala normal es imposible.
  Latencia, bajada y subida quedan cada una en su tarjeta, y el número
  sube contando en vez de aparecer de golpe.
- **Prueba de sonido con confirmación.** Antes sonaba un tono y ya; si no
  se oía nada, no había forma de saber por qué. Ahora la ventana pregunta
  si lo escuchaste y, si la respuesta es que no, lleva directo al
  mezclador de volumen y al selector de dispositivo de salida. También
  permite probar la bocina izquierda y la derecha por separado, para
  descubrir si una está muerta.
- **Gráficas de línea de tiempo (RAM, CPU, temperatura) rehechas:** el
  valor nuevo entra deslizándose desde la derecha en vez de dar un salto,
  hay rejilla de fondo para leer la altura de un vistazo, degradado bajo la
  línea, punto vivo en la punta y los valores mínimo y máximo del tramo.
- La gráfica de temperatura ya no está siempre en rojo: **el color sigue la
  temperatura real** (verde hasta 65 °C, ámbar hasta 80, rojo por encima).
- Cuando una gráfica no tiene datos lo dice, en vez de quedarse como un
  recuadro vacío sin explicación (pasa en los equipos que no exponen
  temperatura de CPU, que son muchos).

**Corregido:**
- **La subida de la prueba de internet fallaba de forma intermitente.**
  Mandaba siempre 10 MB con un límite de 15 segundos: en una conexión de
  5 Mbps de subida —muy común— esos 10 MB tardan 16 segundos, así que la
  prueba se agotaba por tiempo y la subida salía vacía en una conexión
  perfectamente sana. Ahora se manda primero un sondeo pequeño y con ese
  dato se elige un tamaño que tarde unos 4 segundos en ESA conexión.
- Un fallo en la bajada cortaba la prueba entera y la subida ni se
  intentaba. Ahora cada mitad es independiente y se muestra lo que sí se
  pudo medir.
- El aviso de "tardó demasiado" salía a los 35 segundos, que no alcanzan
  ni para una prueba normal en una conexión modesta, y además se pintaba
  encima de resultados buenos que habían llegado tarde. Corregido.
- Pulsar "Reintentar" mientras un intento anterior seguía vivo dejaba al
  vigilante viejo pintando errores sobre el intento nuevo.
- La prueba de internet consultaba el estado de la ventana **desde el hilo
  de la prueba**. Tkinter no es seguro fuera del hilo principal.
- **El tono de prueba de audio no sonaba en muchos equipos.** Usaba
  `winsound.Beep()`, que no pasa por la tarjeta de sonido: llama al
  generador de tonos del kernel (`beep.sys`), desactivado de fábrica en
  bastantes portátiles. Ningún error, ningún sonido. Ahora se sintetiza un
  WAV en memoria y se reproduce por la salida de audio normal — que además
  es lo que de verdad interesa probar.
- **Las gráficas tenían un ancho fijo de 260 px** mientras el panel que las
  contiene se estira con la ventana: en una pantalla ancha quedaban como un
  bloquecito perdido en medio de un panel enorme y vacío.
- Las gráficas de Inicio eran de anchos distintos entre sí (RAM ocupaba dos
  columnas y CPU una) sin ninguna razón.
- **La pantalla de Inicio no tenía scroll.** Su contenido mide más de
  1000 px de alto, así que en un portátil de 768 px —o en uno de 1080 con
  el escalado de Windows al 125%, que es lo normal de fábrica— las
  gráficas de abajo quedaban cortadas por el borde de la ventana y no
  había ninguna forma de llegar a ellas.

---

## 9. Novedades y correcciones de la versión 1.4.0

**Nuevo:**
- Ícono propio de la app (ventana, bandeja del sistema y el `.exe` compilado).
- Preferencias que persisten entre sesiones (`preferences.py`): widget
  flotante visible, último perfil de energía, alerta de temperatura y si
  crear punto de restauración antes de reparar — todo en un JSON local en
  `%APPDATA%\TechClean\preferencias.json`.
- Widget flotante ampliado: ahora también muestra temperatura de CPU/GPU
  (cuando el equipo la expone) y tiempo encendido.
- Alertas de temperatura de CPU configurables en Ajustes, con notificación
  nativa de Windows (máximo una cada 10 minutos).
- Punto de restauración automático (opcional) antes de sfc/DISM en Reparar.
- Buscar actualizaciones de Windows pendientes (informativo, no instala nada).
- Buscador en tiempo real dentro del Historial.
- Analizador de espacio en disco (top 15 carpetas más pesadas por unidad) en Optimizar.
- Medidor de velocidad de internet (Cloudflare, sin dependencias nuevas) en Componentes.
- Reporte de hardware exportable a `.txt` en Componentes.
- Pestaña "Servicios" en Aplicaciones — inicia/detiene servicios de
  Windows, siempre con confirmación explícita antes de cualquier cambio.
- La Consola Dev de la Edición Administrador ahora también acepta comandos
  escritos (antes era solo de lectura) — usa el mismo motor que el panel
  oculto del cliente.

**Corregido:**
- El switch de "Widget flotante" **nunca podía apagarse** — siempre volvía
  a encenderse solo, y el botón ✕ del widget no avisaba a la app. Corregido.
- `sfc /scannow` respeta ahora el resultado real (antes decía "listo"
  aunque fallara por falta de permisos).

---

## 10. Correcciones de la versión 1.3.0

- El autopiloto (y ahora Modo Juego) llamaban a la función que registra
  acciones **desde su propio hilo de fondo**, tocando directamente la
  Consola Dev — inseguro en Tkinter y causa de fallos intermitentes.
  Corregido: todo el registro se agenda ahora en el hilo principal.
- `sfc /scannow` y la reparación de red siempre reportaban "éxito" aunque
  fallaran por falta de permisos — ahora respetan el resultado real.
- La barra lateral no cabía ya con tantas secciones — ahora tiene scroll,
  y su limpieza dejó de depender de un método que, con scroll activado,
  podía no encontrar los botones reales.
- Si se navegaba fuera de "Aplicaciones" o "Reparar" mientras algo seguía
  cargando en segundo plano (lista de programas, sfc, DISM...), el
  resultado tardío podía intentar tocar un widget ya destruido. Corregido
  con verificaciones de existencia antes de actualizar cualquier widget.

### De la versión 1.2.0
- `wmic` reemplazado por PowerShell/CIM — corrige fallos en Windows 11
  24H2/25H2 en adelante, donde `wmic` ya no existe por defecto.
- Corregida la detección de "Windows 10" vs "Windows 11".
- El inicio automático con Windows nunca abría minimizado — corregido.
- La ruta guardada para el inicio automático quedaba mal formada en la
  versión compilada (.exe) — corregido.
- `relaunch_as_admin` pasaba la ruta del propio ejecutable como argumento
  — corregido.
- El modo automático podía compactar la RAM del propio juego priorizado
  — ahora lo excluye.
- El Historial ocultaba el comando técnico en pantalla para el cliente
  pero el `.txt` exportado lo seguía incluyendo — corregido.

---

## 11. Estructura del proyecto

```
main.py              → interfaz gráfica + edición cliente
main_admin.py           → lanzador de la edición administrador (reutiliza main.py)
idiomas.py                 → todos los textos de la app en español e inglés
build_config.py               → idioma de esta compilación (lo reescribe el .bat)
system_monitor.py          → CPU/RAM/GPU/disco/red/batería/componentes/info del sistema
optimizer.py                   → RAM, temporales, papelera, DNS, BIOS, inicio automático,
                                   perfiles de energía, reparación, limpieza programada,
                                   gestor de inicio, desinstalador, servicios, speedtest,
                                   notificaciones, punto de restauración, espacio en disco
preferences.py                     → preferencias del usuario entre sesiones (JSON local)
privacy.py                            → detección y limpieza de navegadores
report.py                                → registro transparente de sesión
autopilot.py                                → motor de Modo Juego (RAM + impulso + energía)
tray.py                                        → icono en la bandeja del sistema
widget.py                                         → barra de rendimiento flotante
assets/icono.ico                                     → ícono de la app (ventana, bandeja, .exe)
assets/honk.wav                                         → sonido del easter egg
herramientas/                                              → verificaciones (ver abajo)
```

### Herramientas de verificación

Antes de dar un cambio por terminado, doble clic en
**`herramientas\Verificar_Todo.bat`**: corre las 26 comprobaciones seguidas
y espera una tecla al final para que puedas leer los resultados. Al terminar
dice cuántas pasaron y cuántas no — antes solo imprimía "revisa arriba", y
una comprobación que ni llegaba a arrancar no se distinguía de una que
pasaba.

| Herramienta | Qué comprueba |
|---|---|
| `auditoria.py` | Métodos duplicados y referencias rotas entre módulos |
| `verificar_idiomas.py` | Que español e inglés tengan las mismas claves y los mismos `{campos}` |
| `revisar_hilos.py` | Que nadie toque la interfaz desde un hilo de fondo sin pasar por `after(0, ...)` |
| `revisar_claves.py` | Que toda clave que lee la interfaz la escriba algún módulo de datos |
| `revisar_ajustes.py` | Que cambiar un ajuste surta efecto sin reiniciar la app |
| `revisar_lecturas.py` | Ejecuta las ~30 consultas de solo lectura y revisa tipo, claves y cuánto tardan |
| `revisar_comandos.py` | Que los 25 comandos del panel oculto existan, naveguen y aguanten entrada rara |
| `prueba_consola.py` | La consola entera: historial con las flechas, completar con Tab, tope de líneas, un color por tipo de línea, y que no quede ni una frase escrita a mano sin traducir |
| `revisar_pantallas.py` | Abre las 16 pantallas, pulsa cada pestaña y repinta con datos vacíos o a medias |
| `prueba_arranque.py` | Que la app abra y que las 16 pantallas se pinten, en el idioma que le pases |
| `prueba_ediciones.py` | Qué opciones ve cada edición (cliente vs admin) |
| `prueba_animacion.py` | Que las barras, gráficas, aguja y tarjetas animen sin reventar |
| `prueba_widget.py` | Widget flotante: arrastre, límites de pantalla, tooltips, colores, esquinas redondeadas, respuesta al ratón, que los números no muevan la barra, no trabajar oculto |
| `prueba_bucles.py` | Que entrar y salir de una pantalla deprisa no deje bucles de refresco acumulados |
| `prueba_hilos_interfaz.py` | El puente hilo→interfaz, antes de que arranque la app y después de cerrarla |
| `prueba_historial.py` | Que el historial sobreviva al cierre y aguante una línea corrupta |
| `prueba_modo_juego.py` | Que el escritorio y una ventana maximizada NO se tomen por un juego |
| `prueba_limpieza_temp.py` | Que limpiar temporales no borre la propia app |
| `prueba_velocidad.py` | Que la prueba de internet devuelva latencia, bajada **y** subida |
| `prueba_deshacer.py` | Que deshacer llame a la función inversa correcta, y que algo ya deshecho no se pueda deshacer dos veces |
| `prueba_tecnico.py` | Foto antes/después (que sepa que subir no siempre es mejor), inspector de arranque y grabación a CSV |
| `revisar_instalador.py` | Que el script del instalador no mienta: archivos, versión y nombres de las tareas que borra |
| `revisar_empaquetado.py` | Que los `.exe` ya compilados lleven dentro todo lo que la app importa. Un módulo que PyInstaller deje fuera funciona perfectamente desde el código y falla solo en la copia que se reparte |

Los `.py` sueltos también se pueden correr desde una terminal
(`python herramientas\auditoria.py`). Al hacerles doble clic la ventana se
cierra sola en cuanto terminan, porque imprimen y salen — para eso está el
`.bat`.

---

## 12. Licencia y autoría

TechClean es **gratis** pero **no** es de dominio público ni de código
abierto. Copyright © 2026 Edwin Javier Cortez Cardoza (Hades). Todos los
derechos reservados.

El código está publicado a propósito: esta app toca partes sensibles del
sistema (procesos, registro, servicios), y poder revisar exactamente qué
hace es parte de la idea. Que se pueda **leer** no significa que se pueda
**redistribuir**.

| | |
|---|---|
| Usar la app gratis, donde quieras | Sí |
| Leer y estudiar el código | Sí |
| Compilar tu propia copia para uso personal | Sí |
| Compartir el enlace a este repositorio | Sí |
| Redistribuirla como archivo propio | No, sin permiso |
| Publicarla como tuya, con o sin cambios | No |
| Venderla o cobrar por ella | No |
| Reutilizar el código en otro proyecto | No, sin permiso |

El detalle completo está en [LICENSE.md](LICENSE.md), en español e inglés.
Si querés hacer algo de la lista de "no", escribí y hablamos — la respuesta
puede perfectamente ser que sí.

**Sin garantía.** El software se entrega tal cual. El autor no se hace
responsable de daños ni pérdida de datos derivados de su uso.
