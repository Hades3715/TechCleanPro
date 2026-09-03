# TechClean Pro — Panel de Optimización de Sistema

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

---

## 0. La forma más fácil de empezar (recomendada)

No necesitas leer todo este documento para usar la app. Extrae el ZIP y haz
doble clic en:

**`Generar_App_Instalable.bat`**

Ese archivo hace todo el trabajo una sola vez (instala lo necesario y
compila la app) y al final te deja **dos** archivos en la misma carpeta:

- **`TechCleanPro_ES.exe`** — la app en español
- **`TechCleanPro_EN.exe`** — la app en inglés

Quédate con el que quieras usar (o reparte los dos). Ese `.exe` sí lo puedes
mover a tu Escritorio y abrir con doble clic para siempre — no necesitas
Python instalado, ni volver a correr ningún script, ni escribir ningún
comando.

Requisito: tener [Python](https://www.python.org/downloads/) instalado una
vez (marca "Add Python to PATH" al instalarlo). Es solo para generar el
`.exe`; una vez generado, ya no hace falta.

Si mientras seguimos ajustando la app prefieres probar cambios rápido sin
recompilar el `.exe` cada vez, usa `Iniciar_Rapido.bat` en su lugar.

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

TechClean Pro se genera en **dos aplicaciones separadas**, a partir del
mismo código:

| | Edición Cliente | Edición Administrador |
|---|---|---|
| Archivo fuente | `main.py` | `main_admin.py` |
| Script para generar el `.exe` | `Generar_App_Instalable.bat` | `Generar_App_Admin.bat` |
| `.exe` resultante | `TechCleanPro_ES.exe` y `TechCleanPro_EN.exe` | `TechCleanPro_Admin.exe` |
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

## 2. Instalación (paso a paso, sin perderte)

### Paso 1 — Extrae el ZIP
Descarga el archivo `TechCleanPro.zip` y **extráelo completo** (clic derecho →
"Extraer todo...") en una carpeta fácil de recordar, por ejemplo tu Escritorio.

```
TechCleanPro/
├── Generar_App_Instalable.bat   ← doble clic: genera TechCleanPro_ES.exe y _EN.exe
├── Generar_App_Admin.bat        ← doble clic: genera TechCleanPro_Admin.exe
├── Iniciar_Rapido.bat           ← doble clic: prueba la edición cliente sin compilar
├── Iniciar_Rapido_Admin.bat     ← doble clic: prueba la edición admin sin compilar
├── main.py                      ← app + edición cliente
├── main_admin.py                ← lanzador de la edición administrador
├── system_monitor.py
├── optimizer.py
├── privacy.py
├── report.py
├── autopilot.py
├── tray.py
├── widget.py
├── requirements.txt
├── README.md
└── assets/
    └── honk.wav
```

Si solo ves un archivo `.py` suelto, es que no extrajiste el ZIP — todavía está
comprimido. Tiene que quedar la carpeta completa con TODOS los archivos.

### Paso 2 — Instala Python (si no lo tienes)
[python.org/downloads](https://www.python.org/downloads/) — marca **"Add
Python to PATH"** durante la instalación.

### Paso 3 — Abre una terminal EN esa carpeta
Abre la carpeta `TechCleanPro` en el Explorador, clic en la barra de
direcciones, escribe `powershell`, Enter.

Para varias funciones (papelera, RAM, reparación, BIOS) es mejor abrirla como
administrador: clic derecho sobre PowerShell en el menú inicio → "Ejecutar
como administrador", y moverte con `cd` hasta la carpeta:
```
cd $HOME\Desktop\TechCleanPro
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
existe en la interfaz. Al abrirlo, un texto en gris recuerda: *"Escribe
/help o ayuda para ver los comandos disponibles."*

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
Todo con herramientas oficiales de Windows — TechClean Pro no reemplaza
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
  cada programa — TechClean Pro nunca borra archivos de otros programas a mano.

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
En **Ajustes**, activa "Iniciar TechClean Pro con Windows" — se abre solo,
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
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechCleanPro_ES" --add-data "assets;assets" main.py

REM Edición administrador
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechCleanPro_Admin" --add-data "assets;assets" main_admin.py
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
  proceso depende de esa ventana, TechClean Pro no controla lo que pasa
  dentro de ella.

---

## 8. Novedades y correcciones de la versión 1.4.0

**Nuevo:**
- Ícono propio de la app (ventana, bandeja del sistema y el `.exe` compilado).
- Preferencias que persisten entre sesiones (`preferences.py`): widget
  flotante visible, último perfil de energía, alerta de temperatura y si
  crear punto de restauración antes de reparar — todo en un JSON local en
  `%APPDATA%\TechCleanPro\preferencias.json`.
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

## 9. Correcciones de la versión 1.3.0

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

## 10. Estructura del proyecto

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
**`herramientas\Verificar_Todo.bat`**: corre las cinco comprobaciones
seguidas y espera una tecla al final para que puedas leer los resultados.

| Herramienta | Qué comprueba |
|---|---|
| `auditoria.py` | Métodos duplicados y referencias rotas entre módulos |
| `verificar_idiomas.py` | Que español e inglés tengan las mismas claves y los mismos `{campos}` |
| `prueba_arranque.py` | Que la app abra y que las 16 pantallas se pinten, en el idioma que le pases |
| `prueba_ediciones.py` | Qué opciones ve cada edición (cliente vs admin) |
| `prueba_animacion.py` | Que las barras animen y no revienten al destruirlas a media animación |

Los `.py` sueltos también se pueden correr desde una terminal
(`python herramientas\auditoria.py`). Al hacerles doble clic la ventana se
cierra sola en cuanto terminan, porque imprimen y salen — para eso está el
`.bat`.
