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

**`compilar\Generar_App_Instalable.bat`**

Ese archivo hace todo el trabajo una sola vez (instala lo necesario y
compila la app) y al final te deja **dos** archivos en la carpeta principal:

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
recompilar el `.exe` cada vez, usa `Iniciar.bat` en su lugar.

### ¿Y si quieres que abra más rápido?

El `.exe` de un solo archivo lleva la app comprimida dentro, y Windows tiene
que descomprimir 22 MB en una carpeta temporal **cada vez** que lo abres,
antes de que aparezca nada. Medido en el equipo de desarrollo: **3.7
segundos**.

`compilar\Generar_App_Rapida.bat` compila la misma app en modo carpeta, sin nada que
descomprimir: **0.5 segundos**. El costo es que en vez de un archivo suelto
es una carpeta con muchos archivos dentro (el script deja también los `.zip`
listos para repartir).

Para usarla a diario en tu propio equipo, esa es la buena. El `.exe` único
sigue existiendo porque es más cómodo de descargar y de pasarle a alguien.

### ¿Y un instalador normal?

También hay uno. `compilar\Compilar_Instalador.bat` genera un instalador
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
repositorio y puedes generar tu propio `.exe` con `compilar\Generar_App_Instalable.bat`,
o correr la app directamente con `Iniciar.bat`.

El resto de este documento explica el paso a paso manual y el detalle
técnico de cada sección, por si lo necesitas.

---

## 1. Dos ediciones: Cliente y Administrador

TechClean se genera en **dos aplicaciones separadas**, a partir del
mismo código:

| | Edición Cliente | Edición Administrador |
|---|---|---|
| Archivo fuente | `codigo/main.py` | `codigo/main_admin.py` |
| Script para generar el `.exe` | `compilar/Generar_App_Instalable.bat` | `compilar/Generar_App_Admin.bat` |
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

Una pestaña **🧰 Técnico** con herramientas pensadas para quien arregla
computadoras ajenas. Desde la 1.8.0, lo que se marca con ★ también está en
la edición cliente, explicado en lenguaje sencillo (Componentes, Reparar,
Aplicaciones y Drivers):

- **📸 Antes y después** — guarda cómo está el equipo, optimizas, y te
  muestra la diferencia campo por campo. Para enseñarle a quien te pidió el
  favor qué cambió, en vez de decir "quedó mejor".
- **🚀 Arranque completo** ★ — todo lo que se inicia con Windows en una lista:
  el registro del usuario y el de la máquina (incluida la clave de 32 bits,
  que casi nadie revisa), las dos carpetas Inicio, y las tareas programadas.
- **📈 Grabar métricas** — apunta CPU, RAM, disco y temperatura a un CSV cada
  pocos segundos. Para el caso de "a veces se pone lento y no sé por qué":
  lo dejas grabando, usas el equipo, y después buscas el pico en Excel.
- **📄 Informe para el cliente** (1.6.0) — el antes y el después, el trabajo
  hecho y el estado del hardware, en HTML listo para imprimir o guardar como
  PDF.
- **🔧 Mantenimiento completo** (1.6.0) — punto de restauración, RAM,
  temporales, limpieza a fondo, DNS, sfc/DISM opcional y optimizar discos, en
  orden, con foto antes/después y el informe al final.
- **🩺 Salud del equipo** ★ (1.6.0) — desgaste y temperatura de los discos,
  capacidad de la batería, pantallazos azules y apagados inesperados.
