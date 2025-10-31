# Sistema de Gestión de Salas de Estudio (UCU) – BD1

Avance v0.1: estructura base, SQL (schema + seed), backend Python sin ORM (FastAPI), instructivo para correr local.

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
#   SOURCE ./sql/schema.sql;
#   SOURCE ./sql/seed.sql;

# 5) Levantar API
pwsh .\scripts\run.ps1
# -> http://127.0.0.1:8000/health y /turnos

## Docker (rápido)
- Levantar servicios:
  ```powershell
  docker compose up -d
