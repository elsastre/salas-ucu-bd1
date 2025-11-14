param(
  [switch]$KeepApi,
  [switch]$Clean,
  [int]$TimeoutSec = 150,
  [string]$Tag="(working-copy)"
)
$ErrorActionPreference = "Stop"
Write-Host "== PROF CHECK =="

# A) Docker Desktop listo
try { docker info | Out-Null } catch {
  $exe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $exe) {
    Write-Host "-> Iniciando Docker Desktop..."
    Start-Process $exe | Out-Null
    $ok=$false; for($i=0;$i -lt $TimeoutSec/2;$i++){ try{ docker info | Out-Null; $ok=$true; break }catch{ Start-Sleep 2 } }
    if(-not $ok){ throw "Docker Desktop no arrancó a tiempo." }
  } else { throw "Docker Desktop no está instalado." }
}

# B) Puerto host libre para MySQL (3306 -> 3307 -> 3308)
$choices = 3306,3307,3308
$port = $choices | Where-Object { -not (Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue) } | Select-Object -First 1
if (-not $port) { throw "No hay puertos libres en {3306,3307,3308}." }
$Env:DB_PORT = $port
Write-Host "DB_PORT(host) -> $port"

# C) .env coherente para la API (corre en host)
if (!(Test-Path .\.env) -and (Test-Path .\.env.example)) { Copy-Item .\.env.example .\.env -Force }
$envTxt = if (Test-Path .\.env) { Get-Content .\.env -Raw } else { "" }
function Upsert([string]$k,[string]$v) {
  $p = "(?m)^$([regex]::Escape($k))=.*$"
  if ($envTxt -match $p) { $script:envTxt = $envTxt -replace $p, "$k=$v" } else { $script:envTxt += "`r`n$k=$v" }
}
Upsert "DB_HOST" "127.0.0.1"
Upsert "DB_PORT" "$port"
Upsert "DB_USER" "root"
Upsert "DB_PASSWORD" "root"
Upsert "DB_NAME" "salas_db"
Set-Content -Encoding utf8 .\.env $envTxt

# D) Limpieza opcional
if ($Clean -and (Test-Path .\docker-compose.yml)) {
  docker compose down --volumes --remove-orphans
}

# E) Levantar Docker y esperar healthy
docker compose up -d
$deadline = (Get-Date).AddSeconds($TimeoutSec)
do {
  $dbId = (docker compose ps -q db) 2>$null
  if ($dbId) { $st = (docker inspect -f "{{.State.Health.Status}}" $dbId) 2>$null }
  if ($st -eq "healthy") { break }
  Start-Sleep 1
} while ((Get-Date) -lt $deadline)
if ($st -ne "healthy") { throw "MySQL no llegó a healthy a tiempo." }

# F) venv + deps
if (!(Test-Path .\.venv\Scripts\python.exe)) { py -m venv .venv }
$py = Join-Path (Resolve-Path .\.venv\Scripts) 'python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

# G) levantar API (usa run.ps1 que carga .env)
$api = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command",". .\.venv\Scripts\Activate.ps1; .\scripts\run.ps1" -PassThru
Start-Sleep -Seconds 2

# H) /health
$ok=$false
for($i=0;$i -lt 60;$i++){ try{ if((irm "http://127.0.0.1:8000/health").status -eq "ok"){ $ok=$true; break } }catch{ Start-Sleep 1 } }
if(-not $ok){ throw "API no respondió /health." }

function Assert($c,$m){ if(-not $c){ throw "FAIL: $m" } else { Write-Host "PASS:" $m } }

# I) Smoke CRUD turnos
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
$gone=$false; try{ irm "http://127.0.0.1:8000/turnos/99" | Out-Null }catch{ if ($_.Exception.Response.StatusCode.value__ -eq 404){ $gone=$true } }
Assert $gone "DELETE /turnos/99 -> 404"

Write-Host "`nSmoke OK ✅  Tag: $Tag"
if(-not $KeepApi){
  Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'uvicorn' } | Stop-Process -Force
  Write-Host "API detenida. Adminer sigue en http://localhost:8080"
}else{
  Write-Host "API se mantiene en http://127.0.0.1:8000/docs (flag -KeepApi)"
}
