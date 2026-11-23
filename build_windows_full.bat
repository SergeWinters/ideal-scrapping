@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================================
REM Idealista Scraper Pro - Windows build
REM
REM Uso:
REM   build_windows_full.bat 1.0.0
REM   build_windows_full.bat 1.0.0 --out "D:\releases"
REM   build_windows_full.bat 1.0.0 --no-zip
REM   build_windows_full.bat 1.0.0 --no-installer
REM
REM Resultado:
REM   <out>\IdealistaScraper-v1.0.0\IdealistaScraper.exe   (carpeta portable)
REM   <out>\IdealistaScraper-v1.0.0.zip
REM
REM Incluye la carpeta browser\ (Chromium portable de Playwright) junto al .exe;
REM si no existe, la descarga y prepara automáticamente con tools\update_browser.py.
REM ==========================================================

set "SOURCE_DIR=%~dp0"
if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"
set "OUT_DIR=%SOURCE_DIR%\release"
set "VERSION="
set "MAKE_ZIP=1"
set "MAKE_SETUP=0"
set "APP_NAME=IdealistaScraper"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--out" (
    if "%~2"=="" (
        echo [ERROR] Falta el valor de --out
        exit /b 1
    )
    set "OUT_DIR=%~2"
    shift
    shift
    goto :parse_args
)
if /I "%~1"=="--no-zip" (
    set "MAKE_ZIP=0"
    shift
    goto :parse_args
)
if /I "%~1"=="--installer" (
    set "MAKE_SETUP=1"
    shift
    goto :parse_args
)
if /I "%~1"=="--no-installer" (
    set "MAKE_SETUP=0"
    shift
    goto :parse_args
)
if not defined VERSION (
    set "VERSION=%~1"
    shift
    goto :parse_args
)
echo [WARN] Argumento desconocido: %~1
shift
goto :parse_args

:args_done
cd /d "%SOURCE_DIR%"

REM ---- Version: argumento o toma la actual de idealista\version.py
if not defined VERSION (
    if exist "idealista\version.py" (
        for /f "tokens=2 delims==" %%V in ('findstr /B "__version__" idealista\version.py') do set "CUR=%%~V"
        set "CUR=!CUR: =!"
        set "CUR=!CUR:"=!"
    ) else (
        set "CUR=1.0.0"
    )
    set /p "VERSION=Version a compilar [!CUR!]: "
    if not defined VERSION set "VERSION=!CUR!"
)
echo %VERSION%| findstr /R /C:"^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul || (
    echo [ERROR] Version invalida "%VERSION%". Usa el formato X.Y.Z  ^(ej: 1.0.0^)
    exit /b 1
)

set "RELEASE_NAME=%APP_NAME%-v%VERSION%"
set "RELEASE_DIR=%OUT_DIR%\%RELEASE_NAME%"

echo ========================================================
echo  Idealista Scraper BUILD  v%VERSION%
echo  Source : %SOURCE_DIR%
echo  Salida : %RELEASE_DIR%
echo ========================================================

where python >nul 2>&1 || (echo [ERROR] python no encontrado en PATH & goto :error)
if not exist "app.py" (
    echo [ERROR] No se encuentra app.py en el directorio raiz
    goto :error
)
if exist "%RELEASE_DIR%" (
    echo [WARN] Ya existe %RELEASE_DIR%. Limpiando release anterior...
    rmdir /s /q "%RELEASE_DIR%"
)

REM ----------------------------------------------------------
REM 1) Dependencias
REM ----------------------------------------------------------
echo.
echo [1/5] Comprobando dependencias...
python -c "import PySide6, playwright, cryptography, openpyxl, lxml, yaml, PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Instalando dependencias de requirements.txt y PyInstaller...
    python -m pip install -r requirements.txt PyInstaller || goto :error
)

REM ----------------------------------------------------------
REM 2) Version + icono + Chromium portable
REM ----------------------------------------------------------
echo.
echo [2/5] Fijando version %VERSION% e icono...
> "idealista\version.py" echo __version__ = "%VERSION%"
python tools\make_icon.py || goto :error

if not exist "browser\chrome-win64\chrome.exe" (
    echo [INFO] No se encontro Chromium portable. Preparando con tools\update_browser.py...
    python tools\update_browser.py || goto :error
)

REM ----------------------------------------------------------
REM 3) Limpieza
REM ----------------------------------------------------------
echo.
echo [3/5] Limpiando carpetas temporales de compilacion...
if exist "build" rmdir /s /q "build"
if exist "%APP_NAME%.spec" del /f /q "%APP_NAME%.spec"

