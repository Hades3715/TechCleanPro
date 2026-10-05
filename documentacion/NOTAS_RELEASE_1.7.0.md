# TechClean 1.7.0

**Más rápida, y con todo a un atajo de distancia.** Inicio ya no se traba,
Drivers abre al instante, y lo que más se usa (liberar RAM, limpiar, medir el
Wi-Fi) se hace desde la bandeja, con un atajo de teclado o escribiéndolo en
el nuevo buscador **Ctrl+K**. Y una revisión de las extensiones de tus
navegadores, que es por donde más se roban cuentas hoy.

Si venías de la 1.6.0, tus preferencias y tu historial siguen como estaban.

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

## Más rápida

Medido en un equipo real, no a ojo:

| Qué | Antes | Ahora |
|---|---|---|
| Inicio (los indicadores en vivo) | se congelaba 0.3 s cada 2 s | sin tirones |
| Abrir la lista de drivers | 3.3 s congelada | 0.01 s |
| Escribir en el buscador de drivers | 3 s por cada letra | instantáneo |
| Cambiar de pantalla | 0.6 a 1.7 s | un 15-20 % menos |

- **Inicio se trababa** porque, para medir la CPU, la ventana se quedaba
  esperando 0.3 segundos, cada 2 segundos: clics y scroll a tirones el 15 %
  del tiempo.
- **Las barras de desplazamiento** de la librería de la interfaz recalculaban
  la ventana entera cada vez que se movían, y eso se encadenaba.
- **Drivers** creaba una tarjeta por cada driver (más de 200) y las rehacía
  todas con cada letra del buscador. Ahora es una sola lista, y se puede
  copiar el nombre de un driver.

Y sigue siendo ligera: **0.35 % de CPU** con la ventana abierta y **0.09 %**
en la bandeja, con todo lo nuevo encendido.

---

## Novedades

### 🔎 Buscador de funciones: Ctrl+K

Desde cualquier pantalla, pulsá **Ctrl+K** (o "Buscar" arriba a la
izquierda) y escribí lo que querés hacer: "ram", "wifi", "dns", "drivers",
"duplicados"... Te lleva directo, y si es una acción la hace. Entiende con o
sin tildes, en español o en inglés, y aunque escribas "memroia".

### 🧠 Desde la bandeja, sin abrir la ventana

Clic derecho en el icono de TechClean junto al reloj: **Liberar RAM** y
**Limpieza rápida** (RAM + temporales). El resultado sale en una notificación.

### ⌨ Atajo de teclado para liberar RAM

Opcional, en Ajustes: **Ctrl + Alt + R** (o la combinación que elijas) libera
RAM desde cualquier programa, incluso en mitad de una partida. Con el Modo
Juego encendido, el juego no se toca.

Está hecho con la función de Windows para atajos, no con un "gancho" de
teclado: TechClean solo se entera de esa combinación, no de nada más que
escribas. Si otro programa ya la usa, te lo dice.

### 📶 Wi-Fi

En **Gaming**, debajo del medidor de lag: señal (en dBm, que es lo fiable),
banda (2,4 / 5 / 6 GHz), canal, estándar (Wi-Fi 5, Wi-Fi 6...), velocidad del
enlace y cuántas redes vecinas comparten tu canal. Y un veredicto en
castellano: "estás en 2,4 GHz y hay 6 redes en tu canal, cambiá a la red 5G".
Si el medidor de lag dice que el problema está en tu casa, esto te dice por qué.

### 🧩 Extensiones del navegador

En **Seguridad → Extensiones**: todas las extensiones de Chrome, Edge, Brave,
Opera, Vivaldi y Firefox, en todos sus perfiles. Una extensión que puede leer
todas las webs ve lo que escribís, contraseñas incluidas, y ningún antivirus
la revisa. Marca:

- las **cargadas sin pasar por la tienda** (así se instalan muchas maliciosas),
- las **forzadas por el registro** de Windows (no se pueden quitar desde el
  navegador: una técnica típica de malware),
- las que pueden **leer todas las webs y tus cookies**,
- y las **VPN gratuitas** que desvían tu tráfico.

