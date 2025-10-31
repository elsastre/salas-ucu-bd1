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

## ✅ Prueba rápida (modo profesor)
```powershell
# en Windows PowerShell
git clone https://github.com/<tu-usuario>/salas-ucu-bd1
cd salas-ucu-bd1
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File .\scripts\prof-check.ps1

## ✅ Prueba rápida (modo profesor)
```powershell
git clone https://github.com/<tu-usuario>/salas-ucu-bd1
cd salas-ucu-bd1
Copy-Item .env.example .env -Force
powershell -ExecutionPolicy Bypass -File .\scripts\prof-check.ps1 -KeepApi
# Swagger: http://127.0.0.1:8000/docs  · Adminer: http://localhost:8080 (Servidor=db, root/root, base=salas_db)

## ✅ Prueba rápida (modo profesor)
```powershell
git clone https://github.com/<tu-usuario>/salas-ucu-bd1
cd salas-ucu-bd1
Copy-Item .env.example .env -Force
# El script verifica/arranca Docker Desktop, alinea .env y corre smoke.
powershell -ExecutionPolicy Bypass -File .\scripts\prof-check.ps1 -KeepApi
# Swagger: http://127.0.0.1:8000/docs  · Adminer: http://localhost:8080 (Servidor=db, root/root, base=salas_db)

### 🧪 Prueba rápida (modo profesor)
El script arranca **Docker Desktop** si está apagado, selecciona automáticamente **DB_PORT** libre (3306→3307→3308), alinea `.env` y corre un smoke.
```powershell
Copy-Item .env.example .env -Force
powershell -ExecutionPolicy Bypass -File .\scripts\prof-check.ps1 -KeepApi
# Swagger: http://127.0.0.1:8000/docs · Adminer: http://localhost:8080 (Servidor=db, root/root, base=salas_db)
