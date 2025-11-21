Param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$base      = $BaseUrl
$ciAlumno  = "41234567"   # Matihas (grado)
$ciDocente = "59876543"   # Ada (docente posgrado)
$ciCapA    = "43333333"   # Beto (estudiante)
$ciCapB    = "44444444"   # Caro (estudiante)

# Idempotencia: limpiar huellas de ejecuciones previas en las fechas de prueba
$fechasSmoke = @(
    "2030-01-10", "2030-01-11", "2030-01-12", # límite diario + sanción
    "2030-02-12", "2030-02-13", "2030-02-14", "2030-02-15", # límite semanal
    "2030-03-01", "2030-03-02", # rol vs sala posgrado
    "2030-04-01",                 # capacidad de sala
    "2030-04-10", "2030-04-11", "2030-04-12" # exención diaria/semanal en sala posgrado
)
$bodyClean = @{ participantes = @($ciAlumno, $ciDocente, $ciCapA, $ciCapB); fechas = $fechasSmoke } | ConvertTo-Json
try {
    Write-Host "[0] Limpiando datos de smoke (reservas/sanciones de pruebas)" -ForegroundColor Yellow
    Invoke-RestMethod "$base/admin/limpiar-smoke" -Method POST -ContentType "application/json" -Body $bodyClean | Out-Null
} catch {
    Write-Warning "No se pudo limpiar datos de smoke. Verificar que la API esté levantada. Detalle: $($_.Exception.Message)"
}

# Fechas pensadas para estar lejos de los seeds
$fechaLibre = "2030-01-10"
$fechaSanc1 = "2030-01-11"
$fechaSanc2 = "2030-01-12"

$semFecha1 = "2030-02-12"   # martes
$semFecha2 = "2030-02-13"   # miércoles
$semFecha3 = "2030-02-14"   # jueves
$semFecha4 = "2030-02-15"   # viernes

Write-Host "== Smoke negocio BD1 =="

# 1) HEALTH + LOOKUPS
Write-Host "`n[1] /health, /turnos, /edificios, /salas"
irm "$base/health"
irm "$base/turnos"    | Select-Object -First 5
irm "$base/edificios"
irm "$base/salas"

# 2) Límite 2 horas/día (salas libres) + disponibilidad
Write-Host "`n[2] Reglas diarias (2 horas/día en salas libres)"

$body1 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $fechaLibre
    id_turno      = 8
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

$body2 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $fechaLibre
    id_turno      = 9
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

$body3 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $fechaLibre
    id_turno      = 10
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

Write-Host "`n[2.1] Primera reserva del día"
$resa1 = Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body1
$resa1

Write-Host "`n[2.2] Segunda reserva del día"
$resa2 = Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body2
$resa2

Write-Host "`n[2.3] Tercera reserva del día (debería fallar por límite diario)"
try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body3 -ErrorAction Stop
    Write-Host "¡¡OJO!! La tercera reserva se creó y NO debería."
} catch {
    Write-Host "Tercera reserva rechazada como se esperaba (límite diario)."
}

Write-Host "`n[2.4] /disponibilidad para esa sala y fecha"
irm "$base/disponibilidad?fecha=$fechaLibre&edificio=Sede%20Central&nombre_sala=Sala%20101" |
    Select-Object -First 5

# 3) Asistencia + sanción
Write-Host "`n[3] Asistencia y sanción automática"

$bodyS1 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $fechaSanc1
    id_turno      = 11
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

$resaS1 = Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyS1
Write-Host "Reserva para sanción:"
$resaS1

$asisBody = @{
    presentes = @()
} | ConvertTo-Json -Depth 5

$resaS1a = Invoke-RestMethod "$base/reservas/$($resaS1.id_reserva)/asistencia" `
    -Method POST -ContentType "application/json" -Body $asisBody
Write-Host "`nReserva luego de asistencia (esperado 'sin_asistencia'):"
$resaS1a

$bodyS2 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $fechaSanc2
    id_turno      = 12
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

Write-Host "`nIntentar reservar dentro del período de sanción (debería fallar)..."
try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyS2 -ErrorAction Stop
    Write-Host "¡¡OJO!! La reserva se creó y NO debería si la sanción se aplica."
} catch {
    Write-Host "Reserva rechazada por sanción (esperado)."
}

# 4) Límite semanal (3 reservas activas/semana)
Write-Host "`n[4] Límite semanal (3 reservas activas/semana)"

function New-Reserva {
    param(
        [string]$fecha,
        [int]$turno
    )
    $body = @{
        nombre_sala   = "Sala 101"
        edificio      = "Sede Central"
        fecha         = $fecha
        id_turno      = $turno
        participantes = @($ciDocente)   # usamos Ada para evitar sanciones previas
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body -ErrorAction Stop
}

Write-Host "`n[4.1] Tres reservas en la misma semana (deberían ser aceptadas)"
try {
    $sr1 = New-Reserva -fecha $semFecha1 -turno 8
    $sr2 = New-Reserva -fecha $semFecha2 -turno 9
    $sr3 = New-Reserva -fecha $semFecha3 -turno 10
    $sr1; $sr2; $sr3
} catch {
    Write-Host "¡¡OJO!! Alguna de las 3 primeras reservas falló y no debería."
}

Write-Host "`n[4.2] Cuarta reserva en la misma semana (debería fallar)"
$body4 = @{
    nombre_sala   = "Sala 101"
    edificio      = "Sede Central"
    fecha         = $semFecha4
    id_turno      = 11
    participantes = @($ciDocente)
} | ConvertTo-Json -Depth 5

try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body4 -ErrorAction Stop
    Write-Host "¡¡OJO!! La 4ª reserva se creó y NO debería si la regla semanal está activa."
} catch {
    Write-Host "4ª reserva rechazada como se esperaba (límite semanal)."
}

