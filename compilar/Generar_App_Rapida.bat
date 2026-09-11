@echo off
chcp 65001 >nul
title TechClean - Generador de la version RAPIDA (carpeta)
REM Se trabaja desde la RAIZ del proyecto, no desde compilar: asi las
REM rutas relativas que ya habia (assets, requirements.txt, dist, el
REM .exe de salida) siguen valiendo tal cual.
cd /d "%~dp0.."
echo ============================================================
echo   TechClean - Version RAPIDA (arranca en menos de 1 segundo)
echo ============================================================
echo.
echo Genera la MISMA aplicacion, pero en modo carpeta en vez de un
echo unico archivo .exe.
echo.
echo   Por que arranca mucho mas rapido:
echo   El .exe unico lleva la app entera comprimida dentro, y
echo   Windows tiene que descomprimir 22 MB en una carpeta temporal
echo   CADA VEZ que lo abres, antes de que aparezca nada. En modo
echo   carpeta los archivos ya estan en su sitio: no hay nada que
echo   descomprimir.
echo.
echo   Medido en el equipo del desarrollador:
echo     .exe unico   3.7 segundos
echo     carpeta      0.5 segundos
echo.
echo   El costo: en vez de un archivo suelto es una carpeta con
echo   muchos archivos dentro. Para repartirla se comprime en .zip
echo   (este script lo hace solo). Para usarla a diario en tu propio
echo   equipo, esta es la buena.
echo.
echo (Puede tardar 3-6 minutos. No cierres esta ventana.)
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en este equipo.
    echo Instala Python desde https://www.python.org/downloads/
    echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

set PYTHONIOENCODING=utf-8

echo [1/4] Instalando lo necesario para compilar...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Limpiando restos de compilaciones anteriores...
rmdir /s /q build >nul 2>nul
rmdir /s /q dist_rapida >nul 2>nul
del /q "TechClean_ES_rapida.spec" >nul 2>nul
del /q "TechClean_EN_rapida.spec" >nul 2>nul

echo.
echo [2/4] Comprobando que los dos idiomas esten completos...
python herramientas\verificar_idiomas.py
if errorlevel 1 (
    echo.
    echo [ERROR] La verificacion de idiomas fallo. No se compila nada.
    pause
    exit /b 1
)

echo.
echo [3/4] Compilando las dos versiones rapidas...
call :compilar es ES
if errorlevel 1 goto :error
call :compilar en EN
if errorlevel 1 goto :error

call :fijar_idioma es

echo.
echo [4/4] Comprimiendo cada carpeta en un .zip para repartirla...
call :comprimir ES
call :comprimir EN

rmdir /s /q build >nul 2>nul
del /q "TechClean_ES_rapida.spec" >nul 2>nul
del /q "TechClean_EN_rapida.spec" >nul 2>nul

echo.
echo ============================================================
echo   Listo. En la carpeta dist_rapida quedaron:
echo.
echo     TechClean_ES_rapida\TechClean_ES_rapida.exe
echo     TechClean_EN_rapida\TechClean_EN_rapida.exe
echo.
echo   Y al lado, los .zip listos para subir a Releases:
echo.
echo     TechClean_ES_rapida.zip
echo     TechClean_EN_rapida.zip
echo.
echo   Quien lo descargue tiene que DESCOMPRIMIR el zip entero y
echo   abrir el .exe de dentro. Si saca solo el .exe de la carpeta,
echo   no funciona: necesita los archivos que van con el.
echo ============================================================
echo.
pause
exit /b 0

REM ------------------------------------------------------------
REM  Compila una version.  %1 = idioma (es/en)   %2 = sufijo (ES/EN)
REM ------------------------------------------------------------
:compilar
echo.
echo   --- Compilando version %2 (rapida) ---
call :fijar_idioma %1
python -m PyInstaller --noconfirm --clean --onedir --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_%2_rapida" --distpath "dist_rapida" --add-data "assets;assets" --paths codigo codigo\main.py

if not exist "dist_rapida\TechClean_%2_rapida\TechClean_%2_rapida.exe" (
    echo.
    echo   [ERROR] Fallo la compilacion de la version %2. Revisa los mensajes de arriba.
    exit /b 1
)
exit /b 0

REM ------------------------------------------------------------
REM  Comprime una carpeta en un .zip.  %1 = sufijo (ES/EN)
REM ------------------------------------------------------------
:comprimir
powershell -NoProfile -Command "Compress-Archive -Path 'dist_rapida\TechClean_%1_rapida' -DestinationPath 'dist_rapida\TechClean_%1_rapida.zip' -Force"
if errorlevel 1 (
    echo   [AVISO] No se pudo comprimir la version %1. La carpeta esta igual en dist_rapida.
)
exit /b 0

REM ------------------------------------------------------------
REM  Reescribe SOLO build_config.py con el idioma %1
REM ------------------------------------------------------------
:fijar_idioma
> codigo\build_config.py echo # -*- coding: utf-8 -*-
>> codigo\build_config.py echo """Idioma fijado al compilar.
>> codigo\build_config.py echo.
>> codigo\build_config.py echo Este archivo lo REESCRIBE el generador antes de cada compilacion.
>> codigo\build_config.py echo No lo edites a mano: se pierde en la siguiente build.
>> codigo\build_config.py echo """
>> codigo\build_config.py echo.
>> codigo\build_config.py echo IDIOMA = "%1"
exit /b 0

:error
echo.
echo [ERROR] La generacion se detuvo. Revisa los mensajes de arriba.
call :fijar_idioma es
pause
exit /b 1
