from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from pydantic import AliasChoices
from typing import List, Literal, Any
import os, mysql.connector, re
from datetime import timedelta, date
from pathlib import Path as FilePath

app = FastAPI(title="UCU Salas - BD1", version="0.3.0")

BASE_DIR = FilePath(__file__).parent
UI_TEMPLATE = BASE_DIR / "templates" / "ui.html"
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# --------- DB ---------
def get_conn():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", "root"),
        database=os.getenv("DB_NAME", "salas_db"),
        autocommit=True
    )
    ensure_schema_migrations(conn)
    return conn

# Para compatibilidad con el código existente
def get_reservas_connection():
    return get_conn()

# --------- helpers ---------
from datetime import time, timedelta

CI_CLEAN_RE = re.compile(r"\D")


_MIGRATIONS_APPLIED = False


def ensure_schema_migrations(conn: mysql.connector.MySQLConnection) -> None:
    """
    Aplica migraciones ligeras para entornos ya inicializados con un schema
    anterior (por ejemplo, bases levantadas antes de agregar el campo
    tipo_participante).

    Esto evita errores 500 de "Unknown column 'tipo_participante'" cuando el
    volumen de datos persiste entre levantadas de Docker.
    """
    global _MIGRATIONS_APPLIED
    if _MIGRATIONS_APPLIED:
        return

    cur = conn.cursor()
    try:
        # MySQL no soporta "ADD COLUMN IF NOT EXISTS". Para que la migración
        # sea idempotente, verificamos primero si la columna está presente y
        # solo ejecutamos el ALTER cuando falta.
        cur.execute("SHOW COLUMNS FROM participante LIKE 'tipo_participante'")
        if cur.fetchone() is None:
            cur.execute(
                """
                ALTER TABLE participante
                ADD COLUMN tipo_participante
                ENUM('estudiante','docente','posgrado')
                NOT NULL DEFAULT 'estudiante'
                """
            )

        # Normalizar CIs existentes (seeds viejos podían tener puntos/guiones).
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for table, column in [
            ("participante", "ci"),
            ("participante_programa_academico", "ci_participante"),
            ("reserva_participante", "ci_participante"),
            ("sancion_participante", "ci_participante"),
        ]:
            cur.execute(
                f"""
                UPDATE {table}
                SET {column} = REGEXP_REPLACE({column}, '[^0-9]', '')
                WHERE {column} REGEXP '[^0-9]'
                """
            )
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        _MIGRATIONS_APPLIED = True
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error aplicando migraciones: {e}",
        )
    finally:
        cur.close()


def normalize_ci(ci: str) -> str:
    if ci is None:
        raise HTTPException(status_code=422, detail="Formato de CI inválido")
    raw = ci.strip()
    digits = CI_CLEAN_RE.sub("", raw)
    if 7 <= len(digits) <= 8 and digits.isdigit():
        return digits
    raise HTTPException(status_code=422, detail="Formato de CI inválido")


def normalize_ci_list(cis: List[str]) -> List[str]:
    return [normalize_ci(ci) for ci in cis or []]


ESTADOS_OCUPAN_DIA = ("activa", "sin_asistencia", "finalizada")


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


@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
def render_ui():
    """Interfaz mínima en HTML que consume la API."""
    return HTMLResponse(content=UI_TEMPLATE.read_text(encoding="utf-8"))

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

# --------- MODELOS SALA ---------
class SalaBase(BaseModel):
    nombre_sala: str
    edificio: str
    capacidad: int
    tipo_sala: Literal["libre", "posgrado", "docente"]

class SalaCreate(SalaBase):
    """Modelo para alta de sala."""
    pass

class SalaUpdate(BaseModel):
    """Actualizar los atributos editables de una sala (permite renombrar)."""
    nombre_sala: str
    capacidad: int
    tipo_sala: Literal["libre", "posgrado", "docente"]

