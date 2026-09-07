@echo off
chcp 65001 >nul
title TechClean - Compilar el instalador
cd /d "%~dp0"
echo ============================================================
echo   TechClean - Generando el instalador
echo ============================================================
echo.
echo Esto crea un TechClean_1.5.0_Instalador.exe: un instalador de
echo verdad, que deja la app en Archivos de programa, la pone en
echo "Agregar o quitar programas" y la desinstala limpia.
echo.
echo Lo que NO hace: no reemplaza la firma digital. Windows va a
echo seguir avisando la primera vez, porque el instalador tampoco
echo esta firmado. Avisa menos y molesta menos, pero avisa.
echo.

REM ------------------------------------------------------------
REM  1. Comprobar que estan los .exe que hay que empaquetar
REM ------------------------------------------------------------
set FALTAN=0
if not exist "..\TechClean_ES.exe" (
    echo [ERROR] No se encuentra TechClean_ES.exe
    set FALTAN=1
)
if not exist "..\TechClean_EN.exe" (
    echo [ERROR] No se encuentra TechClean_EN.exe
    set FALTAN=1
)
if "%FALTAN%"=="1" (
    echo.
    echo Primero hay que generar las aplicaciones: vuelve a la carpeta
    echo de arriba y haz doble clic en Generar_App_Instalable.bat.
    echo Cuando termine, vuelve aqui.
    echo.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM  2. Buscar Inno Setup
REM ------------------------------------------------------------
set ISCC=
for %%R in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
    "%ProgramFiles%\Inno Setup 5\ISCC.exe"
) do (
    if exist %%R set ISCC=%%R
)
if not defined ISCC (
    where ISCC.exe >nul 2>nul
    if not errorlevel 1 set ISCC=ISCC.exe
)

if not defined ISCC (
    echo [ERROR] No se encontro Inno Setup en este equipo.
    echo.
    echo Es gratis y pesa poco. Descargalo de:
    echo.
    echo     https://jrsoftware.org/isdl.php
    echo.
    echo Instalalo con las opciones por defecto y vuelve a hacer doble
    echo clic en este archivo. No hay que configurar nada mas.
    echo.
    pause
    exit /b 1
)

echo Inno Setup encontrado: %ISCC%
echo.
echo Compilando...
echo.

if not exist "salida" mkdir "salida"
%ISCC% "TechClean.iss"
if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Listo. El instalador quedo en:
echo.
echo     instalador\salida\TechClean_1.5.0_Instalador.exe
echo.
echo   Ese es el archivo que se sube a Releases. Quien lo descargue
echo   solo tiene que abrirlo y darle a Siguiente.
echo ============================================================
echo.
pause
