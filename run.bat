@echo off
setlocal enabledelayedexpansion

set MODE=%1
if "%MODE%"=="" set MODE=run

REM Verificar Docker
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no esta en el PATH. Instala/abre Docker Desktop.
    exit /b 1
)

echo Construyendo y levantando contenedores...
docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] No se pudieron levantar los contenedores.
    exit /b 1
)

if "%API_PORT%"=="" set API_PORT=8000
set HEALTH_URL=http://127.0.0.1:%API_PORT%/health
set BASE_URL=http://127.0.0.1:%API_PORT%
set /a retries=60
echo Esperando a que la API responda en %HEALTH_URL% ...
:wait
powershell -NoLogo -Command "try { $r = Invoke-WebRequest -UseBasicParsing %HEALTH_URL%; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel%==0 goto ready
set /a retries-=1
if %retries% LEQ 0 goto fail
timeout /t 2 >nul
goto wait

:ready
if /I "%MODE%"=="run" goto ui
if /I "%MODE%"=="test" goto smoke

echo [ERROR] Modo desconocido: %MODE%
exit /b 1

:ui
echo API lista. Abriendo navegador...
start "" %BASE_URL%/docs
start "" %BASE_URL%/ui
echo Listo. Usa docker compose logs para ver los registros.
echo Ejecuta "run.bat test" para correr los smoke tests completos antes de entregar.
exit /b 0

:smoke
echo API lista. Ejecutando smoke tests (negocio + full)...

set overall=0

echo.> smoke_negocio.log
powershell -NoLogo -Command "& { & '.\scripts\smoke_negocio.ps1' -BaseUrl '%BASE_URL%' }" ^> smoke_negocio.log
set rc_negocio=%ERRORLEVEL%
type smoke_negocio.log
findstr /C:"¡¡OJO!!" smoke_negocio.log >nul
if %ERRORLEVEL%==0 set rc_negocio=2
if not %rc_negocio%==0 set overall=1

echo.> smoke_full.log
powershell -NoLogo -Command "& { & '.\scripts\smoke_full.ps1' -BaseUrl '%BASE_URL%' }" ^> smoke_full.log
set rc_full=%ERRORLEVEL%
type smoke_full.log
findstr /C:"¡¡OJO!!" smoke_full.log >nul
if %ERRORLEVEL%==0 set rc_full=2
if not %rc_full%==0 set overall=1

if exist scripts\smoke_reportes.ps1 (
    echo.> smoke_reportes.log
    powershell -NoLogo -Command "& { & '.\scripts\smoke_reportes.ps1' -BaseUrl '%BASE_URL%' }" ^> smoke_reportes.log
    set rc_reportes=%ERRORLEVEL%
    type smoke_reportes.log
    findstr /C:"¡¡OJO!!" smoke_reportes.log >nul
    if %ERRORLEVEL%==0 set rc_reportes=2
    if not %rc_reportes%==0 set overall=1
)

if %overall%==0 (
    echo Todas las verificaciones de smoke finalizaron sin alertas.
    exit /b 0
) else (
    echo.
    echo =====================================
    echo Se detectaron fallos o alertas en smoke.
    echo Revisar los archivos smoke_*.log para mas detalle.
    echo El comando devolvera codigo distinto de cero.
    echo =====================================
    exit /b 1
)

:fail
echo Tiempo de espera agotado. Revisa los logs con "docker compose logs api".
exit /b 1
