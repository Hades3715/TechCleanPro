@echo off
chcp 65001 >nul
title TechClean Pro - Verificacion
cd /d "%~dp0.."

echo ==========================================================
echo   VERIFICACION COMPLETA - TechClean Pro
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

echo ---------- 1. Auditoria (duplicados y referencias rotas) ----------
python herramientas\auditoria.py
echo.

echo ---------- 2. Idiomas (paridad es/en y claves) ----------
python herramientas\verificar_idiomas.py
echo.

echo ---------- 3. Animacion de las barras ----------
python herramientas\prueba_animacion.py
echo.

echo ---------- 4. Arranque real en espanol ----------
python herramientas\prueba_arranque.py es
echo.

echo ---------- 5. Arranque real en ingles ----------
python herramientas\prueba_arranque.py en
echo.

echo ==========================================================
echo   Termino. Revisa arriba que no haya FALLO ni errores.
echo ==========================================================
pause
