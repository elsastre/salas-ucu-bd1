param([int]$Port=8000)
$ErrorActionPreference = "Stop"
# venv ya activado por el caller; aseguramos .env
if (!(Test-Path ".\.env") -and (Test-Path ".\.env.example")) { Copy-Item ".\.env.example" ".\.env" -Force }
python -m uvicorn src.app:app --host 127.0.0.1 --port $Port --env-file .env