- **📦 Respaldo de controladores** ★ (1.6.0) — exportarlos antes de formatear y
  reinstalarlos después, sin buscarlos uno por uno.

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
├── Iniciar.bat                  ← doble clic: abre la edición cliente sin compilar
├── Iniciar_Admin.bat            ← doble clic: abre la edición admin sin compilar
├── README.md
├── LICENSE.md
├── requirements.txt
├── codigo/                      ← el programa
│   ├── main.py                  ← app + edición cliente
│   ├── main_admin.py            ← lanzador de la edición administrador
│   ├── idiomas.py               ← todos los textos, en español e inglés
│   ├── optimizer.py · system_monitor.py · widget.py · tray.py · ...
│   ├── rutas.py                 ← dónde está assets/, desde el código o compilada
│   └── build_config.py          ← idioma de esta compilación (lo reescribe el .bat)
├── compilar/                    ← todo lo que genera ejecutables
│   ├── Generar_App_Instalable.bat   ← genera TechClean_ES.exe y _EN.exe
│   ├── Generar_App_Rapida.bat       ← la misma app, pero abre en medio segundo
│   ├── Generar_App_Admin.bat        ← genera TechClean_Admin.exe
│   ├── Compilar_Instalador.bat      ← instalador de Windows (necesita Inno Setup)
│   └── TechClean.iss
├── documentacion/               ← contexto del proyecto y notas de cada versión
├── herramientas/                ← el banco de comprobaciones (ver sección 14)
└── assets/                      ← icono y sonido
```

Los `.exe` que generan los scripts de `compilar/` aparecen en la carpeta
principal, junto a `Iniciar.bat`, para que no haya que buscarlos.

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
python codigo\main.py
```
(o `python codigo\main_admin.py` para la edición administrador — o, sin
terminal, doble clic en `Iniciar.bat` / `Iniciar_Admin.bat`)

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
| `/ramprofunda` | Liberación profunda de RAM (también vacía la caché en espera) |
| `/autoram` | Enciende o apaga la liberación automática de RAM |
| `/fondo` | Limpieza a fondo (restos de Windows Update, informes de errores...) |
| `/fugas` | Programas con posible fuga de memoria |
| `/procesos` | Los 10 procesos que más RAM usan |
| `/discos` | Salud de los discos |
| `/bateria` | Salud de la batería |
| `/pantallazos` | Pantallazos azules y apagados inesperados |
| `/unidades` | Discos con su tipo (SSD/HDD) y espacio libre |
| `/medirdns` | Mide la velocidad de tu DNS y de los públicos |
| `/plan` | Plan de energía activo |
| `/red` | Conexiones activas con su IP y DNS |
| `/tecnico` | Abre Herramientas de técnico (solo edición Administrador) |
| `/wifi` | Analiza tu Wi-Fi: señal, banda, canal y redes vecinas |
| `/disco` | Velocidad real del disco (escribe 256 MB temporales y los borra) |
| `/extensiones` | Revisa las extensiones de todos tus navegadores |
| `/accesos` | Accesos directos rotos del Escritorio y del menú Inicio |
| `/encendido` | Cuántos días lleva el equipo sin reiniciarse |
| `/buscar` | Abre el buscador de funciones (también con Ctrl+K) |

Repite los 7 clics para ocultarlo de nuevo.

---

## 4. Qué hace cada apartado

| Apartado | Qué hace realmente |
|---|---|
| **Inicio** | La salud del equipo (0-100) con lo que conviene arreglar, y RAM, CPU, disco y GPU en vivo, con "Optimización con un clic" arriba |
| **Componentes** | CPU por núcleo, frecuencia y temperatura; GPU de **cualquier marca** con uso, memoria y temperatura; RAM por módulo; **salud de los discos** (en los NVMe, sin administrador) y **de la batería**; red, placa base y BIOS; **medidor de velocidad de internet**; reporte de hardware exportable. Desde aquí, **Drivers** (dispositivos con problemas, copia de seguridad de drivers, actualizaciones) |
| **Optimizar** | RAM, temporales, papelera, **perfiles de energía**, optimizar unidades y **Espacio en disco**: análisis de la unidad entera carpeta a carpeta, archivos grandes, instaladores viejos, cachés, limpieza a fondo, duplicados y accesos rotos |
| **Reparar** | **Diagnóstico de fallos** (pantallazos azules, apagados inesperados, apps que se cierran solas y avisos del disco de los últimos 30 días), sfc, DISM, reparar red, DNS más rápido, revisar disco y **puntos de restauración** |
| **Energía** | Estado de la batería, **qué apps gastan más energía** (como administrador) y reiniciar directo a la BIOS |
| **Seguridad** | **Estado de la protección** (antivirus, cortafuegos, arranque seguro, control de cuentas), **secuestros** del navegador o de la conexión, Defender, auditoría de malware, extensiones del navegador, programas en la red, permisos de apps, cortafuegos y cuentas de usuario |
| **Privacidad** | **Qué apps usaron tu cámara, micrófono y ubicación** y cuándo; historial y caché de navegadores; ajustes de privacidad de Windows |
| **Aplicaciones** | **Todo lo que arranca con Windows** (activar/desactivar como el Administrador de tareas, con deshacer), desinstalar programas, apps de serie, servicios, actualizar apps (winget) y tareas programadas |
| **Gaming** | Modo Juego (también **automático por juego**), **frenar lo que acapara la CPU** mientras juegas, cerrar apps al jugar, ajustes de Windows para juegos, lag, **bufferbloat** y Wi-Fi |
| **Segundo Plano** | Widget flotante, limpieza programada y un resumen de **todo lo que TechClean hace sola** |
| **Historial** | Cada acción ejecutada y su resultado — exportable a `.txt`, con buscador; y lo que se puede deshacer |
| **Ajustes** | Apariencia (9 temas), inicio con Windows, memoria automática, atajo de teclado, avisos, bandeja y widget, diagnóstico y configuración |

