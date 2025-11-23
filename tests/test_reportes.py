from src import app as app_module


class _FakeCursorReport:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params=None):
        self.query = query

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        pass


class _FakeConnReport:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, dictionary=False):
        return _FakeCursorReport(self.rows)

    def close(self):
        self.closed = True


def _setup(monkeypatch, rows):
    monkeypatch.setattr(app_module, "get_conn", lambda: _FakeConnReport(rows))


def test_reporte_turnos_mas_demandados(monkeypatch):
    rows = [{"id_turno": 1, "hora_inicio": "08:00:00", "hora_fin": "09:00:00", "total_reservas": 12}]
    _setup(monkeypatch, rows)
    data = app_module.report_turnos_mas_demandados()
    assert data[0]["id_turno"] == 1
    assert "total_reservas" in data[0]


def test_reporte_salas_mas_usadas(monkeypatch):
    rows = [
        {"nombre_sala": "Sala 1", "edificio": "Central", "total_reservas": 5, "total_participantes": 10}
    ]
    _setup(monkeypatch, rows)
    data = app_module.report_salas_mas_usadas()
    assert data[0]["nombre_sala"] == "Sala 1"


def test_reporte_promedio_participantes(monkeypatch):
    rows = [{"nombre_sala": "Sala 1", "edificio": "Central", "promedio_participantes": 3.5}]
    _setup(monkeypatch, rows)
    data = app_module.report_promedio_participantes_por_sala()
    assert data[0]["promedio_participantes"] == 3.5


def test_reporte_reservas_por_carrera(monkeypatch):
    rows = [{"id_facultad": 1, "nombre_programa": "Ing", "total_reservas": 2}]
    _setup(monkeypatch, rows)
    data = app_module.report_reservas_por_carrera_facultad()
    assert data[0]["total_reservas"] == 2


def test_reporte_ocupacion_por_edificio(monkeypatch):
    rows = [{"edificio": "Central", "total_reservas": 10, "porcentaje_ocupacion": 50.0}]
    _setup(monkeypatch, rows)
    data = app_module.report_ocupacion_por_edificio()
    assert data[0]["edificio"] == "Central"


def test_reporte_reservas_asistencias_por_rol(monkeypatch):
    rows = [{"rol": "alumno", "tipo_programa": "grado", "total_reservas": 3, "con_asistencia": 2, "sin_asistencia": 1, "canceladas": 0}]
    _setup(monkeypatch, rows)
    data = app_module.report_reservas_y_asistencias_por_rol()
    assert data[0]["rol"] == "alumno"


def test_reporte_sanciones_por_rol(monkeypatch):
    rows = [{"rol": "docente", "tipo_programa": "grado", "total_sanciones": 1}]
    _setup(monkeypatch, rows)
    data = app_module.report_sanciones_por_rol()
    assert data[0]["total_sanciones"] == 1


def test_reporte_efectividad(monkeypatch):
    rows = [
        {"estado": "finalizada", "total": 5},
        {"estado": "cancelada", "total": 2},
        {"estado": "sin_asistencia", "total": 1},
    ]
    _setup(monkeypatch, rows)
    data = app_module.report_efectividad_reservas()
    assert data["total_reservas"] == 8
    assert data["porcentaje_canceladas"] > 0


def test_reporte_uso_por_rol(monkeypatch):
    rows = [{"rol": "docente", "tipo_programa": "posgrado", "total_reservas": 4}]
    _setup(monkeypatch, rows)
    data = app_module.report_uso_por_rol()
    assert data[0]["total_reservas"] == 4


def test_reporte_top_participantes(monkeypatch):
    rows = [{"ci_participante": "50000001", "total_reservas": 6}]
    _setup(monkeypatch, rows)
    data = app_module.report_top_participantes()
    assert data[0]["ci_participante"] == "50000001"


def test_reporte_salas_no_show(monkeypatch):
    rows = [{"edificio": "Central", "nombre_sala": "Sala 1", "total_sin_asistencia": 2}]
    _setup(monkeypatch, rows)
    data = app_module.report_salas_no_show()
    assert data[0]["total_sin_asistencia"] == 2


def test_reporte_distribucion_semana_turno(monkeypatch):
    rows = [{"dia_semana": "Monday", "id_turno": 1, "total_reservas": 3}]
    _setup(monkeypatch, rows)
    data = app_module.report_distribucion_semana_turno()
    assert data[0]["dia_semana"] == "Monday"
