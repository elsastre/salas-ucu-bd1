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
#   SOURCE ./sql/seed.sql;

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

### Windows (un solo paso)
Ejecuta `run.bat` en la raíz del repo:
```
run.bat
```
El script valida que Docker esté disponible, levanta `db`, `adminer` y `api`, espera el `/health` y abre automáticamente `/docs` y `/ui`.

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
