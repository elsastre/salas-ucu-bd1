@echo off
setlocal enabledelayedexpansion

REM Uso: run.bat [--reset-db]
REM Levanta los contenedores y abre las URLs principales.

set RESET_DB=0
if /I "%1"=="--reset-db" (
    set RESET_DB=1
)

REM Leer API_PORT desde .env si existe
set API_PORT=
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%A in (`findstr /B "API_PORT=" .env`) do (
        set "API_PORT=%%B"
    )
)
if "!API_PORT!"=="" set "API_PORT=8000"

if %RESET_DB%==1 (
    echo Reiniciando base de datos (docker compose down --volumes)...
    docker compose down --volumes
)

echo Levantando contenedores con docker compose...
docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] No se pudieron levantar los contenedores.
    exit /b 1
)

set "BASE_URL=http://localhost:!API_PORT!"
echo.
echo Servicios en marcha (espera unos segundos si es la primera vez):
echo    UI:   !BASE_URL!/ui
echo    Docs: !BASE_URL!/docs
echo    Adminer: http://localhost:8080
echo.
echo Abriendo navegador...
start "" "!BASE_URL!/ui"
start "" "!BASE_URL!/docs"
start "" "http://localhost:8080"

echo Listo. Usa "docker compose logs" para ver los registros.
exit /b 0