# --------- MODELOS PARTICIPANTE ---------
class ParticipanteBase(BaseModel):
    ci: str
    nombre: str
    apellido: str
    email: str
    tipo_participante: Literal["estudiante", "docente", "posgrado"]

    @field_validator("ci")
    @classmethod
    def _val_ci(cls, v):
        return normalize_ci(v)

    @staticmethod
    def _val_nombre_apellido(v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 2 or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", clean):
            raise ValueError("Debe tener al menos 2 caracteres alfabéticos")
        return clean

    @field_validator("nombre")
    @classmethod
    def _val_nombre(cls, v):
        return ParticipanteBase._val_nombre_apellido(v)

    @field_validator("apellido")
    @classmethod
    def _val_apellido(cls, v):
        return ParticipanteBase._val_nombre_apellido(v)

class ParticipanteCreate(ParticipanteBase):
    """Modelo para alta de participante (tiene todos los campos)."""
    pass

class ParticipanteUpdate(BaseModel):
    """Modelo para actualizar datos de un participante existente (no se cambia la CI)."""
    nombre: str
    apellido: str
    email: str
    tipo_participante: Literal["estudiante", "docente", "posgrado"]

    @field_validator("nombre")
    @classmethod
    def _val_nombre(cls, v):
        return ParticipanteBase._val_nombre_apellido(v)

    @field_validator("apellido")
    @classmethod
    def _val_apellido(cls, v):
        return ParticipanteBase._val_nombre_apellido(v)

# --------- MODELOS REPORTES ---------
class ReportSalaUso(BaseModel):
    edificio: str
    nombre_sala: str
    total_reservas: int


class ReportOcupacionEdificio(BaseModel):
    edificio: str
    total_reservas: int
    porcentaje_sobre_total: float


class ReportUsoPorRol(BaseModel):
    rol: str
    tipo_programa: str
    total_reservas: int


# --------- MODELOS SANCIONES ---------
class SancionBase(BaseModel):
    ci: str = Field(
        ...,
        validation_alias=AliasChoices("ci", "ci_participante"),
        serialization_alias="ci",
        description="CI del participante sancionado",
    )
    fecha_inicio: date
    fecha_fin: date

    @field_validator("ci")
    @classmethod
    def _val_ci(cls, v):
        return normalize_ci(v)

    @field_validator("fecha_fin")
    @classmethod
    def _val_fechas(cls, v, values):
        inicio = values.data.get("fecha_inicio")
        if inicio and v <= inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return v


class SancionCreate(SancionBase):
    pass


class SancionUpdate(BaseModel):
    fecha_fin: date

    @field_validator("fecha_fin")
    @classmethod
    def _val_fin(cls, v):
        if not v:
            raise ValueError("fecha_fin es requerida")
        return v

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
class ReservaOut(BaseModel):
    id_reserva: int
    nombre_sala: str
    edificio: str
    fecha: date
    id_turno: int
    estado: str
    participantes: str | None = None

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
            SELECT r.id_reserva,
                   r.nombre_sala,
                   r.edificio,
                   r.fecha,
                   r.id_turno,
                   r.estado,
                   GROUP_CONCAT(rp.ci_participante ORDER BY rp.ci_participante) AS participantes
            FROM reserva r
            LEFT JOIN reserva_participante rp ON rp.id_reserva = r.id_reserva
        """
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " GROUP BY r.id_reserva, r.nombre_sala, r.edificio, r.fecha, r.id_turno, r.estado"
        sql += " ORDER BY r.fecha, r.edificio, r.nombre_sala, r.id_turno"

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

# ==========================
#  SALAS - ABM
# ==========================

@app.get("/salas", response_model=List[SalaBase])
def listar_salas(edificio: str | None = Query(None, description="Filtrar por edificio")):
    """
    Lista las salas, opcionalmente filtradas por edificio.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        if edificio:
            cur.execute(
                """
                SELECT nombre_sala, edificio, capacidad, tipo_sala
                FROM sala
                WHERE edificio = %s
                ORDER BY edificio, nombre_sala
                """,
                (edificio,),
            )
        else:
            cur.execute(
                """
                SELECT nombre_sala, edificio, capacidad, tipo_sala
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


@app.get(
    "/salas/{edificio}/{nombre_sala}",
    response_model=SalaBase,
)
def obtener_sala(
    edificio: str = Path(..., description="Nombre del edificio"),
    nombre_sala: str = Path(..., description="Nombre de la sala"),
):
    """
    Devuelve una sala específica por (edificio, nombre_sala).
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT nombre_sala, edificio, capacidad, tipo_sala
            FROM sala
            WHERE edificio = %s AND nombre_sala = %s
            """,
            (edificio, nombre_sala),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sala no encontrada")
        return row
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error buscando sala: {e}",
        )
    finally:
        conn.close()


@app.post("/salas", response_model=SalaBase, status_code=201)
def crear_sala(s: SalaCreate):
    """
    Alta de sala.

    - 409 si ya existe esa combinación (nombre_sala, edificio).
    - 400 si el edificio no existe (violación de FK).
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sala (nombre_sala, edificio, capacidad, tipo_sala)
            VALUES (%s, %s, %s, %s)
            """,
            (s.nombre_sala, s.edificio, s.capacidad, s.tipo_sala),
        )
        conn.commit()
        return s
    except mysql.connector.Error as e:
        if e.errno == 1062:
            # clave primaria duplicada
            raise HTTPException(
                status_code=409,
                detail="Ya existe una sala con ese nombre en ese edificio",
            )
        if e.errno == 1452:
            # foreign key fail (edificio no existe)
            raise HTTPException(
                status_code=400,
                detail="El edificio especificado no existe",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error creando sala: {e}",
        )
    finally:
        conn.close()


@app.put(
    "/salas/{edificio}/{nombre_sala}",
    response_model=SalaBase,
)
def actualizar_sala(
    edificio: str = Path(..., description="Nombre del edificio"),
    nombre_sala: str = Path(..., description="Nombre de la sala"),
    s: SalaUpdate = ...,
):
    """
    Actualiza una sala existente. El identificador surge de la URL
    (edificio, nombre_sala) y el payload puede incluir un nombre nuevo.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        # Verificar que exista
        cur.execute(
            """
            SELECT nombre_sala, edificio, capacidad, tipo_sala
            FROM sala
            WHERE edificio = %s AND nombre_sala = %s
            """,
            (edificio, nombre_sala),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sala no encontrada")

        # Actualizar
        cur.execute(
            """
            UPDATE sala
            SET nombre_sala = %s,
                capacidad = %s,
                tipo_sala = %s
            WHERE edificio = %s AND nombre_sala = %s
            """,
            (s.nombre_sala, s.capacidad, s.tipo_sala, edificio, nombre_sala),
        )
        conn.commit()

        return {
            "nombre_sala": s.nombre_sala,
            "edificio": edificio,
            "capacidad": s.capacidad,
            "tipo_sala": s.tipo_sala,
        }
    except mysql.connector.Error as e:
        if e.errno == 1062:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una sala con ese nombre en ese edificio",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando sala: {e}",
        )
    finally:
        conn.close()


@app.delete("/salas/{edificio}/{nombre_sala}")
def eliminar_sala(
    edificio: str = Path(..., description="Nombre del edificio"),
    nombre_sala: str = Path(..., description="Nombre de la sala"),
):
    """
    Elimina una sala.

    - 404 si no existe.
    - 409 si tiene reservas asociadas (violación de FK).
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM sala
            WHERE edificio = %s AND nombre_sala = %s
            """,
            (edificio, nombre_sala),
        )
        conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sala no encontrada")

        return {"detail": "Sala eliminada"}
    except mysql.connector.Error as e:
        if e.errno == 1451:
            raise HTTPException(
                status_code=409,
                detail="No se puede eliminar la sala porque tiene reservas asociadas",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando sala: {e}",
        )
    finally:
        conn.close()

# ==========================
# POST /reservas - crear reserva
# ==========================
class ReservaIn(BaseModel):
    nombre_sala: str
    edificio: str
    fecha: date
    id_turno: int
    participantes: List[str]          # CIs de los participantes
    estado: str | None = None         # opcional, default "activa"

    @field_validator("participantes")
    @classmethod
    def _val_cis(cls, v):
        norm = normalize_ci_list(v)
        if not norm:
            raise ValueError("Debe indicar al menos un participante")
        return norm


class AsistenciaIn(BaseModel):
    presentes: List[str] = []              # CIs que efectivamente asistieron
    sancionar_ausentes: bool = True

    @field_validator("presentes")
    @classmethod
    def _val_presentes(cls, v):
        return normalize_ci_list(v)

@app.post("/reservas", response_model=ReservaOut, status_code=201)
def create_reserva(payload: ReservaIn):
    """
    Crea una reserva nueva aplicando reglas de negocio:

    - Valida sala, turno y estado.
    - Valida que los participantes existan.
    - No se puede superar la capacidad de la sala.
    - No se puede reservar si el participante está sancionado en esa fecha.
    - Salas de uso libre: máx. 2 horas/día y 3 reservas activas/semana por persona.
      * Docentes y alumnos de posgrado NO tienen estos límites en salas exclusivas para ellos.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        def horas_reservadas_libre(ci: str) -> float:
            placeholders_estados = ",".join(["%s"] * len(ESTADOS_OCUPAN_DIA))
            cur.execute(
                f"""
                SELECT COALESCE(SUM(TIME_TO_SEC(t.hora_fin) - TIME_TO_SEC(t.hora_inicio)) / 3600, 0) AS horas
                FROM reserva r
                JOIN reserva_participante rp
                  ON rp.id_reserva = r.id_reserva
                JOIN sala s
                  ON s.nombre_sala = r.nombre_sala
                 AND s.edificio = r.edificio
                JOIN turno t
                  ON t.id_turno = r.id_turno
                WHERE rp.ci_participante = %s
                  AND r.fecha = %s
                  AND r.estado IN ({placeholders_estados})
                  AND s.tipo_sala = 'libre'
                """,
                (ci, payload.fecha, *ESTADOS_OCUPAN_DIA),
            )
            row = cur.fetchone()
            return float(row["horas"]) if row else 0.0

        def reservas_semana_libre(ci: str) -> int:
            cur.execute(
                """
                SELECT COUNT(*) AS cant
                FROM reserva r
                JOIN reserva_participante rp
                  ON rp.id_reserva = r.id_reserva
                JOIN sala s
                  ON s.nombre_sala = r.nombre_sala
                 AND s.edificio = r.edificio
                WHERE rp.ci_participante = %s
                  AND r.estado = 'activa'
                  AND s.tipo_sala = 'libre'
                  AND YEARWEEK(r.fecha, 3) = YEARWEEK(%s, 3)
                """,
                (ci, payload.fecha),
            )
            row = cur.fetchone()
            return int(row["cant"] or 0)

        # 1) Validar sala y obtener capacidad + tipo_sala
        cur.execute(
            """
            SELECT capacidad, tipo_sala
            FROM sala
            WHERE nombre_sala = %s
              AND edificio = %s
            """,
            (payload.nombre_sala, payload.edificio),
        )
        sala_row = cur.fetchone()
        if not sala_row:
            raise HTTPException(status_code=404, detail="Sala no encontrada")

        capacidad = sala_row["capacidad"]
        tipo_sala = sala_row["tipo_sala"]  # 'libre', 'posgrado', 'docente'

        # 2) Validar turno
        cur.execute(
            "SELECT id_turno, hora_inicio, hora_fin FROM turno WHERE id_turno = %s",
            (payload.id_turno,),
        )
        turno_row = cur.fetchone()
        if not turno_row:
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        turno_duracion_horas = (
            _parse_hms(_time_to_str(turno_row["hora_fin"]))
            - _parse_hms(_time_to_str(turno_row["hora_inicio"]))
        ) / 3600

        # 3) Normalizar y validar estado
        estado = (payload.estado or "activa").strip().lower()
        if estado not in ALLOWED_ESTADOS_RESERVA:
            raise HTTPException(
                status_code=422,
                detail=f"Estado inválido. Debe ser uno de: {', '.join(sorted(ALLOWED_ESTADOS_RESERVA))}",
            )

        # 4) Lista de participantes
        participantes = normalize_ci_list(payload.participantes)
        if not participantes:
            raise HTTPException(
                status_code=400,
                detail="Debe indicar al menos un participante para la reserva.",
            )

        # 5) Validar existencia de participantes
        placeholders = ",".join(["%s"] * len(participantes))
        cur.execute(
            f"SELECT ci, tipo_participante FROM participante WHERE ci IN ({placeholders})",
            tuple(participantes),
        )
        participantes_info = {row["ci"]: row for row in cur.fetchall()}
        faltantes = [ci for ci in participantes if ci not in participantes_info]
        if faltantes:
            raise HTTPException(
                status_code=404,
                detail=f"Participantes no encontrados: {', '.join(faltantes)}",
            )

        # 5.b) Validar exclusividad por tipo de sala
        allowed_por_sala = {
            "posgrado": {"posgrado", "docente"},
            "docente": {"docente", "posgrado"},
        }

        if tipo_sala in allowed_por_sala:
            habilitados = allowed_por_sala[tipo_sala]
            no_aptos = [
                ci
                for ci, info in participantes_info.items()
                if info["tipo_participante"] not in habilitados
            ]
            if no_aptos:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"La sala {payload.nombre_sala} en {payload.edificio} es exclusiva para {tipo_sala}. "
                        f"CIs no aptas: {', '.join(no_aptos)}."
                    ),
                )

        # 6) Validar capacidad de la sala
        if len(participantes) > capacidad:
            raise HTTPException(
                status_code=409,
                detail=f"La sala tiene capacidad {capacidad} y se intentan registrar "
                       f"{len(participantes)} participantes.",
            )

        # 7) Reglas de negocio por persona (solo si la reserva será ACTIVA)
        if estado == "activa":
            placeholders = ",".join(["%s"] * len(participantes))
            cur.execute(
                f"""
                SELECT ci_participante, fecha_inicio, fecha_fin
                FROM sancion_participante
                WHERE ci_participante IN ({placeholders})
                  AND %s BETWEEN fecha_inicio AND fecha_fin
                """,
                (*participantes, payload.fecha),
            )
            sancionados = cur.fetchall()
            if sancionados:
                detalles = ", ".join(
                    f"{row['ci_participante']} ({row['fecha_inicio']} a {row['fecha_fin']})"
                    for row in sancionados
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Participantes con sanción activa: {detalles}",
                )

            for ci in participantes:
                # 7.a) Límite diario/semanal solo para salas de uso libre
                if tipo_sala == "libre":
                    horas_dia = horas_reservadas_libre(ci)
                    if horas_dia + turno_duracion_horas > 2:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"El participante {ci} ya tiene {horas_dia:.0f} horas reservadas "
                                "en salas de uso libre para ese día."
                            ),
                        )

                    cant_semana = reservas_semana_libre(ci)
                    if cant_semana >= 3:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                "4ª reserva semanal: límite de 3 reservas activas por semana excedido."
                            ),
                        )

        # 8) Insertar reserva + participantes
        try:
            cur.execute(
                """
                INSERT INTO reserva (nombre_sala, edificio, fecha, id_turno, estado)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (payload.nombre_sala, payload.edificio, payload.fecha, payload.id_turno, estado),
            )
            id_reserva = cur.lastrowid

            valores = [(ci, id_reserva) for ci in participantes]
            cur.executemany(
                """
                INSERT INTO reserva_participante (ci_participante, id_reserva)
                VALUES (%s, %s)
                """,
                valores,
            )

            conn.commit()
        except mysql.connector.IntegrityError as e:
            conn.rollback()
            if getattr(e, "errno", None) == 1062:
                # UNIQUE (nombre_sala, edificio, fecha, id_turno)
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una reserva para esa sala, edificio, fecha y turno",
                )
            raise

        # 9) Devolver la reserva creada
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
            raise HTTPException(status_code=500, detail="No se pudo recuperar la reserva creada.")
        return row
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

