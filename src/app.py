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
from datetime import time, timedelta

def _time_to_str(v: time | timedelta | str | None) -> str:
    if isinstance(v, timedelta):
        total = int(v.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    if isinstance(v, time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, str):
        return v
    return "00:00:00"

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

class EdificioOut(BaseModel):
    edificio: str


class SalaOut(BaseModel):
    edificio: str
    nombre_sala: str

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
# ==========================
# Reservas - endpoints básicos
# ==========================
from datetime import date
from typing import List
from pydantic import BaseModel
import os
import mysql.connector
from fastapi import HTTPException

class ReservaOut(BaseModel):
    id_reserva: int
    nombre_sala: str
    edificio: str
    fecha: date
    id_turno: int
    estado: str

def get_reservas_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
    )

@app.get("/reservas", response_model=List[ReservaOut])
def list_reservas(
    fecha: date | None = None,
    edificio: str | None = None,
    nombre_sala: str | None = None,
    id_turno: int | None = None,
):
    """
    Devuelve las reservas de la tabla 'reserva'.
    Se puede filtrar por fecha, edificio, nombre_sala e id_turno.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        conds = []
        params = []

        if fecha is not None:
            conds.append("fecha = %s")
            params.append(fecha)
        if edificio is not None:
            conds.append("edificio = %s")
            params.append(edificio)
        if nombre_sala is not None:
            conds.append("nombre_sala = %s")
            params.append(nombre_sala)
        if id_turno is not None:
            conds.append("id_turno = %s")
            params.append(id_turno)

        sql = """
            SELECT id_reserva,
                   nombre_sala,
                   edificio,
                   fecha,
                   id_turno,
                   estado
            FROM reserva
        """
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY fecha, edificio, nombre_sala, id_turno"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando reservas: {e}")
    finally:
        conn.close()

@app.get("/edificios", response_model=list[EdificioOut])
def list_edificios():
    """
    Devuelve la lista de edificios que tienen al menos una sala.

    Pensado para poblar combos en el frontend (select de edificio).
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT DISTINCT edificio
            FROM sala
            ORDER BY edificio
            """
        )
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listando edificios: {e}",
        )
    finally:
        conn.close()

@app.get("/salas", response_model=list[SalaOut])
def list_salas(edificio: str | None = None):
    """
    Lista salas.

    - Si se pasa ?edificio=..., trae solo las de ese edificio.
    - Si no, trae todas (ordenadas por edificio, nombre_sala).
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)
        if edificio:
            cur.execute(
                """
                SELECT edificio, nombre_sala
                FROM sala
                WHERE edificio = %s
                ORDER BY nombre_sala
                """,
                (edificio,),
            )
        else:
            cur.execute(
                """
                SELECT edificio, nombre_sala
                FROM sala
                ORDER BY edificio, nombre_sala
                """
            )
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listando salas: {e}",
        )
    finally:
        conn.close()

# ==========================
# Reservas - endpoints básicos
# ==========================
from datetime import date
from typing import List
from pydantic import BaseModel
import os
import mysql.connector
from fastapi import HTTPException

class ReservaOut(BaseModel):
    id_reserva: int
    nombre_sala: str
    edificio: str
    fecha: date
    id_turno: int
    estado: str

def get_reservas_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
    )

@app.get("/reservas", response_model=List[ReservaOut])
def list_reservas():
    """
    Devuelve todas las reservas de la tabla 'reserva'.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id_reserva,
                   nombre_sala,
                   edificio,
                   fecha,
                   id_turno,
                   estado
            FROM reserva
            ORDER BY fecha, edificio, nombre_sala, id_turno
            """
        )
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando reservas: {e}")
    finally:
        conn.close()
# Override helper de reservas para usar misma conexión que turnos
def get_reservas_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),   # por defecto 127.0.0.1 en tu máquina
        port=int(os.getenv("DB_PORT", "3306")),   # mismo puerto que ya usa la API
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
    )
# ==========================
# POST /reservas - crear reserva
# ==========================
class ReservaIn(BaseModel):
    nombre_sala: str
    edificio: str
    fecha: date
    id_turno: int
    estado: str | None = None  # opcional, default "activa"

