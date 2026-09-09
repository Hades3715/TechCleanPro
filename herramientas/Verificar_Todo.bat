@echo off
chcp 65001 >nul
title TechClean - Verificacion
cd /d "%~dp0.."

REM ============================================================
REM  Las rutas van con BARRA NORMAL (herramientas/x.py) y no con
REM  barra invertida, a proposito.
REM
REM  Este archivo estuvo roto y no se noto: ocho de las lineas se
REM  habian escrito como "herramientas\revisar_algo.py" y esa
REM  barra invertida seguida de r acabo convertida en un retorno
REM  de carro de verdad. cmd leia entonces "python herramientas"
REM  —que falla— y "evisar_algo.py" como si fuera otro comando.
REM  Como un .bat sigue con la linea siguiente cuando una falla,
REM  las ocho comprobaciones se saltaban en silencio y el banco
REM  parecia estar pasando entero.
REM
REM  cmd acepta la barra normal en los argumentos igual que la
REM  invertida, y Python tambien. Sin barras invertidas no hay
REM  nada que se pueda convertir en otra cosa.
REM
REM  Y ahora cada comprobacion pasa por :comprobar, que cuenta los
REM  fallos y avisa si una termina mal — incluido el caso de que no
REM  llegue a arrancar.
REM ============================================================

echo ==========================================================
echo   VERIFICACION COMPLETA - TechClean
echo ==========================================================
echo.
echo Esta ventana NO se cierra sola: al terminar espera a que
echo presiones una tecla, para que puedas leer los resultados.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en este equipo.
    echo Instala Python desde https://www.python.org/downloads/
    echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

set PYTHONIOENCODING=utf-8
set TOTAL=0
set FALLOS=0

call :comprobar "1. Auditoria (duplicados y referencias rotas)" herramientas/auditoria.py
call :comprobar "2. Idiomas (paridad es/en y claves)" herramientas/verificar_idiomas.py
call :comprobar "3. Animacion de las barras" herramientas/prueba_animacion.py
call :comprobar "4. Hilos (nadie toca la interfaz desde un hilo)" herramientas/revisar_hilos.py
call :comprobar "5. Widget flotante (arrastre, tooltips, esquinas, hover)" herramientas/prueba_widget.py
call :comprobar "6. Modo Juego (no confundir el escritorio con un juego)" herramientas/prueba_modo_juego.py
call :comprobar "7. Ediciones - cliente" herramientas/prueba_ediciones.py cliente
call :comprobar "8. Ediciones - admin" herramientas/prueba_ediciones.py admin
call :comprobar "9. Historial que sobrevive al cierre" herramientas/prueba_historial.py
call :comprobar "10. Hilos e interfaz (el error de main thread)" herramientas/prueba_hilos_interfaz.py
call :comprobar "11. Limpieza de temporales (no borrar la propia app)" herramientas/prueba_limpieza_temp.py
call :comprobar "12. Datos: lo que lee la interfaz existe" herramientas/revisar_claves.py
call :comprobar "13. Lecturas reales del sistema" herramientas/revisar_lecturas.py
call :comprobar "14. Motor de comandos (cobertura de /help)" herramientas/revisar_comandos.py
call :comprobar "15. Consola: historial, colores, traducciones" herramientas/prueba_consola.py
call :comprobar "16. Todas las pantallas y pestanas (es)" herramientas/revisar_pantallas.py es
call :comprobar "17. Todas las pantallas y pestanas (en)" herramientas/revisar_pantallas.py en
call :comprobar "18. Deshacer: revierte lo correcto" herramientas/prueba_deshacer.py
call :comprobar "19. Herramientas de tecnico (edicion admin)" herramientas/prueba_tecnico.py
call :comprobar "20. Script del instalador" herramientas/revisar_instalador.py
call :comprobar "21. Ajustes: surten efecto sin reiniciar" herramientas/revisar_ajustes.py
call :comprobar "22. Bucles de refresco no se duplican" herramientas/prueba_bucles.py
call :comprobar "23. Arranque real en espanol" herramientas/prueba_arranque.py es
call :comprobar "24. Arranque real en ingles" herramientas/prueba_arranque.py en

call :comprobar "25. Los .exe llevan dentro todo lo que importan" herramientas/revisar_empaquetado.py

echo ---------- 26. Velocidad de internet (necesita conexion) ----------
echo Esta prueba SI usa datos (unos 60 MB). Si estas con datos moviles,
echo cierra esta ventana ahora.
pause
call :comprobar "26. Velocidad de internet" herramientas/prueba_velocidad.py

echo ==========================================================
echo   Termino: %TOTAL% comprobaciones, %FALLOS% con fallo.
echo ==========================================================
if "%FALLOS%"=="0" echo   Todo en verde. Se puede publicar.
if not "%FALLOS%"=="0" echo   Busca arriba las lineas que dicen FALLO.
echo.
pause
exit /b %FALLOS%

REM ------------------------------------------------------------
REM  :comprobar  "titulo"  script  [arg]
REM
REM  Lo importante es el if errorlevel: antes, si una comprobacion
REM  ni siquiera arrancaba, no se distinguia de una que pasaba —
REM  el .bat imprimia el titulo, Python se quejaba en una linea
REM  suelta y seguia con la siguiente.
REM ------------------------------------------------------------
:comprobar
set /a TOTAL+=1
echo ---------- %~1 ----------
python %2 %3
if errorlevel 1 (
    set /a FALLOS+=1
    echo.
    echo    ^>^> FALLO en esta comprobacion: %~1
)
echo.
goto :eof
