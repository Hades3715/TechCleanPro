@echo off
chcp 65001 >nul
title TechClean Pro
echo Iniciando TechClean Pro...

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en este equipo.
    echo Instala Python desde https://www.python.org/downloads/
    echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist ".deps_ok" (
    echo Primera vez: instalando dependencias, un momento...
    python -m pip install -r requirements.txt >nul 2>nul
    echo ok > ".deps_ok"
) 

REM Borra caché de Python vieja antes de arrancar, para nunca correr
REM bytecode de una version anterior por accidente.
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>nul

python main.py