### Perfiles de energía
En **Optimizar**, tres botones cambian el plan de energía de Windows:
Silencioso (ahorro), Equilibrado (uso diario) y Rendimiento (máxima
velocidad). Usan los planes que Windows trae por defecto — si tu equipo no
los tiene (algunos fabricantes los quitan), se buscan por nombre como
respaldo.

### Modo Juego (estilo AMD Adrenaline)
En **Gaming**, actívalo y hace todo esto junto:
1. Cambia el plan de energía a Rendimiento.
2. Cada 8 segundos (bajo consumo, no en bucle continuo) busca el juego y le
   sube la prioridad de CPU sin tocarlo de ninguna otra forma. Cuenta como
   juego lo que está a pantalla completa, **salvo** navegadores y
   reproductores de vídeo, y cualquier programa de la carpeta de un juego de
   tu biblioteca (Steam, Epic, GOG) aunque vaya en ventana (1.8.0).
3. Si la RAM pasa del 85%, libera memoria automáticamente **excluyendo
   siempre el juego priorizado**, para no causarle un micro-tirón justo
   mientras se supone que lo protege.
4. Si un programa de fondo se pone a acaparar la CPU durante la partida, le
   **baja la prioridad** (no lo cierra) y se la devuelve al terminar. Nunca
   toca el juego, lo del sistema, el chat de voz ni la grabación. Se apaga
   con su interruptor (1.8.0).

Al desactivarlo, vuelve al plan Equilibrado. Todo queda en el Historial.
En la biblioteca de juegos puedes marcar los que **encienden el Modo Juego
solos** al abrirlos (y lo apagan al cerrarse).

### Limpieza programada automática
En **Segundo Plano**: crea una tarea real en el Programador de
tareas de Windows (diaria o semanal, a la hora que elijas) que libera RAM y limpia
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
- **Inicio de Windows** (1.8.0): todo lo que abre solo con el equipo — el
  registro (tuyo y el de todos los usuarios, también la clave de 32 bits),
  las carpetas de Inicio y las tareas programadas. Se activa y desactiva
  **igual que en el Administrador de tareas**, se puede deshacer, y lo que
  parece sospechoso (o apunta a un programa que ya no existe) sale marcado.
  Desactivar NO desinstala nada — solo deja de abrirse sola.
- **Desinstalar programas**: lee la misma lista que "Programas y
  características" de Windows y ejecuta el desinstalador **oficial** de
  cada programa — TechClean nunca borra archivos de otros programas a mano.

### Sobre Componentes — límites honestos
- La **temperatura de CPU** no tiene una API pública y universal en Windows.
  Se intenta leer vía el sensor ACPI estándar, disponible en varias laptops
  pero no en todos los equipos ni en la mayoría de PCs de escritorio.
- El **uso, la memoria y la temperatura de la GPU** se leen como lo hace el
  Administrador de tareas, para cualquier marca (1.8.0; antes solo NVIDIA).
  La temperatura depende de que el driver la publique.
- La **salud de los discos**: en los NVMe se lee directo del disco, sin
  administrador. En los SATA hace falta abrir TechClean como administrador
  (el `.exe` ya lo pide).
- El **detalle de RAM/placa madre/BIOS** se lee una sola vez y se cachea.

### Historial — transparencia
El comando/API técnica exacta solo aparece en la Edición Administrador —
en la edición cliente el resultado se muestra en lenguaje simple, tanto en
pantalla como en el `.txt` exportado.

**Crear informe (PDF)** (1.8.0) junta en un PDF, en tu Escritorio, cómo
está el equipo, los problemas que se le ven (pantallazos, discos, batería,
protección, malware, drivers...) con qué hacer en cada uno, y lo que hizo
TechClean. Tarda unos 30 segundos y solo lee.

### Widget flotante
Ve a **Segundo Plano** → activa "Widget de rendimiento flotante". Barra
pequeña, siempre encima, arrastrable. CPU/RAM/Red cada 1s; GPU cada 4s en
un hilo aparte para no afectar el rendimiento mientras juegas.

### Bandeja del sistema
Cerrar con la X **no cierra la app**: se minimiza a la bandeja. Clic derecho
ahí: abrir el panel, **liberar RAM** o hacer una **limpieza rápida** sin abrir
la ventana (1.7.0, con una notificación del resultado), mostrar/ocultar el
widget, activar/desactivar Modo Juego, o salir de verdad.

