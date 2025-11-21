Param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$base      = $BaseUrl
$ciAlumno  = "41234567"
$ciDocente = "59876543"
$ciNuevo   = "40123456"
$ciSanc    = "42222222"

$fechasNegocio = @(
    "2030-01-10", "2030-01-11", "2030-01-12",
    "2030-02-12", "2030-02-13", "2030-02-14", "2030-02-15",
    "2030-03-01", "2030-03-02"
)
$fechasSancion = @("2030-03-01", "2030-05-01")

Write-Host "== Smoke FULL BD1 =="
Write-Host "Base URL: $base"

# Limpieza previa para idempotencia
$bodyClean = @{ participantes = @($ciAlumno, $ciDocente, $ciNuevo, $ciSanc); fechas = ($fechasNegocio + $fechasSancion) } | ConvertTo-Json
try {
    Write-Host "`n[0] Limpiando datos de smoke" -ForegroundColor Yellow
    Invoke-RestMethod "$base/admin/limpiar-smoke" -Method POST -ContentType "application/json" -Body $bodyClean | Out-Null
} catch {
    Write-Warning "No se pudo limpiar datos de smoke. Verificar API. Detalle: $($_.Exception.Message)"
}

Write-Host "`n[1] /health, /turnos, /edificios, /salas"
irm "$base/health"
irm "$base/turnos"    | Select-Object -First 5
irm "$base/edificios"
irm "$base/salas"

Write-Host "`n[2] Ejecutando scripts/smoke_negocio.ps1 (reglas diario + sanción + semanal + rol)"
& "$PSScriptRoot/smoke_negocio.ps1" -BaseUrl $base

Write-Host "`n[3] CRUD Participantes (incluye seed + nuevo)"

Write-Host "`n[3.1] GET /participantes/$ciAlumno (seed-eado)"
try {
    $pSeed = irm "$base/participantes/$ciAlumno"
    Write-Host "Participante seed-eado encontrado correctamente."; $pSeed
} catch {
    Write-Host "¡¡OJO!! No se encontró el participante seed-eado."; $_.ErrorDetails.Message
}

Write-Host "`n[3.2] POST /participantes (nuevo $ciNuevo)"
$bodyNew = @{ ci=$ciNuevo; nombre="Prueba"; apellido="Temporal"; email="prueba$temp@ucu.edu.uy"; tipo_participante="estudiante" } | ConvertTo-Json
try {
    $nuevo = Invoke-RestMethod "$base/participantes" -Method POST -ContentType "application/json" -Body $bodyNew -ErrorAction Stop
    Write-Host "Participante nuevo creado correctamente."; $nuevo
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 409) {
        Write-Host "Participante de prueba ya existía; se reutiliza."; $_.ErrorDetails.Message
    } else { throw }
}

Write-Host "`n[3.3] PUT /participantes/$ciNuevo (editar datos, CI inmutable)"
$bodyUpd = @{ nombre="Prueba"; apellido="Persistente"; email="prueba$temp@ucu.edu.uy"; tipo_participante="estudiante" } | ConvertTo-Json
try {
    $edit = irm "$base/participantes/$ciNuevo" -Method PUT -ContentType "application/json" -Body $bodyUpd
    Write-Host "Participante editado correctamente (sin cambiar CI)."; $edit
} catch { $_.ErrorDetails.Message }

Write-Host "`n[3.4] DELETE /participantes/$ciAlumno (debería fallar SOLO si tiene reservas/sanciones/programas)"
try {
    irm "$base/participantes/$ciAlumno" -Method DELETE -ErrorAction Stop | Out-Null
    Write-Host "¡¡OJO!! El participante seed se eliminó y no debería."
} catch {
    Write-Host "DELETE seed-eado devolvió:"; $_.ErrorDetails.Message
}

Write-Host "`n[3.5] DELETE /participantes/$ciNuevo (debería poder borrarse sin 409 falso)"
try {
    irm "$base/participantes/$ciNuevo" -Method DELETE -ErrorAction Stop | Out-Null
    Write-Host "Participante de prueba $ciNuevo eliminado correctamente (sin asociaciones)."
} catch {
    Write-Host "¡¡OJO!! No se pudo eliminar al participante de prueba."; $_.ErrorDetails.Message
}

