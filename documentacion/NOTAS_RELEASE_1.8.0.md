# TechClean 1.8.0

**Otra cara, y mucho más a fondo.** Nueve temas, todas las pantallas
rediseñadas, y TechClean ahora mira el equipo de verdad: el disco entero,
los fallos de los últimos 30 días, la salud de discos y batería, todo lo
que arranca con Windows, si te secuestraron el navegador... Y lo junta en
un **informe en PDF** con la cara de la app.

Si venías de la 1.7.0, tus preferencias y tu historial siguen como estaban.
La app arranca con el tema nuevo de fábrica (**Pulido**); el aspecto de
siempre está en Ajustes → Apariencia como **Original**.

---

## Descarga

| Archivo | Para quién |
|---|---|
| **TechClean_ES.exe** | Si quieres la app en español |
| **TechClean_EN.exe** | If you want the app in English |

Descarga **uno solo**, el que te sirva. No hace falta instalar nada más.

> **Windows te va a avisar la primera vez.** Sale una pantalla azul que dice
> "Windows protegió tu PC". Es porque la app no tiene firma digital (cuesta
> unos cientos de dólares al año y la hace un estudiante). Haz clic en **Más
> información** → **Ejecutar de todas formas**. Para comprobar que el archivo
> es el original, compara su huella SHA-256 con la de abajo (en PowerShell:
> `Get-FileHash .\TechClean_ES.exe`).

| Archivo | SHA-256 |
|---|---|
| TechClean_ES.exe | `1B3CD7F4086C0A863ADC720992DCC19EF5A9AE967F5A1A675125965E2904FC1D` |
| TechClean_EN.exe | `F2378D916B798DDA22E180F09C270E167A6544842DD045B053692399D197E406` |