Write-Host "`n[5] Rol vs tipo de sala (exclusivas)"

$fechaPos1 = "2030-03-01"
$fechaPos2 = "2030-03-02"

$bodyRol1 = @{
    nombre_sala   = "Sala P1"
    edificio      = "Campus Pocitos"
    fecha         = $fechaPos1
    id_turno      = 12
    participantes = @($ciAlumno)
} | ConvertTo-Json -Depth 5

$bodyRol2 = @{
    nombre_sala   = "Sala P1"
    edificio      = "Campus Pocitos"
    fecha         = $fechaPos2
    id_turno      = 13
    participantes = @($ciDocente)
} | ConvertTo-Json -Depth 5

Write-Host "`n[5.1] Alumno de grado en sala posgrado (debe FALLAR)"
try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyRol1 -ErrorAction Stop | Out-Null
    Write-Host "¡¡OJO!! La reserva de alumno en sala posgrado se creó y NO debería."
} catch {
    Write-Host "Reserva rechazada como se esperaba por rol no apto (sala posgrado)."
    $_.ErrorDetails.Message
}

Write-Host "`n[5.2] Docente/posgrado en sala posgrado (debe PASAR)"
try {
    $rolOk = Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyRol2 -ErrorAction Stop
    $rolOk
} catch {
    Write-Host "¡¡OJO!! No se pudo reservar sala posgrado con docente/posgrado apto."
    $_.ErrorDetails.Message
}

Write-Host "`n[6] Capacidad de sala (Sala Mini, cap = 2)"

$fechaCap = "2030-04-01"
$bodyCapExceso = @{
    nombre_sala   = "Sala Mini"
    edificio      = "Sede Central"
    fecha         = $fechaCap
    id_turno      = 8
    participantes = @($ciAlumno, $ciCapA, $ciCapB) # 3 participantes en sala de 2
} | ConvertTo-Json -Depth 5

$bodyCapOk = @{
    nombre_sala   = "Sala Mini"
    edificio      = "Sede Central"
    fecha         = $fechaCap
    id_turno      = 9
    participantes = @($ciAlumno, $ciCapA) # 2 participantes dentro de capacidad
} | ConvertTo-Json -Depth 5

Write-Host "`n[6.1] Intento exceder capacidad (debe FALLAR)"
try {
    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyCapExceso -ErrorAction Stop | Out-Null
    Write-Host "¡¡OJO!! Se pudo reservar con capacidad excedida y no debería."
} catch {
    Write-Host "Reserva rechazada como se esperaba por capacidad excedida."; $_.ErrorDetails.Message
}

Write-Host "`n[6.2] Reserva dentro de capacidad (debe PASAR)"
try {
    $capOk = Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $bodyCapOk -ErrorAction Stop
    $capOk
} catch {
    Write-Host "¡¡OJO!! La reserva dentro de capacidad falló y no debería."; $_.ErrorDetails.Message
}

Write-Host "`n[7] Exención de límites diario/semanal para docente/posgrado en sala exclusiva"

$fechaPosEx = "2030-04-10"
$fechaPosEx2 = "2030-04-11"
$fechaPosEx3 = "2030-04-12"

function New-ReservaPosgrado {
    param(
        [string]$fecha,
        [int]$turno
    )
    $body = @{
        nombre_sala   = "Sala P1"
        edificio      = "Campus Pocitos"
        fecha         = $fecha
        id_turno      = $turno
        participantes = @($ciDocente)
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod "$base/reservas" -Method POST -ContentType "application/json" -Body $body -ErrorAction Stop
}

Write-Host "`n[7.1] Más de 2 horas en el mismo día (debe PASAR en sala posgrado)"
try {
    $px1 = New-ReservaPosgrado -fecha $fechaPosEx -turno 8
    $px2 = New-ReservaPosgrado -fecha $fechaPosEx -turno 9
    $px3 = New-ReservaPosgrado -fecha $fechaPosEx -turno 10
    $px1; $px2; $px3
} catch {
    Write-Host "¡¡OJO!! Alguna reserva diaria en sala posgrado falló (no deberían aplicar límites)."; $_.ErrorDetails.Message
}

Write-Host "`n[7.2] Más de 3 reservas en la misma semana (debe PASAR en sala posgrado)"
try {
    $pw1 = New-ReservaPosgrado -fecha $fechaPosEx2 -turno 11
    $pw2 = New-ReservaPosgrado -fecha $fechaPosEx3 -turno 12
    $pw1; $pw2
} catch {
    Write-Host "¡¡OJO!! Alguna reserva semanal en sala posgrado falló y no debería."; $_.ErrorDetails.Message
}

Write-Host "`n== Smoke negocio BD1 terminado =="
