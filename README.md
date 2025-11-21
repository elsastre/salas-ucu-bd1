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
