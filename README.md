# Sistema de Gestión de Salas de Estudio (UCU) – BD1

Avance v0.3: FastAPI + MySQL (sin ORM), scripts de base de datos y smoke tests.

## Cómo correr (local)
```powershell
# 1) Crear y activar venv
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Crear .env desde .env.example y ajustar credenciales
Copy-Item .env.example .env

# 4) Crear BD y datos en MySQL
#   SOURCE ./sql/00_schema.sql;
#   SOURCE ./sql/seed_demo.sql;

# 5) Levantar API
uvicorn src.app:app --host 127.0.0.1 --port 8000
# -> http://127.0.0.1:8000/health | /docs | /ui
```

## Ejecución con Docker

### Comando directo
```bash
docker compose up -d --build
```
- API: http://127.0.0.1:${API_PORT:-8000}/docs y /ui
- Adminer: http://127.0.0.1:8080 (Servidor=db, user=root, pass=root, base=salas_db)

**Importante:** si ya habías levantado la base y quieres resembrar con `seed_demo.sql`, resetea el volumen antes de iniciar:
```bash
docker compose down --volumes
docker compose up -d --build
```
También puedes usar el helper `scripts/reset_demo.sh` para automatizar estos pasos.

### Windows (un solo paso)
Ejecuta `run.bat` en la raíz del repo:
```
run.bat
```
El script valida que Docker esté disponible, levanta `db`, `adminer` y `api`, espera el `/health` y abre automáticamente `/docs` y `/ui`.

## Seed de demostración

- El volumen `./sql` solo ejecuta `00_schema.sql` y `seed_demo.sql`, que pobló ~100 participantes, ~100 salas repartidas en 5 edificios, 10 turnos, ~100 reservas con estados variados y un set de sanciones activas/expiradas.
- Los archivos `seed.sql` y `seed2.sql` se dejaron vacíos para evitar cargas duplicadas.

## Scripts de profesor (alternativa)
```powershell
Copy-Item .env.example .env -Force
powershell -ExecutionPolicy Bypass -File .\scripts\prof-check.ps1 -KeepApi
# Swagger: http://127.0.0.1:8000/docs · Adminer: http://localhost:8080
```

## Tests
```bash
pytest
```
Puedes ejecutarlos en local (con las dependencias instaladas) o dentro de un contenedor que tenga Python disponible.

## Smokes e idempotencia

- `scripts/smoke_negocio.ps1` valida reglas de negocio (límite diario/semanal, sanciones y exclusividad de salas). Antes de empezar llama al endpoint de utilería `/admin/limpiar-smoke` para borrar reservas/sanciones de prueba en las fechas 2030 usadas por el smoke.
- `scripts/smoke_reportes.ps1` recorre los reportes principales.
- `scripts/smoke_full.ps1` integra ambos y añade CRUD de participantes y un flujo manual de sanciones idempotente.

Para correrlos sobre un estado limpio:
```powershell
docker compose down --volumes
docker compose up -d --build
powershell -File .\scripts\smoke_negocio.ps1
powershell -File .\scripts\smoke_reportes.ps1
# Opcional
powershell -File .\scripts\smoke_full.ps1
```

Si ya tienes el stack levantado y solo quieres limpiar residuos de ejecuciones previas, puedes invocar manualmente:
```powershell
Invoke-RestMethod "http://127.0.0.1:8000/admin/limpiar-smoke" -Method POST -ContentType "application/json" -Body (@{ participantes = @("41234567","59876543","40123456","42222222"); fechas = @("2030-01-10","2030-01-11","2030-01-12","2030-02-12","2030-02-13","2030-02-14","2030-02-15","2030-03-01","2030-03-02","2030-05-01") } | ConvertTo-Json)
```

El script `prof-check.ps1` ya cuenta con el flag `-Clean` para hacer `docker compose down --volumes` antes de levantar servicios.

## Login lógico y roles

- El panel `/ui` pide iniciar sesión con la CI de un participante (sin contraseña) y **no** persiste sesión entre recargas. El backend expone `/auth/login` para validar la existencia y devolver `es_admin`.
- Solo administradores pueden crear/editar/eliminar salas, participantes, turnos y sanciones manuales. Los botones quedan deshabilitados y, si se fuerzan, aparece el mensaje “Solo administradores pueden realizar esta acción”.
- CI útiles del seed: admin/docente `59876543`, admin `50000001`, estudiante típico `40000001`. Salas de ejemplo: `Sala A-001` (Sede Central, libre), `Sala B-010` (Campus Pocitos), `Sala C-005` (Campus Norte).

## Reportes cubiertos

Todos los reportes de la letra y tres consultas adicionales están expuestos como endpoints GET y accesibles desde la pestaña de
reportes en `/ui` (cada tarjeta tiene filtros propios):

- `/reportes/salas-mas-usadas` (top salas) y `/reportes/turnos-mas-demandados`.
- `/reportes/promedio-participantes-por-sala` y `/reportes/reservas-por-carrera-facultad`.
- `/reportes/ocupacion-por-edificio`.
- `/reportes/reservas-y-asistencias-por-rol` y `/reportes/uso-por-rol`.
- `/reportes/sanciones-por-rol` (visible en UI para admins).
- `/reportes/efectividad-reservas` (efectivamente usadas vs canceladas/no show).
- Extras BI: `/reportes/top-participantes`, `/reportes/salas-no-show`, `/reportes/distribucion-semana-turno`.

La UI permite ejecutar cada consulta con filtros de fecha y límites, mostrando tablas interpretables sin requerir headers de auth en
los endpoints existentes.