### Inicio automático con Windows
En **Ajustes**, activa "Iniciar TechClean con Windows" — se abre solo,
minimizada, cada vez que enciendas el equipo. Usa `HKCU\...\Run`; no
requiere administrador. Funciona igual en código fuente y en el `.exe`.

### Easter egg 🪿
En **Ajustes**, 5 clics seguidos sobre el crédito del desarrollador.

### Temas (Ajustes → Apariencia)
Nueve temas con su miniatura: Original (los colores de siempre), Pulido (de
fábrica), Telemetría, Claro, Negro puro (OLED), Bosque, Terminal retro,
Sakura y Alto contraste (todo un 12 % más grande y con bordes marcados). El
cambio es al instante. Los temas van compilados dentro de la app: no se
descargan ni se leen de archivos, así que nadie los puede cambiar desde fuera.

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

`compilar\Generar_App_Instalable.bat` ya hace esto por ti (y genera los dos idiomas
de una pasada). Si prefieres hacerlo a mano:

```
pip install pyinstaller

REM Desde la carpeta principal del proyecto.
REM Edición cliente — el idioma sale de codigo\build_config.py, así que hay que
REM cambiarlo entre una compilación y la otra (IDIOMA = "es" / "en").
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_ES" --add-data "assets;assets" --paths codigo codigo\main.py

REM Edición administrador
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_Admin" --add-data "assets;assets" --paths codigo codigo\main_admin.py
```

---

## 7. Limitaciones honestas (para que no haya sorpresas)

- **Entrar a la BIOS sin reiniciar es físicamente imposible** — corre antes
  de que el sistema operativo cargue. El botón reinicia directo al menú.
- "Liberar RAM" compacta la que los procesos tienen reservada pero no usan
  — no crea memoria de la nada. Misma técnica que herramientas profesionales.
- El **consumo de energía por app** lo da Windows solo a un administrador.
- **Espacio en disco** recorre la unidad entera (unos 15-25 s para un disco
  de 300 GB). No lee la tabla interna del disco (MFT) como WizTree: sería
  más rápido, pero no se pudo comprobar que leyera bien todos los casos.
- La **temperatura de CPU** no siempre está disponible — depende del equipo.
- El "Modo Juego" reconoce un juego por estar a pantalla completa (salvo
  navegadores y reproductores) o por vivir en la carpeta de un juego de tu
  biblioteca: un programa raro a pantalla completa puede contar como juego.
  Es conservador: sube la prioridad del juego y, si lo dejas encendido,
  baja la de lo que acapare la CPU; nunca cierra nada (salvo las apps que
  tú marques para cerrar al jugar).
- **Reparar** (sfc/DISM/red) necesita permisos de administrador para
  completarse de verdad; sin ellos, la app te lo dice en el resultado en
  vez de fingir que funcionó.
- Borrar historial de navegador es **irreversible**; exige cerrarlo antes.
- Desinstalar un programa abre su desinstalador oficial — completar el
  proceso depende de esa ventana, TechClean no controla lo que pasa
  dentro de ella.

---

## 8. Novedades y correcciones de la versión 1.8.0

**Otra cara, mucho más profunda, e igual de ligera:**

- **🎨 Temas** (Ajustes → Apariencia): Original, Pulido (de fábrica),
  Telemetría, Claro, Negro puro (OLED), Bosque, Terminal retro, Sakura y
  Alto contraste. Cambian al instante, sin reiniciar. Van dentro de la app:
  no se descarga nada y no se pueden cambiar desde fuera (en preferencias
  solo se guarda el nombre; uno que no existe cae en el de fábrica).
- **🧭 Todas las pantallas rediseñadas:** barra lateral agrupada con iconos
  de línea, tarjetas, y cada opción explicada en su fila.
- **📄 Informe del equipo en PDF** (Historial → Crear informe): cómo está el
  equipo, los problemas que se le ven con qué hacer en cada uno, y lo que
  hizo TechClean, con la cara de la app. Solo lee; lo imprime Edge, que viene
  con Windows.
- **🔐 Privacidad de la app** (Ajustes → Privacidad y `PRIVACIDAD.md`): qué
  guarda (solo en tu equipo), cuándo se conecta a internet y qué no hace.
- **🎯 Ajusta TechClean a tu equipo** (Inicio, y luego Ajustes): mira la
  RAM, el procesador, si es portátil y tus juegos, y propone qué funciones
  dejar encendidas y cuáles apagadas, cada una con su porqué. No cambia nada
  sin que lo apruebes.
