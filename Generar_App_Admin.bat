@echo off
chcp 65001 >nul
title TechClean Pro - Generador de la Edicion Administrador
echo ============================================================
echo   TechClean Pro - Edicion ADMINISTRADOR
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
del /q "TechCleanPro_Admin.spec" >nul 2>nul
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>nul

echo.
echo [2/5] Compilando la Edicion Administrador...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --icon "assets\icono.ico" --name "TechCleanPro_Admin" --add-data "assets;assets" main_admin.py

if not exist "dist\TechCleanPro_Admin.exe" (
    echo.
    echo [ERROR] Algo fallo durante la compilacion. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo [3/5] Copiando el resultado a esta misma carpeta...
copy /Y "dist\TechCleanPro_Admin.exe" "TechCleanPro_Admin.exe" >nul

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
        signtool sign /sha1 %CERT_THUMBPRINT% /fd SHA256 /tr %TIMESTAMP_URL% /td SHA256 "TechCleanPro_Admin.exe"
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
del /q "TechCleanPro_Admin.spec" >nul 2>nul

echo.
echo ============================================================
echo   Listo. TechCleanPro_Admin.exe ya esta en esta carpeta.
echo ============================================================
echo.
pause
