param(
  [switch]$KeepApi,
  [switch]$Clean,
  [int]$TimeoutSec = 120,
  [string]$Tag="(working-copy)"
)
$ErrorActionPreference = "Stop"
Write-Host "== PROF CHECK =="

# A) Docker Desktop listo
try { docker info | Out-Null } catch {
  $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerExe) {
    Write-Host "-> Docker Desktop no estaba corriendo. Iniciando..."
    Start-Process $dockerExe | Out-Null
    $ok=$false; for($i=0;$i -lt $TimeoutSec/2;$i++){ try { docker info | Out-Null; $ok=$true; break } catch { Start-Sleep 2 } }
    if(-not $ok){ throw "Docker Desktop no arrancó a tiempo. Abrilo y reintentá." }
  } else {
    throw "Docker Desktop no está disponible en este equipo."
  }
}

# B) Limpieza opcional
if ($Clean -and (Test-Path .\docker-compose.yml)) {
  Write-Host "-> Limpiando contenedores/volúmenes previos..."
  docker compose down --volumes --remove-orphans
}

# C) Levantar servicios
docker compose up -d

# Esperar a que db esté healthy
$deadline = (Get-Date).AddSeconds($TimeoutSec)
do {
  $dbId = (docker compose ps -q db).Trim()
  if (-not $dbId) { Start-Sleep 1; continue }
  $status = (docker inspect -f "{{.State.Health.Status}}" $dbId) 2>$null
  if ($status -eq "healthy") { break }
  Start-Sleep 1
} while ((Get-Date) -lt $deadline)
if ($status -ne "healthy") { throw "MySQL no llegó a healthy a tiempo." }

# D) Descubrir puerto host real y alinear .env
$hostPort = (docker compose port db 3306) -replace '.*:',''
if (-not $hostPort) { throw "No pude obtener el puerto host de MySQL." }
Write-Host "DB_PORT(host) -> $hostPort"

$envPath = ".\.env"
if (!(Test-Path $envPath)) { Copy-Item .\.env.example $envPath -Force }
$envText = Get-Content $envPath -Raw
function UpsertEnv([string]$k,[string]$v) {
  $pattern = "(?m)^$([regex]::Escape($k))=.*$"
  if ($envText -match $pattern) { $script:envText = $envText -replace $pattern, "$k=$v" }
  else { $script:envText += "`r`n$k=$v" }
}
UpsertEnv "DB_HOST" "127.0.0.1"
UpsertEnv "DB_PORT" "$hostPort"
UpsertEnv "DB_USER" "root"
UpsertEnv "DB_PASSWORD" "root"
UpsertEnv "DB_NAME" "salas_db"
Set-Content -Encoding utf8 $envPath $envText

# E) Venv + deps
if (!(Test-Path .\.venv\Scripts\python.exe)) { py -m venv .venv }
$py = Join-Path (Resolve-Path .\.venv\Scripts) 'python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

# F) Levantar API en otra consola (carga .env desde run.ps1)
$api = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command",". .\.venv\Scripts\Activate.ps1; .\scripts\run.ps1" -PassThru
Start-Sleep -Seconds 2

# G) Esperar /health
$ok=$false
for($i=0;$i -lt 60;$i++){
  try{ $h=irm "http://127.0.0.1:8000/health"; if($h.status -eq "ok"){ $ok=$true; break } }catch{ Start-Sleep -Milliseconds 500 }
}
if(-not $ok){ throw "API no respondió /health." }

function Assert($cond,$msg){ if(-not $cond){ throw "FAIL: $msg" } else { Write-Host "PASS:" $msg } }

# H) Smoke CRUD turnos
$t = irm "http://127.0.0.1:8000/turnos"
Assert ($t.Count -ge 15) "GET /turnos >= 15"

$create = @{ id_turno=99; hora_inicio="07:00:00"; hora_fin="08:00:00" } | ConvertTo-Json
$r = irm "http://127.0.0.1:8000/turnos" -Method POST -Body $create -ContentType 'application/json'
Assert ($r.id_turno -eq 99) "POST /turnos crea 99"

$dup=$false
try{ irm "http://127.0.0.1:8000/turnos" -Method POST -Body $create -ContentType 'application/json' | Out-Null }catch{ if($_.Exception.Response.StatusCode.value__ -eq 409){$dup=$true}}
Assert $dup "POST duplicado -> 409"

$bad = @{ id_turno=100; hora_inicio="09:00:00"; hora_fin="08:00:00" } | ConvertTo-Json
$val=$false
try{ irm "http://127.0.0.1:8000/turnos" -Method POST -Body $bad -ContentType 'application/json' | Out-Null }catch{ if($_.Exception.Response.StatusCode.value__ -eq 422){$val=$true}}
Assert $val "Validación -> 422"

$upd = @{ hora_inicio="07:30:00"; hora_fin="08:30:00" } | ConvertTo-Json
$u = irm "http://127.0.0.1:8000/turnos/99" -Method PUT -Body $upd -ContentType 'application/json'
Assert ($u.hora_inicio -eq "07:30:00") "PUT /turnos/99"

irm "http://127.0.0.1:8000/turnos/99" -Method DELETE | Out-Null
$gone=$false; try{ irm "http://127.0.0.1:8000/turnos/99" | Out-Null }catch{ if($_.Exception.Response.StatusCode.value__ -eq 404){$gone=$true}}
Assert $gone "DELETE /turnos/99 -> 404"

Write-Host "`nSmoke OK ✅  Tag: $Tag"

if(-not $KeepApi){
  Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'uvicorn' } | Stop-Process -Force
  Write-Host "API detenida. Adminer sigue en http://localhost:8080"
} else {
  Write-Host "API se mantiene en http://127.0.0.1:8000/docs (flag -KeepApi)"
}
