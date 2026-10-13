# Privacidad y condiciones de uso de TechClean

*Versión 1.8.0 · Escrito en lenguaje claro: si algo no se entiende, es un
fallo de este documento, no tuyo. English version below.*

## En corto

- **TechClean no recoge ni envía datos tuyos.** No hay cuentas, ni
  anuncios, ni telemetría, ni estadísticas de uso. Nadie, ni el
  desarrollador, sabe quién usa la app ni qué hace con ella.
- **Lo que guarda, lo guarda en tu equipo**, en `%APPDATA%\TechClean`: tus
  preferencias, el historial de lo que hizo y los registros de errores. Lo
  puedes ver en Ajustes → *Abrir carpeta de registros* y borrar cuando
  quieras.
- **Solo cambia lo que tú le pides.** Lo que se puede deshacer queda en
  Historial → *Se puede deshacer*; lo que no, te lo pregunta antes.
- **El código es público**: cualquiera puede leer exactamente qué hace.

## Cuándo se conecta a internet

Nunca en segundo plano, salvo para buscar actualizaciones como mucho una
vez al día. En todos los casos, el servidor ve tu dirección IP (como
cuando visitas cualquier web) y nada más: TechClean no le envía ningún
dato tuyo ni de tu equipo.

| Cuándo | A dónde | Qué se envía |
|---|---|---|
| Buscar actualizaciones (al abrir, una vez al día, o con el botón) | `api.github.com` | La pregunta "¿cuál es la última versión?" |
| Prueba de velocidad y de bufferbloat (solo si la pulsas) | `speed.cloudflare.com`, `www.gstatic.com` | Datos de relleno para medir la velocidad |
| Medir el lag (solo si lo pulsas) | Tu router y `1.1.1.1` | Pings |
| Comparar o cambiar el DNS (solo si lo pulsas) | Cloudflare, Google, Quad9, OpenDNS | Consultas de nombres de prueba |
| Actualizar apps (solo si lo pulsas) | El catálogo de `winget` de Microsoft | Lo mismo que winget por su cuenta |
| Página de soporte del fabricante, Ko-fi | Se abren en tu navegador | — |

## Qué mira de tu equipo, y para qué

Para enseñarte cómo está el equipo, TechClean **lee**: el uso de CPU,
memoria, discos y red; los programas instalados y los que arrancan con
Windows; los servicios y las tareas programadas; el registro de eventos
de Windows (para el diagnóstico de fallos); la salud de discos y batería;
el estado de la protección (antivirus, cortafuegos); las extensiones de
tus navegadores (sus archivos de descripción, **no** tu historial ni tus
contraseñas); y qué apps usaron la cámara, el micrófono o la ubicación
(lo que ya guarda Windows). **Todo eso se queda en tu equipo**: se enseña
en pantalla y, si tú lo pides, va al informe en PDF, que se guarda en tu
Escritorio y no se envía a ningún sitio.

## Por qué pide permisos de administrador

Muchas reparaciones de Windows (sfc, DISM, liberar la memoria del
sistema, la salud de algunos discos, el consumo de energía por app) solo
funcionan como administrador. La app no usa ese permiso para nada que no
le pidas.

## Por qué Windows avisa al abrirla

TechClean no tiene firma digital (cuesta unos cientos de dólares al año y
la hace un estudiante), así que Windows SmartScreen avisa la primera vez.
Puedes comprobar que el archivo es el original comparando su huella
SHA-256 con la que se publica en cada versión de GitHub, o compilarla tú
desde el código.

## Condiciones de uso

- TechClean es **gratis**. Puedes usarla en todos los equipos que quieras,
  también para arreglar los de otras personas.
- Se ofrece **tal cual, sin garantía**: se prueba mucho (más de 40
  comprobaciones automáticas antes de cada versión), pero toca partes
  delicadas del sistema y ningún programa está libre de errores. Antes de
  reparaciones grandes, la app crea un punto de restauración; aun así, ten
  copia de tus archivos importantes.
- El desarrollador no se hace responsable de daños o pérdidas de datos
  derivados de su uso.
- El código se puede leer, pero no redistribuir ni vender como propio:
  ver [LICENSE.md](LICENSE.md).

## Contacto

Dudas, fallos o sugerencias: en la página del proyecto en GitHub
(*Issues*).

---

# TechClean privacy and terms of use (English)

- **TechClean doesn't collect or send any of your data.** No accounts, no
  ads, no telemetry, no usage statistics.
- **What it saves stays on your computer**, in `%APPDATA%\TechClean`:
  settings, the history of what it did and error logs. You can open that
  folder from Settings and delete it whenever you want.
- **It only changes what you ask it to.** Reversible changes appear in
  History → *Can be undone*; anything that can't be undone is confirmed
  first.
- **It only goes online** to check for updates (at most once a day, at
  `api.github.com`) or when you use something that needs it: the speed
  and bufferbloat tests (Cloudflare, Google), the lag test (pings to your
  router and `1.1.1.1`), comparing DNS servers, or updating apps with
  winget. Those servers see your IP address, like any website does, and
  nothing else.
- **What it reads** about your computer (usage, installed programs,
  startup items, Windows event log, disk and battery health, protection
  status, browser extension descriptions — never your browsing history or
  passwords) stays on your computer. The PDF report is saved to your
  Desktop and sent nowhere.
- **Administrator rights** are needed for several Windows repairs; they're
  not used for anything you didn't ask for.
- **No digital signature** yet (it costs hundreds of dollars a year), so
  SmartScreen warns the first time. You can check the file against the
  SHA-256 hash published with each release, or build it from the source.
- TechClean is **free** and provided **as is, without warranty**. Keep
  backups of important files. The source can be read but not
  redistributed or sold: see [LICENSE.md](LICENSE.md).