- **🐞 Reportar un problema** (Ajustes, o *Enviar este error* cuando algo
  falla): el error y cómo es el equipo, sin el nombre de usuario ni las
  carpetas, listo para publicarlo en GitHub o copiarlo. La app no lo envía:
  lo publica quien lo reporta.
- **💽 Espacio en disco** analiza la unidad entera en segundos (antes, solo
  dos niveles de carpetas): carpeta a carpeta, reparto por tipo de archivo y
  los archivos más grandes. Solo ofrece la papelera para lo tuyo, nunca para
  archivos de Windows, programas o juegos.
- **🔍 Reparar → Diagnóstico de fallos:** pantallazos azules (aunque Windows
  no guardara el informe), apagados inesperados (también durante la
  suspensión), apps que se cierran solas y avisos del disco.
- **🩺 Componentes:** salud del disco y de la batería, uso por núcleo y la GPU
  de cualquier marca. Antes, solo en la edición Admin o solo con NVIDIA.
- **🚀 Aplicaciones → Inicio de Windows** completo (registro, carpetas y
  tareas), con deshacer y lo sospechoso marcado.
- **🛡 Seguridad → Protección:** antivirus, cortafuegos, arranque seguro y
  control de cuentas, y si te secuestraron el navegador o la conexión
  (hosts, proxy, DNS, certificados, directivas).
- **🔐 Privacidad:** qué apps usaron tu cámara, micrófono y ubicación.
- **🎮 Gaming:** Modo Juego automático por juego, frenar lo que acapara la
  CPU y la prueba de bufferbloat.
- **🔋 Energía:** batería y qué apps gastan más.
- **📦 Drivers:** copia de seguridad y reinstalación en la edición cliente.
- **👀 Segundo plano:** todo lo que la app hace sola, de un vistazo.
- **⚡ Listas que ya no congelan la ventana:** carpetas del disco,
  programas, servicios o un Historial con miles de acciones, al momento.
- **Igual de ligera** (medido contra la 1.7.0; ver las notas de la release).

**Errores corregidos:**

- **Servicios mostraba TODOS los servicios como detenidos** (Windows
  PowerShell entrega el estado como número).
- **Tildes rotas** ("Optimizaci¢n") en todo lo que venía de PowerShell.
- **La papelera daba por enviados** archivos que no se habían movido.
- **Una copia de drivers fallida** se quedaba en "Trabajando..." para siempre.
- **Textos cortados por los dos lados** con la ventana a su tamaño de fábrica
  o el zoom de Windows al 125 %.
- **Componentes seguía consultando el sistema con la pantalla cerrada.**
- Y otros menores: el interruptor del widget, la limpieza programada que no
  se reprogramaba al cambiar la hora, borrar la caché del navegador que
  congelaba la ventana... (lista completa en las notas).

Detalle completo en `documentacion/NOTAS_RELEASE_1.8.0.md`.

---

## 9. Novedades y correcciones de la versión 1.7.0

**Más rápida:**

- **Inicio ya no se traba.** Para medir la CPU, la ventana se quedaba
  esperando 0.3 segundos cada 2 segundos: clics y scroll a tirones el 15 %
  del tiempo. Ahora no espera nada (medido: de 300 ms a 11 ms por refresco).
- **Drivers abre al instante** (de 3.3 s a 0.01 s), y el buscador ya no
  congela la ventana 3 segundos con cada letra.
- **Cambiar de pantalla, un 15-20 % más rápido**: se corrigió un fallo de
  customtkinter que recalculaba la ventana entera cada vez que se movía una
  barra de desplazamiento, y la pantalla vieja se destruye después de dibujar
  la nueva.
- Ligera como siempre: 0.35 % de CPU con la ventana abierta y 0.09 % en la
  bandeja, con todo lo nuevo encendido.

**Nuevo:**

- **🔎 Buscador de funciones (Ctrl+K):** escribes "ram", "wifi", "dns" o
  "drivers" y vas directo. Encuentra con o sin tildes, en español o inglés y
  con faltas de ortografía.
- **🧠 Desde la bandeja:** "Liberar RAM" y "Limpieza rápida" sin abrir la
  ventana, con una notificación del resultado.
- **⌨ Atajo de teclado global** (opcional, en Ajustes): libera RAM desde
  cualquier programa, incluso jugando. Usa `RegisterHotKey` de Windows: no
  es un "gancho" de teclado, así que no ve nada más de lo que escribes.
- **📶 Wi-Fi** (en Gaming): señal en dBm, banda, canal, estándar, velocidad
  del enlace y cuántas redes vecinas comparten tu canal, con un veredicto.
