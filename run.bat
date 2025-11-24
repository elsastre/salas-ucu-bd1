@echo off
setlocal enabledelayedexpansion

set RESET_DB=0
if /I "%~1"=="--reset-db" set RESET_DB=1

set API_PORT=
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B "API_PORT=" .env`) do (
        if /I "%%A"=="API_PORT" set "API_PORT=%%B"
    )
)
if "!API_PORT!"=="" set "API_PORT=8000"

if %RESET_DB%==1 (
    docker compose down --volumes
)

docker compose up -d --build

set "BASE_URL=http://localhost:!API_PORT!"
echo UI:   !BASE_URL!/ui
echo Docs: !BASE_URL!/docs
echo Adminer: http://localhost:8080

start "" "!BASE_URL!/ui"
start "" "!BASE_URL!/docs"
start "" "http://localhost:8080"
