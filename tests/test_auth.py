from fastapi.testclient import TestClient

from src import app as app_module


class _DummyConn:
    def close(self):
        pass


def test_auth_login_returns_participante(monkeypatch):
    # Mock DB access to avoid real connection during CI runs
    monkeypatch.setattr(app_module, "get_conn", lambda: _DummyConn())
    monkeypatch.setattr(
        app_module,
        "_fetch_participante",
        lambda conn, ci: {
            "ci": "41234567",
            "nombre": "Matihas",
            "apellido": "Sastre",
            "email": "matihas.sastre@ucu.edu.uy",
            "tipo_participante": "estudiante",
            "es_admin": False,
        },
    )

    client = TestClient(app_module.app)
    response = client.post("/auth/login", json={"ci": "41234567"})

    assert response.status_code == 200
    assert response.json()["ci"] == "41234567"
    assert response.json()["nombre"] == "Matihas"
