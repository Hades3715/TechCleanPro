@echo off
chcp 65001 >nul
title TechClean Pro - Generador de la app instalable (ES + EN)
cd /d "%~dp0"
echo ============================================================
echo   TechClean Pro - Generando tus aplicaciones (.exe)
echo ============================================================
echo.
echo Genera los DOS ejecutables de la edicion cliente:
echo.
echo     TechCleanPro_ES.exe   (espanol)
echo     TechCleanPro_EN.exe   (ingles)
echo.
echo La edicion cliente ya no lleva selector de idioma dentro: se
echo publican los dos archivos y cada quien descarga el que le
echo sirve, por el nombre. Este script reescribe build_config.py
echo antes de cada compilacion y lo deja de vuelta en espanol al
echo terminar, tambien si algo falla a mitad de camino.
echo.
echo (Puede tardar 3-6 minutos. No cierres esta ventana.)
echo.

REM ============================================================
REM   FIRMA DIGITAL (opcional) - deja las 2 lineas de abajo vacias
REM   si todavia no tienes un certificado de firma de codigo. En
REM   cuanto lo tengas, solo hay que completar estas 2 lineas -
REM   nada mas del script cambia.
REM
REM   CERT_THUMBPRINT: la "huella digital" (thumbprint) de tu
REM   certificado, una vez instalado en el almacen de certificados
REM   de Windows (los certificados modernos viven en un token USB
REM   o una nube HSM, no en un archivo .pfx suelto - por eso se
REM   referencia por huella, no por ruta de archivo). Tu proveedor
REM   (Sectigo, Comodo, etc.) te la da al activar el token, o la
REM   ves en certmgr.msc una vez instalado el driver del token.
REM ============================================================
set CERT_THUMBPRINT=
set TIMESTAMP_URL=http://timestamp.digicert.com

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en este equipo.
    echo.
    echo Instala Python desde https://www.python.org/downloads/
    echo IMPORTANTE: durante la instalacion, marca la casilla
    echo "Add Python to PATH" antes de darle a Instalar.
    echo.
    echo Despues de instalarlo, vuelve a hacer doble clic en este archivo.
    pause
    exit /b 1
)

echo [1/4] Instalando lo necesario para compilar...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Limpiando restos de compilaciones anteriores (para evitar usar codigo viejo por error)...
rmdir /s /q build >nul 2>nul
rmdir /s /q dist >nul 2>nul
del /q "TechCleanPro.spec" >nul 2>nul
del /q "TechCleanPro_ES.spec" >nul 2>nul
del /q "TechCleanPro_EN.spec" >nul 2>nul
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>nul

echo.
echo [2/4] Comprobando que los dos idiomas esten completos...
set PYTHONIOENCODING=utf-8
python herramientas\verificar_idiomas.py
if errorlevel 1 (
    echo.
    echo [ERROR] La verificacion de idiomas fallo. No se compila nada.
    echo Un desbalance entre espanol e ingles saldria a la luz recien
    echo con el .exe ya repartido, y ahi ya es tarde.
    pause
    exit /b 1
)

echo.
echo [3/4] Compilando las dos builds...
call :compilar es ES
if errorlevel 1 goto :error
call :compilar en EN
if errorlevel 1 goto :error

REM Dejar build_config.py como estaba
call :fijar_idioma es

echo.
echo [4/4] Limpiando archivos temporales de la compilacion...
rmdir /s /q build >nul 2>nul
del /q "TechCleanPro_ES.spec" >nul 2>nul
del /q "TechCleanPro_EN.spec" >nul 2>nul

echo.
echo ============================================================
echo   Listo. En esta carpeta quedaron:
echo.
echo     TechCleanPro_ES.exe   - version en espanol
echo     TechCleanPro_EN.exe   - version en ingles
echo.
echo   Subilos con esos nombres a Releases de GitHub: el nombre del
echo   archivo es lo unico que le dice a la gente cual descargar,
echo   porque la app ya no pregunta el idioma.
echo ============================================================
echo.
pause
exit /b 0