@app.post("/reservas/{id_reserva}/asistencia", response_model=ReservaOut)
def registrar_asistencia(id_reserva: int, payload: AsistenciaIn):
    """
    Registra la asistencia de los participantes de una reserva.

    - `presentes` es la lista de CIs que asistieron.
    - Si no hay ningún asistente:
        * la reserva queda en estado `sin_asistencia`
        * se generan sanciones de 2 meses para todos los participantes.
    """
    conn = get_reservas_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Verificar que la reserva exista
        cur.execute(
            """
            SELECT id_reserva, fecha, estado
            FROM reserva
            WHERE id_reserva = %s
            """,
            (id_reserva,),
        )
        reserva = cur.fetchone()
        if not reserva:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")

        # 2) Verificar que tenga participantes asociados
        cur.execute(
            """
            SELECT ci_participante
            FROM reserva_participante
            WHERE id_reserva = %s
            """,
            (id_reserva,),
        )
        filas_part = cur.fetchall()
        if not filas_part:
            raise HTTPException(
                status_code=400,
                detail="La reserva no tiene participantes; no se puede registrar asistencia.",
            )

        participantes_reserva = {row["ci_participante"] for row in filas_part}

        presentes = set(normalize_ci_list(payload.presentes))
        desconocidos = [ci for ci in presentes if ci not in participantes_reserva]
        if desconocidos:
            raise HTTPException(
                status_code=422,
                detail=f"Las CIs {', '.join(desconocidos)} no pertenecen a la reserva.",
            )

        # 3) Marcar asistencia: primero todos en FALSE, luego los presentes en TRUE
        cur.execute(
            "UPDATE reserva_participante SET asistencia = FALSE WHERE id_reserva = %s",
            (id_reserva,),
        )
        if presentes:
            placeholders = ",".join(["%s"] * len(presentes))
            params = tuple(presentes) + (id_reserva,)
            cur.execute(
                f"""
                UPDATE reserva_participante
                SET asistencia = TRUE
                WHERE ci_participante IN ({placeholders})
                  AND id_reserva = %s
                """,
                params,
            )

        # 4) Contar cuántos asistieron
        cur.execute(
            """
            SELECT COUNT(*) AS asistentes
            FROM reserva_participante
            WHERE id_reserva = %s
              AND asistencia = TRUE
            """,
            (id_reserva,),
        )
        asistentes = cur.fetchone()["asistentes"] or 0

        ausentes = participantes_reserva - presentes
        nuevo_estado = "finalizada" if asistentes > 0 else "sin_asistencia"

        # 5) Actualizar estado de la reserva
        cur.execute(
            "UPDATE reserva SET estado = %s WHERE id_reserva = %s",
            (nuevo_estado, id_reserva),
        )

        # 6) Sancionar ausentes según configuración (2 meses)
        if payload.sancionar_ausentes and ausentes:
            cur.executemany(
                """
                INSERT IGNORE INTO sancion_participante (ci_participante, fecha_inicio, fecha_fin)
                VALUES (%s, %s, DATE_ADD(%s, INTERVAL 2 MONTH))
                """,
                [(ci, reserva["fecha"], reserva["fecha"]) for ci in ausentes],
            )

        conn.commit()

        # 7) Devolver la reserva actualizada
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
            raise HTTPException(status_code=500, detail="No se pudo recuperar la reserva actualizada.")
        return row
    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error registrando asistencia: {e}")
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