REM ----------------------------------------------------------
REM 4) PyInstaller (carpeta portable con ventana y soporte Playwright)
REM ----------------------------------------------------------
echo.
echo [4/5] Compilando ejecutable con PyInstaller...
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name %APP_NAME% ^
    --icon "assets\app_icon.ico" ^
    --distpath "build\_out" ^
    --workpath "build\_work" ^
    --paths . ^
    --collect-all playwright ^
    --collect-all lxml ^
    --collect-all openpyxl ^
    --collect-all yaml ^
    --collect-all cryptography ^
    --hidden-import win32ctypes.core ^
    --exclude-module tkinter ^
    app.py
if %ERRORLEVEL% NEQ 0 goto :error
if not exist "build\_out\%APP_NAME%\%APP_NAME%.exe" (
    echo [ERROR] No se genero build\_out\%APP_NAME%\%APP_NAME%.exe
    goto :error
)

REM ----------------------------------------------------------
REM 5) Paquete de release
REM ----------------------------------------------------------
echo.
echo [5/5] Creando paquete portable %RELEASE_NAME%...
mkdir "%RELEASE_DIR%" || goto :error
robocopy "build\_out\%APP_NAME%" "%RELEASE_DIR%" /E /NFL /NDL /NJH /NJS >nul
if %ERRORLEVEL% GEQ 8 goto :error

REM ---- Copiar Chromium portable junto al ejecutable
if exist "browser\chrome-win64\chrome.exe" (
    echo [INFO] Copiando Chromium portable ^(Playwright^)...
    robocopy "browser" "%RELEASE_DIR%\browser" /E /NFL /NDL /NJH /NJS /XF debug.log >nul
    if !ERRORLEVEL! GEQ 8 goto :error
) else (
    echo [WARN] No existe browser\chrome-win64\chrome.exe: usara Chrome/Edge del sistema.
)

REM ---- Copiar config.yaml por defecto
if exist "config.yaml" (
    copy /Y "config.yaml" "%RELEASE_DIR%\config.yaml" >nul
)

echo Idealista Scraper Pro v%VERSION% > "%RELEASE_DIR%\LEEME.txt"
echo. >> "%RELEASE_DIR%\LEEME.txt"
echo 1. Abre %APP_NAME%.exe para iniciar la aplicacion con interfaz grafica. >> "%RELEASE_DIR%\LEEME.txt"
echo 2. Pestana "Busqueda y Filtros": selecciona tu provincia o introduce la URL de Idealista. >> "%RELEASE_DIR%\LEEME.txt"
echo 3. Pulsa "Iniciar Extraccion y Analisis". Si aparece un captcha de DataDome, resuelvelo >> "%RELEASE_DIR%\LEEME.txt"
echo    en la ventana visible del navegador y continuara automaticamente. >> "%RELEASE_DIR%\LEEME.txt"
echo 4. Pestana "Inmuebles y Analisis": visualiza los inmuebles puntuados y exporta a CSV o Excel. >> "%RELEASE_DIR%\LEEME.txt"
echo 5. Pestana "Licencia": activa tu clave ligada a este equipo con la misma llave de certificados. >> "%RELEASE_DIR%\LEEME.txt"
echo. >> "%RELEASE_DIR%\LEEME.txt"
echo PORTABLE: No requiere instalar Python ni Google Chrome. >> "%RELEASE_DIR%\LEEME.txt"
echo Incluye Chromium portable en browser\ y todos los componentes listos para usar. >> "%RELEASE_DIR%\LEEME.txt"
echo %VERSION%> "%RELEASE_DIR%\version.txt"

if "%MAKE_ZIP%"=="1" (
    echo [INFO] Comprimiendo paquete en zip...
    powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath '%OUT_DIR%\%RELEASE_NAME%.zip' -Force" || goto :error
)

REM ----------------------------------------------------------
REM Fin
REM ----------------------------------------------------------
echo.
echo ========================================================
echo  Build completado con exito.
echo --------------------------------------------------------
echo  Version : %VERSION%
echo  Carpeta : %RELEASE_DIR%
echo  Exe     : %RELEASE_DIR%\%APP_NAME%.exe
if "%MAKE_ZIP%"=="1" echo  Zip     : %OUT_DIR%\%RELEASE_NAME%.zip
echo ========================================================
goto :end

:error
echo.
echo [ERROR] Build fallido. Revisa los mensajes anteriores.
exit /b 1

:end
exit /b 0