REM ------------------------------------------------------------
REM  Compila una build.  %1 = idioma (es/en)   %2 = sufijo (ES/EN)
REM ------------------------------------------------------------
:compilar
echo.
echo   --- Compilando version %2 ---
call :fijar_idioma %1
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechCleanPro_%2" --add-data "assets;assets" main.py

if not exist "dist\TechCleanPro_%2.exe" (
    echo.
    echo   [ERROR] Fallo la compilacion de la version %2. Revisa los mensajes de arriba.
    exit /b 1
)
REM BUG corregido: este copy mandaba su salida a nul, asi que cuando
REM fallaba nadie se enteraba. Y falla de verdad: si el .exe anterior
REM esta ABIERTO (tipico, porque uno lo deja minimizado en la bandeja
REM para probarlo), Windows no deja sobreescribirlo. El script seguia
REM diciendo "Listo" y en la carpeta quedaba el ejecutable VIEJO, listo
REM para subirse a una release con codigo de hace dos versiones.
REM
REM Truco: Windows SI deja renombrar un .exe en ejecucion (el candado es
REM sobre el contenido, no sobre el nombre). Se aparta el viejo y se copia
REM el nuevo en su lugar; el que este corriendo sigue vivo sin enterarse.
if exist "TechCleanPro_%2.exe" (
    del /q "TechCleanPro_%2_anterior.exe" >nul 2>nul
    ren "TechCleanPro_%2.exe" "TechCleanPro_%2_anterior.exe" >nul 2>nul
)
copy /Y "dist\TechCleanPro_%2.exe" "TechCleanPro_%2.exe"
if errorlevel 1 (
    echo.
    echo   [ERROR] No se pudo dejar TechCleanPro_%2.exe en esta carpeta.
    echo   Cierra la app si la tienes abierta (mira el icono de la bandeja,
    echo   junto al reloj: clic derecho y Salir) y vuelve a intentarlo.
    echo   El ejecutable recien compilado quedo en la carpeta dist.
    exit /b 1
)
del /q "TechCleanPro_%2_anterior.exe" >nul 2>nul
call :firmar "TechCleanPro_%2.exe"
exit /b 0

REM ------------------------------------------------------------
REM  Reescribe SOLO build_config.py con el idioma %1
REM ------------------------------------------------------------
:fijar_idioma
python -c "import io,re,sys; c=io.open('build_config.py',encoding='utf-8').read(); c=re.sub(r'^IDIOMA = \".*\"$', 'IDIOMA = \"'+sys.argv[1]+'\"', c, flags=re.M); io.open('build_config.py','w',encoding='utf-8',newline='\n').write(c)" %1
exit /b 0

REM ------------------------------------------------------------
:firmar
if "%CERT_THUMBPRINT%"=="" (
    echo   Sin firmar - no se configuro CERT_THUMBPRINT al inicio de este archivo.
    echo   Windows va a mostrar "Editor desconocido" al abrirlo. Es normal
    echo   mientras no tengas un certificado de firma de codigo.
    exit /b 0
)
where signtool >nul 2>nul
if errorlevel 1 (
    echo   [AVISO] No se encontro signtool.exe. Se instala con el "Windows SDK"
    echo   ^(componente "Windows SDK Signing Tools"^).
    echo   %~1 quedo SIN firmar por esta vez.
    exit /b 0
)
signtool sign /sha1 %CERT_THUMBPRINT% /fd SHA256 /tr %TIMESTAMP_URL% /td SHA256 %1
if errorlevel 1 (
    echo   [AVISO] La firma de %~1 fallo - revisa que el token este conectado
    echo   y que CERT_THUMBPRINT sea correcto.
) else (
    echo   %~1 firmado correctamente.
)
exit /b 0

REM ------------------------------------------------------------
:error
echo.
echo Se restaura build_config.py a espanol antes de salir.
call :fijar_idioma es
pause
exit /b 1