Las que pone tu escuela o tu empresa en una cuenta de trabajo se reconocen
como tales y no se marcan como peligro. **Solo mira**: para quitar una, se
hace desde el navegador.

### 🔗 Accesos directos rotos

En **Espacio en disco → Accesos rotos**: los accesos del Escritorio y del menú
Inicio que apuntan a programas que ya no existen. Van a la papelera, así que
se pueden recuperar. Los que se abrían solos al encender el equipo salen
**sin marcar**: pueden ser restos de algo sospechoso, y conviene mirarlos
antes en la Auditoría de seguridad.

### 🔔 Avisos nuevos

- **Días sin reiniciar.** Con el "Inicio rápido" de Windows (activado de
  fábrica), **apagar no reinicia**: el sistema sigue donde lo dejaste. Hay
  equipos con semanas sin un reinicio de verdad. TechClean avisa a los 7 días
  (o 3, o 14) y lo tiene en cuenta en la salud de Inicio.
- **Límite de carga de la batería** (opcional, para portátiles): avisa al
  llegar al 80 % (o 85, o 90) para que desenchufes. Tenerla siempre al 100 %
  es lo que más la desgasta.

### ✨ Y además

- **Ventana de novedades** la primera vez que abrís una versión nueva (y en
  Ajustes, para verla otra vez).
- **Historial**: "Lo que TechClean hizo por ti", con el espacio de disco y la
  RAM liberados por separado, y lo de este mes.
- **6 comandos nuevos** en la consola (44 en total): `/wifi`, `/disco`,
  `/extensiones`, `/accesos`, `/encendido` y `/buscar`.

---

## Errores corregidos

- **La prueba de velocidad del disco medía la RAM, no el disco.** Leía el
  archivo que acababa de escribir, y Windows lo servía desde la memoria: salían
  miles de MB/s también en un disco mecánico viejo. Ahora mide el disco de
  verdad, también en bloques sueltos (lo que más se nota al abrir programas),
  y te dice si rinde como un disco mecánico, un SSD o un NVMe. Si Windows dice
  que es un SSD pero rinde como uno mecánico, te avisa.
- **El Historial contaba la RAM como "espacio liberado".** Con la liberación
  automática de RAM cada pocos minutos, la cifra llegaba a cientos de GB que
  nunca fueron espacio en disco. Ahora van separados, también lo que se guardó
  con versiones anteriores.
- **Importar ajustes aceptaba cualquier archivo.** Uno con un texto donde va
  un número rompía la app más tarde, en otra pantalla. Ahora solo se importan
  ajustes conocidos y con valores válidos, y te dice cuántos se ignoraron.
- **Las fechas de los drivers salían como `/Date(1150848000000)/`** y no se
  ordenaban por antigüedad.

---

## Para quien mire el código

- El banco de comprobaciones pasó de 35 a **39**:
  `prueba_rendimiento.py` (que nada vuelva a congelar la ventana),
  `prueba_wifi_disco.py`, `prueba_extensiones_accesos.py` (un navegador de
  mentira con cada tipo de extensión, y accesos directos reales creados con
  Windows) y `prueba_acciones_rapidas.py`.
- El Wi-Fi se lee con `wlanapi.dll` y no con `netsh`, cuya salida viene
  traducida al idioma de Windows. Sin pedir un escaneo, Windows 11 solo
  devuelve la red a la que estás conectado.
- La prueba de disco usa `FILE_FLAG_NO_BUFFERING` (el comentario antiguo decía
  que hacían falta privilegios: no) y `FILE_FLAG_DELETE_ON_CLOSE`, así que el
  archivo de prueba desaparece aunque la app se cierre de golpe.
- Los `.lnk` se leen con un lector propio del formato MS-SHLLINK, comparado
  contra lo que dice Windows en 147 accesos reales.
- `atajos.py`: `RegisterHotKey` con su propio bucle de mensajes. Ningún gancho
  de teclado.

---

Desarrollado por **Edwin Javier Cortez Cardoza (Hades)**.
Gratis de usar y de leer — ver [LICENSE.md](LICENSE.md).
