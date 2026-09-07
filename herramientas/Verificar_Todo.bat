@echo off
chcp 65001 >nul
title TechClean - Verificacion
cd /d "%~dp0.."

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

echo ---------- 1. Auditoria (duplicados y referencias rotas) ----------
python herramientas\auditoria.py
echo.

echo ---------- 2. Idiomas (paridad es/en y claves) ----------
python herramientas\verificar_idiomas.py
echo.

echo ---------- 3. Animacion de las barras ----------
python herramientas\prueba_animacion.py
echo.

echo ---------- 4. Hilos (nadie toca la interfaz desde un hilo) ----------
python herramientasevisar_hilos.py
echo.

echo ---------- 5. Widget flotante (arrastre, tooltips, colores) ----------
python herramientas\prueba_widget.py
echo.

echo ---------- 6. Modo Juego (no confundir el escritorio con un juego) ----------
python herramientas\prueba_modo_juego.py
echo.

echo ---------- 7. Ediciones (que opciones ve cada una) ----------
python herramientas\prueba_ediciones.py cliente
python herramientas\prueba_ediciones.py admin
echo.

echo ---------- 8. Historial que sobrevive al cierre ----------
python herramientas\prueba_historial.py
echo.

echo ---------- 9. Hilos e interfaz (el error de main thread) ----------
python herramientas\prueba_hilos_interfaz.py
echo.

echo ---------- 10. Limpieza de temporales (no borrar la propia app) ----------
python herramientas\prueba_limpieza_temp.py
echo.

echo ---------- 11. Datos: lo que lee la interfaz existe ----------
python herramientasevisar_claves.py
echo.

echo ---------- 12. Lecturas reales del sistema ----------
python herramientasevisar_lecturas.py
echo.

echo ---------- 13. Panel de comandos oculto ----------
python herramientasevisar_comandos.py
echo.

echo ---------- 14. Todas las pantallas y pestanas (es) ----------
python herramientasevisar_pantallas.py es
echo.

echo ---------- 15. Todas las pantallas y pestanas (en) ----------
python herramientasevisar_pantallas.py en
echo.

echo ---------- 16. Deshacer: revierte lo correcto ----------
python herramientas\prueba_deshacer.py
echo.

echo ---------- 17. Ajustes: surten efecto sin reiniciar ----------
python herramientasevisar_ajustes.py
echo.

echo ---------- 18. Bucles de refresco no se duplican ----------
python herramientas\prueba_bucles.py
echo.

echo ---------- 19. Arranque real en espanol ----------
python herramientas\prueba_arranque.py es
echo.

echo ---------- 20. Arranque real en ingles ----------
python herramientas\prueba_arranque.py en
echo.

echo ---------- 21. Velocidad de internet (necesita conexion) ----------
echo Esta prueba SI usa datos (unos 60 MB). Si estas con datos moviles,
echo cierra esta ventana ahora.
pause
python herramientas\prueba_velocidad.py
echo.

echo ==========================================================
echo   Termino. Revisa arriba que no haya FALLO ni errores.
echo ==========================================================
pause
