@echo off
setlocal enabledelayedexpansion

chcp 65001 > nul

set "module_path=%~1"
if "%module_path%"=="" (
    echo Por favor, arrastra y suelta la carpeta del módulo sobre este script o escribe su ruta.
    set /p "module_path=Ingresa la ruta del módulo: "
)

if not exist "%module_path%" (
    echo La ruta especificada no existe.
    pause
    exit /b 1
)

rem Obtener nombre de la carpeta desde la ruta
for %%A in ("%module_path%") do set "folder_name=%%~nxA"

rem Definir archivo de salida con el nombre requerido
set "output_file=%~dp0description for !folder_name!.txt"

rem Extensiones a excluir (agregar más si es necesario)
set "exclude_exts=.pyc .exe .dll .png .jpg .jpeg .gif .bmp .bin .svg .ico .msi .bat .cmd .po .pot .mp4"

echo Generando archivo de salida...
echo. > "!output_file!"

for /r "%module_path%" %%f in (*) do (
    rem Obtener extensión del archivo
    set "file_ext=%%~xf"
    
    rem Verificar si la extensión está en la lista de exclusiones (case-insensitive)
    echo !exclude_exts! | findstr /i /c:"!file_ext!" > nul
    if not errorlevel 1 (
        echo Skipping: %%~nxf
    ) else (
        echo Procesando: %%~nxf
        echo. >> "!output_file!"
        echo ==== Archivo: %%f ==== >> "!output_file!"
        echo. >> "!output_file!"
        type "%%f" >> "!output_file!" 2> nul
        echo. >> "!output_file!"
    )
)

echo ¡Proceso completado! Archivo generado: "!output_file!"
pause