# ==========================
#  PARTICIPANTES - ABM
# ==========================

@app.get("/participantes", response_model=List[ParticipanteBase])
def listar_participantes():
    """
    Lista todos los participantes.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ci, nombre, apellido, email, tipo_participante
            FROM participante
            ORDER BY apellido, nombre
            """
        )
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listando participantes: {e}",
        )
    finally:
        conn.close()


@app.get("/participantes/{ci}", response_model=ParticipanteBase)
def obtener_participante(ci: str = Path(..., description="CI del participante")):
    """
    Devuelve un participante por CI.
    """
    ci = normalize_ci(ci)
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ci, nombre, apellido, email, tipo_participante
            FROM participante
            WHERE ci = %s
            """,
            (ci,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Participante no encontrado")
        return row
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error buscando participante: {e}",
        )
    finally:
        conn.close()


@app.post("/participantes", response_model=ParticipanteBase, status_code=201)
def crear_participante(p: ParticipanteCreate):
    """
    Alta de participante.

    - Falla con 409 si la CI o el email ya existen.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO participante (ci, nombre, apellido, email, tipo_participante)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (p.ci, p.nombre, p.apellido, p.email, p.tipo_participante),
        )
        conn.commit()
        return p
    except mysql.connector.Error as e:
        # 1062 = duplicate entry
        if e.errno == 1062:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un participante con esa CI o email",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error creando participante: {e}",
        )
    finally:
        conn.close()


