@echo off
chcp 65001 >nul
title TechClean - Generador de la Edicion Administrador
REM Se trabaja desde la RAIZ del proyecto, no desde compilar: asi las
REM rutas relativas que ya habia (assets, requirements.txt, dist, el
REM .exe de salida) siguen valiendo tal cual.
cd /d "%~dp0.."
echo ============================================================
echo   TechClean - Edicion ADMINISTRADOR
echo ============================================================
echo.
echo Esta version muestra la Consola Dev y los comandos tecnicos
echo exactos de cada accion, sin ocultar nada. Es para uso propio
echo o de soporte tecnico, NO para repartir al usuario final
echo (para eso usa Generar_App_Instalable.bat, la version cliente).
echo.
echo (Puede tardar 1-3 minutos la primera vez. No cierres esta ventana.)
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
    echo Instala Python desde https://www.python.org/downloads/
    echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo [1/5] Instalando lo necesario para compilar...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Limpiando restos de compilaciones anteriores (para evitar usar codigo viejo por error)...
rmdir /s /q build >nul 2>nul
rmdir /s /q dist >nul 2>nul
del /q "TechClean_Admin.spec" >nul 2>nul
if exist "codigo\__pycache__" rmdir /s /q "codigo\__pycache__" >nul 2>nul

echo.
echo [2/5] Compilando la Edicion Administrador...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechClean_Admin" --add-data "assets;assets" --paths codigo codigo\main_admin.py

if not exist "dist\TechClean_Admin.exe" (
    echo.
    echo [ERROR] Algo fallo durante la compilacion. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo [3/5] Copiando el resultado a esta misma carpeta...
REM BUG corregido: este copy mandaba su salida a nul, asi que cuando fallaba
REM nadie se enteraba. Y falla de verdad: si el .exe anterior esta ABIERTO
REM (tipico, porque uno lo deja minimizado en la bandeja para probarlo),
REM Windows no deja sobreescribirlo. El script seguia diciendo "Listo" y en
REM la carpeta quedaba el ejecutable VIEJO.
REM
REM El arreglo ya estaba en Generar_App_Instalable.bat, pero a este generador
REM nunca llego: dos copias del mismo paso, el arreglo solo en una.
REM
REM Truco: Windows SI deja renombrar un .exe en ejecucion (el candado es
REM sobre el contenido, no sobre el nombre). Se aparta el viejo y se copia el
REM nuevo en su lugar; el que este corriendo sigue vivo sin enterarse.
if exist "TechClean_Admin.exe" (
    del /q "TechClean_Admin_anterior.exe" >nul 2>nul
    ren "TechClean_Admin.exe" "TechClean_Admin_anterior.exe" >nul 2>nul
)
copy /Y "dist\TechClean_Admin.exe" "TechClean_Admin.exe"
if errorlevel 1 (
    echo.
    echo   [ERROR] No se pudo dejar TechClean_Admin.exe en esta carpeta.
    REM Ojo: NADA de parentesis sueltos dentro de un bloque if ^(...^) —
    REM cmd cierra el bloque en el primer ^) que encuentra y revienta con
    REM "No se esperaba y en este momento". Van escapados con ^.
    echo   Cierra la app si la tienes abierta: mira el icono de la bandeja,
    echo   junto al reloj, clic derecho y Salir. Luego vuelve a intentarlo.
    echo   El ejecutable recien compilado quedo en la carpeta dist.
    pause
    exit /b 1
)
del /q "TechClean_Admin_anterior.exe" >nul 2>nul

echo.
echo [4/5] Firma digital...
if "%CERT_THUMBPRINT%"=="" (
    echo Sin firmar - no se configuro CERT_THUMBPRINT al inicio de este archivo.
    echo Windows va a mostrar "Editor desconocido" al abrirlo. Esto es normal
    echo mientras no tengas un certificado de firma de codigo.
) else (
    where signtool >nul 2>nul
    if errorlevel 1 (
        echo [AVISO] No se encontro signtool.exe. Se instala con el "Windows SDK"
        echo ^(componente "Windows SDK Signing Tools"^) - https://developer.microsoft.com/windows/downloads/windows-sdk/
        echo El .exe quedo SIN firmar por esta vez.
    ) else (
        signtool sign /sha1 %CERT_THUMBPRINT% /fd SHA256 /tr %TIMESTAMP_URL% /td SHA256 "TechClean_Admin.exe"
        if errorlevel 1 (
            echo [AVISO] La firma fallo - revisa que el token este conectado y CERT_THUMBPRINT sea correcto.
        ) else (
            echo Firmado correctamente.
        )
    )
)

echo.
echo [5/5] Limpiando archivos temporales de la compilacion...
rmdir /s /q build >nul 2>nul
del /q "TechClean_Admin.spec" >nul 2>nul

echo.
echo ============================================================
echo   Listo. TechClean_Admin.exe ya esta en esta carpeta.
echo ============================================================
echo.
pause
