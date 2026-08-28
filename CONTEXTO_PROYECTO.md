# TechClean Pro — Contexto del proyecto

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

- **Versión actual**: 1.0.0 (`APP_VERSION` en `main.py`)
- **Stack**: Python + customtkinter (tema oscuro), psutil, pystray+Pillow,
  winreg, ctypes, sqlite3, PowerShell (para WMI vía `Get-CimInstance`)
- **~9,200 líneas** repartidas en `main.py` (5,160), `optimizer.py` (2,896),
  `system_monitor.py` (645), `idiomas.py` (388), más módulos más pequeños.

## Las dos ediciones

- **Cliente** (`main.py`, `EDICION = "cliente"`): oculta lo técnico. Panel oculto
  (7 clics en la versión, en Ajustes) con comandos `/help`, `/ram`, etc.
- **Admin** (`main_admin.py`, importa y reusa casi todo de `main.py`): Consola
  Dev siempre visible con el comando técnico exacto de cada acción — nunca se
  reparte al usuario final, es para el propio desarrollador o soporte técnico.

**Solo se sube a GitHub la edición cliente.** La admin nunca se publica.

## Cómo compilar

`Generar_App_Instalable.bat` (cliente) y `Generar_App_Admin.bat` (admin) —
PyInstaller, `--onefile --windowed --uac-admin`. Ambos scripts tienen una
sección de **firma digital opcional** al inicio (`CERT_THUMBPRINT` vacío por
defecto) — se activa sola en cuanto se rellene, sin tocar nada más del script.
`Iniciar_Rapido.bat`/`Iniciar_Rapido_Admin.bat` corren desde código fuente
directo, sin compilar (para probar rápido).

## Estado de publicación (a la fecha de este documento)

- **Todavía NO subido a GitHub.** `REPO_ACTUALIZACIONES = "TU_USUARIO/TU_REPO"`
  en `optimizer.py` sigue como placeholder — el buscador de actualizaciones
  está construido pero inactivo hasta que exista el repo real.
- **Certificado de firma digital**: no comprado todavía (~$220/año, OV/IV de
  Sectigo o Comodo — no EV, ya no vale la pena desde que Microsoft quitó la
  ventaja de SmartScreen instantáneo en 2024). Script listo para cuando exista.
- **Donaciones**: SÍ está activo — Ko-fi conectado a PayPal (Buy Me a Coffee no
  sirve, no paga a El Salvador). `URL_DONACION = "https://ko-fi.com/hadesdev"`
  en `optimizer.py`, botón "☕ Apoyar el proyecto" en Ajustes ya funcionando.
- **Plan de distribución**: cuando se publique, la idea es subir dos builds
  separados por idioma (ES/EN) para que alguien elija el correcto por el
  nombre del archivo en Releases de GitHub — el selector de idioma en la app
  se queda de todas formas (no es redundante: el mismo .exe pregunta el
  idioma la primera vez sin importar cuál build sea).

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

**Progreso de traducción**: 127 claves. Migrado por completo: menú lateral,
Inicio (Dashboard), Ajustes. **Sin migrar todavía**: Componentes, Optimizar,
Reparar, Aplicaciones, Privacidad, Seguridad, Gaming, Segundo Plano, Historial,
Energía, Consola Dev/Panel oculto — son la mayoría de las pantallas. Al
migrar una pantalla nueva: catalogar TODOS los strings (incluidos los que
solo aparecen en callbacks de botones, no solo en la construcción inicial),
agregar a ambos idiomas con paridad exacta, y verificar con:
```
python3 -c "
import re, idiomas
codigo = open('main.py', encoding='utf-8').read()
usadas = set(re.findall(r'(?<![a-zA-Z_.])t\(\"([a-z_0-9]+)\"', codigo))
definidas = set(idiomas.TEXTOS['es'].keys())
print('Sin definir:', usadas - definidas or 'ninguna')
print('Sin usar:', definidas - usadas or 'ninguna')
"
```

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

## Rutina de auditoría — correr SIEMPRE antes de dar algo por terminado

1. `python3 -m py_compile` de todos los archivos `.py`
2. Buscar métodos/funciones duplicados a nivel de clase o de módulo (no las
   funciones anidadas locales con nombres genéricos como `worker`/`confirmar`
   — esas SÍ pueden repetirse en distintos scopes sin problema)
3. Buscar llamadas a `self._algo(...)` sin que `_algo` esté definido en la
   clase (referencias rotas)
4. Buscar llamadas a `opt.algo(...)` / `sysmon.algo(...)` sin que existan esas
   funciones en sus módulos
5. Si se tocó `idiomas.py`: verificar paridad de claves entre `es` y `en`, y
   que toda clave usada en `main.py` con `t(...)` esté definida
6. Si se agregó una ventana Toplevel nueva: confirmar que tiene `grab_set()`
   (o una razón documentada para no tenerlo, como la ventana de error)

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
