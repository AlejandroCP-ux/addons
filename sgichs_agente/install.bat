@echo off
:: BatchGotAdmin
:-------------------------------------
REM  --> Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

REM --> If error flag set, we do not have admin.
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"
:--------------------------------------

:: SCRIPT STARTS HERE
TITLE Instalador del Agente de Activos de TI

echo.
echo ===================================================
echo   Instalador del Agente de Activos de TI
echo ===================================================
echo.

REM --- Variables ---
SET "EXE_NAME=AgenteActivosTI.exe"
SET "CONFIG_NAME=config_agente.json"
SET "INSTALL_DIR=%ProgramFiles%\AgenteActivosTI"
SET "SHORTCUT_NAME=Agente de Activos de TI.lnk"
SET "STARTUP_SHORTCUT_PATH=%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\StartUp\%SHORTCUT_NAME%"

echo Directorio de instalacion: %INSTALL_DIR%
echo.

REM --- Crear directorio de instalacion ---
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo Directorio de instalacion creado.
)

REM --- Copiar archivos ---
echo Copiando archivos necesarios...
copy /Y "%~dp0\%EXE_NAME%" "%INSTALL_DIR%\"
copy /Y "%~dp0\%CONFIG_NAME%" "%INSTALL_DIR%\"

if %errorlevel% NEQ 0 (
    echo.
    echo ERROR: No se pudieron copiar los archivos. Asegurate de que '%EXE_NAME%' y '%CONFIG_NAME%' estan en la misma carpeta que este script.
    goto End
)

REM --- Crear acceso directo en el inicio de Windows para todos los usuarios ---
echo Creando acceso directo para inicio automatico...
set "VBS_CMD=mshta vbscript:Execute("Set a=CreateObject(""WScript.Shell""):Set b=a.CreateShortcut(a.ExpandEnvironmentStrings(""%STARTUP_SHORTCUT_PATH%"")):b.TargetPath=""""%INSTALL_DIR%\%EXE_NAME%"""":b.WorkingDirectory=""""%INSTALL_DIR%"""":b.Save:close")"
%VBS_CMD%

echo.
echo ===================================================
echo  Instalacion completada exitosamente!
echo ===================================================
echo El agente se iniciara automaticamente la proxima vez que cualquier usuario inicie sesion.

:End
echo.
pause