@app.put("/participantes/{ci}", response_model=ParticipanteBase)
def actualizar_participante(
    ci: str = Path(..., description="CI del participante a actualizar"),
    p: ParticipanteUpdate = ...,
):
    """
    Actualiza nombre, apellido y email de un participante existente.
    La CI se toma de la ruta y no se cambia.
    """
    ci = normalize_ci(ci)
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        # Verificar que exista
        cur.execute(
            "SELECT ci FROM participante WHERE ci = %s",
            (ci,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Participante no encontrado")

        # Actualizar datos
        cur.execute(
            """
            UPDATE participante
            SET nombre = %s,
                apellido = %s,
                email = %s,
                tipo_participante = %s
            WHERE ci = %s
            """,
            (p.nombre, p.apellido, p.email, p.tipo_participante, ci),
        )
        conn.commit()

        return {
            "ci": ci,
            "nombre": p.nombre,
            "apellido": p.apellido,
            "email": p.email,
            "tipo_participante": p.tipo_participante,
        }
    except mysql.connector.Error as e:
        if e.errno == 1062:
            # email duplicado
            raise HTTPException(
                status_code=409,
                detail="Ya existe otro participante con ese email",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando participante: {e}",
        )
    finally:
        conn.close()


@app.delete("/participantes/{ci}")
def eliminar_participante(ci: str = Path(..., description="CI del participante a eliminar")):
    """
    Elimina un participante.

    - 404 si no existe.
    - 409 si tiene reservas, programas o sanciones asociadas (violación de FK).
    """
    ci = normalize_ci(ci)
    conn = get_conn()
    try:
        cur = conn.cursor()

        bloqueos = []
        cur.execute("SELECT COUNT(*) FROM reserva_participante WHERE ci_participante = %s", (ci,))
        if (cur.fetchone() or [0])[0]:
            bloqueos.append("tiene reservas asociadas")

        cur.execute("SELECT COUNT(*) FROM sancion_participante WHERE ci_participante = %s", (ci,))
        if (cur.fetchone() or [0])[0]:
            bloqueos.append("tiene sanciones asociadas")

        cur.execute(
            "SELECT COUNT(*) FROM participante_programa_academico WHERE ci_participante = %s",
            (ci,),
        )
        if (cur.fetchone() or [0])[0]:
            bloqueos.append("está vinculado a programas académicos")

        if bloqueos:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede eliminar el participante porque {', '.join(bloqueos)}",
            )

        cur.execute(
            "DELETE FROM participante WHERE ci = %s",
            (ci,),
        )
        conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Participante no encontrado")

        return {"detail": "Participante eliminado"}
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando participante: {e}",
        )
    finally:
        conn.close()

