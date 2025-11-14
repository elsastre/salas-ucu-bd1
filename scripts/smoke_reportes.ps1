Param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$base = $BaseUrl

Write-Host "== Smoke reportes BD1 =="

Write-Host "`n[1] /reportes/salas-mas-usadas (top 5)"
irm "$base/reportes/salas-mas-usadas?limit=5"

Write-Host "`n[1.b] /reportes/salas-mas-usadas (noviembre 2025)"
irm "$base/reportes/salas-mas-usadas?limit=5&desde=2025-11-01&hasta=2025-11-30"

Write-Host "`n[2] /reportes/ocupacion-por-edificio"
irm "$base/reportes/ocupacion-por-edificio"

Write-Host "`n[2.b] /reportes/ocupacion-por-edificio (noviembre 2025)"
irm "$base/reportes/ocupacion-por-edificio?desde=2025-11-01&hasta=2025-11-30"

Write-Host "`n[3] /reportes/uso-por-rol"
irm "$base/reportes/uso-por-rol"

Write-Host "`n[3.b] /reportes/uso-por-rol (noviembre 2025)"
irm "$base/reportes/uso-por-rol?desde=2025-11-01&hasta=2025-11-30"

Write-Host "`n== Smoke reportes BD1 terminado =="
