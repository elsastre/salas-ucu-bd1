@echo off
setlocal enabledelayedexpansion

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

set HEALTH_URL=http://127.0.0.1:8000/health
set /a retries=60
echo Esperando a que la API responda en %HEALTH_URL% ...
:wait
powershell -Command "try { $r = Invoke-WebRequest -UseBasicParsing %HEALTH_URL%; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel%==0 goto ready
set /a retries-=1
if %retries% LEQ 0 goto fail
timeout /t 2 >nul
goto wait

:ready
echo API lista. Abriendo navegador...
start "" http://127.0.0.1:8000/docs
start "" http://127.0.0.1:8000/ui
echo Listo. Usa docker compose logs para ver los registros.
exit /b 0

:fail
echo Tiempo de espera agotado. Revisa los logs con "docker compose logs api".
exit /b 1