# ==========================
#  SANCIONES
# ==========================


@app.get("/sanciones", response_model=List[SancionBase])
def listar_sanciones(ci: str | None = Query(None, description="Filtrar por CI")):
    """
    Devuelve sanciones vigentes o históricas de participantes.
    """

    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        if ci:
            ci = normalize_ci(ci)
            cur.execute(
                """
                SELECT ci_participante, fecha_inicio, fecha_fin
                FROM sancion_participante
                WHERE ci_participante = %s
                ORDER BY fecha_inicio DESC
                """,
                (ci,),
            )
        else:
            cur.execute(
                """
                SELECT ci_participante, fecha_inicio, fecha_fin
                FROM sancion_participante
                ORDER BY fecha_inicio DESC
                """
            )
        rows = cur.fetchall()
        return [
            {
                "ci": row["ci_participante"],
                "fecha_inicio": row["fecha_inicio"],
                "fecha_fin": row["fecha_fin"],
            }
            for row in rows
        ]
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando sanciones: {e}")
    finally:
        conn.close()


@app.post("/sanciones", response_model=SancionBase, status_code=201)
def crear_sancion(payload: SancionCreate):
    """Crea una sanción manual para un participante."""

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sancion_participante (ci_participante, fecha_inicio, fecha_fin)
            VALUES (%s, %s, %s)
            """,
            (payload.ci, payload.fecha_inicio, payload.fecha_fin),
        )
        conn.commit()
        return payload.model_dump(by_alias=True)
    except mysql.connector.Error as e:
        if e.errno == 1452:
            raise HTTPException(
                status_code=404,
                detail="Participante no encontrado para sanción",
            )
        if e.errno == 1062:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una sanción con la misma fecha de inicio para este participante",
            )
        raise HTTPException(status_code=500, detail=f"Error creando sanción: {e}")
    finally:
        conn.close()


@app.put("/sanciones/{ci}/{fecha_inicio}", response_model=SancionBase)
def actualizar_sancion(
    ci: str = Path(..., description="CI del participante"),
    fecha_inicio: date = Path(..., description="Fecha de inicio original"),
    payload: SancionUpdate = ...,
):
    """Actualiza la fecha de fin de una sanción existente."""

    ci = normalize_ci(ci)
    if payload.fecha_fin <= fecha_inicio:
        raise HTTPException(status_code=422, detail="fecha_fin debe ser posterior a fecha_inicio")

    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT ci_participante, fecha_inicio, fecha_fin
            FROM sancion_participante
            WHERE ci_participante = %s AND fecha_inicio = %s
            """,
            (ci, fecha_inicio),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sanción no encontrada")

        cur.execute(
            """
            UPDATE sancion_participante
            SET fecha_fin = %s
            WHERE ci_participante = %s AND fecha_inicio = %s
            """,
            (payload.fecha_fin, ci, fecha_inicio),
        )
        conn.commit()

        return {
            "ci": ci,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": payload.fecha_fin,
        }
    except HTTPException:
        raise
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando sanción: {e}")
    finally:
        conn.close()