- **🧩 Extensiones del navegador** (Seguridad): Chrome, Edge, Brave, Opera,
  Vivaldi y Firefox, en todos sus perfiles. Marca las cargadas sin pasar por
  la tienda, las forzadas por el registro y las que pueden leer tus datos en
  todas las webs. Las que instala tu escuela o empresa se reconocen como tales.
- **🔗 Accesos directos rotos** (Espacio en disco): los que quedaron al
  desinstalar programas, a la papelera. Los que se abrían al encender el
  equipo salen sin marcar, para revisarlos antes.
- **🔔 Avisos nuevos:** cuando el equipo lleva días sin reiniciarse (con el
  Inicio rápido de Windows, apagar no reinicia) y, opcional, cuando la batería
  llega a su límite de carga.
- **✨ Ventana de novedades** al actualizar, una sola vez.

**Errores corregidos:**

- **La prueba de disco medía la RAM, no el disco.** Leía el archivo que
  acababa de escribir, y Windows lo servía desde la caché: miles de MB/s
  también en un disco mecánico. Ahora usa `FILE_FLAG_NO_BUFFERING`, mide
  también bloques sueltos de 4 KB y dice si rinde como un HDD, un SSD o un NVMe.
- **El Historial sumaba la RAM como "espacio liberado".** Con la liberación
  automática, la cifra llegaba a cientos de GB que nunca fueron disco. Ahora
  van separados, también en lo guardado por versiones anteriores.
- **Importar ajustes aceptaba cualquier cosa:** un archivo con un texto donde
  va un número rompía la app después. Ahora solo se importan ajustes
  conocidos y del tipo correcto.
- **Las fechas de los drivers salían como `/Date(1150848000000)/`.**

Detalle completo en `documentacion/NOTAS_RELEASE_1.7.0.md`.

---

## 10. Novedades y correcciones de la versión 1.6.0

**Lo más grande:**

- **🧠 RAM al nivel de Mem Reduct.** Se libera a nivel de sistema (procesos
  protegidos, caché de archivos, datos pendientes de escribir), no programa
  por programa. Medido: de 38 % a 25 % de RAM en uso. Botón aparte de
  **liberación profunda**, y la **liberación automática funciona de verdad**
  (antes solo con el Modo Juego), con intervalo opcional.
- **🧹 Limpieza a fondo** en Espacio en disco: lo del Liberador de espacio de
  Windows con el tamaño real, más limpiar componentes viejos de Windows
  (DISM). **Duplicados** (siempre queda una copia) y **optimizar unidades**
  (TRIM en SSD, desfragmentar solo en HDD).
- **🎮 Gaming:** cerrar apps al jugar y reabrirlas al salir (opcional, viene
  apagado), ajustes de Windows para juegos con deshacer, medidor de lag
  (¿Wi-Fi o proveedor?), plan Máximo rendimiento y juegos de GOG Galaxy.
- **🔎 Auditoría de seguridad** (pestaña en Seguridad, solo lee): intérpretes
  disfrazados, cosas que arrancan solas con comandos ocultos, mineros,
  exclusiones de Defender. Más **programas en la red** y un **vigilante** que
  avisa de fugas de memoria y discos casi llenos.
- **🔒 Privacidad de Windows:** seis interruptores (publicidad, sugerencias,
  Bing en Inicio...) con deshacer.
- **📦 Aplicaciones:** quitar apps de serie (de una lista conocida) y
  actualizar todas con winget. **🌐 DNS más rápido** con deshacer.
- **🛟 Puntos de restauración** (espacio, crear, borrar los viejos) e
  **informe de energía**.
- **🧰 Edición Administrador:** informe para el cliente, salud de discos y
  batería, pantallazos azules, respaldo de controladores y mantenimiento
  completo. Ver la sección 1.

**Errores corregidos que importan:**

- "Limpiar temporales" podía borrar archivos de **fuera** de %TEMP% a través
  de una unión (junction) de Windows. Comprobado con la 1.5.0.
- "Punto de restauración creado" sin crearlo (límite de 24 h de Windows).
- Minimizada en la bandeja seguía dibujando y lanzando procesos: CPU de
  3.1 % a 1.0 %.
- sfc/DISM podían colgarse; la lista de winget salía vacía en español;
  Steam y Discord no aparecían en la caché de apps; 11 sitios tocaban la
  interfaz desde un hilo; unos 20 textos en español en la build en inglés.

Detalle completo en `documentacion/NOTAS_RELEASE_1.6.0.md`.

---

## 11. Novedades y correcciones de la versión 1.5.0

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
- **Versión que arranca en medio segundo** (`compilar\Generar_App_Rapida.bat`) — ver
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

