@echo off
chcp 65001 >nul
title TechClean - Edicion Administrador
echo Iniciando TechClean (Edicion Administrador)...

REM cd explicito: al hacer doble clic, cmd ya entra en esta carpeta, pero
REM llamandolo desde otro sitio no — y entonces no encontraria codigo.
cd /d "%~dp0"

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
if exist "codigo\__pycache__" rmdir /s /q "codigo\__pycache__" >nul 2>nul

python codigo\main_admin.py
