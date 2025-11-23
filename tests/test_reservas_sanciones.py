from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from src import app as app_module


class _FakeCursorAsistencia:
    def __init__(self):
        self._next_one = None
        self._next_all = []

    def execute(self, query, params=None):
        if "FROM reserva" in query and "reserva_participante" not in query and "id_turno" not in query:
            self._next_one = {"id_reserva": params[0], "fecha": date(2024, 1, 10), "estado": "activa"}
        elif "FROM reserva_participante" in query and "COUNT" not in query:
            self._next_all = [{"ci_participante": "50000001"}]
        elif "COUNT(*) AS asistentes" in query:
            self._next_one = {"asistentes": 0}
        elif "SELECT id_reserva," in query and "id_turno" in query:
            self._next_one = {
                "id_reserva": params[0],
                "nombre_sala": "Sala A-001",
                "edificio": "Sede Central",
                "fecha": date(2024, 1, 10),
                "id_turno": 1,
                "estado": "sin_asistencia",
            }
        else:
            self._next_one = None
            self._next_all = []

    def fetchone(self):
        return self._next_one

    def fetchall(self):
        return self._next_all

    def close(self):
        pass


class _FakeConnAsistencia:
    def __init__(self):
        self.cursor_obj = _FakeCursorAsistencia()
        self.committed = False

    def cursor(self, dictionary=False):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_asistencia_sin_presentes_crea_sancion(monkeypatch):
    calls = {}
    monkeypatch.setattr(app_module, "get_reservas_connection", lambda: _FakeConnAsistencia())

    def _fake_crear(conn, id_reserva, presentes=None):
        calls["reserva"] = id_reserva
        calls["presentes"] = set(presentes or [])

    monkeypatch.setattr(app_module, "crear_sanciones_por_ausencia", _fake_crear)

    resp = app_module.registrar_asistencia(1, app_module.AsistenciaIn(presentes=[], sancionar_ausentes=True))

    assert resp["reserva"]["estado"] == "sin_asistencia"
    assert calls["reserva"] == 1
    assert calls["presentes"] == set()


class _FakeCursorUpdate:
    def __init__(self):
        self._next_one = None

    def execute(self, query, params=None):
        if "SELECT id_reserva" in query:
            self._next_one = {
                "id_reserva": params[0],
                "nombre_sala": "Sala A-002",
                "edificio": "Campus Pocitos",
                "fecha": date(2024, 2, 2),
                "id_turno": 2,
                "estado": "activa",
            }
        else:
            self._next_one = None

    def fetchone(self):
        return self._next_one

    def close(self):
        pass


class _FakeConnUpdate:
    def __init__(self):
        self.cursor_obj = _FakeCursorUpdate()

    def cursor(self, dictionary=False):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_cambio_estado_a_sin_asistencia_sanciona(monkeypatch):
    calls = {}
    monkeypatch.setattr(app_module, "get_reservas_connection", lambda: _FakeConnUpdate())

    def _fake_crear(conn, id_reserva, presentes=None):
        calls["reserva"] = id_reserva

    monkeypatch.setattr(app_module, "crear_sanciones_por_ausencia", _fake_crear)

    resp = app_module.update_reserva_estado(5, app_module.ReservaEstadoIn(estado="sin_asistencia"))

    assert resp["reserva"]["estado"] == "sin_asistencia"
    assert calls["reserva"] == 5


class _FakeCursorReserva:
    def __init__(self):
        self._next_one = None
        self._next_all = []

    def execute(self, query, params=None):
        if "FROM sala" in query:
            self._next_one = {"capacidad": 6, "tipo_sala": "docente"}
        elif "FROM turno" in query:
            self._next_one = {"id_turno": params[0], "hora_inicio": "08:00:00", "hora_fin": "09:00:00"}
        elif "FROM participante p" in query:
            self._next_all = [
                {
                    "ci": params[0] if isinstance(params, tuple) else params,
                    "tipo_participante": "docente",
                    "es_docente_posgrado": 0,
                    "es_alumno_posgrado": 0,
                }
            ]
        elif "FROM sancion_participante" in query:
            ci_val = params[0] if isinstance(params, tuple) else params
            self._next_all = [
                {"ci_participante": ci_val, "fecha_inicio": date.today(), "fecha_fin": date.today() + timedelta(days=5)}
            ]
        else:
            self._next_one = None
            self._next_all = []

    def fetchone(self):
        return self._next_one

    def fetchall(self):
        return self._next_all

    def close(self):
        pass


class _FakeConnReserva:
    def __init__(self):
        self.cursor_obj = _FakeCursorReserva()

    def cursor(self, dictionary=False):
        return self.cursor_obj

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_reserva_rechazada_por_sancion_activa(monkeypatch):
    monkeypatch.setattr(app_module, "get_reservas_connection", lambda: _FakeConnReserva())

    payload = app_module.ReservaIn(
        nombre_sala="Sala A-001",
        edificio="Sede Central",
        fecha=date.today(),
        id_turno=1,
        participantes=["50000001"],
    )

    with pytest.raises(HTTPException) as excinfo:
        app_module.create_reserva(payload)

    assert "sanción activa" in str(excinfo.value.detail)