## 12. Novedades y correcciones de la versión 1.4.0

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

## 13. Correcciones de la versión 1.3.0

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

## 14. Estructura del proyecto

```
codigo/
  main.py            → interfaz gráfica + edición cliente
  main_admin.py      → lanzador de la edición administrador (reutiliza main.py)
  idiomas.py         → todos los textos de la app en español e inglés
  build_config.py    → idioma de esta compilación (lo reescribe el .bat)
  rutas.py           → dónde está assets/, tanto desde el código como compilada
  system_monitor.py  → CPU/RAM/GPU/disco/red/batería/componentes/info del sistema
  optimizer.py       → RAM, temporales, papelera, DNS, BIOS, inicio automático,
                       perfiles de energía, reparación, limpieza programada,
                       gestor de inicio, desinstalador, servicios, speedtest,
                       notificaciones, punto de restauración, espacio en disco
  preferences.py     → preferencias del usuario entre sesiones (JSON local)
  privacy.py         → detección y limpieza de navegadores
  report.py          → registro transparente de sesión
  deshacer.py        → registro de cambios reversibles
  tecnico.py         → herramientas de la edición administrador
  seguridad.py       → auditor de seguridad (solo lee): malware, mineros, red, extensiones
  autopilot.py       → segundo plano: Modo Juego, RAM automática, vigilante (fugas, disco,
                       días sin reiniciar, límite de carga)
  disco.py           → análisis completo de una unidad (8 hilos, solo lee)
  gpu.py             → GPU de cualquier marca (lo mismo que el Administrador de tareas)
  temas.py           → los 9 temas (colores, letra y forma)
  iconos.py          → iconos de línea dibujados con Pillow (sin archivos de imagen)
  tray.py            → icono en la bandeja del sistema
  atajos.py          → atajo de teclado global (RegisterHotKey, sin ganchos de teclado)
  widget.py          → barra de rendimiento flotante
compilar/            → generadores de .exe, instalador y su script de Inno Setup
documentacion/       → CONTEXTO_PROYECTO.md y las notas de cada versión
assets/icono.ico     → ícono de la app (ventana, bandeja, .exe)
assets/honk.wav      → sonido del easter egg
herramientas/        → verificaciones (ver abajo)
```

### Herramientas de verificación

Antes de dar un cambio por terminado, doble clic en
**`herramientas\Verificar_Todo.bat`**: corre las 43 comprobaciones seguidas
y espera una tecla al final para que puedas leer los resultados. Al terminar
dice cuántas pasaron y cuántas no — antes solo imprimía "revisa arriba", y
una comprobación que ni llegaba a arrancar no se distinguía de una que
pasaba.

