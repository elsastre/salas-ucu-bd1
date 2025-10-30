param([string]$EnvFile = ".env")

# Cargar variables desde .env si existe
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match "^\s*#") { return }
    if ($_ -match "^\s*$") { return }
    $k, $v = $_.Split("=",2)
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
  }
}

# Levantar FastAPI
python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
