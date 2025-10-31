param(
  [switch]$KeepApi,
  [string]$Tag="(working-copy)"
)
$ErrorActionPreference = "Stop"
Write-Host "== PROF CHECK =="

# (a) puerto para DB
$port = 3306
if (Get-NetTCPConnection -LocalPort 3306 -ErrorAction SilentlyContinue) { $port = 3307 }
if (Test-Path .\.env) {
  (Get-Content .\.env) -replace '^DB_PORT=.*$', "DB_PORT=$port" | Set-Content .\.env
} else {
  Copy-Item .\.env.example .\.env -Force
  (Get-Content .\.env) -replace '^DB_PORT=.*$', "DB_PORT=$port" | Set-Content .\.env
}
Write-Host "DB_PORT=$port"

# (b) docker up
docker compose up -d
docker compose ps | Write-Host
docker compose logs -f db | Select-Object -First 10 | Out-Null

# (c) venv + deps
if (!(Test-Path .\.venv\Scripts\python.exe)) { py -m venv .venv }
$py = Join-Path (Resolve-Path .\.venv\Scripts) 'python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

# (d) levantar API (otra consola PowerShell) usando run.ps1 que carga .env
$api = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command",". .\.venv\Scripts\Activate.ps1; .\scripts\run.ps1" -PassThru
Start-Sleep -Seconds 2

# (e) esperar /health
$ok=$false
for($i=0;$i -lt 30;$i++){
  try{ $h=irm "http://127.0.0.1:8000/health"; if($h.status -eq "ok"){ $ok=$true; break } }catch{ Start-Sleep -Milliseconds 500 }
}
if(-not $ok){ throw "API no respondió /health" }

function Assert($cond,$msg){ if(-not $cond){ throw "FAIL: $msg" } else { Write-Host "PASS:" $msg } }

# (f) smoke CRUD turnos
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
  # apagar API para no dejar procesos colgados
  Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'uvicorn' } | Stop-Process -Force
  Write-Host "API detenida. Adminer sigue en http://localhost:8080"
}else{
  Write-Host "API se mantiene en http://127.0.0.1:8000/docs (flag -KeepApi)"
}