| Herramienta | Qué comprueba |
|---|---|
| `auditoria.py` | Funciones y métodos definidos dos veces (el segundo pisa al primero sin avisar), referencias rotas entre módulos, nombres que no existen y variables que tapan una función |
| `verificar_idiomas.py` | Que español e inglés tengan las mismas claves y los mismos `{campos}`, y ninguna clave repetida dentro de un idioma |
| `revisar_hilos.py` | Que nadie toque la interfaz desde un hilo de fondo sin pasar por `after(0, ...)` |
| `revisar_claves.py` | Que toda clave que lee la interfaz la escriba algún módulo de datos |
| `revisar_ajustes.py` | Que cambiar un ajuste surta efecto sin reiniciar la app |
| `revisar_lecturas.py` | Ejecuta las ~30 consultas de solo lectura y revisa tipo, claves y cuánto tardan |
| `revisar_comandos.py` | Que los 44 comandos del panel oculto existan, naveguen y aguanten entrada rara |
| `prueba_consola.py` | La consola entera: historial con las flechas, completar con Tab, tope de líneas, un color por tipo de línea, y que no quede ni una frase escrita a mano sin traducir |
| `revisar_pantallas.py` | Abre las 16 pantallas, pulsa cada pestaña y repinta con datos vacíos o a medias |
| `prueba_arranque.py` | Que la app abra y que las 16 pantallas se pinten, en el idioma que le pases |
| `prueba_ediciones.py` | Qué opciones ve cada edición (cliente vs admin) |
| `prueba_animacion.py` | Que las barras, gráficas, aguja y tarjetas animen sin reventar |
| `prueba_widget.py` | Widget flotante: arrastre, límites de pantalla, tooltips, colores, esquinas redondeadas, respuesta al ratón, que los números no muevan la barra, no trabajar oculto |
| `prueba_bucles.py` | Que entrar y salir de una pantalla deprisa no deje bucles de refresco ni consultas de más |
| `prueba_hilos_interfaz.py` | El puente hilo→interfaz, antes de que arranque la app y después de cerrarla |
| `prueba_historial.py` | Que el historial sobreviva al cierre y aguante una línea corrupta |
| `prueba_modo_juego.py` | Que el escritorio y una ventana maximizada NO se tomen por un juego |
| `prueba_limpieza_temp.py` | Que limpiar temporales no borre la propia app |
| `prueba_velocidad.py` | Que la prueba de internet devuelva latencia, bajada **y** subida |
| `prueba_deshacer.py` | Que deshacer llame a la función inversa correcta, y que algo ya deshecho no se pueda deshacer dos veces |
| `prueba_tecnico.py` | Foto antes/después (que sepa que subir no siempre es mejor), inspector de arranque y grabación a CSV |
| `revisar_instalador.py` | Que el script del instalador no mienta: archivos, versión y nombres de las tareas que borra |
| `revisar_empaquetado.py` | Que los `.exe` ya compilados lleven dentro todo lo que la app importa. Un módulo que PyInstaller deje fuera funciona perfectamente desde el código y falla solo en la copia que se reparte |
| `prueba_memoria.py` | Liberación de RAM: estructuras de Windows y, como administrador, que cada paso funcione de verdad |
| `prueba_auto_ram.py` | Liberación automática: umbral con espera, intervalo, y que se aparte con el Modo Juego |
| `prueba_limpieza_fondo.py` | Borrado seguro: no entrar en uniones, no contar lo bloqueado, filtros |
| `prueba_vigilante.py` | Fugas de memoria y disco lleno: qué es y qué no es, sin repetir avisos |
| `prueba_dns_unidades.py` | Consulta DNS contra un servidor de mentira, y que nada raro llegue a PowerShell |
| `prueba_gaming.py` | Cerrar/reabrir apps (nunca el juego), ajustes de juego, lag, juegos de GOG, qué cuenta como juego, Modo Juego automático por juego, frenar lo que acapara la CPU (con un proceso propio, nunca los de verdad) y la nota de bufferbloat |
| `prueba_seguridad.py` | El auditor detecta un malware real y no marca programas legítimos |
| `prueba_apps_sistema.py` | Winget en cualquier idioma, apps de serie, duplicados y puntos de restauración |
| `prueba_rendimiento.py` | Que la ventana no se congele: lecturas del hilo de la interfaz, barras de desplazamiento y la lista de drivers |
| `prueba_wifi_disco.py` | Estructuras de la API de Wi-Fi, veredicto, y que la prueba de disco mida el disco y no la RAM |
| `prueba_extensiones_accesos.py` | Un navegador de mentira con cada tipo de extensión, y accesos directos de verdad (uno roto) |
| `prueba_acciones_rapidas.py` | Buscador Ctrl+K, atajo global (y cuando está ocupado), bandeja, novedades e importar ajustes |
| `prueba_temas.py` | Los 9 temas: contraste de cada texto, que un nombre raro caiga en el de fábrica, ningún color suelto en el código, cambio en caliente, y que el rediseño no vuelva a ser lento (textos que se ajustan una sola vez, letras compartidas, galería que cabe) |
| `prueba_disco.py` | El analizador de disco: totales exactos en una carpeta inventada, que no entre en uniones, descontar lo borrado, cachés de juegos desinstalados y qué se ofrece mandar a la papelera |
| `prueba_diagnostico.py` | Salud NVMe, diagnóstico de fallos (pantallazos, suspensión, volcado sin guardar, NTFS), consumo de energía por app, tildes y estado de los servicios que vienen de PowerShell, copia de drivers |
| `prueba_proteccion.py` | El archivo hosts (bloqueo vs. secuestro), proxy, DNS, certificados, estado de la protección, y activar/desactivar/deshacer lo que arranca con Windows en una clave de registro propia |
| `revisar_errores_banco.py` | Los errores que la app registró mientras corría el banco: una prueba puede decir "ok" aunque dentro haya saltado uno |

Los `.py` sueltos también se pueden correr desde una terminal
(`python herramientas\auditoria.py`). Al hacerles doble clic la ventana se
cierra sola en cuanto terminan, porque imprimen y salen — para eso está el
`.bat`.

---

## 15. Licencia, privacidad y autoría

**Privacidad:** TechClean no recoge ni envía datos tuyos (ni cuentas, ni
anuncios, ni telemetría); lo que guarda se queda en tu equipo. Cuándo se
conecta a internet y qué lee del equipo, en [PRIVACIDAD.md](PRIVACIDAD.md).

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