**Privacidad:** TechClean no recoge ni envía datos tuyos. Todo lo que guarda
se queda en tu equipo, y solo se conecta a internet para buscar
actualizaciones o cuando usas algo que lo necesita. Detalle en
[PRIVACIDAD.md](https://github.com/Hades3715/TechCleanPro/blob/main/PRIVACIDAD.md) (y en la app: Ajustes → Privacidad).

**Al abrirla por primera vez** te enseña las condiciones de uso (sin
garantía, bajo tu responsabilidad, solo en equipos tuyos o con permiso) y
hay que aceptarlas para usarla. También si venías de la 1.7.0.

---

## Novedades

### 📄 Informe del equipo en PDF (Historial → Crear informe)

Un PDF con la cara de TechClean, en tu Escritorio:

- **El resumen**: la salud del equipo con su anillo y, de un vistazo,
  cuántos problemas graves y cuántos para revisar hay.
- **Lo que conviene revisar**: cada problema con su nivel (grave / revisar)
  y **qué hacer**. Sale de todo lo que la app sabe mirar: pantallazos azules
  y apagados, salud de discos y batería, protección y secuestros, la
  auditoría de malware, dispositivos sin driver, disco lleno, demasiados
  programas al inicio, días sin reiniciar...
- **El equipo**: sistema, procesador, memoria, gráfica, unidades, batería.
- **Lo que hizo TechClean**: cada acción con su resultado, y lo liberado.

Tarda unos 30 segundos (revisa el equipo entero) y **solo lee**: generarlo no
cambia nada. Lo imprime Microsoft Edge, que viene con Windows, así que no
hace falta instalar nada; sin Edge, se guarda como página y se pasa a PDF con
Ctrl+P. El informe de la edición Admin para el cliente tiene la misma cara.

### 🎨 Temas (Ajustes → Apariencia)

Original, **Pulido** (de fábrica), Telemetría, Claro, Negro puro (OLED),
Bosque, Terminal retro, Sakura y Alto contraste. Cambian al instante. Van
dentro de la app: no se descarga nada y no se pueden cambiar desde fuera.
Cada color de texto cumple el contraste mínimo de accesibilidad (WCAG).

### 🧭 Todas las pantallas rediseñadas

Barra lateral agrupada con iconos de línea, tarjetas, y cada opción
explicada en su fila. Las listas largas (carpetas, programas, servicios,
el Historial) se dibujan de otra forma y ya no congelan la ventana.

El **widget flotante** también: con cada tema cambian sus colores (el acento
del tema en barras, gráficas y atajos; ámbar o rojo solo cuando algo se
llena), la letra, las esquinas y hasta el estilo (Telemetría lo pone en
modo panel de control). Tarjetas redondeadas, los mismos iconos que la app
y el logo con la versión, como en la barra lateral.

### 💽 Espacio en disco: la unidad entera

Antes se miraban dos niveles de carpetas. Ahora se recorre **todo el disco**
(unos 15-25 s para 300 GB) y puedes **entrar carpeta a carpeta**, ver qué
**tipos de archivo** ocupan más y los **archivos más grandes**. Solo ofrece
la papelera para lo tuyo: nunca para archivos de Windows, programas o
juegos. En OneDrive no despierta lo que está solo en la nube.

### 🔍 Reparar → Diagnóstico de fallos

Los últimos 30 días, explicados: **pantallazos azules** (también los que
Windows no llegó a guardar), **apagados inesperados** (y cuántos durante la
suspensión), **apps que se cierran solas**, errores de hardware y avisos del
disco. Cada cosa con qué suele haber detrás.

### 🩺 Lo de la edición Admin, ahora para todos

- **Componentes**: salud de los discos (en los NVMe, al momento y sin ser
  administrador) y de la batería; el uso de cada núcleo; y la **gráfica de la
  GPU de cualquier marca** (antes solo NVIDIA).
- **Aplicaciones → Inicio de Windows completo**: el registro (tuyo y el de
  todos los usuarios), las carpetas de Inicio y las tareas programadas. Se
  activa y desactiva igual que en el Administrador de tareas, **se puede
  deshacer**, y lo sospechoso sale marcado.
- **Drivers**: copia de seguridad de todos tus drivers antes de formatear, y
  reinstalarlos de una vez después.

### 🛡 Seguridad → Protección

Antivirus, cortafuegos, arranque seguro, control de cuentas y aislamiento del
núcleo de un vistazo (y por qué Defender sale apagado cuando otro antivirus
manda). Y si alguien **secuestró el navegador o la conexión**: archivo hosts,
proxy, DNS, certificados raíz y directivas del navegador.

### 🔐 Privacidad

Qué apps usaron tu **cámara, micrófono y ubicación**, y cuándo. Y en Ajustes,
qué guarda TechClean y cuándo se conecta.

### 🐞 Reportar un problema

Si algo falla, el aviso tiene **Enviar este error** (y en Ajustes está
**Reportar un problema**). Enseña exactamente lo que se envía: el error y
cómo es tu equipo, **sin tu nombre de usuario, el del equipo ni tus
carpetas**. La app no lo envía: *Abrir en GitHub* abre la página con el
texto puesto y lo publicas tú; *Copiar* lo deja listo para mandarlo por
donde quieras.

### 🎮 Gaming

- **Modo Juego automático por juego**: marca un juego y lo enciende solo al
  abrirlo.
- **Frenar lo que acapara la CPU** mientras juegas: le baja la prioridad (no
  lo cierra) y se la devuelve al terminar. Nunca toca el juego, el chat de
  voz ni la grabación.
- Un navegador o un vídeo a pantalla completa ya no cuentan como juego.
- **Bufferbloat**: el lag que aparece cuando alguien de la casa descarga.

### 🔋 Energía y 👀 Segundo plano

Energía: estado de la batería y qué apps gastan más (con la app como
administrador). Segundo plano: todo lo que TechClean hace sola, de un
vistazo, con un salto a donde se cambia cada cosa.

---

## Lo que pesa (medido, sin maquillar)

Cambiar de pantalla, en segundos (mediana de 4 medidas, alternando versiones
en el mismo equipo):

| Pantalla | 1.7.0 | 1.8.0 |
|---|---|---|
| Inicio | 0.51 | 0.69 |
| Componentes | 0.76 | 0.98 |
| Optimizar | 0.77 | 0.97 |
| Reparar | 0.69 | 1.15 |
| Aplicaciones | 0.46 | 0.45 |
| Seguridad | 0.30 | 0.43 |
| Privacidad | 0.58 | 0.59 |
| Gaming | 1.08 | 0.94 |
| Segundo plano | 0.27 | 0.45 |
| Historial | 0.21 | 0.33 |
| Energía | 0.26 | 0.42 |
| Ajustes | 1.01 | 1.38 |
| Espacio en disco | 0.34 | 0.45 |
| Drivers | 0.36 | 0.94 |

Las pantallas enseñan bastante más que antes (Reparar, el diagnóstico de
fallos; Drivers, la copia de seguridad y cuatro tarjetas nuevas) y tardan
entre una y cinco décimas más en abrirse. Aplicaciones, Privacidad y Gaming,
igual o menos. **En la bandeja gasta lo mismo** (0.1 % de CPU); con la
ventana abierta y quieta, **0.45 %** (0.35 % la 1.7.0), porque Inicio ahora
también lee la gráfica de las GPU AMD e Intel. Memoria: 97 MB (86 MB).

Por el camino se encontró por qué un primer rediseño era el doble de lento:
en Windows, cada pieza de la interfaz es una ventana del sistema, y una lista
de 40 filas eran cientos de ventanas. Las listas largas se dibujan ahora en un
solo lienzo: entrar en una carpeta del disco pasó de 0,9 s a 0,05 s, y la
lista de Inicio de Windows de 1 s a 0,25 s.

---

## Errores corregidos

- **Servicios enseñaba TODOS los servicios como detenidos**, también los que
  estaban en marcha (Windows entrega el estado como número).
- **Tildes rotas** ("Optimizaci¢n") en todo lo que venía de PowerShell:
  Servicios, Drivers, Tareas.
- **La papelera daba por enviados** archivos que no se habían movido.
- **Una copia de drivers fallida** se quedaba en "Trabajando..." para siempre.
- **Los avisos con texto largo se cortaban** (ventana fija de 420×150).
- **Textos cortados por los dos lados** con la ventana a su tamaño de fábrica
  o el zoom de Windows al 125 %.
- **Componentes seguía consultando el sistema** después de cerrar la pantalla.
- Borrar la caché o el historial del navegador congelaba la ventana; el
  desinstalador se lanzaba desde el hilo de la ventana.
- Segundo plano: cambiar la hora de la limpieza programada no la
  reprogramaba, la frecuencia no se guardaba y el interruptor del widget no
  decía si estaba visible.
- Actualizar una app con winget se daba por hecho sin comprobarlo.

---

## Para quien mire el código

- Módulos nuevos: `disco.py` (análisis de una unidad con 8 hilos; no lee la
  MFT a propósito: ver CONTEXTO), `gpu.py` (D3DKMT y contadores PDH, lo
  mismo que el Administrador de tareas), `informe.py` (HTML con la cara de la
  app → PDF con Edge sin ventana), `temas.py` e `iconos.py`.
- `ListaLienzo` (main.py): filas, barras, acciones e interruptores dibujados
  en un `tk.Canvas`. Lo que se aprendió está en
  `documentacion/CONTEXTO_PROYECTO.md` ("cada widget de Tk es una ventana").
- PowerShell que se lee como texto: `PS_UTF8` delante del script y
  `encoding="utf-8"`; los enumerados de `ConvertTo-Json` llegan como números.
- El banco pasó de 39 a **43 comprobaciones** (disco, diagnóstico,
  protección, temas). La auditoría ahora falla si una función está definida
  dos veces (la segunda pisa a la primera sin avisar: pasó en esta versión) y
  el verificador de idiomas si una clave está repetida.

---

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.
Gratis de usar y de leer — ver [LICENSE.md](https://github.com/Hades3715/TechCleanPro/blob/main/LICENSE.md) y
[PRIVACIDAD.md](https://github.com/Hades3715/TechCleanPro/blob/main/PRIVACIDAD.md).
