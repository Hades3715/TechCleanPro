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

echo ---------- 4. Ediciones (que opciones ve cada una) ----------
python herramientas\prueba_ediciones.py cliente
python herramientas\prueba_ediciones.py admin
echo.

echo ---------- 5. Limpieza de temporales (no borrar la propia app) ----------
python herramientas\prueba_limpieza_temp.py
echo.

echo ---------- 6. Arranque real en espanol ----------
python herramientas\prueba_arranque.py es
echo.

echo ---------- 7. Arranque real en ingles ----------
python herramientas\prueba_arranque.py en
echo.

echo ---------- 8. Velocidad de internet (necesita conexion) ----------
echo Esta prueba SI usa datos (unos 60 MB). Si estas con datos moviles,
echo cierra esta ventana ahora.
pause
python herramientas\prueba_velocidad.py
echo.

echo ==========================================================
echo   Termino. Revisa arriba que no haya FALLO ni errores.
echo ==========================================================
pause