@app.delete("/sanciones/{ci}/{fecha_inicio}", status_code=204)
def eliminar_sancion(
    ci: str = Path(..., description="CI del participante"),
    fecha_inicio: date = Path(..., description="Fecha de inicio de la sanción"),
):
    """Elimina una sanción manual."""

    ci = normalize_ci(ci)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM sancion_participante WHERE ci_participante = %s AND fecha_inicio = %s",
            (ci, fecha_inicio),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Sanción no encontrada")
        return
    except HTTPException:
        raise
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando sanción: {e}")
    finally:
        conn.close()

# ==========================
#  REPORTES - BI
# ==========================

@app.get(
    "/reportes/salas-mas-usadas",
    response_model=List[ReportSalaUso],
)
def report_salas_mas_usadas(
    limit: int = Query(10, ge=1, le=100, description="Cantidad máxima de salas a devolver"),
    desde: str | None = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    hasta: str | None = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
):
    """
    Devuelve las salas con más reservas (activa/finalizada/sin_asistencia),
    opcionalmente filtrando por rango de fechas.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        conditions = ["r.estado IN ('activa','finalizada','sin_asistencia')"]
        params: list[Any] = []

        if desde:
            conditions.append("r.fecha >= %s")
            params.append(desde)
        if hasta:
            conditions.append("r.fecha <= %s")
            params.append(hasta)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
              r.edificio,
              r.nombre_sala,
              COUNT(*) AS total_reservas
            FROM reserva r
            WHERE {where_clause}
            GROUP BY r.edificio, r.nombre_sala
            ORDER BY total_reservas DESC, r.edificio, r.nombre_sala
            LIMIT %s
        """
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando reporte de salas más usadas: {e}",
        )
    finally:
        conn.close()