@app.post("/reservas", response_model=ReservaOut, status_code=201)
def create_reserva(payload: ReservaIn):
    """
    Crea una reserva nueva en la tabla 'reserva'.

    Reglas básicas:
    - La sala (nombre_sala + edificio) debe existir.
    - El turno debe existir.
    - Si ya hay una reserva para esa sala/edificio/fecha/turno -> 409.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Validar sala
        cur.execute(
            """
            SELECT 1
            FROM sala
            WHERE nombre_sala = %s
              AND edificio = %s
            """,
            (payload.nombre_sala, payload.edificio),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Sala no encontrada")

        # 2) Validar turno
        cur.execute(
            "SELECT 1 FROM turno WHERE id_turno = %s",
            (payload.id_turno,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        # 3) Insertar reserva
        estado = payload.estado or "activa"
        try:
            cur.execute(
                """
                INSERT INTO reserva (nombre_sala, edificio, fecha, id_turno, estado)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (payload.nombre_sala, payload.edificio, payload.fecha, payload.id_turno, estado),
            )
            conn.commit()
        except mysql.connector.IntegrityError as e:
            # 1062 = duplicate entry (viola UNIQUE uq_reserva_unica)
            if getattr(e, "errno", None) == 1062:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una reserva para esa sala, edificio, fecha y turno",
                )
            raise

        # 4) Devolver la fila recién creada
        new_id = cur.lastrowid
        cur.execute(
            """
            SELECT id_reserva,
                   nombre_sala,
                   edificio,
                   fecha,
                   id_turno,
                   estado
            FROM reserva
            WHERE id_reserva = %s
            """,
            (new_id,),
        )
        row = cur.fetchone()
        return row

    except HTTPException:
        # Relevantar HTTPException tal cual
        raise
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error creando reserva: {e}")
    finally:
        conn.close()

# ==========================
# PATCH /reservas/{id_reserva} - cambiar estado
# ==========================
class ReservaEstadoIn(BaseModel):
    estado: str

ALLOWED_ESTADOS_RESERVA = {"activa", "cancelada", "sin_asistencia", "finalizada"}

@app.patch("/reservas/{id_reserva}", response_model=ReservaOut)
def update_reserva_estado(id_reserva: int, payload: ReservaEstadoIn):
    """
    Cambia el estado de una reserva existente.

    - Solo toca el campo `estado`.
    - Estados válidos: activa, cancelada, sin_asistencia, finalizada.
    """
    # Normalizar estado (trim + lower)
    raw = (payload.estado or "").strip().lower()
    if raw not in ALLOWED_ESTADOS_RESERVA:
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(sorted(ALLOWED_ESTADOS_RESERVA))}",
        )
    estado = raw

    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Verificar que la reserva exista
        cur.execute(
            """
            SELECT id_reserva,
                   nombre_sala,
                   edificio,
                   fecha,
                   id_turno,
                   estado
            FROM reserva
            WHERE id_reserva = %s
            """,
            (id_reserva,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")

        # 2) Actualizar solo el estado
        cur.execute(
            "UPDATE reserva SET estado = %s WHERE id_reserva = %s",
            (estado, id_reserva),
        )
        conn.commit()

        # 3) Devolver la reserva actualizada
        row["estado"] = estado
        return row

    except HTTPException:
        raise
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando reserva: {e}")
    finally:
        conn.close()

from datetime import time

class TurnoDisponibilidad(BaseModel):
    id_turno: int
    hora_inicio: str   # antes: time
    hora_fin: str      # antes: time
    reservado: bool
    estado_reserva: str | None = None


@app.get("/disponibilidad", response_model=List[TurnoDisponibilidad])
def disponibilidad(
    fecha: date,
    edificio: str,
    nombre_sala: str,
):
    """
    Devuelve todos los turnos y si están reservados o no
    para (edificio, nombre_sala, fecha).

    Reglas:
    - Si la sala no existe en ese edificio -> 404.
    - reservado = True solo si hay reserva ACTIVA de esa sala en ese turno.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Validar que la sala exista para ese edificio
        cur.execute(
            """
            SELECT 1
            FROM sala
            WHERE edificio = %s
              AND nombre_sala = %s
            LIMIT 1
            """,
            (edificio, nombre_sala),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"Sala '{nombre_sala}' no existe en edificio '{edificio}'",
            )

        # 2) Traer todos los turnos + (si hay) su reserva para esa sala/fecha
        cur.execute(
            """
            SELECT
                t.id_turno,
                t.hora_inicio,
                t.hora_fin,
                r.id_reserva,
                r.estado
            FROM turno t
            LEFT JOIN reserva r
              ON r.id_turno    = t.id_turno
             AND r.fecha       = %s
             AND r.edificio    = %s
             AND r.nombre_sala = %s
            ORDER BY t.id_turno
            """,
            (fecha, edificio, nombre_sala),
        )
        rows = cur.fetchall()

        result = []
        for row in rows:
            reservado = row["id_reserva"] is not None and row["estado"] == "activa"
            result.append(
                {
                    "id_turno": row["id_turno"],
                    "hora_inicio": _time_to_str(row["hora_inicio"]),
                    "hora_fin": _time_to_str(row["hora_fin"]),
                    "reservado": reservado,
                    "estado_reserva": row["estado"],
                }
            )
        return result
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando disponibilidad: {e}",
        )
    finally:
        conn.close()

