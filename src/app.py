from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, field_validator
from typing import List
import os, mysql.connector
from datetime import timedelta

app = FastAPI(title="UCU Salas - BD1", version="0.3.0")

# --------- DB ---------
def get_conn():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
        autocommit=True
    )

# --------- helpers ---------
def _fmt_time(t):
    if isinstance(t, timedelta):
        total = int(t.total_seconds())
        h, r = divmod(total, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return str(t)

def _parse_hms(hms: str) -> int:
    try:
        h, m, s = map(int, hms.split(":"))
        return h*3600 + m*60 + s
    except Exception:
        raise HTTPException(status_code=422, detail="Formato de hora inválido. Use 'HH:MM:SS'.")

def _row_to_turno(r):
    return {
        "id_turno": r["id_turno"],
        "hora_inicio": _fmt_time(r["hora_inicio"]),
        "hora_fin": _fmt_time(r["hora_fin"]),
    }

# --------- MODELOS ---------
class TurnoIn(BaseModel):
    id_turno: int
    hora_inicio: str  # 'HH:MM:SS'
    hora_fin: str     # 'HH:MM:SS'

    @field_validator("hora_inicio", "hora_fin")
    @classmethod
    def _val_fmt(cls, v):
        _ = _parse_hms(v); return v

class TurnoUpdate(BaseModel):
    hora_inicio: str
    hora_fin: str
    @field_validator("hora_inicio", "hora_fin")
    @classmethod
    def _val_fmt(cls, v):
        _ = _parse_hms(v); return v

class TurnoOut(BaseModel):
    id_turno: int
    hora_inicio: str
    hora_fin: str

# --------- HEALTH ---------
@app.get("/health")
def health():
    try:
        conn = get_conn()
        conn.close()
        return {"status": "ok", "db": "reachable"}
    except Exception as e:
        return {"status": "ok", "db": f"error: {e.__class__.__name__}"}

# --------- TURNOS ---------
@app.get("/turnos", response_model=List[TurnoOut])
def listar_turnos():
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY id_turno;")
        rows = [_row_to_turno(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/turnos/{id_turno}", response_model=TurnoOut)
def obtener_turno(id_turno: int = Path(..., ge=0)):
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno WHERE id_turno=%s;", (id_turno,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        return _row_to_turno(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/turnos", response_model=TurnoOut, status_code=201)
def crear_turno(t: TurnoIn):
    ini = _parse_hms(t.hora_inicio)
    fin = _parse_hms(t.hora_fin)
    if fin <= ini:
        raise HTTPException(status_code=422, detail="hora_fin debe ser mayor a hora_inicio")

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO turno(id_turno, hora_inicio, hora_fin) VALUES (%s,%s,%s);",
                    (t.id_turno, t.hora_inicio, t.hora_fin))
        # devolver registro
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno WHERE id_turno=%s;", (t.id_turno,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return _row_to_turno(row)
    except mysql.connector.Error as e:
        if e.errno == 1062:
            raise HTTPException(status_code=409, detail="id_turno duplicado")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/turnos/{id_turno}", response_model=TurnoOut)
def actualizar_turno(id_turno: int, t: TurnoUpdate):
    ini = _parse_hms(t.hora_inicio)
    fin = _parse_hms(t.hora_fin)
    if fin <= ini:
        raise HTTPException(status_code=422, detail="hora_fin debe ser mayor a hora_inicio")

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE turno SET hora_inicio=%s, hora_fin=%s WHERE id_turno=%s;",
                    (t.hora_inicio, t.hora_fin, id_turno))
        if cur.rowcount == 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno WHERE id_turno=%s;", (id_turno,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return _row_to_turno(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/turnos/{id_turno}", status_code=204)
def borrar_turno(id_turno: int):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM turno WHERE id_turno=%s;", (id_turno,))
        if cur.rowcount == 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        cur.close(); conn.close()
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