@app.get(
    "/reportes/ocupacion-por-edificio",
    response_model=List[ReportOcupacionEdificio],
)
def report_ocupacion_por_edificio(
    desde: str | None = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    hasta: str | None = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
):
    """
    Devuelve, por edificio:
    - total de reservas (activa/finalizada/sin_asistencia)
    - porcentaje que representan sobre el total de reservas.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        conditions = ["r.estado IN ('activa','finalizada','sin_asistencia')"]
        params: list[Any] = []

        if desde:
            conditions.append("r.fecha >= %s")
            params.append(desde)
        if hasta:
            conditions.append("r.fecha <= %s")
            params.append(hasta)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
              r.edificio,
              COUNT(*) AS total_reservas
            FROM reserva r
            WHERE {where_clause}
            GROUP BY r.edificio
            ORDER BY total_reservas DESC, r.edificio
        """

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        total = sum(r["total_reservas"] for r in rows) or 0
        for r in rows:
            if total == 0:
                r["porcentaje_sobre_total"] = 0.0
            else:
                r["porcentaje_sobre_total"] = round(
                    100.0 * r["total_reservas"] / total, 2
                )

        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando reporte de ocupación por edificio: {e}",
        )
    finally:
        conn.close()

@app.get(
    "/reportes/uso-por-rol",
    response_model=List[ReportUsoPorRol],
)
def report_uso_por_rol(
    desde: str | None = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    hasta: str | None = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
):
    """
    Devuelve, por rol (alumno/docente) y tipo de programa (grado/posgrado),
    cuántas reservas realizaron.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        conditions = ["r.estado IN ('activa','finalizada','sin_asistencia')"]
        params: list[Any] = []

        if desde:
            conditions.append("r.fecha >= %s")
            params.append(desde)
        if hasta:
            conditions.append("r.fecha <= %s")
            params.append(hasta)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
              ppa.rol,
              pa.tipo AS tipo_programa,
              COUNT(*) AS total_reservas
            FROM reserva r
            JOIN reserva_participante rp
              ON rp.id_reserva = r.id_reserva
            JOIN participante_programa_academico ppa
              ON ppa.ci_participante = rp.ci_participante
            JOIN programa_academico pa
              ON pa.nombre_programa = ppa.nombre_programa
            WHERE {where_clause}
            GROUP BY ppa.rol, pa.tipo
            ORDER BY total_reservas DESC, ppa.rol, pa.tipo
        """

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando reporte de uso por rol: {e}",
        )
    finally:
        conn.close()