Write-Host "`n[4] ROL vs tipo de sala (exclusivas vs libres)"
Write-Host "(cubierto también en smoke_negocio, se consulta disponibilidad para verificar estado)"
irm "$base/disponibilidad?fecha=2030-03-01&edificio=Campus%20Pocitos&nombre_sala=Sala%20P1" | Select-Object -First 3
irm "$base/disponibilidad?fecha=2030-03-02&edificio=Campus%20Pocitos&nombre_sala=Sala%20P1" | Select-Object -First 3

Write-Host "`n[5] Sanciones: CRUD manual sobre participante de prueba"

Write-Host "`n[5.1] Crear participante sancionable ($ciSanc) si no existe"
$bodySancPart = @{ ci=$ciSanc; nombre="Sancionable"; apellido="Temporal"; email="sancionable$temp@ucu.edu.uy"; tipo_participante="estudiante" } | ConvertTo-Json
try {
    irm "$base/participantes/$ciSanc" -ErrorAction Stop | Out-Null
    Write-Host "Participante sancionable ya existe; se reutiliza."
} catch {
    try {
        $pSanc = Invoke-RestMethod "$base/participantes" -Method POST -ContentType "application/json" -Body $bodySancPart -ErrorAction Stop
        Write-Host "Participante sancionable creado."; $pSanc
    } catch { Write-Host "¡¡OJO!! No se pudo crear el participante sancionable $ciSanc."; $_.ErrorDetails.Message }
}

Write-Host "`n[5.2] Crear sanción manual (idempotente)"
$bodySanc = @{ ci=$ciSanc; fecha_inicio=$fechasSancion[0]; fecha_fin=$fechasSancion[1] } | ConvertTo-Json
try {
    $sancNueva = Invoke-RestMethod "$base/sanciones" -Method POST -ContentType "application/json" -Body $bodySanc -ErrorAction Stop
    Write-Host "Sanción manual creada."; $sancNueva
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 409) {
        Write-Host "Sanción ya existía; se considera OK."; $_.ErrorDetails.Message
    } else { throw }
}

Write-Host "`n[5.3] GET /sanciones?ci=$ciSanc"
irm "$base/sanciones?ci=$ciSanc"

Write-Host "`n[5.4] Intentar reservar durante sanción manual (debería FALLAR)"
$bodyBloqueo = @{ nombre_sala="Sala 101"; edificio="Sede Central"; fecha=$fechasSancion[0]; id_turno=14; participantes=@($ciSanc) } | ConvertTo-Json -Depth 5
try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyBloqueo -ErrorAction Stop | Out-Null
    Write-Host "¡¡OJO!! La reserva durante sanción se creó y NO debería."
} catch {
    Write-Host "Reserva rechazada por sanción manual como se esperaba (ver mensaje)."; $_.ErrorDetails.Message
}

Write-Host "`n[5.5] DELETE sanción y luego DELETE participante sancionable"
try {
    irm "$base/sanciones/$ciSanc/$($fechasSancion[0])" -Method DELETE -ErrorAction Stop | Out-Null
} catch {
    Write-Host "Aviso: la sanción ya no estaba presente."; $_.ErrorDetails.Message
}

# Limpiar reservas potenciales del participante sancionable en las fechas de prueba
$bodyCleanSanc = @{ participantes = @($ciSanc); fechas = $fechasSancion } | ConvertTo-Json
try { Invoke-RestMethod "$base/admin/limpiar-smoke" -Method POST -ContentType "application/json" -Body $bodyCleanSanc | Out-Null } catch { }

try {
    irm "$base/participantes/$ciSanc" -Method DELETE -ErrorAction Stop | Out-Null
    Write-Host "Participante sancionable eliminado tras limpiar sanciones/reservas."
} catch {
    Write-Host "¡¡OJO!! No se pudo eliminar participante sancionable tras limpiar sanciones."; $_.ErrorDetails.Message
}

Write-Host "`n== Smoke FULL BD1 terminado =="
